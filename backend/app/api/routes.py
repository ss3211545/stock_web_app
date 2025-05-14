from flask import jsonify, request, current_app
from app.api import api_bp
from app import socketio
from app.services.data_service import DataService
import time
import traceback
import threading
from datetime import datetime

# 创建数据服务实例
data_service = DataService()

# 获取可用市场
@api_bp.route('/stock/markets', methods=['GET'])
def get_markets():
    markets = [
        {"value": "SH", "label": "上证"},
        {"value": "SZ", "label": "深证"},
        {"value": "BJ", "label": "北证"},
        {"value": "HK", "label": "港股"},
        {"value": "US", "label": "美股"}
    ]
    return jsonify(markets)

# 获取系统状态
@api_bp.route('/system/status', methods=['GET'])
def get_system_status():
    now = datetime.now()
    is_weekday = now.weekday() < 5  # 0-4 是周一到周五
    
    market_status = "已收盘"
    is_tail_market = False
    
    if is_weekday and 9 <= now.hour < 15:  # 交易时间9:00-15:00
        market_status = "交易中"
        
        # 检查是否为尾盘时间（14:30-15:00）
        if now.hour == 14 and now.minute >= 30:
            market_status = "尾盘阶段"
            is_tail_market = True
    
    return jsonify({
        "time": now.strftime('%Y-%m-%d %H:%M:%S'),
        "market_status": market_status,
        "is_tail_market": is_tail_market
    })

# 获取股票详情
@api_bp.route('/stock/detail/<code>', methods=['GET'])
def get_stock_detail(code):
    try:
        # 获取股票详细信息
        detail = data_service.get_stock_details([code])
        if detail and len(detail) > 0:
            return jsonify(detail[0])
        else:
            return jsonify({"error": "未找到股票详情"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 获取K线数据
@api_bp.route('/stock/kline/<code>', methods=['GET'])
def get_kline(code):
    try:
        kline_type = int(request.args.get('type', 1))
        num_periods = int(request.args.get('periods', 60))
        
        # 获取K线数据
        kline_data = data_service.get_kline_data(code, kline_type, num_periods)
        return jsonify(kline_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 开始筛选流程
@api_bp.route('/stock/filter', methods=['POST'])
def start_filter():
    try:
        data = request.json
        market = data.get('market', 'SH')
        api_source = data.get('api_source', 'sina')
        degradation_enabled = data.get('degradation_enabled', False)
        degradation_level = data.get('degradation_level', 'MEDIUM')
        
        # 配置数据服务
        data_service.set_api_source(api_source)
        data_service.set_degradation_settings(degradation_enabled, degradation_level)
        
        # 创建后台线程执行筛选
        thread = threading.Thread(
            target=run_filter_process,
            args=(market,)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({"status": "started", "message": "筛选流程已启动"})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# 导出筛选结果
@api_bp.route('/stock/export', methods=['GET'])
def export_results():
    try:
        # 将最近的筛选结果转换为CSV格式
        results = data_service.get_last_filter_results()
        if not results:
            return jsonify({"error": "没有筛选结果可导出"}), 404
            
        # 这里直接返回JSON数据，前端可以自行转换为CSV
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 后台筛选处理函数
def run_filter_process(market):
    """在后台线程中执行筛选流程"""
    try:
        # 发送初始化消息
        socketio.emit('filter_progress', {
            'status': 'initializing',
            'message': '筛选准备中...',
            'progress': 0,
            'current_step': -1
        })
        
        # 获取股票列表
        socketio.emit('filter_progress', {
            'status': 'loading',
            'message': '获取股票列表...',
            'progress': 5,
            'current_step': -1
        })
        
        stock_list = data_service.get_stock_list(market)
        if not stock_list:
            socketio.emit('filter_progress', {
                'status': 'error',
                'message': '无法获取股票列表',
                'progress': 0,
                'current_step': -1
            })
            return
            
        # 预处理：剔除ST、退市风险和新股
        socketio.emit('filter_progress', {
            'status': 'processing',
            'message': '预处理：剔除ST、退市风险和新股',
            'progress': 10,
            'current_step': -1
        })
        
        filtered_stocks = data_service.filter_by_name(stock_list)
        
        # 预处理：筛选价格大于1元的股票
        socketio.emit('filter_progress', {
            'status': 'processing',
            'message': '预处理：筛选价格大于1元的股票',
            'progress': 15,
            'current_step': -1
        })
        
        filtered_stocks = data_service.filter_by_price(filtered_stocks)
        initial_count = len(filtered_stocks)
        
        # 应用所有筛选条件
        filtered_stocks = data_service.apply_all_filters(
            filtered_stocks,
            step_callback=filter_step_callback
        )
        
        # 处理结果
        if not filtered_stocks:
            # 如果没有找到符合条件的股票
            partial_match = True
            max_step = data_service.last_successful_step if hasattr(data_service, 'last_successful_step') else 0
            
            if hasattr(data_service, 'partial_results') and data_service.partial_results:
                # 获取部分结果
                partial_results = data_service.partial_results
                detailed_info = data_service.get_stock_details(partial_results)
                
                socketio.emit('filter_progress', {
                    'status': 'partial_results',
                    'message': f'未找到完全符合八大步骤的股票，显示符合前{max_step}步的股票',
                    'progress': 100,
                    'current_step': max_step,
                    'results': detailed_info,
                    'partial_match': True,
                    'max_step': max_step
                })
            else:
                # 获取涨幅前20名股票
                top_stocks = data_service.get_top_increase_stocks(stock_list, limit=20)
                detailed_info = data_service.get_stock_details(top_stocks)
                
                socketio.emit('filter_progress', {
                    'status': 'fallback_results',
                    'message': '未找到任何符合条件的股票，显示当日涨幅前20只股票',
                    'progress': 100,
                    'current_step': 0,
                    'results': detailed_info,
                    'partial_match': True,
                    'max_step': 0
                })
        else:
            # 筛选成功
            detailed_info = data_service.get_stock_details(filtered_stocks)
            
            socketio.emit('filter_progress', {
                'status': 'success',
                'message': f'筛选完成，符合八大步骤的股票有 {len(filtered_stocks)} 只',
                'progress': 100,
                'current_step': 8,
                'results': detailed_info,
                'partial_match': False
            })
    except Exception as e:
        traceback.print_exc()
        socketio.emit('filter_progress', {
            'status': 'error',
            'message': f'筛选过程中出错: {str(e)}',
            'progress': 0,
            'current_step': -1
        })

# 筛选步骤回调函数
def filter_step_callback(step_index, status, stock_count, total_count=None):
    """筛选步骤回调函数，通过WebSocket通知前端进度"""
    steps = [
        "涨幅筛选", "量比筛选", "换手率筛选", "市值筛选",
        "成交量筛选", "均线形态筛选", "大盘强度筛选", "尾盘创新高筛选"
    ]
    
    step_name = steps[step_index] if step_index < len(steps) else f"步骤{step_index+1}"
    
    if status == 'in_progress':
        progress = 20 + (step_index / 8) * 80
        socketio.emit('filter_progress', {
            'status': 'processing',
            'message': f'步骤 {step_index+1}: {step_name}',
            'progress': progress,
            'current_step': step_index,
            'stock_count': stock_count
        })
    elif status == 'success':
        progress = 20 + ((step_index + 1) / 8) * 80
        socketio.emit('filter_progress', {
            'status': 'step_complete',
            'message': f'{step_name} 筛选完成，剩余{stock_count}只股票',
            'progress': progress,
            'current_step': step_index,
            'stock_count': stock_count
        })
    elif status == 'fail':
        fail_messages = [
            "股票涨幅不在3%-5%范围内",
            "量比小于1.0",
            "换手率不在5%-10%范围内",
            "市值不在50亿-200亿范围内",
            "成交量未持续放大",
            "均线不满足多头排列或60日线未向上",
            "个股未强于大盘",
            "尾盘未接近日内高点"
        ]
        
        fail_reason = fail_messages[step_index] if step_index < len(fail_messages) else "未满足筛选条件"
        
        socketio.emit('filter_progress', {
            'status': 'step_failed',
            'message': f'{step_name} 筛选失败: {fail_reason}',
            'progress': 20 + ((step_index + 1) / 8) * 80,
            'current_step': step_index,
            'stock_count': stock_count,
            'fail_reason': fail_reason
        })
    
    # 给前端一点时间更新UI
    time.sleep(0.2)

# WebSocket事件
@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected') 