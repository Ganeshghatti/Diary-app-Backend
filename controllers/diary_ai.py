from flask import request, jsonify, g, Response, stream_with_context
from middleware.user_required import user_required
from models.diary import get_or_create_today_diary, increment_image_extraction_count, increment_summary_generation_count
import pytesseract
from PIL import Image
import os
import datetime
import json
import os
import google.generativeai as genai

# Upload folder for diary images
DIARY_IMAGES_FOLDER = "uploads/diary_images"
ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

def ensure_diary_images_folder():
    """Ensure diary images folder exists"""
    if not os.path.exists(DIARY_IMAGES_FOLDER):
        os.makedirs(DIARY_IMAGES_FOLDER)

def allowed_image_file(filename):
    """Check if file extension is allowed"""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS

@user_required
def extract_text_from_image():
    """Extract text from handwritten diary image - max 3 times per day"""
    user_id = str(g.current_user["_id"])
    
    # Get or create today's diary entry (1 document = 1 day)
    today_diary = get_or_create_today_diary(user_id)
    current_count = today_diary.get("image_extraction_count", 0)
    date = today_diary.get("date")
    
    # Check rate limit (3 per day)
    if current_count >= 3:
        return jsonify({"error": "Daily limit reached. You can extract text from images only 3 times per day."}), 429
    
    if 'image' not in request.files:
        return jsonify({"error": "No image file provided."}), 400
    
    image_file = request.files['image']
    
    if not image_file.filename or not allowed_image_file(image_file.filename):
        return jsonify({"error": "Invalid image file. Allowed: png, jpg, jpeg, gif, webp"}), 400
    
    try:
        image = Image.open(image_file.stream)
    except Exception as e:
        return jsonify({"error": f"Invalid image file: {str(e)}"}), 400
    
    try:
        # Ensure folder exists
        ensure_diary_images_folder()
        
        # Save image with user_id and timestamp
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        timestamp = now_utc.strftime("%Y%m%d_%H%M%S")
        extension = image_file.filename.rsplit(".", 1)[1].lower()
        filename = f"{user_id}_{timestamp}.{extension}"
        filepath = os.path.join(DIARY_IMAGES_FOLDER, filename)
        
        # Save original image
        image.save(filepath)
        
        # Use pytesseract to extract text
        text = pytesseract.image_to_string(image)
        
        # Increment usage count in today's diary entry
        increment_image_extraction_count(user_id, date)
        
        return jsonify({
            "text": text.strip(),
            "image_url": f"/uploads/diary_images/{filename}",
            "remaining_uses": 3 - (current_count + 1)
        }), 200
    except Exception as e:
        return jsonify({"error": f"Text extraction failed: {str(e)}"}), 500

@user_required
def generate_summary():
    """Generate summary of diary text using Gemini API - max 3 times per day, streaming response"""
    user_id = str(g.current_user["_id"])
    
    # Get or create today's diary entry (1 document = 1 day)
    today_diary = get_or_create_today_diary(user_id)
    current_count = today_diary.get("summary_generation_count", 0)
    date = today_diary.get("date")
    
    # Check rate limit (3 per day)
    if current_count >= 3:
        return jsonify({"error": "Daily limit reached. You can generate summaries only 3 times per day."}), 429
    
    data = request.get_json()
    diary_text = data.get("text")
    
    if not diary_text:
        return jsonify({"error": "text is required."}), 400
    
    if not isinstance(diary_text, str):
        return jsonify({"error": "text must be a string."}), 400
    
    # Get Gemini API key from environment
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        return jsonify({"error": "Gemini API key not configured on server."}), 500
    
    try:        
        # Configure Gemini
        genai.configure(api_key=gemini_api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Create prompt
        prompt = f"Please provide a concise summary of the following diary entry in 2-3 sentences:\n\n{diary_text}"
        
        # Increment usage count in today's diary entry
        increment_summary_generation_count(user_id, date)
        
        # Stream response
        def generate():
            try:
                response = model.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        max_output_tokens=500,
                        temperature=0.7
                    ),
                    stream=True
                )
                
                # Send initial metadata
                yield f"data: {json.dumps({'type': 'start', 'remaining_uses': 3 - (current_count + 1)})}\n\n"
                
                # Stream chunks
                for chunk in response:
                    if chunk.text:
                        yield f"data: {json.dumps({'type': 'chunk', 'text': chunk.text})}\n\n"
                
                # Send completion
                yield f"data: {json.dumps({'type': 'complete'})}\n\n"
                
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
        
        return Response(
            stream_with_context(generate()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no'
            }
        )

    except ImportError:
        return jsonify({"error": "Internal server error"}), 500

