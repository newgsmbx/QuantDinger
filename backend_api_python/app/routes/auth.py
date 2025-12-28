
from flask import Blueprint, request, jsonify
from app.config.settings import Config
from app.utils.auth import generate_token
from app.utils.logger import get_logger

auth_bp = Blueprint('auth', __name__)
logger = get_logger(__name__)

@auth_bp.route('/login', methods=['POST'])
def login():
    """Login (single-user, env-configured credentials)."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'code': 400, 'msg': 'No data provided', 'data': None}), 400
            
        username = data.get('username') or data.get('account')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({'code': 400, 'msg': 'Missing username or password', 'data': None}), 400
            
        # Validate credentials from environment / settings
        if username == Config.ADMIN_USER and password == Config.ADMIN_PASSWORD:
            token = generate_token(username)
            if token:
                return jsonify({
                    'code': 1,
                    'msg': 'Login successful',
                    'data': {
                        'token': token,
                        'userinfo': {
                            'username': username,
                            'nickname': 'Admin',
                            'avatar': ''
                        }
                    }
                })
            else:
                return jsonify({'code': 500, 'msg': 'Token generation error', 'data': None}), 500
        else:
            return jsonify({'code': 0, 'msg': 'Invalid credentials', 'data': None}), 401
            
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({'code': 500, 'msg': str(e), 'data': None}), 500

@auth_bp.route('/logout', methods=['POST'])
def logout():
    """Logout (client removes token; server is stateless)."""
    return jsonify({'code': 1, 'msg': 'Logout successful', 'data': None})

@auth_bp.route('/info', methods=['GET'])
def get_user_info():
    """Get user info (single-user mock)."""
    return jsonify({
        'code': 1,
        'msg': 'Success',
        'data': {
            'id': 1,
            'username': Config.ADMIN_USER,
            'nickname': 'Admin',
            'avatar': '/avatar2.jpg',
            'role': {'id': 'admin', 'permissions': ['dashboard', 'exception', 'account']}
        }
    })

