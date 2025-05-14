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
                    logger.info(f"东方财富返回{stock_code}数据不完整: 换手率={turnover_rate}, 量比={volume_ratio}, 市值={market_cap}")
                    return {
                        'turnover_rate': turnover_rate if turnover_rate > 0 else None,
                        'volume_ratio': volume_ratio if volume_ratio > 0 else None,
                        'market_cap': market_cap if market_cap > 0 else None,
                        'data_status': 'PARTIAL',
                        'data_source': 'EASTMONEY',
                        'reliability': 'MEDIUM'
                    }
                    
                logger.info(f"成功从东方财富获取{stock_code}额外数据: 换手率={turnover_rate:.2f}%, 量比={volume_ratio:.2f}, 市值={market_cap:.2f}亿")
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
            logger.debug(f"请求腾讯API获取{stock_code}的额外信息: {url}")
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
                    # 记录原始数据
                    logger.debug(f"腾讯返回{stock_code}原始数据: 换手率索引[38]={data_part[38]}, 量比索引[49]={data_part[49]}, 总市值索引[45]={data_part[45]}")
                    
                    turnover_rate = float(data_part[38]) if data_part[38] else None
                    volume_ratio = float(data_part[49]) if data_part[49] else None
                    market_cap = float(data_part[45]) / 100 if data_part[45] else None  # 转为亿元
                    
                    # 检查数据完整性
                    if turnover_rate is None or volume_ratio is None or market_cap is None:
                        data_status = 'PARTIAL'
                        reliability = 'MEDIUM'
                        logger.info(f"腾讯返回{stock_code}部分数据缺失: 换手率={turnover_rate}, 量比={volume_ratio}, 市值={market_cap}")
                    else:
                        data_status = 'COMPLETE'
                        reliability = 'MEDIUM'  # 腾讯数据可靠性标记为中等
                        logger.info(f"成功从腾讯获取{stock_code}额外数据: 换手率={turnover_rate:.2f}%, 量比={volume_ratio:.2f}, 市值={market_cap:.2f}亿")
                    
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
            
            # 如果筛选结果为空，执行额外的诊断
            if not filtered_stocks and stock_codes:
                logger.warning(f"换手率筛选后结果为空，执行详细诊断...")
                self.diagnose_filters(stock_codes)
                
                # 输出未通过原因汇总
                failed_reasons = {}
                for stock in detailed_info:
                    turnover_rate = stock.get('turnover_rate')
                    if turnover_rate is None:
                        reason = "换手率数据缺失"
                    elif turnover_rate < 2.0:
                        reason = f"换手率过低(< 2.0%)"
                    elif turnover_rate > 15.0:
                        reason = f"换手率过高(> 15.0%)"
                    else:
                        reason = "未知原因"
                    
                    failed_reasons[reason] = failed_reasons.get(reason, 0) + 1
                
                # 输出汇总结果
                logger.warning("未通过换手率筛选的原因汇总:")
                for reason, count in failed_reasons.items():
                    logger.warning(f"  - {reason}: {count}只股票")
                
                # 如果启用了数据降级，尝试进一步放宽筛选条件
                if hasattr(self, 'degradation_enabled') and self.degradation_enabled:
                    logger.info("数据降级已启用，尝试放宽换手率范围...")
                    
                    # 根据降级级别决定放宽程度
                    if self.degradation_level == "LOW":
                        min_rate, max_rate = 1.5, 16.0  # 轻度放宽
                    elif self.degradation_level == "MEDIUM":
                        min_rate, max_rate = 1.0, 18.0  # 中度放宽
                    else:  # HIGH
                        min_rate, max_rate = 0.5, 20.0  # 重度放宽
                    
                    logger.info(f"放宽换手率范围到{min_rate}%-{max_rate}%")
                    
                    # 应用放宽后的条件
                    filtered_stocks = []
                    for stock in detailed_info:
                        turnover_rate = stock.get('turnover_rate')
                        if turnover_rate is not None and min_rate <= turnover_rate <= max_rate:
                            filtered_stocks.append(stock['code'])
                    
                    print(f"After filter 3 (relaxed turnover rate): {len(filtered_stocks)} stocks")
                    logger.info(f"放宽换手率筛选: 从{len(stock_codes)}只股票中筛选出{len(filtered_stocks)}只")
                    
                    # 记录数据质量信息
                    if not hasattr(self, 'stocks_data_quality'):
                        self.stocks_data_quality = {}
                    
                    for code in filtered_stocks:
                        if code not in self.stocks_data_quality:
                            self.stocks_data_quality[code] = {}
                        
                        self.stocks_data_quality[code]['filter'] = '换手率筛选'
                        self.stocks_data_quality[code]['decision_basis'] = 'FALLBACK'
                        self.stocks_data_quality[code]['alternative_method'] = f'放宽换手率到{min_rate}%-{max_rate}%'
            
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
            
            for stock_code in stock_codes:
                # 获取K线数据（默认获取日线数据）
                kline_data = self.get_kline_data(stock_code, period='daily', limit=5)
                
                if not kline_data or len(kline_data) < 3:
                    logger.warning(f"股票{stock_code}K线数据不足，无法分析成交量趋势")
                    continue
                    
                # 计算最近3天的成交量变化
                # 成交量数据是按时间倒序排序的，最新的在前面
                latest_volumes = [bar['volume'] for bar in kline_data[:3]]
                
                # 判断成交量是否持续放大
                volume_increasing = True
                for i in range(len(latest_volumes) - 1):
                    if latest_volumes[i] <= latest_volumes[i+1]:
                        volume_increasing = False
                        break
                
                # 输出成交量信息
                vol_info = " > ".join([f"{vol:,}" for vol in latest_volumes])
                status = "符合条件" if volume_increasing else "不符合条件"
                logger.info(f"股票{stock_code} - 近3日成交量: {vol_info} [{status}]")
                
                if volume_increasing:
                    filtered_stocks.append(stock_code)
            
            print(f"After filter 5 (increasing volume): {len(filtered_stocks)} stocks")
            logger.info(f"成交量持续放大筛选: 从{len(stock_codes)}只股票中筛选出{len(filtered_stocks)}只")
            return filtered_stocks
            
        except Exception as e:
            logger.error(f"成交量持续放大筛选过程中出错: {str(e)}")
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
            
            for stock_code in stock_codes:
                # 获取K线数据（需要至少60+10天的数据来计算60日均线和趋势）
                kline_data = self.get_kline_data(stock_code, period='daily', limit=70)
                
                if not kline_data or len(kline_data) < 60:
                    logger.warning(f"股票{stock_code}K线数据不足，无法计算均线")
                    continue
                
                # 计算5日、10日、20日和60日均线
                closes = [bar['close'] for bar in kline_data]
                ma5 = self._calculate_ma(closes, 5)
                ma10 = self._calculate_ma(closes, 10)
                ma20 = self._calculate_ma(closes, 20)
                ma60 = self._calculate_ma(closes, 60)
                
                if not all([ma5, ma10, ma20, ma60]):
                    logger.warning(f"股票{stock_code}均线计算失败")
                    continue
                
                # 判断多头排列：MA5 > MA10 > MA20 > MA60
                ma_alignment = ma5[0] > ma10[0] > ma20[0] > ma60[0]
                
                # 判断60日均线是否向上
                ma60_up = ma60[0] > ma60[5]
                
                # 记录均线信息
                ma_info = f"MA5: {ma5[0]:.2f}, MA10: {ma10[0]:.2f}, MA20: {ma20[0]:.2f}, MA60: {ma60[0]:.2f}"
                status = "符合条件" if ma_alignment and ma60_up else "不符合条件"
                logger.info(f"股票{stock_code} - {ma_info}, 60日均线向上: {ma60_up} [{status}]")
                
                if ma_alignment and ma60_up:
                    filtered_stocks.append(stock_code)
            
            print(f"After filter 6 (moving averages): {len(filtered_stocks)} stocks")
            logger.info(f"均线筛选: 从{len(stock_codes)}只股票中筛选出{len(filtered_stocks)}只")
            return filtered_stocks
            
        except Exception as e:
            logger.error(f"均线筛选过程中出错: {str(e)}")
            return []
    
    def _calculate_ma(self, prices, period):
        """
        计算移动平均线
        
        Parameters:
        -----------
        prices: list
            收盘价列表，按时间倒序排列（最新的在前面）
        period: int
            移动平均线周期
        
        Returns:
        --------
        list
            移动平均线值，与prices保持相同的顺序
        """
        if len(prices) < period:
            return []
            
        ma_values = []
        for i in range(len(prices) - period + 1):
            window = prices[i:i+period]
            ma = sum(window) / period
            ma_values.append(ma)
            
        return ma_values
    
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
            # 获取大盘指数（上证指数）的K线数据
            market_index_code = "sh000001"
            market_kline = self.get_kline_data(market_index_code, period='daily', limit=5)
            
            if not market_kline or len(market_kline) < 3:
                logger.warning("无法获取大盘指数数据，跳过大盘强度筛选")
                return stock_codes  # 如果无法获取大盘数据，保留所有股票
            
            # 计算大盘最近3天的涨跌幅
            market_changes = []
            for i in range(len(market_kline) - 1):
                if i+1 < len(market_kline):
                    today_close = market_kline[i]['close']
                    yesterday_close = market_kline[i+1]['close']
                    change_pct = (today_close - yesterday_close) / yesterday_close * 100
                    market_changes.append(change_pct)
            
            # 判断大盘是否处于上升趋势（至少2天上涨）
            market_up_trend = sum(1 for change in market_changes if change > 0) >= 2
            
            if not market_up_trend:
                logger.warning("大盘不处于上升趋势，跳过大盘强度筛选")
                return stock_codes  # 如果大盘不在上升趋势，保留所有股票
            
            filtered_stocks = []
            
            for stock_code in stock_codes:
                # 获取个股K线数据
                stock_kline = self.get_kline_data(stock_code, period='daily', limit=5)
                
                if not stock_kline or len(stock_kline) < 3:
                    logger.warning(f"股票{stock_code}K线数据不足，无法比较与大盘强度")
                    continue
                
                # 计算个股最近3天的涨跌幅
                stock_changes = []
                for i in range(len(stock_kline) - 1):
                    if i+1 < len(stock_kline):
                        today_close = stock_kline[i]['close']
                        yesterday_close = stock_kline[i+1]['close']
                        change_pct = (today_close - yesterday_close) / yesterday_close * 100
                        stock_changes.append(change_pct)
                
                # 比较个股与大盘的强度（个股涨幅大于大盘涨幅）
                stronger_than_market = True
                for i in range(min(len(stock_changes), len(market_changes))):
                    if stock_changes[i] <= market_changes[i]:
                        stronger_than_market = False
                        break
                
                # 记录比较结果
                stock_changes_str = ", ".join([f"{change:.2f}%" for change in stock_changes])
                market_changes_str = ", ".join([f"{change:.2f}%" for change in market_changes])
                status = "符合条件" if stronger_than_market else "不符合条件"
                logger.info(f"股票{stock_code} - 涨跌幅: {stock_changes_str} vs 大盘: {market_changes_str} [{status}]")
                
                if stronger_than_market:
                    filtered_stocks.append(stock_code)
            
            print(f"After filter 7 (market strength): {len(filtered_stocks)} stocks")
            logger.info(f"大盘强度筛选: 从{len(stock_codes)}只股票中筛选出{len(filtered_stocks)}只")
            print(f"After filter 2 (volume ratio > {min_ratio}): {len(filtered_stocks)} stocks")
            logger.info(f"量比筛选: 从{len(stock_codes)}只股票中筛选出{len(filtered_stocks)}只")
            return filtered_stocks
            
        except Exception as e:
            logger.error(f"量比筛选过程中出错: {str(e)}")
            return []
    
    def _filter_by_turnover_rate_strict(self, stock_codes, min_rate=5.0, max_rate=10.0):
        """
        严格步骤3: 筛选换手率在指定范围内的股票
        
        Parameters:
        -----------
        stock_codes: list
            股票代码列表
        min_rate: float
            最小换手率
        max_rate: float
            最大换手率
        
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
            logger.info(f"===== 换手率详细信息(筛选范围{min_rate}%-{max_rate}%) =====")
            for stock in detailed_info:
                turnover_rate = stock.get('turnover_rate')
                stock_code = stock.get('code', 'Unknown')
                stock_name = stock.get('name', 'Unknown')
                data_source = stock.get('data_source', 'Unknown')
                
                if turnover_rate is None:
                    logger.info(f"股票 {stock_code} ({stock_name}): 换手率为None [数据源: {data_source}]")
                else:
                    status = "符合条件" if min_rate <= turnover_rate <= max_rate else "不符合条件"
                    logger.info(f"股票 {stock_code} ({stock_name}): 换手率={turnover_rate:.2f}% [{status}] [数据源: {data_source}]")
            
            # 严格筛选换手率在min_rate到max_rate之间的股票
            filtered_stocks = []
            for stock in detailed_info:
                turnover_rate = stock.get('turnover_rate')
                if turnover_rate is not None and min_rate <= turnover_rate <= max_rate:
                    filtered_stocks.append(stock['code'])
            
            print(f"After filter 3 (turnover rate {min_rate}%-{max_rate}%): {len(filtered_stocks)} stocks")
            logger.info(f"换手率筛选: 从{len(stock_codes)}只股票中筛选出{len(filtered_stocks)}只")
            
            # 如果筛选结果为空且启用了数据降级，尝试适度放宽条件
            if not filtered_stocks and stock_codes and hasattr(self, 'degradation_enabled') and self.degradation_enabled:
                logger.warning(f"换手率筛选结果为空，尝试适度放宽条件...")
                # 根据降级级别决定放宽程度，但仍保持在合理范围内
                if self.degradation_level == "LOW":
                    new_min_rate, new_max_rate = 4.5, 10.5  # 轻度放宽
                elif self.degradation_level == "MEDIUM":
                    new_min_rate, new_max_rate = 4.0, 11.0  # 中度放宽
                else:  # HIGH
                    new_min_rate, new_max_rate = 3.5, 12.0  # 重度放宽
                
                logger.info(f"放宽换手率范围到{new_min_rate}%-{new_max_rate}%")
                
                # 应用放宽后的条件
                filtered_stocks = []
                for stock in detailed_info:
                    turnover_rate = stock.get('turnover_rate')
                    if turnover_rate is not None and new_min_rate <= turnover_rate <= new_max_rate:
                        filtered_stocks.append(stock['code'])
                        # 记录数据质量信息
                        if not hasattr(self, 'stocks_data_quality'):
                            self.stocks_data_quality = {}
                        if stock['code'] not in self.stocks_data_quality:
                            self.stocks_data_quality[stock['code']] = {}
                        self.stocks_data_quality[stock['code']]['filter'] = '换手率筛选'
                        self.stocks_data_quality[stock['code']]['decision_basis'] = 'FALLBACK'
                        self.stocks_data_quality[stock['code']]['alternative_method'] = f'放宽换手率到{new_min_rate}%-{new_max_rate}%'
                
                print(f"After filter 3 (relaxed turnover rate): {len(filtered_stocks)} stocks")
                logger.info(f"放宽换手率筛选: 从{len(stock_codes)}只股票中筛选出{len(filtered_stocks)}只")
            
            return filtered_stocks
            
        except Exception as e:
            logger.error(f"换手率筛选过程中出错: {str(e)}")
            return []
    
    def _filter_by_market_cap_strict(self, stock_codes, min_cap=50.0, max_cap=200.0):
        """
        严格步骤4: 筛选市值在指定范围内的股票
        
        Parameters:
        -----------
        stock_codes: list
            股票代码列表
        min_cap: float
            最小市值（亿元）
        max_cap: float
            最大市值（亿元）
        
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
            
            # 输出详细市值信息用于诊断
            logger.info(f"===== 市值详细信息(筛选范围{min_cap}-{max_cap}亿) =====")
            for stock in detailed_info:
                market_cap = stock.get('market_cap')
                stock_code = stock.get('code', 'Unknown')
                stock_name = stock.get('name', 'Unknown')
                data_source = stock.get('data_source', 'Unknown')
                
                if market_cap is None:
                    logger.info(f"股票 {stock_code} ({stock_name}): 市值为None [数据源: {data_source}]")
                else:
                    status = "符合条件" if min_cap <= market_cap <= max_cap else "不符合条件"
                    logger.info(f"股票 {stock_code} ({stock_name}): 市值={market_cap:.2f}亿 [{status}] [数据源: {data_source}]")
            
            # 严格筛选市值在min_cap到max_cap之间的股票
            filtered_stocks = []
            for stock in detailed_info:
                market_cap = stock.get('market_cap')
                if market_cap is not None and min_cap <= market_cap <= max_cap:
                    filtered_stocks.append(stock['code'])
            
            print(f"After filter 4 (market cap {min_cap}-{max_cap}亿): {len(filtered_stocks)} stocks")
            logger.info(f"市值筛选: 从{len(stock_codes)}只股票中筛选出{len(filtered_stocks)}只")
            return filtered_stocks
            
        except Exception as e:
            logger.error(f"市值筛选过程中出错: {str(e)}")
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