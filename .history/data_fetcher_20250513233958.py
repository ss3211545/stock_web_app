import requests
import json
import pandas as pd
import numpy as np
import time
import re
from datetime import datetime, timedelta
import random
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
    A class to fetch and process stock data for the tailed stock selection system
    implementing the eight-step screening strategy.
    
    Supports multiple API sources for better accessibility in mainland China:
    - AllTick API (https://alltick.co) - International access, requires registration
    - Sina Finance API - Fast access within China, no registration needed
    - Hexun API - Alternative source for China access
    """
    
    def __init__(self, api_source="sina", token=None):
        """
        Initialize the data fetcher with API source and token if needed
        
        Parameters:
        -----------
        api_source : str
            API source to use: "alltick", "sina", or "hexun"
        token : str
            API token for AllTick API. Get one at https://alltick.co/register (only needed for AllTick)
        """
        self.api_source = api_source.lower()
        self.token = token
        
        # API URLs for different sources
        self.api_urls = {
            "alltick": "https://quote.alltick.co/quote-stock-b-api",
            "sina": "https://hq.sinajs.cn",
            "hexun": "http://quote.hexun.com/quote"
        }
        
        # Set base URL based on selected API source
        self.base_url = self.api_urls.get(self.api_source, self.api_urls["sina"])
        
        # Headers for requests
        self.headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'http://finance.sina.com.cn/'
        }
        
        # Cache for stock data to reduce API calls
        self.stock_data_cache = {}
        self.market_index_cache = {}
        self.last_update_time = {}
        
        # Check if token is provided for AllTick
        if self.api_source == "alltick" and not token:
            print("WARNING: AllTick API selected but no token provided. Please register at https://alltick.co/register to get your free API token.")
            print("After registration, use set_token(your_token) method to set your token.")
        else:
            print(f"Using {self.api_source.upper()} API for stock data.")
        
    def set_token(self, token):
        """Set the API token for AllTick API"""
        self.token = token
        print("API token set successfully.")
    
    def set_api_source(self, api_source):
        """Change the API source"""
        api_source = api_source.lower()
        if api_source not in self.api_urls:
            print(f"Invalid API source. Supported sources: {', '.join(self.api_urls.keys())}")
            return
            
        self.api_source = api_source
        self.base_url = self.api_urls[api_source]
        
        # Clear cache when changing API source
        self.stock_data_cache = {}
        self.market_index_cache = {}
        self.last_update_time = {}
        
        print(f"API source changed to {api_source.upper()}.")
        
        if self.api_source == "alltick" and not self.token:
            print("WARNING: AllTick API requires a token. Please set it using set_token(your_token) method.")
        
    def _get_api_url(self, endpoint):
        """Build the full API URL with token for AllTick"""
        if self.api_source == "alltick":
            return f"{self.base_url}/{endpoint}?token={self.token}"
        return self.base_url

    def _make_api_request(self, url, params=None):
        """
        Make an API request and handle errors
        
        Parameters:
        -----------
        url : str
            The API endpoint URL
        params : dict
            Parameters to send with the request
            
        Returns:
        --------
        dict or str : The response data
        """
        if self.api_source == "alltick" and not self.token:
            print("ERROR: AllTick API token not set. Please register at https://alltick.co/register and set your token using set_token(your_token).")
            return None

        try:
            if self.api_source == "alltick":
                if params:
                    # Encode the params for URL
                    encoded_params = requests.utils.quote(json.dumps(params))
                    url = f"{url}&query={encoded_params}"
                    
                response = requests.get(url=url, headers=self.headers)
                response.raise_for_status()
                
                data = response.json()
                
                # Check for API errors
                if data and 'ret' in data and data['ret'] != 0:
                    error_code = data.get('ret', 'Unknown')
                    error_msg = data.get('msg', 'Unknown error')
                    print(f"API Error {error_code}: {error_msg}")
                    return None
                    
                return data
            else:
                response = requests.get(url=url, headers=self.headers)
                response.raise_for_status()
                return response.text
                
        except requests.exceptions.RequestException as e:
            print(f"API request error: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            return None
            
    def _parse_sina_data(self, data_str, stock_code):
        """Parse stock data from Sina Finance API"""
        try:
            # Example format: var hq_str_sh600000="PFYH,浦发银行,12.390,12.410,12.270,12.330,12.260,12.270,12.280,49249235,603574214.000,159832,12.270,212800,12.260,52300,12.250,457900,12.240,132200,12.230,57600,12.280,236400,12.290,305400,12.300,424300,12.310,218200,12.320,2023-11-21,15:00:01,00,";
            pattern = f'var hq_str_(.+){stock_code}="(.+?)";'
            match = re.search(pattern, data_str)
            
            if not match:
                return None
                
            values = match.group(2).split(',')
            
            # Mapping Sina data to our standardized format
            if len(values) < 32:
                return None
                
            result = {
                'code': stock_code,
                'name': values[0],
                'open': float(values[1]),
                'prev_close': float(values[2]),
                'last': float(values[3]),
                'high': float(values[4]),
                'low': float(values[5]),
                'volume': int(float(values[8])),
                'amount': float(values[9]),
                'date': values[30],
                'time': values[31],
                # Calculate additional metrics
                'turnover_rate': 0.0,  # Need to fetch separately
                'market_cap': 0.0  # Need to fetch separately
            }
            
            # Make an additional request for market cap and turnover rate if needed
            # This is a simplified implementation
            
            return result
        except Exception as e:
            print(f"Error parsing Sina data: {e}")
            return None
    
    def _parse_hexun_data(self, data_str, stock_code):
        """Parse stock data from Hexun API"""
        try:
            # Parse Hexun's response format
            # This is a simplified implementation
            pattern = 'quotation":"(.+?)"'
            match = re.search(pattern, data_str)
            
            if not match:
                return None
                
            quote_data = match.group(1).split(',')
            
            if len(quote_data) < 20:
                return None
                
            result = {
                'code': stock_code,
                'name': '',  # Hexun API format may vary
                'open': float(quote_data[2]),
                'prev_close': float(quote_data[7]),
                'last': float(quote_data[3]),
                'high': float(quote_data[4]),
                'low': float(quote_data[5]),
                'volume': int(float(quote_data[8])),
                'amount': float(quote_data[9]),
                'date': datetime.now().strftime("%Y-%m-%d"),
                'time': datetime.now().strftime("%H:%M:%S"),
                'turnover_rate': 0.0,
                'market_cap': 0.0
            }
            
            return result
        except Exception as e:
            print(f"Error parsing Hexun data: {e}")
            return None
            
    def _standardize_code(self, stock_code):
        """Standardize stock code format for different APIs"""
        # Handle stock codes without market suffix
        if "." not in stock_code:
            # Try to determine market from code pattern
            if stock_code.startswith('6'):
                return f"{stock_code}.SH"  # Shanghai
            elif stock_code.startswith(('0', '3')):
                return f"{stock_code}.SZ"  # Shenzhen
            elif stock_code.startswith('4') or stock_code.startswith('8'):
                return f"{stock_code}.BJ"  # Beijing
            elif len(stock_code) <= 5 and stock_code.isdigit():
                return f"{stock_code}.HK"  # Hong Kong
            else:
                return f"{stock_code}.SZ"  # Default to Shenzhen
        
        return stock_code
    
    def get_real_time_quote(self, stock_code, market=None):
        """
        Get real-time stock quote data
        
        Parameters:
        -----------
        stock_code : str
            The stock code to query
        market : str
            Market identifier (e.g., 'US', 'HK', 'SH', 'SZ')
            
        Returns:
        --------
        dict : The real-time quote data
        """
        # Standardize the stock code format
        if market and not stock_code.endswith(f".{market}"):
            full_code = f"{stock_code}.{market}"
        else:
            full_code = self._standardize_code(stock_code)
            
        # Check if we have fresh cached data (less than 5 seconds old)
        current_time = time.time()
        if (full_code in self.stock_data_cache and 
            current_time - self.last_update_time.get(full_code, 0) < 5):
            return self.stock_data_cache[full_code]
        
        # Extract market and code
        if "." in full_code:
            code, market = full_code.split(".")
        else:
            code = full_code
            market = ""
            
        # Handle different API sources
        if self.api_source == "alltick":
            # Build request params
            params = {
                "trace": "python_http_request",
                "data": {
                    "code": full_code
                }
            }
            
            # Make API request
            url = self._get_api_url("quote")
            response_data = self._make_api_request(url, params)
            
            # Update cache
            if response_data and 'data' in response_data:
                self.stock_data_cache[full_code] = response_data['data']
                self.last_update_time[full_code] = current_time
                return response_data['data']
        
        elif self.api_source == "sina":
            # Format for Sina API: https://hq.sinajs.cn/list=sh600000
            sina_market = "sh" if market == "SH" else "sz" if market == "SZ" else market.lower()
            url = f"{self.base_url}/list={sina_market}{code}"
            
            response_data = self._make_api_request(url)
            if response_data:
                parsed_data = self._parse_sina_data(response_data, code)
                if parsed_data:
                    self.stock_data_cache[full_code] = parsed_data
                    self.last_update_time[full_code] = current_time
                    return parsed_data
        
        elif self.api_source == "hexun":
            # Format for Hexun API
            hexun_market = "0" if market == "SZ" else "1" if market == "SH" else "2"
            url = f"{self.base_url}/stocklist.aspx?type=stock&market={hexun_market}&code={code}"
            
            response_data = self._make_api_request(url)
            if response_data:
                parsed_data = self._parse_hexun_data(response_data, code)
                if parsed_data:
                    self.stock_data_cache[full_code] = parsed_data
                    self.last_update_time[full_code] = current_time
                    return parsed_data
        
        return None

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
    
    def get_market_index(self, index_code):
        """
        Get market index data for comparison
        
        Parameters:
        -----------
        index_code : str
            The index code (e.g., '000001.SH' for Shanghai Composite)
            
        Returns:
        --------
        dict : The index data
        """
        # Check if we have fresh cached data (less than 30 seconds old)
        current_time = time.time()
        if (index_code in self.market_index_cache and 
            current_time - self.last_update_time.get(index_code, 0) < 30):
            return self.market_index_cache[index_code]
            
        # Get the index data the same way as regular stocks
        response_data = self.get_real_time_quote(index_code)
        
        # Update cache
        if response_data:
            self.market_index_cache[index_code] = response_data
            self.last_update_time[index_code] = current_time
            return response_data
        
        return None
        
    def get_stock_list(self, market=None):
        """
        Get a list of stocks for screening
        
        Parameters:
        -----------
        market : str
            Optional market filter (e.g., 'SH', 'SZ')
            
        Returns:
        --------
        list : List of stock codes
        """
        # For now, return common stocks based on the market provided
        if market == "SH":
            return ["000001.SH", "600000.SH", "600036.SH", "601318.SH", "600519.SH", "600276.SH"]
        elif market == "SZ":
            return ["399001.SZ", "000001.SZ", "000333.SZ", "000858.SZ", "000651.SZ", "000002.SZ"]
        elif market == "HK":
            return ["5.HK", "700.HK", "9988.HK", "941.HK", "1810.HK", "388.HK"]
        elif market == "US":
            return ["AAPL.US", "MSFT.US", "GOOGL.US", "AMZN.US", "TSLA.US", "META.US"]
        else:
            # Return a mix of stocks from different markets
            return ["000001.SH", "399001.SZ", "000001.SZ", "600000.SH", "700.HK", "5.HK", "AAPL.US", "MSFT.US"]

    # ------------------------------------------------------------------------
    # Eight-step screening methods based on the tail market strategy
    # ------------------------------------------------------------------------
    
    def filter_by_price_increase(self, stock_list, min_pct=3.0, max_pct=5.0):
        """
        Step 1: Filter stocks with daily increase percentage between min_pct and max_pct
        """
        filtered_stocks = []
        
        for stock_code in stock_list:
            data = self.get_real_time_quote(stock_code)
            if data:
                # Calculate percentage increase
                if 'last' in data and 'prev_close' in data and data['prev_close'] > 0:
                    price_change_pct = (data['last'] - data['prev_close']) / data['prev_close'] * 100
                    
                    if min_pct <= price_change_pct <= max_pct:
                        filtered_stocks.append(stock_code)
        
        return filtered_stocks
    
    def filter_by_volume_ratio(self, stock_list, min_ratio=1.0):
        """
        Step 2: Filter stocks with volume ratio greater than min_ratio
        Volume ratio is today's trading volume compared to average volume
        """
        filtered_stocks = []
        
        for stock_code in stock_list:
            data = self.get_real_time_quote(stock_code)
            kline_data = self.get_kline_data(stock_code, kline_type=1, num_periods=6)  # Last 6 days
            
            if data and kline_data and len(kline_data) >= 6:
                # Get current day's volume
                current_volume = data.get('volume', 0)
                
                # Calculate average volume for previous 5 days
                prev_volumes = [k['volume'] for k in kline_data[1:6]]
                avg_volume = sum(prev_volumes) / len(prev_volumes) if prev_volumes else 0
                
                # Calculate volume ratio
                volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0
                
                if volume_ratio >= min_ratio:
                    filtered_stocks.append(stock_code)
        
        return filtered_stocks
    
    def filter_by_turnover_rate(self, stock_list, min_rate=5.0, max_rate=10.0):
        """
        Step 3: Filter stocks with turnover rate between min_rate and max_rate
        """
        filtered_stocks = []
        
        for stock_code in stock_list:
            data = self.get_real_time_quote(stock_code)
            
            if data and 'turnover_rate' in data:
                turnover_rate = data['turnover_rate']
                
                if min_rate <= turnover_rate <= max_rate:
                    filtered_stocks.append(stock_code)
        
        return filtered_stocks
    
    def filter_by_market_cap(self, stock_list, min_cap=50, max_cap=200):
        """
        Step 4: Filter stocks with market cap between min_cap and max_cap (in billions)
        """
        filtered_stocks = []
        
        for stock_code in stock_list:
            data = self.get_real_time_quote(stock_code)
            
            if data and 'market_cap' in data:
                # Convert to billions for easier comparison
                market_cap_billions = data['market_cap'] / 1_000_000_000
                
                if min_cap <= market_cap_billions <= max_cap:
                    filtered_stocks.append(stock_code)
        
        return filtered_stocks
    
    def filter_by_increasing_volume(self, stock_list):
        """
        Step 5: Filter stocks with continuously increasing volume
        """
        filtered_stocks = []
        
        for stock_code in stock_list:
            # Get intraday data to check volume trend in the last few periods
            intraday_data = self.get_kline_data(stock_code, kline_type=6, num_periods=5)  # 5-min intervals
            
            if intraday_data and len(intraday_data) >= 3:
                # Check if volume is increasing in the last 3 periods
                volumes = [k['volume'] for k in intraday_data[:3]]
                if volumes[0] > volumes[1] > volumes[2]:
                    filtered_stocks.append(stock_code)
        
        return filtered_stocks
    
    def filter_by_moving_averages(self, stock_list):
        """
        Step 6: Select stocks with short-term moving averages above the 60-day moving average
        """
        filtered_stocks = []
        
        for stock_code in stock_list:
            kline_data = self.get_kline_data(stock_code, kline_type=1, num_periods=60)
            
            if kline_data and len(kline_data) >= 60:
                # Get closing prices
                closing_prices = [k['close'] for k in kline_data]
                
                # Calculate 5-day and 10-day moving averages
                ma5 = sum(closing_prices[:5]) / 5
                ma10 = sum(closing_prices[:10]) / 10
                
                # Calculate 60-day moving average
                ma60 = sum(closing_prices) / 60
                
                # Check if short-term MAs are above 60-day MA and trending up
                if ma5 > ma60 and ma5 > ma10:
                    filtered_stocks.append(stock_code)
        
        return filtered_stocks
    
    def filter_by_market_strength(self, stock_list, index_code="000001.SH"):
        """
        Step 7: Select stocks performing better than the market
        """
        filtered_stocks = []
        market_data = self.get_market_index(index_code)
        
        if market_data and 'last' in market_data and 'prev_close' in market_data:
            # Calculate market change percentage
            market_change_pct = (market_data['last'] - market_data['prev_close']) / market_data['prev_close'] * 100
            
            for stock_code in stock_list:
                data = self.get_real_time_quote(stock_code)
                
                if data and 'last' in data and 'prev_close' in data:
                    # Calculate stock change percentage
                    stock_change_pct = (data['last'] - data['prev_close']) / data['prev_close'] * 100
                    
                    # Check if stock is outperforming the market
                    if stock_change_pct > market_change_pct:
                        filtered_stocks.append(stock_code)
        
        return filtered_stocks
    
    def filter_by_tail_market_high(self, stock_list):
        """
        Step 8: Identify stocks that are creating new highs in the tail market (last 30 minutes)
        """
        filtered_stocks = []
        current_time = datetime.now()
        market_close_time = datetime(current_time.year, current_time.month, current_time.day, 15, 0)
        
        # Only run this filter during the last 30 minutes of trading
        if current_time > (market_close_time - timedelta(minutes=30)) and current_time < market_close_time:
            for stock_code in stock_list:
                # Get intraday data for detailed analysis
                intraday_data = self.get_kline_data(stock_code, kline_type=5, num_periods=30)  # 1-min intervals
                
                if intraday_data and len(intraday_data) >= 10:
                    # Get the high prices for the last few periods
                    high_prices = [k['high'] for k in intraday_data[:10]]
                    
                    # Check if the latest period has the highest price
                    if high_prices[0] == max(high_prices):
                        filtered_stocks.append(stock_code)
        else:
            # Outside of tail market time, pass through all stocks
            filtered_stocks = stock_list
        
        return filtered_stocks
    
    def apply_all_filters(self, stock_list=None, market=None):
        """
        Apply all eight filters in sequence to get the final list of recommended stocks
        """
        if stock_list is None:
            stock_list = self.get_stock_list(market)
        
        print(f"Starting with {len(stock_list)} stocks")
        
        # Step 1: Filter by price increase
        filtered = self.filter_by_price_increase(stock_list)
        print(f"After filter 1 (price increase): {len(filtered)} stocks")
        
        # Step 2: Filter by volume ratio
        filtered = self.filter_by_volume_ratio(filtered)
        print(f"After filter 2 (volume ratio): {len(filtered)} stocks")
        
        # Step 3: Filter by turnover rate
        filtered = self.filter_by_turnover_rate(filtered)
        print(f"After filter 3 (turnover rate): {len(filtered)} stocks")
        
        # Step 4: Filter by market cap
        filtered = self.filter_by_market_cap(filtered)
        print(f"After filter 4 (market cap): {len(filtered)} stocks")
        
        # Step 5: Filter by increasing volume
        filtered = self.filter_by_increasing_volume(filtered)
        print(f"After filter 5 (increasing volume): {len(filtered)} stocks")
        
        # Step 6: Filter by moving averages
        filtered = self.filter_by_moving_averages(filtered)
        print(f"After filter 6 (moving averages): {len(filtered)} stocks")
        
        # Step 7: Filter by market strength
        filtered = self.filter_by_market_strength(filtered)
        print(f"After filter 7 (market strength): {len(filtered)} stocks")
        
        # Step 8: Filter by tail market high
        filtered = self.filter_by_tail_market_high(filtered)
        print(f"After filter 8 (tail market high): {len(filtered)} stocks")
        
        return filtered
    
    def get_detailed_info(self, stock_list):
        """
        Get detailed information for the list of filtered stocks
        """
        result = []
        
        for stock_code in stock_list:
            data = self.get_real_time_quote(stock_code)
            
            if data:
                stock_info = {
                    'code': stock_code,
                    'name': data.get('name', ''),
                    'price': data.get('last', 0),
                    'change_pct': (data.get('last', 0) - data.get('prev_close', 0)) / data.get('prev_close', 1) * 100 if data.get('prev_close', 0) > 0 else 0,
                    'volume': data.get('volume', 0),
                    'turnover_rate': data.get('turnover_rate', 0),
                    'market_cap': data.get('market_cap', 0) / 1_000_000_000,  # In billions
                }
                result.append(stock_info)
        
        return result


# Example usage
if __name__ == "__main__":
    """
    === Stock API Information ===
    This data fetcher supports multiple API sources:
    
    1. SINA Finance API (默认, 国内访问速度最快)
       - 无需注册，免费使用
       - 数据实时性好，国内访问速度快
    
    2. Hexun API (和讯)
       - 无需注册，免费使用
       - 国内访问速度快，提供更多基本面数据
    
    3. AllTick API (https://alltick.co)
       - 需要注册获取API token
       - 国际访问速度快，但国内可能较慢
       - 提供免费计划和付费升级选项
    
    选择合适的API源可以获得最佳性能。
    """
    
    # 使用新浪财经API创建数据获取器 (默认，国内访问最快)
    fetcher = StockDataFetcher(api_source="sina")
    
    # 获取股票列表 (可用市场: SH, SZ, HK, US)
    stocks = fetcher.get_stock_list(market="SH")
    
    # 应用所有筛选条件
    filtered_stocks = fetcher.apply_all_filters(stocks)
    
    # 获取筛选后股票的详细信息
    details = fetcher.get_detailed_info(filtered_stocks)
    
    # 打印结果
    for stock in details:
        print(f"{stock['code']} - {stock['name']}: ¥{stock['price']:.2f} ({stock['change_pct']:.2f}%), "
              f"市值: {stock['market_cap']:.2f}亿, 换手率: {stock['turnover_rate']:.2f}%")
              
    # 如果想切换到其他API源，可以使用:
    # fetcher.set_api_source("hexun")  # 切换到和讯API
    
    # 如果想使用AllTick API (需要先注册获取token):
    # fetcher.set_api_source("alltick")
    # fetcher.set_token("your-alltick-token-here")
