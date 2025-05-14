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
        
        markets = [("沪深", "SH+SZ"), ("上证", "SH"), ("深证", "SZ"), ("北证", "BJ"), ("港股", "HK"), ("美股", "US")]
        for i, (text, value) in enumerate(markets):
            ttk.Radiobutton(market_frame, text=text, value=value, variable=self.selected_market).pack(anchor=tk.W, padx=10, pady=2)
        
        # 默认选择沪深市场
        self.selected_market.set("SH+SZ")
        
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
            filter_canvas.itemconfig(filter_canvas.find_all()[0], width=event.width)
        
        self.steps_detail_frame.bind("<Configure>", _configure_canvas)
        filter_canvas.bind("<Configure>", lambda e: filter_canvas.itemconfig(filter_canvas.find_all()[0], width=e.width))
        
        # 添加每个步骤的信息卡片
        self._create_filter_steps_cards()
        
        # 创建八大步骤详解内容标签页
        detail_container = ttk.Frame(filter_detail_frame)
        detail_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 创建步骤详解文本框
        self.step_detail_text = tk.Text(detail_container, wrap=tk.WORD)
        self.step_detail_text.pack(fill=tk.BOTH, expand=True)
        self.step_detail_text.config(state=tk.DISABLED)
        
        # 填充详解内容
        self._populate_step_details()
        
        # 初始化筛选步骤数据
        self.filter_steps_data = []
        self.current_step = 0

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
        for i in range(8):
            # 获取步骤描述信息
            step_info = self.step_descriptions[i]
            
            # 创建卡片容器
            card = ttk.Frame(self.steps_detail_frame)
            card.pack(fill=tk.X, padx=5, pady=5, ipady=5)
            
            # 卡片标题
            header_frame = ttk.Frame(card)
            header_frame.pack(fill=tk.X, padx=5, pady=2)
            
            # 步骤名称
            step_label = ttk.Label(header_frame, text=f"步骤 {i+1}: {step_info['title']}")
            step_label.pack(side=tk.LEFT)
            
            # 状态标签 - 初始为等待中
            waiting_label = ttk.Label(header_frame, text="等待中")
            waiting_label.pack(side=tk.RIGHT)
            
            # 保存状态标签的引用
            step_info['waiting_label'] = waiting_label
            step_info['in_progress_label'] = ttk.Label(header_frame, text="筛选中...", foreground=PRIMARY_COLOR)
            step_info['success_label'] = ttk.Label(header_frame, text="通过 ✓", style="Success.TLabel")
            step_info['fail_label'] = ttk.Label(header_frame, text="未通过 ✗", style="Error.TLabel")
            
            # 分隔线
            ttk.Separator(card, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=5, pady=2)
            
            # 详细信息
            detail_frame = ttk.Frame(card)
            detail_frame.pack(fill=tk.X, padx=10, pady=5)
            
            # 筛选条件
            condition_frame = ttk.Frame(detail_frame)
            condition_frame.pack(fill=tk.X, pady=3)
            
            ttk.Label(condition_frame, text="筛选条件:").pack(side=tk.LEFT, padx=(0, 5))
            ttk.Label(condition_frame, text=step_info['condition']).pack(side=tk.LEFT)
            
            # 股票数量标签
            stock_count_label = ttk.Label(detail_frame, text="")
            stock_count_label.pack(anchor=tk.W, pady=3)
            step_info['stock_count_label'] = stock_count_label
            
            # 添加解释
            explanation_frame = ttk.Frame(detail_frame)
            explanation_frame.pack(fill=tk.X, pady=3)
            
            ttk.Label(explanation_frame, text="专业解释:", style="Bold.TLabel").pack(anchor=tk.W)
            ttk.Label(explanation_frame, text=step_info['pro_explanation'], 
                      wraplength=500).pack(anchor=tk.W, padx=10)
            
            ttk.Label(explanation_frame, text="通俗解释:", style="Bold.TLabel").pack(anchor=tk.W, pady=(5, 0))
            ttk.Label(explanation_frame, text=step_info['simple_explanation'], 
                      wraplength=500).pack(anchor=tk.W, padx=10)
            
            # 每个卡片底部的分隔线
            if i < 7:  # 不在最后一个卡片后添加分隔线
                ttk.Separator(self.steps_detail_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        
        # 创建八大步骤详解内容标签页
        detail_container = ttk.Frame(filter_detail_frame)
        detail_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 创建步骤详解文本框
        self.step_detail_text = tk.Text(detail_container, wrap=tk.WORD)
        self.step_detail_text.pack(fill=tk.BOTH, expand=True)
        self.step_detail_text.config(state=tk.DISABLED)
        
        # 填充详解内容
        self._populate_step_details()
        
        # 初始化筛选步骤数据
        self.filter_steps_data = []
        self.current_step = 0

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
    
    def _update_status(self, text):
        """更新状态栏文本
        
        Parameters:
        -----------
        text: str
            状态文本
        """
        self.status_label.config(text=text)
    
    def _update_result_text(self, text):
        """更新结果文本框
        
        Parameters:
        -----------
        text: str
            结果文本
        """
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
        self.animation_dots = 0
        update_animation()
        
        # 添加友好的用户提示
        self._add_log("开始运行尾盘八大步骤选股...", "info")
        self._add_log("系统正在努力为您筛选最佳股票，这可能需要1-3分钟时间...", "progress")
        self._add_log("筛选过程中您可以在'筛选过程可视化'标签页查看进度", "info")
        
        # 禁用开始筛选按钮
        for widget in self.root.winfo_children():
            if isinstance(widget, tk.Button) and widget["text"] == "开始筛选":
                widget.config(state=tk.DISABLED)
        
        # 重置筛选过程可视化
        # 重置进度条
        self.filter_progress['value'] = 0
        self.progress_label.config(text="准备筛选 (0/8)")

    def _stop_progress_animation(self):
        """停止进度动画"""
        if self.progress_animation_id:
            self.root.after_cancel(self.progress_animation_id)
            self.progress_animation_id = None
        
        # 恢复按钮状态
        for widget in self.root.winfo_children():
            if isinstance(widget, tk.Button) and widget["text"] == "开始筛选":
                widget.config(state=tk.NORMAL)
        
        # 更新状态
        self._update_status("筛选完成")
        self._add_log("筛选过程已完成", "info")

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
            日志类型: info, warning, error, success, progress
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
        elif log_type == "progress":
            log_entry += f"进度: {message}\n"
            tag = "progress"
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
        """运行筛选流程"""
        if self.is_running:
            self._add_log("筛选正在进行中，请稍候...", "warning")
            return
        
        # 设置运行状态
        self.is_running = True
        
        # 清空之前的筛选结果
        self._clear_filter_results()
        
        # 根据市场值获取要筛选的市场列表
        markets = []
        if "+" in self.selected_market.get():
            # 处理组合市场，如SH+SZ
            markets = self.selected_market.get().split("+")
        else:
            # 单个市场
            markets = [self.selected_market.get()]
        
        # 开始动画和提示
        self._start_progress_animation()
        self._add_log(f"开始从{len(markets)}个市场获取股票数据...", "info")
        self._add_log("系统正在努力为您挖掘最佳投资机会，这可能需要一点时间...", "progress")
        
        # 创建新线程执行筛选
        self.filter_thread = threading.Thread(target=self._run_filter_thread, args=(markets,))
        self.filter_thread.daemon = True
        self.filter_thread.start()

    def _run_filter_thread(self, markets):
        """线程中执行筛选逻辑
        
        Parameters:
        -----------
        markets: list
            要筛选的市场列表
        """
        try:
            # 等待100ms确保UI已更新
            time.sleep(0.1)
            
            # 为每个市场筛选股票并合并结果
            all_stocks = []
            market_sizes = {}
            
            for market in markets:
                # 获取单个市场的股票
                self.root.after(0, lambda m=market: self._add_log(f"正在获取{m}市场的股票列表...", "info"))
                stocks = self.data_fetcher.get_stock_list(market)
                market_sizes[market] = len(stocks)
                all_stocks.extend(stocks)
            
            total_stocks = len(all_stocks)
            
            # 显示获取的股票总数
            market_info = ", ".join([f"{m}: {size}只" for m, size in market_sizes.items()])
            self.root.after(0, lambda: self._add_log(f"共获取到{total_stocks}只股票 ({market_info})", "info"))
            
            if total_stocks == 0:
                self.root.after(0, lambda: self._add_log("没有获取到股票数据，请检查网络连接", "error"))
                self.root.after(0, self._stop_progress_animation)
                self.is_running = False
                return
            
            # 显示鼓励性信息
            self.root.after(0, lambda: self._add_log("正在用尾盘八大步骤为您分析每一只股票...", "progress"))
            
            # 执行八大步骤筛选
            result_stocks, detailed_info = self.data_fetcher.filter_by_eight_steps(
                all_stocks, 
                callback=self._filter_step_callback
            )
            
            # 更新筛选结果
            self.filtered_stocks = result_stocks
            self.detailed_info = detailed_info
            
            # 计算匹配情况
            if self.filtered_stocks:
                self.partial_match = False
                self._add_log(f"筛选完成！找到{len(self.filtered_stocks)}只符合八大步骤的股票！", "success")
            else:
                # 查找部分匹配的股票
                self._find_partial_matches()
            
            # 更新UI
            self.root.after(0, lambda: self._update_filter_results())
        except Exception as e:
            # 处理异常
            error_msg = str(e)
            self.root.after(0, lambda: self._add_log(f"筛选过程中出错: {error_msg}", "error"))
            traceback_str = traceback.format_exc()
            print(f"错误详情: {traceback_str}")
        finally:
            # 完成后清理
            self.root.after(0, self._stop_progress_animation)
            self.is_running = False

    def _clear_filter_results(self):
        """清空之前的筛选结果"""
        self.filtered_stocks = []
        self.detailed_info = []
        self.partial_match = False
        self.max_step = 0
        self.filter_steps_data = []
        self.current_step = 0
        self.result_text.config(state=tk.NORMAL)
        self.result_text.delete(1.0, tk.END)
        self.result_text.config(state=tk.DISABLED)
        self.status_label.config(text="就绪")
        self.filter_progress['value'] = 0
        self.progress_label.config(text="准备筛选 (0/8)")

    def _find_partial_matches(self):
        """查找部分匹配的股票"""
        if hasattr(self.data_fetcher, 'partial_results') and self.data_fetcher.partial_results:
            self.filtered_stocks = self.data_fetcher.partial_results
            self.max_step = getattr(self.data_fetcher, 'last_successful_step', 0)
            self.partial_match = True
            self.root.after(0, lambda: self._add_log(f"未找到完全符合八大步骤的股票，显示符合前{self.max_step}步的{len(self.filtered_stocks)}只股票", "warning"))
        else:
            # 如果连部分结果都没有，显示涨幅前20只股票
            self.root.after(0, lambda: self._add_log("未找到任何符合条件的股票，将显示当日涨幅前20只股票", "warning"))
            # 获取涨幅前20名股票
            markets = []
            if "+" in self.selected_market.get():
                markets = self.selected_market.get().split("+")
            else:
                markets = [self.selected_market.get()]
            
            all_stocks = []
            for market in markets:
                all_stocks.extend(self.data_fetcher.get_stock_list(market))
            
            top_stocks = self.data_fetcher.get_top_increase_stocks(all_stocks, limit=20)
            self.filtered_stocks = top_stocks
            self.partial_match = True
            self.max_step = 0

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

    def _update_filter_results(self):
        """更新筛选结果"""
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
                summary += f"共{len(self.filtered_stocks)}只股票\n"
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
                summary += f"共{len(self.filtered_stocks)}只股票\n"
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
            markets_str = self.selected_market.get()
            summary += f"筛选市场: {markets_str}\n"
            summary += f"筛选结果数: {len(self.filtered_stocks)}\n"
            summary += f"\n完成时间: {datetime.now().strftime('%H:%M:%S')}"
            
            # 设置结果文本背景为绿色成功色
            self.result_text.config(state=tk.NORMAL, background="#E0F8E0")  # 淡绿色
            self._update_result_text(summary)
            self._update_status("✅ 筛选完成")
            
            # 添加日志
            self._add_log(f"筛选完成，成功找到{len(self.filtered_stocks)}只符合八大步骤的股票", "success")
        
        # 如果有结果，自动选择第一个
        if self.detailed_info:
            if self.stock_table.get_children():
                self.stock_table.selection_set(self.stock_table.get_children()[0])
                self._on_stock_select(None)
        
        # 保存结果
        self._save_results()

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

if __name__ == "__main__":
    root = tk.Tk()
    app = TailMarketStockApp(root)
    root.mainloop() 