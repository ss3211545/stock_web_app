from flask import render_template, redirect, url_for
from app import create_app

app = create_app()

@app.route('/')
def index():
    """首页路由，加载Vue应用"""
    return render_template('index.html')

@app.route('/health')
def health():
    """健康检查路由"""
    return {'status': 'ok', 'version': '1.0.0'} 