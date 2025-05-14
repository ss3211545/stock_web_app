import schedule
import time
import threading
import os
import datetime
import csv
import logging
from data_fetcher import StockDataFetcher

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scheduler.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("TailMarketScheduler")

class StockScheduler:
    """
    尾盘选股定时任务管理器
    在特定时间自动执行选股策略，并将结果保存到文件
    """
    
    def __init__(self, data_fetcher=None, api_source="sina", token=None, interval=60):
        """
        初始化调度器
        
        Parameters:
        -----------
        data_fetcher: StockDataFetcher
            数据获取器实例，如果不提供则创建新实例
        api_source: str
            数据源，默认为新浪财经，仅在不提供data_fetcher时使用
        token: str
            API令牌，仅在不提供data_fetcher且使用需要认证的API时使用
        interval: int
            定时任务检查间隔，单位为秒，默认60秒
        """
        # 设置数据获取器
        if data_fetcher is not None:
            self.data_fetcher = data_fetcher
        else:
            self.data_fetcher = StockDataFetcher(api_source=api_source, token=token)
        
        # 保存结果的目录
        self.results_dir = "results"
        os.makedirs(self.results_dir, exist_ok=True)
        
        # 调度状态
        self.running = False
        self.scheduler_thread = None
        self.check_interval = interval
        
        logger.info(f"初始化尾盘选股调度器，使用{self.data_fetcher.api_source}数据源，检查间隔: {interval}秒")
    
    def set_api_source(self, api_source, token=None):
        """设置数据源"""
        self.data_fetcher.set_api_source(api_source)
        if token and api_source == "alltick":
            self.data_fetcher.set_token(token)
        logger.info(f"数据源已变更为: {api_source}")
    
    def schedule_daily_task(self):
        """设置每日定时任务"""
        # 设置在每个工作日14:30执行尾盘选股
        schedule.every().monday.at("14:30").do(self.run_tail_market_filter)
        schedule.every().tuesday.at("14:30").do(self.run_tail_market_filter)
        schedule.every().wednesday.at("14:30").do(self.run_tail_market_filter)
        schedule.every().thursday.at("14:30").do(self.run_tail_market_filter)
        schedule.every().friday.at("14:30").do(self.run_tail_market_filter)
        
        logger.info("已设置每个工作日14:30自动执行尾盘选股")
    
    def run_tail_market_filter(self, markets=None):
        """
        运行尾盘选股筛选
        
        Parameters:
        -----------
        markets: list
            需要筛选的市场列表，默认为["SH", "SZ"]
        """
        if markets is None:
            markets = ["SH", "SZ"]
        
        logger.info(f"开始执行尾盘选股筛选，市场: {', '.join(markets)}")
        
        all_results = []
        
        for market in markets:
            try:
                logger.info(f"筛选{market}市场...")
                
                # 获取市场股票列表
                stocks = self.data_fetcher.get_stock_list(market=market)
                logger.info(f"获取到{len(stocks)}只{market}股票")
                
                # 应用八大步骤筛选
                filtered_stocks = self.data_fetcher.apply_all_filters(stocks)
                logger.info(f"{market}市场筛选结果: {len(filtered_stocks)}只股票")
                
                # 获取详细信息
                if filtered_stocks:
                    detailed_info = self.data_fetcher.get_detailed_info(filtered_stocks)
                    all_results.extend(detailed_info)
                
            except Exception as e:
                logger.error(f"筛选{market}市场时出错: {str(e)}")
        
        # 保存结果
        if all_results:
            self._save_results(all_results)
            logger.info(f"筛选完成，共找到{len(all_results)}只符合条件的股票")
        else:
            logger.info("筛选完成，没有找到符合条件的股票")
        
        return all_results
    
    def _save_results(self, results):
        """保存结果到CSV文件"""
        # 生成文件名
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(self.results_dir, f"尾盘选股结果_{timestamp}.csv")
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                # 写入表头
                writer.writerow(['代码', '名称', '价格', '涨跌幅(%)', '成交量', '换手率(%)', '市值(亿)'])
                
                # 写入数据
                for stock in results:
                    writer.writerow([
                        stock['code'],
                        stock['name'],
                        f"{stock['price']:.2f}",
                        f"{stock['change_pct']:.2f}",
                        stock['volume'],
                        f"{stock['turnover_rate']:.2f}",
                        f"{stock['market_cap']:.2f}"
                    ])
                    
            logger.info(f"结果已保存到文件: {filename}")
            
            # 也保存到最新结果文件
            latest_file = os.path.join(self.results_dir, "尾盘选股_最新结果.csv")
            with open(latest_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                # 写入表头
                writer.writerow(['代码', '名称', '价格', '涨跌幅(%)', '成交量', '换手率(%)', '市值(亿)', '筛选时间'])
                
                # 写入数据
                for stock in results:
                    writer.writerow([
                        stock['code'],
                        stock['name'],
                        f"{stock['price']:.2f}",
                        f"{stock['change_pct']:.2f}",
                        stock['volume'],
                        f"{stock['turnover_rate']:.2f}",
                        f"{stock['market_cap']:.2f}",
                        timestamp
                    ])
                    
        except Exception as e:
            logger.error(f"保存结果时出错: {str(e)}")
    
    def start(self):
        """启动调度器"""
        if self.running:
            logger.warning("调度器已在运行中")
            return
        
        self.running = True
        
        # 设置每日任务
        self.schedule_daily_task()
        
        # 启动调度线程
        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()
        
        logger.info("调度器已启动")
    
    def _run_scheduler(self):
        """运行调度线程"""
        while self.running:
            schedule.run_pending()
            time.sleep(self.check_interval)  # 每分钟检查一次
    
    def stop(self):
        """停止调度器"""
        if not self.running:
            logger.warning("调度器未运行")
            return
        
        self.running = False
        
        # 等待线程结束
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=1)
            
        # 清空所有调度
        schedule.clear()
        
        logger.info("调度器已停止")
    
    def run_now(self, markets=None):
        """立即执行一次尾盘选股"""
        return self.run_tail_market_filter(markets)


# 示例用法
if __name__ == "__main__":
    # 创建数据获取器实例
    data_fetcher = StockDataFetcher(api_source="sina")
    
    # 创建调度器实例
    scheduler = StockScheduler(data_fetcher=data_fetcher, interval=60)
    
    # 设置每日自动任务
    scheduler.schedule_daily_task()
    
    # 立即执行一次筛选
    print("正在执行尾盘选股...")
    results = scheduler.run_now(markets=["SH", "SZ"])
    
    print(f"筛选完成，找到{len(results)}只符合条件的股票:")
    for stock in results[:5]:  # 只打印前5个结果
        print(f"{stock['code']} - {stock['name']}: ¥{stock['price']:.2f} ({stock['change_pct']:.2f}%)")
    
    # 如果需要启动定时器，取消下面的注释
    # scheduler.start()
    # 
    # try:
    #     # 保持主线程运行
    #     while True:
    #         time.sleep(1)
    # except KeyboardInterrupt:
    #     scheduler.stop()
    #     print("程序已停止") 