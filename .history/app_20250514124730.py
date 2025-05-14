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
import webbrowser  # 添加用于打开外部链接

# 导入数据获取器
from data_fetcher import StockDataFetcher

# 新增自定义颜色主题和样式
THEME_COLOR = "#f0f0f0"  # 背景色
PRIMARY_COLOR = "#3498db"  # 主色调
SUCCESS_COLOR = "#2ecc71"  # 成功色
WARNING_COLOR = "#f39c12"  # 警告色
ERROR_COLOR = "#e74c3c"  # 错误色
TEXT_COLOR = "#2c3e50"  # 文本色

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
        
        # 应用全局样式
        self._apply_styles()
        
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
        
        # 筛选过程线程
        self.filter_thread = None
        
        # 进度动画变量
        self.progress_animation_id = None
        self.animation_dots = 0
        
        # 添加一个字典来跟踪已打开的股票分析窗口
        self.open_stock_windows = {}
        
        # 筛选过程可视化数据
        self.filter_steps_data = []
        self.current_step = 0
        
        # 初始化界面
        self._init_ui()
        
    def _apply_styles(self):
        """应用全局样式设置"""
        # 创建自定义样式
        style = ttk.Style()
        style.configure("TFrame", background=THEME_COLOR)
        style.configure("TLabel", background=THEME_COLOR, foreground=TEXT_COLOR)
        style.configure("TButton", 
                       background=PRIMARY_COLOR, 
                       foreground="white",
                       font=("Arial", 10))
        style.map("TButton", 
                 background=[("active", "#2980b9"), ("disabled", "#95a5a6")],
                 foreground=[("active", "white"), ("disabled", "#7f8c8d")])
                 
        # 添加醒目的Primary按钮样式
        style.configure("Primary.TButton", 
                       background="#e74c3c",  # 红色调
                       foreground="white", 
                       font=("Arial", 12, "bold"))
        style.map("Primary.TButton",
                 background=[("active", "#c0392b"), ("disabled", "#95a5a6")],
                 foreground=[("active", "white"), ("disabled", "#7f8c8d")])
        
        # 配置进度条样式
        style.configure("Filter.Horizontal.TProgressbar", 
                       background=PRIMARY_COLOR,
                       troughcolor=THEME_COLOR,
                       borderwidth=0)
        
        # 配置选项卡样式
        style.configure("TNotebook", background=THEME_COLOR, borderwidth=0)
        style.configure("TNotebook.Tab", background="#d5dbdb", foreground=TEXT_COLOR, padding=[10, 4])
        style.map("TNotebook.Tab",
                 background=[("selected", PRIMARY_COLOR)],
                 foreground=[("selected", "white")])
        
        # 表格样式
        style.configure("Treeview", 
                       background="white", 
                       foreground=TEXT_COLOR, 
                       rowheight=25,
                       fieldbackground="white")
        style.configure("Treeview.Heading", 
                       background="#d5dbdb", 
                       foreground=TEXT_COLOR,
                       font=("Arial", 9, "bold"))
        style.map("Treeview",
                 background=[("selected", PRIMARY_COLOR)],
                 foreground=[("selected", "white")])
        
        # 自定义标签样式
        style.configure("Title.TLabel", font=("Arial", 12, "bold"), foreground=PRIMARY_COLOR)
        style.configure("Subtitle.TLabel", font=("Arial", 10, "bold"))
        style.configure("Success.TLabel", foreground=SUCCESS_COLOR)
        style.configure("Warning.TLabel", foreground=WARNING_COLOR)
        style.configure("Error.TLabel", foreground=ERROR_COLOR)
        
        # 设置标准Tkinter按钮的默认样式
        self.root.option_add('*Button.background', '#f0f0f0')
        self.root.option_add('*Button.foreground', TEXT_COLOR)
        self.root.option_add('*Button.highlightBackground', '#d9d9d9')
        self.root.option_add('*Button.activeBackground', '#e6e6e6')
        self.root.option_add('*Button.activeForeground', TEXT_COLOR)
        self.root.option_add('*Button.relief', 'raised')
        self.root.option_add('*Button.borderWidth', 1)
    
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
        
        # 替换ttk.Button为tk.Button以确保文字可见
        start_button = tk.Button(
            filter_frame, 
            text="开始筛选", 
            command=self.run_filter,
            bg="#e74c3c",  # 红色背景
            fg="black",    # 修改为黑色文字  
            font=("Arial", 14, "bold"),  # 增大字体
            relief="raised",
            bd=3,  # 增加边框厚度
            padx=15,
            pady=8,
            highlightthickness=0,  # 移除高亮边框
            activebackground="#c0392b",  # 激活时的背景
            activeforeground="black"  # 激活时文字颜色也改为黑色
        )
        start_button.pack(fill=tk.X, padx=10, pady=10, ipady=10)  # 增加垂直内边距
        
        # 添加视觉分隔
        ttk.Separator(filter_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=5, pady=10)
        
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
        
        # 详细信息标签页 - 使用标准tkinter的Frame和按钮组合实现可见的标签页
        notebook_frame = tk.Frame(data_frame, bg=THEME_COLOR)
        notebook_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 创建标签按钮框架
        tab_buttons_frame = tk.Frame(notebook_frame, bg=THEME_COLOR)
        tab_buttons_frame.pack(fill=tk.X, side=tk.TOP)

        # 创建内容框架
        tab_content_frame = tk.Frame(notebook_frame, bg=THEME_COLOR)
        tab_content_frame.pack(fill=tk.BOTH, expand=True, side=tk.BOTTOM)

        # 创建各个内容页面
        self.kline_frame = tk.Frame(tab_content_frame, bg=THEME_COLOR)
        detail_frame = tk.Frame(tab_content_frame, bg=THEME_COLOR)
        steps_frame = tk.Frame(tab_content_frame, bg=THEME_COLOR)
        quality_frame = tk.Frame(tab_content_frame, bg=THEME_COLOR)
        filter_vis_frame = tk.Frame(tab_content_frame, bg=THEME_COLOR)
        filter_detail_frame = tk.Frame(tab_content_frame, bg=THEME_COLOR)

        # 所有标签页
        tab_frames = [
            {"frame": self.kline_frame, "text": "K线图"},
            {"frame": detail_frame, "text": "详细数据"},
            {"frame": steps_frame, "text": "八大步骤解析"},
            {"frame": quality_frame, "text": "数据质量分析"},
            {"frame": filter_vis_frame, "text": "筛选过程可视化"},
            {"frame": filter_detail_frame, "text": "八大步骤详解"}
        ]

        # 跟踪当前显示的标签页
        self.current_tab = tk.StringVar(value="K线图")

        # 创建显示/隐藏标签页内容的函数
        def show_tab(tab_name):
            self.current_tab.set(tab_name)
            # 隐藏所有标签页
            for tab in tab_frames:
                tab["frame"].pack_forget()
            
            # 显示选中的标签页
            for tab in tab_frames:
                if tab["text"] == tab_name:
                    tab["frame"].pack(fill=tk.BOTH, expand=True)
                    
                    # 更新按钮样式，保持文字为黑色
                    for btn in tab_buttons:
                        if btn["text"] == tab_name:
                            btn.config(bg=PRIMARY_COLOR, fg="black")
                        else:
                            btn.config(bg="#d5dbdb", fg="black")

        # 创建标签按钮
        tab_buttons = []
        for tab in tab_frames:
            tab_btn = tk.Button(
                tab_buttons_frame, 
                text=tab["text"],
                bg="#d5dbdb" if tab["text"] != "K线图" else PRIMARY_COLOR,
                fg="black",  # 将所有标签页按钮文字颜色设为黑色
                relief="raised",
                borderwidth=1,
                command=lambda t=tab["text"]: show_tab(t),
                padx=10,
                pady=4
            )
            tab_btn.pack(side=tk.LEFT, padx=2, pady=5)
            tab_buttons.append(tab_btn)

        # 默认显示第一个标签页
        show_tab("K线图")

        # 初始化K线图区域
        self.fig = plt.Figure(figsize=(12, 6), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.kline_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # 继续添加其他内容到各个标签页
        # 详细数据标签页
        self.detail_text = tk.Text(detail_frame, wrap=tk.WORD)
        self.detail_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.detail_text.config(state=tk.DISABLED)

        # 八大步骤解析标签页
        self.steps_text = tk.Text(steps_frame, wrap=tk.WORD)
        self.steps_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.steps_text.config(state=tk.DISABLED)

        # 数据质量分析标签页
        self.quality_text = tk.Text(quality_frame, wrap=tk.WORD)
        self.quality_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.quality_text.config(state=tk.DISABLED)

        # 筛选过程可视化标签页内容
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

        # 八大步骤详解标签页内容
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
        # 如果已经在运行筛选，则不允许再次运行
        if self.is_running:
            messagebox.showinfo("提示", "筛选正在进行中，请稍候...")
            return
            
        # 确认执行筛选
        self.is_running = True
        
        # 更新UI状态
        self._update_status("筛选准备中...")
        self.result_text.config(state=tk.NORMAL)
        self.result_text.delete(1.0, tk.END)
        self._add_log("开始运行尾盘八大步骤选股...", "info")
        
        # 禁用开始筛选按钮
        for widget in self.root.winfo_children():
            if isinstance(widget, tk.Button) and widget["text"] == "开始筛选":
                widget.config(state=tk.DISABLED)
        
        # 显示友好的用户提示
        self._show_user_friendly_message()
        
        # 开始进度动画
        self._start_progress_animation()
        
        # 重置筛选过程可视化
        self._reset_filter_visualization()
        
        # 创建并启动筛选线程
        self.filter_thread = threading.Thread(target=self._execute_filter_process)
        self.filter_thread.daemon = True
        self.filter_thread.start()
    
    def _show_user_friendly_message(self):
        """显示用户友好的筛选提示信息"""
        # 设置一个友好的提示消息
        tips = [
            "👨‍💻 正在启动智能筛选引擎，稍等片刻...",
            "🔍 系统将对所有股票进行八大步骤的逐一筛选",
            "📊 筛选过程中您可以查看'筛选过程可视化'标签页实时了解进度",
            "⏱️ 根据市场股票数量不同，整个过程可能需要1-3分钟",
            "💡 在等待过程中，您可以了解一下'八大步骤详解'以熟悉选股策略",
            "✨ 筛选完成后，所有符合条件的股票将自动显示在列表中"
        ]
        
        # 在结果区域显示友好提示
        self.result_text.config(state=tk.NORMAL)
        self.result_text.delete(1.0, tk.END)
        
        self.result_text.insert(tk.END, "筛选提示：\n\n", "heading")
        for tip in tips:
            self.result_text.insert(tk.END, f"{tip}\n\n", "tip")
        
        # 配置文本标签样式
        self.result_text.tag_configure("heading", font=("Arial", 11, "bold"))
        self.result_text.tag_configure("tip", font=("Arial", 10))
        
        self.result_text.config(state=tk.DISABLED)
    
    def _start_progress_animation(self):
        """开始进度动画"""
        def update_animation():
            if not self.is_running:
                return
                
            self.animation_dots = (self.animation_dots % 3) + 1
            dots = "." * self.animation_dots
            status_text = f"筛选中{dots}（请稍候）"
            self._update_status(status_text)
            
            # 每500毫秒更新一次动画
            self.progress_animation_id = self.root.after(500, update_animation)
        
        # 启动动画
        update_animation()
    
    def _stop_progress_animation(self):
        """停止进度动画"""
        if self.progress_animation_id:
            self.root.after_cancel(self.progress_animation_id)
            self.progress_animation_id = None
        
        # 恢复按钮状态
        for widget in self.root.winfo_children():
            if isinstance(widget, tk.Button) and widget["text"] == "开始筛选":
                widget.config(state=tk.NORMAL)
    
    def _execute_filter_process(self):
        """在独立线程中执行筛选过程"""
        try:
            # 创建并配置数据获取器
            if not hasattr(self, 'data_fetcher') or self.data_fetcher is None:
                self.data_fetcher = StockDataFetcher()
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