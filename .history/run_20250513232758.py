#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import os
import sys
import tkinter as tk
import threading
import time
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("tail_market_stock.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("TailMarketStockSystem")

def check_dependencies():
    """检查依赖项是否已安装"""
    try:
        import requests
        import pandas
        import numpy
        import matplotlib
        import schedule
        return True
    except ImportError as e:
        print(f"缺少必要的依赖项: {str(e)}")
        print("请先运行: pip install -r requirements.txt")
        return False

def run_gui_app():
    """运行GUI应用程序"""
    try:
        from app import TailMarketStockApp
        root = tk.Tk()
        app = TailMarketStockApp(root)
        root.mainloop()
    except Exception as e:
        logger.error(f"启动GUI应用时出错: {str(e)}")
        print(f"启动GUI应用时出错: {str(e)}")
        sys.exit(1)

def run_scheduler(api_source, token=None, run_now=False):
    """运行定时任务调度器"""
    try:
        from scheduler import TailMarketScheduler
        
        scheduler = TailMarketScheduler(api_source=api_source, token=token)
        
        if run_now:
            print("正在执行尾盘选股...")
            results = scheduler.run_now(markets=["SH", "SZ"])
            
            print(f"筛选完成，找到{len(results)}只符合条件的股票:")
            for stock in results[:10]:  # 打印前10个结果
                print(f"{stock['code']} - {stock['name']}: ¥{stock['price']:.2f} ({stock['change_pct']:.2f}%)")
            
            print(f"\n结果已保存到 results 目录")
            return
            
        scheduler.start()
        print("定时调度器已启动，将在每个工作日的14:30执行尾盘选股...")
        print("按 Ctrl+C 停止程序")
        
        try:
            # 保持主线程运行
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            scheduler.stop()
            print("程序已停止")
            
    except Exception as e:
        logger.error(f"运行调度器时出错: {str(e)}")
        print(f"运行调度器时出错: {str(e)}")
        sys.exit(1)

def run_test():
    """运行测试模式，直接执行一次筛选"""
    try:
        from data_fetcher import StockDataFetcher
        
        print("使用新浪财经API进行测试...")
        fetcher = StockDataFetcher(api_source="sina")
        
        print("获取上证市场股票列表...")
        stocks = fetcher.get_stock_list(market="SH")
        print(f"获取到{len(stocks)}只股票")
        
        print("应用尾盘选股八大步骤筛选...")
        filtered_stocks = fetcher.apply_all_filters(stocks[:10])  # 测试时只筛选前10只股票
        
        print(f"筛选完成，找到{len(filtered_stocks)}只符合条件的股票")
        if filtered_stocks:
            details = fetcher.get_detailed_info(filtered_stocks)
            for stock in details:
                print(f"{stock['code']} - {stock['name']}: ¥{stock['price']:.2f} ({stock['change_pct']:.2f}%)")
        
        print("测试成功完成！系统工作正常")
    except Exception as e:
        logger.error(f"测试时出错: {str(e)}")
        print(f"测试时出错: {str(e)}")
        sys.exit(1)

def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="尾盘选股八大步骤系统")
    parser.add_argument('--mode', choices=['gui', 'scheduler', 'test'], default='gui',
                       help='运行模式: gui(图形界面), scheduler(定时任务), test(测试)')
    parser.add_argument('--api', choices=['sina', 'hexun', 'alltick'], default='sina',
                       help='数据源: sina(新浪财经), hexun(和讯), alltick(AllTick)')
    parser.add_argument('--token', type=str, help='AllTick API的token (仅在使用alltick时需要)')
    parser.add_argument('--run-now', action='store_true', help='立即执行一次筛选（仅调度器模式有效）')
    
    args = parser.parse_args()
    
    # 显示欢迎信息
    print("="*60)
    print("尾盘选股八大步骤系统")
    print("基于尾盘选股八大步骤策略的自动化选股系统")
    print("="*60)
    
    # 检查依赖项
    if not check_dependencies():
        sys.exit(1)
    
    # 运行所选模式
    if args.mode == 'gui':
        print("启动图形界面模式...")
        run_gui_app()
    elif args.mode == 'scheduler':
        print(f"启动定时任务模式，使用{args.api}数据源...")
        run_scheduler(args.api, args.token, args.run_now)
    elif args.mode == 'test':
        print("运行测试模式...")
        run_test()
    else:
        print(f"未知的运行模式: {args.mode}")
        sys.exit(1)

if __name__ == "__main__":
    main() 