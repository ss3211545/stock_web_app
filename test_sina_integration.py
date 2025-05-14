from data_fetcher import StockDataFetcher
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def test_sina_integration():
    """Test the integration of Sina API in the StockDataFetcher class"""
    # Initialize the data fetcher with Sina API
    fetcher = StockDataFetcher(api_source='sina')
    
    # Test stock code
    stock_code = 'sh600000'
    
    # Temporarily override the data sources to only use Sina
    # Store the original list
    original_list = None
    try:
        import sys
        frame = sys._getframe(0)
        # Find the get_kline_data function's frame
        while frame:
            if 'data_sources' in frame.f_globals:
                original_list = frame.f_globals['data_sources']
                frame.f_globals['data_sources'] = ['sina']
                break
            frame = frame.f_back
    except:
        print("Warning: Could not modify global data_sources list. Using alternative approach.")
    
    # If we couldn't modify the global list, try an alternative approach
    try:
        # Modify data_fetcher instance to only use Sina API
        original_method = fetcher.get_kline_data
        
        def wrapped_method(*args, **kwargs):
            """Modified get_kline_data method to force Sina API usage"""
            # Store original data sources
            original_sources = fetcher.get_best_data_source
            
            # Replace with function that only returns Sina
            fetcher.get_best_data_source = lambda *args, **kwargs: ['sina']
            
            # Call original method
            result = original_method(*args, **kwargs)
            
            # Restore original function
            fetcher.get_best_data_source = original_sources
            
            return result
            
        # Replace method temporarily
        fetcher.get_kline_data = wrapped_method
    except:
        print("Warning: Could not replace get_kline_data method. Using direct approach.")
        
    try:
        # Try to retrieve K-line data
        print(f"Attempting to get K-line data for {stock_code}...")
        result = fetcher.get_kline_data(stock_code, kline_type=1, num_periods=10)
        
        # Print result metadata
        metadata = result.get('metadata', {})
        print(f"Data Source: {metadata.get('source')}")
        print(f"Reliability: {metadata.get('reliability')}")
        print(f"Status: {metadata.get('status')}")
        print(f"Count: {metadata.get('count')}")
        
        # Print a sample of the data
        data = result.get('data', [])
        if data:
            print("\nFirst 3 data points:")
            for i, item in enumerate(data[:3]):
                print(f"{i+1}. {item}")
            return True
        else:
            print("No data returned.")
            return False
            
    finally:
        # Restore original data sources list if we modified it
        if original_list is not None:
            try:
                frame = sys._getframe(0)
                while frame:
                    if 'data_sources' in frame.f_globals:
                        frame.f_globals['data_sources'] = original_list
                        break
                    frame = frame.f_back
            except:
                pass
        
        # Restore original method if we replaced it
        if 'original_method' in locals():
            fetcher.get_kline_data = original_method

if __name__ == "__main__":
    success = test_sina_integration()
    print(f"\nTest result: {'Success' if success else 'Failed'}") 