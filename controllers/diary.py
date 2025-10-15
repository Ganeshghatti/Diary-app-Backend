from flask import request, jsonify, g
from models.diary import get_diary, upsert_diary, get_month_diaries
from middleware.user_required import user_required
import datetime
import pytz
import pytesseract
from PIL import Image
import io

try:
    import pytz
except ImportError:
    pytz = None

@user_required
def extract_text_from_image():
    if 'image' not in request.files:
        return jsonify({"error": "No image file provided."}), 400
    image_file = request.files['image']
    try:
        image = Image.open(image_file.stream)
    except Exception as e:
        return jsonify({"error": f"Invalid image file: {str(e)}"}), 400
    try:
        # Use pytesseract to extract text with layout
        text = pytesseract.image_to_string(image)

        return jsonify({"text": text}), 200
    except Exception as e:
        return jsonify({"error": f"Text extraction failed: {str(e)}"}), 500
    
@user_required
def add_or_update_diary():
    data = request.get_json()
    content = data.get("content")
    user_id = str(g.current_user["_id"])
    if not content:
        return jsonify({"error": "content is required."}), 400
    # Get current date in IST
    ist = pytz.timezone('Asia/Kolkata')
    now_ist = datetime.datetime.now(ist)
    date = now_ist.strftime("%d-%m-%Y")
    try:
        upsert_diary(user_id, content, date, now_ist)
        return jsonify({"message": "Diary entry saved successfully.", "date": date}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@user_required
def get_diaries_month():
    # Get current month in IST
    ist = pytz.timezone('Asia/Kolkata')
    now_ist = datetime.datetime.now(ist)
    year = now_ist.year
    month = now_ist.month
    user_id = str(g.current_user["_id"])
    try:
        diaries = get_month_diaries(user_id, year, month)
        return jsonify({"diaries": diaries}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@user_required
def get_diary_by_date():
    date = request.args.get("date")  # Expecting DD-MM-YYYY
    user_id = str(g.current_user["_id"])
    if not date:
        return jsonify({"error": "date is required as query param."}), 400
    try:
        datetime.datetime.strptime(date, "%d-%m-%Y")
    except Exception:
        return jsonify({"error": "date must be in DD-MM-YYYY format."}), 400
    try:
        diary = get_diary(user_id, date)
        if diary:
            return jsonify({"diary": diary}), 200
        else:
            return jsonify({"error": "No diary found for this date."}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@user_required
def delete_diary_by_date():
    date = request.args.get("date")  # Expecting DD-MM-YYYY
    user_id = str(g.current_user["_id"])
    if not date:
        return jsonify({"error": "date is required."}), 400
    # Get today's date in IST
    ist = pytz.timezone('Asia/Kolkata')
    today_ist = datetime.datetime.now(ist).strftime("%d-%m-%Y")
    if date == today_ist:
        return jsonify({"error": "Cannot delete today's diary."}), 400
    try:
        datetime.datetime.strptime(date, "%d-%m-%Y")
    except Exception:
        return jsonify({"error": "date must be in DD-MM-YYYY format."}), 400
    from models.diary import mongo, ObjectId
    result = mongo.db.diaries.delete_one({"user_id": ObjectId(user_id), "date": date})
    if result.deleted_count:
        return jsonify({"message": "Diary deleted successfully."}), 200
    else:
        return jsonify({"error": "No diary found for this date."}), 404