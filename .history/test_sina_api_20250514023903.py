from data_fetcher import StockDataFetcher
import logging
import json

# 配置详细日志
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def test_sina_kline():
    """测试新浪K线数据获取"""
    print("测试新浪K线数据获取...")
    
    # 初始化获取器，使用新浪API
    fetcher = StockDataFetcher(api_source="sina")
    
    # 保存原始API轮换顺序
    original_sources = fetcher.get_kline_data.__globals__.get('data_sources', [])
    
    try:
        # 强制只使用新浪API
        fetcher.get_kline_data.__globals__['data_sources'] = ['sina']
        
        # 尝试获取K线数据
        code = "sh600000"
        result = fetcher.get_kline_data(code, kline_type=1, num_periods=10)
        
        # 打印结果摘要
        metadata = result.get('metadata', {})
        print(f"数据源: {metadata.get('source')}")
        print(f"可靠性: {metadata.get('reliability')}")
        print(f"数据量: {metadata.get('count')}")
        print(f"状态: {metadata.get('status')}")
        
        # 打印前3条数据示例
        data = result.get('data', [])
        if data:
            print("\n数据示例:")
            for i, item in enumerate(data[:3]):
                print(f"{i+1}. {item['date']} - 开:{item['open']} 高:{item['high']} 低:{item['low']} 收:{item['close']} 量:{item['volume']}")
        else:
            print("未获取到任何数据")
        
        # 返回测试结果
        return len(data) > 0
        
    finally:
        # 恢复原始API轮换顺序
        fetcher.get_kline_data.__globals__['data_sources'] = original_sources

if __name__ == "__main__":
    success = test_sina_kline()
    print(f"\n测试结果: {'成功' if success else '失败'}") 