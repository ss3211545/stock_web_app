<<<<<<< HEAD
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
=======
# 尾盘选股八大步骤系统

基于尾盘选股八大步骤策略的自动化选股系统，支持多种数据源，可视化界面展示，并具备自动定时筛选功能。

## 功能特点

- **八大步骤自动筛选**：实现完整的尾盘选股八大步骤策略
- **多数据源支持**：支持新浪财经API、和讯API、AllTick API等多种数据源
- **可视化界面**：直观展示筛选结果，K线图表分析
- **自动定时执行**：可设置在尾盘时段(14:30-15:00)自动执行筛选
- **结果导出**：支持将筛选结果导出到CSV文件
- **动态市场监测**：自动检测交易时段，识别尾盘时间

## 系统截图

(系统截图将在首次使用后添加)

## 安装说明

### 1. 安装依赖项

```bash
# 安装依赖项
pip install -r requirements.txt
```

### 2. 配置说明

本系统默认使用新浪财经API作为数据源，该数据源在国内访问速度最快，且无需注册。

如果需要使用AllTick API，需要在[alltick.co](https://alltick.co)注册账号并获取API Token。

## 使用方法

### 图形界面模式

运行以下命令启动图形界面：

```bash
python app.py
```

在图形界面中：
1. 选择数据源（新浪财经/和讯/AllTick）
2. 选择市场（上证/深证/港股/美股）
3. 点击"运行筛选"按钮执行筛选
4. 查看结果列表和详细分析

### 命令行模式（定时任务）

如果需要设置定时任务，可以运行调度器：

```bash
python scheduler.py
```

默认情况下，调度器会在每个工作日的14:30自动执行尾盘选股策略。

## 尾盘选股八大步骤说明

该系统实现了完整的尾盘选股八大步骤策略：

1. **涨幅筛选**：筛选当日涨幅在3%-5%之间的股票
2. **量比筛选**：筛选量比大于1的股票
3. **换手率筛选**：筛选换手率在5%-10%之间的股票
4. **市值筛选**：筛选市值在50亿-200亿之间的股票
5. **成交量分析**：筛选成交量持续放大的股票
6. **均线分析**：筛选短期均线搭配60日线向上的股票
7. **强弱分析**：筛选强于大盘的股票
8. **尾盘创新高**：筛选尾盘阶段创新高的股票

系统会逐步应用这八个步骤，最终筛选出符合所有条件的潜力股票。

## 文件说明

- `data_fetcher.py`：数据获取器，支持多种API源
- `app.py`：图形界面应用程序
- `scheduler.py`：定时任务调度器
- `requirements.txt`：依赖项列表
- `README.md`：使用说明

## 注意事项

- 本系统仅供学习研究使用，不构成投资建议
- 使用新浪财经API和和讯API时无需注册，国内访问速度最快
- 使用AllTick API需要注册账号并获取Token
- 建议在交易时段运行，以获取最准确的数据

## 后续规划

- 增加更多技术指标分析
- 支持自定义筛选条件
- 增加回测功能
- 增加股票池管理
- 增加短信/邮件通知功能

## 贡献与反馈

欢迎提出建议和改进意见，共同完善尾盘选股系统。

---

**免责声明**：本系统仅供学习研究使用，不构成任何投资建议。投资有风险，入市需谨慎。 
>>>>>>> aa5aa3044ff99e396c981bb42aab76931d61a807
