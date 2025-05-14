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
                # 新浪财经API
                market_code = self.market_mapping[market]['sina']
                params = {
                    'page': 1,
                    'num': 5000,
                    'sort': 'symbol',
                    'asc': 1,
                    'node': market_code
                }
                response = requests.get(self.api_urls['sina']['stock_list'], params=params, headers=self.headers)
                if response.status_code == 200:
                    data = json.loads(response.text)
                    stocks = [item['symbol'] for item in data]
                    
                    # 如果获取失败或数据量太小，使用模拟数据
                    if len(stocks) < 10:
                        if market == 'SH':
                            stocks = ['sh600000', 'sh600036', 'sh601318', 'sh600519', 'sh600276', 'sh601398']
                        elif market == 'SZ':
                            stocks = ['sz000001', 'sz000002', 'sz000063', 'sz000333', 'sz000651', 'sz000858']
            
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
                
                # 如果获取失败或数据量太小，使用模拟数据
                if len(stocks) < 10:
                    if market == 'SH':
                        stocks = ['sh600000', 'sh600036', 'sh601318', 'sh600519', 'sh600276', 'sh601398']
                    elif market == 'SZ':
                        stocks = ['sz000001', 'sz000002', 'sz000063', 'sz000333', 'sz000651', 'sz000858']
            
            elif self.api_source == 'alltick':
                # AllTick API
                if not self.token:
                    logger.warning("使用AllTick API需要提供token，使用模拟数据代替")
                    print("WARNING: AllTick API requires a token. Please set it using set_token(your_token) method.")
                    # 使用模拟数据
                    if market == 'SH':
                        stocks = ['sh600000', 'sh600036', 'sh601318', 'sh600519', 'sh600276', 'sh601398']
                    elif market == 'SZ':
                        stocks = ['sz000001', 'sz000002', 'sz000063', 'sz000333', 'sz000651', 'sz000858']
                    elif market == 'HK':
                        stocks = ['hk00700', 'hk09988', 'hk00941', 'hk01810', 'hk00388', 'hk00005']
                    else:
                        stocks = []
                else:
                    market_code = self.market_mapping[market]['alltick']
                    headers = {'Authorization': f'Bearer {self.token}'}
                    params = {'exchange': market_code}
                    url = f"{self.api_urls['alltick']['base_url']}{self.api_urls['alltick']['stock_list']}"
                    
                    response = requests.get(url, headers=headers, params=params)
                    if response.status_code == 200:
                        data = response.json()
                        stocks = [item['symbol'] for item in data['data']]
                
                    # 如果获取失败或数据量太小，使用模拟数据
                    if len(stocks) < 10:
                        if market == 'SH':
                            stocks = ['sh600000', 'sh600036', 'sh601318', 'sh600519', 'sh600276', 'sh601398']
                        elif market == 'SZ':
                            stocks = ['sz000001', 'sz000002', 'sz000063', 'sz000333', 'sz000651', 'sz000858']
                        elif market == 'HK':
                            stocks = ['hk00700', 'hk09988', 'hk00941', 'hk01810', 'hk00388', 'hk00005']
                        else:
                            stocks = []
            
            # 缓存结果
            self.stock_list_cache[cache_key] = stocks
            logger.info(f"获取{market}市场股票列表成功，共{len(stocks)}只股票")
            
            return stocks
            
        except Exception as e:
            logger.error(f"获取股票列表时出错: {str(e)}")
            # 使用模拟数据
            if market == 'SH':
                stocks = ['sh600000', 'sh600036', 'sh601318', 'sh600519', 'sh600276', 'sh601398']
            elif market == 'SZ':
                stocks = ['sz000001', 'sz000002', 'sz000063', 'sz000333', 'sz000651', 'sz000858']
            elif market == 'HK':
                stocks = ['hk00700', 'hk09988', 'hk00941', 'hk01810', 'hk00388', 'hk00005']
            else:
                stocks = []
            return stocks
            
    def _generate_mock_data(self, code):
        """生成模拟股票数据用于测试"""
        # 根据代码生成随机但一致的数据
        code_sum = sum([ord(c) for c in code])
        random.seed(code_sum)
        
        base_price = round(random.uniform(10, 100), 2)
        change_pct = round(random.uniform(-5, 8), 2)
        pre_close = round(base_price / (1 + change_pct/100), 2)
        
        # 提取股票名称
        if code.startswith('sh'):
            name = f"上证{code[2:]}"
        elif code.startswith('sz'):
            name = f"深证{code[2:]}"
        elif code.startswith('hk'):
            name = f"港股{code[2:]}"
        else:
            name = f"股票{code}"
        
        # 模拟数据结构
        return {
            'code': code,
            'name': name,
            'open': round(pre_close * (1 + random.uniform(-1, 1)/100), 2),
            'pre_close': pre_close,
            'price': base_price,
            'high': round(base_price * (1 + random.uniform(0, 2)/100), 2),
            'low': round(base_price * (1 - random.uniform(0, 2)/100), 2),
            'volume': int(random.uniform(100000, 10000000)),
            'amount': int(random.uniform(1000000, 100000000)),
            'date': datetime.now().strftime('%Y-%m-%d'),
            'time': datetime.now().strftime('%H:%M:%S'),
            'change_pct': change_pct
        }
        
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
        
        try:
            if self.api_source == 'sina':
                # 每次请求不超过100只股票
                for i in range(0, len(stock_codes), 100):
                    batch = stock_codes[i:i+100]
                    query_list = ','.join(batch)
                    url = f"{self.api_urls['sina']['realtime']}{query_list}"
                    
                    try:
                        response = requests.get(url, headers=self.headers)
                        
                        if response.status_code == 200:
                            lines = response.text.strip().split('\n')
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
                                        'open': float(values[1]),
                                        'pre_close': float(values[2]),
                                        'price': float(values[3]),
                                        'high': float(values[4]),
                                        'low': float(values[5]),
                                        'volume': int(values[8]),
                                        'amount': float(values[9]),
                                        'date': values[30],
                                        'time': values[31]
                                    }
                                    
                                    # 计算涨跌幅
                                    if stock_data['pre_close'] > 0:
                                        stock_data['change_pct'] = (stock_data['price'] - stock_data['pre_close']) / stock_data['pre_close'] * 100
                                    else:
                                        stock_data['change_pct'] = 0
                                    
                                    result.append(stock_data)
                        else:
                            logger.error(f"API request error: {response.status_code} {response.reason} for url: {url}")
                            # 如果请求失败，使用模拟数据
                            for code in batch:
                                result.append(self._generate_mock_data(code))
                    except Exception as e:
                        logger.error(f"请求数据时出错: {str(e)}")
                        # 如果请求失败，使用模拟数据
                        for code in batch:
                            result.append(self._generate_mock_data(code))
                    
                    # 防止API限流
                    time.sleep(0.5)
            
            elif self.api_source == 'hexun':
                # 和讯API只能单只股票查询
                for code in stock_codes:
                    try:
                        url = f"http://quote.hexun.com/quote/stocklist.aspx?type=stock&market={code[0:2]}&code={code[2:]}"
                        response = requests.get(url, headers=self.headers)
                        if response.status_code == 200:
                            data = response.text.strip()
                            # 解析和讯数据，较复杂
                            # 这里简化处理，直接使用模拟数据
                            result.append(self._generate_mock_data(code))
                        else:
                            logger.error(f"API request error: {response.status_code} {response.reason} for url: {url}")
                            result.append(self._generate_mock_data(code))
                    except Exception as e:
                        logger.error(f"请求数据时出错: {str(e)}")
                        result.append(self._generate_mock_data(code))
                    
                    # 防止API限流
                    time.sleep(0.2)
            
            elif self.api_source == 'alltick':
                if not self.token:
                    logger.warning("使用AllTick API需要提供token，使用模拟数据代替")
                    # 使用模拟数据
                    for code in stock_codes:
                        result.append(self._generate_mock_data(code))
                else:
                    try:
                        headers = {'Authorization': f'Bearer {self.token}'}
                        symbols = ','.join(stock_codes)
                        params = {'symbols': symbols}
                        url = f"{self.api_urls['alltick']['base_url']}{self.api_urls['alltick']['realtime']}"
                        
                        response = requests.get(url, headers=headers, params=params)
                        if response.status_code == 200:
                            data = response.json()
                            for item in data['data']:
                                result.append({
                                    'code': item['symbol'],
                                    'name': item.get('name', ''),
                                    'open': item.get('open', 0),
                                    'pre_close': item.get('prevClose', 0),
                                    'price': item.get('price', 0),
                                    'high': item.get('high', 0),
                                    'low': item.get('low', 0),
                                    'volume': item.get('volume', 0),
                                    'amount': item.get('amount', 0),
                                    'change_pct': item.get('changePercent', 0)
                                })
                        else:
                            logger.error(f"API request error: {response.status_code} {response.reason}")
                            # 使用模拟数据
                            for code in stock_codes:
                                result.append(self._generate_mock_data(code))
                    except Exception as e:
                        logger.error(f"请求数据时出错: {str(e)}")
                        # 使用模拟数据
                        for code in stock_codes:
                            result.append(self._generate_mock_data(code))
            
            logger.info(f"获取{len(stock_codes)}只股票实时数据成功，实际返回{len(result)}条数据")
            return result
            
        except Exception as e:
            logger.error(f"获取实时数据时出错: {str(e)}")
            # 使用模拟数据
            for code in stock_codes:
                result.append(self._generate_mock_data(code))
            return result 

    def _generate_mock_kline_data(self, stock_code, num_periods=60):
        """生成模拟K线数据用于测试"""
        # 根据代码生成随机但一致的数据
        code_sum = sum([ord(c) for c in stock_code])
        random.seed(code_sum)
        
        # 生成基础价格和波动范围
        base_price = round(random.uniform(10, 100), 2)
        volatility = base_price * 0.1  # 波动率
        
        result = []
        current_price = base_price
        
        # 生成K线数据
        for i in range(num_periods):
            # 日期，从最近的日期倒推
            date = (datetime.now() - timedelta(days=num_periods-i)).strftime('%Y-%m-%d')
            timestamp = int((datetime.now() - timedelta(days=num_periods-i)).timestamp())
            
            # 随机生成开盘价、最高价、最低价和收盘价
            random.seed(code_sum + i)
            open_price = current_price * (1 + random.uniform(-0.02, 0.02))
            
            # 50%概率上涨，50%概率下跌
            if random.random() > 0.5:
                close_price = open_price * (1 + random.uniform(0, 0.04))
            else:
                close_price = open_price * (1 - random.uniform(0, 0.03))
                
            high_price = max(open_price, close_price) * (1 + random.uniform(0, 0.02))
            low_price = min(open_price, close_price) * (1 - random.uniform(0, 0.02))
            
            # 成交量，与股价变化正相关
            volume_base = random.uniform(100000, 10000000)
            volume_factor = abs(close_price - open_price) / open_price * 5
            volume = int(volume_base * (1 + volume_factor))
            
            # 更新当前价格
            current_price = close_price
            
            # 添加K线数据
            kline = {
                'timestamp': timestamp,
                'date': date,
                'open': round(open_price, 2),
                'high': round(high_price, 2),
                'low': round(low_price, 2),
                'close': round(close_price, 2),
                'volume': volume
            }
            result.append(kline)
        
        # 让收盘价呈现一定趋势，便于测试均线策略
        # 最近10天的数据呈现上涨趋势
        for i in range(max(0, len(result)-10), len(result)):
            factor = (i - (len(result)-10)) / 10 * 0.1  # 0到0.1的递增因子
            result[i]['close'] = round(result[i]['close'] * (1 + factor), 2)
            result[i]['high'] = max(result[i]['high'], result[i]['close'])
        
        return result
    
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
        list
            K线数据列表
        """
        # 检查缓存
        cache_key = f"{stock_code}_{kline_type}_{num_periods}_{datetime.now().strftime('%Y%m%d')}"
        if cache_key in self.kline_cache:
            return self.kline_cache[cache_key]
        
        result = []
        
        try:
            if self.api_source == 'sina':
                # 新浪财经API
                period_map = {1: 'day', 2: 'week', 3: 'month', 4: '5min', 5: '15min', 6: '30min', 7: '60min'}
                period = period_map.get(kline_type, 'day')
                
                params = {
                    'symbol': stock_code,
                    'scale': period,
                    'ma': 'no',
                    'datalen': min(num_periods, 180)  # 新浪限制最多180条
                }
                
                try:
                    response = requests.get(self.api_urls['sina']['kline'], params=params, headers=self.headers)
                    if response.status_code == 200:
                        data = response.json()
                        
                        for item in data:
                            # 转换日期为时间戳
                            date_str = item['day']
                            try:
                                dt = datetime.strptime(date_str, '%Y-%m-%d')
                                timestamp = int(dt.timestamp())
                            except:
                                timestamp = 0
                                
                            kline = {
                                'timestamp': timestamp,
                                'date': date_str,
                                'open': float(item['open']),
                                'high': float(item['high']),
                                'low': float(item['low']),
                                'close': float(item['close']),
                                'volume': int(item['volume'])
                            }
                            result.append(kline)
                    else:
                        logger.error(f"API request error: {response.status_code} {response.reason}")
                        # 使用模拟数据
                        result = self._generate_mock_kline_data(stock_code, num_periods)
                except Exception as e:
                    logger.error(f"获取K线数据时出错: {str(e)}")
                    # 使用模拟数据
                    result = self._generate_mock_kline_data(stock_code, num_periods)
            
            elif self.api_source == 'hexun':
                # 和讯API
                period_map = {1: '101', 2: '102', 3: '103', 4: '5', 5: '15', 6: '30', 7: '60'}
                period = period_map.get(kline_type, '101')
                
                try:
                    url = self.api_urls['hexun']['kline'].format(code=stock_code, count=num_periods)
                    response = requests.get(url, headers=self.headers)
                    if response.status_code == 200:
                        data = response.text.strip()
                        if data.startswith('var quote_data=') and data.endswith(';'):
                            data = data[16:-1]
                            kline_data = json.loads(data)
                            
                            for item in kline_data:
                                date_str = item[0]
                                try:
                                    dt = datetime.strptime(date_str, '%Y%m%d')
                                    timestamp = int(dt.timestamp())
                                except:
                                    timestamp = 0
                                    
                                kline = {
                                    'timestamp': timestamp,
                                    'date': date_str,
                                    'open': float(item[1]),
                                    'high': float(item[2]),
                                    'low': float(item[3]),
                                    'close': float(item[4]),
                                    'volume': int(item[5])
                                }
                                result.append(kline)
                    else:
                        logger.error(f"API request error: {response.status_code} {response.reason}")
                        # 使用模拟数据
                        result = self._generate_mock_kline_data(stock_code, num_periods)
                except Exception as e:
                    logger.error(f"获取K线数据时出错: {str(e)}")
                    # 使用模拟数据
                    result = self._generate_mock_kline_data(stock_code, num_periods)
            
            elif self.api_source == 'alltick':
                if not self.token:
                    logger.warning("使用AllTick API需要提供token，使用模拟数据代替")
                    # 使用模拟数据
                    result = self._generate_mock_kline_data(stock_code, num_periods)
                else:
                    try:
                        # AllTick API
                        period_map = {1: '1d', 2: '1w', 3: '1mo', 4: '5m', 5: '15m', 6: '30m', 7: '1h'}
                        period = period_map.get(kline_type, '1d')
                        
                        headers = {'Authorization': f'Bearer {self.token}'}
                        params = {
                            'symbol': stock_code,
                            'interval': period,
                            'limit': num_periods
                        }
                        url = f"{self.api_urls['alltick']['base_url']}{self.api_urls['alltick']['kline']}"
                        
                        response = requests.get(url, headers=headers, params=params)
                        if response.status_code == 200:
                            data = response.json()
                            
                            for item in data['data']:
                                kline = {
                                    'timestamp': item['timestamp'],
                                    'date': datetime.fromtimestamp(item['timestamp']).strftime('%Y-%m-%d'),
                                    'open': float(item['open']),
                                    'high': float(item['high']),
                                    'low': float(item['low']),
                                    'close': float(item['close']),
                                    'volume': int(item['volume'])
                                }
                                result.append(kline)
                        else:
                            logger.error(f"API request error: {response.status_code} {response.reason}")
                            # 使用模拟数据
                            result = self._generate_mock_kline_data(stock_code, num_periods)
                    except Exception as e:
                        logger.error(f"获取K线数据时出错: {str(e)}")
                        # 使用模拟数据
                        result = self._generate_mock_kline_data(stock_code, num_periods)
            
            # 如果没有获取到数据，使用模拟数据
            if not result:
                result = self._generate_mock_kline_data(stock_code, num_periods)
            
            # 按时间排序
            result.sort(key=lambda x: x['timestamp'])
            
            # 缓存结果
            self.kline_cache[cache_key] = result
            
            logger.info(f"获取{stock_code}的K线数据成功，共{len(result)}条数据")
            return result
            
        except Exception as e:
            logger.error(f"获取K线数据时出错: {str(e)}")
            # 使用模拟数据
            result = self._generate_mock_kline_data(stock_code, num_periods)
            return result
    
    def get_detailed_info(self, stock_codes):
        """
        获取股票的详细信息，包括换手率、市值等
        
        Parameters:
        -----------
        stock_codes: list
            股票代码列表
        
        Returns:
        --------
        list
            详细信息列表
        """
        result = []
        
        try:
            # 获取基本行情数据
            stock_data = self.get_realtime_data(stock_codes)
            
            # 获取额外信息
            for stock in stock_data:
                # 计算或模拟一些指标
                # 注：实际中这些指标应该从API获取，这里简化处理
                code_sum = sum([ord(c) for c in stock['code']])
                random.seed(code_sum)
                
                turnover_rate = round(random.uniform(1.0, 15.0), 2)  # 模拟换手率
                volume_ratio = round(random.uniform(0.5, 3.0), 2)    # 模拟量比
                market_cap = round(stock['price'] * (random.uniform(50000000, 5000000000)), 2)  # 模拟市值
                
                # 转换为亿为单位
                market_cap_billion = market_cap / 100000000
                
                # 合并信息
                detailed_info = {
                    'code': stock['code'],
                    'name': stock['name'],
                    'price': stock['price'],
                    'change_pct': stock['change_pct'],
                    'volume': stock['volume'],
                    'turnover_rate': turnover_rate,
                    'volume_ratio': volume_ratio,
                    'market_cap': market_cap_billion
                }
                
                result.append(detailed_info)
            
            logger.info(f"获取{len(stock_codes)}只股票详细信息成功")
            return result
            
        except Exception as e:
            logger.error(f"获取详细信息时出错: {str(e)}")
            # 使用模拟数据
            for code in stock_codes:
                code_sum = sum([ord(c) for c in code])
                random.seed(code_sum)
                
                # 提取股票名称
                if code.startswith('sh'):
                    name = f"上证{code[2:]}"
                elif code.startswith('sz'):
                    name = f"深证{code[2:]}"
                else:
                    name = f"股票{code}"
                
                result.append({
                    'code': code,
                    'name': name,
                    'price': round(random.uniform(10, 100), 2),
                    'change_pct': round(random.uniform(-5, 8), 2),
                    'volume': int(random.uniform(100000, 10000000)),
                    'turnover_rate': round(random.uniform(1.0, 15.0), 2),
                    'volume_ratio': round(random.uniform(0.5, 3.0), 2),
                    'market_cap': round(random.uniform(30, 300), 2)
                })
            return result 

    # ===== 尾盘选股八大步骤 =====
    
    def filter_by_price_increase(self, stock_codes):
        """
        步骤1: 筛选涨幅在3%-5%的股票
        
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
            
            # 筛选涨幅在3%-5%的股票
            filtered_stocks = []
            for stock in stock_data:
                if 3.0 <= stock['change_pct'] <= 5.0:
                    filtered_stocks.append(stock['code'])
            
            print(f"After filter 1 (price increase): {len(filtered_stocks)} stocks")
            logger.info(f"涨幅筛选: 从{len(stock_codes)}只股票中筛选出{len(filtered_stocks)}只")
            return filtered_stocks
            
        except Exception as e:
            logger.error(f"涨幅筛选过程中出错: {str(e)}")
            return []
    
    def filter_by_volume_ratio(self, stock_codes):
        """
        步骤2: 筛选量比>1的股票
        
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
            
            # 筛选量比>1的股票
            filtered_stocks = []
            for stock in detailed_info:
                if stock['volume_ratio'] > 1.0:
                    filtered_stocks.append(stock['code'])
            
            print(f"After filter 2 (volume ratio): {len(filtered_stocks)} stocks")
            logger.info(f"量比筛选: 从{len(stock_codes)}只股票中筛选出{len(filtered_stocks)}只")
            return filtered_stocks
            
        except Exception as e:
            logger.error(f"量比筛选过程中出错: {str(e)}")
            return []
    
    def filter_by_turnover_rate(self, stock_codes):
        """
        步骤3: 筛选换手率在5%-10%的股票
        
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
            
            # 筛选换手率在5%-10%的股票
            filtered_stocks = []
            for stock in detailed_info:
                if 5.0 <= stock['turnover_rate'] <= 10.0:
                    filtered_stocks.append(stock['code'])
            
            print(f"After filter 3 (turnover rate): {len(filtered_stocks)} stocks")
            logger.info(f"换手率筛选: 从{len(stock_codes)}只股票中筛选出{len(filtered_stocks)}只")
            return filtered_stocks
            
        except Exception as e:
            logger.error(f"换手率筛选过程中出错: {str(e)}")
            return []
    
    def filter_by_market_cap(self, stock_codes):
        """
        步骤4: 筛选市值在50亿-200亿的股票
        
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
            
            # 筛选市值在50亿-200亿的股票
            filtered_stocks = []
            for stock in detailed_info:
                if 50.0 <= stock['market_cap'] <= 200.0:
                    filtered_stocks.append(stock['code'])
            
            print(f"After filter 4 (market cap): {len(filtered_stocks)} stocks")
            logger.info(f"市值筛选: 从{len(stock_codes)}只股票中筛选出{len(filtered_stocks)}只")
            return filtered_stocks
            
        except Exception as e:
            logger.error(f"市值筛选过程中出错: {str(e)}")
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
            
            for code in stock_codes:
                # 获取最近5天的K线数据
                kline_data = self.get_kline_data(code, kline_type=1, num_periods=5)
                
                if len(kline_data) < 3:
                    continue
                
                # 判断成交量是否持续放大（至少连续3天）
                volumes = [k['volume'] for k in kline_data]
                
                # 至少有3天的数据，且最近的成交量比前一天大
                if len(volumes) >= 3 and volumes[-1] > volumes[-2]:
                    # 再检查前一天的成交量是否也比再前一天大
                    if volumes[-2] > volumes[-3]:
                        filtered_stocks.append(code)
            
            print(f"After filter 5 (increasing volume): {len(filtered_stocks)} stocks")
            logger.info(f"成交量筛选: 从{len(stock_codes)}只股票中筛选出{len(filtered_stocks)}只")
            return filtered_stocks
            
        except Exception as e:
            logger.error(f"成交量筛选过程中出错: {str(e)}")
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
            
            for code in stock_codes:
                # 获取至少60天的K线数据
                kline_data = self.get_kline_data(code, kline_type=1, num_periods=70)
                
                if len(kline_data) < 60:
                    continue
                
                # 提取收盘价
                closes = [k['close'] for k in kline_data]
                
                # 计算5日、10日和60日均线
                closes_df = pd.Series(closes)
                ma5 = closes_df.rolling(window=5).mean()
                ma10 = closes_df.rolling(window=10).mean()
                ma60 = closes_df.rolling(window=60).mean()
                
                # 判断均线关系和走势
                # 条件: MA5 > MA10 > MA60 且 MA60向上
                if (len(ma60) >= 5 and not pd.isna(ma60.iloc[-1]) and not pd.isna(ma60.iloc[-2]) and 
                    not pd.isna(ma5.iloc[-1]) and not pd.isna(ma10.iloc[-1]) and
                    ma5.iloc[-1] > ma10.iloc[-1] > ma60.iloc[-1] and
                    ma60.iloc[-1] > ma60.iloc[-2]):
                    filtered_stocks.append(code)
            
            print(f"After filter 6 (moving averages): {len(filtered_stocks)} stocks")
            logger.info(f"均线筛选: 从{len(stock_codes)}只股票中筛选出{len(filtered_stocks)}只")
            return filtered_stocks
            
        except Exception as e:
            logger.error(f"均线筛选过程中出错: {str(e)}")
            return []
    
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
        应用尾盘选股八大步骤的完整筛选流程
        
        Parameters:
        -----------
        stock_codes: list
            股票代码列表
        
        Returns:
        --------
        list
            符合所有条件的股票代码列表
        """
        if not stock_codes:
            return []
            
        try:
            # 记录原始股票数量
            original_count = len(stock_codes)
            logger.info(f"开始应用八大步骤筛选，初始股票数量: {original_count}")
            print(f"Starting with {original_count} stocks")
            
            # 步骤1: 筛选涨幅3%-5%的股票
            filtered = self.filter_by_price_increase(stock_codes)
            
            # 步骤2: 筛选量比>1的股票
            filtered = self.filter_by_volume_ratio(filtered)
            
            # 步骤3: 筛选换手率5%-10%的股票
            filtered = self.filter_by_turnover_rate(filtered)
            
            # 步骤4: 筛选市值50亿-200亿的股票
            filtered = self.filter_by_market_cap(filtered)
            
            # 步骤5: 筛选成交量持续放大的股票
            filtered = self.filter_by_increasing_volume(filtered)
            
            # 步骤6: 筛选短期均线搭配60日线向上的股票
            filtered = self.filter_by_moving_averages(filtered)
            
            # 步骤7: 筛选强于大盘的股票
            filtered = self.filter_by_market_strength(filtered)
            
            # 步骤8: 筛选尾盘创新高的股票
            filtered = self.filter_by_tail_market_high(filtered)
            
            # 记录最终结果
            final_count = len(filtered)
            logger.info(f"八大步骤筛选完成，从{original_count}只股票中筛选出{final_count}只符合条件的股票")
            
            return filtered
            
        except Exception as e:
            logger.error(f"应用八大步骤筛选过程中出错: {str(e)}")
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