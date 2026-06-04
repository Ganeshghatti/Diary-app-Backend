from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from config.db import init_db
from routes.auth import auth_routes
from routes.diary import diary_routes
from routes.user import user_routes
from routes.admin import admin_routes

app = Flask(__name__)
CORS(app)

# Block public access to image folders
@app.route("/uploads/profile_pics/<filename>")
def block_profile_pic(filename):
    """Block public access to profile pictures"""
    return jsonify({"error": "Access denied. Images are not publicly accessible."}), 403

DIARY_IMAGES_FOLDER = "uploads/diary_images"


@app.route("/uploads/diary_images/<filename>")
def serve_diary_image(filename):
    """Serve diary images for public URL access."""
    safe_name = secure_filename(filename)
    if not safe_name or safe_name != filename:
        return jsonify({"error": "Invalid filename."}), 400
    return send_from_directory(DIARY_IMAGES_FOLDER, safe_name)

# Global rate limit (e.g., 2000 requests per hour per IP)
limiter = Limiter(app=app, key_func=get_remote_address, default_limits=["2000 per hour"])

# Initialize MongoDB
init_db(app)

# Register routes
app.register_blueprint(auth_routes)
app.register_blueprint(diary_routes)
app.register_blueprint(user_routes)
app.register_blueprint(admin_routes)

@app.route("/")
def index():
    return "Hello, World!"
    
if __name__ == "__main__":
    app.run(debug=True, port=4000) 
