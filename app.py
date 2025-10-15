from flask import Flask
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from config.db import init_db
from routes.auth import auth_routes
from routes.diary import diary_routes

app = Flask(__name__)
CORS(app)

# Global rate limit (e.g., 2000 requests per hour per IP)
limiter = Limiter(app=app, key_func=get_remote_address, default_limits=["2000 per hour"])

# Initialize MongoDB
init_db(app)

# Register routes
app.register_blueprint(auth_routes)
app.register_blueprint(diary_routes)

if __name__ == "__main__":
    app.run(debug=True, port=4000)
