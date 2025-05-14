# 构建阶段
FROM node:14 AS build

WORKDIR /app

# 复制项目文件
COPY ./frontend/package.json ./frontend/package-lock.json* ./

# 安装依赖
RUN npm install

# 复制其余文件
COPY ./frontend .

# 设置API地址环境变量
ENV VUE_APP_API_URL=http://localhost:5000/api

# 构建前端应用
RUN npm run build

# 部署阶段
FROM nginx:stable-alpine

# 从构建阶段复制构建结果
COPY --from=build /app/dist /usr/share/nginx/html

# 复制Nginx配置文件
COPY ./docker/nginx.conf /etc/nginx/conf.d/default.conf

# 暴露端口
EXPOSE 80

# 启动Nginx
CMD ["nginx", "-g", "daemon off;"] 