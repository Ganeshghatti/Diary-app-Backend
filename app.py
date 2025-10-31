from flask import Flask, send_from_directory
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from config.db import init_db
from routes.auth import auth_routes
from routes.diary import diary_routes
from routes.user import user_routes
import os

app = Flask(__name__)
CORS(app)

# Serve profile pictures
@app.route("/uploads/profile_pics/<filename>")
def serve_profile_pic(filename):
    """Serve profile picture files"""
    return send_from_directory("uploads/profile_pics", filename)

# Global rate limit (e.g., 2000 requests per hour per IP)
limiter = Limiter(app=app, key_func=get_remote_address, default_limits=["2000 per hour"])

# Initialize MongoDB
init_db(app)

# Register routes
app.register_blueprint(auth_routes)
app.register_blueprint(diary_routes)
app.register_blueprint(user_routes)

@app.route("/")
def index():
    return "Hello, World!"
    
if __name__ == "__main__":
    app.run(debug=True, port=4000) 
