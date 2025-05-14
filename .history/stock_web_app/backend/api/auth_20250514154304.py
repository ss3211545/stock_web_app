from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token, jwt_required, get_jwt_identity
)
from models.user import User
from utils.validators import validate_email, validate_password

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
def register():
    """注册新用户"""
    data = request.get_json()
    
    # 验证输入
    if not data or not data.get('username') or not data.get('email') or not data.get('password'):
        return jsonify({"error": "所有字段都是必填的"}), 400
    
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    
    # 验证邮箱格式
    if not validate_email(email):
        return jsonify({"error": "无效的邮箱格式"}), 400
    
    # 验证密码强度
    if not validate_password(password):
        return jsonify({"error": "密码必须至少8个字符，包含数字和字母"}), 400
    
    # 检查用户是否已存在
    if User.find_by_username(username):
        return jsonify({"error": "用户名已存在"}), 400
    
    if User.find_by_email(email):
        return jsonify({"error": "邮箱已注册"}), 400
    
    # 创建新用户
    user = User(username=username, email=email)
    user.set_password(password)
    user.save()
    
    # 生成访问令牌
    access_token = create_access_token(identity=user.id)
    
    return jsonify({
        "message": "用户注册成功",
        "access_token": access_token,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email
        }
    }), 201

@auth_bp.route('/login', methods=['POST'])
def login():
    """用户登录"""
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "无效的数据"}), 400
    
    # 支持用户名或邮箱登录
    username_or_email = data.get('username')
    password = data.get('password')
    
    if not username_or_email or not password:
        return jsonify({"error": "用户名和密码都是必填的"}), 400
    
    # 查找用户
    user = User.find_by_username(username_or_email) or User.find_by_email(username_or_email)
    
    if not user or not user.check_password(password):
        return jsonify({"error": "无效的用户名或密码"}), 401
    
    # 生成访问令牌
    access_token = create_access_token(identity=user.id)
    
    return jsonify({
        "access_token": access_token,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email
        }
    })

@auth_bp.route('/user', methods=['GET'])
@jwt_required()
def get_user():
    """获取当前登录用户信息"""
    user_id = get_jwt_identity()
    user = User.find_by_id(user_id)
    
    if not user:
        return jsonify({"error": "用户不存在"}), 404
    
    return jsonify({
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "settings": user.settings
        }
    })

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """用户登出 - 客户端只需销毁token"""
    return jsonify({"message": "成功登出"}) 