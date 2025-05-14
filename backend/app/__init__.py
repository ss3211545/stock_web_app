from flask import Flask
from flask_socketio import SocketIO
from flask_cors import CORS

socketio = SocketIO()

def create_app():
    app = Flask(__name__, 
                static_folder='../static',
                template_folder='../templates')
    
    app.config['SECRET_KEY'] = 'tailmarket-stock-app-secret-key'
    
    # 允许跨域请求
    CORS(app)
    
    # 注册蓝图
    from app.api import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # 初始化SocketIO
    socketio.init_app(app, cors_allowed_origins="*")
    
    return app 