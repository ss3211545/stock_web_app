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
        self.step_descriptions = [
            {
                "title": "涨幅筛选",
                "condition": "3%-5%",
                "pro_explanation": "筛选日内涨幅在3%到5%之间的股票，避免涨幅过大风险和过小无动力",
                "simple_explanation": "股票今天涨了，但不是涨太多也不是涨太少，处于'金发姑娘区间'",
                "icon": "📈"
            },
            {
                "title": "量比筛选",
                "condition": "> 1.0",
                "pro_explanation": "量比大于1.0表示当日成交量高于最近5日平均成交量，说明交投活跃",
                "simple_explanation": "今天的交易比平时更活跃，有更多人在买卖这只股票",
                "icon": "📊"
            },
            {
                "title": "换手率筛选",
                "condition": "5%-10%",
                "pro_explanation": "换手率表示当日成交股数占流通股本的百分比，反映市场活跃度",
                "simple_explanation": "今天有适当比例的股票易主，既不是少得没人要，也不是多到疯狂炒作",
                "icon": "🔄"
            },
            {
                "title": "市值筛选",
                "condition": "50亿-200亿",
                "pro_explanation": "中等市值具有足够流动性又不会资金推动困难",
                "simple_explanation": "公司规模适中，既不是小到不稳定，也不是大到难以上涨",
                "icon": "💰"
            },
            {
                "title": "成交量筛选",
                "condition": "持续放大",
                "pro_explanation": "连续几日成交量呈现放大趋势，表明买入意愿增强",
                "simple_explanation": "最近几天越来越多的人在交易这只股票，关注度在提升",
                "icon": "📶"
            },
            {
                "title": "均线形态筛选",
                "condition": "短期均线搭配60日线向上",
                "pro_explanation": "MA5>MA10>MA20>MA60且MA60向上，是典型多头排列形态",
                "simple_explanation": "股价的各种平均线呈现向上的阶梯状，表明上涨趋势健康",
                "icon": "📈"
            },
            {
                "title": "大盘强度筛选",
                "condition": "强于大盘",
                "pro_explanation": "个股涨幅持续强于上证指数，表现出相对强势",
                "simple_explanation": "这只股票表现比整体市场更好，有独立上涨能力",
                "icon": "💪"
            },
            {
                "title": "尾盘创新高筛选",
                "condition": "尾盘接近日内高点",
                "pro_explanation": "尾盘价格接近当日最高价(≥95%)，表明上涨势头强劲",
                "simple_explanation": "收盘前股价仍然保持在当天的高位，说明看好的人更多",
                "icon": "🏆"
            }
        ]
        
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
                # 如果选择了AllTick API，设置token
                if self.api_var.get() == "alltick" and hasattr(self, 'token_entry'):
                    self.data_fetcher.set_token(self.token_entry.get())
            
            # 设置数据降级策略
            enabled = self.degradation_enabled.get()
            level = self.degradation_level.get()
            self.data_fetcher.set_degradation_settings(enabled=enabled, level=level)
            self.root.after(0, lambda: self._add_log(f"数据降级策略: {'启用' if enabled else '禁用'}, 级别: {level}", "info"))
            
            # 执行筛选
            selected_market = self.selected_market.get()
            self.root.after(0, lambda: self._add_log(f"选择的市场: {selected_market}", "info"))
            
            # 获取股票列表
            stock_list = self.data_fetcher.get_stock_list(selected_market)
            if not stock_list:
                self.root.after(0, lambda: messagebox.showerror("错误", "无法获取股票列表"))
                self.root.after(0, lambda: self._update_status("获取股票列表失败"))
                self.root.after(0, lambda: self._add_log("获取股票列表失败", "error"))
                self.is_running = False
                self.root.after(0, self._stop_progress_animation)
                return
            
            self.root.after(0, lambda: self._add_log(f"获取到{len(stock_list)}只{selected_market}市场股票", "info"))
            self.filter_steps_data = [{'count': len(stock_list), 'status': 'waiting'}]
            
            # 执行八大步骤筛选（严格按照文档要求的顺序和条件）
            self.root.after(0, lambda: self._add_log("开始执行八大步骤筛选，步骤严格按照要求执行", "info"))
            
            # 去除ST、退市风险和新股
            self.root.after(0, lambda: self._add_log("预处理：剔除ST、退市风险和新股", "info"))
            self.root.after(0, lambda: self._update_filter_step(-1, 'in_progress', len(stock_list)))
            filtered_stocks = self.data_fetcher.filter_by_name(stock_list)
            self.root.after(0, lambda: self._add_log(f"预处理后剩余：{len(filtered_stocks)}只股票", "info"))
            self.root.after(0, lambda: self._update_filter_step(-1, 'success', len(filtered_stocks)))
            
            # 筛选价格大于1元的股票
            self.root.after(0, lambda: self._add_log("预处理：筛选价格大于1元的股票", "info"))
            self.root.after(0, lambda: self._update_filter_step(-2, 'in_progress', len(filtered_stocks)))
            filtered_stocks = self.data_fetcher.filter_by_price(filtered_stocks)
            self.root.after(0, lambda: self._add_log(f"价格筛选后剩余：{len(filtered_stocks)}只股票", "info"))
            self.root.after(0, lambda: self._update_filter_step(-2, 'success', len(filtered_stocks)))
            
            initial_count = len(filtered_stocks)
            self.filter_steps_data.append({'count': initial_count, 'status': 'waiting'})
            
            # 开始执行八大步骤
            self.root.after(0, lambda: self._add_log("开始执行八大步骤：", "info"))
            
            # 更新进度条初始状态
            self.root.after(0, lambda: self.filter_progress.configure(value=0))
            self.root.after(0, lambda: self.progress_label.configure(text=f"准备筛选 (0/8)"))
            
            # 步骤1: 筛选涨幅在3%-5%的股票
            self.root.after(0, lambda: self._add_log("步骤1: 筛选涨幅在3%-5%的股票", "info"))
            self.root.after(0, lambda: self._update_filter_step(0, 'in_progress', len(filtered_stocks)))
            
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
                    self.root.after(0, lambda: self._add_log(f"未找到完全符合八大步骤的股票，显示符合前{self.max_step}步的{len(self.filtered_stocks)}只股票", "warning"))
                else:
                    # 如果连部分结果都没有，显示涨幅前20只股票
                    self.root.after(0, lambda: self._add_log("未找到任何符合条件的股票，将显示当日涨幅前20只股票", "warning"))
                    # 获取涨幅前20名股票
                    top_stocks = self.data_fetcher.get_top_increase_stocks(stock_list, limit=20)
                    self.filtered_stocks = top_stocks
            else:
                self.root.after(0, lambda: self._add_log(f"筛选完成，符合八大步骤的股票有 {len(filtered_stocks)} 只", "success"))
                self.root.after(0, lambda: self._update_filter_step(7, 'success', len(filtered_stocks)))
                self.root.after(0, lambda: self.filter_progress.configure(value=100))
                self.root.after(0, lambda: self.progress_label.configure(text=f"筛选完成 (8/8)"))
            
            # 获取详细信息
            self._get_stock_details()
            
        except Exception as e:
            error_message = f"筛选过程中出错: {str(e)}"
            self.root.after(0, lambda: messagebox.showerror("错误", error_message))
            self.root.after(0, lambda: self._update_status("筛选失败"))
            self.root.after(0, lambda: self._add_log(error_message, "error"))
            traceback.print_exc()
        finally:
            # 筛选过程结束，更新状态
            self.is_running = False
            self.root.after(0, self._stop_progress_animation)
    
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
            
            # 添加更详细的失败原因
            if step_index == 0:
                fail_reason = "股票涨幅不在3%-5%范围内"
                standard = "涨幅应在3%-5%之间"
            elif step_index == 1:
                fail_reason = "量比小于1.0"
                standard = "量比应大于1.0"
            elif step_index == 2:
                fail_reason = "换手率不在5%-10%范围内"
                standard = "换手率应在5%-10%之间"
            elif step_index == 3:
                fail_reason = "市值不在50亿-200亿范围内"
                standard = "市值应在50亿-200亿之间"
            elif step_index == 4:
                fail_reason = "成交量未持续放大"
                standard = "连续几日成交量应呈现放大趋势"
            elif step_index == 5:
                fail_reason = "均线不满足多头排列或60日均线未向上"
                standard = "MA5>MA10>MA20>MA60且MA60向上"
            elif step_index == 6:
                fail_reason = "个股未强于大盘"
                standard = "个股涨幅应持续强于上证指数"
            elif step_index == 7:
                fail_reason = "尾盘未接近日内高点"
                standard = "尾盘价格应接近当日最高价(≥95%)"
            else:
                fail_reason = "未满足筛选条件"
                standard = "未知标准"
                
            self.root.after(0, lambda: self._add_log(f"{step_name} 筛选失败: {fail_reason}，标准: {standard}", "error"))
            
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
        self.root.after(0, lambda: self._update_status("获取股票详细信息..."))
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
            steps_results = []
            step_data = {}
            
            # 步骤1: 涨幅分析
            step1 = self.data_fetcher.filter_by_price_increase(stock_list)
            steps_text += f"1. 涨幅过滤(3%-5%): {'通过' if step1 else '未通过'}\n"
            step_data[0] = {'passed': bool(step1), 'name': '涨幅筛选'}
            steps_results.append(step1)
            
            # 步骤2: 量比分析
            step2 = self.data_fetcher.filter_by_volume_ratio(stock_list)
            steps_text += f"2. 量比过滤(>1): {'通过' if step2 else '未通过'}\n"
            step_data[1] = {'passed': bool(step2), 'name': '量比筛选'}
            steps_results.append(step2)
            
            # 步骤3: 换手率分析
            step3 = self.data_fetcher.filter_by_turnover_rate(stock_list)
            steps_text += f"3. 换手率过滤(5%-10%): {'通过' if step3 else '未通过'}\n"
            step_data[2] = {'passed': bool(step3), 'name': '换手率筛选'}
            steps_results.append(step3)
            
            # 步骤4: 市值分析
            step4 = self.data_fetcher.filter_by_market_cap(stock_list)
            steps_text += f"4. 市值过滤(50亿-200亿): {'通过' if step4 else '未通过'}\n"
            step_data[3] = {'passed': bool(step4), 'name': '市值筛选'}
            steps_results.append(step4)
            
            # 步骤5: 成交量分析
            step5 = self.data_fetcher.filter_by_increasing_volume(stock_list)
            steps_text += f"5. 成交量持续放大: {'通过' if step5 else '未通过'}\n"
            step_data[4] = {'passed': bool(step5), 'name': '成交量筛选'}
            steps_results.append(step5)
            
            # 步骤6: 均线分析
            step6 = self.data_fetcher.filter_by_moving_averages(stock_list)
            steps_text += f"6. 短期均线搭配60日均线向上: {'通过' if step6 else '未通过'}\n"
            step_data[5] = {'passed': bool(step6), 'name': '均线形态筛选'}
            steps_results.append(step6)
            
            # 步骤7: 强弱分析
            step7 = self.data_fetcher.filter_by_market_strength(stock_list)
            steps_text += f"7. 强于大盘: {'通过' if step7 else '未通过'}\n"
            step_data[6] = {'passed': bool(step7), 'name': '大盘强度筛选'}
            steps_results.append(step7)
            
            # 步骤8: 尾盘创新高分析
            step8 = self.data_fetcher.filter_by_tail_market_high(stock_list)
            steps_text += f"8. 尾盘创新高: {'通过' if step8 else '未通过'}\n"
            step_data[7] = {'passed': bool(step8), 'name': '尾盘创新高筛选'}
            steps_results.append(step8)
            
            # 获取详细数据
            try:
                detailed_info = self.data_fetcher.get_detailed_info(stock_list)[0]
                # 添加具体数据到步骤分析中
                step_data[0]['value'] = f"{detailed_info.get('change_pct', 'N/A')}%"
                step_data[0]['required'] = "3%-5%"
                step_data[0]['details'] = f"当日涨幅为{detailed_info.get('change_pct', 'N/A')}%，{'在' if 3 <= detailed_info.get('change_pct', 0) <= 5 else '不在'}3%-5%范围内"
                
                step_data[1]['value'] = f"{detailed_info.get('volume_ratio', 'N/A')}"
                step_data[1]['required'] = "> 1.0"
                step_data[1]['details'] = f"量比为{detailed_info.get('volume_ratio', 'N/A')}，{'大于' if detailed_info.get('volume_ratio', 0) > 1 else '不大于'}1.0"
                
                step_data[2]['value'] = f"{detailed_info.get('turnover_rate', 'N/A')}%"
                step_data[2]['required'] = "5%-10%"
                step_data[2]['details'] = f"换手率为{detailed_info.get('turnover_rate', 'N/A')}%，{'在' if 5 <= detailed_info.get('turnover_rate', 0) <= 10 else '不在'}5%-10%范围内"
                
                step_data[3]['value'] = f"{detailed_info.get('market_cap', 'N/A')}亿"
                step_data[3]['required'] = "50亿-200亿"
                step_data[3]['details'] = f"市值为{detailed_info.get('market_cap', 'N/A')}亿，{'在' if 50 <= detailed_info.get('market_cap', 0) <= 200 else '不在'}50亿-200亿范围内"
            except Exception as e:
                print(f"获取详细数据异常: {e}")
            
            # 计算通过率
            passed_steps = sum(1 for s in steps_results if s)
            steps_text += f"\n总体评分: {passed_steps}/8 ({passed_steps/8*100:.1f}%)\n"
            
            # 投资建议
            if passed_steps >= 7:
                steps_text += "\n投资建议: 强烈推荐关注，符合尾盘选股策略的高质量标的"
            elif passed_steps >= 5:
                steps_text += "\n投资建议: 建议关注，具有一定潜力"
            else:
                steps_text += "\n投资建议: 暂不推荐，不完全符合尾盘选股策略"
                
            # 增强视觉展示 - 添加到原有文本分析后
            steps_text += "\n\n==== 可视化评分卡 ====\n\n"
            for i in range(8):
                data = step_data.get(i, {})
                passed = data.get('passed', False)
                name = data.get('name', f'步骤{i+1}')
                value = data.get('value', 'N/A')
                required = data.get('required', 'N/A')
                details = data.get('details', '')
                
                if passed:
                    steps_text += f"✅ {name}: {value} (要求: {required})\n"
                    if details:
                        steps_text += f"   {details}\n"
                else:
                    steps_text += f"❌ {name}: {value} (要求: {required})\n"
                    if details:
                        steps_text += f"   {details}\n"
                        
                if i < 7:  # 不在最后一步后添加分隔符
                    steps_text += "-" * 30 + "\n"
                
        except Exception as e:
            steps_text += f"\n分析过程出错: {str(e)}"
        
        # 更新文本区域
        self.steps_text.config(state=tk.NORMAL)
        self.steps_text.delete(1.0, tk.END)
        self.steps_text.insert(tk.END, steps_text)
        
        # 添加文本标签样式
        self.steps_text.tag_configure("success", foreground=SUCCESS_COLOR)
        self.steps_text.tag_configure("warning", foreground=WARNING_COLOR)
        self.steps_text.tag_configure("error", foreground=ERROR_COLOR)
        self.steps_text.tag_configure("heading", font=("Arial", 10, "bold"))
        
        # 找到所有通过/未通过文本并应用样式
        start_index = "1.0"
        while True:
            pos = self.steps_text.search("通过", start_index, tk.END)
            if not pos:
                break
            self.steps_text.tag_add("success", pos, f"{pos}+2c")
            start_index = f"{pos}+2c"
            
        start_index = "1.0"
        while True:
            pos = self.steps_text.search("未通过", start_index, tk.END)
            if not pos:
                break
            self.steps_text.tag_add("error", pos, f"{pos}+3c")
            start_index = f"{pos}+3c"
            
        # 给✅和❌应用样式
        start_index = "1.0"
        while True:
            pos = self.steps_text.search("✅", start_index, tk.END)
            if not pos:
                break
            self.steps_text.tag_add("success", pos, f"{pos}+1c")
            start_index = f"{pos}+1c"
            
        start_index = "1.0"
        while True:
            pos = self.steps_text.search("❌", start_index, tk.END)
            if not pos:
                break
            self.steps_text.tag_add("error", pos, f"{pos}+1c")
            start_index = f"{pos}+1c"
            
        # 设置标题样式
        start_index = "1.0"
        while True:
            pos = self.steps_text.search("====", start_index, tk.END)
            if not pos:
                break
            line_end = self.steps_text.search("\n", pos, tk.END)
            self.steps_text.tag_add("heading", pos, line_end)
            start_index = line_end
        
        self.steps_text.config(state=tk.DISABLED)
        
        # 创建并展示股票筛选信息卡片
        self._show_stock_filter_card(stock_code, step_data)
    
    def _show_stock_filter_card(self, stock_code, step_data):
        """展示股票筛选信息卡片
        
        Parameters:
        -----------
        stock_code: str
            股票代码
        step_data: dict
            各步骤的筛选数据
        """
        # 检查是否有详细信息
        if not hasattr(self, 'detailed_info') or not self.detailed_info:
            return
            
        # 查找当前股票的详细信息
        stock_info = None
        for stock in self.detailed_info:
            if stock.get('code') == stock_code:
                stock_info = stock
                break
                
        if not stock_info:
            return

        # 检查是否已经有此股票的窗口打开
        if stock_code in self.open_stock_windows:
            # 如果窗口还存在，则将其置顶
            if self.open_stock_windows[stock_code].winfo_exists():
                self.open_stock_windows[stock_code].lift()
                self.open_stock_windows[stock_code].focus_set()
                return
            # 如果窗口已被关闭，则从字典中移除
            else:
                del self.open_stock_windows[stock_code]
        
        # 创建一个弹出窗口
        card_window = tk.Toplevel(self.root)
        card_window.title(f"{stock_info.get('name', '')}({stock_code}) - 筛选分析")
        card_window.geometry("600x700")
        card_window.minsize(500, 600)
        
        # 记录这个窗口
        self.open_stock_windows[stock_code] = card_window
        
        # 窗口关闭时从字典中移除
        def on_window_close():
            if stock_code in self.open_stock_windows:
                del self.open_stock_windows[stock_code]
            card_window.destroy()
        
        card_window.protocol("WM_DELETE_WINDOW", on_window_close)
        
        # 设置窗口样式
        card_window.configure(background=THEME_COLOR)
        
        # 创建主容器
        main_frame = ttk.Frame(card_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 股票基本信息
        info_frame = ttk.Frame(main_frame)
        info_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(info_frame, text=f"{stock_info.get('name', '')}({stock_code})", 
                 font=("Arial", 14, "bold"), foreground=PRIMARY_COLOR).pack(anchor=tk.W)
        price_text = f"价格: {stock_info.get('price', 0):.2f}  "
        price_text += f"涨跌幅: {stock_info.get('change_pct', 0):.2f}%"
        ttk.Label(info_frame, text=price_text).pack(anchor=tk.W)
        
        market_text = f"市值: {stock_info.get('market_cap', 0):.2f}亿  "
        market_text += f"换手率: {stock_info.get('turnover_rate', 0):.2f}%  "
        market_text += f"量比: {stock_info.get('volume_ratio', 0):.2f}"
        ttk.Label(info_frame, text=market_text).pack(anchor=tk.W)
        
        # 筛选结果摘要
        ttk.Separator(main_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        
        summary_frame = ttk.Frame(main_frame)
        summary_frame.pack(fill=tk.X, pady=10)
        
        # 计算通过步骤数
        passed_steps = sum(1 for s in step_data.values() if s.get('passed', False))
        total_steps = len(step_data)
        
        progress_frame = ttk.Frame(summary_frame)
        progress_frame.pack(fill=tk.X, pady=5)
        
        progress = ttk.Progressbar(progress_frame, orient=tk.HORIZONTAL, length=100, mode='determinate')
        progress.pack(fill=tk.X, padx=5, pady=5)
        progress['value'] = (passed_steps / total_steps) * 100
        
        summary_text = f"通过 {passed_steps}/{total_steps} 步骤 ({passed_steps/total_steps*100:.1f}%)"
        ttk.Label(summary_frame, text=summary_text, font=("Arial", 10, "bold")).pack(anchor=tk.CENTER)
        
        # 展示每个步骤的详细结果
        ttk.Separator(main_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        
        steps_frame = ttk.Frame(main_frame)
        steps_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # 创建带滚动条的Canvas
        canvas = tk.Canvas(steps_frame, bg=THEME_COLOR, highlightthickness=0)
        scrollbar = ttk.Scrollbar(steps_frame, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 创建Canvas内的Frame
        steps_container = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=steps_container, anchor=tk.NW, width=canvas.winfo_width())
        
        # 配置Canvas的滚动区域
        def _configure_canvas(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(canvas.find_all()[0], width=event.width)
        
        steps_container.bind("<Configure>", _configure_canvas)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas.find_all()[0], width=e.width))
        
        # 添加每个步骤的信息卡片
        for i in range(8):
            data = step_data.get(i, {})
            passed = data.get('passed', False)
            name = data.get('name', f'步骤{i+1}')
            value = data.get('value', 'N/A')
            required = data.get('required', 'N/A')
            details = data.get('details', '')
            
            # 创建卡片容器
            card = ttk.Frame(steps_container)
            card.pack(fill=tk.X, padx=5, pady=5, ipady=5)
            
            # 卡片标题
            header_frame = ttk.Frame(card)
            header_frame.pack(fill=tk.X, padx=5, pady=2)
            
            # 步骤名称
            step_label = ttk.Label(header_frame, text=f"步骤 {i+1}: {name}")
            step_label.pack(side=tk.LEFT)
            
            # 通过/失败标签
            if passed:
                status_label = ttk.Label(header_frame, text="通过 ✓", foreground=SUCCESS_COLOR)
            else:
                status_label = ttk.Label(header_frame, text="未通过 ✗", foreground=ERROR_COLOR)
            status_label.pack(side=tk.RIGHT)
            
            # 分隔线
            ttk.Separator(card, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=5, pady=2)
            
            # 详细信息
            detail_frame = ttk.Frame(card)
            detail_frame.pack(fill=tk.X, padx=10, pady=5)
            
            # 要求vs实际
            compare_frame = ttk.Frame(detail_frame)
            compare_frame.pack(fill=tk.X, pady=3)
            
            ttk.Label(compare_frame, text="要求:").pack(side=tk.LEFT, padx=(0, 5))
            ttk.Label(compare_frame, text=required).pack(side=tk.LEFT)
            
            ttk.Label(compare_frame, text="实际:").pack(side=tk.LEFT, padx=(20, 5))
            if passed:
                ttk.Label(compare_frame, text=value, foreground=SUCCESS_COLOR).pack(side=tk.LEFT)
            else:
                ttk.Label(compare_frame, text=value, foreground=ERROR_COLOR).pack(side=tk.LEFT)
            
            # 详细解释
            if details:
                ttk.Label(detail_frame, text=details, wraplength=500).pack(anchor=tk.W, pady=3)
            
            # 每个卡片底部的分隔线
            if i < 7:  # 不在最后一个卡片后添加分隔线
                ttk.Separator(steps_container, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        
        # 投资建议
        ttk.Separator(main_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        
        advice_frame = ttk.Frame(main_frame)
        advice_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(advice_frame, text="投资建议", font=("Arial", 12, "bold")).pack(anchor=tk.W)
        
        if passed_steps >= 7:
            advice = "强烈推荐关注，符合尾盘选股策略的高质量标的"
            advice_label = ttk.Label(advice_frame, text=advice, foreground=SUCCESS_COLOR, wraplength=550)
        elif passed_steps >= 5:
            advice = "建议关注，具有一定潜力，但不完全符合筛选标准"
            advice_label = ttk.Label(advice_frame, text=advice, foreground=WARNING_COLOR, wraplength=550)
        else:
            advice = "不建议关注，不符合尾盘选股策略的大部分条件"
            advice_label = ttk.Label(advice_frame, text=advice, foreground=ERROR_COLOR, wraplength=550)
        
        advice_label.pack(anchor=tk.W, pady=5)
        
        # 底部按钮
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        # 使用标准按钮样式而不是TTK样式，确保文字可见
        close_button = tk.Button(button_frame, text="关闭", 
                               bg="#f0f0f0", fg="#2c3e50",
                               command=card_window.destroy)
        close_button.pack(side=tk.RIGHT, padx=5)
        
        # 如果是通过大部分步骤的股票，添加添加至关注列表按钮
        if passed_steps >= 5:
            watch_button = tk.Button(button_frame, text="添加至关注列表", 
                                   bg="#f0f0f0", fg="#2c3e50",
                                   command=lambda: self._add_to_watchlist(stock_code, stock_info.get('name', '')))
            watch_button.pack(side=tk.RIGHT, padx=5)
    
    def _add_to_watchlist(self, stock_code, stock_name):
        """添加股票到关注列表
        
        Parameters:
        -----------
        stock_code: str
            股票代码
        stock_name: str
            股票名称
        """
        # 在实际应用中，这里可以实现保存关注列表的功能
        # 目前仅显示一个消息框表示已添加
        messagebox.showinfo("添加成功", f"已将 {stock_name}({stock_code}) 添加至关注列表")
        
        # TODO: 实现关注列表管理功能
    
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