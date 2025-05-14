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
    url = "http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
    
    try:
        print(f"请求URL: {url}")
        print(f"参数: {params}")
        
        # 发送请求
        response = requests.get(url, params=params, headers=headers, timeout=5)
        print(f"状态码: {response.status_code}")
        
        # 如果请求成功
        if response.status_code == 200:
            content = response.text
            print(f"完整响应内容: {content}")
            
            # 检查是否为直接JSON格式（新URL可能直接返回JSON而非JSONP）
            try:
                data = json.loads(content)
                print(f"成功解析JSON数据: {data}")
                
                # 打印数据示例
                if isinstance(data, list) and data:
                    print("\n数据示例:")
                    for i, item in enumerate(data[:3]):
                        if isinstance(item, dict):
                            print(f"{i+1}. 日期:{item.get('day')} 开:{item.get('open')} 高:{item.get('high')} 低:{item.get('low')} 收:{item.get('close')} 量:{item.get('volume')}")
                
                return len(data) > 0 if isinstance(data, list) else False
                
            except json.JSONDecodeError:
                # 如果不是直接JSON，尝试JSONP格式
                print("非直接JSON格式，尝试解析JSONP")
                
                # 检查JSONP格式
                if 'CN_MarketData.getKLineData(' in content:
                    print("检测到JSONP格式，进行解析...")
                    try:
                        # 提取 JSON 部分
                        start_idx = content.find('CN_MarketData.getKLineData(') + len('CN_MarketData.getKLineData(')
                        end_idx = content.rfind(')')
                        
                        if start_idx > 0 and end_idx > start_idx:
                            json_str = content[start_idx:end_idx]
                            print(f"提取的JSON字符串: {json_str}")
                            
                            data = json.loads(json_str)
                            print(f"解析后的数据: {data}")
                            
                            # 检查是否有错误
                            if '__ERROR' in data and data['__ERROR'] == 0:
                                print("API返回成功状态")
                                
                                # 从 data 中提取实际数据
                                kline_data = data.get('result', {}).get('data', [])
                                if isinstance(kline_data, list):
                                    print(f"成功获取K线数据，共{len(kline_data)}条记录")
                                    
                                    if kline_data:
                                        print("\n数据示例:")
                                        for i, item in enumerate(kline_data[:3]):
                                            if isinstance(item, dict):
                                                print(f"{i+1}. 日期:{item.get('day')} 开:{item.get('open')} 高:{item.get('high')} 低:{item.get('low')} 收:{item.get('close')} 量:{item.get('volume')}")
                                    
                                    return len(kline_data) > 0
                                else:
                                    print(f"未找到K线数据列表，返回格式异常: {kline_data}")
                            else:
                                error_code = data.get('__ERROR', 'unknown')
                                error_msg = data.get('__E', 'No error message')
                                print(f"API报告错误: 代码={error_code}, 消息={error_msg}")
                        else:
                            print("无法提取JSON部分，索引无效")
                            return False
                    except json.JSONDecodeError as e:
                        print(f"解析JSONP数据失败: {str(e)}")
                        return False
                    except Exception as e:
                        print(f"处理JSONP数据时出错: {str(e)}")
                        return False
                else:
                    print("未检测到JSONP格式，尝试直接解析JSON")
                    try:
                        data = response.json()
                        print(f"解析后的JSON数据: {data}")
                        return True
                    except json.JSONDecodeError as e:
                        print(f"解析JSON数据失败: {str(e)}")
                        return False
        else:
            print(f"请求失败，状态码: {response.status_code}")
            return False
    
    except Exception as e:
        print(f"请求出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_sina_kline_directly()
    print(f"\n测试结果: {'成功' if success else '失败'}") 