from flask import request, jsonify, g
from middleware.user_required import user_required
from models.user import update_user_profile, find_user
import pytz
import os
import base64
from werkzeug.utils import secure_filename
from PIL import Image
import datetime

# Create uploads directory if it doesn't exist
UPLOAD_FOLDER = "uploads/profile_pics"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

def ensure_upload_folder():
    """Ensure upload folder exists"""
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    """Check if file extension is allowed"""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def add_profile_pic_base64(user_data):
    """Add profile picture as base64 to user_data if profile_pic_url exists"""
    profile_pic_url = user_data.get("profile_pic_url")
    if profile_pic_url:
        try:
            # Extract filename from URL
            filename = profile_pic_url.split("/")[-1]
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            
            if os.path.exists(filepath):
                # Read image file and convert to base64
                with open(filepath, "rb") as image_file:
                    image_data = base64.b64encode(image_file.read()).decode('utf-8')
                    # Add data URI prefix
                    user_data["profile_pic"] = f"data:image/jpeg;base64,{image_data}"
            else:
                # File doesn't exist, remove the URL
                user_data.pop("profile_pic_url", None)
        except Exception as e:
            # If error reading image, just skip it
            print(f"Warning: Could not load profile picture: {str(e)}")
            user_data.pop("profile_pic_url", None)
    return user_data

@user_required
def update_profile():
    """Update user's profile (name, email, profile pic, timezone)"""
    user_id = str(g.current_user["_id"])
    phone = g.current_user.get("phone")
    
    # Handle JSON data (name, email, timezone) - support both JSON and form-data
    data = {}
    if request.is_json:
        data = request.get_json() or {}
    elif request.form:
        data = request.form.to_dict()
    
    # Handle file upload (profile picture)
    profile_pic_url = None
    if "profile_pic" in request.files:
        file = request.files["profile_pic"]
        if file and file.filename and allowed_file(file.filename):
            try:
                ensure_upload_folder()
                
                # Validate and process image
                file.stream.seek(0)
                image = Image.open(file.stream)
                # Convert to RGB if necessary (handles RGBA, P, etc.)
                if image.mode in ("RGBA", "P"):
                    rgb_image = Image.new("RGB", image.size, (255, 255, 255))
                    rgb_image.paste(image, mask=image.split()[-1] if image.mode == "RGBA" else None)
                    image = rgb_image
                elif image.mode != "RGB":
                    image = image.convert("RGB")
                
                # Generate filename using user_id (always use jpg for consistency)
                filename = f"{user_id}.jpg"
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                
                # Delete old profile pic if exists
                if os.path.exists(filepath):
                    os.remove(filepath)
                
                # Also check for other extensions and delete them
                for ext in ALLOWED_EXTENSIONS:
                    old_file = os.path.join(UPLOAD_FOLDER, f"{user_id}.{ext}")
                    if os.path.exists(old_file):
                        os.remove(old_file)
                
                # Save file as JPG (better compression)
                image.save(filepath, "JPEG", quality=85, optimize=True)
                
                # Generate URL (relative path)
                profile_pic_url = f"/uploads/profile_pics/{filename}"
                
            except Exception as e:
                return jsonify({"error": f"Failed to process image: {str(e)}"}), 400
        elif file and file.filename:
            return jsonify({"error": "Invalid file type. Allowed: png, jpg, jpeg, gif, webp"}), 400
    
    # Extract and validate fields
    name = data.get("name")
    email = data.get("email")
    timezone_str = data.get("timezone")
    
    # Validate timezone if provided
    if timezone_str:
        try:
            pytz.timezone(timezone_str)
        except pytz.exceptions.UnknownTimeZoneError:
            return jsonify({
                "error": f"Invalid timezone: {timezone_str}. Use IANA timezone names like 'America/New_York', 'Asia/Kolkata', 'Europe/London', etc."
            }), 400
    
    # Validate email format if provided
    if email and "@" not in email:
        return jsonify({"error": "Invalid email format."}), 400
    
    # Prepare update data (only include provided fields)
    update_name = name if name is not None and name.strip() else None
    update_email = email if email is not None and email.strip() else None
    update_timezone = timezone_str if timezone_str else None
    
    # Update user profile
    try:
        update_user_profile(
            phone,
            name=update_name,
            email=update_email,
            profile_pic_url=profile_pic_url,
            timezone=update_timezone
        )
        
        # Refresh user data
        user = find_user(phone)
        user_data = {k: v for k, v in user.items() if k != "_id"}
        
        # Add profile picture as base64
        user_data = add_profile_pic_base64(user_data)
        
        return jsonify({
            "message": "Profile updated successfully.",
            "user": user_data
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@user_required
def get_profile():
    """Get user profile information with profile picture as base64"""
    user_data = {k: v for k, v in g.current_user.items() if k != "_id"}
    
    # Add profile picture as base64
    user_data = add_profile_pic_base64(user_data)
    
    return jsonify({"user": user_data}), 200
