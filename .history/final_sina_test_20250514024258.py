import requests
import json

def test_sina_finance_kline():
    """Test the Sina Finance K-line API with the documented parameters format"""
    # Stock code to test with
    stock_code = "sh600000"
    
    # Use the documented URL format
    url = f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
    
    # Parameters based on documentation
    params = {
        "symbol": stock_code,          # Stock code
        "scale": "240",                # Time period: 5=5min, 15=15min, 30=30min, 60=60min, 240=day
        "ma": "no",                    # Moving average: no=without MA
        "datalen": "10"                # Number of data points to return
    }
    
    # Add headers to mimic a browser
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Referer': 'http://finance.sina.com.cn/'
    }
    
    print(f"Requesting URL: {url}")
    print(f"With parameters: {params}")
    
    try:
        # Send request
        response = requests.get(url, params=params, headers=headers, timeout=5)
        
        # Check response status
        print(f"Response status code: {response.status_code}")
        
        if response.status_code == 200:
            try:
                # Try to parse as JSON
                data = json.loads(response.text)
                print(f"Successfully parsed JSON data: {len(data)} records")
                
                # Print first 3 records for verification
                if data and len(data) > 0:
                    print("\nData sample:")
                    for i, item in enumerate(data[:3]):
                        print(f"{i+1}. {item}")
                
                return True
            except json.JSONDecodeError as e:
                print(f"Failed to parse JSON: {e}")
                print(f"Raw response: {response.text[:200]}...")
                
                return False
        else:
            print(f"Request failed with status code: {response.status_code}")
            print(f"Response content: {response.text[:200]}...")
            
            return False
    
    except Exception as e:
        print(f"Request error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return False

if __name__ == "__main__":
    success = test_sina_finance_kline()
    print(f"\nTest result: {'Success' if success else 'Failed'}") 