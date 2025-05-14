from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.task_service import TaskService

tasks_bp = Blueprint('tasks', __name__)
task_service = TaskService()

@tasks_bp.route('', methods=['GET'])
@jwt_required()
def get_tasks():
    """获取用户的所有定时任务"""
    user_id = get_jwt_identity()
    
    tasks = task_service.get_user_tasks(user_id)
    
    return jsonify({
        "count": len(tasks),
        "tasks": tasks
    })

@tasks_bp.route('', methods=['POST'])
@jwt_required()
def create_task():
    """创建新的定时任务"""
    user_id = get_jwt_identity()
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "无效的请求数据"}), 400
    
    # 验证必填字段
    required_fields = ['task_type', 'schedule', 'parameters']
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"缺少必填字段: {field}"}), 400
    
    # 验证任务类型
    valid_task_types = ['filter']
    if data['task_type'] not in valid_task_types:
        return jsonify({"error": f"无效的任务类型，支持的类型: {', '.join(valid_task_types)}"}), 400
    
    # 验证cron表达式
    schedule = data['schedule']
    if not task_service.validate_cron_expression(schedule):
        return jsonify({"error": "无效的cron表达式"}), 400
    
    # 创建任务
    try:
        task = task_service.create_scheduled_task(
            user_id=user_id,
            task_type=data['task_type'],
            schedule=schedule,
            parameters=data['parameters'],
            name=data.get('name', '定时筛选任务'),
            description=data.get('description', '')
        )
        
        return jsonify({
            "message": "定时任务创建成功",
            "task": task
        }), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@tasks_bp.route('/<task_id>', methods=['PUT'])
@jwt_required()
def update_task(task_id):
    """更新定时任务"""
    user_id = get_jwt_identity()
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "无效的请求数据"}), 400
    
    # 检查任务是否存在
    task = task_service.get_scheduled_task(task_id)
    if not task:
        return jsonify({"error": "任务不存在"}), 404
    
    # 验证任务归属
    if str(task.user_id) != str(user_id):
        return jsonify({"error": "无权访问此任务"}), 403
    
    # 验证cron表达式
    if 'schedule' in data:
        schedule = data['schedule']
        if not task_service.validate_cron_expression(schedule):
            return jsonify({"error": "无效的cron表达式"}), 400
    
    # 更新任务
    try:
        updated_task = task_service.update_scheduled_task(
            task_id=task_id,
            name=data.get('name'),
            description=data.get('description'),
            schedule=data.get('schedule'),
            parameters=data.get('parameters'),
            is_active=data.get('is_active')
        )
        
        return jsonify({
            "message": "定时任务更新成功",
            "task": updated_task
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@tasks_bp.route('/<task_id>', methods=['DELETE'])
@jwt_required()
def delete_task(task_id):
    """删除定时任务"""
    user_id = get_jwt_identity()
    
    # 检查任务是否存在
    task = task_service.get_scheduled_task(task_id)
    if not task:
        return jsonify({"error": "任务不存在"}), 404
    
    # 验证任务归属
    if str(task.user_id) != str(user_id):
        return jsonify({"error": "无权访问此任务"}), 403
    
    # 删除任务
    try:
        task_service.delete_scheduled_task(task_id)
        return jsonify({"message": "定时任务已删除"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500 