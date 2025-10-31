"""
Script to load dummy diary entries for testing the RAG chat system.
This script will create diary entries in MongoDB and embed them in Pinecone.

Usage:
    python load_dummy_diaries.py <user_id>

Note: The user_id should be a valid MongoDB ObjectId from your users collection.
You can also use this via the API by making POST requests to /diary endpoint with the entries from dummy_diary_entries.json
"""

import sys
import os
import json
from datetime import datetime, timezone
from bson import ObjectId
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import Flask app to use database connection
from config.db import init_db
from flask import Flask
from models.diary import upsert_diary

# Import embedding functions
from pinecone import Pinecone
from openai import OpenAI

app = Flask(__name__)
init_db(app)

# Initialize Pinecone and OpenAI
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
pinecone_index = pc.Index("diarydad")
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def create_embedding(text):
    """Create embedding using OpenAI text-embedding-3-small model"""
    try:
        response = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        raise Exception(f"Failed to create embedding: {str(e)}")

def prepare_text_for_embedding(diary_obj, mood_tracker=None, expense_tracker=None, health_stats=None):
    """Prepare text content from diary entry for embedding"""
    text_parts = []
    
    # Add diary content and summary
    if diary_obj:
        if isinstance(diary_obj, dict):
            if "content" in diary_obj and diary_obj["content"]:
                text_parts.append(f"Content: {diary_obj['content']}")
            if "summary" in diary_obj and diary_obj["summary"]:
                text_parts.append(f"Summary: {diary_obj['summary']}")
    
    # Add mood tracker
    if mood_tracker and isinstance(mood_tracker, list) and len(mood_tracker) > 0:
        text_parts.append(f"Moods: {', '.join(mood_tracker)}")
    
    # Add expense tracker summary
    if expense_tracker and isinstance(expense_tracker, list) and len(expense_tracker) > 0:
        expense_summary = []
        for item in expense_tracker:
            if isinstance(item, dict) and "name" in item:
                expense_summary.append(item["name"])
        if expense_summary:
            text_parts.append(f"Expenses: {', '.join(expense_summary)}")
    
    # Add health stats summary
    if health_stats and isinstance(health_stats, list) and len(health_stats) > 0:
        health_summary = []
        for item in health_stats:
            if isinstance(item, dict) and "name" in item and "value" in item:
                health_summary.append(f"{item['name']}: {item['value']}")
        if health_summary:
            text_parts.append(f"Health: {', '.join(health_summary)}")
    
    # Join all parts
    combined_text = " | ".join(text_parts)
    
    # Return a default text if empty to ensure we always have something to embed
    return combined_text if combined_text else "Diary entry"

def upsert_to_pinecone(user_id, date, diary_obj, mood_tracker, expense_tracker, health_stats):
    """Upsert diary entry to Pinecone vector database"""
    try:
        # Prepare text for embedding
        text_to_embed = prepare_text_for_embedding(diary_obj, mood_tracker, expense_tracker, health_stats)
        
        # Create embedding
        embedding = create_embedding(text_to_embed)
        
        # Create unique vector ID (user_id_date)
        vector_id = f"{user_id}_{date}"
        
        # Prepare metadata
        metadata = {
            "user_id": user_id,
            "date": date,
            "text": text_to_embed
        }
        
        # Add diary content to metadata if available
        if diary_obj and isinstance(diary_obj, dict):
            if "content" in diary_obj:
                metadata["content"] = diary_obj["content"][:1000]  # Limit metadata size
        
        # Upsert to Pinecone
        pinecone_index.upsert(
            vectors=[{
                "id": vector_id,
                "values": embedding,
                "metadata": metadata
            }]
        )
        
    except Exception as e:
        # Log error but don't fail the main request
        print(f"Warning: Failed to upsert to Pinecone: {str(e)}")
        raise

def load_dummy_entries(user_id):
    """Load dummy diary entries for a user"""
    
    # Read dummy entries
    with open('dummy_diary_entries.json', 'r') as f:
        entries = json.load(f)
    
    print(f"Loading {len(entries)} dummy diary entries for user: {user_id}")
    
    # Process each entry
    for entry in entries:
        date = entry['date']
        diary_obj = entry.get('diary')
        mood_tracker = entry.get('mood_tracker')
        expense_tracker = entry.get('expense_tracker')
        health_stats = entry.get('health_stats')
        
        print(f"\nProcessing entry for date: {date}")
        
        # Upsert to MongoDB
        try:
            result = upsert_diary(user_id, date, diary_obj, mood_tracker, expense_tracker, health_stats)
            if result["upserted"]:
                print(f"  ✓ Created new diary entry")
            else:
                print(f"  ✓ Updated existing diary entry")
        except Exception as e:
            print(f"  ✗ Error upserting to MongoDB: {str(e)}")
            continue
        
        # Embed and store in Pinecone
        try:
            upsert_to_pinecone(user_id, date, diary_obj, mood_tracker, expense_tracker, health_stats)
            print(f"  ✓ Embedded and stored in Pinecone")
        except Exception as e:
            print(f"  ✗ Error embedding to Pinecone: {str(e)}")
    
    print(f"\n✓ Completed loading dummy entries for user: {user_id}")

if __name__ == "__main__":
    
    user_id = "690445ec9475e6559cf776b0"
    
    # Validate ObjectId format
    try:
        ObjectId(user_id)
    except:
        print(f"Error: '{user_id}' is not a valid MongoDB ObjectId")
        sys.exit(1)
    
    load_dummy_entries(user_id)

