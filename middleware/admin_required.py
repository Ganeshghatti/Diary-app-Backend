from functools import wraps
from flask import request, jsonify, g
import jwt
import os

def admin_required(f):
    """Decorator to require admin authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        
        # Check if token is in headers
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(' ')[1]  # Extract token from "Bearer TOKEN"
            except IndexError:
                return jsonify({"error": "Authorization header format invalid. Use: Bearer <token>"}), 401
        
        if not token:
            return jsonify({"error": "Authorization header missing"}), 401
        
        try:
            # Decode token
            secret_key = os.getenv("JWT_SECRET")
            decoded = jwt.decode(token, secret_key, algorithms=["HS256"])
            
            # Check if admin token
            if decoded.get("role") != "admin" or decoded.get("email") != "tech@diarydad.me":
                return jsonify({"error": "Admin access required"}), 403
            
            # Store admin info in g
            g.admin_email = decoded.get("email")
            g.admin_role = decoded.get("role")
            
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token has expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401
        except Exception as e:
            return jsonify({"error": f"Token verification failed: {str(e)}"}), 401
        
        return f(*args, **kwargs)
    
    return decorated_function

