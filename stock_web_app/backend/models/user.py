import uuid
from datetime import datetime
import hashlib
import os
import json
from utils.db import get_db

class User:
    """用户模型"""
    
    def __init__(self, username, email, id=None, password_hash=None, 
                 settings=None, created_at=None):
        self.id = id or str(uuid.uuid4())
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.settings = settings or {}
        self.created_at = created_at or datetime.now()
    
    def set_password(self, password):
        """设置密码"""
        salt = os.urandom(32)
        self.password_hash = self._hash_password(password, salt)
    
    def check_password(self, password):
        """验证密码"""
        if not self.password_hash:
            return False
        
        # 从存储的密码哈希中提取盐值
        stored_hash = bytes.fromhex(self.password_hash)
        salt = stored_hash[:32]  # 盐值是前32字节
        
        # 计算哈希值并比较
        calculated_hash = self._hash_password(password, salt)
        
        return calculated_hash == self.password_hash
    
    def _hash_password(self, password, salt):
        """计算密码哈希值"""
        # 使用PBKDF2算法对密码进行哈希
        key = hashlib.pbkdf2_hmac(
            'sha256',  # 哈希函数
            password.encode('utf-8'),  # 密码转换为bytes
            salt,  # 盐值
            100000,  # 迭代次数
            dklen=64  # 密钥长度
        )
        
        # 将盐值和密钥合并
        hash_bytes = salt + key
        
        # 转换为十六进制字符串
        return hash_bytes.hex()
    
    def save(self):
        """保存用户到数据库"""
        db = get_db()
        cursor = db.cursor()
        
        # 检查用户是否已存在
        cursor.execute(
            "SELECT id FROM users WHERE id = %s",
            (self.id,)
        )
        
        user_exists = cursor.fetchone()
        
        if user_exists:
            # 更新用户
            cursor.execute(
                """
                UPDATE users 
                SET username = %s, email = %s, password_hash = %s, settings = %s
                WHERE id = %s
                """,
                (
                    self.username, 
                    self.email, 
                    self.password_hash,
                    json.dumps(self.settings),
                    self.id
                )
            )
        else:
            # 创建新用户
            cursor.execute(
                """
                INSERT INTO users (id, username, email, password_hash, settings, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    self.id,
                    self.username,
                    self.email,
                    self.password_hash,
                    json.dumps(self.settings),
                    self.created_at
                )
            )
        
        db.commit()
        return self.id
    
    @classmethod
    def find_by_id(cls, user_id):
        """通过ID查找用户"""
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute(
            """
            SELECT id, username, email, password_hash, settings, created_at
            FROM users
            WHERE id = %s
            """,
            (user_id,)
        )
        
        user_data = cursor.fetchone()
        
        if not user_data:
            return None
        
        # 解析JSON字段
        settings = json.loads(user_data[4]) if user_data[4] else {}
        
        return cls(
            id=user_data[0],
            username=user_data[1],
            email=user_data[2],
            password_hash=user_data[3],
            settings=settings,
            created_at=user_data[5]
        )
    
    @classmethod
    def find_by_username(cls, username):
        """通过用户名查找用户"""
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute(
            """
            SELECT id, username, email, password_hash, settings, created_at
            FROM users
            WHERE username = %s
            """,
            (username,)
        )
        
        user_data = cursor.fetchone()
        
        if not user_data:
            return None
        
        # 解析JSON字段
        settings = json.loads(user_data[4]) if user_data[4] else {}
        
        return cls(
            id=user_data[0],
            username=user_data[1],
            email=user_data[2],
            password_hash=user_data[3],
            settings=settings,
            created_at=user_data[5]
        )
    
    @classmethod
    def find_by_email(cls, email):
        """通过邮箱查找用户"""
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute(
            """
            SELECT id, username, email, password_hash, settings, created_at
            FROM users
            WHERE email = %s
            """,
            (email,)
        )
        
        user_data = cursor.fetchone()
        
        if not user_data:
            return None
        
        # 解析JSON字段
        settings = json.loads(user_data[4]) if user_data[4] else {}
        
        return cls(
            id=user_data[0],
            username=user_data[1],
            email=user_data[2],
            password_hash=user_data[3],
            settings=settings,
            created_at=user_data[5]
        ) 