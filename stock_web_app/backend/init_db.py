#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
数据库初始化脚本
"""

import os
import sys
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from utils.db import init_db, get_db
from models.user import User

def create_admin_user():
    """创建默认管理员用户"""
    db = get_db()
    cursor = db.cursor()
    
    # 检查是否已存在admin用户
    cursor.execute("SELECT id FROM users WHERE username = 'admin'")
    admin_exists = cursor.fetchone()
    
    if not admin_exists:
        # 创建管理员用户
        admin = User(
            username="admin", 
            email="admin@example.com"
        )
        admin.set_password("Admin12345")
        admin_id = admin.save()
        
        print(f"已创建管理员用户 (ID: {admin_id})")
        print("用户名: admin")
        print("密码: Admin12345")
        print("请首次登录后修改密码")
    else:
        print("管理员用户已存在，跳过创建")

def main():
    """初始化数据库"""
    print("正在初始化数据库...")
    
    # 创建数据库表
    init_db()
    print("数据库表创建完成")
    
    # 创建管理员用户
    create_admin_user()
    
    print("数据库初始化完成")

if __name__ == "__main__":
    main() 