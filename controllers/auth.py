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

limiter = Limiter(key_func=get_remote_address, app=None, default_limits=[])

@limiter.limit("5 per hour", key_func=get_remote_address)
def request_otp():
    data = request.get_json()
    phone = data.get("phone")
    if not phone or not phone.isdigit() or len(phone) != 10:
        return jsonify({"error": "Phone number must be 10 digits."}), 400
    otp = str(random.randint(100000, 999999))
    try:
        save_otp(phone, otp)
    except Exception as e:
        return jsonify({"error": f"Failed to save OTP: {str(e)}"}), 500
    if send_otp(phone, otp):
        return jsonify({"message": "OTP sent successfully"}), 200
    else:
        return jsonify({"error": "Failed to send OTP. Please check the phone number and try again."}), 500

def verify_otp():
    data = request.get_json()
    phone = data.get("phone")
    otp = data.get("otp")
    if not phone or not phone.isdigit() or len(phone) != 10:
        return jsonify({"error": "Phone number must be 10 digits."}), 400
    if not otp or not otp.isdigit() or len(otp) != 6:
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
        timezone = request.headers.get("X-Timezone") or request.headers.get("x-timezone") or "UTC"
        
        # Log received timezone for debugging
        print(f"Received timezone header for new user: {timezone}")
        
        # Validate timezone
        if timezone != "UTC":
            try:
                import pytz
                pytz.timezone(timezone)
                print(f"Timezone validated: {timezone}")
            except pytz.exceptions.UnknownTimeZoneError:
                print(f"Invalid timezone '{timezone}', falling back to UTC")
                timezone = "UTC"  # Fallback to UTC if invalid
        
        try:
            create_user(phone, timezone)
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
