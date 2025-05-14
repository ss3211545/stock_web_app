import uuid
import json
from datetime import datetime
import re
import croniter
from utils.db import get_db

class TaskService:
    """任务管理服务"""
    
    def create_task(self, task_id, user_id, task_type, status, parameters=None):
        """创建任务记录
        
        Args:
            task_id: 任务ID
            user_id: 用户ID
            task_type: 任务类型
            status: 任务状态
            parameters: 任务参数
        
        Returns:
            任务ID
        """
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute(
            """
            INSERT INTO tasks (id, user_id, task_type, status, parameters, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                task_id,
                user_id,
                task_type,
                status,
                json.dumps(parameters) if parameters else None,
                datetime.now()
            )
        )
        
        db.commit()
        return task_id
    
    def get_task(self, task_id):
        """获取任务详情
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务对象
        """
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute(
            "SELECT * FROM tasks WHERE id = %s",
            (task_id,)
        )
        
        return cursor.fetchone()
    
    def update_task(self, task_id, status=None, progress=None, message=None, result_id=None):
        """更新任务状态
        
        Args:
            task_id: 任务ID
            status: 任务状态
            progress: 任务进度
            message: 任务消息
            result_id: 结果ID
        """
        db = get_db()
        cursor = db.cursor()
        
        update_fields = []
        params = []
        
        if status:
            update_fields.append("status = %s")
            params.append(status)
        
        if progress is not None:
            update_fields.append("progress = %s")
            params.append(progress)
        
        if message:
            update_fields.append("message = %s")
            params.append(message)
        
        if result_id:
            update_fields.append("result_id = %s")
            params.append(result_id)
        
        update_fields.append("updated_at = %s")
        params.append(datetime.now())
        
        # 添加任务ID作为WHERE条件的参数
        params.append(task_id)
        
        query = f"""
            UPDATE tasks
            SET {', '.join(update_fields)}
            WHERE id = %s
        """
        
        cursor.execute(query, params)
        db.commit()
    
    def create_scheduled_task(self, user_id, task_type, schedule, parameters, name=None, description=None):
        """创建定时任务
        
        Args:
            user_id: 用户ID
            task_type: 任务类型
            schedule: cron表达式
            parameters: 任务参数
            name: 任务名称
            description: 任务描述
            
        Returns:
            定时任务对象
        """
        task_id = str(uuid.uuid4())
        
        # 验证cron表达式
        if not self.validate_cron_expression(schedule):
            raise ValueError("无效的cron表达式")
        
        # 计算下次运行时间
        next_run = self._calculate_next_run(schedule)
        
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute(
            """
            INSERT INTO scheduled_tasks (
                id, user_id, name, description, task_type, 
                schedule, parameters, next_run, created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                task_id,
                user_id,
                name or f"{task_type} 任务",
                description or "",
                task_type,
                schedule,
                json.dumps(parameters),
                next_run,
                datetime.now()
            )
        )
        
        db.commit()
        
        # 获取新创建的任务
        cursor.execute(
            "SELECT * FROM scheduled_tasks WHERE id = %s",
            (task_id,)
        )
        
        task = cursor.fetchone()
        
        return {
            'id': task['id'],
            'name': task['name'],
            'schedule': task['schedule'],
            'next_run': task['next_run'].isoformat() if task['next_run'] else None,
            'is_active': task['is_active']
        }
    
    def get_scheduled_task(self, task_id):
        """获取定时任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            定时任务对象
        """
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute(
            "SELECT * FROM scheduled_tasks WHERE id = %s",
            (task_id,)
        )
        
        return cursor.fetchone()
    
    def update_scheduled_task(self, task_id, name=None, description=None, 
                             schedule=None, parameters=None, is_active=None):
        """更新定时任务
        
        Args:
            task_id: 任务ID
            name: 任务名称
            description: 任务描述
            schedule: cron表达式
            parameters: 任务参数
            is_active: 是否激活
            
        Returns:
            更新后的定时任务对象
        """
        db = get_db()
        cursor = db.cursor()
        
        # 获取现有任务
        task = self.get_scheduled_task(task_id)
        if not task:
            raise ValueError(f"任务 {task_id} 不存在")
        
        # 构建更新语句
        update_fields = []
        params = []
        
        if name is not None:
            update_fields.append("name = %s")
            params.append(name)
        
        if description is not None:
            update_fields.append("description = %s")
            params.append(description)
        
        if schedule is not None:
            # 验证新的cron表达式
            if not self.validate_cron_expression(schedule):
                raise ValueError("无效的cron表达式")
                
            update_fields.append("schedule = %s")
            params.append(schedule)
            
            # 更新下次运行时间
            next_run = self._calculate_next_run(schedule)
            update_fields.append("next_run = %s")
            params.append(next_run)
        
        if parameters is not None:
            update_fields.append("parameters = %s")
            params.append(json.dumps(parameters))
        
        if is_active is not None:
            update_fields.append("is_active = %s")
            params.append(is_active)
        
        # 如果没有需要更新的字段，直接返回现有任务
        if not update_fields:
            return {
                'id': task['id'],
                'name': task['name'],
                'schedule': task['schedule'],
                'next_run': task['next_run'].isoformat() if task['next_run'] else None,
                'is_active': task['is_active']
            }
        
        # 添加任务ID作为WHERE条件的参数
        params.append(task_id)
        
        # 执行更新
        query = f"""
            UPDATE scheduled_tasks
            SET {', '.join(update_fields)}
            WHERE id = %s
        """
        
        cursor.execute(query, params)
        db.commit()
        
        # 获取更新后的任务
        task = self.get_scheduled_task(task_id)
        
        return {
            'id': task['id'],
            'name': task['name'],
            'schedule': task['schedule'],
            'next_run': task['next_run'].isoformat() if task['next_run'] else None,
            'is_active': task['is_active']
        }
    
    def delete_scheduled_task(self, task_id):
        """删除定时任务
        
        Args:
            task_id: 任务ID
        """
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute(
            "DELETE FROM scheduled_tasks WHERE id = %s",
            (task_id,)
        )
        
        db.commit()
    
    def get_user_tasks(self, user_id):
        """获取用户的所有定时任务
        
        Args:
            user_id: 用户ID
            
        Returns:
            定时任务列表
        """
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute(
            """
            SELECT id, name, description, task_type, schedule, 
                   parameters, is_active, last_run, next_run, created_at
            FROM scheduled_tasks
            WHERE user_id = %s
            ORDER BY created_at DESC
            """,
            (user_id,)
        )
        
        tasks = []
        for row in cursor.fetchall():
            tasks.append({
                'id': row['id'],
                'name': row['name'],
                'description': row['description'],
                'task_type': row['task_type'],
                'schedule': row['schedule'],
                'parameters': json.loads(row['parameters']) if row['parameters'] else {},
                'is_active': row['is_active'],
                'last_run': row['last_run'].isoformat() if row['last_run'] else None,
                'next_run': row['next_run'].isoformat() if row['next_run'] else None,
                'created_at': row['created_at'].isoformat()
            })
        
        return tasks
    
    def validate_cron_expression(self, cron_expr):
        """验证cron表达式
        
        Args:
            cron_expr: cron表达式
            
        Returns:
            是否有效
        """
        try:
            # 检查是否是有效的cron表达式格式
            parts = cron_expr.split()
            if len(parts) not in (5, 6):
                return False
            
            # 使用croniter库验证cron表达式
            base = datetime.now()
            iter = croniter.croniter(cron_expr, base)
            
            # 如果能获取下一次运行时间，则表达式有效
            iter.get_next(datetime)
            return True
        except (ValueError, KeyError):
            return False
    
    def _calculate_next_run(self, cron_expr):
        """计算下次运行时间
        
        Args:
            cron_expr: cron表达式
            
        Returns:
            下次运行时间
        """
        base = datetime.now()
        iter = croniter.croniter(cron_expr, base)
        return iter.get_next(datetime) 