import datetime
from config.db import mongo
from bson import ObjectId

def upsert_diary(user_id, date, diary=None, mood_tracker=None, expense_tracker=None, health_stats=None):
    """Create or update a diary entry (upsert) - everything stored in UTC"""
    now_utc = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    
    # Check if diary exists by date string (for backward compatibility)
    existing = mongo.db.diaries.find_one({"user_id": ObjectId(user_id), "date": date})
    
    if existing:
        # Update existing diary - append to update_log
        update_data = {"last_update": now_utc}
        
        # Add to update log array
        update_log_entry = {"timestamp": now_utc}
        mongo.db.diaries.update_one(
            {"user_id": ObjectId(user_id), "date": date},
            {"$push": {"update_log": update_log_entry}}
        )
        
        if diary is not None:
            update_data["diary"] = diary
        if mood_tracker is not None:
            update_data["mood_tracker"] = mood_tracker
        if expense_tracker is not None:
            update_data["expense_tracker"] = expense_tracker
        if health_stats is not None:
            update_data["health_stats"] = health_stats
        
        result = mongo.db.diaries.update_one(
            {"user_id": ObjectId(user_id), "date": date},
            {"$set": update_data}
        )
        return {"upserted": False, "result": result}
    else:
        # Create new diary - everything in UTC
        diary_data = {
            "user_id": ObjectId(user_id),
            "date": date,  # UTC date string (DD-MM-YYYY)
            "created_at": now_utc,  # UTC timestamp
            "last_update": now_utc,  # UTC timestamp
            "update_log": [{"timestamp": now_utc}]  # UTC timestamps
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

def get_diary_by_date_range(user_id, start_utc, end_utc):
    """Get diary entry by UTC date range (query using created_at)"""
    return mongo.db.diaries.find_one({
        "user_id": ObjectId(user_id),
        "created_at": {
            "$gte": start_utc,
            "$lte": end_utc
        }
    })

def get_month_diaries_by_date_range(user_id, start_utc, end_utc):
    """Get all diary entries for a UTC date range (query using created_at)"""
    return list(mongo.db.diaries.find({
        "user_id": ObjectId(user_id),
        "created_at": {
            "$gte": start_utc,
            "$lte": end_utc
        }
    }).sort("created_at", -1))

def delete_diary_by_date_range(user_id, start_utc, end_utc):
    """Delete diary entry by UTC date range (query using created_at)"""
    result = mongo.db.diaries.delete_one({
        "user_id": ObjectId(user_id),
        "created_at": {
            "$gte": start_utc,
            "$lte": end_utc
        }
    })
    return result

def get_all_diaries(user_id):
    """Get all diary entries for a user"""
    return list(mongo.db.diaries.find({"user_id": ObjectId(user_id)}).sort("created_at", -1))
