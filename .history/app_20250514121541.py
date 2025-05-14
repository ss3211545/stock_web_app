import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
from datetime import datetime, timedelta
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import schedule
import csv
import os
import traceback

# 导入数据获取器
from data_fetcher import StockDataFetcher

class TailMarketStockApp:
    """
    尾盘选股八大步骤应用程序
    实现图形界面展示和自动筛选功能
    """
    
    def __init__(self, root):
        """初始化应用程序"""
        self.root = root
        self.root.title("尾盘选股八大步骤")
        self.root.geometry("1200x800")
        self.root.minsize(1000, 700)
        
        # 创建数据获取器（默认使用新浪API，速度最快）
        self.data_fetcher = StockDataFetcher(api_source="sina")
        
        # 筛选结果
        self.filtered_stocks = []
        self.detailed_info = []
        self.partial_match = False  # 是否部分匹配
        self.max_step = 0  # 最大匹配步骤
        
        # 市场选择和当前选中股票
        self.selected_market = tk.StringVar(value="SH")
        self.selected_stock = None
        
        # 自动运行状态
        self.auto_run_enabled = False
        self.schedule_thread = None
        self.is_running = False
        
        # 初始化界面
        self._init_ui()
        
    def _init_ui(self):
        """初始化用户界面"""
        # 主框架
        main_frame = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 左侧控制面板
        control_frame = ttk.Frame(main_frame)
        main_frame.add(control_frame, weight=1)
        
        # 右侧数据展示面板
        data_frame = ttk.Frame(main_frame)
        main_frame.add(data_frame, weight=3)
        
        # ===== 左侧控制面板 =====
        # API选择
        api_frame = ttk.LabelFrame(control_frame, text="数据源")
        api_frame.pack(fill=tk.X, padx=5, pady=5)
        
        api_sources = [("新浪财经(推荐)", "sina"), ("和讯财经", "hexun"), ("AllTick API", "alltick")]
        self.api_var = tk.StringVar(value="sina")
        
        for i, (text, value) in enumerate(api_sources):
            ttk.Radiobutton(api_frame, text=text, value=value, variable=self.api_var, 
                          command=self._change_api_source).pack(anchor=tk.W, padx=10, pady=2)
        
        # AllTick Token输入框（初始隐藏）
        self.token_frame = ttk.Frame(api_frame)
        ttk.Label(self.token_frame, text="Token:").pack(side=tk.LEFT, padx=5)
        self.token_entry = ttk.Entry(self.token_frame, width=20)
        self.token_entry.pack(side=tk.LEFT, padx=5)
        ttk.Button(self.token_frame, text="设置", command=self._set_token).pack(side=tk.LEFT, padx=5)
        
        # 数据降级策略设置
        degradation_frame = ttk.LabelFrame(control_frame, text="数据降级策略")
        degradation_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 是否允许数据降级
        self.degradation_enabled = tk.BooleanVar(value=False)
        ttk.Checkbutton(degradation_frame, text="允许数据降级", 
                       variable=self.degradation_enabled, 
                       command=self._update_degradation_settings).pack(anchor=tk.W, padx=10, pady=2)
        
        # 降级程度
        ttk.Label(degradation_frame, text="降级程度:").pack(anchor=tk.W, padx=10, pady=2)
        self.degradation_level = tk.StringVar(value="MEDIUM")
        ttk.Radiobutton(degradation_frame, text="轻度 (仅允许高可靠性数据源替代)", 
                       value="LOW", variable=self.degradation_level).pack(anchor=tk.W, padx=20, pady=2)
        ttk.Radiobutton(degradation_frame, text="中度 (允许替代数据分析方法)", 
                       value="MEDIUM", variable=self.degradation_level).pack(anchor=tk.W, padx=20, pady=2)
        ttk.Radiobutton(degradation_frame, text="重度 (允许所有降级策略)", 
                       value="HIGH", variable=self.degradation_level).pack(anchor=tk.W, padx=20, pady=2)
        
        # 市场选择
        market_frame = ttk.LabelFrame(control_frame, text="市场")
        market_frame.pack(fill=tk.X, padx=5, pady=5)
        
        markets = [("上证", "SH"), ("深证", "SZ"), ("北证", "BJ"), ("港股", "HK"), ("美股", "US")]
        for i, (text, value) in enumerate(markets):
            ttk.Radiobutton(market_frame, text=text, value=value, variable=self.selected_market).pack(anchor=tk.W, padx=10, pady=2)
        
        # 筛选控制区
        filter_frame = ttk.LabelFrame(control_frame, text="筛选控制")
        filter_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(filter_frame, text="运行筛选", command=self.run_filter).pack(fill=tk.X, padx=10, pady=5)
        ttk.Separator(filter_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=5, pady=5)
        
        # 自动运行控制
        auto_frame = ttk.Frame(filter_frame)
        auto_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(auto_frame, text="自动运行:").pack(side=tk.LEFT, padx=5)
        self.auto_run_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(auto_frame, variable=self.auto_run_var, command=self._toggle_auto_run).pack(side=tk.LEFT, padx=5)
        ttk.Label(auto_frame, text="(在尾盘自动筛选)").pack(side=tk.LEFT, padx=5)
        
        # 筛选进度状态
        status_frame = ttk.Frame(control_frame)
        status_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(status_frame, text="状态:").pack(side=tk.LEFT, padx=5)
        self.status_label = ttk.Label(status_frame, text="就绪")
        self.status_label.pack(side=tk.LEFT, padx=5)
        
        # 筛选结果信息
        result_frame = ttk.LabelFrame(control_frame, text="结果统计")
        result_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.result_text = tk.Text(result_frame, height=10, width=30, wrap=tk.WORD)
        self.result_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.result_text.config(state=tk.DISABLED)
        
        # 导出结果按钮
        export_button = ttk.Button(control_frame, text="导出结果到CSV", command=self._export_to_csv)
        export_button.pack(fill=tk.X, padx=10, pady=10)
        
        # ===== 右侧数据展示面板 =====
        # 股票列表
        list_frame = ttk.Frame(data_frame)
        list_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 创建表格
        columns = ("代码", "名称", "价格", "涨跌幅", "成交量", "换手率", "市值(亿)")
        self.stock_table = ttk.Treeview(list_frame, columns=columns, show="headings", height=10)
        
        # 设置列格式
        for col in columns:
            self.stock_table.heading(col, text=col)
            width = 80 if col in ("代码", "价格", "涨跌幅", "换手率", "市值(亿)") else 120
            self.stock_table.column(col, width=width, anchor=tk.CENTER)
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.stock_table.yview)
        self.stock_table.configure(yscrollcommand=scrollbar.set)
        
        # 布局表格和滚动条
        self.stock_table.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 绑定选择事件
        self.stock_table.bind("<<TreeviewSelect>>", self._on_stock_select)
        
        # 详细信息标签页
        notebook = ttk.Notebook(data_frame)
        notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # K线图面板
        self.kline_frame = ttk.Frame(notebook)
        notebook.add(self.kline_frame, text="K线图")
        
        # 初始化K线图区域
        self.fig = plt.Figure(figsize=(12, 6), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.kline_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # 详细数据面板
        detail_frame = ttk.Frame(notebook)
        notebook.add(detail_frame, text="详细数据")
        
        # 详细信息文本区域
        self.detail_text = tk.Text(detail_frame, wrap=tk.WORD)
        self.detail_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.detail_text.config(state=tk.DISABLED)
        
        # 八大步骤解析面板
        steps_frame = ttk.Frame(notebook)
        notebook.add(steps_frame, text="八大步骤解析")
        
        # 步骤解析展示区域
        self.steps_text = tk.Text(steps_frame, wrap=tk.WORD)
        self.steps_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.steps_text.config(state=tk.DISABLED)
        
        # 数据质量分析面板
        quality_frame = ttk.Frame(notebook)
        notebook.add(quality_frame, text="数据质量分析")
        
        # 数据质量分析展示区域
        self.quality_text = tk.Text(quality_frame, wrap=tk.WORD)
        self.quality_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.quality_text.config(state=tk.DISABLED)
        
        # 新增: 筛选过程可视化面板
        filter_vis_frame = ttk.Frame(notebook)
        notebook.add(filter_vis_frame, text="筛选过程可视化")
        
        # 创建筛选过程可视化内容
        filter_vis_container = ttk.Frame(filter_vis_frame)
        filter_vis_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 顶部标题
        vis_title_frame = ttk.Frame(filter_vis_container)
        vis_title_frame.pack(fill=tk.X, pady=5)
        ttk.Label(vis_title_frame, text="尾盘八大步骤选股策略", style="Title.TLabel").pack(anchor=tk.CENTER)
        ttk.Label(vis_title_frame, text="一步步筛选优质股票的智能流程", style="Subtitle.TLabel").pack(anchor=tk.CENTER)
        
        # 筛选进度条
        progress_frame = ttk.Frame(filter_vis_container)
        progress_frame.pack(fill=tk.X, pady=10)
        self.filter_progress = ttk.Progressbar(progress_frame, orient=tk.HORIZONTAL, 
                                             length=100, mode='determinate', 
                                             style="Filter.Horizontal.TProgressbar")
        self.filter_progress.pack(fill=tk.X, padx=20, pady=5)
        self.progress_label = ttk.Label(progress_frame, text="准备筛选 (0/8)")
        self.progress_label.pack(anchor=tk.CENTER)
        
        # 步骤详解区域 - 使用Canvas搭配滚动条
        canvas_frame = ttk.Frame(filter_vis_container)
        canvas_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 创建Canvas和滚动条
        filter_canvas = tk.Canvas(canvas_frame, bg=THEME_COLOR, highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=filter_canvas.yview)
        filter_canvas.configure(yscrollcommand=scrollbar.set)
        
        # 放置Canvas和滚动条
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        filter_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 创建Canvas内的Frame
        self.steps_detail_frame = ttk.Frame(filter_canvas)
        filter_canvas.create_window((0, 0), window=self.steps_detail_frame, anchor=tk.NW)
        
        # 配置Canvas的滚动区域
        def _configure_canvas(event):
            filter_canvas.configure(scrollregion=filter_canvas.bbox("all"))
        self.steps_detail_frame.bind("<Configure>", _configure_canvas)
        
        # 创建八大步骤详解卡片
        self._create_filter_steps_cards()
        
        # 新增: 八大步骤详解面板
        filter_detail_frame = ttk.Frame(notebook)
        notebook.add(filter_detail_frame, text="八大步骤详解")
        
        # 创建八大步骤详解内容
        detail_container = ttk.Frame(filter_detail_frame)
        detail_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 顶部标题
        detail_title_frame = ttk.Frame(detail_container)
        detail_title_frame.pack(fill=tk.X, pady=5)
        ttk.Label(detail_title_frame, text="尾盘八大步骤 - 专业指南", style="Title.TLabel").pack(anchor=tk.CENTER)
        ttk.Label(detail_title_frame, text="了解每个筛选步骤背后的专业逻辑", style="Subtitle.TLabel").pack(anchor=tk.CENTER)
        
        # 创建详解内容区域
        detail_content_frame = ttk.Frame(detail_container)
        detail_content_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 使用Text组件展示富文本
        self.step_detail_text = tk.Text(detail_content_frame, wrap=tk.WORD, padx=10, pady=10)
        detail_scrollbar = ttk.Scrollbar(detail_content_frame, orient=tk.VERTICAL, command=self.step_detail_text.yview)
        self.step_detail_text.configure(yscrollcommand=detail_scrollbar.set)
        
        detail_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.step_detail_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 填充八大步骤详解内容
        self._populate_step_details()
        
        # 底部状态栏
        status_bar = ttk.Frame(self.root)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM, padx=10, pady=5)
        
        self.time_label = ttk.Label(status_bar, text=f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.time_label.pack(side=tk.LEFT, padx=5)
        
        self.market_status_label = ttk.Label(status_bar, text="交易状态: 待检测")
        self.market_status_label.pack(side=tk.RIGHT, padx=5)
        
        # 启动时钟更新
        self._update_clock()
        
        # 启动动态市场状态检测
        self._check_market_status()
    
    def _change_api_source(self):
        """更改API数据源"""
        api_source = self.api_var.get()
        self.data_fetcher.set_api_source(api_source)
        
        # 如果选择AllTick，显示Token输入框
        if api_source == "alltick":
            self.token_frame.pack(fill=tk.X, padx=10, pady=5)
        else:
            self.token_frame.pack_forget()
            
        self.status_label.config(text=f"已切换到{api_source}数据源")
    
    def _set_token(self):
        """设置AllTick API Token"""
        token = self.token_entry.get().strip()
        if token:
            self.data_fetcher.set_token(token)
            messagebox.showinfo("设置成功", "API Token已设置")
        else:
            messagebox.showerror("错误", "请输入有效的Token")
    
    def _update_degradation_settings(self):
        """更新数据降级策略设置"""
        # 获取是否允许降级和降级程度
        enabled = self.degradation_enabled.get()
        level = self.degradation_level.get()
        
        # 更新到数据获取器
        if hasattr(self, 'data_fetcher') and self.data_fetcher is not None:
            self.data_fetcher.set_degradation_settings(enabled=enabled, level=level)
            
        # 更新UI提示
        status_text = f"数据降级策略: {'已启用' if enabled else '已禁用'}"
        if enabled:
            status_text += f", 级别: {level}"
        self.status_label.config(text=status_text)
    
    def _add_log(self, message, log_type="info"):
        """添加日志信息到结果文本框
        
        Parameters:
        -----------
        message: str
            日志消息
        log_type: str
            日志类型: info, warning, error, success
        """
        if not hasattr(self, 'result_text'):
            # 如果结果文本框不存在，仅打印到控制台
            print(f"[{log_type.upper()}] {message}")
            return
            
        # 确保可以写入
        self.result_text.config(state=tk.NORMAL)
        
        # 添加时间戳和类型标记
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] "
        
        # 根据类型设置颜色
        tag = None
        if log_type == "info":
            log_entry += f"INFO: {message}\n"
            tag = "info"
        elif log_type == "warning":
            log_entry += f"警告: {message}\n"
            tag = "warning"
        elif log_type == "error":
            log_entry += f"错误: {message}\n"
            tag = "error"
        elif log_type == "success":
            log_entry += f"成功: {message}\n"
            tag = "success"
        else:
            log_entry += f"{message}\n"
        
        # 添加日志
        self.result_text.insert(tk.END, log_entry)
        
        # 如果有标签，应用颜色样式
        if tag:
            line_start = self.result_text.index(f"end-{len(log_entry) + 1}c")
            line_end = self.result_text.index("end-1c")
            self.result_text.tag_add(tag, line_start, line_end)
        
        # 自动滚动到最后
        self.result_text.see(tk.END)
        
        # 恢复只读状态
        self.result_text.config(state=tk.DISABLED)
        
        # 同时输出到控制台
        print(log_entry.strip())
    
    def _update_clock(self):
        """更新时钟"""
        now = datetime.now()
        self.time_label.config(text=f"当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        self.root.after(1000, self._update_clock)
    
    def _check_market_status(self):
        """检查市场状态"""
        now = datetime.now()
        is_weekday = now.weekday() < 5  # 0-4 是周一到周五
        
        if is_weekday and 9 <= now.hour < 15:  # 交易时间9:00-15:00
            self.market_status_label.config(text="交易状态: 交易中")
            
            # 检查是否为尾盘时间（14:30-15:00）
            if now.hour == 14 and now.minute >= 30:
                self.market_status_label.config(text="交易状态: 尾盘阶段")
                
                # 如果启用了自动运行并且当前还没有运行，则开始筛选
                if self.auto_run_var.get() and not self.is_running:
                    self.run_filter()
        else:
            self.market_status_label.config(text="交易状态: 已收盘")
            
        # 每分钟检查一次
        self.root.after(60000, self._check_market_status)
    
    def _toggle_auto_run(self):
        """切换自动运行状态"""
        if self.auto_run_var.get():
            messagebox.showinfo("自动运行", "已启用自动运行，将在尾盘时间(14:30-15:00)自动执行筛选")
        else:
            messagebox.showinfo("自动运行", "已禁用自动运行")
    
    def run_filter(self):
        """运行筛选"""
        try:
            # 更新UI状态
            self._update_status("筛选中...")
            self.result_text.config(state=tk.NORMAL)
            self.result_text.delete(1.0, tk.END)
            self._add_log("开始运行尾盘八大步骤选股...", "info")
            
            # 重置筛选过程可视化
            self._reset_filter_visualization()
            
            # 创建并配置数据获取器
            if not hasattr(self, 'data_fetcher') or self.data_fetcher is None:
                self.data_fetcher = StockDataFetcher()
                # 如果选择了AllTick API，设置token
                if self.api_var.get() == "alltick" and hasattr(self, 'token_entry'):
                    self.data_fetcher.set_token(self.token_entry.get())
            
            # 设置数据降级策略
            enabled = self.degradation_enabled.get()
            level = self.degradation_level.get()
            self.data_fetcher.set_degradation_settings(enabled=enabled, level=level)
            self._add_log(f"数据降级策略: {'启用' if enabled else '禁用'}, 级别: {level}", "info")
            
            # 执行筛选
            selected_market = self.selected_market.get()
            self._add_log(f"选择的市场: {selected_market}", "info")
            
            # 获取股票列表
            stock_list = self.data_fetcher.get_stock_list(selected_market)
            if not stock_list:
                messagebox.showerror("错误", "无法获取股票列表")
                self._update_status("获取股票列表失败")
                self._add_log("获取股票列表失败", "error")
                return
            
            self._add_log(f"获取到{len(stock_list)}只{selected_market}市场股票", "info")
            self.filter_steps_data = [{'count': len(stock_list), 'status': 'waiting'}]
            
            # 执行八大步骤筛选（严格按照文档要求的顺序和条件）
            self._add_log("开始执行八大步骤筛选，步骤严格按照要求执行", "info")
            
            # 去除ST、退市风险和新股
            self._add_log("预处理：剔除ST、退市风险和新股", "info")
            self._update_filter_step(-1, 'in_progress', len(stock_list))
            filtered_stocks = self.data_fetcher.filter_by_name(stock_list)
            self._add_log(f"预处理后剩余：{len(filtered_stocks)}只股票", "info")
            self._update_filter_step(-1, 'success', len(filtered_stocks))
            
            # 筛选价格大于1元的股票
            self._add_log("预处理：筛选价格大于1元的股票", "info")
            self._update_filter_step(-2, 'in_progress', len(filtered_stocks))
            filtered_stocks = self.data_fetcher.filter_by_price(filtered_stocks)
            self._add_log(f"价格筛选后剩余：{len(filtered_stocks)}只股票", "info")
            self._update_filter_step(-2, 'success', len(filtered_stocks))
            
            initial_count = len(filtered_stocks)
            self.filter_steps_data.append({'count': initial_count, 'status': 'waiting'})
            
            # 开始执行八大步骤
            self._add_log("开始执行八大步骤：", "info")
            
            # 更新进度条初始状态
            self.filter_progress['value'] = 0
            self.progress_label.config(text=f"准备筛选 (0/8)")
            
            # 步骤1: 筛选涨幅在3%-5%的股票
            self._add_log("步骤1: 筛选涨幅在3%-5%的股票", "info")
            self._update_filter_step(0, 'in_progress', len(filtered_stocks))
            
            # 应用所有筛选条件，但会在每一步更新UI
            filtered_stocks = self.data_fetcher.apply_all_filters(filtered_stocks, 
                                                                step_callback=self._filter_step_callback)
            
            # 保存筛选结果
            self.filtered_stocks = filtered_stocks
            self.partial_match = False
            
            # 如果没有找到符合条件的股票，可能是因为某个步骤筛选失败
            if not filtered_stocks:
                self.partial_match = True
                self.max_step = getattr(self.data_fetcher, 'last_successful_step', 0)
                
                if hasattr(self.data_fetcher, 'partial_results') and self.data_fetcher.partial_results:
                    # 获取部分结果（最后一个成功步骤的结果）
                    self.filtered_stocks = self.data_fetcher.partial_results
                    self._add_log(f"未找到完全符合八大步骤的股票，显示符合前{self.max_step}步的{len(self.filtered_stocks)}只股票", "warning")
                else:
                    # 如果连部分结果都没有，显示涨幅前20只股票
                    self._add_log("未找到任何符合条件的股票，将显示当日涨幅前20只股票", "warning")
                    # 获取涨幅前20名股票
                    top_stocks = self.data_fetcher.get_top_increase_stocks(stock_list, limit=20)
                    self.filtered_stocks = top_stocks
            else:
                self._add_log(f"筛选完成，符合八大步骤的股票有 {len(filtered_stocks)} 只", "success")
                self._update_filter_step(7, 'success', len(filtered_stocks))
                self.filter_progress['value'] = 100
                self.progress_label.config(text=f"筛选完成 (8/8)")
            
            # 获取详细信息
            self._get_stock_details()
            
        except Exception as e:
            error_message = f"筛选过程中出错: {str(e)}"
            messagebox.showerror("错误", error_message)
            self._update_status("筛选失败")
            self._add_log(error_message, "error")
            traceback.print_exc()
            
    def _reset_filter_visualization(self):
        """重置筛选过程可视化"""
        # 重置进度条
        self.filter_progress['value'] = 0
        self.progress_label.config(text="准备筛选 (0/8)")
        
        # 重置每个步骤的状态
        for i, step in enumerate(self.step_descriptions):
            # 隐藏所有状态标签
            if hasattr(step, 'waiting_label') and step['waiting_label'].winfo_exists():
                step['waiting_label'].pack_forget()
                step['in_progress_label'].pack_forget()
                step['success_label'].pack_forget()
                step['fail_label'].pack_forget()
                
                # 只显示等待状态
                step['waiting_label'].pack(side=tk.RIGHT)
                
            # 重置股票数量标签
            if hasattr(step, 'stock_count_label') and step['stock_count_label'].winfo_exists():
                step['stock_count_label'].config(text="")
                
        # 重置数据
        self.filter_steps_data = []
        self.current_step = 0
    
    def _update_filter_step(self, step_index, status, stock_count, total_stocks=None):
        """更新筛选步骤状态
        
        Parameters:
        -----------
        step_index: int
            步骤索引，0-7表示八大步骤，负数表示预处理步骤
        status: str
            状态，'waiting', 'in_progress', 'success', 'fail'
        stock_count: int
            该步骤筛选后剩余的股票数量
        total_stocks: int
            筛选前的总股票数量，用于计算筛选率
        """
        if step_index < 0:
            # 预处理步骤不在可视化中显示
            return
            
        if step_index >= len(self.step_descriptions):
            return
            
        # 更新步骤数据
        if len(self.filter_steps_data) <= step_index:
            # 如果步骤数据不存在，创建新数据
            self.filter_steps_data.append({
                'count': stock_count,
                'status': status
            })
        else:
            # 如果步骤数据存在，更新数据
            self.filter_steps_data[step_index]['count'] = stock_count
            self.filter_steps_data[step_index]['status'] = status
        
        # 获取该步骤描述
        step = self.step_descriptions[step_index]
        
        # 隐藏所有状态标签
        if hasattr(step, 'waiting_label') and step['waiting_label'].winfo_exists():
            step['waiting_label'].pack_forget()
            step['in_progress_label'].pack_forget()
            step['success_label'].pack_forget()
            step['fail_label'].pack_forget()
            
            # 显示对应状态标签
            if status == 'waiting':
                step['waiting_label'].pack(side=tk.RIGHT)
            elif status == 'in_progress':
                step['in_progress_label'].pack(side=tk.RIGHT)
            elif status == 'success':
                step['success_label'].pack(side=tk.RIGHT)
            elif status == 'fail':
                step['fail_label'].pack(side=tk.RIGHT)
        
        # 更新股票数量标签
        if hasattr(step, 'stock_count_label') and step['stock_count_label'].winfo_exists():
            if total_stocks is None and step_index > 0:
                # 如果没有提供总数，使用上一步的结果作为总数
                total_stocks = self.filter_steps_data[step_index - 1]['count']
                
            if total_stocks and total_stocks > 0:
                filter_rate = (1 - stock_count / total_stocks) * 100
                stock_count_text = f"剩余: {stock_count}只 (筛除率: {filter_rate:.1f}%)"
            else:
                stock_count_text = f"剩余: {stock_count}只"
                
            step['stock_count_label'].config(text=stock_count_text)
        
        # 更新进度条
        if status == 'in_progress':
            self.current_step = step_index
            progress_value = (step_index / 8) * 100
            self.filter_progress['value'] = progress_value
            self.progress_label.config(text=f"步骤 {step_index+1}: {step['title']} ({step_index+1}/8)")
        elif status == 'success' and step_index == 7:
            # 全部完成
            self.filter_progress['value'] = 100
            self.progress_label.config(text="筛选完成 (8/8)")
    
    def _filter_step_callback(self, step_index, status, stock_count, total_count=None):
        """筛选步骤回调函数，用于在data_fetcher中调用，更新UI
        
        Parameters:
        -----------
        step_index: int
            步骤索引，0-7表示八大步骤
        status: str
            状态，'waiting', 'in_progress', 'success', 'fail'
        stock_count: int
            该步骤筛选后剩余的股票数量
        total_count: int
            筛选前的总股票数量
        """
        # 在主线程中更新UI
        self.root.after(0, lambda: self._update_filter_step(step_index, status, stock_count, total_count))
        
        # 更新日志
        if status == 'in_progress':
            step_name = self.step_descriptions[step_index]['title'] if step_index < len(self.step_descriptions) else f"步骤{step_index+1}"
            self.root.after(0, lambda: self._add_log(f"开始 {step_name} 筛选...", "info"))
        elif status == 'success':
            step_name = self.step_descriptions[step_index]['title'] if step_index < len(self.step_descriptions) else f"步骤{step_index+1}"
            self.root.after(0, lambda: self._add_log(f"{step_name} 筛选完成，剩余{stock_count}只股票", "info"))
        elif status == 'fail':
            step_name = self.step_descriptions[step_index]['title'] if step_index < len(self.step_descriptions) else f"步骤{step_index+1}"
            self.root.after(0, lambda: self._add_log(f"{step_name} 筛选失败", "error"))
            
        # 短暂延迟，使UI更新更加平滑生动
        time.sleep(0.3)
    
    def _handle_partial_results(self, steps_results, step):
        """处理部分符合条件的股票"""
        self.partial_match = True
        self.max_step = step + 1
        self.filtered_stocks = steps_results[step]
        
        # 获取详细信息
        self._get_stock_details()
    
    def _get_stock_details(self):
        """获取股票详细信息"""
        self._update_status("获取股票详细信息...")
        self.detailed_info = self.data_fetcher.get_detailed_info(self.filtered_stocks)
        
        # 在UI线程中更新界面
        self.root.after(0, self._update_ui_with_results)
    
    def _update_ui_with_results(self):
        """使用筛选结果更新UI"""
        # 清空表格
        self.stock_table.delete(*self.stock_table.get_children())
        
        # 添加筛选结果到表格
        for stock in self.detailed_info:
            # 获取数据质量信息
            data_status = stock.get('data_status', 'UNKNOWN')
            reliability = stock.get('reliability', 'UNKNOWN')
            
            # 确定数据质量标记
            if data_status == 'COMPLETE' and reliability == 'HIGH':
                quality_tag = "✓"  # 完全可靠
                row_tag = "complete"
            elif data_status == 'PARTIAL' or reliability == 'MEDIUM':
                quality_tag = "⚠️"  # 部分可靠
                row_tag = "partial"
            elif data_status == 'MISSING' or reliability == 'NONE':
                quality_tag = "✗"  # 数据缺失
                row_tag = "missing"
            else:
                quality_tag = "?"  # 未知状态
                row_tag = ""
            
            # 处理可能缺失的数据
            turnover_rate = f"{stock['turnover_rate']:.2f}%" if stock.get('turnover_rate') is not None else "数据缺失"
            market_cap = f"{stock['market_cap']:.2f}" if stock.get('market_cap') is not None else "数据缺失"
            
            values = (
                quality_tag,
                stock['code'],
                stock['name'],
                f"{stock['price']:.2f}",
                f"{stock['change_pct']:.2f}%",
                f"{stock['volume']:,}",
                turnover_rate,
                market_cap
            )
            
            self.stock_table.insert("", tk.END, values=values, tags=(row_tag,))
        
        # 更新结果统计信息
        if hasattr(self, 'partial_match') and self.partial_match:
            if hasattr(self, 'max_step') and self.max_step > 0:
                summary = f"⚠️ 警告：未找到完全符合八大步骤的股票\n\n"
                summary += f"显示的是符合前{self.max_step}步条件的股票\n"
                summary += f"共{len(self.filtered_stocks)}只股票\n\n"
                summary += f"数据质量统计:\n"
                summary += self._get_data_quality_summary()
                summary += f"\n完成时间: {datetime.now().strftime('%H:%M:%S')}"
                
                # 设置结果文本背景为黄色警告色
                self.result_text.config(state=tk.NORMAL, background="#FFFACD")  # 淡黄色
                self._update_result_text(summary)
                
                # 设置警告标签
                self._update_status(f"⚠️ 仅显示符合前{self.max_step}步的股票")
                
                # 添加日志
                self._add_log(f"未找到完全符合八大步骤的股票，显示符合前{self.max_step}步的{len(self.filtered_stocks)}只股票", "warning")
            else:
                summary = f"⚠️ 警告：未找到任何符合八大步骤的股票\n\n"
                summary += f"显示的是当日涨幅前20只股票\n"
                summary += f"共{len(self.filtered_stocks)}只股票\n\n"
                summary += f"数据质量统计:\n"
                summary += self._get_data_quality_summary()
                summary += f"\n完成时间: {datetime.now().strftime('%H:%M:%S')}"
                
                # 设置结果文本背景为红色警告色
                self.result_text.config(state=tk.NORMAL, background="#FFE4E1")  # 淡红色
                self._update_result_text(summary)
                
                # 设置警告标签
                self._update_status("⚠️ 未找到符合条件股票，显示涨幅前20")
                
                # 添加日志
                self._add_log("未找到任何符合八大步骤的股票，显示涨幅前20只股票", "warning")
        else:
            summary = f"✅ 筛选完成，成功找到八大步骤股票!\n\n"
            summary += f"初始股票数: {len(self.data_fetcher.get_stock_list(self.selected_market.get()))}\n"
            summary += f"筛选结果数: {len(self.filtered_stocks)}\n\n"
            summary += f"数据质量统计:\n"
            summary += self._get_data_quality_summary()
            summary += f"\n完成时间: {datetime.now().strftime('%H:%M:%S')}"
            
            # 设置结果文本背景为绿色成功色
            self.result_text.config(state=tk.NORMAL, background="#E0F8E0")  # 淡绿色
            self._update_result_text(summary)
            self._update_status("✅ 筛选完成")
            
            # 添加日志
            self._add_log(f"筛选完成，成功找到{len(self.filtered_stocks)}只符合八大步骤的股票", "success")
        
        # 如果有结果，自动选择第一个
        if self.detailed_info:
            self.stock_table.selection_set(self.stock_table.get_children()[0])
            self._on_stock_select(None)
        
        # 保存结果
        self._save_results()
        
        # 更新数据质量分析面板
        self._update_quality_analysis()
    
    def _get_data_quality_summary(self):
        """生成数据质量统计摘要"""
        complete_count = 0
        partial_count = 0
        missing_count = 0
        
        for stock in self.detailed_info:
            data_status = stock.get('data_status', 'UNKNOWN')
            reliability = stock.get('reliability', 'UNKNOWN')
            
            if data_status == 'COMPLETE' and reliability == 'HIGH':
                complete_count += 1
            elif data_status == 'PARTIAL' or reliability == 'MEDIUM':
                partial_count += 1
            elif data_status == 'MISSING' or reliability == 'NONE':
                missing_count += 1
        
        summary = f"完全可靠: {complete_count} 只\n"
        summary += f"部分可靠: {partial_count} 只\n"
        summary += f"数据缺失: {missing_count} 只\n"
        
        return summary
    
    def _update_quality_analysis(self):
        """更新数据质量分析面板"""
        self.quality_text.config(state=tk.NORMAL)
        self.quality_text.delete(1.0, tk.END)
        
        if hasattr(self.data_fetcher, 'stocks_data_quality'):
            quality_data = self.data_fetcher.stocks_data_quality
            
            if not quality_data:
                self.quality_text.insert(tk.END, "无数据质量信息可显示")
            else:
                self.quality_text.insert(tk.END, "数据质量分析报告\n\n", "title")
                
                # 添加筛选步骤数据质量
                filters = set([info.get('filter', '') for info in quality_data.values() if 'filter' in info])
                
                for filter_name in filters:
                    if not filter_name:
                        continue
                        
                    self.quality_text.insert(tk.END, f"== {filter_name} ==\n", "heading")
                    
                    # 统计此筛选步骤的数据质量
                    filter_stats = {
                        'STANDARD': 0,    # 标准方法
                        'ALTERNATIVE': 0, # 替代方法
                        'FALLBACK': 0,    # 降级方法
                        'SINA': 0,        # 新浪数据源
                        'TENCENT': 0,     # 腾讯数据源
                        'EASTMONEY': 0,   # 东方财富数据源
                        'MISSING': 0      # 数据缺失
                    }
                    
                    for code, info in quality_data.items():
                        if info.get('filter') != filter_name:
                            continue
                            
                        # 统计决策基础
                        decision_basis = info.get('decision_basis', '')
                        if decision_basis:
                            filter_stats[decision_basis] = filter_stats.get(decision_basis, 0) + 1
                        
                        # 统计数据源
                        source = info.get('source', '')
                        if source:
                            filter_stats[source] = filter_stats.get(source, 0) + 1
                        
                        # 统计缺失数据
                        if info.get('status') == 'MISSING':
                            filter_stats['MISSING'] = filter_stats.get('MISSING', 0) + 1
                    
                    # 输出统计结果
                    self.quality_text.insert(tk.END, f"决策基础:\n")
                    self.quality_text.insert(tk.END, f"  标准方法: {filter_stats['STANDARD']} 只\n")
                    self.quality_text.insert(tk.END, f"  替代方法: {filter_stats['ALTERNATIVE']} 只\n")
                    self.quality_text.insert(tk.END, f"  降级方法: {filter_stats['FALLBACK']} 只\n\n")
                    
                    self.quality_text.insert(tk.END, f"数据来源:\n")
                    self.quality_text.insert(tk.END, f"  新浪: {filter_stats['SINA']} 只\n")
                    self.quality_text.insert(tk.END, f"  腾讯: {filter_stats['TENCENT']} 只\n")
                    self.quality_text.insert(tk.END, f"  东方财富: {filter_stats['EASTMONEY']} 只\n")
                    self.quality_text.insert(tk.END, f"  数据缺失: {filter_stats['MISSING']} 只\n\n")
                
                # 添加总结
                self.quality_text.insert(tk.END, "== 数据质量总结 ==\n", "heading")
                if hasattr(self, 'partial_match') and self.partial_match:
                    if hasattr(self, 'max_step') and self.max_step > 0:
                        self.quality_text.insert(tk.END, f"筛选仅完成了前{self.max_step}步，未能完成完整八大步骤筛选\n", "warning")
                    else:
                        self.quality_text.insert(tk.END, f"未能完成任何筛选步骤，显示的是默认排序股票\n", "error")
                else:
                    self.quality_text.insert(tk.END, f"成功完成了全部八大步骤筛选\n", "success")
                
                # 添加数据源可靠性建议
                self.quality_text.insert(tk.END, "\n== 数据源可靠性说明 ==\n", "heading")
                self.quality_text.insert(tk.END, "新浪财经(HIGH): 最稳定、准确的主要数据源\n")
                self.quality_text.insert(tk.END, "东方财富(MEDIUM): 备用数据源，一般可靠\n")
                self.quality_text.insert(tk.END, "腾讯财经(MEDIUM): 备用数据源，一般可靠\n\n")
                
                # 添加建议
                self.quality_text.insert(tk.END, "== 投资建议 ==\n", "heading")
                complete_quality = len([s for s in self.detailed_info if s.get('data_status') == 'COMPLETE' and s.get('reliability') == 'HIGH'])
                total = len(self.detailed_info)
                quality_ratio = complete_quality / total if total > 0 else 0
                
                if quality_ratio > 0.8:
                    self.quality_text.insert(tk.END, "数据质量优良，筛选结果可信度高，适合作为投资决策依据\n", "success")
                elif quality_ratio > 0.5:
                    self.quality_text.insert(tk.END, "数据质量中等，建议进一步研究确认筛选结果后再做投资决策\n", "warning")
                else:
                    self.quality_text.insert(tk.END, "数据质量较差，筛选结果可信度低，不建议直接用于投资决策\n", "error")
        else:
            self.quality_text.insert(tk.END, "尚未执行筛选，无数据质量信息可显示")
        
        # 配置文本标签样式
        self.quality_text.tag_configure("title", font=("Arial", 12, "bold"))
        self.quality_text.tag_configure("heading", font=("Arial", 10, "bold"))
        self.quality_text.tag_configure("success", foreground="green")
        self.quality_text.tag_configure("warning", foreground="orange")
        self.quality_text.tag_configure("error", foreground="red")
        
        self.quality_text.config(state=tk.DISABLED)
    
    def _on_stock_select(self, event):
        """股票选择事件处理"""
        selected_items = self.stock_table.selection()
        if not selected_items:
            return
            
        # 获取选中项的索引
        index = self.stock_table.index(selected_items[0])
        if index < len(self.detailed_info):
            selected_stock = self.detailed_info[index]
            self.selected_stock = selected_stock
            
            # 更新K线图
            self._update_kline_chart(selected_stock['code'])
            
            # 更新详细信息
            self._update_detail_info(selected_stock)
            
            # 更新八大步骤解析
            self._update_steps_analysis(selected_stock['code'])
    
    def _update_kline_chart(self, stock_code):
        """更新K线图，显示数据来源和可靠性信息"""
        try:
            # 获取K线数据
            kline_result = self.data_fetcher.get_kline_data(stock_code, kline_type=1, num_periods=60)
            
            # 从新的数据结构中获取数据和元数据
            kline_data = kline_result.get('data', [])
            metadata = kline_result.get('metadata', {})
            
            data_source = metadata.get('source', 'UNKNOWN')
            reliability = metadata.get('reliability', 'UNKNOWN')
            data_status = metadata.get('status', 'UNKNOWN')
            
            # 如果没有K线数据，显示错误信息
            if not kline_data:
                # 清除之前的图表
                self.fig.clear()
                ax = self.fig.add_subplot(111)
                ax.text(0.5, 0.5, "无法获取K线数据", ha='center', va='center', fontsize=14)
                ax.set_axis_off()
                self.canvas.draw()
                
                # 添加日志
                self._add_log(f"无法获取{stock_code}的K线数据", "error")
                return
            
            # 清除之前的图表
            self.fig.clear()
            
            # 创建新的子图
            ax1 = self.fig.add_subplot(111)
            
            # 提取数据
            dates = [datetime.fromtimestamp(k['timestamp']) if 'timestamp' in k else i for i, k in enumerate(kline_data)]
            opens = [k['open'] for k in kline_data]
            closes = [k['close'] for k in kline_data]
            highs = [k['high'] for k in kline_data]
            lows = [k['low'] for k in kline_data]
            volumes = [k['volume'] for k in kline_data]
            
            # 计算移动平均线
            ma5 = pd.Series(closes).rolling(window=5).mean().tolist()
            ma10 = pd.Series(closes).rolling(window=10).mean().tolist()
            ma20 = pd.Series(closes).rolling(window=20).mean().tolist()
            
            # 绘制K线
            for i in range(len(dates)):
                # 绘制K线柱体
                if closes[i] >= opens[i]:
                    color = 'red'
                else:
                    color = 'green'
                    
                # 绘制K线实体
                ax1.plot([dates[i], dates[i]], [lows[i], highs[i]], color=color)
                ax1.plot([dates[i], dates[i]], [opens[i], closes[i]], color=color, linewidth=3)
            
            # 绘制移动平均线
            ax1.plot(dates, ma5, label='MA5', color='blue', linewidth=1)
            ax1.plot(dates, ma10, label='MA10', color='yellow', linewidth=1)
            ax1.plot(dates, ma20, label='MA20', color='purple', linewidth=1)
            
            # 设置数据来源和可靠性信息
            reliability_color = 'green' if reliability == 'HIGH' else 'orange' if reliability == 'MEDIUM' else 'red'
            reliability_text = 'HIGH' if reliability == 'HIGH' else 'MEDIUM' if reliability == 'MEDIUM' else 'LOW'
            source_text = f"数据来源: {data_source} (可靠性: {reliability_text})"
            
            # 添加数据源和可靠性标注
            ax1.text(0.02, 0.02, source_text, transform=ax1.transAxes, 
                    color=reliability_color, fontsize=10, 
                    bbox=dict(facecolor='white', alpha=0.8))
            
            # 设置图表标题和说明
            title = f"{stock_code} 日K线 "
            if data_status != 'COMPLETE':
                title += "⚠️ (数据可能不完整)"
            ax1.set_title(title, fontproperties="SimHei")
            
            ax1.set_xlabel("日期")
            ax1.set_ylabel("价格")
            ax1.legend()
            ax1.grid(True)
            
            # 旋转X轴标签
            plt.xticks(rotation=45)
            
            # 自动调整布局
            self.fig.tight_layout()
            
            # 刷新画布
            self.canvas.draw()
            
            # 添加日志
            self._add_log(f"更新{stock_code}的K线图，数据来源: {data_source}，可靠性: {reliability}", "info")
            
        except Exception as e:
            error_message = f"更新K线图时出错: {str(e)}"
            messagebox.showerror("错误", error_message)
            self._add_log(error_message, "error")
    
    def _update_detail_info(self, stock_info):
        """更新详细信息，添加数据来源和可靠性信息"""
        # 格式化详细信息文本
        detail_text = f"股票代码: {stock_info['code']}\n"
        detail_text += f"股票名称: {stock_info['name']}\n"
        
        # 添加数据质量摘要
        data_status = stock_info.get('data_status', 'UNKNOWN')
        reliability = stock_info.get('reliability', 'UNKNOWN')
        detail_text += f"\n数据质量摘要:\n"
        
        if data_status == 'COMPLETE' and reliability == 'HIGH':
            quality_text = "完全可靠 ✓"
            tag = "success"
        elif data_status == 'PARTIAL' or reliability == 'MEDIUM':
            quality_text = "部分可靠 ⚠️"
            tag = "warning"
        elif data_status == 'MISSING' or reliability == 'NONE':
            quality_text = "数据缺失 ✗"
            tag = "error"
        else:
            quality_text = "未知状态 ?"
            tag = "normal"
        
        detail_text += f"整体数据质量: {quality_text}\n"
        
        # 价格数据
        detail_text += f"\n价格数据:\n"
        detail_text += f"当前价格: {stock_info['price']:.2f} [可靠性: HIGH]\n"
        detail_text += f"涨跌幅: {stock_info['change_pct']:.2f}% [可靠性: HIGH]\n"
        
        # 成交量数据
        detail_text += f"\n交易数据:\n"
        detail_text += f"成交量: {stock_info['volume']:,} [可靠性: HIGH]\n"
        
        # 财务指标
        detail_text += f"\n财务指标:\n"
        
        # 换手率
        turnover_rate = stock_info.get('turnover_rate')
        turnover_source = stock_info.get('data_source', 'UNKNOWN')
        if turnover_rate is not None:
            detail_text += f"换手率: {turnover_rate:.2f}% [来源: {turnover_source}]\n"
        else:
            detail_text += f"换手率: 数据缺失 [来源: {turnover_source}]\n"
        
        # 量比
        volume_ratio = stock_info.get('volume_ratio')
        if volume_ratio is not None:
            detail_text += f"量比: {volume_ratio:.2f} [来源: {turnover_source}]\n"
        else:
            detail_text += f"量比: 数据缺失 [来源: {turnover_source}]\n"
        
        # 市值
        market_cap = stock_info.get('market_cap')
        if market_cap is not None:
            detail_text += f"市值(亿): {market_cap:.2f} [来源: {turnover_source}]\n"
        else:
            detail_text += f"市值(亿): 数据缺失 [来源: {turnover_source}]\n"
        
        # 八大步骤符合情况
        if hasattr(self.data_fetcher, 'stocks_data_quality'):
            code = stock_info['code']
            if code in self.data_fetcher.stocks_data_quality:
                detail_text += f"\n八大步骤筛选情况:\n"
                quality_info = self.data_fetcher.stocks_data_quality[code]
                
                # 显示筛选步骤信息
                filter_name = quality_info.get('filter', '')
                if filter_name:
                    detail_text += f"筛选步骤: {filter_name}\n"
                
                # 显示决策基础
                decision_basis = quality_info.get('decision_basis', '')
                if decision_basis:
                    if decision_basis == 'STANDARD':
                        detail_text += f"决策基础: 标准方法 ✓\n"
                    elif decision_basis == 'ALTERNATIVE':
                        detail_text += f"决策基础: 替代方法 ⚠️\n"
                    elif decision_basis == 'FALLBACK':
                        detail_text += f"决策基础: 降级方法 ⚠️\n"
                
                # 如果使用了替代方法，显示具体是什么方法
                alt_method = quality_info.get('alternative_method', '')
                if alt_method:
                    detail_text += f"替代分析方法: {alt_method}\n"
                
                # 显示K线数据信息
                if 'data_count' in quality_info:
                    detail_text += f"K线数据: {quality_info['data_count']}条\n"
                
                # 显示均线对齐情况
                if 'ma_alignment' in quality_info:
                    alignment = "是" if quality_info['ma_alignment'] == 'YES' else "否"
                    detail_text += f"均线对齐(MA5>MA10>MA60): {alignment}\n"
                
                # 显示60日均线上涨情况
                if 'ma60_uptrend' in quality_info:
                    uptrend = "是" if quality_info['ma60_uptrend'] == 'YES' else "否"
                    detail_text += f"60日均线上涨: {uptrend}\n"
        
        # 数据来源建议
        detail_text += f"\n数据源可靠性说明:\n"
        detail_text += f"新浪财经(HIGH): 最稳定、准确的主要数据源\n"
        detail_text += f"东方财富(MEDIUM): 备用数据源，一般可靠\n"
        detail_text += f"腾讯财经(MEDIUM): 备用数据源，一般可靠\n"
        
        # 更新文本区域
        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete(1.0, tk.END)
        self.detail_text.insert(tk.END, detail_text)
        
        # 配置文本标签样式
        self.detail_text.tag_configure("success", foreground="green")
        self.detail_text.tag_configure("warning", foreground="orange")
        self.detail_text.tag_configure("error", foreground="red")
        
        # 设置"整体数据质量"部分的颜色
        start_pos = detail_text.find("整体数据质量:")
        if start_pos >= 0:
            end_pos = detail_text.find("\n", start_pos)
            if end_pos >= 0:
                self.detail_text.tag_add(tag, f"1.0 + {start_pos}c", f"1.0 + {end_pos}c")
        
        self.detail_text.config(state=tk.DISABLED)
    
    def _update_steps_analysis(self, stock_code):
        """更新八大步骤分析"""
        # 获取单独应用每个步骤的结果
        steps_text = "八大步骤分析:\n\n"
        
        try:
            stock_list = [stock_code]
            
            # 步骤1: 涨幅分析
            step1 = self.data_fetcher.filter_by_price_increase(stock_list)
            steps_text += f"1. 涨幅过滤(3%-5%): {'通过' if step1 else '未通过'}\n"
            
            # 步骤2: 量比分析
            step2 = self.data_fetcher.filter_by_volume_ratio(stock_list)
            steps_text += f"2. 量比过滤(>1): {'通过' if step2 else '未通过'}\n"
            
            # 步骤3: 换手率分析
            step3 = self.data_fetcher.filter_by_turnover_rate(stock_list)
            steps_text += f"3. 换手率过滤(5%-10%): {'通过' if step3 else '未通过'}\n"
            
            # 步骤4: 市值分析
            step4 = self.data_fetcher.filter_by_market_cap(stock_list)
            steps_text += f"4. 市值过滤(50亿-200亿): {'通过' if step4 else '未通过'}\n"
            
            # 步骤5: 成交量分析
            step5 = self.data_fetcher.filter_by_increasing_volume(stock_list)
            steps_text += f"5. 成交量持续放大: {'通过' if step5 else '未通过'}\n"
            
            # 步骤6: 均线分析
            step6 = self.data_fetcher.filter_by_moving_averages(stock_list)
            steps_text += f"6. 短期均线搭配60日均线向上: {'通过' if step6 else '未通过'}\n"
            
            # 步骤7: 强弱分析
            step7 = self.data_fetcher.filter_by_market_strength(stock_list)
            steps_text += f"7. 强于大盘: {'通过' if step7 else '未通过'}\n"
            
            # 步骤8: 尾盘创新高分析
            step8 = self.data_fetcher.filter_by_tail_market_high(stock_list)
            steps_text += f"8. 尾盘创新高: {'通过' if step8 else '未通过'}\n"
            
            # 计算通过率
            passed_steps = sum(1 for s in [step1, step2, step3, step4, step5, step6, step7, step8] if s)
            steps_text += f"\n总体评分: {passed_steps}/8 ({passed_steps/8*100:.1f}%)\n"
            
            # 投资建议
            if passed_steps >= 7:
                steps_text += "\n投资建议: 强烈推荐关注，符合尾盘选股策略的高质量标的"
            elif passed_steps >= 5:
                steps_text += "\n投资建议: 建议关注，具有一定潜力"
            else:
                steps_text += "\n投资建议: 暂不推荐，不完全符合尾盘选股策略"
                
        except Exception as e:
            steps_text += f"\n分析过程出错: {str(e)}"
        
        # 更新文本区域
        self.steps_text.config(state=tk.NORMAL)
        self.steps_text.delete(1.0, tk.END)
        self.steps_text.insert(tk.END, steps_text)
        self.steps_text.config(state=tk.DISABLED)
    
    def _update_status(self, status):
        """更新状态标签"""
        self.root.after(0, lambda: self.status_label.config(text=status))
    
    def _update_result_text(self, text):
        """更新结果文本区域"""
        self.root.after(0, lambda: self._set_result_text(text))
    
    def _set_result_text(self, text):
        """设置结果文本"""
        self.result_text.config(state=tk.NORMAL)
        self.result_text.delete(1.0, tk.END)
        self.result_text.insert(tk.END, text)
        self.result_text.config(state=tk.DISABLED)
    
    def _handle_error(self, error_message):
        """处理错误"""
        self.status_label.config(text="筛选出错")
        messagebox.showerror("筛选错误", f"筛选过程中发生错误:\n{error_message}")
        self.is_running = False
    
    def _save_results(self):
        """保存筛选结果到本地文件"""
        if not self.detailed_info:
            return
            
        # 创建结果目录
        os.makedirs("results", exist_ok=True)
        
        # 生成文件名
        filename = f"results/尾盘选股结果_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                # 写入表头
                writer.writerow(['代码', '名称', '价格', '涨跌幅(%)', '成交量', '换手率(%)', '市值(亿)'])
                
                # 写入数据
                for stock in self.detailed_info:
                    writer.writerow([
                        stock['code'],
                        stock['name'],
                        f"{stock['price']:.2f}",
                        f"{stock['change_pct']:.2f}",
                        stock['volume'],
                        f"{stock['turnover_rate']:.2f}",
                        f"{stock['market_cap']:.2f}"
                    ])
        except Exception as e:
            messagebox.showerror("保存错误", f"保存结果时出错:\n{str(e)}")
    
    def _export_to_csv(self):
        """导出结果到CSV文件"""
        if not self.detailed_info:
            messagebox.showinfo("提示", "没有可导出的数据")
            return
            
        try:
            from tkinter import filedialog
            # 打开文件对话框
            filename = filedialog.asksaveasfilename(
                initialdir="./",
                title="导出到CSV",
                filetypes=(("CSV文件", "*.csv"), ("所有文件", "*.*")),
                defaultextension=".csv"
            )
            
            if not filename:
                return
                
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                # 写入表头
                writer.writerow(['代码', '名称', '价格', '涨跌幅(%)', '成交量', '换手率(%)', '市值(亿)'])
                
                # 写入数据
                for stock in self.detailed_info:
                    writer.writerow([
                        stock['code'],
                        stock['name'],
                        f"{stock['price']:.2f}",
                        f"{stock['change_pct']:.2f}",
                        stock['volume'],
                        f"{stock['turnover_rate']:.2f}",
                        f"{stock['market_cap']:.2f}"
                    ])
                
            messagebox.showinfo("成功", f"数据已成功导出到\n{filename}")
        except Exception as e:
            messagebox.showerror("导出错误", f"导出过程中发生错误:\n{str(e)}")

    def _create_filter_steps_cards(self):
        """创建八大步骤详解卡片"""
        for i, step in enumerate(self.step_descriptions):
            # 创建卡片框架
            card_frame = ttk.Frame(self.steps_detail_frame)
            card_frame.pack(fill=tk.X, padx=10, pady=5, ipady=5)
            
            # 卡片内容
            # 标题行
            title_frame = ttk.Frame(card_frame)
            title_frame.pack(fill=tk.X, padx=5, pady=2)
            
            step_label = ttk.Label(title_frame, text=f"步骤 {i+1}: {step['icon']} {step['title']}")
            step_label.pack(side=tk.LEFT)
            
            condition_label = ttk.Label(title_frame, text=f"条件: {step['condition']}")
            condition_label.pack(side=tk.RIGHT)
            
            # 分隔线
            separator = ttk.Separator(card_frame, orient=tk.HORIZONTAL)
            separator.pack(fill=tk.X, padx=5, pady=5)
            
            # 解释区域
            explain_frame = ttk.Frame(card_frame)
            explain_frame.pack(fill=tk.X, padx=5)
            
            # 创建标签页切换专业/通俗解释
            explanation_tabs = ttk.Notebook(explain_frame)
            explanation_tabs.pack(fill=tk.X, pady=5)
            
            # 专业解释面板
            pro_frame = ttk.Frame(explanation_tabs)
            explanation_tabs.add(pro_frame, text="专业解释")
            ttk.Label(pro_frame, text=step['pro_explanation'], wraplength=400).pack(padx=10, pady=10)
            
            # 通俗解释面板
            simple_frame = ttk.Frame(explanation_tabs)
            explanation_tabs.add(simple_frame, text="通俗解释")
            ttk.Label(simple_frame, text=step['simple_explanation'], wraplength=400).pack(padx=10, pady=10)
            
            # 创建进度指示器
            progress_frame = ttk.Frame(card_frame)
            progress_frame.pack(fill=tk.X, padx=5, pady=5)
            
            # 等待/进行中/完成/失败 状态指示
            status_frame = ttk.Frame(progress_frame)
            status_frame.pack(side=tk.RIGHT)
            
            # 保存状态标签的引用
            step['waiting_label'] = ttk.Label(status_frame, text="等待中")
            step['in_progress_label'] = ttk.Label(status_frame, text="筛选中...", foreground=PRIMARY_COLOR)
            step['success_label'] = ttk.Label(status_frame, text="通过 ✓", style="Success.TLabel")
            step['fail_label'] = ttk.Label(status_frame, text="未通过 ✗", style="Error.TLabel")
            
            # 默认显示等待中状态
            step['waiting_label'].pack(side=tk.RIGHT)
            
            # 股票数量变化指示
            self.step_descriptions[i]['stock_count_label'] = ttk.Label(progress_frame, text="")
            self.step_descriptions[i]['stock_count_label'].pack(side=tk.LEFT)
    
    def _populate_step_details(self):
        """填充八大步骤详解内容"""
        self.step_detail_text.config(state=tk.NORMAL)
        self.step_detail_text.delete(1.0, tk.END)
        
        # 设置Text标签
        self.step_detail_text.tag_configure("title", font=("Arial", 14, "bold"), foreground=PRIMARY_COLOR)
        self.step_detail_text.tag_configure("heading", font=("Arial", 12, "bold"), foreground=TEXT_COLOR)
        self.step_detail_text.tag_configure("subheading", font=("Arial", 10, "bold"), foreground=TEXT_COLOR)
        self.step_detail_text.tag_configure("normal", font=("Arial", 10), foreground=TEXT_COLOR)
        self.step_detail_text.tag_configure("emphasis", font=("Arial", 10, "italic"), foreground=PRIMARY_COLOR)
        self.step_detail_text.tag_configure("success", foreground=SUCCESS_COLOR)
        self.step_detail_text.tag_configure("warning", foreground=WARNING_COLOR)
        self.step_detail_text.tag_configure("error", foreground=ERROR_COLOR)
        
        # 添加标题
        self.step_detail_text.insert(tk.END, "尾盘八大步骤选股策略详解\n\n", "title")
        self.step_detail_text.insert(tk.END, "本指南详细解释了尾盘八大步骤选股策略的每个步骤，帮助您理解筛选逻辑和投资思路。\n\n", "normal")
        
        # 介绍
        self.step_detail_text.insert(tk.END, "策略介绍\n", "heading")
        self.step_detail_text.insert(tk.END, "尾盘八大步骤选股策略是一种系统化的选股方法，专注于发现处于强势突破的中等市值股票。该策略在收盘前的尾盘时段（14:30-15:00）执行，筛选符合特定技术和基本面条件的标的，以寻找次日可能有良好表现的投资机会。\n\n", "normal")
        
        # 为什么选择尾盘
        self.step_detail_text.insert(tk.END, "为什么选择尾盘时段?\n", "subheading")
        self.step_detail_text.insert(tk.END, "尾盘时段通常是机构投资者建仓或调仓的重要时间窗口，此时的成交更能反映市场真实意图。尾盘走强的股票往往显示出较强的资金支持，可能预示着次日的延续性行情。\n\n", "normal")
        
        # 详解每个步骤
        self.step_detail_text.insert(tk.END, "八大步骤详解\n", "heading")
        
        for i, step in enumerate(self.step_descriptions):
            self.step_detail_text.insert(tk.END, f"\n{i+1}. {step['title']} ({step['condition']})\n", "subheading")
            
            # 专业解释
            self.step_detail_text.insert(tk.END, "专业解释: ", "emphasis")
            self.step_detail_text.insert(tk.END, f"{step['pro_explanation']}\n", "normal")
            
            # 通俗解释
            self.step_detail_text.insert(tk.END, "通俗解释: ", "emphasis")
            self.step_detail_text.insert(tk.END, f"{step['simple_explanation']}\n", "normal")
            
            # 投资逻辑
            investment_logic = self._get_investment_logic(i)
            self.step_detail_text.insert(tk.END, "投资逻辑: ", "emphasis")
            self.step_detail_text.insert(tk.END, f"{investment_logic}\n", "normal")
            
            # 常见误区
            pitfall = self._get_common_pitfall(i)
            self.step_detail_text.insert(tk.END, "常见误区: ", "emphasis")
            self.step_detail_text.insert(tk.END, f"{pitfall}\n", "normal")
        
        # 组合使用的威力
        self.step_detail_text.insert(tk.END, "\n八大步骤的组合威力\n", "heading")
        self.step_detail_text.insert(tk.END, "单个步骤的筛选条件可能看起来并不特别，但八大步骤的组合使用形成了一个强大的多重过滤系统。这种系统化方法能有效排除大多数不合格的标的，留下那些真正具有短期爆发潜力的优质股票。\n\n", "normal")
        self.step_detail_text.insert(tk.END, "需要注意的是，没有任何选股策略能保证100%的成功率。尾盘八大步骤选股策略提供的是一种系统化的方法来提高成功概率，但投资者仍需结合市场环境、行业趋势和自身风险承受能力做出最终决策。\n", "normal")
        
        self.step_detail_text.config(state=tk.DISABLED)
    
    def _get_investment_logic(self, step_index):
        """获取投资逻辑详解"""
        investment_logics = [
            "涨幅3%-5%的股票处于上涨初期，具有足够的动能但又不至于过热，避免追高风险。",
            "量比大于1表明当日交易活跃度高于常态，可能是机构资金关注或布局的信号。",
            "5%-10%的换手率意味着适度的交易活跃度，既有足够的流动性，又不会因为过度交易导致价格剧烈波动。",
            "50亿-200亿市值的公司规模适中，既有一定抗风险能力，又有上涨空间，避开了大盘股上涨困难和小盘股风险大的问题。",
            "成交量持续放大是买盘积极性增强的表现，表明资金持续流入，支撑股价进一步上涨。",
            "短期均线搭配60日线向上的形态是典型的技术面强势信号，表明短中期趋势一致看好。",
            "强于大盘的个股显示出独立行情的特性，即使在大盘走弱时也可能保持强势，抗跌性更强。",
            "尾盘创新高说明买盘力量直到收盘依然强劲，没有获利了结的抛压，上涨趋势有望在次日延续。"
        ]
        return investment_logics[step_index]
    
    def _get_common_pitfall(self, step_index):
        """获取常见误区详解"""
        pitfalls = [
            "不要仅看涨幅百分比而忽视股价实际变动幅度，低价股即使小幅变动也可能产生较高百分比。",
            "量比指标可能受到历史异常交易日的影响，应结合其他成交量指标综合判断。",
            "换手率与流通股本相关，不同行业和不同市值股票的正常换手率水平可能有较大差异。",
            "市值筛选不应过于机械，某些特殊行业的龙头可能市值较大但仍有良好表现。",
            "成交量放大需要是逐步提升的过程，单日爆量后迅速萎缩的情况反而可能是出货信号。",
            "均线形态需要结合时间周期看，单纯的短期均线多头排列可能是昙花一现，需要60日线提供中期支撑。",
            "与大盘比较时要注意所属板块特性，某些板块整体强于大盘可能更多是板块效应而非个股优势。",
            "尾盘拉高创新高可能是刻意做盘行为，需要警惕尾盘突然放量拉高后无法持续的情况。"
        ]
        return pitfalls[step_index]

if __name__ == "__main__":
    root = tk.Tk()
    app = TailMarketStockApp(root)
    root.mainloop() 