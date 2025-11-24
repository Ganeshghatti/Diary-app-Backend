import datetime
from config.db import mongo

def find_user(phone):
    return mongo.db.users.find_one({"phone": phone})

def create_user(phone, timezone="UTC", country_code="+91"):
    mongo.db.users.insert_one({
        "phone": phone,
        "country_code": country_code,
        "timezone": timezone,
        "created_at": datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    })

def update_user_profile(phone, name=None, email=None, profile_pic_url=None, timezone=None, country_code=None):
    """Update user's profile information"""
    update_data = {}
    
    if name is not None:
        update_data["name"] = name
    if email is not None:
        update_data["email"] = email
    if profile_pic_url is not None:
        update_data["profile_pic_url"] = profile_pic_url
    if timezone is not None:
        update_data["timezone"] = timezone
    if country_code is not None:
        update_data["country_code"] = country_code
    
    if update_data:
        mongo.db.users.update_one(
            {"phone": phone},
            {"$set": update_data}
        )
