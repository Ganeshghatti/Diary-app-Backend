from flask import request, jsonify, g, Response, stream_with_context
from middleware.user_required import user_required
from models.diary import (
    get_or_create_today_diary,
    increment_image_extraction_count,
    increment_speech_to_text_count,
    increment_summary_generation_count,
    upsert_diary
)
import pytesseract
from PIL import Image
import os
import datetime
import json
import google.generativeai as genai
from google.cloud import vision
from google.cloud import speech_v1 as speech
from google.oauth2 import service_account
from pinecone import Pinecone
from openai import OpenAI
import shutil
from config.db import mongo
from bson import ObjectId

if os.getenv("env") == "production":
    from pydub import AudioSegment
    from pydub.utils import which
    AudioSegment.ffmpeg = which("ffmpeg")
    AudioSegment.ffprobe = which("ffprobe")

# Upload folder for diary images and audio
DIARY_IMAGES_FOLDER = "uploads/diary_images"
DIARY_AUDIO_FOLDER = "uploads/diary_audio"
ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
ALLOWED_AUDIO_EXTENSIONS = {"wav","flac","mp3","m4a","ogg","webm","amr","3gp"}

# Initialize Pinecone and OpenAI for RAG
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
pinecone_index = pc.Index("diarydad")
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Initialize Google Cloud Vision client
_vision_client = None
def get_vision_client():
    """Initialize and return Google Cloud Vision client using service account JSON"""
    global _vision_client
    if _vision_client is None:
        try:
            # Path to service account JSON file
            service_account_path = "diarydad-main-3aa4055d5ff0.json"
            if not os.path.exists(service_account_path):
                return jsonify({"error": "Google Cloud Vision is not configured. Please ensure diarydad-main.json service account file exists."}), 500
            
            credentials = service_account.Credentials.from_service_account_file(
                service_account_path,
                scopes=['https://www.googleapis.com/auth/cloud-vision']
            )
            _vision_client = vision.ImageAnnotatorClient(credentials=credentials)
        except Exception as e:
            print(f"Warning: Failed to initialize Google Cloud Vision client: {str(e)}")
            return None
    return _vision_client

# Initialize Google Cloud Speech client
_speech_client = None
def get_speech_client():
    """Initialize and return Google Cloud Speech client using service account JSON"""
    global _speech_client
    if _speech_client is None:
        try:
            # Path to service account JSON file
            service_account_path = "diarydad-main-3aa4055d5ff0.json"
            if not os.path.exists(service_account_path):
                print(f"Warning: Service account file '{service_account_path}' not found for Speech-to-Text")
                return None
            
            credentials = service_account.Credentials.from_service_account_file(
                service_account_path,
                scopes=['https://www.googleapis.com/auth/cloud-platform']
            )
            _speech_client = speech.SpeechClient(credentials=credentials)
            print("Google Cloud Speech client initialized")
        except Exception as e:
            print(f"Warning: Failed to initialize Google Cloud Speech client: {str(e)}")
            return None
    return _speech_client

# Configure Tesseract path
def configure_tesseract():
    """Try to configure Tesseract path automatically"""
    
    # Common tesseract locations
    common_paths = [
        '/usr/bin/tesseract',
        '/usr/local/bin/tesseract',
        '/opt/homebrew/bin/tesseract',  # macOS
        os.getenv('TESSERACT_CMD'),  # Environment variable
    ]
    
    # Check if tesseract is in PATH
    tesseract_path = shutil.which('tesseract')
    
    # If found in PATH, use it
    if tesseract_path:
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
        return True
    
    # Try common paths
    for path in common_paths:
        if path and os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            return True
    
    return False

# Auto-configure tesseract on module load
_tesseract_configured = configure_tesseract()
if not _tesseract_configured:
    print("Warning: Tesseract OCR not found. Text extraction from images will not work.")
    print("Install with: sudo apt install tesseract-ocr (Ubuntu/Debian)")

def ensure_diary_images_folder():
    """Ensure diary images folder exists"""
    if not os.path.exists(DIARY_IMAGES_FOLDER):
        os.makedirs(DIARY_IMAGES_FOLDER)

def ensure_diary_audio_folder():
    """Ensure diary audio folder exists"""
    if not os.path.exists(DIARY_AUDIO_FOLDER):
        os.makedirs(DIARY_AUDIO_FOLDER)

def allowed_image_file(filename):
    """Check if file extension is allowed"""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS

def allowed_audio_file(filename):
    """Check if audio file extension is allowed"""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_AUDIO_EXTENSIONS

@user_required
def extract_text_from_image():
    """Extract text from handwritten diary image - max 3 times per day"""
    user_id = str(g.current_user["_id"])
    
    # Get timezone from user model
    timezone = g.current_user.get("timezone", "UTC")
    
    # Get or create today's diary entry (1 document = 1 day)
    today_diary = get_or_create_today_diary(user_id, timezone)
    current_count = today_diary.get("image_extraction_count", 0)
    local_date = today_diary.get("local_date")
    
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
        
        # Check if tesseract is configured
        if not _tesseract_configured:
            # Try to configure again (in case it was installed after server start)
            if not configure_tesseract():
                return jsonify({
                    "error": "Tesseract OCR is not installed or not found in PATH. Please install it: sudo apt install tesseract-ocr (Ubuntu/Debian)"
                }), 500
        
        # Use pytesseract to extract text
        try:
            text = pytesseract.image_to_string(image)
        except pytesseract.pytesseract.TesseractNotFoundError:
            return jsonify({
                "error": "Tesseract OCR is not installed or not found in PATH. Please install it: sudo apt install tesseract-ocr (Ubuntu/Debian)"
            }), 500
        except Exception as ocr_error:
            return jsonify({
                "error": f"OCR processing failed: {str(ocr_error)}"
            }), 500
        
        # Increment usage count in today's diary entry
        increment_image_extraction_count(user_id, local_date)
        
        return jsonify({
            "text": text.strip(),
            "image_url": f"/uploads/diary_images/{filename}",
            "remaining_uses": 3 - (current_count + 1)
        }), 200
    except Exception as e:
        return jsonify({"error": f"Text extraction failed: {str(e)}"}), 500

@user_required
def extract_text_from_image_google_vision():
    """Extract text from handwritten diary image using Google Cloud Vision - max 3 times per day"""
    user_id = str(g.current_user["_id"])
    
    # Get timezone from user model
    timezone = g.current_user.get("timezone", "UTC")
    
    # Get or create today's diary entry (1 document = 1 day)
    today_diary = get_or_create_today_diary(user_id, timezone)
    current_count = today_diary.get("image_extraction_count", 0)
    local_date = today_diary.get("local_date")
    
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
        
        # Initialize Google Cloud Vision client
        vision_client = get_vision_client()
        if not vision_client:
            return jsonify({
                "error": "Google Cloud Vision is not configured. Please ensure diarydad-main.json service account file exists."
            }), 500
        
        # Read image content for Vision API
        with open(filepath, 'rb') as image_file_content:
            content = image_file_content.read()
        
        # Create image object for Vision API
        vision_image = vision.Image(content=content)
        
        # Perform document text detection (optimized for handwriting and dense text)
        try:
            response = vision_client.document_text_detection(image=vision_image)
            
            # DOCUMENT_TEXT_DETECTION returns full_text_annotation with structured data
            # The full_text_annotation.text contains the complete extracted text
            if response.full_text_annotation:
                extracted_text = response.full_text_annotation.text
            elif response.text_annotations:
                # Fallback to text_annotations if full_text_annotation is not available
                extracted_text = response.text_annotations[0].description
            else:
                extracted_text = ""
            
        except Exception as vision_error:
            return jsonify({
                "error": f"Google Vision API processing failed: {str(vision_error)}"
            }), 500
        
        # Increment usage count in today's diary entry
        increment_image_extraction_count(user_id, local_date)
        
        return jsonify({
            "text": extracted_text.strip(),
            "image_url": f"/uploads/diary_images/{filename}",
            "remaining_uses": 3 - (current_count + 1)
        }), 200
    except Exception as e:
        return jsonify({"error": f"Text extraction failed: {str(e)}"}), 500

@user_required
def speech_to_text():
    user_id = str(g.current_user["_id"])
    
    # Get timezone from user model
    timezone = g.current_user.get("timezone", "UTC")
    
    today_diary = get_or_create_today_diary(user_id, timezone)
    current_count = today_diary.get("speech_to_text_count", 0)
    local_date = today_diary.get("local_date")

    if current_count >= 10:
        return jsonify({"error": "Daily limit reached. You can use speech-to-text only 10 times per day."}), 429

    if "audio" not in request.files:
        return jsonify({"error": "No audio file provided."}), 400

    audio_file = request.files["audio"]

    if not audio_file.filename or not allowed_audio_file(audio_file.filename):
        return jsonify({"error": f"Invalid audio file. Allowed formats: {', '.join(sorted(ALLOWED_AUDIO_EXTENSIONS))}"}), 400

    data = request.form.to_dict() if request.form else {}
    requested_language = data.get("language_code", "hi-IN")
    indian_languages = ["hi-IN","en-IN","bn-IN","te-IN","mr-IN","ta-IN","gu-IN","kn-IN","ml-IN","or-IN","pa-IN","as-IN"]

    if requested_language in indian_languages:
        language_code = requested_language
        alternative_languages = None
    else:
        language_code = "hi-IN"
        alternative_languages = None
    try:
        ensure_diary_audio_folder()
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        timestamp = now_utc.strftime("%Y%m%d_%H%M%S")
        extension = audio_file.filename.rsplit(".", 1)[1].lower()
        filename_original = f"{user_id}_{timestamp}.{extension}"
        filepath_original = os.path.join(DIARY_AUDIO_FOLDER, filename_original)
        audio_file.save(filepath_original)
        try:
            sound = AudioSegment.from_file(filepath_original)
            sound = sound.set_frame_rate(16000).set_channels(1)
            wav_path = os.path.join(DIARY_AUDIO_FOLDER, f"{user_id}_{timestamp}.wav")
            sound.export(wav_path, format="wav")
            filepath_for_stt = wav_path
            extension_lower = "wav"
        except Exception as conv_err:
            return jsonify({"error": f"Audio conversion failed: {str(conv_err)}"}), 500
        speech_client = get_speech_client()
        if not speech_client:
            return jsonify({"error": "Google Cloud Speech-to-Text is not configured. Please ensure the service account file exists."}), 500
        with open(filepath_for_stt, "rb") as f:
            audio_data = f.read()
        audio = speech.RecognitionAudio(content=audio_data)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code=language_code,
            alternative_language_codes=alternative_languages,
            enable_automatic_punctuation=True,
            model="latest_long"
        )
        try:
            response = speech_client.recognize(config=config, audio=audio)
            transcribed_text = ""
            if response.results:
                for result in response.results:
                    if result.alternatives:
                        transcribed_text += result.alternatives[0].transcript + " "
            else:
                transcribed_text = ""
            increment_speech_to_text_count(user_id, local_date)
            audio_url = f"/uploads/diary_audio/{os.path.basename(filepath_original)}"
            try:
                if os.path.exists(wav_path):
                    os.remove(wav_path)
            except Exception:
                pass
            return jsonify({
                "text": transcribed_text.strip(),
                "language_code": language_code,
                "audio_url": audio_url,
                "remaining_uses": 10 - (current_count + 1)
            }), 200
        except Exception as speech_error:
            return jsonify({"error": f"Speech recognition failed: {str(speech_error)}"}), 500
    except Exception as e:
        return jsonify({"error": f"Speech-to-text processing failed: {str(e)}"}), 500


@user_required
def generate_summary():
    """Generate summary of diary text using GPT API - max 3 times per day, streaming response. Saves summary to DB after completion."""
    user_id = str(g.current_user["_id"])
    
    # Get timezone from user model
    timezone = g.current_user.get("timezone", "UTC")
    
    # Get or create today's diary entry (1 document = 1 day)
    today_diary = get_or_create_today_diary(user_id, timezone)
    current_count = today_diary.get("summary_generation_count", 0)
    local_date = today_diary.get("local_date")
    
    # Check rate limit (3 per day)
    if current_count >= 3:
        return jsonify({"error": "Daily limit reached. You can generate summaries only 3 times per day."}), 429
    
    data = request.get_json()
    diary_text = data.get("text")
    
    if not diary_text:
        return jsonify({"error": "text is required."}), 400
    
    if not isinstance(diary_text, str):
        return jsonify({"error": "text must be a string."}), 400
    
    # Check OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        return jsonify({"error": "OpenAI API key not configured on server."}), 500
    
    try:
        # Create prompt for GPT
        system_message = "You are a helpful assistant that creates concise, thoughtful summaries of diary entries."
        user_message = f"Please provide a concise summary of the following diary entry in 2-3 sentences:\n\n{diary_text}"
        
        # Increment usage count in today's diary entry
        increment_summary_generation_count(user_id, local_date)
        
        # Stream response and collect full summary
        def generate():
            full_summary = ""
            try:
                # Stream response from OpenAI
                stream = openai_client.chat.completions.create(
                    model="gpt-4o-mini",  # Using gpt-4o-mini for cost-effectiveness
                    messages=[
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": user_message}
                    ],
                    max_tokens=500,
                    temperature=0.7,
                    stream=True
                )
                
                # Send initial metadata
                yield f"data: {json.dumps({'type': 'start', 'remaining_uses': 3 - (current_count + 1)})}\n\n"
                
                # Stream chunks and collect summary
                for chunk in stream:
                    if chunk.choices[0].delta.content is not None:
                        text = chunk.choices[0].delta.content
                        full_summary += text
                        yield f"data: {json.dumps({'type': 'chunk', 'text': text})}\n\n"
                
                # Save summary to database after completion
                try:
                   
                    # Get existing diary entry
                    existing_diary_entry = mongo.db.diaries.find_one({"user_id": ObjectId(user_id), "local_date": local_date})
                    
                    if existing_diary_entry:
                        # Get existing diary object or create new one
                        diary_obj = existing_diary_entry.get("diary", {})
                        if not isinstance(diary_obj, dict):
                            diary_obj = {}
                        
                        # Update summary
                        diary_obj["summary"] = full_summary.strip()
                        
                        # Save to database
                        upsert_diary(user_id, local_date, timezone, diary=diary_obj)
                    else:
                        # Create new diary entry with summary
                        upsert_diary(user_id, local_date, timezone, diary={"summary": full_summary.strip()})
                    
                except Exception as db_error:
                    # Log error but don't fail the stream
                    print(f"Warning: Failed to save summary to database: {str(db_error)}")
                    yield f"data: {json.dumps({'type': 'warning', 'message': 'Summary generated but failed to save to database.'})}\n\n"
                
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

    except Exception as e:
        return jsonify({"error": f"Summary generation failed: {str(e)}"}), 500

@user_required
def chat_with_diary():
    """Chat with diary using RAG (Retrieval-Augmented Generation) - streaming response"""
    user_id = str(g.current_user["_id"])
    
    data = request.get_json()
    query = data.get("query")
    
    if not query:
        return jsonify({"error": "query is required."}), 400
    
    if not isinstance(query, str):
        return jsonify({"error": "query must be a string."}), 400
    
    # Check OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        return jsonify({"error": "OpenAI API key not configured on server."}), 500
    
    try:
        # Create embedding for the query
        try:
            query_embedding = openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=query
            ).data[0].embedding
        except Exception as e:
            return jsonify({"error": f"Failed to create query embedding: {str(e)}"}), 500
        
        # Search Pinecone for relevant diary entries (filter by user_id)
        try:
            search_results = pinecone_index.query(
                vector=query_embedding,
                top_k=3,
                include_metadata=True,
                filter={"user_id": user_id}
            )
        except Exception as e:
            return jsonify({"error": f"Failed to search diary entries: {str(e)}"}), 500
        
        # Prepare context from retrieved diary entries
        context_parts = []
        if search_results.matches and len(search_results.matches) > 0:
            for match in search_results.matches:
                metadata = match.metadata
                date = metadata.get("date", "Unknown date")
                content = metadata.get("content", metadata.get("text", ""))
                
                if content:
                    context_parts.append(f"Date: {date}\nEntry: {content}")
        
        # If no relevant entries found, still provide a response
        if not context_parts:
            context = "No relevant diary entries found in your diary."
        else:
            context = "\n\n---\n\n".join(context_parts)
        
        # Create RAG prompt for GPT
        system_message = """You are a helpful assistant that helps users understand and reflect on their diary entries in maximum 2-3 sentences. Based on the diary entries provided, answer the user's question in a thoughtful, empathetic, and concise manner.If the context doesn't contain relevant information to answer the question, politely let the user know. Be warm, understanding, and focus on helping the user gain insights from their diary entries."""
        
        user_message = f"""Relevant Diary Entries: {context}

        User Question: {query}

        Please provide a helpful response based on the diary entries above in maximum 2-3 sentences:"""
        
        # Stream response using OpenAI GPT
        def generate():
            try:
                # Stream response from OpenAI
                stream = openai_client.chat.completions.create(
                    model="gpt-4o-mini",  # Using gpt-4o-mini for cost-effectiveness, can change to gpt-4o for better quality
                    messages=[
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": user_message}
                    ],
                    max_tokens=1000,
                    temperature=0.7,
                    stream=True
                )
                
                # Send initial metadata
                yield f"data: {json.dumps({'type': 'start', 'matches_found': len(search_results.matches) if search_results.matches else 0})}\n\n"
                
                # Stream chunks
                for chunk in stream:
                    if chunk.choices[0].delta.content is not None:
                        text = chunk.choices[0].delta.content
                        yield f"data: {json.dumps({'type': 'chunk', 'text': text})}\n\n"
                
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
        
    except Exception as e:
        return jsonify({"error": f"Chat failed: {str(e)}"}), 500

