from flask import request, jsonify, g
from models.diary import (
    upsert_diary,
    get_diary_by_date_range,
    get_month_diaries_by_date_range,
    delete_diary_by_date_range,
    get_all_diaries
)
from middleware.user_required import user_required
from utils.timezone import format_datetime_for_response, convert_user_date_to_utc_range, convert_user_month_to_utc_range, convert_user_date_to_utc_date_string
import datetime
from pinecone import Pinecone
from openai import OpenAI
import os

pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index("diarydad")
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def create_embedding(text):
    """Create embedding using OpenAI text-embedding-3-small model"""
    try:
        response = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        raise Exception(f"Failed to create embedding: {str(e)}")

def prepare_text_for_embedding(diary_obj, mood_tracker=None, expense_tracker=None, health_stats=None, date=None):
    """Prepare text content from diary entry for embedding"""
    text_parts = []
    
    text_parts.append(f"Date: {date}")
    # Add diary content and summary
    if diary_obj:
        if isinstance(diary_obj, dict):
            if "content" in diary_obj and diary_obj["content"]:
                text_parts.append(f"Content: {diary_obj['content']}")
    
    # Add mood tracker
    if mood_tracker and isinstance(mood_tracker, list) and len(mood_tracker) > 0:
        text_parts.append(f"Moods: {', '.join(mood_tracker)}")
    
    # Add expense tracker summary
    if expense_tracker and isinstance(expense_tracker, list) and len(expense_tracker) > 0:
        expense_summary = []
        for item in expense_tracker:
            if isinstance(item, dict) and "name" in item:
                expense_summary.append(item["name"])
        if expense_summary:
            text_parts.append(f"Expenses: {', '.join(expense_summary)}")
    
    # Add health stats summary
    if health_stats and isinstance(health_stats, list) and len(health_stats) > 0:
        health_summary = []
        for item in health_stats:
            if isinstance(item, dict) and "name" in item and "value" in item:
                health_summary.append(f"{item['name']}: {item['value']}")
        if health_summary:
            text_parts.append(f"Health: {', '.join(health_summary)}")
    
    # Join all parts
    combined_text = " | ".join(text_parts)
    
    # Return a default text if empty to ensure we always have something to embed
    return combined_text if combined_text else "Diary entry"

def upsert_to_pinecone(user_id, date, diary_obj, mood_tracker, expense_tracker, health_stats):
    """Upsert diary entry to Pinecone vector database"""
    try:
        # Prepare text for embedding
        text_to_embed = prepare_text_for_embedding(diary_obj, mood_tracker, expense_tracker, health_stats, date)
        
        # Create embedding
        embedding = create_embedding(text_to_embed)
        
        # Create unique vector ID (user_id_date)
        vector_id = f"{user_id}_{date}"
        
        # Prepare metadata
        metadata = {
            "user_id": user_id,
            "date": date,
            "text": text_to_embed
        }
        
        # Add diary content to metadata if available
        if diary_obj and isinstance(diary_obj, dict):
            if "content" in diary_obj:
                metadata["content"] = diary_obj["content"][:1000]  # Limit metadata size
        
        # Upsert to Pinecone
        index.upsert(
            vectors=[{
                "id": vector_id,
                "values": embedding,
                "metadata": metadata
            }]
        )
        
    except Exception as e:
        # Log error but don't fail the main request
        print(f"Warning: Failed to upsert to Pinecone: {str(e)}")

@user_required
def upsert_diary_entry():
    """Create or update a diary entry (upsert) - everything stored in UTC"""
    data = request.get_json()
    user_id = str(g.current_user["_id"])
    
    # Get user's timezone from profile
    user_timezone = g.current_user.get("timezone", "UTC")
    
    # Get date from request body (optional)
    date_input = data.get("date")
    
    if date_input:
        # Validate date format
        try:
            datetime.datetime.strptime(date_input, "%d-%m-%Y")
        except ValueError:
            return jsonify({"error": "date must be in DD-MM-YYYY format."}), 400
        
        # Convert user's date to UTC date string
        date = convert_user_date_to_utc_date_string(date_input, user_timezone)
    else:
        # Use current UTC date if not provided
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        date = now_utc.strftime("%d-%m-%Y")
    
    # Extract diary object (containing content and summary)
    diary_obj = data.get("diary")
    mood_tracker = data.get("mood_tracker")
    expense_tracker = data.get("expense_tracker")
    health_stats = data.get("health_stats")
    
    # Validate diary object (should contain content and/or summary)
    if diary_obj is not None:
        if not isinstance(diary_obj, dict):
            return jsonify({"error": "diary must be an object."}), 400
        if "content" in diary_obj and not isinstance(diary_obj["content"], str):
            return jsonify({"error": "diary.content must be a string."}), 400
    
    # Validate mood_tracker (array of strings, max 5)
    if mood_tracker is not None:
        if not isinstance(mood_tracker, list):
            return jsonify({"error": "mood_tracker must be an array."}), 400
        if len(mood_tracker) > 5:
            return jsonify({"error": "mood_tracker can have maximum 5 items."}), 400
        if not all(isinstance(item, str) for item in mood_tracker):
            return jsonify({"error": "All items in mood_tracker must be strings."}), 400
    
    # Validate expense_tracker (array of objects with name, description, amount)
    if expense_tracker is not None:
        if not isinstance(expense_tracker, list):
            return jsonify({"error": "expense_tracker must be an array."}), 400
        for item in expense_tracker:
            if not isinstance(item, dict):
                return jsonify({"error": "All items in expense_tracker must be objects."}), 400
            if "name" not in item or "amount" not in item:
                return jsonify({"error": "Each expense_tracker item must have name and amount."}), 400
            if not isinstance(item["amount"], (int, float)):
                return jsonify({"error": "amount must be a number."}), 400
    
    # Validate health_stats (array of objects with name, description, value, unit)
    if health_stats is not None:
        if not isinstance(health_stats, list):
            return jsonify({"error": "health_stats must be an array."}), 400
        for item in health_stats:
            if not isinstance(item, dict):
                return jsonify({"error": "All items in health_stats must be objects."}), 400
            if "name" not in item or "description" not in item or "value" not in item or "unit" not in item:
                return jsonify({"error": "Each health_stats item must have name, description, value, and unit."}), 400
            if not isinstance(item["value"], (int, float)):
                return jsonify({"error": "value must be a number."}), 400
    
    try:
        result = upsert_diary(user_id, date, diary_obj, mood_tracker, expense_tracker, health_stats)
        
        # Embed and store in Pinecone vector database
        # Only embed if there's meaningful content to embed
        print("Checking if there's meaningful content to embed")
        if diary_obj or mood_tracker or expense_tracker or health_stats:
            print("Embedding and storing in Pinecone vector database")
            upsert_to_pinecone(user_id, date, diary_obj, mood_tracker, expense_tracker, health_stats)
            print("Embedding and storing in Pinecone vector database completed")
        
        if result["upserted"]:
            return jsonify({
                "message": "Diary entry created successfully.",
                "date": date,
                "id": str(result["result"].inserted_id)
            }), 201
        else:
            return jsonify({
                "message": "Diary entry updated successfully.",
                "date": date
            }), 200
        

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@user_required
def get_diary_entry():
    """Get a diary entry by date - converts user's date to UTC range and queries by created_at"""
    date = request.args.get("date")
    user_id = str(g.current_user["_id"])
    
    if not date:
        return jsonify({"error": "date is required as query parameter."}), 400
    
    try:
        datetime.datetime.strptime(date, "%d-%m-%Y")
    except ValueError:
        return jsonify({"error": "date must be in DD-MM-YYYY format."}), 400
    
    # Get user's timezone from profile
    user_timezone = g.current_user.get("timezone", "UTC")
    
    # Convert user's date to UTC date range
    start_utc, end_utc = convert_user_date_to_utc_range(date, user_timezone)
    
    try:
        diary = get_diary_by_date_range(user_id, start_utc, end_utc)
        if diary:
            # Convert ObjectId to string for JSON serialization
            diary["_id"] = str(diary["_id"])
            diary["user_id"] = str(diary["user_id"])
            
            # Convert timestamps to user's timezone for response
            if "created_at" in diary:
                diary["created_at"] = format_datetime_for_response(diary["created_at"], user_timezone)
            if "last_update" in diary:
                diary["last_update"] = format_datetime_for_response(diary["last_update"], user_timezone)
            if "update_log" in diary and isinstance(diary["update_log"], list):
                for log_entry in diary["update_log"]:
                    if "timestamp" in log_entry:
                        log_entry["timestamp"] = format_datetime_for_response(log_entry["timestamp"], user_timezone)
            
            return jsonify({"diary": diary}), 200
        else:
            return jsonify({"error": "No diary found for this date."}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@user_required
def delete_diary_entry():
    """Delete a diary entry by date - converts user's date to UTC range and queries by created_at"""
    date = request.args.get("date")
    user_id = str(g.current_user["_id"])
    
    if not date:
        return jsonify({"error": "date is required as query parameter."}), 400
    
    try:
        datetime.datetime.strptime(date, "%d-%m-%Y")
    except ValueError:
        return jsonify({"error": "date must be in DD-MM-YYYY format."}), 400
    
    # Get user's timezone from profile
    user_timezone = g.current_user.get("timezone", "UTC")
    
    # Convert user's date to UTC date range
    start_utc, end_utc = convert_user_date_to_utc_range(date, user_timezone)
    
    try:
        result = delete_diary_by_date_range(user_id, start_utc, end_utc)
        if result.deleted_count > 0:
            return jsonify({"message": "Diary entry deleted successfully."}), 200
        else:
            return jsonify({"error": "No diary found for this date."}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@user_required
def get_month_diaries_entries():
    """Get all diary entries for current month - converts user's month to UTC range and queries by created_at"""
    user_id = str(g.current_user["_id"])
    
    # Get user's timezone from profile
    user_timezone = g.current_user.get("timezone", "UTC")
    
    # Get current year and month in user's timezone
    import pytz
    try:
        user_tz = pytz.timezone(user_timezone)
    except pytz.exceptions.UnknownTimeZoneError:
        user_tz = pytz.UTC
    
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    now_user_tz = now_utc.astimezone(user_tz)
    year = now_user_tz.year
    month = now_user_tz.month
    
    # Convert user's month to UTC date range
    start_utc, end_utc = convert_user_month_to_utc_range(year, month, user_timezone)
    
    try:
        diaries = get_month_diaries_by_date_range(user_id, start_utc, end_utc)
        # Convert ObjectIds to strings and timestamps to user timezone
        for diary in diaries:
            diary["_id"] = str(diary["_id"])
            diary["user_id"] = str(diary["user_id"])
            
            # Convert timestamps to user's timezone for response
            if "created_at" in diary:
                diary["created_at"] = format_datetime_for_response(diary["created_at"], user_timezone)
            if "last_update" in diary:
                diary["last_update"] = format_datetime_for_response(diary["last_update"], user_timezone)
            if "update_log" in diary and isinstance(diary["update_log"], list):
                for log_entry in diary["update_log"]:
                    if "timestamp" in log_entry:
                        log_entry["timestamp"] = format_datetime_for_response(log_entry["timestamp"], user_timezone)
        
        return jsonify({"diaries": diaries}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@user_required
def get_all_diaries_entries():
    """Get all diary entries for the user"""
    user_id = str(g.current_user["_id"])
    
    try:
        diaries = get_all_diaries(user_id)
        # Convert ObjectIds to strings and timestamps to user timezone
        user_timezone = g.current_user.get("timezone", "UTC")
        
        for diary in diaries:
            diary["_id"] = str(diary["_id"])
            diary["user_id"] = str(diary["user_id"])
            
            # Convert timestamps to user's timezone for response
            if "created_at" in diary:
                diary["created_at"] = format_datetime_for_response(diary["created_at"], user_timezone)
            if "last_update" in diary:
                diary["last_update"] = format_datetime_for_response(diary["last_update"], user_timezone)
            if "update_log" in diary and isinstance(diary["update_log"], list):
                for log_entry in diary["update_log"]:
                    if "timestamp" in log_entry:
                        log_entry["timestamp"] = format_datetime_for_response(log_entry["timestamp"], user_timezone)
        
        return jsonify({"diaries": diaries}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
