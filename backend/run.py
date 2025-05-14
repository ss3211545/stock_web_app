from app import create_app, socketio
import sys
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("stock_web_app.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

app = create_app()

if __name__ == '__main__':
    print("启动股票筛选Web应用服务...")
    print("访问 http://localhost:5000 查看应用")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True) 