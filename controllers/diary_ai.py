from flask import request, jsonify, g, Response, stream_with_context
from middleware.user_required import user_required
from models.diary import get_or_create_today_diary, increment_image_extraction_count, increment_summary_generation_count
import pytesseract
from PIL import Image
import os
import datetime
import json
import google.generativeai as genai
from pinecone import Pinecone
from openai import OpenAI

# Upload folder for diary images
DIARY_IMAGES_FOLDER = "uploads/diary_images"
ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

# Initialize Pinecone and OpenAI for RAG
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
pinecone_index = pc.Index("diarydad")
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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
    """Generate summary of diary text using GPT API - max 3 times per day, streaming response. Saves summary to DB after completion."""
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
    
    # Check OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        return jsonify({"error": "OpenAI API key not configured on server."}), 500
    
    try:
        # Create prompt for GPT
        system_message = "You are a helpful assistant that creates concise, thoughtful summaries of diary entries."
        user_message = f"Please provide a concise summary of the following diary entry in 2-3 sentences:\n\n{diary_text}"
        
        # Increment usage count in today's diary entry
        increment_summary_generation_count(user_id, date)
        
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
                    from models.diary import upsert_diary
                    from config.db import mongo
                    from bson import ObjectId
                    
                    # Get existing diary entry
                    existing_diary_entry = mongo.db.diaries.find_one({"user_id": ObjectId(user_id), "date": date})
                    
                    if existing_diary_entry:
                        # Get existing diary object or create new one
                        diary_obj = existing_diary_entry.get("diary", {})
                        if not isinstance(diary_obj, dict):
                            diary_obj = {}
                        
                        # Update summary
                        diary_obj["summary"] = full_summary.strip()
                        
                        # Save to database
                        upsert_diary(user_id, date, diary_obj=diary_obj)
                    else:
                        # Create new diary entry with summary
                        upsert_diary(user_id, date, diary={"summary": full_summary.strip()})
                    
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
        system_message = """You are a helpful assistant that helps users understand and reflect on their diary entries. 
Based on the diary entries provided, answer the user's question in a thoughtful, empathetic, and concise manner.
If the context doesn't contain relevant information to answer the question, politely let the user know.
Be warm, understanding, and focus on helping the user gain insights from their diary entries."""
        
        user_message = f"""Relevant Diary Entries:
{context}

User Question: {query}

Please provide a helpful response based on the diary entries above:"""
        
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

