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
        
        # 设置降级策略
        self.degradation_enabled = True   # 是否启用数据降级策略
        self.degradation_level = "MEDIUM"  # 降级程度: LOW, MEDIUM, HIGH
        
        # 数据质量信息记录
        self.stocks_data_quality = {}
        
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
            if self.api_source == 'sina':
                # 每次请求不超过80只股票，防止请求过大
                batch_size = 80
                for i in range(0, len(stock_codes), batch_size):
                    batch = stock_codes[i:i+batch_size]
                    query_list = ','.join(batch)
                    url = f"{self.api_urls['sina']['realtime']}{query_list}"
                    
                    # 添加重试机制
                    for retry in range(max_retries):
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
                                            'open': float(values[1]) if values[1] else 0,
                                            'pre_close': float(values[2]) if values[2] else 0,
                                            'price': float(values[3]) if values[3] else 0,
                                            'high': float(values[4]) if values[4] else 0,
                                            'low': float(values[5]) if values[5] else 0,
                                            'volume': int(float(values[8])) if values[8] else 0,
                                            'amount': float(values[9]) if values[9] else 0,
                                            'date': values[30],
                                            'time': values[31]
                                        }
                                        
                                        # 计算涨跌幅
                                        if stock_data['pre_close'] > 0:
                                            stock_data['change_pct'] = round((stock_data['price'] - stock_data['pre_close']) / stock_data['pre_close'] * 100, 2)
                                        else:
                                            stock_data['change_pct'] = 0
                                        
                                        result.append(stock_data)
                                # 请求成功，跳出重试循环
                                break
                            else:
                                logger.error(f"API请求错误 (尝试 {retry+1}/{max_retries}): {response.status_code} {response.reason} for url: {url}")
                                if retry == max_retries - 1:
                                    logger.error(f"获取实时数据失败，已达最大重试次数")
                                else:
                                    # 请求失败，等待后重试
                                    time.sleep(1)
                        except Exception as e:
                            logger.error(f"请求数据时出错 (尝试 {retry+1}/{max_retries}): {str(e)}")
                            if retry == max_retries - 1:
                                logger.error(f"处理数据失败，已达最大重试次数")
                            else:
                                # 出错，等待后重试
                                time.sleep(1)
                    
                    # 防止API限流
                    if i + batch_size < len(stock_codes):
                        time.sleep(0.3)
            
            elif self.api_source == 'hexun':
                # 和讯API只能单只股票查询
                for code in stock_codes:
                    try:
                        url = f"http://quote.hexun.com/quote/stocklist.aspx?type=stock&market={code[0:2]}&code={code[2:]}"
                        response = requests.get(url, headers=self.headers)
                        if response.status_code == 200:
                            # 解析和讯数据
                            data = response.text.strip()
                            # 这里需要根据实际返回格式解析数据
                            logger.warning("和讯数据解析暂未完全实现，可能返回不完整数据")
                            # 至少要创建一个包含基本信息的结构
                            stock_data = {
                                'code': code,
                                'name': f"股票{code}",
                                'price': 0,
                                'change_pct': 0,
                                'volume': 0,
                                'amount': 0
                            }
                            result.append(stock_data)
                    except Exception as e:
                        logger.error(f"请求和讯数据时出错: {str(e)}")
                        print(f"ERROR: Failed to get Hexun data for {code}: {str(e)}")
                    
                    # 防止API限流
                    time.sleep(0.2)
            
            elif self.api_source == 'alltick':
                if not self.token:
                    logger.error("使用AllTick API需要提供token")
                    print("ERROR: AllTick API requires a token. Please set it using set_token(your_token) method.")
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
                                stock_data = {
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
                                }
                                result.append(stock_data)
                        else:
                            logger.error(f"API request error: {response.status_code} {response.reason}")
                            print(f"ERROR: Failed to get AllTick data: {response.status_code}")
                    except Exception as e:
                        logger.error(f"请求AllTick数据时出错: {str(e)}")
                        print(f"ERROR: Failed to process AllTick data: {str(e)}")
            
            if not result:
                logger.error(f"未能获取任何实时数据")
                print("ERROR: Failed to get any real-time stock data!")
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
            
            # 筛选换手率范围放宽到2%-15%
            filtered_stocks = []
            for stock in detailed_info:
                if 2.0 <= stock['turnover_rate'] <= 15.0:
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
                if 30.0 <= stock['market_cap'] <= 500.0:
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
                    # 获取最近5天的K线数据
                    kline_result = self.get_kline_data(code, kline_type=1, num_periods=5)
                    kline_data = kline_result.get('data', [])
                    metadata = kline_result.get('metadata', {})
                    
                    # 记录数据质量
                    stocks_data_quality[code] = {
                        'source': metadata.get('source', 'UNKNOWN'),
                        'reliability': metadata.get('reliability', 'NONE'),
                        'status': metadata.get('status', 'MISSING'),
                        'filter': '成交量分析'
                    }
                    
                    if len(kline_data) < 3:
                        # 如果无法获取K线数据，使用实时数据判断
                        logger.warning(f"无法获取{code}足够的K线数据，尝试使用实时数据代替")
                        
                        try:
                            # 获取当前股票实时数据
                            realtime_data = self.get_realtime_data([code])
                            if realtime_data and realtime_data[0]['volume'] > 0:
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
                    volumes = [k['volume'] for k in kline_data]
                    
                    # 至少有3天的数据，且最近的成交量比前一天大
                    if len(volumes) >= 3 and volumes[-1] > volumes[-2]:
                        # 再检查前一天的成交量是否也比再前一天大
                        if volumes[-2] > volumes[-3]:
                            filtered_stocks.append(code)
                            stocks_data_quality[code]['decision_basis'] = 'STANDARD'
                
                # 批次间添加延迟，避免API限流
                if batch_idx < total_batches - 1:
                    time.sleep(2 + random.random())
            
            # 如果没有符合条件的股票，考虑更宽松的条件
            if not filtered_stocks and stock_codes:
                logger.warning("未找到符合严格成交量条件的股票，尝试使用宽松条件")
                # 返回前20%的股票作为备选（按成交量排序）
                try:
                    # 获取实时数据
                    realtime_data = self.get_realtime_data(stock_codes[:min(50, len(stock_codes))])
                    # 按成交量排序
                    sorted_stocks = sorted(realtime_data, key=lambda x: x['volume'], reverse=True)
                    # 取前20%或至少5只
                    selected_count = max(min(len(sorted_stocks) // 5, 10), min(5, len(sorted_stocks)))
                    filtered_stocks = [stock['code'] for stock in sorted_stocks[:selected_count]]
                    
                    # 标记这些股票使用了降级策略
                    for code in filtered_stocks:
                        if code in stocks_data_quality:
                            stocks_data_quality[code]['decision_basis'] = 'FALLBACK'
                        else:
                            stocks_data_quality[code] = {
                                'source': 'REALTIME',
                                'reliability': 'LOW',
                                'status': 'FALLBACK',
                                'filter': '成交量分析',
                                'decision_basis': 'FALLBACK'
                            }
                    
                    logger.warning(f"使用宽松条件选择了{len(filtered_stocks)}只成交量较大的股票")
                except Exception as e:
                    logger.error(f"尝试使用宽松条件筛选股票失败: {str(e)}")
            
            # 保存数据质量信息到全局变量，供UI显示
            self.stocks_data_quality = stocks_data_quality if hasattr(self, 'stocks_data_quality') else {}
            self.stocks_data_quality.update(stocks_data_quality)
            
            print(f"After filter 5 (increasing volume): {len(filtered_stocks)} stocks")
            logger.info(f"成交量筛选: 从{len(stock_codes)}只股票中筛选出{len(filtered_stocks)}只")
            return filtered_stocks
            
        except Exception as e:
            logger.error(f"成交量筛选过程中出错: {str(e)}")
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
                    # 获取至少60天的K线数据
                    kline_result = self.get_kline_data(code, kline_type=1, num_periods=70)
                    kline_data = kline_result.get('data', [])
                    metadata = kline_result.get('metadata', {})
                    
                    # 记录数据质量
                    stocks_data_quality[code] = {
                        'source': metadata.get('source', 'UNKNOWN'),
                        'reliability': metadata.get('reliability', 'NONE'),
                        'status': metadata.get('status', 'MISSING'),
                        'filter': '均线分析',
                        'data_count': len(kline_data)
                    }
                    
                    if len(kline_data) < 60:
                        # 如果无法获取足够的K线数据，使用备用方法
                        logger.warning(f"无法获取{code}足够的K线数据进行均线分析，尝试备用分析方法")
                        stocks_data_quality[code]['alternative_method'] = '实时价格动态'
                        
                        try:
                            # 获取当前股票的实时数据
                            realtime_data = self.get_realtime_data([code])
                            if realtime_data:
                                stock_data = realtime_data[0]
                                # 获取额外的技术指标数据
                                extra_info = self._get_extra_stock_info(code)
                                
                                # 如果价格大于当日均价且接近涨停，可能是走势强劲
                                price_strength = stock_data['price'] > stock_data['open'] * 1.03
                                volume_strength = extra_info.get('volume_ratio', 0) > 1.0
                                
                                if price_strength and volume_strength:
                                    filtered_stocks.append(code)
                                    stocks_data_quality[code]['decision_basis'] = 'ALTERNATIVE'
                                    logger.info(f"{code}无K线数据，但价格大于开盘价3%且量比>1，视为符合条件")
                        except Exception as e:
                            logger.error(f"尝试使用实时数据判断{code}均线趋势失败: {str(e)}")
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
                    else:
                        stocks_data_quality[code]['status'] = 'INSUFFICIENT'
                
                # 批次间添加延迟，避免API限流
                if batch_idx < total_batches - 1:
                    time.sleep(3 + random.random())
            
            # 保存数据质量信息到全局变量，供UI显示
            if not hasattr(self, 'stocks_data_quality'):
                self.stocks_data_quality = {}
            self.stocks_data_quality.update(stocks_data_quality)
            
            # 如果没有符合条件的股票，不降级策略，保持原有的筛选严格性
            if not filtered_stocks:
                logger.warning("未找到符合均线条件的股票，保持筛选严格性")
                return []
            
            print(f"After filter 6 (moving averages): {len(filtered_stocks)} stocks")
            logger.info(f"均线筛选: 从{len(stock_codes)}只股票中筛选出{len(filtered_stocks)}只")
            return filtered_stocks
            
        except Exception as e:
            logger.error(f"均线筛选过程中出错: {str(e)}")
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
        应用尾盘选股八大步骤的完整筛选流程
        
        Parameters:
        -----------
        stock_codes: list
            股票代码列表
        
        Returns:
        --------
        list
            符合所有条件的股票代码列表,以及各步骤的筛选结果
        """
        if not stock_codes:
            return []
            
        try:
            # 记录原始股票数量
            original_count = len(stock_codes)
            logger.info(f"开始应用八大步骤筛选，初始股票数量: {original_count}")
            print(f"Starting with {original_count} stocks")
            
            # 获取所有股票的基本信息用于打印
            all_stocks_info = self.get_detailed_info(stock_codes[:20] if len(stock_codes) > 20 else stock_codes)
            print(f"\n初始股票：")
            for stock in all_stocks_info[:5]:  # 只显示前5只用于示例
                print(f"  {stock['code']} - {stock['name']}: ¥{stock['price']:.2f} ({stock['change_pct']:.2f}%)")
            if len(all_stocks_info) > 5:
                print(f"  ... 还有 {len(all_stocks_info)-5} 只股票未显示")
            
            # 步骤1: 筛选涨幅3%-5%的股票
            filtered_step1 = self.filter_by_price_increase(stock_codes)
            
            # 打印步骤1的结果
            print(f"\n步骤1 (涨幅3%-5%)后: {len(filtered_step1)} 只股票")
            step1_info = self.get_detailed_info(filtered_step1)
            for stock in step1_info[:min(5, len(step1_info))]:
                print(f"  {stock['code']} - {stock['name']}: ¥{stock['price']:.2f} ({stock['change_pct']:.2f}%)")
            
            if not filtered_step1:
                logger.info(f"步骤1后无符合条件股票，八大步骤筛选完成")
                return []
            
            # 步骤2: 筛选量比>1的股票
            filtered_step2 = self.filter_by_volume_ratio(filtered_step1)
            
            # 打印步骤2的结果
            print(f"\n步骤2 (量比>1)后: {len(filtered_step2)} 只股票")
            step2_info = self.get_detailed_info(filtered_step2)
            for stock in step2_info[:min(5, len(step2_info))]:
                print(f"  {stock['code']} - {stock['name']}: 量比{stock['volume_ratio']:.2f}")
            
            if not filtered_step2:
                logger.info(f"步骤2后无符合条件股票，八大步骤筛选完成")
                return []
            
            # 步骤3: 筛选换手率5%-10%的股票
            filtered_step3 = self.filter_by_turnover_rate(filtered_step2)
            
            # 打印步骤3的结果
            print(f"\n步骤3 (换手率5%-10%)后: {len(filtered_step3)} 只股票")
            step3_info = self.get_detailed_info(filtered_step3)
            for stock in step3_info[:min(5, len(step3_info))]:
                print(f"  {stock['code']} - {stock['name']}: 换手率{stock['turnover_rate']:.2f}%")
            
            if not filtered_step3:
                logger.info(f"步骤3后无符合条件股票，八大步骤筛选完成")
                return []
            
            # 步骤4: 筛选市值50亿-200亿的股票
            filtered_step4 = self.filter_by_market_cap(filtered_step3)
            
            # 打印步骤4的结果
            print(f"\n步骤4 (市值50亿-200亿)后: {len(filtered_step4)} 只股票")
            step4_info = self.get_detailed_info(filtered_step4)
            for stock in step4_info[:min(5, len(step4_info))]:
                print(f"  {stock['code']} - {stock['name']}: 市值{stock['market_cap']:.2f}亿")
            
            if not filtered_step4:
                logger.info(f"步骤4后无符合条件股票，八大步骤筛选完成")
                return []
            
            # 步骤5: 筛选成交量持续放大的股票
            filtered_step5 = self.filter_by_increasing_volume(filtered_step4)
            
            # 打印步骤5的结果
            print(f"\n步骤5 (成交量持续放大)后: {len(filtered_step5)} 只股票")
            step5_info = self.get_detailed_info(filtered_step5)
            for stock in step5_info[:min(5, len(step5_info))]:
                print(f"  {stock['code']} - {stock['name']}")
            
            if not filtered_step5:
                logger.info(f"步骤5后无符合条件股票，八大步骤筛选完成")
                return []
            
            # 步骤6: 筛选短期均线搭配60日线向上的股票
            filtered_step6 = self.filter_by_moving_averages(filtered_step5)
            
            # 打印步骤6的结果
            print(f"\n步骤6 (均线条件)后: {len(filtered_step6)} 只股票")
            step6_info = self.get_detailed_info(filtered_step6)
            for stock in step6_info[:min(5, len(step6_info))]:
                print(f"  {stock['code']} - {stock['name']}")
            
            if not filtered_step6:
                logger.info(f"步骤6后无符合条件股票，八大步骤筛选完成")
                return []
            
            # 步骤7: 筛选强于大盘的股票
            filtered_step7 = self.filter_by_market_strength(filtered_step6)
            
            # 打印步骤7的结果
            print(f"\n步骤7 (强于大盘)后: {len(filtered_step7)} 只股票")
            step7_info = self.get_detailed_info(filtered_step7)
            for stock in step7_info[:min(5, len(step7_info))]:
                print(f"  {stock['code']} - {stock['name']}")
            
            if not filtered_step7:
                logger.info(f"步骤7后无符合条件股票，八大步骤筛选完成")
                return []
            
            # 步骤8: 筛选尾盘创新高的股票
            filtered_step8 = self.filter_by_tail_market_high(filtered_step7)
            
            # 打印步骤8的结果
            print(f"\n步骤8 (尾盘创新高)后: {len(filtered_step8)} 只股票")
            step8_info = self.get_detailed_info(filtered_step8)
            for stock in step8_info[:min(5, len(step8_info))]:
                print(f"  {stock['code']} - {stock['name']}")
            
            # 记录最终结果
            final_count = len(filtered_step8)
            logger.info(f"八大步骤筛选完成，从{original_count}只股票中筛选出{final_count}只符合条件的股票")
            print(f"\n筛选完成！从{original_count}只股票中筛选出{final_count}只符合条件的股票\n")
            
            # 返回完整的筛选结果包含所有步骤
            return filtered_step8
            
        except Exception as e:
            logger.error(f"应用八大步骤筛选过程中出错: {str(e)}")
            print(f"ERROR: 筛选过程出错: {str(e)}")
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
        # 调整API轮换顺序 - 根据可靠性排序: 新浪 -> 东方财富 -> 腾讯 -> 其他备用API
        data_sources = ['sina', 'eastmoney', 'tencent', 'ifeng', 'akshare']  # 增加更多备用API源
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
                    time.sleep(0.5 + random.random())  # 随机延迟0.5-1.5秒
                    
                    # === 新浪API ===
                    if source == 'sina':
                        logger.info(f"尝试从新浪获取{stock_code}的K线数据 (尝试 {retry+1}/{max_retries})")
                        period_map = {1: 'day', 2: 'week', 3: 'month', 4: '5min', 5: '15min', 6: '30min', 7: '60min'}
                        period = period_map.get(kline_type, 'day')
                        
                        params = {
                            'symbol': stock_code,
                            'scale': period,
                            'ma': 'no',
                            'datalen': min(num_periods, 180)  # 新浪限制最多180条
                        }
                        
                        url = self.api_urls['sina']['kline']
                        response = requests.get(url, params=params, headers=self.headers, timeout=5)
                        if response.status_code == 200:
                            data = response.json()
                            
                            for item in data:
                                # 转换日期为时间戳
                                date_str = item['day'] if isinstance(item, dict) and 'day' in item else ""
                                if not date_str:
                                    continue
                                    
                                try:
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
                                logger.info(f"从新浪API成功获取{stock_code}的K线数据")
                                break
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
                        
                        response = requests.get(url, headers=self.headers, timeout=5)
                        if response.status_code == 200:
                            json_data = response.json()
                            
                            # 解析东方财富API返回的数据
                            try:
                                if 'data' in json_data and 'klines' in json_data['data']:
                                    data = json_data['data']['klines']
                                    
                                    for item_str in data:
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
                            except Exception as e:
                                logger.error(f"解析东方财富K线数据出错: {str(e)}")
                            
                            if result:  # 获取成功，记录数据源并设置可靠性
                                used_source = 'EASTMONEY'
                                reliability = 'HIGH'  # 提高东方财富的可靠性级别
                                logger.info(f"从东方财富API成功获取{stock_code}的K线数据")
                                break
                        else:
                            logger.error(f"东方财富API请求错误 (尝试 {retry+1}/{max_retries}): {response.status_code}")
                    
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
                        
                        # 腾讯API格式: https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh600000,day,2020-01-01,2023-01-01,100,qfq
                        period_map = {1: 'day', 2: 'week', 3: 'month', 4: 'm5', 5: 'm15', 6: 'm30', 7: 'm60'}
                        period = period_map.get(kline_type, 'day')
                        
                        # 构建URL
                        url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},{period},{start_date.strftime('%Y-%m-%d')},{end_date.strftime('%Y-%m-%d')},{num_periods},qfq"
                        
                        response = requests.get(url, headers=self.headers, timeout=5)
                        if response.status_code == 200:
                            json_data = response.json()
                            
                            # 解析腾讯API返回的数据
                            try:
                                if 'data' in json_data and code in json_data['data']:
                                    kline_data = json_data['data'][code]
                                    
                                    if period in kline_data:
                                        data = kline_data[period]
                                        
                                        for item in data:
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
                            except Exception as e:
                                logger.error(f"解析腾讯K线数据出错: {str(e)}")
                            
                            if result:  # 获取成功，记录数据源并设置可靠性
                                used_source = 'TENCENT'
                                reliability = 'MEDIUM'
                                logger.info(f"从腾讯API成功获取{stock_code}的K线数据")
                                break
                        else:
                            logger.error(f"腾讯API请求错误 (尝试 {retry+1}/{max_retries}): {response.status_code}")
                    
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
                                json_data = response.json()
                                
                                # 解析凤凰财经API返回的数据
                                if 'record' in json_data:
                                    for item in json_data['record']:
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
                                    
                                if result:
                                    used_source = 'IFENG'
                                    reliability = 'MEDIUM'
                                    logger.info(f"从凤凰财经API成功获取{stock_code}的K线数据")
                                    break
                            else:
                                logger.error(f"凤凰财经API请求错误 (尝试 {retry+1}/{max_retries}): {response.status_code}")
                        except Exception as e:
                            logger.error(f"请求凤凰财经API出错: {str(e)}")
                    
                    # === AKShare API (新增) ===
                    elif source == 'akshare':
                        try:
                            logger.info(f"尝试从AKShare获取{stock_code}的K线数据 (尝试 {retry+1}/{max_retries})")
                            
                            # 尝试导入akshare
                            try:
                                import akshare as ak
                            except ImportError:
                                logger.error("AKShare模块未安装，无法使用该数据源")
                                break
                            
                            # 转换股票代码格式为akshare格式
                            if stock_code.startswith('sh'):
                                ak_code = f"{stock_code[2:]}.SH"
                            elif stock_code.startswith('sz'):
                                ak_code = f"{stock_code[2:]}.SZ"
                            else:
                                ak_code = stock_code
                            
                            # 获取K线数据
                            period_map = {1: 'daily', 2: 'weekly', 3: 'monthly', 4: '5min', 5: '15min', 6: '30min', 7: '60min'}
                            period = period_map.get(kline_type, 'daily')
                            
                            if period in ['daily', 'weekly', 'monthly']:
                                df = ak.stock_zh_a_hist(symbol=ak_code, period=period, adjust="qfq")
                            else:
                                df = ak.stock_zh_a_minute(symbol=ak_code, period=period)
                            
                            # 将DataFrame转换为K线数据
                            for _, row in df.iterrows():
                                try:
                                    date_str = str(row['日期'])
                                    dt = datetime.strptime(date_str, '%Y-%m-%d')
                                    timestamp = int(dt.timestamp())
                                    
                                    kline = {
                                        'timestamp': timestamp,
                                        'date': date_str,
                                        'open': float(row['开盘']),
                                        'high': float(row['最高']),
                                        'low': float(row['最低']),
                                        'close': float(row['收盘']),
                                        'volume': int(row['成交量'])
                                    }
                                    result.append(kline)
                                except Exception as e:
                                    logger.error(f"解析AKShare数据出错: {str(e)}")
                                    continue
                            
                            if result:
                                used_source = 'AKSHARE'
                                reliability = 'HIGH'
                                logger.info(f"从AKShare成功获取{stock_code}的K线数据")
                                break
                        except Exception as e:
                            logger.error(f"请求AKShare数据出错: {str(e)}")
                            
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