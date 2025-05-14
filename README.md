# 尾盘选股八大步骤 Web应用

这是一个基于Web的股票筛选应用，实现了"尾盘选股八大步骤"策略的自动化筛选功能。

## 主要功能

- 支持多种数据源（新浪财经、和讯财经、AllTick API）
- 市场选择（上证、深证、北证、港股、美股）
- 八大步骤自动筛选流程
- 筛选进度可视化
- K线图展示
- 股票详情数据分析
- 结果导出为CSV
- 自动判断尾盘时段

## 技术架构

- 前端：Vue.js 3 + Element Plus + ECharts
- 后端：Flask + Flask-SocketIO
- 数据库：不需要（直接调用API）

## 部署步骤

### 准备工作

1. 确保安装了Python 3.6+
2. 克隆此仓库到本地

```bash
git clone <repo-url>
cd stock-web-app
```

### 开发环境运行

1. 安装后端依赖

```bash
cd backend
pip install -r requirements.txt
```

2. 运行开发服务器

```bash
python run.py
```

3. 访问 http://localhost:5000 查看应用

### 生产环境部署

#### 使用Gunicorn和Nginx

1. 安装生产环境依赖

```bash
pip install gunicorn eventlet
```

2. 使用Gunicorn启动应用

```bash
cd backend
gunicorn -c gunicorn.conf.py 'app:create_app()'
```

3. 配置Nginx

将`nginx.conf`文件中的配置复制到您的Nginx配置中（通常在`/etc/nginx/sites-available/`目录下），然后修改域名和路径：

```bash
# 替换示例配置中的路径和域名
sudo cp nginx.conf /etc/nginx/sites-available/tailmarket
sudo sed -i 's/tailmarket.example.com/您的域名/g' /etc/nginx/sites-available/tailmarket
sudo sed -i 's/\/path\/to\/stock-web-app\/backend/实际路径/g' /etc/nginx/sites-available/tailmarket

# 启用站点配置
sudo ln -s /etc/nginx/sites-available/tailmarket /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

4. 设置开机自启动（可选，使用systemd）

创建服务文件 `/etc/systemd/system/tailmarket.service`：

```ini
[Unit]
Description=Tail Market Stock App
After=network.target

[Service]
User=your_username
WorkingDirectory=/path/to/stock-web-app/backend
ExecStart=/usr/local/bin/gunicorn -c gunicorn.conf.py 'app:create_app()'
Restart=always

[Install]
WantedBy=multi-user.target
```

启用服务：

```bash
sudo systemctl enable tailmarket
sudo systemctl start tailmarket
```

## 使用说明

1. 进入首页后，选择数据源和市场
2. 如需使用AllTick API，请输入您的Token
3. 配置数据降级策略（可选）
4. 点击"开始筛选"按钮开始执行筛选流程
5. 筛选完成后，可以查看筛选结果和详细数据
6. 点击结果表格中的股票可查看K线图和详细信息
7. 使用"导出结果到CSV"按钮可导出结果

## 常见问题

### 无法启动应用

确保安装了所有依赖，并且端口5000未被占用。可以修改`run.py`中的端口号。

### 无法获取数据

检查网络连接和API数据源状态。本应用支持数据降级策略，如果主要数据源不可用，可以启用降级。

### 如何更新

获取最新代码并重启应用：

```bash
git pull
cd backend
pip install -r requirements.txt  # 如有依赖更新
# 然后重启服务
sudo systemctl restart tailmarket  # 如使用systemd
```

## 许可证

MIT

## 联系方式

如有问题或建议，请提交Issue或联系开发者。 