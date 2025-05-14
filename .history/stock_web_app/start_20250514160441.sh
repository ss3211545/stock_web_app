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

# 检查.env文件是否存在，不存在则从示例创建
if [ ! -f .env ]; then
    echo -e "${YELLOW}未检测到.env文件，将从.env.example创建${NC}"
    cp .env.example .env
    echo -e "${GREEN}已创建.env文件，请检查并修改其中的配置${NC}"
    echo -e "${YELLOW}建议在启动前修改SECRET_KEY和JWT_SECRET_KEY${NC}"
    read -p "是否立即编辑.env文件? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        ${EDITOR:-vi} .env
    fi
fi

# 构建并启动容器
echo -e "${YELLOW}正在构建和启动服务...${NC}"
docker-compose up -d

# 等待服务启动
echo -e "${YELLOW}等待服务启动...${NC}"
sleep 10

# 初始化数据库
echo -e "${YELLOW}正在初始化数据库...${NC}"
docker-compose exec backend python -c "from utils.db import init_db; init_db()"

# 显示服务状态
echo -e "${GREEN}服务已启动!${NC}"
docker-compose ps

# 显示访问信息
echo -e "\n${GREEN}======================================================${NC}"
echo -e "${GREEN}尾盘选股系统已成功启动!${NC}"
echo -e "${GREEN}前端访问地址: http://localhost${NC}"
echo -e "${GREEN}API访问地址: http://localhost:5000/api${NC}"
echo -e "${GREEN}======================================================${NC}"

echo -e "\n${YELLOW}提示:${NC}"
echo -e "- 使用 ${GREEN}docker-compose logs -f${NC} 查看日志"
echo -e "- 使用 ${GREEN}docker-compose down${NC} 停止服务"
echo -e "- 使用 ${GREEN}docker-compose restart${NC} 重启服务" 