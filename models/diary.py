import datetime
import pytz
from config.db import mongo
from bson import ObjectId

def upsert_diary(user_id, local_date, timezone, diary=None, mood_tracker=None, expense_tracker=None, health_stats=None):
    """Create or update a diary entry (upsert) - stores datetimes in local timezone (except created_at which is UTC)"""
    now_utc = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    
    # Get current datetime in user's local timezone
    try:
        user_tz = pytz.timezone(timezone)
        now_local = datetime.datetime.now(user_tz).replace(tzinfo=None)
    except:
        # Fallback to UTC if timezone invalid
        now_local = now_utc
    
    # Check if diary exists by local_date
    existing = mongo.db.diaries.find_one({"user_id": ObjectId(user_id), "local_date": local_date})
    
    if existing:
        # Update existing diary - append to update_log
        update_data = {
            "last_update": now_local,  # Local timezone
            "timezone": timezone  # Update timezone snapshot
        }
        
        # Add to update log array (local timezone)
        update_log_entry = {"timestamp": now_local}
        mongo.db.diaries.update_one(
            {"user_id": ObjectId(user_id), "local_date": local_date},
            {"$push": {"update_log": update_log_entry}}
        )
        
        if diary is not None:
            existing_diary = existing.get("diary", {})
            if not isinstance(existing_diary, dict):
                existing_diary = {}
            update_data["diary"] = {**existing_diary, **diary}
        if mood_tracker is not None:
            update_data["mood_tracker"] = mood_tracker
        if expense_tracker is not None:
            update_data["expense_tracker"] = expense_tracker
        if health_stats is not None:
            update_data["health_stats"] = health_stats
        
        result = mongo.db.diaries.update_one(
            {"user_id": ObjectId(user_id), "local_date": local_date},
            {"$set": update_data}
        )
        return {"upserted": False, "result": result}
    else:
        # Create new diary
        diary_data = {
            "user_id": ObjectId(user_id),
            "local_date": local_date,  # Local date string (DD-MM-YYYY)
            "timezone": timezone,  # Timezone snapshot
            "created_at": now_utc,  # UTC timestamp (always UTC)
            "last_update": now_local,  # Local timezone timestamp
            "update_log": [{"timestamp": now_local}],  # Local timezone timestamps
            "image_extraction_count": 0,  # Usage tracking for this day
            "speech_to_text_count": 0,  # Usage tracking for speech-to-text this day
            "summary_generation_count": 0  # Usage tracking for this day
        }
        
        if diary is not None:
            diary_data["diary"] = diary
        if mood_tracker is not None:
            diary_data["mood_tracker"] = mood_tracker
        if expense_tracker is not None:
            diary_data["expense_tracker"] = expense_tracker
        if health_stats is not None:
            diary_data["health_stats"] = health_stats
        
        result = mongo.db.diaries.insert_one(diary_data)
        return {"upserted": True, "result": result}

def get_or_create_today_diary(user_id, timezone="UTC"):
    """Get today's diary entry or create it if it doesn't exist"""
    now_utc = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    
    # Get current date in user's timezone
    try:
        user_tz = pytz.timezone(timezone)
        now_local = datetime.datetime.now(user_tz).replace(tzinfo=None)
        local_date = now_local.strftime("%d-%m-%Y")
    except:
        # Fallback to UTC if timezone invalid
        local_date = now_utc.strftime("%d-%m-%Y")
        now_local = now_utc
    
    diary = mongo.db.diaries.find_one({"user_id": ObjectId(user_id), "local_date": local_date})
    
    if not diary:
        # Create diary entry for today with usage tracking initialized
        diary_data = {
            "user_id": ObjectId(user_id),
            "local_date": local_date,
            "timezone": timezone,
            "created_at": now_utc,  # UTC
            "last_update": now_local,  # Local timezone
            "update_log": [{"timestamp": now_local}],  # Local timezone
            "image_extraction_count": 0,
            "speech_to_text_count": 0,
            "summary_generation_count": 0
        }
        mongo.db.diaries.insert_one(diary_data)
        diary = mongo.db.diaries.find_one({"user_id": ObjectId(user_id), "local_date": local_date})
    
    # Ensure usage fields exist (for old entries)
    if "image_extraction_count" not in diary or "speech_to_text_count" not in diary or "summary_generation_count" not in diary:
        update_fields = {}
        if "image_extraction_count" not in diary:
            update_fields["image_extraction_count"] = 0
            diary["image_extraction_count"] = 0
        if "speech_to_text_count" not in diary:
            update_fields["speech_to_text_count"] = 0
            diary["speech_to_text_count"] = 0
        if "summary_generation_count" not in diary:
            update_fields["summary_generation_count"] = 0
            diary["summary_generation_count"] = 0
        
        if update_fields:
            mongo.db.diaries.update_one(
                {"user_id": ObjectId(user_id), "local_date": local_date},
                {"$set": update_fields}
            )
    
    return diary

def set_diary_image_url(user_id, local_date, image_url):
    """Persist OCR diary image path on the diary document for this date."""
    mongo.db.diaries.update_one(
        {"user_id": ObjectId(user_id), "local_date": local_date},
        {"$set": {"diary.image_url": image_url}}
    )

def increment_image_extraction_count(user_id, local_date):
    """Increment image extraction count for today's diary"""
    mongo.db.diaries.update_one(
        {"user_id": ObjectId(user_id), "local_date": local_date},
        {"$inc": {"image_extraction_count": 1}}
    )

def increment_speech_to_text_count(user_id, local_date):
    """Increment speech-to-text count for today's diary"""
    mongo.db.diaries.update_one(
        {"user_id": ObjectId(user_id), "local_date": local_date},
        {"$inc": {"speech_to_text_count": 1}}
    )

def increment_summary_generation_count(user_id, local_date):
    """Increment summary generation count for today's diary"""
    mongo.db.diaries.update_one(
        {"user_id": ObjectId(user_id), "local_date": local_date},
        {"$inc": {"summary_generation_count": 1}}
    )

def get_diary_by_local_date(user_id, local_date):
    """Get diary entry by local_date"""
    return mongo.db.diaries.find_one({
        "user_id": ObjectId(user_id),
        "local_date": local_date
    })

def get_month_diaries_by_local_date(user_id, year, month):
    """Get all diary entries for a specific month (by local_date)"""
    # Build regex pattern to match dates in the format DD-MM-YYYY for the given month/year
    # Pattern: DD-MM-YYYY where month matches and year matches
    day_pattern = r"\d{2}"
    month_pattern = f"{month:02d}"
    year_pattern = str(year)
    date_pattern = f"^{day_pattern}-{month_pattern}-{year_pattern}$"
    
    return list(mongo.db.diaries.find({
        "user_id": ObjectId(user_id),
        "local_date": {"$regex": date_pattern}
    }).sort("created_at", -1))

def delete_diary_by_local_date(user_id, local_date):
    """Delete diary entry by local_date"""
    result = mongo.db.diaries.delete_one({
        "user_id": ObjectId(user_id),
        "local_date": local_date
    })
    return result

def get_all_diaries(user_id, page=1, limit=30):
    """Get all diary entries for a user with pagination, sorted by local_date descending (latest entries first)"""
    skip = (page - 1) * limit
    
    # Use aggregation pipeline to parse local_date (DD-MM-YYYY) and sort chronologically
    pipeline = [
        {"$match": {"user_id": ObjectId(user_id)}},
        {
            "$addFields": {
                "parsed_date": {
                    "$dateFromString": {
                        "dateString": {
                            "$concat": [
                                {"$arrayElemAt": [{"$split": ["$local_date", "-"]}, 2]},  # Year
                                "-",
                                {"$arrayElemAt": [{"$split": ["$local_date", "-"]}, 1]},  # Month
                                "-",
                                {"$arrayElemAt": [{"$split": ["$local_date", "-"]}, 0]}   # Day
                            ]
                        },
                        "format": "%Y-%m-%d"
                    }
                }
            }
        },
        {"$sort": {"parsed_date": -1}},  # Descending: latest dates first
        {"$skip": skip},
        {"$limit": limit},
        {"$project": {"parsed_date": 0}}  # Remove the temporary parsed_date field
    ]
    
    return list(mongo.db.diaries.aggregate(pipeline))

def get_all_diaries_count(user_id):
    """Get total count of diary entries for a user"""
    return mongo.db.diaries.count_documents({"user_id": ObjectId(user_id)})
