from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.filter_service import FilterService
from services.task_service import TaskService
import uuid

filter_bp = Blueprint('filter', __name__)
filter_service = FilterService()
task_service = TaskService()

@filter_bp.route('/run', methods=['POST'])
@jwt_required()
def run_filter():
    """启动筛选任务（异步）"""
    user_id = get_jwt_identity()
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "无效的请求数据"}), 400
    
    # 获取筛选参数
    market = data.get('market', 'SH')
    degradation_enabled = data.get('degradation_enabled', False)
    degradation_level = data.get('degradation_level', 'MEDIUM')
    api_source = data.get('api_source', 'sina')
    
    # 创建任务ID并启动异步任务
    task_id = str(uuid.uuid4())
    
    # 保存任务记录
    task_service.create_task(
        task_id=task_id,
        user_id=user_id,
        task_type='filter',
        status='PENDING',
        parameters={
            'market': market,
            'degradation_enabled': degradation_enabled,
            'degradation_level': degradation_level,
            'api_source': api_source
        }
    )
    
    # 启动异步筛选任务
    filter_service.run_filter_async(
        task_id=task_id,
        user_id=user_id,
        market=market,
        degradation_enabled=degradation_enabled,
        degradation_level=degradation_level,
        api_source=api_source
    )
    
    return jsonify({
        "message": "筛选任务已启动",
        "task_id": task_id
    })

@filter_bp.route('/status/<task_id>', methods=['GET'])
@jwt_required()
def get_filter_status(task_id):
    """获取筛选任务状态"""
    user_id = get_jwt_identity()
    
    task = task_service.get_task(task_id)
    
    if not task:
        return jsonify({"error": "任务不存在"}), 404
    
    # 验证任务归属
    if str(task.user_id) != str(user_id):
        return jsonify({"error": "无权访问此任务"}), 403
    
    return jsonify({
        "task_id": task.id,
        "status": task.status,
        "progress": task.progress,
        "message": task.message,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        "result_id": task.result_id
    })

@filter_bp.route('/results', methods=['GET'])
@jwt_required()
def get_filter_results():
    """获取用户的筛选结果列表"""
    user_id = get_jwt_identity()
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 10))
    
    results, total = filter_service.get_user_results(user_id, page, per_page)
    
    return jsonify({
        "total": total,
        "page": page,
        "per_page": per_page,
        "results": results
    })

@filter_bp.route('/results/<result_id>', methods=['GET'])
@jwt_required()
def get_filter_result(result_id):
    """获取单个筛选结果详情"""
    user_id = get_jwt_identity()
    
    result = filter_service.get_result(result_id)
    
    if not result:
        return jsonify({"error": "结果不存在"}), 404
    
    # 验证结果归属
    if str(result.user_id) != str(user_id):
        return jsonify({"error": "无权访问此结果"}), 403
    
    # 获取详细的筛选结果数据
    result_data = filter_service.get_result_details(result_id)
    
    return jsonify(result_data)

@filter_bp.route('/analyze/<code>', methods=['GET'])
@jwt_required()
def analyze_stock(code):
    """分析单只股票的八大步骤结果"""
    
    try:
        analysis = filter_service.analyze_stock(code)
        return jsonify(analysis)
    except Exception as e:
        return jsonify({"error": str(e)}), 500 