import sys
import os
import json
from datetime import datetime
import uuid
from utils.db import get_db

# 将主项目路径添加到Python路径中，以便导入data_fetcher
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
from data_fetcher import StockDataFetcher

class StockService:
    """股票数据服务，基于原data_fetcher封装"""
    
    def __init__(self):
        # 默认使用新浪API作为数据源
        self.data_fetcher = StockDataFetcher(api_source="sina")
        
    def set_api_source(self, api_source, token=None):
        """设置API数据源"""
        self.data_fetcher.set_api_source(api_source)
        if token and api_source == "alltick":
            self.data_fetcher.set_token(token)
    
    def set_degradation_settings(self, enabled=True, level="MEDIUM"):
        """设置数据降级策略"""
        self.data_fetcher.set_degradation_settings(enabled=enabled, level=level)
    
    def get_stock_list(self, market="SH"):
        """获取股票列表
        
        Args:
            market: 市场代码，可选值: SH, SZ, BJ, HK, US
            
        Returns:
            股票列表，格式: [{'code': 'sh600000', 'name': '浦发银行'}, ...]
        """
        stock_list = self.data_fetcher.get_stock_list(market)
        
        # 缓存股票列表到数据库
        self._cache_stock_list(stock_list, market)
        
        return stock_list
    
    def _cache_stock_list(self, stock_list, market):
        """缓存股票列表到数据库"""
        db = get_db()
        cursor = db.cursor()
        
        # 批量插入或更新股票基本信息
        for stock in stock_list:
            code = stock.get('code')
            name = stock.get('name')
            
            if not code or not name:
                continue
                
            # 检查是否已存在
            cursor.execute(
                "SELECT code FROM stock_data WHERE code = %s",
                (code,)
            )
            
            exists = cursor.fetchone()
            
            if exists:
                # 更新
                cursor.execute(
                    """
                    UPDATE stock_data 
                    SET name = %s, market = %s, last_updated = %s
                    WHERE code = %s
                    """,
                    (name, market, datetime.now(), code)
                )
            else:
                # 插入
                cursor.execute(
                    """
                    INSERT INTO stock_data (code, name, market, last_updated)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (code, name, market, datetime.now())
                )
        
        db.commit()
    
    def get_kline_data(self, stock_code, kline_type=1, num_periods=60):
        """获取K线数据
        
        Args:
            stock_code: 股票代码
            kline_type: K线类型，1-日K, 2-周K, 3-月K
            num_periods: 获取的周期数
            
        Returns:
            K线数据，包含开盘价，收盘价，最高价，最低价，成交量等
        """
        kline_result = self.data_fetcher.get_kline_data(stock_code, kline_type, num_periods)
        
        # 缓存K线数据到数据库
        self._cache_kline_data(stock_code, kline_result)
        
        return kline_result
    
    def _cache_kline_data(self, stock_code, kline_data):
        """缓存K线数据到数据库"""
        db = get_db()
        cursor = db.cursor()
        
        # 更新股票的daily_data和metadata字段
        cursor.execute(
            """
            UPDATE stock_data 
            SET daily_data = %s, metadata = %s, last_updated = %s
            WHERE code = %s
            """,
            (
                json.dumps(kline_data.get('data', [])),
                json.dumps(kline_data.get('metadata', {})),
                datetime.now(),
                stock_code
            )
        )
        
        db.commit()
    
    def get_realtime_data(self, stock_codes):
        """获取实时行情数据
        
        Args:
            stock_codes: 股票代码列表
            
        Returns:
            实时行情数据列表
        """
        return self.data_fetcher.get_realtime_data(stock_codes)
    
    def get_stock_details(self, stock_code):
        """获取股票详细信息
        
        Args:
            stock_code: 股票代码
            
        Returns:
            股票详细信息，包含价格、涨跌幅、成交量、换手率等
        """
        # 使用data_fetcher获取详细信息
        detailed_info = self.data_fetcher.get_detailed_info([stock_code])
        
        if not detailed_info or len(detailed_info) == 0:
            return None
            
        # 返回第一个结果
        return detailed_info[0] 