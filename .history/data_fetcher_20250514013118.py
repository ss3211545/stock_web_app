import requests
import json
import time
import random
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
import traceback

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
            },
            'eastmoney': {
                'stock_list': 'http://80.push2.eastmoney.com/api/qt/clist/get',
                'realtime': 'http://82.push2.eastmoney.com/api/qt/ulist/get',
                'kline': 'http://push2his.eastmoney.com/api/qt/stock/kline/get'
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
        
        # 设置降级策略
        self.degradation_enabled = True   # 是否启用数据降级策略
        self.degradation_level = "MEDIUM"  # 降级程度: LOW, MEDIUM, HIGH
        
        # 数据质量信息记录
        self.stocks_data_quality = {}
        
        # 数据源健康度跟踪
        self.source_health = {
            'sina': {'success': 0, 'failure': 0, 'last_success': None, 'response_time': 0},
            'eastmoney': {'success': 0, 'failure': 0, 'last_success': None, 'response_time': 0},
            'tencent': {'success': 0, 'failure': 0, 'last_success': None, 'response_time': 0},
            'akshare': {'success': 0, 'failure': 0, 'last_success': None, 'response_time': 0},
            'ifeng': {'success': 0, 'failure': 0, 'last_success': None, 'response_time': 0},
            'hexun': {'success': 0, 'failure': 0, 'last_success': None, 'response_time': 0},
            'alltick': {'success': 0, 'failure': 0, 'last_success': None, 'response_time': 0}
        }
        
        # 智能数据源切换记录
        self.auto_switch_count = 0
        self.last_switch_time = None
        
        logger.info(f"初始化数据获取器，使用{api_source}数据源")
        print(f"Using {api_source.upper()} API for stock data.")
    
    def set_api_source(self, api_source):
        """设置数据源"""
        self.api_source = api_source
        logger.info(f"API source changed to {api_source}.")
        print(f"API source changed to {api_source.upper()}.")
    
    def set_token(self, token):
        """设置AllTick API Token"""
        self.token = token
        logger.info("Token has been set.")
        print("Token has been set successfully.")
    
    def get_best_data_source(self, data_type='realtime'):
        """
        基于历史数据源健康度，智能选择最佳数据源
        
        Parameters:
        -----------
        data_type: str
            数据类型，'realtime'(实时数据), 'kline'(K线), 'stock_list'(股票列表)
        
        Returns:
        --------
        list
            按优先级排序的数据源列表
        """
        # 基础数据源排序
        base_sources = []
        
        # 根据数据类型调整优先级
        if data_type == 'realtime':
            # 实时数据优先考虑速度
            base_sources = ['sina', 'eastmoney', 'akshare', 'tencent', 'ifeng']
        elif data_type == 'kline':
            # K线数据优先考虑稳定性和完整性
            base_sources = ['eastmoney', 'akshare', 'sina', 'tencent', 'ifeng']
        elif data_type == 'stock_list':
            # 股票列表优先考虑完整性
            base_sources = ['akshare', 'eastmoney', 'sina', 'tencent']
        
        # 根据历史成功率调整顺序
        sources_with_score = []
        for source in base_sources:
            health = self.source_health.get(source, {})
            success = health.get('success', 0)
            failure = health.get('failure', 0)
            
            # 计算成功率 (避免除以零)
            if success + failure > 0:
                success_rate = success / (success + failure)
            else:
                success_rate = 0.5  # 默认值
                
            # 计算时间衰减因子
            if health.get('last_success'):
                seconds_since_success = (datetime.now() - health['last_success']).total_seconds()
                time_factor = max(0, 1 - seconds_since_success / 3600)  # 1小时内衰减到0
            else:
                time_factor = 0.5  # 默认值
                
            # 计算响应时间分数（越快越好）
            response_time = health.get('response_time', 1)
            if response_time > 0:
                speed_score = min(1, 1 / response_time)  # 响应时间越短，分数越高
            else:
                speed_score = 0.5  # 默认值
            
            # 综合评分 (成功率 * 0.6 + 时间因子 * 0.2 + 速度分数 * 0.2)
            score = success_rate * 0.6 + time_factor * 0.2 + speed_score * 0.2
            
            sources_with_score.append((source, score))
        
        # 按分数降序排序
        sources_with_score.sort(key=lambda x: x[1], reverse=True)
        
        # 提取排序后的数据源列表
        sorted_sources = [source for source, _ in sources_with_score]
        
        # 确保当前设置的API源在列表中的优先级
        if self.api_source in sorted_sources:
            # 如果当前API已在列表中，将其提升优先级
            sorted_sources.remove(self.api_source)
            sorted_sources.insert(0, self.api_source)
        else:
            # 如果没在列表中，也添加到首位
            sorted_sources.insert(0, self.api_source)
        
        # 返回去重后的列表
        return list(dict.fromkeys(sorted_sources))
    
    def update_source_health(self, source, success=True, response_time=None):
        """
        更新数据源健康状态
        
        Parameters:
        -----------
        source: str
            数据源名称
        success: bool
            请求是否成功
        response_time: float
            响应时间（秒）
        """
        if source not in self.source_health:
            self.source_health[source] = {
                'success': 0, 
                'failure': 0, 
                'last_success': None,
                'response_time': 0
            }
        
        if success:
            self.source_health[source]['success'] += 1
            self.source_health[source]['last_success'] = datetime.now()
            
            # 更新响应时间（移动平均）
            if response_time is not None:
                old_time = self.source_health[source]['response_time']
                if old_time > 0:
                    # 90% 旧值 + 10% 新值
                    self.source_health[source]['response_time'] = old_time * 0.9 + response_time * 0.1
                else:
                    self.source_health[source]['response_time'] = response_time
        else:
            self.source_health[source]['failure'] += 1
    
    def auto_switch_source_if_needed(self, data_type='realtime'):
        """
        根据健康度情况，自动切换到更好的数据源
        返回是否进行了切换
        """
        # 获取当前数据源的健康状态
        current_health = self.source_health.get(self.api_source, {})
        failures = current_health.get('failure', 0)
        successes = current_health.get('success', 0)
        
        # 如果当前数据源失败率过高，考虑切换
        switch_needed = False
        if failures >= 5 and failures / (failures + successes + 0.1) > 0.5:
            switch_needed = True
        
        # 如果上次切换时间超过10分钟，允许再次切换
        can_switch_now = True
        if self.last_switch_time:
            minutes_since_last_switch = (datetime.now() - self.last_switch_time).total_seconds() / 60
            if minutes_since_last_switch < 10:
                can_switch_now = False
        
        if switch_needed and can_switch_now:
            # 获取备选数据源列表
            sources = self.get_best_data_source(data_type)
            
            # 移除当前数据源
            if self.api_source in sources:
                sources.remove(self.api_source)
            
            # 如果有备选数据源，切换到第一个
            if sources:
                new_source = sources[0]
                self.set_api_source(new_source)
                self.last_switch_time = datetime.now()
                self.auto_switch_count += 1
                logger.info(f"自动切换数据源: {self.api_source} -> {new_source} (这是今天第{self.auto_switch_count}次切换)")
                return True
        
        return False
    
    def get_stock_list(self, market="SH"):
        """
        获取指定市场的股票列表
        
        Parameters:
        -----------
        market: str
            市场代码，'SH'(上证), 'SZ'(深证), 'BJ'(北证), 'HK'(港股), 'US'(美股)
        
        Returns:
        --------
        list
            股票代码列表
        """
        # 检查缓存
        cache_key = f"{market}_{datetime.now().strftime('%Y%m%d')}"
        if cache_key in self.stock_list_cache:
            return self.stock_list_cache[cache_key]
        
        stocks = []
        
        try:
            if self.api_source == 'sina':
                # 新浪财经API - 分页获取所有股票
                market_code = self.market_mapping[market]['sina']
                
                # 分页参数
                page = 1
                page_size = 100
                total_stocks = []
                
                while True:
                    params = {
                        'page': page,
                        'num': page_size,
                        'sort': 'symbol',
                        'asc': 1,
                        'node': market_code
                    }
                    
                    response = requests.get(self.api_urls['sina']['stock_list'], params=params, headers=self.headers)
                    if response.status_code == 200:
                        data = json.loads(response.text)
                        if not data:  # 如果返回空列表，说明已经获取完所有股票
                            break
                            
                        page_stocks = [item['symbol'] for item in data]
                        total_stocks.extend(page_stocks)
                        
                        logger.info(f"从新浪API成功获取第{page}页{len(page_stocks)}只{market}市场股票")
                        
                        # 如果返回的数量小于页大小，说明已经是最后一页
                        if len(page_stocks) < page_size:
                            break
                            
                        # 请求下一页
                        page += 1
                        
                        # 防止API限流
                        time.sleep(0.5)
                    else:
                        logger.error(f"获取股票列表失败: {response.status_code}")
                        break
                
                stocks = total_stocks
                logger.info(f"从新浪API成功获取总计{len(stocks)}只{market}市场股票")
            
            elif self.api_source == 'hexun':
                # 和讯API
                market_code = self.market_mapping[market]['hexun']
                url = self.api_urls['hexun']['stock_list'].format(market=market_code)
                response = requests.get(url, headers=self.headers)
                if response.status_code == 200:
                    data = response.text.strip()
                    if data.startswith('var quote_data=') and data.endswith(';'):
                        data = data[16:-1]  # 移除前缀和后缀
                        data_list = json.loads(data)
                        stocks = [f"{market.lower()}{item['code']}" for item in data_list]
                        logger.info(f"从和讯API成功获取{len(stocks)}只{market}市场股票")
            
            elif self.api_source == 'alltick':
                # AllTick API
                if not self.token:
                    logger.error("使用AllTick API需要提供token")
                    print("ERROR: AllTick API requires a token. Please set it using set_token(your_token) method.")
                    return []
                else:
                    market_code = self.market_mapping[market]['alltick']
                    headers = {'Authorization': f'Bearer {self.token}'}
                    params = {'exchange': market_code}
                    url = f"{self.api_urls['alltick']['base_url']}{self.api_urls['alltick']['stock_list']}"
                    
                    response = requests.get(url, headers=headers, params=params)
                    if response.status_code == 200:
                        data = response.json()
                        stocks = [item['symbol'] for item in data['data']]
                        logger.info(f"从AllTick API成功获取{len(stocks)}只{market}市场股票")
            
            elif self.api_source == 'akshare':
                # 使用AKShare获取股票列表
                try:
                    import akshare as ak
                    
                    # 根据市场选择不同的股票列表获取函数
                    if market == 'SH':
                        # 获取上证A股列表
                        stock_df = ak.stock_info_sh_name_code(symbol="主板A股")
                        if not stock_df.empty:
                            # 转换为sina格式的股票代码
                            stocks = [f"sh{code}" for code in stock_df['证券代码'].tolist()]
                            logger.info(f"从AKShare成功获取{len(stocks)}只{market}市场股票")
                    
                    elif market == 'SZ':
                        # 获取深证A股列表
                        stock_df = ak.stock_info_sz_name_code(symbol="A股列表")
                        if not stock_df.empty:
                            # 转换为sina格式的股票代码
                            stocks = [f"sz{code}" for code in stock_df['A股代码'].tolist()]
                            logger.info(f"从AKShare成功获取{len(stocks)}只{market}市场股票")
                    
                    elif market == 'BJ':
                        # 获取北交所股票列表
                        stock_df = ak.stock_info_bj_name_code()
                        if not stock_df.empty:
                            # 转换为sina格式的股票代码
                            stocks = [f"bj{code}" for code in stock_df['证券代码'].tolist()]
                            logger.info(f"从AKShare成功获取{len(stocks)}只{market}市场股票")
                    
                    elif market == 'HK':
                        # 获取港股列表
                        stock_df = ak.stock_hk_spot_em()
                        if not stock_df.empty:
                            # 转换为sina格式的股票代码
                            stocks = [f"hk{code}" for code in stock_df['代码'].tolist()]
                            logger.info(f"从AKShare成功获取{len(stocks)}只{market}市场股票")
                    
                    elif market == 'US':
                        # 获取美股列表
                        stock_df = ak.stock_us_spot_em()
                        if not stock_df.empty:
                            # 转换为sina格式的股票代码
                            stocks = [f"us{code}" for code in stock_df['代码'].tolist()]
                            logger.info(f"从AKShare成功获取{len(stocks)}只{market}市场股票")
                
                except ImportError:
                    logger.error("AKShare库未安装，无法使用AKShare获取股票列表")
                    print("ERROR: AKShare library is not installed. Please install it using: pip install akshare")
                except Exception as e:
                    logger.error(f"使用AKShare获取股票列表出错: {str(e)}")
                    print(f"ERROR: Failed to get stock list from AKShare: {str(e)}")
            
            elif self.api_source == 'eastmoney':
                # 使用东方财富获取股票列表
                try:
                    if market == 'SH':
                        url = "http://80.push2.eastmoney.com/api/qt/clist/get?pn=1&pz=5000&fs=m:1+t:2,m:1+t:23&fields=f12"
                    elif market == 'SZ':
                        url = "http://80.push2.eastmoney.com/api/qt/clist/get?pn=1&pz=5000&fs=m:0+t:6,m:0+t:80&fields=f12"
                    elif market == 'BJ':
                        url = "http://80.push2.eastmoney.com/api/qt/clist/get?pn=1&pz=5000&fs=m:0+t:81+s:2048&fields=f12"
                    else:
                        logger.error(f"东方财富API不支持{market}市场")
                        return []
                        
                    response = requests.get(url, headers=self.headers)
                    if response.status_code == 200:
                        data = response.json()
                        if 'data' in data and 'diff' in data['data']:
                            if market == 'SH':
                                stocks = [f"sh{item['f12']}" for item in data['data']['diff']]
                            elif market == 'SZ':
                                stocks = [f"sz{item['f12']}" for item in data['data']['diff']]
                            elif market == 'BJ':
                                stocks = [f"bj{item['f12']}" for item in data['data']['diff']]
                            
                            logger.info(f"从东方财富API成功获取{len(stocks)}只{market}市场股票")
                    
                except Exception as e:
                    logger.error(f"使用东方财富获取股票列表出错: {str(e)}")
                    print(f"ERROR: Failed to get stock list from EastMoney: {str(e)}")
            
            # 缓存结果
            if stocks:
                self.stock_list_cache[cache_key] = stocks
                logger.info(f"获取{market}市场股票列表成功，共{len(stocks)}只股票")
            else:
                logger.error(f"获取{market}市场股票列表失败，返回空列表")
                print(f"ERROR: Failed to get stock list for {market} market. Check API connection.")
            
            return stocks
            
        except Exception as e:
            logger.error(f"获取股票列表时出错: {str(e)}")
            print(f"ERROR: Failed to get stock list: {str(e)}")
            return stocks

    def get_realtime_data(self, stock_codes):
        """
        获取实时股票数据
        
        Parameters:
        -----------
        stock_codes: list
            股票代码列表
        
        Returns:
        --------
        list
            股票实时数据列表，包含价格、涨跌幅等信息
        """
        if not stock_codes:
            return []
            
        result = []
        max_retries = 3
        
        try:
            # 使用智能数据源选择功能获取最佳数据源顺序
            data_sources = self.get_best_data_source(data_type='realtime')
            logger.info(f"智能数据源排序: {', '.join(data_sources)}")
            
            # 首先尝试当前设置的数据源
            original_source = self.api_source
            source_tried = set()
            
            # 为了防止过于频繁请求同一数据源，添加自动切换逻辑
            self.auto_switch_source_if_needed(data_type='realtime')
            
            # 对各数据源进行尝试
            for source in data_sources:
                # 如果已经尝试过，跳过
                if source in source_tried:
                    continue
                
                source_tried.add(source)
                self.api_source = source
                logger.info(f"尝试使用 {source} 数据源获取实时数据...")
                
                start_time = time.time()
                success = False
                
                if source == 'sina':
                    # 每次请求不超过80只股票，防止请求过大
                    batch_size = 80
                    for i in range(0, len(stock_codes), batch_size):
                        batch = stock_codes[i:i+batch_size]
                        query_list = ','.join(batch)
                        url = f"{self.api_urls['sina']['realtime']}{query_list}"
                        
                        # 添加重试机制
                        for retry in range(max_retries):
                            try:
                                response = requests.get(url, headers=self.headers, timeout=5)
                                
                                if response.status_code == 200:
                                    lines = response.text.strip().split('\n')
                                    valid_data_count = 0
                                    
                                    for line in lines:
                                        if len(line) > 10:  # 有效数据行
                                            parts = line.split('=')
                                            if len(parts) != 2:
                                                continue
                                                
                                            code = parts[0].split('_')[-1].strip()
                                            values = parts[1].strip(';').strip('"').split(',')
                                            
                                            if len(values) < 32:
                                                continue
                                                
                                            # 提取需要的数据
                                            stock_data = {
                                                'code': code,
                                                'name': values[0],
                                                'open': float(values[1]) if values[1] else 0,
                                                'pre_close': float(values[2]) if values[2] else 0,
                                                'price': float(values[3]) if values[3] else 0,
                                                'high': float(values[4]) if values[4] else 0,
                                                'low': float(values[5]) if values[5] else 0,
                                                'volume': int(float(values[8])) if values[8] else 0,
                                                'amount': float(values[9]) if values[9] else 0,
                                                'date': values[30],
                                                'time': values[31],
                                                'data_source': 'SINA'
                                            }
                                            
                                            # 计算涨跌幅
                                            if stock_data['pre_close'] > 0:
                                                stock_data['change_pct'] = round((stock_data['price'] - stock_data['pre_close']) / stock_data['pre_close'] * 100, 2)
                                            else:
                                                stock_data['change_pct'] = 0
                                            
                                            result.append(stock_data)
                                            valid_data_count += 1
                                    
                                    logger.info(f"批次{i//batch_size+1}: 从新浪获取{len(batch)}只股票数据，有效数据{valid_data_count}条")
                                    
                                    # 请求成功，跳出重试循环
                                    success = True
                                    break
                                else:
                                    logger.error(f"新浪API请求错误 (尝试 {retry+1}/{max_retries}): {response.status_code} {response.reason} for url: {url}")
                                    if retry == max_retries - 1:
                                        logger.error(f"获取实时数据失败，已达最大重试次数")
                                    else:
                                        # 请求失败，等待后重试
                                        time.sleep(1)
                            except Exception as e:
                                logger.error(f"请求新浪数据时出错 (尝试 {retry+1}/{max_retries}): {str(e)}")
                                if retry == max_retries - 1:
                                    logger.error(f"处理数据失败，已达最大重试次数")
                                else:
                                    # 出错，等待后重试
                                    time.sleep(1)
                        
                        # 防止API限流
                        if i + batch_size < len(stock_codes):
                            time.sleep(0.3)
                
                elif source == 'eastmoney':
                    # 使用东方财富获取实时数据
                    try:
                        for i in range(0, len(stock_codes), 50):
                            batch = stock_codes[i:i+50]
                            codes_str = ",".join([
                                f"1.{code[2:]}" if code.startswith("sh") else f"0.{code[2:]}" 
                                for code in batch
                            ])
                            
                            url = f"http://82.push2.eastmoney.com/api/qt/ulist/get?secids={codes_str}&pn=1&pz=50&po=1&fields=f2,f3,f4,f5,f6,f12,f14,f15,f16,f17,f18&ut=bd1d9ddb04089700cf9c27f6f7426281"
                            response = requests.get(url, headers=self.headers, timeout=5)
                            
                            if response.status_code == 200:
                                try:
                                    data = response.json()
                                    if 'data' in data and 'diff' in data['data']:
                                        items = data['data']['diff']
                                        valid_data_count = 0
                                        
                                        for item in items:
                                            # 通过secid分离市场和代码
                                            secid = item.get('f12', '')
                                            if not secid or not isinstance(secid, str):  # 确保secid是有效的字符串
                                                continue
                                                
                                            market_code = 'sh' if codes_str.find(f"1.{secid}") >= 0 else 'sz'
                                            
                                            try:
                                                # 确保所有数值字段都是数值类型
                                                price = float(item.get('f2', 0)) / 100
                                                change_pct = float(item.get('f3', 0)) / 100
                                                open_price = float(item.get('f17', 0)) / 100
                                                high_price = float(item.get('f15', 0)) / 100
                                                low_price = float(item.get('f16', 0)) / 100
                                                pre_close = float(item.get('f18', 0)) / 100
                                                volume = int(float(item.get('f5', 0)))
                                                amount = float(item.get('f6', 0)) / 100000  # 转换为万元
                                                
                                                # 数据异常检测 - 确保价格在合理范围
                                                if price <= 0 or high_price <= 0 or low_price <= 0:
                                                    logger.warning(f"东方财富API返回的{market_code}{secid}价格数据异常，跳过")
                                                    continue
                                                
                                                # 构建股票数据
                                                stock_data = {
                                                    'code': f"{market_code}{secid}",
                                                    'name': item.get('f14', ''),
                                                    'price': price,
                                                    'change_pct': change_pct,
                                                    'open': open_price,
                                                    'high': high_price,
                                                    'low': low_price,
                                                    'pre_close': pre_close,
                                                    'volume': volume,
                                                    'amount': amount,
                                                    'date': datetime.now().strftime('%Y-%m-%d'),
                                                    'time': datetime.now().strftime('%H:%M:%S'),
                                                    'data_source': 'EASTMONEY',
                                                    'data_quality': 'HIGH'  # 默认高质量
                                                }
                                                
                                                # 数据一致性检查
                                                if high_price < low_price or price > high_price * 1.1 or price < low_price * 0.9:
                                                    stock_data['data_quality'] = 'MEDIUM'  # 降低数据质量评级
                                                
                                                result.append(stock_data)
                                                valid_data_count += 1
                                            except (ValueError, TypeError) as e:
                                                logger.error(f"处理东方财富数据时出错: {str(e)}, 股票代码: {secid}")
                                            logger.error(f"K线数据格式错误: {str(e)}, 项: {item}")
                                            continue
                                
                                if result:  # 获取成功，记录数据源并设置可靠性
                                    used_source = 'SINA'
                                    reliability = 'HIGH'
                                    status = 'OK'
                                    logger.info(f"从新浪API成功获取{stock_code}的K线数据，共{len(result)}条数据")
                                    break
                            except json.JSONDecodeError as e:
                                logger.error(f"解析新浪K线数据失败: {str(e)}")
                        else:
                            logger.error(f"新浪API请求错误 (尝试 {retry+1}/{max_retries}): {response.status_code}")
                    
                    # === 东方财富API (提升到第二位) ===
                    elif source == 'eastmoney':
                        logger.info(f"尝试从东方财富获取{stock_code}的K线数据 (尝试 {retry+1}/{max_retries})")
                        
                        # 转换股票代码格式为东方财富格式 (0.股票代码 或 1.股票代码)
                        market_id = '1' if stock_code.startswith('sh') else '0'
                        code_only = stock_code[2:]
                        
                        # 设置K线类型
                        period_map = {1: '101', 2: '102', 3: '103', 4: '5', 5: '15', 6: '30', 7: '60'}
                        period = period_map.get(kline_type, '101')
                        
                        # 构建URL
                        url = f"http://push2his.eastmoney.com/api/qt/stock/kline/get?secid={market_id}.{code_only}&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&klt={period}&fqt=1&end=20500101&lmt={num_periods}"
                        
                        try:
                            response = requests.get(url, headers=self.headers, timeout=5)
                            if response.status_code == 200:
                                try:
                                    json_data = response.json()
                                    
                                    # 解析东方财富API返回的数据
                                    if 'data' in json_data and 'klines' in json_data['data']:
                                        data = json_data['data']['klines']
                                        
                                        for item_str in data:
                                            try:
                                                item = item_str.split(',')
                                                if len(item) >= 6:
                                                    date_str = item[0]
                                                    try:
                                                        dt = datetime.strptime(date_str, '%Y-%m-%d')
                                                        timestamp = int(dt.timestamp())
                                                    except:
                                                        timestamp = 0
                                                    
                                                    kline = {
                                                        'timestamp': timestamp,
                                                        'date': date_str,
                                                        'open': float(item[1]),
                                                        'close': float(item[2]),
                                                        'high': float(item[3]),
                                                        'low': float(item[4]),
                                                        'volume': int(float(item[5]))
                                                    }
                                                    result.append(kline)
                                            except (IndexError, ValueError) as e:
                                                logger.error(f"解析东方财富K线单条数据出错: {str(e)}, 数据: {item_str}")
                                                continue
                                
                                    if result:  # 获取成功，记录数据源并设置可靠性
                                        used_source = 'EASTMONEY'
                                        reliability = 'HIGH'  # 提高东方财富的可靠性级别
                                        status = 'OK'
                                        logger.info(f"从东方财富API成功获取{stock_code}的K线数据，共{len(result)}条数据")
                                        break
                                except json.JSONDecodeError as e:
                                    logger.error(f"解析东方财富K线数据失败: {str(e)}")
                            else:
                                logger.error(f"东方财富API请求错误 (尝试 {retry+1}/{max_retries}): {response.status_code}")
                        except requests.exceptions.RequestException as e:
                            logger.error(f"请求东方财富数据出错: {str(e)}")
                    
                    # === 腾讯API(降级为第三位) ===
                    elif source == 'tencent':
                        logger.info(f"尝试从腾讯获取{stock_code}的K线数据 (尝试 {retry+1}/{max_retries})")
                        # 转换股票代码格式为腾讯格式
                        if stock_code.startswith("sh"):
                            code = f"sh{stock_code[2:]}"
                        elif stock_code.startswith("sz"):
                            code = f"sz{stock_code[2:]}"
                        else:
                            code = stock_code
                            
                        # 设置时间范围
                        end_date = datetime.now()
                        start_date = end_date - timedelta(days=num_periods * 2)  # 获取更多天数以确保有足够数据
                        
                        # 腾讯API格式
                        period_map = {1: 'day', 2: 'week', 3: 'month', 4: 'm5', 5: 'm15', 6: 'm30', 7: 'm60'}
                        period = period_map.get(kline_type, 'day')
                        
                        # 构建URL
                        url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},{period},{start_date.strftime('%Y-%m-%d')},{end_date.strftime('%Y-%m-%d')},{num_periods},qfq"
                        
                        try:
                            response = requests.get(url, headers=self.headers, timeout=5)
                            if response.status_code == 200:
                                try:
                                    json_data = response.json()
                                    
                                    # 解析腾讯API返回的数据
                                    if 'data' in json_data and code in json_data['data']:
                                        kline_data = json_data['data'][code]
                                        
                                        # 腾讯API可能返回多种格式的数据
                                        data = None
                                        if period in kline_data:
                                            data = kline_data[period]
                                        elif f"{period}qfq" in kline_data:  # 前复权数据
                                            data = kline_data[f"{period}qfq"]
                                        
                                        if data and isinstance(data, list):
                                            for item in data:
                                                try:
                                                    if len(item) >= 6:
                                                        date_str = item[0]
                                                        try:
                                                            dt = datetime.strptime(date_str, '%Y-%m-%d')
                                                            timestamp = int(dt.timestamp())
                                                        except:
                                                            timestamp = 0
                                                        
                                                        kline = {
                                                            'timestamp': timestamp,
                                                            'date': date_str,
                                                            'open': float(item[1]),
                                                            'close': float(item[2]),
                                                            'high': float(item[3]),
                                                            'low': float(item[4]),
                                                            'volume': int(float(item[5]))
                                                        }
                                                        result.append(kline)
                                                except (IndexError, ValueError) as e:
                                                    logger.error(f"解析腾讯K线单条数据出错: {str(e)}")
                                                    continue
                                    
                                    if result:  # 获取成功，记录数据源并设置可靠性
                                        used_source = 'TENCENT'
                                        reliability = 'MEDIUM'
                                        status = 'OK'
                                        logger.info(f"从腾讯API成功获取{stock_code}的K线数据，共{len(result)}条数据")
                                        break
                                except json.JSONDecodeError as e:
                                    logger.error(f"解析腾讯K线数据失败: {str(e)}")
                            else:
                                logger.error(f"腾讯API请求错误 (尝试 {retry+1}/{max_retries}): {response.status_code}")
                        except requests.exceptions.RequestException as e:
                            logger.error(f"请求腾讯数据出错: {str(e)}")
                    
                    # === 凤凰财经API (新增) ===
                    elif source == 'ifeng':
                        logger.info(f"尝试从凤凰财经获取{stock_code}的K线数据 (尝试 {retry+1}/{max_retries})")
                        # 转换股票代码格式为凤凰财经格式
                        market = '0' if stock_code.startswith('sh') else '1'
                        code_only = stock_code[2:]
                        
                        # 设置K线类型
                        period_map = {1: 'day', 2: 'week', 3: 'month', 4: '5min', 5: '15min', 6: '30min', 7: '60min'}
                        period = period_map.get(kline_type, 'day')
                        
                        # 构建URL
                        url = f"https://api.finance.ifeng.com/akdaily/?code={market}{code_only}&type={period}"
                        
                        try:
                            response = requests.get(url, headers=self.headers, timeout=5)
                            if response.status_code == 200:
                                try:
                                    json_data = response.json()
                                    
                                    # 解析凤凰财经API返回的数据
                                    if 'record' in json_data and isinstance(json_data['record'], list):
                                        data = json_data['record']
                                        
                                        for item in data:
                                            try:
                                                if len(item) >= 6:
                                                    date_str = item[0]
                                                    try:
                                                        dt = datetime.strptime(date_str, '%Y-%m-%d')
                                                        timestamp = int(dt.timestamp())
                                                    except:
                                                        timestamp = 0
                                                        
                                                    kline = {
                                                        'timestamp': timestamp,
                                                        'date': date_str,
                                                        'open': float(item[1]),
                                                        'high': float(item[2]),
                                                        'close': float(item[3]),
                                                        'low': float(item[4]),
                                                        'volume': int(float(item[5]))
                                                    }
                                                    result.append(kline)
                                            except (IndexError, ValueError) as e:
                                                logger.error(f"解析凤凰财经K线单条数据出错: {str(e)}")
                                                continue
                                    
                                    if result:
                                        used_source = 'IFENG'
                                        reliability = 'MEDIUM'
                                        status = 'OK'
                                        logger.info(f"从凤凰财经API成功获取{stock_code}的K线数据，共{len(result)}条数据")
                                        break
                                except json.JSONDecodeError as e:
                                    logger.error(f"解析凤凰财经K线数据失败: {str(e)}")
                            else:
                                logger.error(f"凤凰财经API请求错误 (尝试 {retry+1}/{max_retries}): {response.status_code}")
                        except requests.exceptions.RequestException as e:
                            logger.error(f"请求凤凰财经数据出错: {str(e)}")
                            
                    # === AKShare API (第五个数据源) ===
                    elif source == 'akshare':
                        logger.info(f"尝试从AKShare获取{stock_code}的K线数据 (尝试 {retry+1}/{max_retries})")
                        
                        try:
                            import akshare as ak
                            
                            # 转换股票代码格式为AKShare格式
                            if stock_code.startswith('sh'):
                                ak_code = stock_code[2:]
                                market = "1"
                            elif stock_code.startswith('sz'):
                                ak_code = stock_code[2:]
                                market = "0"
                            else:
                                ak_code = stock_code  # 已经是正确格式
                                market = "1" if ak_code[0] in ["6", "9"] else "0"
                            
                            # 根据K线类型选择合适的接口
                            if kline_type == 1:  # 日K
                                df = ak.stock_zh_a_hist(symbol=ak_code, period="daily", 
                                                     adjust="qfq", start_date=(datetime.now() - timedelta(days=num_periods*2)).strftime('%Y%m%d'),
                                                     end_date=datetime.now().strftime('%Y%m%d'))
                            elif kline_type == 2:  # 周K
                                df = ak.stock_zh_a_hist(symbol=ak_code, period="weekly", 
                                                     adjust="qfq", start_date=(datetime.now() - timedelta(days=num_periods*14)).strftime('%Y%m%d'),
                                                     end_date=datetime.now().strftime('%Y%m%d'))
                            elif kline_type == 3:  # 月K
                                df = ak.stock_zh_a_hist(symbol=ak_code, period="monthly", 
                                                     adjust="qfq", start_date=(datetime.now() - timedelta(days=num_periods*30)).strftime('%Y%m%d'),
                                                     end_date=datetime.now().strftime('%Y%m%d'))
                            elif kline_type in [4, 5, 6, 7]:  # 分钟K线
                                # 分钟K线种类映射
                                minute_map = {4: "5", 5: "15", 6: "30", 7: "60"}
                                period = minute_map.get(kline_type, "5")
                                
                                # 分钟级别数据通常只保留最近的，可以直接获取
                                df = ak.stock_zh_a_hist_min_em(symbol=ak_code, period=period, adjust="qfq")
                                
                                # 限制数量
                                if len(df) > num_periods:
                                    df = df.tail(num_periods)
                            
                            # 确保DataFrame不为空且格式正确
                            if not df.empty:
                                # 将DataFrame转换为K线数据
                                for _, row in df.iterrows():
                                    try:
                                        # 日期格式化
                                        if '日期' in df.columns:
                                            date_str = str(row['日期'])
                                        elif '时间' in df.columns:
                                            date_str = str(row['时间'])
                                        else:
                                            date_str = "未知日期"
                                            
                                        try:
                                            # 尝试解析日期时间
                                            dt = pd.to_datetime(date_str)
                                            timestamp = int(dt.timestamp())
                                        except:
                                            timestamp = 0
                                        
                                        # 获取OHLCV数据
                                        # 检查各列名称
                                        open_col = '开盘' if '开盘' in df.columns else '开'
                                        high_col = '最高' if '最高' in df.columns else '高'
                                        low_col = '最低' if '最低' in df.columns else '低'
                                        close_col = '收盘' if '收盘' in df.columns else '收'
                                        volume_col = '成交量' if '成交量' in df.columns else '量'
                                        
                                        kline = {
                                            'timestamp': timestamp,
                                            'date': date_str,
                                            'open': float(row[open_col]),
                                            'high': float(row[high_col]),
                                            'low': float(row[low_col]),
                                            'close': float(row[close_col]),
                                            'volume': int(float(row[volume_col]))
                                        }
                                        result.append(kline)
                                    except Exception as e:
                                        logger.error(f"解析AKShare单条数据出错: {str(e)}")
                                        continue
                                
                                if result:
                                    used_source = 'AKSHARE'
                                    reliability = 'HIGH'
                                    status = 'OK'
                                    logger.info(f"从AKShare成功获取{stock_code}的K线数据，共{len(result)}条数据")
                                    break
                        except ImportError:
                            logger.warning("AKShare库未安装，跳过此数据源")
                        except Exception as e:
                            logger.error(f"使用AKShare获取K线数据出错: {str(e)}")
                
                except requests.exceptions.RequestException as e:
                    logger.error(f"请求{source} API出错 (尝试 {retry+1}/{max_retries}): {str(e)}")
                except Exception as e:
                    logger.error(f"处理{source}数据出错 (尝试 {retry+1}/{max_retries}): {str(e)}")
                
                # 失败后等待更长时间再重试
                time.sleep(1 + random.random())
        
        # 构建结果
        if result:
            # 按时间排序
            result.sort(key=lambda x: x['timestamp'])
            
        result_with_metadata = {
            'data': result,
            'metadata': {
                'source': used_source,
                'reliability': reliability,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'count': len(result),
                'status': 'COMPLETE' if result else 'MISSING'
            }
        }
        
        # 缓存结果
        self.kline_cache[cache_key] = result_with_metadata
        
        if result:
            logger.info(f"获取{stock_code}的K线数据成功，共{len(result)}条数据，来源: {used_source}，可靠性: {reliability}")
        else:
            logger.error(f"无法获取{stock_code}的K线数据，所有API源请求均失败")
        
        return result_with_metadata

    def set_degradation_settings(self, enabled=True, level="MEDIUM"):
        """设置数据降级策略"""
        self.degradation_enabled = enabled
        self.degradation_level = level
        logger.info(f"数据降级策略: {'启用' if enabled else '禁用'}, 级别: {level}")


# 测试代码
if __name__ == "__main__":
    # 创建数据获取器
    fetcher = StockDataFetcher(api_source="sina")
    
    # 获取股票列表
    print("获取上证A股列表...")
    stocks = fetcher.get_stock_list(market="SH")
    print(f"获取到{len(stocks)}只股票")
    
    # 测试尾盘选股八大步骤
    print("应用尾盘选股八大步骤...")
    # 为了快速测试，只取前10只股票
    test_stocks = stocks[:10] if len(stocks) > 10 else stocks
    filtered_stocks = fetcher.apply_all_filters(test_stocks)
    
    print(f"筛选结果: {filtered_stocks}") 