import requests
import json
import time
import random
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("data_fetcher.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("StockDataFetcher")

class StockDataFetcher:
    """
    股票数据获取器
    支持多种数据源，实现尾盘选股八大步骤
    """
    
    def __init__(self, api_source="sina", token=None):
        """
        初始化数据获取器
        
        Parameters:
        -----------
        api_source: str
            数据源，可选 'sina'(新浪财经), 'hexun'(和讯), 'alltick'(AllTick API)
        token: str
            AllTick API的token，仅在使用alltick时需要
        """
        self.api_source = api_source
        self.token = token
        
        # API基础URL
        self.api_urls = {
            'sina': {
                'stock_list': 'http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData',
                'realtime': 'http://hq.sinajs.cn/list=',
                'kline': 'https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService.getKLineData'
            },
            'hexun': {
                'stock_list': 'http://quote.tool.hexun.com/hqzx/quote.aspx?type=2&market={market}&count=5000',
                'realtime': 'http://quote.tool.hexun.com/hqzx/quote.aspx?type=2&code={code}',
                'kline': 'http://quote.tool.hexun.com/hqzx/quote.aspx?type=5&code={code}&count={count}'
            },
            'alltick': {
                'base_url': 'https://api.alltick.co/v1',
                'stock_list': '/securities',
                'realtime': '/quotes',
                'kline': '/candles'
            }
        }
        
        # 请求头，用于绕过反爬虫机制
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'http://finance.sina.com.cn/'
        }
        
        # 市场代码映射
        self.market_mapping = {
            'SH': {'sina': 'sh_a', 'hexun': '2', 'alltick': 'XSHG'},
            'SZ': {'sina': 'sz_a', 'hexun': '1', 'alltick': 'XSHE'},
            'BJ': {'sina': 'bj_a', 'hexun': '5', 'alltick': 'BJSE'},
            'HK': {'sina': 'hk_main', 'hexun': '7', 'alltick': 'XHKG'},
            'US': {'sina': 'us_main', 'hexun': '6', 'alltick': 'XNAS'}
        }
        
        # 缓存
        self.stock_list_cache = {}
        self.price_cache = {}
        self.kline_cache = {}
        
        # 指数代码
        self.index_codes = {
            'SH': 'sh000001',  # 上证指数
            'SZ': 'sz399001',  # 深证成指
            'BJ': 'bj000001',  # 北证指数
            'HK': 'hkHSI',     # 恒生指数
            'US': 'gb_dji'     # 道琼斯指数
        }
        
        logger.info(f"初始化数据获取器，使用{api_source}数据源")
        print(f"Using {api_source.upper()} API for stock data.") 