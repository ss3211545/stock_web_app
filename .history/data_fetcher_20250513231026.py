import requests
import json
import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta

class StockDataFetcher:
    """
    A class to fetch and process stock data for the tailed stock selection system
    implementing the eight-step screening strategy.
    """
    
    def __init__(self, token=None):
        """
        Initialize the data fetcher with API token
        
        Parameters:
        -----------
        token : str
            API token for accessing stock data APIs
        """
        self.token = token
        self.base_url = "https://quote.tradeswitcher.com/quote-stock-b-api"
        self.headers = {
            'Content-Type': 'application/json'
        }
        
        # Cache for stock data to reduce API calls
        self.stock_data_cache = {}
        self.market_index_cache = {}
        self.last_update_time = {}
        
    def set_token(self, token):
        """Set the API token"""
        self.token = token
        
    def _get_api_url(self, endpoint):
        """Build the full API URL with token"""
        return f"{self.base_url}/{endpoint}?token={self.token}"

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
        dict : The response data
        """
        try:
            if params:
                # Encode the params for URL
                encoded_params = requests.utils.quote(json.dumps(params))
                url = f"{url}&query={encoded_params}"
                
            response = requests.get(url=url, headers=self.headers)
            response.raise_for_status()
            
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"API request error: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            return None
            
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
        # Append market to stock code if provided and not already in code
        if market and not stock_code.endswith(f".{market}"):
            full_code = f"{stock_code}.{market}"
        else:
            full_code = stock_code
            
        # Check if we have fresh cached data (less than 5 seconds old)
        current_time = time.time()
        if (full_code in self.stock_data_cache and 
            current_time - self.last_update_time.get(full_code, 0) < 5):
            return self.stock_data_cache[full_code]
            
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
        
        return None

    def get_kline_data(self, stock_code, kline_type=1, num_periods=60, market=None):
        """
        Get K-line historical data for a stock
        
        Parameters:
        -----------
        stock_code : str
            The stock code to query
        kline_type : int
            Type of k-line (1=daily, 2=weekly, 3=monthly, 4=yearly, 5=1min, 6=5min, etc.)
        num_periods : int
            Number of periods to retrieve
        market : str
            Market identifier
            
        Returns:
        --------
        list : The k-line data
        """
        # Append market to stock code if provided and not already in code
        if market and not stock_code.endswith(f".{market}"):
            full_code = f"{stock_code}.{market}"
        else:
            full_code = stock_code
            
        # Build request params
        params = {
            "trace": "python_http_request",
            "data": {
                "code": full_code,
                "kline_type": kline_type,
                "kline_timestamp_end": 0,  # 0 means latest data
                "query_kline_num": num_periods,
                "adjust_type": 0  # 0=no adjustment, 1=forward, 2=backward
            }
        }
        
        # Make API request
        url = self._get_api_url("kline")
        response_data = self._make_api_request(url, params)
        
        if response_data and 'data' in response_data and 'klines' in response_data['data']:
            return response_data['data']['klines']
        
        return None
    
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
        # In a real implementation, this would fetch from the API
        # For now, we'll just return a placeholder
        # This function would typically return all available stocks or stocks by market
        
        params = {
            "trace": "python_http_request",
            "data": {
                "market": market
            }
        }
        
        url = self._get_api_url("stock_list")
        response_data = self._make_api_request(url, params)
        
        if response_data and 'data' in response_data and 'stocks' in response_data['data']:
            return response_data['data']['stocks']
        
        # Fallback to dummy data for testing
        return ["000001.SZ", "600000.SH", "600036.SH"]

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
    # Create a data fetcher with your API token
    fetcher = StockDataFetcher(token="your-api-token-here")
    
    # Get stock list for a market
    stocks = fetcher.get_stock_list(market="SH")
    
    # Apply all filters
    filtered_stocks = fetcher.apply_all_filters(stocks)
    
    # Get detailed information about the filtered stocks
    details = fetcher.get_detailed_info(filtered_stocks)
    
    # Print the results
    for stock in details:
        print(f"{stock['code']} - {stock['name']}: ¥{stock['price']:.2f} ({stock['change_pct']:.2f}%), "
              f"Market Cap: {stock['market_cap']:.2f}B, Turnover: {stock['turnover_rate']:.2f}%")
