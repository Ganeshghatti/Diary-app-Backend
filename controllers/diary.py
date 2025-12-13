from flask import request, jsonify, g
from models.diary import (
    upsert_diary,
    get_diary_by_local_date,
    get_month_diaries_by_local_date,
    delete_diary_by_local_date,
    get_all_diaries,
    get_all_diaries_count
)
from middleware.user_required import user_required
import datetime
import pytz
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

def prepare_text_for_embedding(diary_obj, mood_tracker=None, expense_tracker=None, health_stats=None, local_date=None):
    """Prepare text content from diary entry for embedding"""
    text_parts = []
    
    text_parts.append(f"Date: {local_date}")
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

def upsert_to_pinecone(user_id, local_date, diary_obj, mood_tracker, expense_tracker, health_stats):
    """Upsert diary entry to Pinecone vector database"""
    try:
        # Prepare text for embedding
        text_to_embed = prepare_text_for_embedding(diary_obj, mood_tracker, expense_tracker, health_stats, local_date)
        
        # Create embedding
        embedding = create_embedding(text_to_embed)
        
        # Create unique vector ID (user_id_local_date)
        vector_id = f"{user_id}_{local_date}"
        
        # Prepare metadata
        metadata = {
            "user_id": user_id,
            "date": local_date,  # Keep "date" key for backward compatibility with Pinecone
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
    """Create or update a diary entry (upsert)"""
    data = request.get_json()
    user_id = str(g.current_user["_id"])
    
    # Get timezone from user model
    timezone = g.current_user.get("timezone", "UTC")
    
    # Validate timezone
    try:
        pytz.timezone(timezone)
    except pytz.exceptions.UnknownTimeZoneError:
        return jsonify({"error": f"Invalid timezone: {timezone}"}), 400
    
    # Get date from request body (optional) - frontend uses "date" parameter
    date_input = data.get("date")
    
    if date_input:
        # Validate date format
        try:
            datetime.datetime.strptime(date_input, "%d-%m-%Y")
        except ValueError:
            return jsonify({"error": "date must be in DD-MM-YYYY format."}), 400
        
        local_date = date_input
    else:
        # Use current date in provided timezone if not provided
        try:
            user_tz = pytz.timezone(timezone)
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            now_user_tz = now_utc.astimezone(user_tz)
            local_date = now_user_tz.strftime("%d-%m-%Y")
        except:
            # Fallback to UTC if timezone invalid
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            local_date = now_utc.strftime("%d-%m-%Y")
    
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
        result = upsert_diary(user_id, local_date, timezone, diary_obj, mood_tracker, expense_tracker, health_stats)
        
        # Embed and store in Pinecone vector database
        # Only embed if there's meaningful content to embed
        print("Checking if there's meaningful content to embed")
        if diary_obj or mood_tracker or expense_tracker or health_stats:
            print("Embedding and storing in Pinecone vector database")
            upsert_to_pinecone(user_id, local_date, diary_obj, mood_tracker, expense_tracker, health_stats)
            print("Embedding and storing in Pinecone vector database completed")
        
        if result["upserted"]:
            return jsonify({
                "message": "Diary entry created successfully.",
                "date": local_date,  # Return as "date" for frontend compatibility
                "timezone": timezone,
                "id": str(result["result"].inserted_id)
            }), 201
        else:
            return jsonify({
                "message": "Diary entry updated successfully.",
                "date": local_date,  # Return as "date" for frontend compatibility
                "timezone": timezone
            }), 200
        

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@user_required
def get_diary_entry():
    """Get a diary entry by date"""
    date = request.args.get("date")
    user_id = str(g.current_user["_id"])
    
    if not date:
        return jsonify({"error": "date is required as query parameter."}), 400
    
    try:
        datetime.datetime.strptime(date, "%d-%m-%Y")
    except ValueError:
        return jsonify({"error": "date must be in DD-MM-YYYY format."}), 400
    
    local_date = date  # Use date from request as local_date internally
    
    try:
        diary = get_diary_by_local_date(user_id, local_date)
        if diary:
            # Convert ObjectId to string for JSON serialization
            diary["_id"] = str(diary["_id"])
            diary["user_id"] = str(diary["user_id"])
            
            # Convert timestamps to ISO format for response
            if "created_at" in diary and isinstance(diary["created_at"], datetime.datetime):
                diary["created_at"] = diary["created_at"].isoformat()
            if "last_update" in diary and isinstance(diary["last_update"], datetime.datetime):
                diary["last_update"] = diary["last_update"].isoformat()
            if "update_log" in diary and isinstance(diary["update_log"], list):
                for log_entry in diary["update_log"]:
                    if "timestamp" in log_entry and isinstance(log_entry["timestamp"], datetime.datetime):
                        log_entry["timestamp"] = log_entry["timestamp"].isoformat()
            
            return jsonify({"diary": diary}), 200
        else:
            return jsonify({"error": "No diary found for this date."}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@user_required
def delete_diary_entry():
    """Delete a diary entry by date"""
    date = request.args.get("date")
    user_id = str(g.current_user["_id"])
    
    if not date:
        return jsonify({"error": "date is required as query parameter."}), 400
    
    try:
        datetime.datetime.strptime(date, "%d-%m-%Y")
    except ValueError:
        return jsonify({"error": "date must be in DD-MM-YYYY format."}), 400
    
    local_date = date  # Use date from request as local_date internally
    
    try:
        result = delete_diary_by_local_date(user_id, local_date)
        if result.deleted_count > 0:
            return jsonify({"message": "Diary entry deleted successfully."}), 200
        else:
            return jsonify({"error": "No diary found for this date."}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@user_required
def get_month_diaries_entries():
    """Get all diary entries for current month"""
    user_id = str(g.current_user["_id"])
    
    # Get year and month from query params (optional, defaults to current month in UTC)
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    
    if not year or not month:
        # Use current month in UTC if not provided
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        year = year or now_utc.year
        month = month or now_utc.month
    
    try:
        diaries = get_month_diaries_by_local_date(user_id, year, month)
        # Convert ObjectIds to strings and timestamps to ISO format
        for diary in diaries:
            diary["_id"] = str(diary["_id"])
            diary["user_id"] = str(diary["user_id"])
            
            # Convert timestamps to ISO format for response
            if "created_at" in diary and isinstance(diary["created_at"], datetime.datetime):
                diary["created_at"] = diary["created_at"].isoformat()
            if "last_update" in diary and isinstance(diary["last_update"], datetime.datetime):
                diary["last_update"] = diary["last_update"].isoformat()
            if "update_log" in diary and isinstance(diary["update_log"], list):
                for log_entry in diary["update_log"]:
                    if "timestamp" in log_entry and isinstance(log_entry["timestamp"], datetime.datetime):
                        log_entry["timestamp"] = log_entry["timestamp"].isoformat()
        
        return jsonify({"diaries": diaries}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@user_required
def get_all_diaries_entries():
    """Get all diary entries for the user with pagination (30 entries per page)"""
    user_id = str(g.current_user["_id"])
    
    # Get page number from query parameter (default to 1)
    try:
        page = int(request.args.get("page", 1))
        if page < 1:
            page = 1
    except (ValueError, TypeError):
        page = 1
    
    try:
        # Get paginated diaries
        diaries = get_all_diaries(user_id, page=page, limit=30)
        
        # Get total count for pagination metadata
        total_count = get_all_diaries_count(user_id)
        total_pages = (total_count + 29) // 30  # Ceiling division: (total + limit - 1) // limit
        
        # Convert ObjectIds to strings and timestamps to ISO format
        for diary in diaries:
            diary["_id"] = str(diary["_id"])
            diary["user_id"] = str(diary["user_id"])
            
            # Convert timestamps to ISO format for response
            if "created_at" in diary and isinstance(diary["created_at"], datetime.datetime):
                diary["created_at"] = diary["created_at"].isoformat()
            if "last_update" in diary and isinstance(diary["last_update"], datetime.datetime):
                diary["last_update"] = diary["last_update"].isoformat()
            if "update_log" in diary and isinstance(diary["update_log"], list):
                for log_entry in diary["update_log"]:
                    if "timestamp" in log_entry and isinstance(log_entry["timestamp"], datetime.datetime):
                        log_entry["timestamp"] = log_entry["timestamp"].isoformat()
        
        return jsonify({
            "diaries": diaries,
            "pagination": {
                "page": page,
                "limit": 30,
                "total": total_count,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
