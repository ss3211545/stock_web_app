from data_fetcher import StockDataFetcher
import logging
import json
import requests
from datetime import datetime

# 配置详细日志
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def test_sina_kline_directly():
    """直接测试新浪K线API，不通过数据获取器的轮换机制"""
    print("直接测试新浪K线API...")
    
    # 使用与数据获取器相同的请求参数
    code = "sh600000"
    period = "day"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Referer': 'http://finance.sina.com.cn/'
    }
    
    params = {
        'symbol': code,
        'scale': period,
        'ma': 'no',
        'datalen': 10
    }
    
    # 新的URL (已修复)
    url = "https://quotes.sina.cn/cn/api/jsonp_v2.php/CN_MarketDataService.getKLineData"
    
    try:
        print(f"请求URL: {url}")
        print(f"参数: {params}")
        
        # 发送请求
        response = requests.get(url, params=params, headers=headers, timeout=5)
        print(f"状态码: {response.status_code}")
        
        # 如果请求成功
        if response.status_code == 200:
            content = response.text
            print(f"响应内容前100个字符: {content[:100]}...")
            
            # 检查JSONP格式
            if '(' in content and ')' in content:
                print("检测到JSONP格式，进行解析...")
                json_str = content.split('(', 1)[1].rsplit(')', 1)[0]
                try:
                    data = json.loads(json_str)
                    print(f"成功解析JSONP数据，获得{len(data)}条记录")
                    
                    # 打印前3条数据
                    if data:
                        print("\n数据示例:")
                        for i, item in enumerate(data[:3]):
                            print(f"{i+1}. {item.get('day')} - 开:{item.get('open')} 高:{item.get('high')} 低:{item.get('low')} 收:{item.get('close')} 量:{item.get('volume')}")
                    
                    return len(data) > 0
                except json.JSONDecodeError as e:
                    print(f"解析JSONP数据失败: {str(e)}")
                    return False
            else:
                # 尝试直接解析JSON
                try:
                    data = response.json()
                    print(f"成功解析JSON数据，获得{len(data)}条记录")
                    return len(data) > 0
                except json.JSONDecodeError as e:
                    print(f"解析JSON数据失败: {str(e)}")
                    return False
        else:
            print(f"请求失败，状态码: {response.status_code}")
            return False
    
    except Exception as e:
        print(f"请求出错: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_sina_kline_directly()
    print(f"\n测试结果: {'成功' if success else '失败'}") 