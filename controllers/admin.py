from flask import request, jsonify, g
from middleware.admin_required import admin_required
from models.user import find_user
from models.diary import get_all_diaries
from config.db import mongo
import jwt
import os
import datetime
import pytz
import base64
from bson import ObjectId

# Hardcoded admin credentials
ADMIN_EMAIL = "tech@diarydad.me"
ADMIN_PASSWORD = "adminpass1"

def admin_login():
    """Admin login - hardcoded credentials"""
    data = request.get_json()
    
    email = data.get("email")
    password = data.get("password")
    
    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400
    
    # Check hardcoded credentials
    if email != ADMIN_EMAIL or password != ADMIN_PASSWORD:
        return jsonify({"error": "Invalid credentials."}), 401
    
    # Generate JWT token
    secret_key = os.getenv("JWT_SECRET")
    token = jwt.encode({
        "email": ADMIN_EMAIL,
        "role": "admin"
    }, secret_key, algorithm="HS256")
    
    return jsonify({
        "message": "Admin login successful",
        "token": token,
        "email": ADMIN_EMAIL
    }), 200

@admin_required
def get_all_users():
    """Get all users with basic info"""
    try:
        users = list(mongo.db.users.find({}, {
            "_id": 1,
            "phone": 1,
            "name": 1,
            "email": 1,
            "timezone": 1,
            "created_at": 1
        }).sort("created_at", -1))
        
        # Convert ObjectId to string and format dates
        for user in users:
            user["_id"] = str(user["_id"])
            if "created_at" in user and user["created_at"]:
                if isinstance(user["created_at"], datetime.datetime):
                    user["created_at"] = user["created_at"].isoformat()
        
        return jsonify({
            "users": users,
            "total": len(users)
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def add_profile_pic_base64(user_data):
    """Add profile picture as base64 to user_data if profile_pic_url exists"""
    profile_pic_url = user_data.get("profile_pic_url")
    if profile_pic_url:
        try:
            # Extract filename from URL
            filename = profile_pic_url.split("/")[-1]
            filepath = os.path.join("uploads/profile_pics", filename)
            
            if os.path.exists(filepath):
                # Read image file and convert to base64
                with open(filepath, "rb") as image_file:
                    image_data = base64.b64encode(image_file.read()).decode('utf-8')
                    # Detect image type from file extension
                    ext = filename.rsplit(".", 1)[-1].lower()
                    mime_type = f"image/{ext}" if ext in ["png", "gif", "webp"] else "image/jpeg"
                    # Add data URI prefix
                    user_data["profile_pic"] = f"data:{mime_type};base64,{image_data}"
        except Exception as e:
            # If error reading image, just skip it
            print(f"Warning: Could not load profile picture: {str(e)}")
    return user_data

def format_diary_for_response(diary, user_id, include_full_data=True):
    """Format diary entry for API response"""
    formatted = {
        "_id": str(diary.get("_id", "")),
        "date": diary.get("date", ""),
        "created_at": diary.get("created_at").isoformat() if isinstance(diary.get("created_at"), datetime.datetime) else diary.get("created_at"),
        "last_update": diary.get("last_update").isoformat() if isinstance(diary.get("last_update"), datetime.datetime) else diary.get("last_update"),
        "image_extraction_count": diary.get("image_extraction_count", 0),
        "summary_generation_count": diary.get("summary_generation_count", 0)
    }
    
    if include_full_data:
        # Include full diary content for recent entries
        if "diary" in diary:
            formatted["diary"] = diary["diary"]
        if "mood_tracker" in diary:
            formatted["mood_tracker"] = diary["mood_tracker"]
        if "expense_tracker" in diary:
            formatted["expense_tracker"] = diary["expense_tracker"]
        if "health_stats" in diary:
            formatted["health_stats"] = diary["health_stats"]
        if "update_log" in diary:
            formatted["update_log"] = [
                {"timestamp": log_entry.get("timestamp").isoformat() if isinstance(log_entry.get("timestamp"), datetime.datetime) else log_entry.get("timestamp")}
                for log_entry in diary["update_log"]
            ]
    else:
        # Only include stats for older entries
        formatted["type"] = "summary"
    
    return formatted

@admin_required
def get_user_details(user_id):
    """Get detailed information about a specific user with diary entries"""
    try:
        # Get user
        user = mongo.db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            return jsonify({"error": "User not found."}), 404
        
        # Convert ObjectId to string
        user["_id"] = str(user["_id"])
        
        # Format dates
        if "created_at" in user and user["created_at"]:
            if isinstance(user["created_at"], datetime.datetime):
                user["created_at"] = user["created_at"].isoformat()
        
        # Add profile picture as base64
        user = add_profile_pic_base64(user)
        
        # Get all diary entries
        diaries = get_all_diaries(user_id)
        user["total_diary_entries"] = len(diaries)
        
        # Get last diary entry date
        if diaries:
            last_entry = diaries[0]  # Already sorted by created_at descending
            if "created_at" in last_entry and last_entry["created_at"]:
                if isinstance(last_entry["created_at"], datetime.datetime):
                    user["last_diary_entry"] = last_entry["created_at"].isoformat()
        else:
            user["last_diary_entry"] = None
        
        # Get usage stats from today's diary if exists
        now_utc = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        today_date = now_utc.strftime("%d-%m-%Y")
        today_diary = mongo.db.diaries.find_one({
            "user_id": ObjectId(user_id),
            "date": today_date
        })
        
        if today_diary:
            user["today_image_extractions"] = today_diary.get("image_extraction_count", 0)
            user["today_summary_generations"] = today_diary.get("summary_generation_count", 0)
        else:
            user["today_image_extractions"] = 0
            user["today_summary_generations"] = 0
        
        # Process diary entries: full data for past 3 calendar days, stats only for older
        now_utc = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        # Calculate date threshold (today, yesterday, day before yesterday)
        today_date = now_utc.date()
        three_days_ago_date = today_date - datetime.timedelta(days=2)  # Include today, yesterday, and 2 days ago (3 total days)
        
        formatted_diaries = []
        for diary in diaries:
            diary_created_at = diary.get("created_at")
            if isinstance(diary_created_at, datetime.datetime):
                # Include full data if created within last 3 calendar days (today, yesterday, day before)
                diary_date = diary_created_at.date()
                include_full = diary_date >= three_days_ago_date
                formatted_diary = format_diary_for_response(diary, user_id, include_full_data=include_full)
                formatted_diaries.append(formatted_diary)
            else:
                # If no created_at, only send stats
                formatted_diary = format_diary_for_response(diary, user_id, include_full_data=False)
                formatted_diaries.append(formatted_diary)
        
        user["diaries"] = formatted_diaries
        
        # Calculate user-specific engagement stats
        now_utc = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        
        # Today
        today_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = now_utc
        
        # This week (Monday to today)
        days_since_monday = now_utc.weekday()
        week_start = (now_utc - datetime.timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = now_utc
        
        # This month (first day to today)
        month_start = now_utc.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_end = now_utc
        
        # Last 7 days (rolling)
        last_7_days_start = (now_utc - datetime.timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Last 30 days (rolling)
        last_30_days_start = (now_utc - datetime.timedelta(days=29)).replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Last 90 days (rolling)
        last_90_days_start = (now_utc - datetime.timedelta(days=89)).replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Count active days (days with diary entries) for this user
        def count_active_days(start_date, end_date):
            """Count number of unique days with diary activity"""
            active_diaries = list(mongo.db.diaries.find({
                "user_id": ObjectId(user_id),
                "$or": [
                    {"created_at": {"$gte": start_date, "$lte": end_date}},
                    {"last_update": {"$gte": start_date, "$lte": end_date}}
                ]
            }))
            unique_dates = set()
            for diary in active_diaries:
                if "created_at" in diary and diary["created_at"]:
                    unique_dates.add(diary["created_at"].date() if isinstance(diary["created_at"], datetime.datetime) else None)
                if "last_update" in diary and diary["last_update"]:
                    unique_dates.add(diary["last_update"].date() if isinstance(diary["last_update"], datetime.datetime) else None)
            return len([d for d in unique_dates if d is not None])
        
        user["engagement_stats"] = {
            "today": count_active_days(today_start, today_end),
            "this_week": count_active_days(week_start, week_end),
            "this_month": count_active_days(month_start, month_end),
            "last_7_days": count_active_days(last_7_days_start, now_utc),
            "last_30_days": count_active_days(last_30_days_start, now_utc),
            "last_90_days": count_active_days(last_90_days_start, now_utc)
        }
        
        return jsonify({"user": user}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@admin_required
def get_engagement_stats():
    """Get engagement rate statistics for graphs"""
    try:
        now_utc = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        
        def count_users_as_of(end_date):
            """Count users that existed up to a given timestamp."""
            return mongo.db.users.count_documents({
                "$or": [
                    {"created_at": {"$lte": end_date}},
                    {"created_at": {"$exists": False}}
                ]
            })
        
        # Today
        today_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = now_utc
        
        # This week (Monday to today)
        days_since_monday = now_utc.weekday()
        week_start = (now_utc - datetime.timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = now_utc
        
        # This month (first day to today)
        month_start = now_utc.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_end = now_utc
        
        # Last 7 days (rolling)
        last_7_days_start = (now_utc - datetime.timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Last 30 days (rolling)
        last_30_days_start = (now_utc - datetime.timedelta(days=29)).replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Last 90 days (rolling)
        last_90_days_start = (now_utc - datetime.timedelta(days=89)).replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Get total users
        total_users = mongo.db.users.count_documents({})
        
        # Today - users who created/updated diary today
        today_active_users = mongo.db.diaries.distinct("user_id", {
            "$or": [
                {"created_at": {"$gte": today_start, "$lte": today_end}},
                {"last_update": {"$gte": today_start, "$lte": today_end}}
            ]
        })
        today_count = len(today_active_users)
        
        # This week
        week_active_users = mongo.db.diaries.distinct("user_id", {
            "$or": [
                {"created_at": {"$gte": week_start, "$lte": week_end}},
                {"last_update": {"$gte": week_start, "$lte": week_end}}
            ]
        })
        week_count = len(week_active_users)
        
        # This month
        month_active_users = mongo.db.diaries.distinct("user_id", {
            "$or": [
                {"created_at": {"$gte": month_start, "$lte": month_end}},
                {"last_update": {"$gte": month_start, "$lte": month_end}}
            ]
        })
        month_count = len(month_active_users)
        
        # Last 7 days (rolling)
        last_7_days_users = mongo.db.diaries.distinct("user_id", {
            "$or": [
                {"created_at": {"$gte": last_7_days_start, "$lte": now_utc}},
                {"last_update": {"$gte": last_7_days_start, "$lte": now_utc}}
            ]
        })
        last_7_days_count = len(last_7_days_users)
        
        # Last 30 days (rolling)
        last_30_days_users = mongo.db.diaries.distinct("user_id", {
            "$or": [
                {"created_at": {"$gte": last_30_days_start, "$lte": now_utc}},
                {"last_update": {"$gte": last_30_days_start, "$lte": now_utc}}
            ]
        })
        last_30_days_count = len(last_30_days_users)
        
        # Last 90 days (rolling)
        last_90_days_users = mongo.db.diaries.distinct("user_id", {
            "$or": [
                {"created_at": {"$gte": last_90_days_start, "$lte": now_utc}},
                {"last_update": {"$gte": last_90_days_start, "$lte": now_utc}}
            ]
        })
        last_90_days_count = len(last_90_days_users)
        
        # Daily breakdown for last 30 days (for graph)
        daily_engagement = []
        for i in range(29, -1, -1):  # Last 30 days
            day_start = (now_utc - datetime.timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + datetime.timedelta(days=1) - datetime.timedelta(microseconds=1)
            
            day_users = mongo.db.diaries.distinct("user_id", {
                "$or": [
                    {"created_at": {"$gte": day_start, "$lte": day_end}},
                    {"last_update": {"$gte": day_start, "$lte": day_end}}
                ]
            })
            day_total_users = count_users_as_of(day_end)
            
            daily_engagement.append({
                "date": day_start.strftime("%Y-%m-%d"),
                "active_users": len(day_users),
                "total_users": day_total_users,
                "engagement_rate": round((len(day_users) / day_total_users * 100) if day_total_users > 0 else 0, 2)
            })
        
        # Weekly breakdown for last 12 weeks (for graph)
        weekly_engagement = []
        for i in range(11, -1, -1):  # Last 12 weeks
            week_end_date = now_utc - datetime.timedelta(weeks=i, days=now_utc.weekday())
            week_start_date = week_end_date - datetime.timedelta(days=6)
            week_start_date = week_start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            week_end_date = week_end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
            
            week_users = mongo.db.diaries.distinct("user_id", {
                "$or": [
                    {"created_at": {"$gte": week_start_date, "$lte": week_end_date}},
                    {"last_update": {"$gte": week_start_date, "$lte": week_end_date}}
                ]
            })
            week_total_users = count_users_as_of(week_end_date)
            
            weekly_engagement.append({
                "week_start": week_start_date.strftime("%Y-%m-%d"),
                "week_end": week_end_date.strftime("%Y-%m-%d"),
                "active_users": len(week_users),
                "total_users": week_total_users,
                "engagement_rate": round((len(week_users) / week_total_users * 100) if week_total_users > 0 else 0, 2)
            })
        
        # Monthly breakdown for last 12 months (for graph)
        monthly_engagement = []
        for i in range(11, -1, -1):  # Last 12 months
            # Calculate month start and end
            month_date = now_utc - datetime.timedelta(days=30 * i)
            month_start_date = month_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            # Calculate next month start to get current month end
            if month_start_date.month == 12:
                next_month_start = month_start_date.replace(year=month_start_date.year + 1, month=1, day=1)
            else:
                next_month_start = month_start_date.replace(month=month_start_date.month + 1, day=1)
            
            month_end_date = next_month_start - datetime.timedelta(microseconds=1)
            
            month_users = mongo.db.diaries.distinct("user_id", {
                "$or": [
                    {"created_at": {"$gte": month_start_date, "$lte": month_end_date}},
                    {"last_update": {"$gte": month_start_date, "$lte": month_end_date}}
                ]
            })
            month_total_users = count_users_as_of(month_end_date)
            
            monthly_engagement.append({
                "month": month_start_date.strftime("%Y-%m"),
                "month_name": month_start_date.strftime("%B %Y"),
                "active_users": len(month_users),
                "total_users": month_total_users,
                "engagement_rate": round((len(month_users) / month_total_users * 100) if month_total_users > 0 else 0, 2)
            })
        
        return jsonify({
            "summary": {
                "total_users": total_users,
                "today": {
                    "active_users": today_count,
                    "engagement_rate": round((today_count / total_users * 100) if total_users > 0 else 0, 2)
                },
                "this_week": {
                    "active_users": week_count,
                    "engagement_rate": round((week_count / total_users * 100) if total_users > 0 else 0, 2)
                },
                "this_month": {
                    "active_users": month_count,
                    "engagement_rate": round((month_count / total_users * 100) if total_users > 0 else 0, 2)
                },
                "last_7_days": {
                    "active_users": last_7_days_count,
                    "engagement_rate": round((last_7_days_count / total_users * 100) if total_users > 0 else 0, 2)
                },
                "last_30_days": {
                    "active_users": last_30_days_count,
                    "engagement_rate": round((last_30_days_count / total_users * 100) if total_users > 0 else 0, 2)
                },
                "last_90_days": {
                    "active_users": last_90_days_count,
                    "engagement_rate": round((last_90_days_count / total_users * 100) if total_users > 0 else 0, 2)
                }
            },
            "graphs": {
                "daily": daily_engagement,
                "weekly": weekly_engagement,
                "monthly": monthly_engagement
            }
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

