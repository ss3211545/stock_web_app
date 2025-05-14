import requests
import json
from datetime import datetime

def test_direct_sina_implementation():
    """Directly implement the Sina API portion of the get_kline_data method"""
    # Stock code to test with
    stock_code = "sh600000"
    
    # Parameters
    kline_type = 1  # Daily K-line
    num_periods = 10  # Number of periods
    
    # Mapping for period types (same as in the fixed code)
    period_map = {1: '240', 2: '1680', 3: '7680', 4: '5', 5: '15', 6: '30', 7: '60'}
    period = period_map.get(kline_type, '240')
    
    # Request parameters
    params = {
        'symbol': stock_code,
        'scale': period,
        'ma': 'no',
        'datalen': num_periods
    }
    
    # URL from the fixed code
    url = "http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
    
    # Headers
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Referer': 'http://finance.sina.com.cn/'
    }
    
    print(f"URL: {url}")
    print(f"Parameters: {params}")
    
    # Send request
    try:
        response = requests.get(url, params=params, headers=headers, timeout=5)
        print(f"Status code: {response.status_code}")
        
        if response.status_code == 200:
            content = response.text
            print(f"Response content: {content[:100]}...")
            
            # Parse JSON
            try:
                data = json.loads(content)
                print(f"Successfully parsed JSON: {len(data)} records")
                
                # Process the data into the same format as our method
                result = []
                for item in data:
                    if isinstance(item, dict):
                        date_str = item.get('day', '')
                        if not date_str:
                            continue
                            
                        try:
                            dt = datetime.strptime(date_str, '%Y-%m-%d')
                            timestamp = int(dt.timestamp())
                        except:
                            timestamp = 0
                            
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
                
                # Print the processed data
                if result:
                    print("\nProcessed data sample:")
                    for i, item in enumerate(result[:3]):
                        print(f"{i+1}. {item}")
                        
                    return True
                else:
                    print("No processed data.")
                    return False
                
            except json.JSONDecodeError as e:
                print(f"Failed to parse JSON: {e}")
                print(f"Raw response: {response.text}")
                return False
        else:
            print(f"Request failed: {response.status_code}")
            print(f"Response content: {response.text}")
            return False
            
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_direct_sina_implementation()
    print(f"\nTest result: {'Success' if success else 'Failed'}") 