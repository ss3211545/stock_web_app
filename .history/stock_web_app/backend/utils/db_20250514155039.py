import os
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import g, current_app

def get_db():
    """获取数据库连接"""
    if 'db' not in g:
        g.db = psycopg2.connect(
            host=os.environ.get('DB_HOST', 'localhost'),
            database=os.environ.get('DB_NAME', 'stock_web_app'),
            user=os.environ.get('DB_USER', 'postgres'),
            password=os.environ.get('DB_PASSWORD', 'postgres'),
            port=os.environ.get('DB_PORT', '5432'),
            cursor_factory=RealDictCursor
        )
    return g.db

def close_db(e=None):
    """关闭数据库连接"""
    db = g.pop('db', None)
    
    if db is not None:
        db.close()

def init_app(app):
    """初始化数据库连接"""
    app.teardown_appcontext(close_db)

def init_db():
    """初始化数据库表结构"""
    db = get_db()
    cursor = db.cursor()
    
    # 创建用户表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id VARCHAR(36) PRIMARY KEY,
        username VARCHAR(100) UNIQUE NOT NULL,
        email VARCHAR(100) UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        settings JSONB,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # 创建筛选结果表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS filter_results (
        id VARCHAR(36) PRIMARY KEY,
        user_id VARCHAR(36) REFERENCES users(id),
        market VARCHAR(10) NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        filter_parameters JSONB,
        matched_stocks JSONB,
        filter_steps_data JSONB
    )
    ''')
    
    # 创建股票数据表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS stock_data (
        code VARCHAR(20) PRIMARY KEY,
        market VARCHAR(10) NOT NULL,
        name VARCHAR(100),
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        daily_data JSONB,
        metadata JSONB
    )
    ''')
    
    # 创建任务表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tasks (
        id VARCHAR(36) PRIMARY KEY,
        user_id VARCHAR(36) REFERENCES users(id),
        task_type VARCHAR(20) NOT NULL,
        status VARCHAR(20) NOT NULL,
        progress INTEGER DEFAULT 0,
        message TEXT,
        parameters JSONB,
        result_id VARCHAR(36),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP
    )
    ''')
    
    # 创建定时任务表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS scheduled_tasks (
        id VARCHAR(36) PRIMARY KEY,
        user_id VARCHAR(36) REFERENCES users(id),
        name VARCHAR(100),
        description TEXT,
        task_type VARCHAR(20) NOT NULL,
        schedule VARCHAR(100) NOT NULL,
        parameters JSONB,
        is_active BOOLEAN DEFAULT TRUE,
        last_run TIMESTAMP,
        next_run TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    db.commit() 