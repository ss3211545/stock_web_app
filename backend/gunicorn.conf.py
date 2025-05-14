# Gunicorn配置文件

# 绑定的IP和端口
bind = "0.0.0.0:5000"

# 工作进程数
workers = 4

# 工作模式
worker_class = "eventlet"

# 超时时间
timeout = 120

# 日志配置
accesslog = "./access.log"
errorlog = "./error.log"
loglevel = "info"

# 重载
reload = True 