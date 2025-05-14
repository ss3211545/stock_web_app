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
            messagebox.showinfo("提示", "筛选正在进行中，请稍候...")
            return
            
        self.is_running = True
        self.status_label.config(text="筛选中...")
        
        # 清空之前的结果
        self.stock_table.delete(*self.stock_table.get_children())
        self.filtered_stocks = []
        self.detailed_info = []
        
        # 更新结果统计
        self._update_result_text("开始筛选...\n")
        
        # 在新线程中运行筛选，避免卡住UI
        threading.Thread(target=self._run_filter_thread, daemon=True).start()
    
    def _run_filter_thread(self):
        """在后台线程中运行筛选"""
        try:
            # 获取所选市场
            market = self.selected_market.get()
            
            # 获取股票列表
            self._update_status(f"正在获取{market}市场股票列表...")
            stocks = self.data_fetcher.get_stock_list(market=market)
            self._update_result_text(f"获取到{len(stocks)}只股票\n")
            
            # 存储各步骤筛选结果
            step_results = {}
            
            # 应用八大步骤筛选，尝试获取完全符合条件的股票
            self._update_status("应用八大步骤筛选中...")
            self.filtered_stocks = self.data_fetcher.apply_all_filters(stocks)
            
            # 如果没有完全符合条件的股票，尝试获取部分符合条件的股票
            if not self.filtered_stocks:
                self._update_status("未找到完全符合八大步骤的股票，展示部分符合条件的股票...")
                
                # 分步获取各步骤筛选结果
                try:
                    # 步骤1: 涨幅3%-5%
                    self._update_status("获取符合步骤1的股票...")
                    step1_stocks = self.data_fetcher.filter_by_price_increase(stocks[:200])
                    step_results[1] = step1_stocks
                    
                    if step1_stocks:
                        # 步骤2: 量比>1
                        self._update_status("获取符合步骤1-2的股票...")
                        step2_stocks = self.data_fetcher.filter_by_volume_ratio(step1_stocks)
                        step_results[2] = step2_stocks
                        
                        if step2_stocks:
                            # 步骤3: 换手率5%-10%
                            self._update_status("获取符合步骤1-3的股票...")
                            step3_stocks = self.data_fetcher.filter_by_turnover_rate(step2_stocks)
                            step_results[3] = step3_stocks
                            
                            if step3_stocks:
                                # 步骤4: 市值50亿-200亿
                                self._update_status("获取符合步骤1-4的股票...")
                                step4_stocks = self.data_fetcher.filter_by_market_cap(step3_stocks)
                                step_results[4] = step4_stocks
                                
                                if step4_stocks:
                                    # 步骤5: 成交量持续放大
                                    self._update_status("获取符合步骤1-5的股票...")
                                    step5_stocks = self.data_fetcher.filter_by_increasing_volume(step4_stocks)
                                    step_results[5] = step5_stocks
                                    
                                    if step5_stocks:
                                        # 步骤6: 短期均线搭配60日线向上
                                        self._update_status("获取符合步骤1-6的股票...")
                                        step6_stocks = self.data_fetcher.filter_by_moving_averages(step5_stocks)
                                        step_results[6] = step6_stocks
                                        
                                        if step6_stocks:
                                            # 步骤7: 强于大盘
                                            self._update_status("获取符合步骤1-7的股票...")
                                            step7_stocks = self.data_fetcher.filter_by_market_strength(step6_stocks)
                                            step_results[7] = step7_stocks
                
                except Exception as e:
                    logger.error(f"获取部分符合条件的股票时出错: {str(e)}")
                
                # 从后往前找到第一个有结果的步骤
                partial_stocks = []
                max_step = 0
                for step in range(7, 0, -1):
                    if step in step_results and step_results[step]:
                        partial_stocks = step_results[step]
                        max_step = step
                        break
                
                if not partial_stocks and 1 in step_results:
                    # 如果没有找到任何部分符合的，至少显示符合第一步的
                    partial_stocks = step_results[1]
                    max_step = 1
                
                # 如果找到部分符合条件的股票，使用它们
                if partial_stocks:
                    self.filtered_stocks = partial_stocks
                    self.partial_match = True
                    self.max_step = max_step
                else:
                    # 如果仍然没有，显示顶部涨幅股票
                    self._update_status("没有找到任何符合条件的股票，显示当日涨幅前20只股票...")
                    stock_data = self.data_fetcher.get_realtime_data(stocks[:200])
                    rising_stocks = sorted(stock_data, key=lambda x: x['change_pct'], reverse=True)
                    self.filtered_stocks = [stock['code'] for stock in rising_stocks[:20]]
                    self.partial_match = True
                    self.max_step = 0
            else:
                # 完全符合八大步骤
                self.partial_match = False
            
            # 获取详细信息
            self._update_status("获取股票详细信息...")
            self.detailed_info = self.data_fetcher.get_detailed_info(self.filtered_stocks)
            
            # 在UI线程中更新界面
            self.root.after(0, self._update_ui_with_results)
            
        except Exception as e:
            self.root.after(0, lambda: self._handle_error(str(e)))
        finally:
            self.is_running = False
    
    def _update_ui_with_results(self):
        """使用筛选结果更新UI"""
        # 清空表格
        self.stock_table.delete(*self.stock_table.get_children())
        
        # 添加筛选结果到表格
        for stock in self.detailed_info:
            values = (
                stock['code'],
                stock['name'],
                f"{stock['price']:.2f}",
                f"{stock['change_pct']:.2f}%",
                f"{stock['volume']:,}",
                f"{stock['turnover_rate']:.2f}%",
                f"{stock['market_cap']:.2f}"
            )
            self.stock_table.insert("", tk.END, values=values)
        
        # 更新结果统计信息
        if hasattr(self, 'partial_match') and self.partial_match:
            if hasattr(self, 'max_step') and self.max_step > 0:
                summary = f"⚠️ 警告：未找到完全符合八大步骤的股票\n\n"
                summary += f"显示的是符合前{self.max_step}步条件的股票\n"
                summary += f"共{len(self.filtered_stocks)}只股票\n\n"
                summary += f"完成时间: {datetime.now().strftime('%H:%M:%S')}"
                
                # 设置结果文本背景为黄色警告色
                self.result_text.config(state=tk.NORMAL, background="#FFFACD")  # 淡黄色
                self._update_result_text(summary)
                
                # 设置警告标签
                self._update_status(f"⚠️ 仅显示符合前{self.max_step}步的股票")
            else:
                summary = f"⚠️ 警告：未找到任何符合八大步骤的股票\n\n"
                summary += f"显示的是当日涨幅前20只股票\n"
                summary += f"共{len(self.filtered_stocks)}只股票\n\n"
                summary += f"完成时间: {datetime.now().strftime('%H:%M:%S')}"
                
                # 设置结果文本背景为红色警告色
                self.result_text.config(state=tk.NORMAL, background="#FFE4E1")  # 淡红色
                self._update_result_text(summary)
                
                # 设置警告标签
                self._update_status("⚠️ 未找到符合条件股票，显示涨幅前20")
        else:
            summary = f"✅ 筛选完成，成功找到八大步骤股票!\n\n"
            summary += f"初始股票数: {len(self.data_fetcher.get_stock_list(self.selected_market.get()))}\n"
            summary += f"筛选结果数: {len(self.filtered_stocks)}\n\n"
            summary += f"完成时间: {datetime.now().strftime('%H:%M:%S')}"
            
            # 设置结果文本背景为绿色成功色
            self.result_text.config(state=tk.NORMAL, background="#E0F8E0")  # 淡绿色
            self._update_result_text(summary)
            self._update_status("✅ 筛选完成")
        
        # 如果有结果，自动选择第一个
        if self.detailed_info:
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
    
    def _update_kline_chart(self, stock_code):
        """更新K线图"""
        try:
            # 获取K线数据
            kline_data = self.data_fetcher.get_kline_data(stock_code, kline_type=1, num_periods=60)
            
            if not kline_data:
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
            
            # 设置图表
            ax1.set_title(f"{stock_code} 日K线", fontproperties="SimHei")
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
            
        except Exception as e:
            messagebox.showerror("错误", f"更新K线图时出错: {str(e)}")
    
    def _update_detail_info(self, stock_info):
        """更新详细信息"""
        # 格式化详细信息文本
        detail_text = f"股票代码: {stock_info['code']}\n"
        detail_text += f"股票名称: {stock_info['name']}\n"
        detail_text += f"当前价格: {stock_info['price']:.2f}\n"
        detail_text += f"涨跌幅: {stock_info['change_pct']:.2f}%\n"
        detail_text += f"成交量: {stock_info['volume']:,}\n"
        detail_text += f"换手率: {stock_info['turnover_rate']:.2f}%\n"
        detail_text += f"市值(亿): {stock_info['market_cap']:.2f}\n"
        
        # 更新文本区域
        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete(1.0, tk.END)
        self.detail_text.insert(tk.END, detail_text)
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

if __name__ == "__main__":
    root = tk.Tk()
    app = TailMarketStockApp(root)
    root.mainloop() 