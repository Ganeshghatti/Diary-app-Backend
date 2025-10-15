from flask import request, jsonify, g
import jwt
import os
from models.user import find_user

def user_required(f):
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Authorization header missing or invalid'}), 401
        token = auth_header.split(' ')[1]
        jwt_secret = os.getenv('JWT_SECRET')
        if not jwt_secret:
            return jsonify({'error': 'JWT secret not configured on server.'}), 500
        try:
            payload = jwt.decode(token, jwt_secret, algorithms=['HS256'])
            phone = payload.get('phone')
            if not phone:
                return jsonify({'error': 'Invalid token: phone missing'}), 401
            user = find_user(phone)
            if not user:
                return jsonify({'error': 'User not found'}), 401
            g.current_user = user
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper
