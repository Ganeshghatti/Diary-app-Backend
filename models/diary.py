import datetime
from config.db import mongo
from bson import ObjectId

def get_diary(user_id, date):
    return mongo.db.diaries.find_one({"user_id": ObjectId(user_id), "date": date})

def upsert_diary(user_id, content, date, ist_now):
    # Save IST time as naive datetime (no tzinfo) for MongoDB compatibility
    ist_naive = ist_now.replace(tzinfo=None)
    diary = mongo.db.diaries.find_one({"user_id": ObjectId(user_id), "date": date})
    if diary:
        mongo.db.diaries.update_one(
            {"user_id": ObjectId(user_id), "date": date},
            {"$set": {"content": content, "last_update": ist_naive}}
        )
    else:
        mongo.db.diaries.insert_one({
            "user_id": ObjectId(user_id),
            "content": content,
            "date": date,
            "last_update": ist_naive
        })

def get_month_diaries(user_id, year, month):
    # Dates in DD-MM-YYYY format, get all for month
    month_str = f"{month:02d}-{year}"
    return list(mongo.db.diaries.find({
        "user_id": ObjectId(user_id),
        "date": {"$regex": f"^\\d{{2}}-{month_str}$"}
    }))
