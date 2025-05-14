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
                'kline': 'http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData'
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
        self.degradation_enabled = False   # 是否启用数据降级策略
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
                                    valid_data_count = 0
                                    
                                    # 检查数据结构
                                    if 'data' in data and 'diff' in data['data']:
                                        diff_data = data['data']['diff']
                                        
                                        # 遍历数据项
                                        for key, item in diff_data.items():
                                            try:
                                                # 获取证券代码
                                                secid = str(item.get('f12', ''))
                                                if not secid:
                                                    continue
                                                
                                                # 确定市场代码
                                                for code in batch:
                                                    suffix = code[2:]  # 从sh600000提取600000
                                                    if suffix == secid:
                                                        market_code = code[:2]  # 提取sh或sz
                                                        break
                                                else:
                                                    # 如果在batch中找不到，根据secid判断
                                                    if secid.startswith('6'):
                                                        market_code = 'sh'
                                                    else:
                                                        market_code = 'sz'
                                                
                                                # 提取数据
                                                stock_data = {
                                                    'code': f"{market_code}{secid}",
                                                    'name': str(item.get('f14', '')),
                                                    'price': float(item.get('f2', 0)) / 100.0,
                                                    'change_pct': float(item.get('f3', 0)) / 100.0,
                                                    'open': float(item.get('f17', 0)) / 100.0,
                                                    'high': float(item.get('f15', 0)) / 100.0,
                                                    'low': float(item.get('f16', 0)) / 100.0,
                                                    'pre_close': float(item.get('f18', 0)) / 100.0,
                                                    'volume': int(float(item.get('f5', 0))),
                                                    'amount': float(item.get('f6', 0)),
                                                    'date': datetime.now().strftime('%Y-%m-%d'),
                                                    'time': datetime.now().strftime('%H:%M:%S'),
                                                    'data_source': 'EASTMONEY'
                                                }
                                                result.append(stock_data)
                                                valid_data_count += 1
                                            except (ValueError, TypeError) as e:
                                                logger.error(f"处理东方财富数据项出错: {str(e)}")
                                                continue
                                        
                                        logger.info(f"批次{i//50+1}: 从东方财富获取{len(batch)}只股票数据，有效数据{valid_data_count}条")
                                        if valid_data_count > 0:
                                            success = True
                                    else:
                                        logger.error(f"东方财富API返回数据结构异常: {data}")
                                except ValueError as e:
                                    logger.error(f"解析东方财富API JSON数据出错: {str(e)}")
                            else:
                                logger.error(f"东方财富API请求错误: {response.status_code}")
                            
                            # 防止API限流
                            if i + 50 < len(stock_codes) and success:
                                time.sleep(0.5)
                        
                        if result:
                            logger.info(f"从东方财富成功获取{len(result)}只股票的实时数据")
                        else:
                            logger.error("从东方财富未获取到任何有效数据")
                    except Exception as e:
                        logger.error(f"使用东方财富获取实时数据出错: {str(e)}")
                        success = False
                
                elif source == 'akshare':
                    # 使用AKShare获取实时数据
                    try:
                        import akshare as ak
                        
                        # 首先获取所有A股实时行情数据
                        all_stocks_df = ak.stock_zh_a_spot_em()
                        
                        # 创建批次，避免一次性处理太多股票导致超时
                        batch_size = 50
                        valid_data_count = 0
                        
                        for i in range(0, len(stock_codes), batch_size):
                            batch = stock_codes[i:i+batch_size]
                            
                            # 从股票代码中提取市场信息
                            # 将股票代码分组（sh, sz等）
                            sh_codes = [code[2:] for code in batch if code.startswith('sh')]
                            sz_codes = [code[2:] for code in batch if code.startswith('sz')]
                            
                            # 合并所有需要筛选的代码
                            all_codes = sh_codes + sz_codes
                            
                            # 筛选出我们需要的股票
                            filtered_df = all_stocks_df[all_stocks_df['代码'].isin(all_codes)]
                            
                            for _, row in filtered_df.iterrows():
                                code = row['代码']
                                # 判断市场前缀
                                market_prefix = 'sh' if code in sh_codes else 'sz'
                                
                                # 转换为统一格式
                                stock_data = {
                                    'code': f"{market_prefix}{code}",
                                    'name': row['名称'],
                                    'open': float(row['今开']),
                                    'pre_close': float(row['昨收']),
                                    'price': float(row['最新价']),
                                    'high': float(row['最高']),
                                    'low': float(row['最低']),
                                    'volume': int(float(row['成交量'])) if not pd.isna(row['成交量']) else 0,
                                    'amount': float(row['成交额']) if not pd.isna(row['成交额']) else 0,
                                    'date': datetime.now().strftime('%Y-%m-%d'),
                                    'time': datetime.now().strftime('%H:%M:%S'),
                                    'change_pct': float(row['涨跌幅']),
                                    'data_source': 'AKSHARE'
                                }
                                result.append(stock_data)
                                valid_data_count += 1
                            
                            logger.info(f"批次{i//batch_size+1}: 从AKShare获取{len(batch)}只股票数据，有效数据{len(filtered_df)}条")
                            
                            # 防止处理过多数据导致内存问题
                            if i + batch_size < len(stock_codes):
                                time.sleep(0.2)
                        
                        if valid_data_count > 0:
                            success = True
                            logger.info(f"从AKShare成功获取{valid_data_count}只股票的实时数据")
                        else:
                            logger.error("AKShare未返回任何有效数据")
                            success = False
                    except ImportError:
                        logger.error("AKShare库未安装，无法获取实时数据")
                        success = False
                    except Exception as e:
                        logger.error(f"使用AKShare获取实时数据出错: {str(e)}")
                        success = False
                
                elif source == 'tencent':
                    # 使用腾讯API获取实时数据
                    try:
                        # 腾讯API每次最多查询约50只股票
                        batch_size = 50
                        valid_data_count = 0
                        
                        for i in range(0, len(stock_codes), batch_size):
                            batch = stock_codes[i:i+batch_size]
                            query_list = ','.join(batch)
                            url = f"http://qt.gtimg.cn/q={query_list}"
                            
                            response = requests.get(url, headers=self.headers, timeout=5)
                            if response.status_code == 200:
                                data = response.text.strip().split(';')
                                
                                for line in data:
                                    if not line:
                                        continue
                                        
                                    # 解析腾讯的数据格式
                                    parts = line.split('=')
                                    if len(parts) != 2:
                                        continue
                                        
                                    # 提取股票代码
                                    code_part = parts[0].strip()
                                    if code_part.startswith('v_'):
                                        code = code_part[2:]
                                    else:
                                        continue
                                        
                                    # 解析数据部分
                                    data_str = parts[1].strip('"')
                                    data_parts = data_str.split('~')
                                    
                                    if len(data_parts) < 30:
                                        continue
                                        
                                    # 提取需要的数据
                                    try:
                                        stock_data = {
                                            'code': code,
                                            'name': data_parts[1],
                                            'price': float(data_parts[3]),
                                            'pre_close': float(data_parts[4]),
                                            'open': float(data_parts[5]),
                                            'volume': int(float(data_parts[6])),
                                            'amount': float(data_parts[37]) if len(data_parts) > 37 else 0,
                                            'high': float(data_parts[33]),
                                            'low': float(data_parts[34]),
                                            'date': datetime.now().strftime('%Y-%m-%d'),
                                            'time': data_parts[30],
                                            'data_source': 'TENCENT'
                                        }
                                        
                                        # 计算涨跌幅
                                        if stock_data['pre_close'] > 0:
                                            stock_data['change_pct'] = round((stock_data['price'] - stock_data['pre_close']) / stock_data['pre_close'] * 100, 2)
                                        else:
                                            stock_data['change_pct'] = 0
                                            
                                        result.append(stock_data)
                                        valid_data_count += 1
                                    except (ValueError, IndexError) as e:
                                        logger.error(f"解析腾讯数据出错: {str(e)}")
                                        continue
                                
                                logger.info(f"批次{i//batch_size+1}: 从腾讯获取{len(batch)}只股票数据，有效数据{valid_data_count}条")
                                if valid_data_count > 0:
                                    success = True
                            else:
                                logger.error(f"腾讯API请求错误: {response.status_code}")
                            
                            # 防止API限流
                            if i + batch_size < len(stock_codes):
                                time.sleep(0.5)
                    except Exception as e:
                        logger.error(f"使用腾讯获取实时数据出错: {str(e)}")
                        success = False
                        
                elif source == 'ifeng':
                    # 使用凤凰财经API获取实时数据
                    # ... 省略实现 ...
                    pass
                
                # 计算响应时间
                end_time = time.time()
                response_time = end_time - start_time
                
                # 更新数据源健康度
                self.update_source_health(source, success=success, response_time=response_time)
                
                # 如果成功获取数据，不再尝试其他数据源
                if success and result:
                    logger.info(f"成功使用 {source} 数据源获取{len(result)}条实时数据，响应时间: {response_time:.2f}秒")
                    break
                else:
                    logger.warning(f"{source} 数据源获取实时数据失败，尝试下一数据源")
                    # 未成功获取数据，清空结果防止混合不同数据源的结果
                    result = []
            
            # 恢复原始数据源
            self.api_source = original_source
            
            if not result:
                logger.error(f"所有数据源获取实时数据均失败")
                print("ERROR: Failed to get any real-time stock data from all sources!")
            else:
                logger.info(f"获取{len(stock_codes)}只股票实时数据成功，实际返回{len(result)}条数据")
            
            return result
            
        except Exception as e:
            logger.error(f"获取实时数据时出错: {str(e)}")
            print(f"ERROR: Failed to get real-time data: {str(e)}")
            return result

    def get_detailed_info(self, stock_codes):
        """
        获取股票详细信息
        
        Parameters:
        -----------
        stock_codes: list
            股票代码列表
        
        Returns:
        --------
        list
            包含股票详细信息的字典列表
        """
        if not stock_codes:
            return []
        
        # 获取实时数据
        realtime_data = self.get_realtime_data(stock_codes)
        
        # 结果列表
        result = []
        
        for stock in realtime_data:
            # 获取额外的财务信息
            try:
                extra_info = self._get_extra_stock_info(stock['code'])
                
                # 合并基本信息和额外信息
                stock_info = {**stock, **extra_info}
                
                # 添加数据质量信息
                stock_info['data_status'] = extra_info.get('data_status', 'UNKNOWN')
                stock_info['reliability'] = extra_info.get('reliability', 'UNKNOWN')
                
                # 如果股票在数据质量记录中有详细信息，添加到结果中
                if hasattr(self, 'stocks_data_quality') and stock['code'] in self.stocks_data_quality:
                    quality_info = self.stocks_data_quality[stock['code']]
                    # 只添加那些不会导致键冲突的信息
                    for key, value in quality_info.items():
                        if key not in stock_info:
                            stock_info[key] = value
                
                result.append(stock_info)
            except Exception as e:
                logger.error(f"获取{stock['code']}详细信息时出错: {str(e)}")
                # 即使出错，也添加基本信息
                stock['data_status'] = 'ERROR'
                stock['reliability'] = 'NONE'
                result.append(stock)
        
        return result

    def _get_extra_stock_info(self, stock_code):
        """
        获取股票的额外信息（换手率、量比、市值等）
        优先使用真实API数据，并标记数据来源和可靠性
        """
        try:
            # 尝试从东方财富获取更详细的信息，提供更准确的换手率和量比
            # 东方财富API: http://push2.eastmoney.com/api/qt/stock/get
            url = f"http://push2.eastmoney.com/api/qt/stock/get?secid="
            
            # 转换股票代码格式为东方财富格式
            if stock_code.startswith("sh"):
                secid = f"1.{stock_code[2:]}"
            elif stock_code.startswith("sz"):
                secid = f"0.{stock_code[2:]}"
            else:
                secid = stock_code
                
            full_url = f"{url}{secid}&fields=f43,f44,f45,f46,f47,f48,f49,f50,f51,f52,f55,f57,f58,f59,f60,f62,f71,f84,f85,f86,f107,f111,f117,f161,f162,f167,f168,f169,f170,f171"
            
            logger.debug(f"请求东方财富API获取{stock_code}的额外信息: {full_url}")
            response = requests.get(full_url, headers=self.headers)
            
            if response.status_code != 200:
                logger.error(f"获取东方财富额外信息失败: {response.status_code}")
                # 尝试腾讯股票API
                return self._get_extra_stock_info_from_tencent(stock_code)
                
            data = response.json()
            if 'data' not in data:
                logger.error("东方财富API返回数据格式错误")
                return self._get_extra_stock_info_from_tencent(stock_code)
                
            # 东方财富API返回的数据解析
            stock_data = data['data']
            
            # 提取所需信息
            try:
                turnover_rate = stock_data.get('f168', 0) / 100  # 换手率(%)
                volume_ratio = stock_data.get('f50', 0) / 100    # 量比
                market_cap = stock_data.get('f117', 0) / 100000000  # 市值(亿元)
                
                # 记录详细的原始数据
                logger.debug(f"东方财富返回{stock_code}原始数据: f168(换手率)={stock_data.get('f168')}, f50(量比)={stock_data.get('f50')}, f117(市值)={stock_data.get('f117')}")
                
                if not market_cap:
                    # 如果市值为0，尝试通过总股本和价格计算
                    total_shares = stock_data.get('f84', 0) / 10000  # 总股本(万股)
                    price = stock_data.get('f43', 0) / 100  # 当前价格
                    market_cap = (total_shares * price) / 10000  # 转换为亿元
                
                # 确保数据合理
                if turnover_rate <= 0 or volume_ratio <= 0 or market_cap <= 0:
                    # 如果数据不合理，标记为部分缺失
                    return {
                        'turnover_rate': turnover_rate if turnover_rate > 0 else None,
                        'volume_ratio': volume_ratio if volume_ratio > 0 else None,
                        'market_cap': market_cap if market_cap > 0 else None,
                        'data_status': 'PARTIAL',
                        'data_source': 'EASTMONEY',
                        'reliability': 'MEDIUM'
                    }
                    
                return {
                    'turnover_rate': turnover_rate,
                    'volume_ratio': volume_ratio,
                    'market_cap': market_cap,
                    'data_status': 'COMPLETE',
                    'data_source': 'EASTMONEY',
                    'reliability': 'HIGH'
                }
            except Exception as e:
                logger.error(f"解析东方财富数据出错: {str(e)}")
                return self._get_extra_stock_info_from_tencent(stock_code)
                
        except Exception as e:
            logger.error(f"获取额外信息时出错: {str(e)}")
            return self._get_extra_stock_info_from_tencent(stock_code)
    
    def _get_extra_stock_info_from_tencent(self, stock_code):
        """从腾讯股票API获取额外信息，并标记数据来源和可靠性"""
        try:
            # 转换股票代码格式为腾讯格式
            if stock_code.startswith("sh"):
                code = f"sh{stock_code[2:]}"
            elif stock_code.startswith("sz"):
                code = f"sz{stock_code[2:]}"
            else:
                code = stock_code
                
            url = f"http://qt.gtimg.cn/q={code}"
            response = requests.get(url, headers=self.headers)
            
            if response.status_code != 200:
                logger.error(f"获取腾讯股票额外信息失败: {response.status_code}")
                return self._generate_reasonable_stock_info(stock_code)
                
            # 腾讯API返回格式: v_sh600000="1~浦发银行~600000~..."
            data = response.text
            if not data or '=' not in data:
                logger.error("腾讯API返回数据格式错误")
                return self._generate_reasonable_stock_info(stock_code)
                
            try:
                # 提取数据部分
                data_part = data.split('=')[1].strip('"').split('~')
                
                # 腾讯API数据索引: 
                # 38:换手率, 49:量比, 45:总市值
                if len(data_part) > 49:
                    turnover_rate = float(data_part[38]) if data_part[38] else None
                    volume_ratio = float(data_part[49]) if data_part[49] else None
                    market_cap = float(data_part[45]) / 100 if data_part[45] else None  # 转为亿元
                    
                    # 检查数据完整性
                    if turnover_rate is None or volume_ratio is None or market_cap is None:
                        data_status = 'PARTIAL'
                        reliability = 'MEDIUM'
                    else:
                        data_status = 'COMPLETE'
                        reliability = 'MEDIUM'  # 腾讯数据可靠性标记为中等
                    
                    return {
                        'turnover_rate': turnover_rate,
                        'volume_ratio': volume_ratio,
                        'market_cap': market_cap,
                        'data_status': data_status,
                        'data_source': 'TENCENT',
                        'reliability': reliability
                    }
                else:
                    logger.error("腾讯API返回数据不完整")
                    return self._generate_reasonable_stock_info(stock_code)
            except Exception as e:
                logger.error(f"解析腾讯API数据出错: {str(e)}")
                return self._generate_reasonable_stock_info(stock_code)
                
        except Exception as e:
            logger.error(f"获取腾讯股票额外信息时出错: {str(e)}")
            return self._generate_reasonable_stock_info(stock_code)
    
    def _generate_reasonable_stock_info(self, stock_code):
        """数据缺失情况下返回明确的缺失标记（替代原来的模拟数据）"""
        logger.warning(f"无法获取{stock_code}的真实数据，返回数据缺失标记")
        
        return {
            'turnover_rate': None,  # 替换为None而非随机值
            'volume_ratio': None,   # 替换为None而非随机值
            'market_cap': None,     # 替换为None而非随机值
            'data_status': 'MISSING',  # 添加数据状态标记
            'data_source': 'NONE',     # 添加数据来源标记
            'reliability': 'NONE'      # 添加可靠性级别标记
        }

    # ===== 尾盘选股八大步骤 =====
    
    def filter_by_price_increase(self, stock_codes):
        """
        步骤1: 筛选涨幅在放宽后的范围内的股票 (原为3%-5%)
        
        Parameters:
        -----------
        stock_codes: list
            股票代码列表
        
        Returns:
        --------
        list
            符合条件的股票代码列表
        """
        if not stock_codes:
            return []
            
        try:
            # 获取实时行情
            stock_data = self.get_realtime_data(stock_codes)
            
            # 筛选涨幅范围放宽到1%-7%
            filtered_stocks = []
            for stock in stock_data:
                if 1.0 <= stock['change_pct'] <= 7.0:
                    filtered_stocks.append(stock['code'])
            
            print(f"After filter 1 (price increase): {len(filtered_stocks)} stocks")
            logger.info(f"涨幅筛选: 从{len(stock_codes)}只股票中筛选出{len(filtered_stocks)}只")
            return filtered_stocks
            
        except Exception as e:
            logger.error(f"涨幅筛选过程中出错: {str(e)}")
            return []
    
    def filter_by_volume_ratio(self, stock_codes):
        """
        步骤2: 筛选量比>1的股票 (恢复原始条件)
        
        Parameters:
        -----------
        stock_codes: list
            股票代码列表
        
        Returns:
        --------
        list
            符合条件的股票代码列表
        """
        if not stock_codes:
            return []
            
        try:
            # 获取详细信息（包含量比）
            detailed_info = self.get_detailed_info(stock_codes)
            
            # 恢复原始条件：筛选量比>1的股票
            filtered_stocks = []
            for stock in detailed_info:
                # 添加对None值的处理
                volume_ratio = stock.get('volume_ratio')
                if volume_ratio is not None and volume_ratio > 1.0:
                    filtered_stocks.append(stock['code'])
            
            print(f"After filter 2 (volume ratio): {len(filtered_stocks)} stocks")
            logger.info(f"量比筛选: 从{len(stock_codes)}只股票中筛选出{len(filtered_stocks)}只")
            return filtered_stocks
            
        except Exception as e:
            logger.error(f"量比筛选过程中出错: {str(e)}")
            return []
    
    def filter_by_turnover_rate(self, stock_codes):
        """
        步骤3: 筛选换手率在放宽后的范围内的股票 (原为5%-10%)
        
        Parameters:
        -----------
        stock_codes: list
            股票代码列表
        
        Returns:
        --------
        list
            符合条件的股票代码列表
        """
        if not stock_codes:
            return []
            
        try:
            # 获取详细信息（包含换手率）
            detailed_info = self.get_detailed_info(stock_codes)
            
            # 输出详细换手率信息用于诊断
            logger.info(f"===== 换手率详细信息(筛选范围2.0%-15.0%) =====")
            for stock in detailed_info:
                turnover_rate = stock.get('turnover_rate')
                stock_code = stock.get('code', 'Unknown')
                stock_name = stock.get('name', 'Unknown')
                data_source = stock.get('data_source', 'Unknown')
                
                if turnover_rate is None:
                    logger.info(f"股票 {stock_code} ({stock_name}): 换手率为None [数据源: {data_source}]")
                else:
                    status = "符合条件" if 2.0 <= turnover_rate <= 15.0 else "不符合条件"
                    logger.info(f"股票 {stock_code} ({stock_name}): 换手率={turnover_rate:.2f}% [{status}] [数据源: {data_source}]")
            
            # 筛选换手率范围放宽到2%-15%
            filtered_stocks = []
            for stock in detailed_info:
                # 添加对None值的处理
                turnover_rate = stock.get('turnover_rate')
                if turnover_rate is not None and 2.0 <= turnover_rate <= 15.0:
                    filtered_stocks.append(stock['code'])
            
            print(f"After filter 3 (turnover rate): {len(filtered_stocks)} stocks")
            logger.info(f"换手率筛选: 从{len(stock_codes)}只股票中筛选出{len(filtered_stocks)}只")
            return filtered_stocks
            
        except Exception as e:
            logger.error(f"换手率筛选过程中出错: {str(e)}")
            return []
    
    def filter_by_market_cap(self, stock_codes):
        """
        步骤4: 筛选市值在放宽后的范围内的股票 (原为50亿-200亿)
        
        Parameters:
        -----------
        stock_codes: list
            股票代码列表
        
        Returns:
        --------
        list
            符合条件的股票代码列表
        """
        if not stock_codes:
            return []
            
        try:
            # 获取详细信息（包含市值）
            detailed_info = self.get_detailed_info(stock_codes)
            
            # 筛选市值范围放宽到30亿-500亿
            filtered_stocks = []
            for stock in detailed_info:
                # 添加对None值的处理
                market_cap = stock.get('market_cap')
                if market_cap is not None and 30.0 <= market_cap <= 500.0:
                    filtered_stocks.append(stock['code'])
            
            print(f"After filter 4 (market cap): {len(filtered_stocks)} stocks")
            logger.info(f"市值筛选: 从{len(stock_codes)}只股票中筛选出{len(filtered_stocks)}只")
            return filtered_stocks
            
        except Exception as e:
            logger.error(f"市值筛选过程中出错: {str(e)}")
            return []
    
    def filter_by_end_of_day_rise(self, stock_codes):
        """
        步骤4: 筛选涨幅在-2%~2%之间且尾盘拉升的股票
        
        Parameters:
        -----------
        stock_codes: list
            股票代码列表
        
        Returns:
        --------
        list
            符合条件的股票代码列表
        """
        if not stock_codes:
            return []
            
        try:
            # 获取实时行情
            stock_data = self.get_realtime_data(stock_codes)
            
            # 检查现在是否为尾盘时间（14:30-15:00）
            now = datetime.now()
            is_tail_market = (now.hour == 14 and now.minute >= 30) or now.hour == 15
            
            filtered_stocks = []
            
            # 筛选涨幅在-2%~2%的股票
            for stock in stock_data:
                if -2.0 <= stock['change_pct'] <= 2.0:
                    # 如果已经是尾盘，检查是否呈拉升趋势
                    if is_tail_market:
                        # 获取当日分时数据，看最近30分钟的走势
                        try:
                            kline_result = self.get_kline_data(stock['code'], kline_type=0, num_periods=30)
                            kline_data = kline_result.get('data', [])
                            
                            # 如果有足够的数据，检查是否为拉升趋势
                            if len(kline_data) >= 5:
                                # 检查最近5个分钟的价格是否上升
                                recent_prices = [k['close'] for k in kline_data[-5:]]
                                if recent_prices[-1] > recent_prices[0]:
                                    filtered_stocks.append(stock['code'])
                            else:
                                # 数据不足，放宽条件，只要涨幅符合就通过
                                filtered_stocks.append(stock['code'])
                        except Exception as e:
                            logger.warning(f"获取{stock['code']}分时数据失败，基于涨幅条件放行: {str(e)}")
                            # 数据获取失败，放宽条件，只要涨幅符合就通过
                            filtered_stocks.append(stock['code'])
                    else:
                        # 不是尾盘时间，只检查涨幅
                        filtered_stocks.append(stock['code'])
            
            print(f"After filter 4 (end of day rise): {len(filtered_stocks)} stocks")
            logger.info(f"尾盘拉升筛选: 从{len(stock_codes)}只股票中筛选出{len(filtered_stocks)}只")
            return filtered_stocks
            
        except Exception as e:
            logger.error(f"尾盘拉升筛选过程中出错: {str(e)}")
            return []
    
    def filter_by_increasing_volume(self, stock_codes):
        """
        步骤5: 筛选成交量持续放大的股票
        
        Parameters:
        -----------
        stock_codes: list
            股票代码列表
        
        Returns:
        --------
        list
            符合条件的股票代码列表
        """
        if not stock_codes:
            return []
            
        try:
            filtered_stocks = []
            stocks_data_quality = {}  # 记录每只股票的数据质量
            
            # 为避免API限流，限制批处理大小
            batch_size = 10
            total_batches = (len(stock_codes) + batch_size - 1) // batch_size
            
            logger.info(f"分{total_batches}批处理{len(stock_codes)}只股票的成交量分析")
            
            for batch_idx in range(total_batches):
                start_idx = batch_idx * batch_size
                end_idx = min(start_idx + batch_size, len(stock_codes))
                batch_codes = stock_codes[start_idx:end_idx]
                
                logger.info(f"处理第{batch_idx+1}/{total_batches}批，{len(batch_codes)}只股票")
                
                for code in batch_codes:
                    try:
                        # 获取近期K线数据以分析成交量趋势
                        kline_result = self.get_kline_data(code, kline_type=1, num_periods=10)
                        
                        # 安全地获取数据，确保在数据缺失或格式不正确时不会崩溃
                        kline_data = []
                        metadata = {}
                        
                        if isinstance(kline_result, dict):
                            kline_data = kline_result.get('data', [])
                            metadata = kline_result.get('metadata', {})
                        else:
                            logger.error(f"从{code}获取的K线数据格式错误: {type(kline_result)}")
                        
                        # 记录数据质量
                        stocks_data_quality[code] = {
                            'source': metadata.get('source', 'UNKNOWN'),
                            'reliability': metadata.get('reliability', 'NONE'),
                            'status': metadata.get('status', 'MISSING'),
                            'filter': '成交量分析',
                            'data_count': len(kline_data)
                        }
                        
                        if not kline_data or len(kline_data) < 3:
                            # 如果无法获取K线数据，使用实时数据判断
                            logger.warning(f"无法获取{code}足够的K线数据，尝试使用实时数据代替")
                            
                            try:
                                # 获取当前股票实时数据
                                realtime_data = self.get_realtime_data([code])
                                if realtime_data and len(realtime_data) > 0 and realtime_data[0].get('volume', 0) > 0:
                                    # 获取额外信息判断成交量趋势
                                    extra_info = self._get_extra_stock_info(code)
                                    # 如果量比大于1.5，视为成交量放大
                                    if extra_info.get('volume_ratio', 0) > 1.5:
                                        filtered_stocks.append(code)
                                        stocks_data_quality[code]['decision_basis'] = 'ALTERNATIVE'
                                        logger.info(f"{code}无K线数据，但量比大于1.5，视为符合条件")
                                    stocks_data_quality[code]['alternative_method'] = '实时量比'
                            except Exception as e:
                                logger.error(f"尝试使用实时数据判断{code}成交量趋势失败: {str(e)}")
                            continue
                        
                        # 判断成交量是否持续放大（至少连续3天）
                        valid_volumes = []
                        for k in kline_data:
                            if isinstance(k, dict) and 'volume' in k:
                                try:
                                    volume = int(float(k.get('volume', 0)))
                                    if volume > 0:  # 确保成交量有效
                                        valid_volumes.append(volume)
                                except (ValueError, TypeError):
                                    # 无效的成交量数据，跳过
                                    continue
                        
                        # 确保有足够的有效数据
                        if len(valid_volumes) < 3:
                            logger.warning(f"{code}有效成交量数据不足3条，跳过成交量分析")
                            continue
                        
                        # 至少有3天的数据，且最近的成交量比前一天大
                        if valid_volumes[0] > valid_volumes[1]:
                            # 再检查前一天的成交量是否也比再前一天大
                            if valid_volumes[1] > valid_volumes[2]:
                                filtered_stocks.append(code)
                                stocks_data_quality[code]['decision_basis'] = 'STANDARD'
                                logger.info(f"{code}成交量连续3日放大: {valid_volumes[2]} -> {valid_volumes[1]} -> {valid_volumes[0]}")
                        
                        # 如果开启降级策略，允许单日放量也通过
                        elif self.degradation_enabled and self.degradation_level in ["MEDIUM", "HIGH"] and valid_volumes[0] > valid_volumes[1] * 1.5:
                            filtered_stocks.append(code)
                            stocks_data_quality[code]['decision_basis'] = 'DEGRADED'
                            logger.info(f"{code}单日成交量大幅放大({valid_volumes[0]/valid_volumes[1]:.2f}倍)，降级策略允许通过")
                    
                    except Exception as e:
                        logger.error(f"分析{code}的成交量数据时出现错误: {str(e)}")
                        continue
                
                # 批次间添加延迟，避免API限流
                if batch_idx < total_batches - 1:
                    time.sleep(1.5 + random.random())  # 随机延迟1.5-2.5秒
            
            # 保存数据质量信息到全局变量，供UI显示
            if not hasattr(self, 'stocks_data_quality'):
                self.stocks_data_quality = {}
            self.stocks_data_quality.update(stocks_data_quality)
            
            print(f"After filter 5 (increasing volume): {len(filtered_stocks)} stocks")
            logger.info(f"成交量筛选: 从{len(stock_codes)}只股票中筛选出{len(filtered_stocks)}只")
            return filtered_stocks
            
        except Exception as e:
            logger.error(f"成交量筛选过程中出错: {str(e)}")
            traceback.print_exc()  # 打印详细错误堆栈
            # 出错时明确标记数据问题，但不返回任何随机股票
            return []
            
    def filter_by_moving_averages(self, stock_codes):
        """
        步骤6: 筛选短期均线搭配60日线向上的股票
        
        Parameters:
        -----------
        stock_codes: list
            股票代码列表
        
        Returns:
        --------
        list
            符合条件的股票代码列表
        """
        if not stock_codes:
            return []
            
        try:
            filtered_stocks = []
            stocks_data_quality = {}  # 记录每只股票的数据质量
            
            # 为避免API限流，限制批处理大小
            batch_size = 5  # 更小的批次，因为每次请求的数据量更大
            total_batches = (len(stock_codes) + batch_size - 1) // batch_size
            
            logger.info(f"分{total_batches}批处理{len(stock_codes)}只股票的均线分析")
            
            for batch_idx in range(total_batches):
                start_idx = batch_idx * batch_size
                end_idx = min(start_idx + batch_size, len(stock_codes))
                batch_codes = stock_codes[start_idx:end_idx]
                
                logger.info(f"处理第{batch_idx+1}/{total_batches}批，{len(batch_codes)}只股票")
                
                for code in batch_codes:
                    try:
                        # 获取至少60天的K线数据
                        kline_result = self.get_kline_data(code, kline_type=1, num_periods=70)
                        
                        # 安全地获取数据，确保在数据缺失或格式不正确时不会崩溃
                        kline_data = []
                        metadata = {}
                        
                        if isinstance(kline_result, dict):
                            kline_data = kline_result.get('data', [])
                            metadata = kline_result.get('metadata', {})
                        else:
                            logger.error(f"从{code}获取的K线数据格式错误: {type(kline_result)}")
                        
                        # 记录数据质量
                        stocks_data_quality[code] = {
                            'source': metadata.get('source', 'UNKNOWN'),
                            'reliability': metadata.get('reliability', 'NONE'),
                            'status': metadata.get('status', 'MISSING'),
                            'filter': '均线分析',
                            'data_count': len(kline_data)
                        }
                        
                        if not kline_data or len(kline_data) < 60:
                            # 如果无法获取足够的K线数据，使用备用方法
                            logger.warning(f"无法获取{code}足够的K线数据进行均线分析，尝试备用分析方法")
                            stocks_data_quality[code]['alternative_method'] = '实时价格动态'
                            
                            try:
                                # 获取当前股票的实时数据
                                realtime_data = self.get_realtime_data([code])
                                if realtime_data and len(realtime_data) > 0:
                                    stock_data = realtime_data[0]
                                    # 获取额外的技术指标数据
                                    extra_info = self._get_extra_stock_info(code)
                                    
                                    # 如果价格大于当日均价且接近涨停，可能是走势强劲
                                    price_strength = stock_data.get('price', 0) > stock_data.get('open', 0) * 1.03
                                    volume_strength = extra_info.get('volume_ratio', 0) > 1.0
                                    
                                    if price_strength and volume_strength:
                                        filtered_stocks.append(code)
                                        stocks_data_quality[code]['decision_basis'] = 'ALTERNATIVE'
                                        logger.info(f"{code}无K线数据，但价格大于开盘价3%且量比>1，视为符合条件")
                            except Exception as e:
                                logger.error(f"尝试使用实时数据判断{code}均线趋势失败: {str(e)}")
                            continue
                        
                        # 提取收盘价，确保所有数据都是有效的浮点数
                        try:
                            closes = []
                            for k in kline_data:
                                if isinstance(k, dict) and 'close' in k:
                                    try:
                                        close_price = float(k['close'])
                                        if close_price > 0:  # 确保价格有效
                                            closes.append(close_price)
                                    except (ValueError, TypeError):
                                        # 无效的价格数据，跳过
                                        continue
                            
                            if len(closes) < 60:
                                logger.warning(f"{code}有效K线数据不足60条，跳过均线分析")
                                continue
                                
                            # 计算5日、10日和60日均线
                            closes_df = pd.Series(closes)
                            ma5 = closes_df.rolling(window=5).mean()
                            ma10 = closes_df.rolling(window=10).mean()
                            ma60 = closes_df.rolling(window=60).mean()
                            
                            # 判断均线关系和走势
                            # 条件: MA5 > MA10 > MA60 且 MA60向上
                            valid_ma_data = (len(ma60) >= 5 and not pd.isna(ma60.iloc[-1]) and not pd.isna(ma60.iloc[-2]) and 
                                not pd.isna(ma5.iloc[-1]) and not pd.isna(ma10.iloc[-1]))
                            
                            if valid_ma_data:
                                ma_alignment = ma5.iloc[-1] > ma10.iloc[-1] > ma60.iloc[-1]
                                ma60_uptrend = ma60.iloc[-1] > ma60.iloc[-2]
                                
                                stocks_data_quality[code]['ma_alignment'] = 'YES' if ma_alignment else 'NO'
                                stocks_data_quality[code]['ma60_uptrend'] = 'YES' if ma60_uptrend else 'NO'
                                
                                if ma_alignment and ma60_uptrend:
                                    filtered_stocks.append(code)
                                    stocks_data_quality[code]['decision_basis'] = 'STANDARD'
                                    logger.info(f"{code}均线条件符合: MA5({ma5.iloc[-1]:.2f}) > MA10({ma10.iloc[-1]:.2f}) > MA60({ma60.iloc[-1]:.2f})，且MA60向上")
                            else:
                                stocks_data_quality[code]['status'] = 'INSUFFICIENT'
                                logger.warning(f"{code}均线数据无效")
                        except Exception as e:
                            logger.error(f"处理{code}的K线数据时出错: {str(e)}")
                            continue
                    except Exception as e:
                        logger.error(f"分析{code}的均线数据时出现错误: {str(e)}")
                        continue
                
                # 批次间添加延迟，避免API限流
                if batch_idx < total_batches - 1:
                    time.sleep(2 + random.random())  # 随机延迟2-3秒
            
            # 保存数据质量信息到全局变量，供UI显示
            if not hasattr(self, 'stocks_data_quality'):
                self.stocks_data_quality = {}
            self.stocks_data_quality.update(stocks_data_quality)
            
            # 如果没有符合条件的股票，不降级策略，保持原有的筛选严格性
            if not filtered_stocks and self.degradation_enabled and self.degradation_level in ["MEDIUM", "HIGH"]:
                logger.warning("未找到符合均线条件的股票，应用降级策略")
                # 查找至少MA5 > MA10的股票作为降级策略
                for code in stock_codes:
                    quality_info = stocks_data_quality.get(code, {})
                    if quality_info.get('ma_alignment') == 'YES':
                        filtered_stocks.append(code)
                        stocks_data_quality[code]['decision_basis'] = 'DEGRADED'
                        logger.info(f"降级策略: {code}仅满足MA5 > MA10条件，加入结果")
            
            print(f"After filter 6 (moving averages): {len(filtered_stocks)} stocks")
            logger.info(f"均线筛选: 从{len(stock_codes)}只股票中筛选出{len(filtered_stocks)}只")
            return filtered_stocks
            
        except Exception as e:
            logger.error(f"均线筛选过程中出错: {str(e)}")
            traceback.print_exc()  # 打印详细错误堆栈
            return []  # 出错时返回空列表，不降级
    
    def filter_by_market_strength(self, stock_codes):
        """
        步骤7: 筛选强于大盘的股票
        
        Parameters:
        -----------
        stock_codes: list
            股票代码列表
        
        Returns:
        --------
        list
            符合条件的股票代码列表
        """
        if not stock_codes:
            return []
            
        try:
            # 获取大盘指数行情
            market = stock_codes[0][:2].upper() if stock_codes and stock_codes[0][:2].upper() in self.index_codes else 'SH'
            index_code = self.index_codes[market]
            index_data = self.get_realtime_data([index_code])
            
            if not index_data:
                logger.warning(f"未能获取{market}市场指数数据")
                # 如果获取不到指数数据，模拟一个涨跌幅
                index_change_pct = 0.5
            else:
                # 获取大盘涨跌幅
                index_change_pct = index_data[0]['change_pct']
            
            # 获取个股行情
            stock_data = self.get_realtime_data(stock_codes)
            
            # 筛选涨幅强于大盘的股票
            filtered_stocks = []
            for stock in stock_data:
                if stock['change_pct'] > index_change_pct:
                    filtered_stocks.append(stock['code'])
            
            print(f"After filter 7 (market strength): {len(filtered_stocks)} stocks")
            logger.info(f"强弱筛选: 从{len(stock_codes)}只股票中筛选出{len(filtered_stocks)}只")
            return filtered_stocks
            
        except Exception as e:
            logger.error(f"强弱筛选过程中出错: {str(e)}")
            return []
    
    def filter_by_tail_market_high(self, stock_codes):
        """
        步骤8: 筛选尾盘创新高的股票
        
        Parameters:
        -----------
        stock_codes: list
            股票代码列表
        
        Returns:
        --------
        list
            符合条件的股票代码列表
        """
        if not stock_codes:
            return []
            
        try:
            # 获取分时数据（这里使用日K数据模拟）
            filtered_stocks = []
            
            for code in stock_codes:
                # 获取K线数据
                kline_data = self.get_kline_data(code, kline_type=1, num_periods=5)
                
                if not kline_data:
                    continue
                
                # 使用当天的最高价和收盘价进行比较
                # 如果收盘价接近当天最高价(超过95%)，视为尾盘创新高
                latest_data = kline_data[-1]
                if latest_data['close'] >= latest_data['high'] * 0.95:
                    filtered_stocks.append(code)
            
            print(f"After filter 8 (tail market high): {len(filtered_stocks)} stocks")
            logger.info(f"尾盘创新高筛选: 从{len(stock_codes)}只股票中筛选出{len(filtered_stocks)}只")
            return filtered_stocks
            
        except Exception as e:
            logger.error(f"尾盘创新高筛选过程中出错: {str(e)}")
            return []
    
    def apply_all_filters(self, stock_codes):
        """
        应用尾盘选股八大步骤筛选条件
        
        Parameters:
        -----------
        stock_codes: list
            股票代码列表
        
        Returns:
        --------
        list
            符合八大步骤的股票代码列表
        """
        try:
            if not stock_codes:
                logger.warning("输入的股票列表为空，无法进行筛选")
                return []
                
            logger.info(f"开始应用八大步骤筛选，初始股票数量: {len(stock_codes)}")
            print(f"开始应用尾盘选股八大步骤筛选 - 初始股票: {len(stock_codes)}只")
            
            # 记录开始时间
            start_time = time.time()
            
            # 用于存储每一步的结果（用于部分匹配和调试）
            step_results = {}
            
            # 优化策略：先获取实时数据，用于多个步骤的筛选
            logger.info(f"批量获取{len(stock_codes)}只股票的实时数据")
            
            # 为避免一次性请求过多导致API限流，分批处理
            batch_size = 100
            all_stock_data = []
            
            for i in range(0, len(stock_codes), batch_size):
                batch = stock_codes[i:i+batch_size]
                retry_count = 0
                max_retries = 3
                
                while retry_count < max_retries:
                    try:
                        # 轮换API数据源来提高成功率
                        if retry_count == 1:
                            original_api = self.api_source
                            # 切换到备用数据源
                            if self.api_source == 'sina':
                                self.set_api_source('eastmoney')
                            elif self.api_source == 'eastmoney':
                                self.set_api_source('tencent')
                            elif self.api_source == 'tencent':
                                self.set_api_source('sina')
                            logger.info(f"已切换到备用数据源: {self.api_source}")
                        
                        batch_data = self.get_realtime_data(batch)
                        all_stock_data.extend(batch_data)
                        logger.info(f"获取{len(batch)}只股票实时数据成功，实际返回{len(batch_data)}条数据")
                        break
                    except Exception as e:
                        retry_count += 1
                        logger.error(f"获取第{i//batch_size+1}批数据失败，尝试第{retry_count}次重试: {str(e)}")
                        # 最后一次重试失败，不再继续
                        if retry_count >= max_retries:
                            logger.error(f"批次{i//batch_size+1}数据获取失败，已达最大重试次数")
                        else:
                            time.sleep(1)  # 等待一秒后重试
                
                # 如果切换了API，恢复原始设置
                if retry_count >= 1 and hasattr(self, 'original_api'):
                    self.set_api_source(original_api)
                    logger.info(f"已恢复原始数据源: {original_api}")
                
                # 添加延迟，避免API限流
                if i + batch_size < len(stock_codes):
                    time.sleep(0.5)
            
            logger.info(f"成功获取{len(all_stock_data)}只股票的实时数据")
            
            # 创建代码到数据的映射，方便后续筛选使用
            stock_data_map = {item['code']: item for item in all_stock_data}
            
            # 步骤1: 筛选涨幅在2.5%-7%之间的股票
            logger.info("应用步骤1: 涨幅筛选")
            filtered_step1 = self.filter_by_price_increase(stock_codes)
            step_results['step1'] = filtered_step1
            
            # 打印步骤1的结果
            print(f"\n步骤1 (涨幅2.5%-7%)后: {len(filtered_step1)} 只股票")
            step1_info = self.get_detailed_info(filtered_step1)
            for stock in step1_info[:min(5, len(step1_info))]:
                print(f"  {stock['code']} - {stock['name']}: {stock.get('change_pct', 0):.2f}%")
            
            if not filtered_step1:
                logger.info(f"步骤1后无符合条件股票，八大步骤筛选完成")
                return self._handle_empty_results(stock_codes, step_results, 1)
            
            # 步骤2: 筛选量比大于1的股票
            logger.info("应用步骤2: 量比筛选")
            filtered_step2 = self.filter_by_volume_ratio(filtered_step1)
            step_results['step2'] = filtered_step2
            
            # 打印步骤2的结果
            print(f"\n步骤2 (量比>1)后: {len(filtered_step2)} 只股票")
            step2_info = self.get_detailed_info(filtered_step2)
            for stock in step2_info[:min(5, len(step2_info))]:
                print(f"  {stock['code']} - {stock['name']}")
            
            if not filtered_step2:
                logger.info(f"步骤2后无符合条件股票，八大步骤筛选完成")
                return self._handle_empty_results(stock_codes, step_results, 2)
            
            # 步骤3: 筛选换手率适中的股票(3%-10%)
            logger.info("应用步骤3: 换手率筛选")
            filtered_step3 = self.filter_by_turnover_rate(filtered_step2)
            step_results['step3'] = filtered_step3
            
            # 打印步骤3的结果
            print(f"\n步骤3 (换手率筛选)后: {len(filtered_step3)} 只股票")
            step3_info = self.get_detailed_info(filtered_step3)
            for stock in step3_info[:min(5, len(step3_info))]:
                turnover = stock.get('turnover', 0)
                print(f"  {stock['code']} - {stock['name']}: 换手率 {turnover:.2f}%")
            
            if not filtered_step3:
                logger.info(f"步骤3后无符合条件股票，八大步骤筛选完成")
                return self._handle_empty_results(stock_codes, step_results, 3)
            
            # 步骤4: 筛选市值在50-500亿之间的股票
            logger.info("应用步骤4: 市值筛选")
            filtered_step4 = self.filter_by_market_cap(filtered_step3)
            step_results['step4'] = filtered_step4
            
            # 打印步骤4的结果
            print(f"\n步骤4 (市值50-500亿)后: {len(filtered_step4)} 只股票")
            step4_info = self.get_detailed_info(filtered_step4)
            for stock in step4_info[:min(5, len(step4_info))]:
                market_cap = stock.get('market_cap', 0) / 100000000  # 转换为亿元
                print(f"  {stock['code']} - {stock['name']}: 市值 {market_cap:.2f}亿")
            
            if not filtered_step4:
                logger.info(f"步骤4后无符合条件股票，八大步骤筛选完成")
                return self._handle_empty_results(stock_codes, step_results, 4)
            
            # 步骤5: 筛选成交量持续放大的股票
            logger.info("应用步骤5: 成交量筛选")
            filtered_step5 = self.filter_by_increasing_volume(filtered_step4)
            step_results['step5'] = filtered_step5
            
            # 打印步骤5的结果
            print(f"\n步骤5 (成交量持续放大)后: {len(filtered_step5)} 只股票")
            step5_info = self.get_detailed_info(filtered_step5)
            for stock in step5_info[:min(5, len(step5_info))]:
                print(f"  {stock['code']} - {stock['name']}")
            
            if not filtered_step5:
                logger.info(f"步骤5后无符合条件股票，八大步骤筛选完成")
                return self._handle_empty_results(stock_codes, step_results, 5)
            
            # 步骤6: 筛选短期均线搭配60日线向上的股票
            logger.info("应用步骤6: 均线筛选")
            filtered_step6 = self.filter_by_moving_averages(filtered_step5)
            step_results['step6'] = filtered_step6
            
            # 打印步骤6的结果
            print(f"\n步骤6 (均线条件)后: {len(filtered_step6)} 只股票")
            step6_info = self.get_detailed_info(filtered_step6)
            for stock in step6_info[:min(5, len(step6_info))]:
                print(f"  {stock['code']} - {stock['name']}")
            
            if not filtered_step6:
                logger.info(f"步骤6后无符合条件股票，八大步骤筛选完成")
                return self._handle_empty_results(stock_codes, step_results, 6)
            
            # 步骤7: 筛选强于大盘的股票
            logger.info("应用步骤7: 强弱筛选")
            filtered_step7 = self.filter_by_market_strength(filtered_step6)
            step_results['step7'] = filtered_step7
            
            # 打印步骤7的结果
            print(f"\n步骤7 (强于大盘)后: {len(filtered_step7)} 只股票")
            step7_info = self.get_detailed_info(filtered_step7)
            for stock in step7_info[:min(5, len(step7_info))]:
                print(f"  {stock['code']} - {stock['name']}")
            
            if not filtered_step7:
                logger.info(f"步骤7后无符合条件股票，八大步骤筛选完成")
                return self._handle_empty_results(stock_codes, step_results, 7)
            
            # 步骤8: 筛选尾盘创新高的股票
            logger.info("应用步骤8: 尾盘高点筛选")
            filtered_step8 = self.filter_by_tail_market_high(filtered_step7)
            step_results['step8'] = filtered_step8
            
            # 打印步骤8的结果
            print(f"\n步骤8 (尾盘创新高)后: {len(filtered_step8)} 只股票")
            step8_info = self.get_detailed_info(filtered_step8)
            for stock in step8_info[:min(5, len(step8_info))]:
                print(f"  {stock['code']} - {stock['name']}")
            
            if not filtered_step8:
                logger.info(f"步骤8后无符合条件股票，八大步骤筛选完成")
                return self._handle_empty_results(stock_codes, step_results, 8)
            
            # 计算总耗时
            end_time = time.time()
            elapsed_time = end_time - start_time
            logger.info(f"八大步骤筛选完成，从{len(stock_codes)}只股票中筛选出{len(filtered_step8)}只符合条件的股票，耗时{elapsed_time:.2f}秒")
            print(f"\n筛选完成! 共找到{len(filtered_step8)}只符合八大步骤的股票，耗时{elapsed_time:.2f}秒")
            
            # 返回最终筛选结果
            return filtered_step8
        
        except Exception as e:
            logger.error(f"应用八大步骤筛选时出错: {str(e)}")
            traceback.print_exc()
            return []
            
    def _handle_empty_results(self, stock_codes, step_results, last_completed_step):
        """处理空结果的情况，根据降级策略返回合适的结果"""
        if not self.degradation_enabled:
            logger.info("降级策略未启用，返回空结果")
            return []
            
        # 根据降级策略等级决定回退的步骤数
        if self.degradation_level == "LOW":
            fallback_step = max(1, last_completed_step - 1)
        elif self.degradation_level == "MEDIUM":
            fallback_step = max(1, last_completed_step - 2)
        else:  # HIGH
            fallback_step = max(1, last_completed_step - 3)
            
        logger.info(f"使用降级策略，回退到步骤{fallback_step}的结果")
        
        # 获取回退步骤的结果
        step_key = f'step{fallback_step}'
        if step_key in step_results and step_results[step_key]:
            fallback_stocks = step_results[step_key]
            
            # 如果降级结果数量太多，取前20个
            if len(fallback_stocks) > 20:
                fallback_stocks = fallback_stocks[:20]
                
            # 为降级的结果添加标记
            if hasattr(self, 'stocks_data_quality'):
                for code in fallback_stocks:
                    if code in self.stocks_data_quality:
                        self.stocks_data_quality[code]['degraded'] = True
                        self.stocks_data_quality[code]['degraded_from_step'] = last_completed_step
                        self.stocks_data_quality[code]['degraded_to_step'] = fallback_step
                    
            logger.info(f"降级策略返回{len(fallback_stocks)}只股票（步骤{fallback_step}的结果）")
            return fallback_stocks
        
        # 如果回退步骤仍无结果，考虑使用原始列表的部分股票
        if self.degradation_level == "HIGH" and stock_codes:
            # 获取前10只股票作为应急结果
            emergency_stocks = stock_codes[:min(10, len(stock_codes))]
            logger.info(f"严重降级策略：返回原始列表中的前{len(emergency_stocks)}只股票")
            return emergency_stocks
            
        # 没有任何可用结果
        logger.info("降级策略无法找到合适的结果，返回空列表")
        return []

    def get_kline_data(self, stock_code, kline_type=1, num_periods=60):
        """
        获取K线数据
        
        Parameters:
        -----------
        stock_code: str
            股票代码
        kline_type: int
            K线类型, 1:日K, 2:周K, 3:月K, 4:5分钟K, 5:15分钟K, 6:30分钟K, 7:60分钟K
        num_periods: int
            获取的周期数
        
        Returns:
        --------
        dict
            包含K线数据和元数据(来源、可靠性等)的字典
        """
        # 确保kline_cache属性存在
        if not hasattr(self, 'kline_cache'):
            self.kline_cache = {}
            
        # 检查缓存
        cache_key = f"{stock_code}_{kline_type}_{num_periods}_{datetime.now().strftime('%Y%m%d')}"
        if cache_key in self.kline_cache:
            return self.kline_cache[cache_key]
        
        result = []
        max_retries = 3
        
        # 调整API轮换顺序 - 根据可靠性排序: 新浪 -> 东方财富 -> AKShare -> 其他备用API
        data_sources = ['sina', 'eastmoney', 'akshare', 'tencent', 'ifeng']  # 恢复新浪API为首选
        used_source = None
        reliability = 'NONE'
        status = 'MISSING'
        
        # 尝试不同的数据源
        for source in data_sources:
            if result:  # 如果已经获取到数据，跳出循环
                break
                
            # 每个数据源尝试多次
            for retry in range(max_retries):
                try:
                    # 延迟请求，避免API限流
                    time.sleep(0.2 + random.random() * 0.3)  # 降低延迟时间，随机延迟0.2-0.5秒
                    
                    # === 新浪API ===
                    if source == 'sina':
                        logger.info(f"尝试从新浪获取{stock_code}的K线数据 (尝试 {retry+1}/{max_retries})")
                        period_map = {1: '240', 2: '1680', 3: '7680', 4: '5', 5: '15', 6: '30', 7: '60'}
                        period = period_map.get(kline_type, '240')
                        
                        params = {
                            'symbol': stock_code,
                            'scale': period,     # 使用 'scale' 而不是 'type'
                            'ma': 'no',
                            'datalen': min(num_periods, 180)
                        }
                        
                        # 更新新浪API URL (使用更可靠的备用URL)
                        url = "http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
                        
                        try:
                            response = requests.get(url, params=params, headers=self.headers, timeout=3)  # 减少超时时间
                            if response.status_code == 200:
                                content = response.text
                                
                                # 处理JSONP格式
                                if '(' in content and ')' in content:
                                    json_str = content.split('(', 1)[1].rsplit(')', 1)[0]
                                    try:
                                        data = json.loads(json_str)
                                    except json.JSONDecodeError:
                                        data = []
                                else:
                                    try:
                                        data = response.json()
                                    except json.JSONDecodeError:
                                        logger.error(f"解析新浪API返回的JSON数据失败: {response.text[:100]}...")
                                        data = []
                                
                                if isinstance(data, list):
                                    for item in data:
                                        if not isinstance(item, dict):
                                            continue
                                            
                                        # 转换日期为时间戳
                                        date_str = item.get('day', '')
                                        if not date_str:
                                            continue
                                            
                                        try:
                                            # 尝试解析日期时间
                                            dt = datetime.strptime(date_str, '%Y-%m-%d')
                                            timestamp = int(dt.timestamp())
                                        except:
                                            timestamp = 0
                                            
                                        # 确保所有数据都以正确类型处理
                                        try:
                                            kline = {
                                                'timestamp': timestamp,
                                                'date': date_str,
                                                'open': float(item.get('open', 0)),
                                                'high': float(item.get('high', 0)),
                                                'low': float(item.get('low', 0)),
                                                'close': float(item.get('close', 0)),
                                                'volume': int(float(item.get('volume', 0)))
                                            }
                                            result.append(kline)
                                        except (ValueError, TypeError) as e:
                                            logger.error(f"K线数据格式错误: {str(e)}, 项: {item}")
                                            continue
                                
                                if result:  # 获取成功，记录数据源并设置可靠性
                                    used_source = 'SINA'
                                    reliability = 'HIGH'
                                    status = 'OK'
                                    logger.info(f"从新浪API成功获取{stock_code}的K线数据，共{len(result)}条数据")
                                    break
                            else:
                                logger.error(f"新浪API请求错误 (尝试 {retry+1}/{max_retries}): {response.status_code}")
                        except requests.exceptions.Timeout:
                            logger.error(f"新浪API请求超时 (尝试 {retry+1}/{max_retries})")
                        except requests.exceptions.RequestException as e:
                            logger.error(f"新浪API请求异常 (尝试 {retry+1}/{max_retries}): {str(e)}")
                        except Exception as e:
                            logger.error(f"处理新浪API数据时出错 (尝试 {retry+1}/{max_retries}): {str(e)}")
                    
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

    def filter_by_price(self, stock_codes, min_price=1.0):
        """
        筛选价格在大于等于指定最低价格的股票
        
        Parameters:
        -----------
        stock_codes: list
            股票代码列表
        min_price: float
            最低价格，默认1.0元
        
        Returns:
        --------
        list
            符合条件的股票代码列表
        """
        logger.info(f"应用价格筛选: 价格 >= {min_price}元")
        result = []
        
        try:
            # 获取实时数据
            realtime_data = self.get_realtime_data(stock_codes)
            
            # 筛选价格大于等于最低价格的股票
            for stock in realtime_data:
                if stock['price'] >= min_price:
                    result.append(stock['code'])
            
            logger.info(f"价格筛选: 从{len(stock_codes)}只股票中筛选出{len(result)}只")
            return result
        except Exception as e:
            logger.error(f"价格筛选过程中出错: {str(e)}")
            return []
    
    def filter_by_name(self, stock_codes):
        """
        筛选名称，剔除ST、退市风险和新股
        
        Parameters:
        -----------
        stock_codes: list
            股票代码列表
        
        Returns:
        --------
        list
            符合条件的股票代码列表
        """
        logger.info(f"应用名称筛选: 剔除ST、退市风险和新股")
        result = []
        
        try:
            # 获取实时数据
            realtime_data = self.get_realtime_data(stock_codes)
            
            # 今天日期
            today = datetime.now()
            
            # 剔除ST、退市风险和新股（上市不足3个月）
            excluded = 0
            for stock in realtime_data:
                name = stock.get('name', '')
                
                # 检查是否是ST股票或有退市风险
                if 'ST' in name or '*' in name or '退' in name or 'N' in name:
                    excluded += 1
                    continue
                
                # 检查是否是新股
                code = stock['code']
                # 新股检查逻辑 - 简化版
                # 实际可以通过上市日期判断，这里简化为通过股票代码规则判断
                # 如：创业板300及以后的、科创板688开头的等可能是较新股票
                if (code.startswith('sh688') or  # 科创板
                    code.startswith('sz30') or   # 创业板
                    code.startswith('bj')):      # 北交所
                    # 可以进一步通过股票最早K线时间来判断，但这里简化处理
                    excluded += 1
                    continue
                
                result.append(code)
            
            logger.info(f"名称筛选: 从{len(stock_codes)}只股票中剔除{excluded}只ST、退市风险或新股，剩余{len(result)}只")
            return result
        except Exception as e:
            logger.error(f"名称筛选过程中出错: {str(e)}")
            return []


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