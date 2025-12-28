
import jwt
import datetime
from functools import wraps
from flask import request, jsonify, g
from app.config.settings import Config
from app.utils.logger import get_logger

logger = get_logger(__name__)

def generate_token(username):
    """Generate JWT token."""
    try:
        payload = {
            'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7),
            'iat': datetime.datetime.utcnow(),
            'sub': username
        }
        return jwt.encode(
            payload,
            Config.SECRET_KEY,
            algorithm='HS256'
        )
    except Exception as e:
        logger.error(f"Token generation failed: {e}")
        return None

def verify_token(token):
    """Verify JWT token."""
    try:
        payload = jwt.decode(token, Config.SECRET_KEY, algorithms=['HS256'])
        return payload['sub']
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def login_required(f):
    """Decorator that enforces Bearer token auth."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # Read token from Authorization: Bearer <token>
        auth_header = request.headers.get('Authorization')
        if auth_header:
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == 'bearer':
                token = parts[1]
        
        if not token:
            return jsonify({'code': 401, 'msg': 'Token missing', 'data': None}), 401
        
        username = verify_token(token)
        if not username:
            return jsonify({'code': 401, 'msg': 'Token invalid or expired', 'data': None}), 401
            
        # Store user in flask.g
        g.user = username
        return f(*args, **kwargs)
        
    return decorated

