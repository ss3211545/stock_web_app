from data_fetcher import StockDataFetcher
import time
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def benchmark_api(api_name, stock_code='sh600000', kline_type=1, num_periods=10, num_runs=3):
    """Benchmark a specific API for K-line data retrieval"""
    total_time = 0
    success_count = 0
    results = []
    
    print(f"\nTesting {api_name.upper()} API ({num_runs} runs):")
    
    for i in range(num_runs):
        print(f"  Run {i+1}/{num_runs}...")
        
        # Create a fresh instance for each run
        fetcher = StockDataFetcher(api_source=api_name)
        
        # Force specific API by setting data sources
        if api_name == 'sina':
            # Override data_sources to only use Sina
            fetcher.get_kline_data.__globals__['data_sources'] = ['sina']
        elif api_name == 'eastmoney':
            # Override data_sources to only use East Money
            fetcher.get_kline_data.__globals__['data_sources'] = ['eastmoney']
        
        start = time.time()
        try:
            # Get K-line data
            result = fetcher.get_kline_data(stock_code, kline_type=kline_type, num_periods=num_periods)
            
            elapsed = time.time() - start
            total_time += elapsed
            success_count += 1
            
            metadata = result.get('metadata', {})
            results.append({
                'run': i+1,
                'time': elapsed,
                'status': metadata.get('status'),
                'count': metadata.get('count'),
                'source': metadata.get('source')
            })
            
            print(f"    Time: {elapsed:.2f}s, Source: {metadata.get('source')}, Status: {metadata.get('status')}, Records: {metadata.get('count')}")
            
        except Exception as e:
            elapsed = time.time() - start
            print(f"    Error: {str(e)}, Time: {elapsed:.2f}s")
            results.append({
                'run': i+1,
                'time': elapsed,
                'status': 'ERROR',
                'error': str(e)
            })
    
    # Calculate average time
    avg_time = total_time / num_runs if num_runs > 0 else 0
    success_rate = (success_count / num_runs) * 100 if num_runs > 0 else 0
    
    print(f"\n{api_name.upper()} API Summary:")
    print(f"  Average Time: {avg_time:.2f} seconds")
    print(f"  Success Rate: {success_rate:.1f}%")
    
    return {
        'api': api_name,
        'avg_time': avg_time,
        'success_rate': success_rate,
        'runs': results
    }

def run_benchmark():
    # APIs to test
    apis = ['sina', 'eastmoney']
    results = {}
    
    for api in apis:
        results[api] = benchmark_api(api)
    
    # Compare results
    print("\n=== API Comparison ===")
    if 'sina' in results and 'eastmoney' in results:
        sina_time = results['sina']['avg_time']
        eastmoney_time = results['eastmoney']['avg_time']
        
        if sina_time > 0 and eastmoney_time > 0:
            print(f"Speed Ratio: East Money is {eastmoney_time/sina_time:.2f}x the time of Sina")
            if eastmoney_time > sina_time:
                print(f"Sina is {eastmoney_time/sina_time:.2f}x faster than East Money")
            else:
                print(f"East Money is {sina_time/eastmoney_time:.2f}x faster than Sina")
        
        print(f"Sina Success Rate: {results['sina']['success_rate']:.1f}%")
        print(f"East Money Success Rate: {results['eastmoney']['success_rate']:.1f}%")
    
    return results

if __name__ == "__main__":
    run_benchmark() 