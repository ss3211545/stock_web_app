# 尾盘选股系统 - Web版

基于八大步骤的专业选股策略，从桌面应用转化为Web应用，支持多用户、远程访问、定时任务等高级功能。

## 功能特点

- **专业筛选策略**：基于尾盘八大步骤选股策略
- **多市场支持**：沪深北港美五大市场
- **数据降级策略**：在数据源不可用时自动降级
- **多用户支持**：完整的用户注册登录系统
- **定时任务**：支持定时自动筛选
- **Web访问**：随时随地通过浏览器访问
- **响应式设计**：兼容PC和移动设备

## 技术架构

### 后端

- Python + Flask：RESTful API
- PostgreSQL：关系型数据库
- Redis：缓存和消息队列
- Celery：异步任务处理

### 前端

- Vue.js：前端框架
- Element UI：UI组件库
- ECharts：图表可视化
- Axios：HTTP客户端

### 部署

- Docker：容器化部署
- NGINX：Web服务器和反向代理

## 快速启动

确保已安装Docker和Docker Compose，然后运行:

```bash
# 给启动脚本添加执行权限
chmod +x start.sh

# 运行启动脚本
./start.sh
```

启动脚本会自动:
1. 创建必要的环境配置文件
2. 构建Docker镜像
3. 启动所有服务
4. 初始化数据库
5. 创建默认管理员账户

启动后，打开浏览器访问:
- 前端应用: http://localhost
- API服务: http://localhost:5000/api

默认管理员账户:
- 用户名: admin
- 密码: Admin12345

## 手动部署步骤

如果需要手动部署，请按照以下步骤操作:

1. 克隆仓库并进入项目目录
```bash
git clone <仓库地址>
cd stock_web_app
```

2. 创建`.env`文件并设置环境变量
```bash
cat > .env << EOF
# 数据库设置
DB_HOST=postgres
DB_NAME=stock_web_app
DB_USER=postgres
DB_PASSWORD=postgres
DB_PORT=5432

# 应用密钥 (务必修改为随机值)
SECRET_KEY=your_secret_key_here
JWT_SECRET_KEY=your_jwt_secret_key_here

# Celery配置
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# 前端配置
VUE_APP_API_URL=http://localhost:5000/api

# 数据API配置
ALLTICK_API_TOKEN=your_alltick_api_token_here
EOF
```

3. 构建和启动服务
```bash
docker-compose up -d --build
```

4. 初始化数据库
```bash
docker-compose exec backend python init_db.py
```

## 开发指南

### 后端开发

1. 安装依赖
```bash
cd backend
pip install -r requirements.txt
```

2. 运行开发服务器
```bash
python app.py
```

### 前端开发

1. 安装依赖
```bash
cd frontend
npm install
```

2. 运行开发服务器
```bash
npm run serve
```

## 许可证

本项目采用MIT许可证 