import datetime
from config.db import mongo

def save_otp(phone, otp):
    mongo.db.otps.update_one(
        {"phone": phone},
        {"$set": {
            "otp": otp,
            "created_at": datetime.datetime.utcnow()
        }},
        upsert=True
    )

def get_otp(phone):
    return mongo.db.otps.find_one({"phone": phone})

def delete_otp(phone):
    mongo.db.otps.delete_one({"phone": phone})
