import datetime
from config.db import mongo

def find_user(phone):
    return mongo.db.users.find_one({"phone": phone})

def create_user(phone):
    mongo.db.users.insert_one({
        "phone": phone,
        "created_at": datetime.datetime.utcnow()
    })
