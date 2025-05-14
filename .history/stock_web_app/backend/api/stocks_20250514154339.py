from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.stock_service import StockService

stocks_bp = Blueprint('stocks', __name__)
stock_service = StockService()

@stocks_bp.route('', methods=['GET'])
@jwt_required()
def get_stock_list():
    """获取股票列表"""
    market = request.args.get('market', 'SH')
    
    try:
        stocks = stock_service.get_stock_list(market)
        return jsonify({
            "market": market,
            "count": len(stocks),
            "stocks": stocks
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@stocks_bp.route('/<code>', methods=['GET'])
@jwt_required()
def get_stock_details(code):
    """获取单只股票详细信息"""
    try:
        details = stock_service.get_stock_details(code)
        return jsonify(details)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@stocks_bp.route('/<code>/kline', methods=['GET'])
@jwt_required()
def get_kline_data(code):
    """获取K线数据"""
    kline_type = int(request.args.get('type', 1))
    num_periods = int(request.args.get('periods', 60))
    
    try:
        kline_data = stock_service.get_kline_data(code, kline_type, num_periods)
        return jsonify(kline_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@stocks_bp.route('/realtime', methods=['POST'])
@jwt_required()
def get_realtime_data():
    """获取多只股票的实时数据"""
    data = request.get_json()
    
    if not data or not data.get('codes'):
        return jsonify({"error": "需要提供股票代码列表"}), 400
    
    stock_codes = data.get('codes')
    
    # 验证股票代码列表
    if not isinstance(stock_codes, list) or len(stock_codes) == 0:
        return jsonify({"error": "股票代码列表格式无效"}), 400
    
    # 限制一次查询的股票数量
    if len(stock_codes) > 50:
        return jsonify({"error": "一次最多查询50只股票"}), 400
    
    try:
        realtime_data = stock_service.get_realtime_data(stock_codes)
        return jsonify({
            "count": len(realtime_data),
            "data": realtime_data
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500 