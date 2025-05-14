import sys
import os
import json
from datetime import datetime
import uuid
import threading
import time
from utils.db import get_db
from services.stock_service import StockService
from celery import Celery

# 将主项目路径添加到Python路径中，以便导入data_fetcher
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
from data_fetcher import StockDataFetcher

# 创建Celery实例
celery = Celery(__name__)
celery.conf.update(
    broker_url=os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    result_backend=os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),
)

class FilterService:
    """股票筛选服务，基于原data_fetcher封装"""
    
    def __init__(self):
        self.stock_service = StockService()
        self.data_fetcher = self.stock_service.data_fetcher
    
    def run_filter_async(self, task_id, user_id, market='SH', 
                       degradation_enabled=False, degradation_level='MEDIUM', 
                       api_source='sina'):
        """异步启动筛选任务
        
        Args:
            task_id: 任务ID
            user_id: 用户ID
            market: 市场代码，可选值: SH, SZ, BJ, HK, US
            degradation_enabled: 是否启用数据降级策略
            degradation_level: 降级级别，可选值: LOW, MEDIUM, HIGH
            api_source: API数据源，可选值: sina, eastmoney, alltick
        """
        # 设置API源和降级策略
        self.stock_service.set_api_source(api_source)
        self.stock_service.set_degradation_settings(
            enabled=degradation_enabled, 
            level=degradation_level
        )
        
        # 启动筛选任务
        run_filter_task.delay(
            task_id=task_id, 
            user_id=user_id, 
            market=market,
            degradation_enabled=degradation_enabled,
            degradation_level=degradation_level,
            api_source=api_source
        )
    
    def analyze_stock(self, stock_code):
        """分析单只股票是否符合八大步骤
        
        Args:
            stock_code: 股票代码
            
        Returns:
            分析结果，包含每个步骤的通过情况
        """
        stock_list = [stock_code]
        
        # 将每个步骤单独应用到股票上
        step_results = []
        step_data = {}
        
        # 步骤1: 涨幅分析
        step1 = self.data_fetcher.filter_by_price_increase(stock_list)
        step_data[0] = {'passed': bool(step1), 'name': '涨幅筛选'}
        step_results.append(step1)
        
        # 步骤2: 量比分析
        step2 = self.data_fetcher.filter_by_volume_ratio(stock_list)
        step_data[1] = {'passed': bool(step2), 'name': '量比筛选'}
        step_results.append(step2)
        
        # 步骤3: 换手率分析
        step3 = self.data_fetcher.filter_by_turnover_rate(stock_list)
        step_data[2] = {'passed': bool(step3), 'name': '换手率筛选'}
        step_results.append(step3)
        
        # 步骤4: 市值分析
        step4 = self.data_fetcher.filter_by_market_cap(stock_list)
        step_data[3] = {'passed': bool(step4), 'name': '市值筛选'}
        step_results.append(step4)
        
        # 步骤5: 成交量分析
        step5 = self.data_fetcher.filter_by_increasing_volume(stock_list)
        step_data[4] = {'passed': bool(step5), 'name': '成交量筛选'}
        step_results.append(step5)
        
        # 步骤6: 均线分析
        step6 = self.data_fetcher.filter_by_moving_averages(stock_list)
        step_data[5] = {'passed': bool(step6), 'name': '均线形态筛选'}
        step_results.append(step6)
        
        # 步骤7: 强弱分析
        step7 = self.data_fetcher.filter_by_market_strength(stock_list)
        step_data[6] = {'passed': bool(step7), 'name': '大盘强度筛选'}
        step_results.append(step7)
        
        # 步骤8: 尾盘创新高分析
        step8 = self.data_fetcher.filter_by_tail_market_high(stock_list)
        step_data[7] = {'passed': bool(step8), 'name': '尾盘创新高筛选'}
        step_results.append(step8)
        
        # 获取股票详细信息添加到分析结果中
        stock_info = None
        try:
            stock_info = self.stock_service.get_stock_details(stock_code)
        except Exception:
            pass
        
        if stock_info:
            # 添加具体数据到步骤分析中
            step_data[0]['value'] = f"{stock_info.get('change_pct', 'N/A')}%"
            step_data[0]['required'] = "3%-5%"
            step_data[0]['details'] = f"当日涨幅为{stock_info.get('change_pct', 'N/A')}%，{'在' if 3 <= stock_info.get('change_pct', 0) <= 5 else '不在'}3%-5%范围内"
            
            step_data[1]['value'] = f"{stock_info.get('volume_ratio', 'N/A')}"
            step_data[1]['required'] = "> 1.0"
            step_data[1]['details'] = f"量比为{stock_info.get('volume_ratio', 'N/A')}，{'大于' if stock_info.get('volume_ratio', 0) > 1 else '不大于'}1.0"
            
            step_data[2]['value'] = f"{stock_info.get('turnover_rate', 'N/A')}%"
            step_data[2]['required'] = "5%-10%"
            step_data[2]['details'] = f"换手率为{stock_info.get('turnover_rate', 'N/A')}%，{'在' if 5 <= stock_info.get('turnover_rate', 0) <= 10 else '不在'}5%-10%范围内"
            
            step_data[3]['value'] = f"{stock_info.get('market_cap', 'N/A')}亿"
            step_data[3]['required'] = "50亿-200亿"
            step_data[3]['details'] = f"市值为{stock_info.get('market_cap', 'N/A')}亿，{'在' if 50 <= stock_info.get('market_cap', 0) <= 200 else '不在'}50亿-200亿范围内"
        
        # 计算通过率
        passed_steps = sum(1 for s in step_results if s)
        pass_rate = (passed_steps / 8) * 100
        
        # 构建分析结果
        analysis = {
            'stock_code': stock_code,
            'stock_info': stock_info,
            'step_results': step_data,
            'passed_steps': passed_steps,
            'total_steps': 8,
            'pass_rate': pass_rate,
            'analysis_time': datetime.now().isoformat()
        }
        
        # 添加投资建议
        if passed_steps >= 7:
            analysis['recommendation'] = "强烈推荐关注，符合尾盘选股策略的高质量标的"
            analysis['recommendation_level'] = "HIGH"
        elif passed_steps >= 5:
            analysis['recommendation'] = "建议关注，具有一定潜力"
            analysis['recommendation_level'] = "MEDIUM"
        else:
            analysis['recommendation'] = "暂不推荐，不完全符合尾盘选股策略"
            analysis['recommendation_level'] = "LOW"
        
        return analysis
    
    def get_user_results(self, user_id, page=1, per_page=10):
        """获取用户的筛选结果列表
        
        Args:
            user_id: 用户ID
            page: 页码
            per_page: 每页数量
            
        Returns:
            (结果列表, 总数量)
        """
        db = get_db()
        cursor = db.cursor()
        
        # 计算总数
        cursor.execute(
            "SELECT COUNT(*) FROM filter_results WHERE user_id = %s",
            (user_id,)
        )
        total = cursor.fetchone()['count']
        
        # 获取分页数据
        offset = (page - 1) * per_page
        cursor.execute(
            """
            SELECT id, market, timestamp, 
                   jsonb_array_length(matched_stocks) as matched_count
            FROM filter_results 
            WHERE user_id = %s
            ORDER BY timestamp DESC
            LIMIT %s OFFSET %s
            """,
            (user_id, per_page, offset)
        )
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'id': row['id'],
                'market': row['market'],
                'timestamp': row['timestamp'].isoformat(),
                'matched_count': row['matched_count']
            })
        
        return results, total
    
    def get_result(self, result_id):
        """获取单个筛选结果
        
        Args:
            result_id: 结果ID
            
        Returns:
            筛选结果对象
        """
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute(
            "SELECT * FROM filter_results WHERE id = %s",
            (result_id,)
        )
        
        return cursor.fetchone()
    
    def get_result_details(self, result_id):
        """获取筛选结果详情
        
        Args:
            result_id: 结果ID
            
        Returns:
            详细的筛选结果数据
        """
        result = self.get_result(result_id)
        
        if not result:
            return None
        
        # 获取筛选的股票详细信息
        matched_stocks = json.loads(result['matched_stocks'])
        filter_steps_data = json.loads(result['filter_steps_data'])
        filter_parameters = json.loads(result['filter_parameters'])
        
        # 获取股票详细信息
        stock_details = []
        for stock_code in matched_stocks:
            try:
                stock_info = self.stock_service.get_stock_details(stock_code)
                if stock_info:
                    stock_details.append(stock_info)
            except Exception:
                # 忽略获取详情失败的股票
                pass
        
        return {
            'id': result['id'],
            'market': result['market'],
            'timestamp': result['timestamp'].isoformat(),
            'parameters': filter_parameters,
            'steps_data': filter_steps_data,
            'matched_stocks': matched_stocks,
            'stock_details': stock_details
        }


@celery.task(name='run_filter_task')
def run_filter_task(task_id, user_id, market, degradation_enabled, degradation_level, api_source):
    """Celery任务: 执行股票筛选
    
    Args:
        task_id: 任务ID
        user_id: 用户ID
        market: 市场代码
        degradation_enabled: 是否启用数据降级策略
        degradation_level: 降级级别
        api_source: API数据源
    """
    from utils.db import get_db
    from data_fetcher import StockDataFetcher
    
    # 更新任务状态为进行中
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        """
        UPDATE tasks 
        SET status = 'RUNNING', progress = 5, message = '正在获取股票列表', updated_at = %s
        WHERE id = %s
        """,
        (datetime.now(), task_id)
    )
    db.commit()
    
    try:
        # 初始化数据获取器
        data_fetcher = StockDataFetcher(api_source=api_source)
        data_fetcher.set_degradation_settings(enabled=degradation_enabled, level=degradation_level)
        
        # 获取股票列表
        cursor.execute(
            """
            UPDATE tasks 
            SET progress = 10, message = '获取股票列表中...', updated_at = %s
            WHERE id = %s
            """,
            (datetime.now(), task_id)
        )
        db.commit()
        
        stock_list = data_fetcher.get_stock_list(market)
        
        # 更新进度
        cursor.execute(
            """
            UPDATE tasks 
            SET progress = 15, message = '预处理: 剔除ST和退市风险股', updated_at = %s
            WHERE id = %s
            """,
            (datetime.now(), task_id)
        )
        db.commit()
        
        # 预处理: 剔除ST和退市风险股
        filtered_stocks = data_fetcher.filter_by_name(stock_list)
        
        # 更新进度
        cursor.execute(
            """
            UPDATE tasks 
            SET progress = 20, message = '预处理: 筛选价格大于1元的股票', updated_at = %s
            WHERE id = %s
            """,
            (datetime.now(), task_id)
        )
        db.commit()
        
        # 预处理: 筛选价格大于1元的股票
        filtered_stocks = data_fetcher.filter_by_price(filtered_stocks)
        
        initial_count = len(filtered_stocks)
        filter_steps_data = []
        
        # 定义进度更新回调函数
        def progress_callback(step_index, status, stock_count, total_count=None):
            nonlocal filter_steps_data
            
            # 记录筛选步骤数据
            if status == 'in_progress':
                progress = 20 + (step_index + 1) * 10
                if progress > 95:
                    progress = 95
                    
                cursor.execute(
                    """
                    UPDATE tasks 
                    SET progress = %s, message = %s, updated_at = %s
                    WHERE id = %s
                    """,
                    (progress, f"步骤 {step_index+1}: 筛选中 ({stock_count}只股票)", datetime.now(), task_id)
                )
                db.commit()
            
            if status == 'success':
                # 记录步骤数据
                filter_steps_data.append({
                    'step': step_index,
                    'count': stock_count,
                    'status': 'success'
                })
        
        # 执行八大步骤筛选
        matched_stocks = data_fetcher.apply_all_filters(filtered_stocks, step_callback=progress_callback)
        
        # 保存筛选结果
        result_id = str(uuid.uuid4())
        
        # 处理部分匹配情况
        partial_match = False
        if not matched_stocks:
            partial_match = True
            max_step = getattr(data_fetcher, 'last_successful_step', 0)
            
            if hasattr(data_fetcher, 'partial_results') and data_fetcher.partial_results:
                # 获取部分结果（最后一个成功步骤的结果）
                matched_stocks = data_fetcher.partial_results
            else:
                # 如果连部分结果都没有，显示涨幅前20只股票
                matched_stocks = data_fetcher.get_top_increase_stocks(stock_list, limit=20)
        
        # 保存结果到数据库
        cursor.execute(
            """
            INSERT INTO filter_results (id, user_id, market, timestamp, 
                                      filter_parameters, matched_stocks, filter_steps_data)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                result_id,
                user_id,
                market,
                datetime.now(),
                json.dumps({
                    'degradation_enabled': degradation_enabled,
                    'degradation_level': degradation_level,
                    'api_source': api_source,
                    'partial_match': partial_match,
                    'max_step': max_step if partial_match else 8
                }),
                json.dumps([stock['code'] if isinstance(stock, dict) else stock for stock in matched_stocks]),
                json.dumps(filter_steps_data)
            )
        )
        
        # 更新任务状态为完成
        cursor.execute(
            """
            UPDATE tasks 
            SET status = 'COMPLETED', progress = 100, 
                message = %s, result_id = %s, updated_at = %s
            WHERE id = %s
            """,
            (
                f"筛选完成，找到{len(matched_stocks)}只股票" + (" (部分匹配)" if partial_match else ""),
                result_id,
                datetime.now(),
                task_id
            )
        )
        db.commit()
        
    except Exception as e:
        # 更新任务状态为失败
        cursor.execute(
            """
            UPDATE tasks 
            SET status = 'FAILED', message = %s, updated_at = %s
            WHERE id = %s
            """,
            (f"筛选失败: {str(e)}", datetime.now(), task_id)
        )
        db.commit()
        raise 