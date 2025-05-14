#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import os
import sys
import tkinter as tk
import threading
import time
import logging
from datetime import datetime

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

def run_test(args):
    """运行测试模式，直接执行一次筛选"""
    try:
        from data_fetcher import StockDataFetcher
        
        print("使用新浪财经API进行测试...")
        fetcher = StockDataFetcher(api_source="sina")
        
        print("获取上证市场股票列表...")
        stocks = fetcher.get_stock_list(market="SH")
        print(f"获取到{len(stocks)}只股票")
        
        print("应用尾盘选股八大步骤筛选...")
        filtered_stocks = fetcher.apply_all_filters(stocks[:args.test_stocks])  # 测试时只筛选前10只股票
        
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

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='股票实时监控和选股系统')
    
    # 运行模式
    parser.add_argument('--mode', type=str, choices=['gui', 'cmd', 'test', 'scheduler', 'benchmark'], 
                        default='gui', help='运行模式：gui(GUI界面), cmd(命令行), test(测试), scheduler(定时任务), benchmark(API性能测试)')
    
    # 股票代码或股票列表文件
    parser.add_argument('--stocks', type=str, help='股票代码(逗号分隔)或股票列表文件路径')
    
    # 数据获取API选项
    parser.add_argument('--api', type=str, choices=['sina', 'eastmoney', 'tencent', 'ifeng', 'akshare'],
                        default='sina', help='使用的股票数据API')
    
    # API Token (用于某些需要认证的API)
    parser.add_argument('--token', type=str, help='API Token (用于某些需要认证的API)')
    
    # 定时器选项
    parser.add_argument('--interval', type=int, default=60, 
                        help='数据更新间隔(秒) (用于定时器模式)')
    parser.add_argument('--run-time', type=str, help='指定运行时间，格式: HH:MM (用于定时器模式)')
    parser.add_argument('--run-now', action='store_true', help='立即运行一次(用于定时器模式)')
    
    # 输出选项
    parser.add_argument('--output', type=str, help='输出文件路径')
    parser.add_argument('--quiet', action='store_true', help='静默模式，不输出进度信息')
    
    # 性能测试选项
    parser.add_argument('--benchmark-apis', type=str, 
                        help='用于基准测试的API列表，逗号分隔（例如：sina,eastmoney,akshare）')
    parser.add_argument('--test-stocks', type=int, default=10,
                        help='测试使用的股票数量，默认10只')
    
    args = parser.parse_args()
    return args

def run_benchmark(args):
    """
    运行API性能基准测试，对比不同数据源的性能
    
    Parameters:
    -----------
    args : Namespace
        命令行参数
    """
    logger.info("开始运行API性能基准测试")
    print("\n=== 股票数据API性能基准测试 ===\n")
    
    # 确定要测试的API列表
    apis_to_test = []
    if args.benchmark_apis:
        apis_to_test = [api.strip() for api in args.benchmark_apis.split(',')]
    else:
        # 默认测试所有支持的API
        apis_to_test = ['sina', 'eastmoney', 'tencent', 'akshare', 'ifeng']
    
    # 过滤掉不支持的API
    supported_apis = ['sina', 'eastmoney', 'tencent', 'akshare', 'ifeng']
    apis_to_test = [api for api in apis_to_test if api in supported_apis]
    
    if not apis_to_test:
        logger.error("未指定有效的API进行测试")
        print("错误：未指定有效的API进行测试。支持的API包括：" + ", ".join(supported_apis))
        return
    
    # 测试股票数量
    test_stock_count = args.test_stocks if args.test_stocks > 0 else 10
    
    # 初始化数据获取器，使用sina作为默认源获取测试股票列表
    data_fetcher = StockDataFetcher(api_source='sina')
    
    try:
        # 1. 先获取测试用的股票列表
        print(f"获取测试用股票列表中，默认使用上证市场前{test_stock_count}只股票...")
        sh_stocks = data_fetcher.get_stock_list(market="SH")
        if not sh_stocks:
            print("无法获取上证股票列表，尝试获取深证股票列表...")
            sh_stocks = data_fetcher.get_stock_list(market="SZ")
        
        if not sh_stocks:
            logger.error("无法获取股票列表用于测试")
            print("错误：无法获取股票列表用于测试，请检查网络连接或API可用性。")
            return
            
        # 只使用前N只股票进行测试
        test_stocks = sh_stocks[:test_stock_count]
        print(f"将使用以下{len(test_stocks)}只股票进行测试: {', '.join(test_stocks)}")
        
        # 2. 对每个API进行性能测试
        results = []
        
        for api in apis_to_test:
            print(f"\n测试 {api.upper()} API...")
            data_fetcher.set_api_source(api)
            
            # 每个API测试3轮
            api_times = []
            success_rates = []
            data_completeness = []
            
            for round_num in range(3):
                print(f"  - 轮次 {round_num+1}/3: ", end="", flush=True)
                
                # 记录开始时间
                start_time = time.time()
                
                try:
                    # 获取实时数据
                    realtime_data = data_fetcher.get_realtime_data(test_stocks)
                    
                    # 记录结束时间
                    end_time = time.time()
                    elapsed = end_time - start_time
                    api_times.append(elapsed)
                    
                    # 计算成功率和数据完整性
                    if realtime_data:
                        success_rate = len(realtime_data) / len(test_stocks) * 100
                        success_rates.append(success_rate)
                        
                        # 检查数据完整性
                        fields_to_check = ['code', 'name', 'price', 'open', 'high', 'low', 'volume']
                        completeness_scores = []
                        
                        for item in realtime_data:
                            score = sum(1 for field in fields_to_check if field in item and item[field]) / len(fields_to_check) * 100
                            completeness_scores.append(score)
                        
                        avg_completeness = sum(completeness_scores) / len(completeness_scores) if completeness_scores else 0
                        data_completeness.append(avg_completeness)
                        
                        print(f"成功 - 用时: {elapsed:.2f}秒, 成功率: {success_rate:.1f}%, 数据完整性: {avg_completeness:.1f}%")
                    else:
                        success_rates.append(0)
                        data_completeness.append(0)
                        print(f"失败 - 用时: {elapsed:.2f}秒，未获取到数据")
                
                except Exception as e:
                    # 记录结束时间
                    end_time = time.time()
                    elapsed = end_time - start_time
                    api_times.append(elapsed)
                    success_rates.append(0)
                    data_completeness.append(0)
                    print(f"出错 - 用时: {elapsed:.2f}秒, 错误: {str(e)}")
                
                # 避免频繁请求
                if round_num < 2:  # 最后一轮不需要等待
                    time.sleep(2)
            
            # 计算平均值
            avg_time = sum(api_times) / len(api_times) if api_times else float('inf')
            avg_success = sum(success_rates) / len(success_rates) if success_rates else 0
            avg_completeness = sum(data_completeness) / len(data_completeness) if data_completeness else 0
            
            # 保存结果
            results.append({
                'api': api,
                'avg_time': avg_time,
                'avg_success': avg_success,
                'avg_completeness': avg_completeness,
                'reliability_score': (avg_success * 0.6 + avg_completeness * 0.4) / 100 * (10 - min(avg_time, 10))/10
            })
            
            print(f"  {api.upper()} API 平均性能: 响应时间 {avg_time:.2f}秒, 成功率 {avg_success:.1f}%, 数据完整性 {avg_completeness:.1f}%")
            
            # 在API之间添加间隔，避免频繁请求
            if api != apis_to_test[-1]:
                time.sleep(3)
        
        # 3. 生成最终报告
        if results:
            print("\n\n===== API性能测试结果报告 =====")
            print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"测试股票数量: {len(test_stocks)}")
            print("-----------------------------------")
            print("API        | 响应时间 | 成功率 | 数据完整性 | 综合评分")
            print("-----------|---------|--------|-----------|--------")
            
            # 按综合评分排序
            results.sort(key=lambda x: x['reliability_score'], reverse=True)
            
            for result in results:
                time_str = f"{result['avg_time']:.2f}秒"
                success_str = f"{result['avg_success']:.1f}%"
                completeness_str = f"{result['avg_completeness']:.1f}%"
                score_str = f"{result['reliability_score']:.2f}"
                
                print(f"{result['api']:<10} | {time_str:<7} | {success_str:<6} | {completeness_str:<9} | {score_str}")
            
            print("-----------------------------------")
            print(f"推荐API: {results[0]['api'].upper()} (综合表现最佳)")
            print("\n注意：评测结果基于当前测试，可能受网络状况影响。建议定期重新测试。")
        
        logger.info("API性能基准测试完成")
    
    except Exception as e:
        logger.error(f"性能测试过程中发生错误: {str(e)}")
        print(f"\n错误：测试过程中发生异常: {str(e)}")

def main():
    """主函数"""
    # 检查依赖项
    if not check_dependencies():
        sys.exit(1)
    
    # 解析命令行参数
    args = parse_args()
    
    # 日志级别调整
    if args.quiet:
        logger.setLevel(logging.WARNING)
    
    # 根据运行模式执行不同操作
    if args.mode == 'gui':
        run_gui_app()
    elif args.mode == 'cmd':
        run_cmd_app(args)
    elif args.mode == 'test':
        run_test(args)
    elif args.mode == 'scheduler':
        run_scheduler(args.api, args.token, args.run_now)
    elif args.mode == 'benchmark':
        run_benchmark(args)
    else:
        print(f"不支持的运行模式: {args.mode}")
        sys.exit(1)

if __name__ == "__main__":
    main() 