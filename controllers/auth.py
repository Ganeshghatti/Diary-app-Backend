from flask import jsonify, request, g
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import random
import jwt
import datetime
from models.user import find_user, create_user
from models.otp import save_otp, get_otp, delete_otp
from utils.sms import send_otp
import os
import pytz

limiter = Limiter(key_func=get_remote_address, app=None, default_limits=[])

TEST_PHONE_NUMBER = "9999999999"
TEST_PHONE_OTP = "123456"
TIMEZONE_ALIASES = {
    # Keep canonical IANA timezone names in DB.
    "Asia/Calcutta": "Asia/Kolkata"
}

def normalize_timezone(timezone):
    """Normalize timezone aliases and fallback to UTC for invalid values."""
    if not timezone:
        return "UTC"
    
    normalized = TIMEZONE_ALIASES.get(timezone.strip(), timezone.strip())
    
    if normalized == "UTC":
        return "UTC"
    
    try:
        pytz.timezone(normalized)
        return normalized
    except pytz.exceptions.UnknownTimeZoneError:
        return "UTC"


def _normalize_digit_string(value, min_len, max_len):
    """Coerce phone/OTP from JSON (may be int) to a validated digit string."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and value != int(value):
            return None
        value = str(int(value))
    elif isinstance(value, str):
        value = value.strip()
    else:
        return None
    if not value.isdigit() or not (min_len <= len(value) <= max_len):
        return None
    return value


@limiter.limit("5 per hour", key_func=get_remote_address)
def request_otp():
    data = request.get_json() or {}
    phone = _normalize_digit_string(data.get("phone"), 7, 15)
    country_code = data.get("country_code", "+91")
    if not phone:
        return jsonify({"error": "Phone number must be between 7 and 15 digits."}), 400
    otp = TEST_PHONE_OTP if phone == TEST_PHONE_NUMBER else str(random.randint(100000, 999999))
    try:
        save_otp(phone, otp, country_code)
    except Exception as e:
        return jsonify({"error": f"Failed to save OTP: {str(e)}"}), 500
    if phone == TEST_PHONE_NUMBER:
        return jsonify({"message": "OTP stored successfully for test account"}), 200
    if send_otp(phone, otp, country_code):
        return jsonify({"message": "OTP sent successfully"}), 200
    else:
        return jsonify({"error": "Failed to send OTP. Please check the phone number and try again."}), 500

def verify_otp():
    data = request.get_json() or {}
    phone = _normalize_digit_string(data.get("phone"), 7, 15)
    otp = _normalize_digit_string(data.get("otp"), 6, 6)
    country_code = data.get("country_code", "+91")
    if not phone:
        return jsonify({"error": "Phone number must be between 7 and 15 digits."}), 400
    if not otp:
        return jsonify({"error": "OTP must be a 6-digit number."}), 400
    
    try:
        record = get_otp(phone)
        print(record)
    except Exception as e:
        return jsonify({"error": f"Error accessing OTP: {str(e)}"}), 500
    if not record:
        return jsonify({"error": "No OTP requested for this phone number. Please request a new OTP."}), 400
    if record["otp"] != otp:
        return jsonify({"error": "Invalid OTP. Please check and try again."}), 400
    try:
        user = find_user(phone)
    except Exception as e:
        return jsonify({"error": f"Error accessing user data: {str(e)}"}), 500
    
    newly_created = False
    if not user:
        # Only set timezone when creating NEW user (signup)
        # Get timezone from header (try both uppercase and title case for compatibility)
        raw_timezone = request.headers.get("X-Timezone") or request.headers.get("x-timezone") or "UTC"
        
        # Log received timezone for debugging
        print(f"Received timezone header for new user: {raw_timezone}")
        
        timezone = normalize_timezone(raw_timezone)
        if timezone != raw_timezone:
            print(f"Timezone normalized from '{raw_timezone}' to '{timezone}'")
        else:
            print(f"Timezone validated: {timezone}")
        
        try:
            create_user(phone, timezone, country_code)
            newly_created = True
            user = find_user(phone)
        except Exception as e:
            return jsonify({"error": f"Error creating user: {str(e)}"}), 500
    # For existing users (login), don't update timezone - use existing timezone from profile
    try:
        delete_otp(phone)
    except Exception as e:
        return jsonify({"error": f"Error deleting OTP: {str(e)}"}), 500
    jwt_secret = os.getenv("JWT_SECRET")
    if not jwt_secret:
        return jsonify({"error": "JWT secret not configured on server."}), 500
    payload = {
        "phone": phone
    }
    try:
        token = jwt.encode(payload, jwt_secret, algorithm="HS256")
    except Exception as e:
        return jsonify({"error": f"Error generating token: {str(e)}"}), 500
    response = {
        "message": "OTP verified successfully.",
        "phone": phone,
        "token": token,
        "newly_created": newly_created
    }
    if not newly_created:
        user_data = {k: v for k, v in user.items() if k != "_id"}
        response["user"] = user_data
    return jsonify(response), 200
