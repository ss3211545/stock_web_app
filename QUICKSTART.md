# 快速启动指南

本指南帮助您快速启动和测试尾盘选股八大步骤Web应用。

## 开发环境快速启动

### 前提条件

- Python 3.6+
- pip

### 步骤1: 安装依赖

进入backend目录并安装所需依赖：

```bash
cd stock-web-app/backend
pip install -r requirements.txt
```

### 步骤2: 运行应用

启动开发服务器：

```bash
python run.py
```

如果一切正常，您应该看到以下输出：

```
启动股票筛选Web应用服务...
访问 http://localhost:5000 查看应用
```

### 步骤3: 打开浏览器

访问 http://localhost:5000 查看应用。

## 快速测试

以下是测试应用主要功能的步骤：

### 1. 数据源和市场选择

- 在左侧面板中选择数据源（默认为新浪财经）
- 选择要筛选的市场（如上证或深证）

### 2. 开始筛选

- 点击"开始筛选"按钮
- 观察筛选进度条和步骤可视化
- 查看右侧的筛选日志了解实时状态

### 3. 查看结果

- 筛选完成后，结果将显示在表格中
- 点击任何一行查看该股票的详细信息
- K线图将自动加载并显示

### 4. 导出结果

- 点击"导出结果到CSV"按钮
- 浏览器会自动下载包含筛选结果的CSV文件

## 常见问题排查

### 无法启动应用

- 检查Python版本：`python --version`
- 确认所有依赖已安装：`pip list`
- 查看错误日志

### 无法获取股票数据

- 确认网络连接正常
- 尝试切换数据源
- 检查是否需要启用数据降级策略

### K线图不显示

- 检查浏览器控制台是否有JavaScript错误
- 确认ECharts库已正确加载
- 尝试刷新页面

## 生产环境快速部署

请参考 [README.md](README.md) 中的生产环境部署说明，了解如何使用Gunicorn和Nginx进行生产部署。 