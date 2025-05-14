#!/bin/bash

# 设置颜色变量
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # 无颜色

echo -e "${GREEN}==== 尾盘选股系统 - Web版 启动脚本 ====${NC}"
echo -e "${YELLOW}准备启动服务...${NC}"

# 检查Docker是否安装
if ! command -v docker &> /dev/null; then
    echo "Docker未安装，请先安装Docker和Docker Compose"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "Docker Compose未安装，请先安装Docker Compose"
    exit 1
fi

# 生成随机密钥
generate_key() {
    cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 32 | head -n 1
}

# 检查.env文件是否存在，不存在则创建
if [ ! -f .env ]; then
    echo -e "${YELLOW}未检测到.env文件，将创建新的环境配置${NC}"
    
    # 生成随机密钥
    SECRET_KEY=$(generate_key)
    JWT_SECRET_KEY=$(generate_key)
    
    # 创建.env文件
    cat > .env << EOF
# 数据库设置
DB_HOST=postgres
DB_NAME=stock_web_app
DB_USER=postgres
DB_PASSWORD=postgres
DB_PORT=5432

# 应用密钥
SECRET_KEY=${SECRET_KEY}
JWT_SECRET_KEY=${JWT_SECRET_KEY}

# Celery配置
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# 前端配置
VUE_APP_API_URL=http://localhost:5000/api

# 数据API配置
ALLTICK_API_TOKEN=your_alltick_api_token_here
EOF
    
    echo -e "${GREEN}已创建.env文件并生成随机密钥${NC}"
    read -p "是否要编辑.env文件? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        ${EDITOR:-vi} .env
    fi
fi

# 构建并启动容器
echo -e "${YELLOW}正在构建和启动服务...${NC}"
docker-compose up -d --build

# 等待服务启动
echo -e "${YELLOW}等待服务启动...${NC}"
sleep 10

# 初始化数据库
echo -e "${YELLOW}正在初始化数据库...${NC}"
docker-compose exec backend python init_db.py

# 显示服务状态
echo -e "${GREEN}服务已启动!${NC}"
docker-compose ps

# 显示访问信息
echo -e "\n${GREEN}======================================================${NC}"
echo -e "${GREEN}尾盘选股系统已成功启动!${NC}"
echo -e "${GREEN}前端访问地址: http://localhost${NC}"
echo -e "${GREEN}API访问地址: http://localhost:5000/api${NC}"
echo -e "${GREEN}默认管理员账户: admin / Admin12345${NC}"
echo -e "${GREEN}======================================================${NC}"

echo -e "\n${YELLOW}提示:${NC}"
echo -e "- 使用 ${GREEN}docker-compose logs -f${NC} 查看日志"
echo -e "- 使用 ${GREEN}docker-compose down${NC} 停止服务"
echo -e "- 使用 ${GREEN}docker-compose restart${NC} 重启服务" 