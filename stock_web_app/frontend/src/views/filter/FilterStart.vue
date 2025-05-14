<template>
  <div class="filter-start">
    <el-card>
      <div slot="header">
        <h2 class="page-title">启动筛选</h2>
        <p class="page-subtitle">尾盘八大步骤选股策略筛选</p>
      </div>
      
      <el-form ref="filterForm" :model="filterForm" label-width="120px">
        <!-- 市场选择 -->
        <el-form-item label="市场">
          <el-radio-group v-model="filterForm.market">
            <el-radio v-for="market in markets" :key="market" :label="market">
              {{ marketLabels[market] }}
            </el-radio>
          </el-radio-group>
        </el-form-item>
        
        <!-- 数据源选择 -->
        <el-form-item label="数据源">
          <el-select v-model="filterForm.api_source" placeholder="请选择数据源">
            <el-option label="新浪财经 (推荐)" value="sina"></el-option>
            <el-option label="东方财富" value="eastmoney"></el-option>
            <el-option label="AllTick API" value="alltick"></el-option>
          </el-select>
          
          <!-- AllTick Token输入 -->
          <el-input 
            v-if="filterForm.api_source === 'alltick'"
            v-model="filterForm.token"
            placeholder="AllTick API Token"
            style="margin-top: 10px; width: 300px;"
          ></el-input>
        </el-form-item>
        
        <!-- 降级策略 -->
        <el-form-item label="数据降级策略">
          <el-switch
            v-model="filterForm.degradation_enabled"
            active-text="启用"
            inactive-text="禁用"
          ></el-switch>
          
          <div v-if="filterForm.degradation_enabled" style="margin-top: 10px;">
            <el-radio-group v-model="filterForm.degradation_level">
              <el-radio label="LOW">轻度 (仅允许高可靠性数据源替代)</el-radio>
              <el-radio label="MEDIUM">中度 (允许替代数据分析方法)</el-radio>
              <el-radio label="HIGH">重度 (允许所有降级策略)</el-radio>
            </el-radio-group>
          </div>
        </el-form-item>
        
        <!-- 创建定时任务选项 -->
        <el-form-item>
          <el-checkbox v-model="createScheduledTask">同时创建为定时任务</el-checkbox>
        </el-form-item>
        
        <!-- 定时任务设置 -->
        <div v-if="createScheduledTask">
          <el-form-item label="任务名称">
            <el-input v-model="taskForm.name" placeholder="请输入任务名称"></el-input>
          </el-form-item>
          
          <el-form-item label="定时表达式">
            <el-row>
              <el-col :span="12">
                <el-input v-model="taskForm.schedule" placeholder="Cron表达式，例如：0 30 14 * * 1-5"></el-input>
              </el-col>
              <el-col :span="12" style="padding-left: 10px;">
                <el-button @click="setDefaultCron">设为每个工作日14:30</el-button>
              </el-col>
            </el-row>
            <span class="help-text">Cron表达式格式: 秒 分 时 日 月 星期</span>
          </el-form-item>
          
          <el-form-item label="任务描述">
            <el-input 
              type="textarea" 
              v-model="taskForm.description" 
              placeholder="任务描述 (可选)"
              :rows="2"
            ></el-input>
          </el-form-item>
        </div>
        
        <!-- 提交按钮 -->
        <el-form-item>
          <el-button 
            type="primary" 
            :loading="loading" 
            @click="startFilter"
          >
            开始筛选
          </el-button>
          <el-button @click="resetForm">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>
    
    <!-- 任务进度对话框 -->
    <el-dialog
      title="筛选任务进行中"
      :visible.sync="progressDialogVisible"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      :show-close="task.status === 'COMPLETED' || task.status === 'FAILED'"
    >
      <div class="progress-dialog">
        <el-progress 
          :percentage="task.progress || 0" 
          :status="progressStatus"
        ></el-progress>
        
        <div class="task-message">{{ task.message || '任务准备中...' }}</div>
        
        <div v-if="task.status === 'COMPLETED'" class="task-completed">
          <el-alert
            title="筛选完成"
            type="success"
            :closable="false"
            show-icon
          >
          </el-alert>
          <div class="dialog-buttons">
            <el-button type="primary" @click="viewResults">查看结果</el-button>
            <el-button @click="closeTaskDialog">关闭</el-button>
          </div>
        </div>
        
        <div v-if="task.status === 'FAILED'" class="task-error">
          <el-alert
            title="筛选失败"
            type="error"
            :closable="false"
            show-icon
          >
            <div>{{ task.message }}</div>
          </el-alert>
          <div class="dialog-buttons">
            <el-button @click="closeTaskDialog">关闭</el-button>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'

export default {
  name: 'FilterStart',
  data() {
    return {
      filterForm: {
        market: 'SH',
        api_source: 'sina',
        token: '',
        degradation_enabled: true,
        degradation_level: 'MEDIUM'
      },
      marketLabels: {
        'SH': '上证',
        'SZ': '深证',
        'BJ': '北证',
        'HK': '港股',
        'US': '美股'
      },
      loading: false,
      progressDialogVisible: false,
      progressUpdateInterval: null,
      createScheduledTask: false,
      taskForm: {
        name: '尾盘定时筛选',
        schedule: '0 30 14 * * 1-5',  // 默认每个工作日14:30
        description: '每个工作日尾盘自动执行八大步骤筛选策略'
      }
    }
  },
  computed: {
    ...mapGetters(['markets', 'currentFilterTask']),
    task() {
      return this.currentFilterTask || { status: 'PENDING', progress: 0, message: '任务准备中...' }
    },
    progressStatus() {
      const statusMap = {
        'COMPLETED': 'success',
        'FAILED': 'exception',
        'RUNNING': '',
        'PENDING': ''
      }
      return statusMap[this.task.status] || ''
    }
  },
  methods: {
    async startFilter() {
      try {
        this.loading = true
        
        // 构建筛选参数
        const filterParams = { ...this.filterForm }
        
        // 执行筛选
        const result = await this.$store.dispatch('startFilter', filterParams)
        
        if (result.success) {
          // 显示进度对话框
          this.progressDialogVisible = true
          
          // 启动进度更新定时器
          this.startProgressUpdate(result.taskId)
          
          // 如果需要创建定时任务
          if (this.createScheduledTask) {
            this.createTask(filterParams)
          }
        } else {
          this.$message.error(result.error || '启动筛选失败')
        }
      } catch (error) {
        this.$message.error('启动筛选出错')
        console.error('启动筛选出错', error)
      } finally {
        this.loading = false
      }
    },
    
    async createTask(filterParams) {
      try {
        // 创建定时任务参数
        const taskParams = {
          task_type: 'filter',
          schedule: this.taskForm.schedule,
          parameters: filterParams,
          name: this.taskForm.name,
          description: this.taskForm.description
        }
        
        // 创建定时任务
        const response = await this.$axios.post('/tasks', taskParams)
        this.$message.success('定时任务创建成功')
      } catch (error) {
        this.$message.error('定时任务创建失败：' + (error.response?.data?.error || '未知错误'))
      }
    },
    
    startProgressUpdate(taskId) {
      // 先立即获取一次状态
      this.updateTaskStatus(taskId)
      
      // 设置定时器每2秒获取一次任务状态
      this.progressUpdateInterval = setInterval(() => {
        this.updateTaskStatus(taskId)
      }, 2000)
    },
    
    async updateTaskStatus(taskId) {
      try {
        const result = await this.$store.dispatch('getFilterTaskStatus', taskId)
        
        // 如果任务已经完成或失败，停止定时器
        if (result.success && (result.data.status === 'COMPLETED' || result.data.status === 'FAILED')) {
          this.stopProgressUpdate()
        }
      } catch (error) {
        console.error('获取任务状态失败', error)
        this.stopProgressUpdate()
      }
    },
    
    stopProgressUpdate() {
      if (this.progressUpdateInterval) {
        clearInterval(this.progressUpdateInterval)
        this.progressUpdateInterval = null
      }
    },
    
    viewResults() {
      // 如果完成并且有结果ID，直接查看结果详情
      if (this.task.status === 'COMPLETED' && this.task.result_id) {
        this.$router.push(`/filter/results/${this.task.result_id}`)
      } else {
        // 否则查看结果列表
        this.$router.push('/filter/results')
      }
      this.closeTaskDialog()
    },
    
    closeTaskDialog() {
      this.progressDialogVisible = false
      this.stopProgressUpdate()
    },
    
    resetForm() {
      this.$refs.filterForm.resetFields()
      this.filterForm = {
        market: 'SH',
        api_source: 'sina',
        token: '',
        degradation_enabled: true,
        degradation_level: 'MEDIUM'
      }
      this.createScheduledTask = false
      this.taskForm = {
        name: '尾盘定时筛选',
        schedule: '0 30 14 * * 1-5',
        description: '每个工作日尾盘自动执行八大步骤筛选策略'
      }
    },
    
    setDefaultCron() {
      this.taskForm.schedule = '0 30 14 * * 1-5'  // 每个工作日14:30
    }
  },
  beforeDestroy() {
    // 组件销毁前清除定时器
    this.stopProgressUpdate()
  }
}
</script>

<style scoped>
.filter-start {
  max-width: 800px;
  margin: 0 auto;
}

.page-title {
  margin: 0;
  font-size: 20px;
  color: #303133;
}

.page-subtitle {
  margin: 5px 0 0;
  font-size: 14px;
  color: #606266;
}

.help-text {
  font-size: 12px;
  color: #909399;
  line-height: 1.2;
  display: block;
  margin-top: 5px;
}

.progress-dialog {
  padding: 20px 0;
}

.task-message {
  margin-top: 15px;
  text-align: center;
  color: #606266;
}

.task-completed,
.task-error {
  margin-top: 20px;
}

.dialog-buttons {
  margin-top: 20px;
  text-align: center;
}
</style> 