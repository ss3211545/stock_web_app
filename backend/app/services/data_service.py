import sys
import os
from datetime import datetime
import traceback

# 添加项目根目录到Python路径以便导入原有模块
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

# 导入原有的数据获取器
from data_fetcher import StockDataFetcher

class DataService:
    """数据服务类，封装StockDataFetcher的功能，增加Web应用所需的扩展"""
    
    def __init__(self, api_source="sina", token=None):
        """初始化数据服务"""
        self.data_fetcher = StockDataFetcher(api_source=api_source, token=token)
        self.last_filter_results = []
        self.partial_results = []
        self.last_successful_step = 0
        
    def set_api_source(self, api_source):
        """设置API数据源"""
        self.data_fetcher.set_api_source(api_source)
        
    def set_token(self, token):
        """设置API Token"""
        self.data_fetcher.set_token(token)
        
    def set_degradation_settings(self, enabled=True, level="MEDIUM"):
        """设置数据降级策略"""
        self.data_fetcher.set_degradation_settings(enabled=enabled, level=level)
        
    def get_stock_list(self, market="SH"):
        """获取股票列表"""
        try:
            return self.data_fetcher.get_stock_list(market)
        except Exception as e:
            print(f"获取股票列表出错: {str(e)}")
            traceback.print_exc()
            return []
            
    def filter_by_name(self, stock_codes):
        """预处理：剔除ST、退市风险和新股"""
        try:
            return self.data_fetcher.filter_by_name(stock_codes)
        except Exception as e:
            print(f"按名称筛选出错: {str(e)}")
            traceback.print_exc()
            return stock_codes
            
    def filter_by_price(self, stock_codes, min_price=1.0):
        """预处理：筛选价格大于指定值的股票"""
        try:
            return self.data_fetcher.filter_by_price(stock_codes, min_price)
        except Exception as e:
            print(f"按价格筛选出错: {str(e)}")
            traceback.print_exc()
            return stock_codes
            
    def apply_all_filters(self, stock_codes, step_callback=None):
        """应用八大步骤筛选"""
        try:
            # 保存原始的回调函数
            original_callback = step_callback
            
            # 创建包装函数来捕获每一步的结果
            def wrapped_callback(step_index, status, stock_count, total_count=None):
                if status == 'success':
                    self.last_successful_step = step_index + 1
                    
                # 调用原始回调
                if original_callback:
                    original_callback(step_index, status, stock_count, total_count)
            
            # 应用所有筛选条件
            results = self.data_fetcher.apply_all_filters(stock_codes, step_callback=wrapped_callback)
            
            # 保存结果
            if results:
                self.last_filter_results = results
            
            # 如果结果为空但有partial_results属性，保存部分结果
            if not results and hasattr(self.data_fetcher, 'partial_results'):
                self.partial_results = self.data_fetcher.partial_results
                
            return results
        except Exception as e:
            print(f"应用筛选条件出错: {str(e)}")
            traceback.print_exc()
            return []
            
    def get_stock_details(self, stock_codes):
        """获取股票详细信息"""
        try:
            details = self.data_fetcher.get_detailed_info(stock_codes)
            
            # 增加Web应用需要的附加属性
            for detail in details:
                # 转换日期格式
                detail['update_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # 添加数据质量指标的可读版本
                data_status = detail.get('data_status', 'UNKNOWN')
                reliability = detail.get('reliability', 'UNKNOWN')
                
                if data_status == 'COMPLETE' and reliability == 'HIGH':
                    detail['quality_level'] = 'high'
                    detail['quality_text'] = '完全可靠'
                elif data_status == 'PARTIAL' or reliability == 'MEDIUM':
                    detail['quality_level'] = 'medium'
                    detail['quality_text'] = '部分可靠'
                elif data_status == 'MISSING' or reliability == 'NONE':
                    detail['quality_level'] = 'low'
                    detail['quality_text'] = '数据缺失'
                else:
                    detail['quality_level'] = 'unknown'
                    detail['quality_text'] = '未知状态'
            
            # 保存为最近的筛选结果
            self.last_filter_results = details
            
            return details
        except Exception as e:
            print(f"获取股票详情出错: {str(e)}")
            traceback.print_exc()
            return []
            
    def get_kline_data(self, stock_code, kline_type=1, num_periods=60):
        """获取K线数据"""
        try:
            kline_result = self.data_fetcher.get_kline_data(stock_code, kline_type=kline_type, num_periods=num_periods)
            
            # 增加Web应用需要的附加属性
            if 'metadata' in kline_result:
                kline_result['metadata']['update_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # 添加前端友好的数据源和可靠性显示
                data_source = kline_result['metadata'].get('source', 'UNKNOWN')
                reliability = kline_result['metadata'].get('reliability', 'UNKNOWN')
                
                if reliability == 'HIGH':
                    kline_result['metadata']['reliability_level'] = 'high'
                    kline_result['metadata']['reliability_text'] = '高可靠性'
                elif reliability == 'MEDIUM':
                    kline_result['metadata']['reliability_level'] = 'medium'
                    kline_result['metadata']['reliability_text'] = '中等可靠性'
                else:
                    kline_result['metadata']['reliability_level'] = 'low'
                    kline_result['metadata']['reliability_text'] = '低可靠性'
                    
                kline_result['metadata']['source_text'] = {
                    'sina': '新浪财经',
                    'eastmoney': '东方财富',
                    'tencent': '腾讯财经',
                    'hexun': '和讯财经',
                    'alltick': 'AllTick'
                }.get(data_source, data_source)
            
            return kline_result
        except Exception as e:
            print(f"获取K线数据出错: {str(e)}")
            traceback.print_exc()
            return {'data': [], 'metadata': {'status': 'ERROR', 'message': str(e)}}
            
    def get_top_increase_stocks(self, stock_list, limit=20):
        """获取涨幅最高的股票列表"""
        try:
            # 获取实时数据
            realtime_data = self.data_fetcher.get_realtime_data(stock_list)
            
            # 按涨幅排序
            sorted_stocks = sorted(
                realtime_data, 
                key=lambda x: x.get('change_pct', 0) if x.get('change_pct') is not None else 0,
                reverse=True
            )
            
            # 返回前N个
            return [stock['code'] for stock in sorted_stocks[:limit]]
        except Exception as e:
            print(f"获取涨幅最高股票出错: {str(e)}")
            traceback.print_exc()
            return stock_list[:min(limit, len(stock_list))]
    
    def get_last_filter_results(self):
        """获取最近的筛选结果"""
        return self.last_filter_results 