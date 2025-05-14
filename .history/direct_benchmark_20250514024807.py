import requests
import json
import time
from datetime import datetime

def benchmark_sina_api(stock_code='sh600000', num_periods=10, num_runs=3):
    """Benchmark the Sina Finance API for K-line data retrieval"""
    total_time = 0
    success_count = 0
    results = []
    
    print(f"\nTesting SINA API ({num_runs} runs):")
    
    url = "http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
    
    for i in range(num_runs):
        print(f"  Run {i+1}/{num_runs}...")
        
        # Parameters for daily K-line
        params = {
            'symbol': stock_code,
            'scale': '240',  # daily K-line
            'ma': 'no',
            'datalen': num_periods
        }
        
        # Headers
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'http://finance.sina.com.cn/'
        }
        
        start = time.time()
        try:
            # Send request
            response = requests.get(url, params=params, headers=headers, timeout=5)
            elapsed = time.time() - start
            
            if response.status_code == 200:
                # Parse JSON
                data = json.loads(response.text)
                record_count = len(data) if isinstance(data, list) else 0
                
                if record_count > 0:
                    success_count += 1
                    results.append({
                        'run': i+1,
                        'time': elapsed,
                        'status': 'SUCCESS',
                        'count': record_count
                    })
                    print(f"    Time: {elapsed:.2f}s, Status: SUCCESS, Records: {record_count}")
                else:
                    results.append({
                        'run': i+1,
                        'time': elapsed,
                        'status': 'NO_DATA',
                        'count': 0
                    })
                    print(f"    Time: {elapsed:.2f}s, Status: NO_DATA, Records: 0")
            else:
                results.append({
                    'run': i+1,
                    'time': elapsed,
                    'status': 'HTTP_ERROR',
                    'count': 0,
                    'http_status': response.status_code
                })
                print(f"    Time: {elapsed:.2f}s, Status: HTTP_ERROR {response.status_code}")
            
            total_time += elapsed
            
        except Exception as e:
            elapsed = time.time() - start
            results.append({
                'run': i+1,
                'time': elapsed,
                'status': 'ERROR',
                'error': str(e)
            })
            print(f"    Time: {elapsed:.2f}s, Status: ERROR, Error: {str(e)}")
            total_time += elapsed
    
    # Calculate average time
    avg_time = total_time / num_runs if num_runs > 0 else 0
    success_rate = (success_count / num_runs) * 100 if num_runs > 0 else 0
    
    print(f"\nSINA API Summary:")
    print(f"  Average Time: {avg_time:.2f} seconds")
    print(f"  Success Rate: {success_rate:.1f}%")
    
    return {
        'api': 'sina',
        'avg_time': avg_time,
        'success_rate': success_rate,
        'runs': results
    }

def benchmark_eastmoney_api(stock_code='sh600000', num_periods=10, num_runs=3):
    """Benchmark the East Money Finance API for K-line data retrieval"""
    total_time = 0
    success_count = 0
    results = []
    
    print(f"\nTesting EASTMONEY API ({num_runs} runs):")
    
    # Convert sh600000 to 1.600000 format for East Money API
    if stock_code.startswith('sh'):
        market_id = '1'
        code = stock_code[2:]
    elif stock_code.startswith('sz'):
        market_id = '0'
        code = stock_code[2:]
    else:
        market_id = '1'  # Default to Shanghai market
        code = stock_code
    
    formatted_code = f"{market_id}.{code}"
    
    for i in range(num_runs):
        print(f"  Run {i+1}/{num_runs}...")
        
        # East Money API URL
        url = f"http://push2his.eastmoney.com/api/qt/stock/kline/get"
        
        # Parameters
        params = {
            'fields1': 'f1,f2,f3,f4,f5,f6',
            'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58',
            'klt': '101',  # Daily K-line
            'fqt': '0',    # No adjustment
            'secid': formatted_code,
            'lmt': num_periods,
            '_': int(time.time() * 1000)
        }
        
        # Headers
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'http://quote.eastmoney.com/'
        }
        
        start = time.time()
        try:
            # Send request
            response = requests.get(url, params=params, headers=headers, timeout=5)
            elapsed = time.time() - start
            
            if response.status_code == 200:
                # Parse JSON
                data = json.loads(response.text)
                
                # Print response for debugging
                print(f"    Response: {response.text[:100]}...")
                
                # Check if data is received
                if data and 'data' in data:
                    klines = data['data'].get('klines', [])
                    record_count = len(klines) if isinstance(klines, list) else 0
                    
                    if record_count > 0:
                        success_count += 1
                        results.append({
                            'run': i+1,
                            'time': elapsed,
                            'status': 'SUCCESS',
                            'count': record_count
                        })
                        print(f"    Time: {elapsed:.2f}s, Status: SUCCESS, Records: {record_count}")
                    else:
                        results.append({
                            'run': i+1,
                            'time': elapsed,
                            'status': 'NO_DATA',
                            'count': 0
                        })
                        print(f"    Time: {elapsed:.2f}s, Status: NO_DATA, Records: 0")
                else:
                    results.append({
                        'run': i+1,
                        'time': elapsed,
                        'status': 'NO_DATA',
                        'count': 0
                    })
                    print(f"    Time: {elapsed:.2f}s, Status: NO_DATA (Invalid response format)")
            else:
                results.append({
                    'run': i+1,
                    'time': elapsed,
                    'status': 'HTTP_ERROR',
                    'count': 0,
                    'http_status': response.status_code
                })
                print(f"    Time: {elapsed:.2f}s, Status: HTTP_ERROR {response.status_code}")
            
            total_time += elapsed
            
        except Exception as e:
            elapsed = time.time() - start
            results.append({
                'run': i+1,
                'time': elapsed,
                'status': 'ERROR',
                'error': str(e)
            })
            print(f"    Time: {elapsed:.2f}s, Status: ERROR, Error: {str(e)}")
            total_time += elapsed
    
    # Calculate average time
    avg_time = total_time / num_runs if num_runs > 0 else 0
    success_rate = (success_count / num_runs) * 100 if num_runs > 0 else 0
    
    print(f"\nEASTMONEY API Summary:")
    print(f"  Average Time: {avg_time:.2f} seconds")
    print(f"  Success Rate: {success_rate:.1f}%")
    
    return {
        'api': 'eastmoney',
        'avg_time': avg_time,
        'success_rate': success_rate,
        'runs': results
    }

def run_benchmark():
    # Run benchmarks for both APIs
    sina_results = benchmark_sina_api()
    eastmoney_results = benchmark_eastmoney_api()
    
    # Compare results
    print("\n=== API Comparison ===")
    
    sina_time = sina_results['avg_time']
    eastmoney_time = eastmoney_results['avg_time']
    
    if sina_time > 0 and eastmoney_time > 0:
        if eastmoney_time > sina_time:
            print(f"Sina is {eastmoney_time/sina_time:.2f}x faster than East Money")
        else:
            print(f"East Money is {sina_time/eastmoney_time:.2f}x faster than Sina")
    
    print(f"Sina Success Rate: {sina_results['success_rate']:.1f}%")
    print(f"East Money Success Rate: {eastmoney_results['success_rate']:.1f}%")
    
    return {
        'sina': sina_results,
        'eastmoney': eastmoney_results
    }

if __name__ == "__main__":
    run_benchmark() 