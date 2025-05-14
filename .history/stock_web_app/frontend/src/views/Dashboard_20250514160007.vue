<template>
  <div class="dashboard">
    <el-row :gutter="20">
      <!-- 欢迎信息卡片 -->
      <el-col :xs="24" :sm="24" :md="24" :lg="24">
        <el-card class="welcome-card">
          <div class="welcome-content">
            <div class="welcome-text">
              <h2>欢迎回来，{{ user.username }}</h2>
              <p>尾盘八大步骤选股系统为您提供专业的股票筛选服务</p>
            </div>
            <div class="welcome-actions">
              <el-button type="primary" @click="startNewFilter">开始新筛选</el-button>
              <el-button @click="viewResults">查看历史结果</el-button>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
    
    <el-row :gutter="20" class="dashboard-row">
      <!-- 统计信息卡片 -->
      <el-col :xs="24" :sm="12" :md="8" :lg="6">
        <el-card class="dashboard-card">
          <div slot="header" class="card-header">
            <span>已保存筛选结果</span>
          </div>
          <div class="card-body">
            <div class="metric">
              <span class="metric-value">{{ filterResultsCount }}</span>
              <el-button type="text" @click="viewResults">查看详情</el-button>
            </div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :xs="24" :sm="12" :md="8" :lg="6">
        <el-card class="dashboard-card">
          <div slot="header" class="card-header">
            <span>定时任务</span>
          </div>
          <div class="card-body">
            <div class="metric">
              <span class="metric-value">{{ scheduledTasksCount }}</span>
              <el-button type="text" @click="viewTasks">查看详情</el-button>
            </div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :xs="24" :sm="12" :md="8" :lg="6">
        <el-card class="dashboard-card">
          <div slot="header" class="card-header">
            <span>市场状态</span>
          </div>
          <div class="card-body">
            <div class="metric market-status">
              <span :class="['status-indicator', marketStatusClass]"></span>
              <span class="metric-value">{{ marketStatus }}</span>
            </div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :xs="24" :sm="12" :md="8" :lg="6">
        <el-card class="dashboard-card">
          <div slot="header" class="card-header">
            <span>数据源状态</span>
          </div>
          <div class="card-body">
            <div class="metric">
              <span :class="['status-indicator', dataSourceStatusClass]"></span>
              <span class="metric-value">{{ dataSourceStatus }}</span>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
    
    <el-row :gutter="20" class="dashboard-row">
      <!-- 最近筛选结果 -->
      <el-col :xs="24" :sm="24" :md="12">
        <el-card class="dashboard-card">
          <div slot="header" class="card-header">
            <span>最近筛选结果</span>
            <el-button style="float: right; padding: 3px 0" type="text" @click="viewResults">
              查看全部
            </el-button>
          </div>
          <div class="card-body">
            <el-table
              v-if="recentResults.length > 0"
              :data="recentResults"
              style="width: 100%"
              size="small"
            >
              <el-table-column prop="market" label="市场" width="70"></el-table-column>
              <el-table-column prop="timestamp" label="时间" :formatter="formatDate"></el-table-column>
              <el-table-column prop="matched_count" label="匹配数量" width="90"></el-table-column>
              <el-table-column label="操作" width="90">
                <template slot-scope="scope">
                  <el-button 
                    type="text" 
                    size="small" 
                    @click="viewResultDetail(scope.row.id)"
                  >
                    查看
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
            <div v-else class="empty-data">
              <span>暂无筛选结果</span>
            </div>
          </div>
        </el-card>
      </el-col>
      
      <!-- 定时任务 -->
      <el-col :xs="24" :sm="24" :md="12">
        <el-card class="dashboard-card">
          <div slot="header" class="card-header">
            <span>定时任务</span>
            <el-button style="float: right; padding: 3px 0" type="text" @click="viewTasks">
              查看全部
            </el-button>
          </div>
          <div class="card-body">
            <el-table
              v-if="scheduledTasks.length > 0"
              :data="scheduledTasks.slice(0, 5)"
              style="width: 100%"
              size="small"
            >
              <el-table-column prop="name" label="名称"></el-table-column>
              <el-table-column label="状态" width="80">
                <template slot-scope="scope">
                  <el-tag 
                    :type="scope.row.is_active ? 'success' : 'info'" 
                    size="mini"
                  >
                    {{ scope.row.is_active ? '启用' : '禁用' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="next_run" label="下次运行" :formatter="formatDate"></el-table-column>
            </el-table>
            <div v-else class="empty-data">
              <span>暂无定时任务</span>
              <el-button size="small" type="primary" @click="createTask">创建任务</el-button>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'
import moment from 'moment'

export default {
  name: 'Dashboard',
  data() {
    return {
      recentResults: [],
      filterResultsCount: 0,
      scheduledTasksCount: 0,
      marketStatus: '交易中',
      dataSourceStatus: '正常'
    }
  },
  computed: {
    ...mapGetters(['user', 'scheduledTasks']),
    marketStatusClass() {
      const statusMap = {
        '交易中': 'status-success',
        '已收盘': 'status-warning',
        '休市': 'status-info'
      }
      return statusMap[this.marketStatus] || 'status-info'
    },
    dataSourceStatusClass() {
      const statusMap = {
        '正常': 'status-success',
        '部分可用': 'status-warning',
        '不可用': 'status-error'
      }
      return statusMap[this.dataSourceStatus] || 'status-info'
    }
  },
  created() {
    this.fetchData()
  },
  methods: {
    async fetchData() {
      try {
        // 获取筛选结果
        const filterResult = await this.$store.dispatch('getFilterResults')
        if (filterResult.success) {
          this.recentResults = filterResult.data.results.slice(0, 5)
          this.filterResultsCount = filterResult.data.total
        }
        
        // 获取定时任务
        const tasksResult = await this.$store.dispatch('getScheduledTasks')
        if (tasksResult.success) {
          this.scheduledTasksCount = tasksResult.data.count
        }
        
        // 检查市场状态
        this.checkMarketStatus()
        
        // 检查数据源状态
        this.checkDataSourceStatus()
      } catch (error) {
        console.error('获取数据失败', error)
        this.$message.error('获取数据失败，请刷新重试')
      }
    },
    
    checkMarketStatus() {
      // 在实际应用中，这里应该通过API检查市场状态
      const now = new Date()
      const hour = now.getHours()
      const day = now.getDay()
      
      // 周末判断
      if (day === 0 || day === 6) {
        this.marketStatus = '休市'
        return
      }
      
      // 交易时间判断 (9:30 - 15:00)
      if ((hour >= 9 && hour < 15) || (hour === 9 && now.getMinutes() >= 30)) {
        this.marketStatus = '交易中'
      } else {
        this.marketStatus = '已收盘'
      }
    },
    
    checkDataSourceStatus() {
      // 在实际应用中，这里应该通过API检查数据源状态
      this.dataSourceStatus = '正常'
    },
    
    formatDate(row, column, cellValue) {
      if (!cellValue) return '-'
      return moment(cellValue).format('YYYY-MM-DD HH:mm')
    },
    
    startNewFilter() {
      this.$router.push('/filter/start')
    },
    
    viewResults() {
      this.$router.push('/filter/results')
    },
    
    viewResultDetail(id) {
      this.$router.push(`/filter/results/${id}`)
    },
    
    viewTasks() {
      this.$router.push('/tasks')
    },
    
    createTask() {
      this.$router.push('/tasks/create')
    }
  }
}
</script>

<style scoped>
.dashboard {
  padding: 10px;
}

.dashboard-row {
  margin-top: 20px;
}

.welcome-card {
  margin-bottom: 20px;
}

.welcome-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.welcome-text h2 {
  font-size: 24px;
  margin-bottom: 10px;
  color: #303133;
}

.welcome-text p {
  color: #606266;
  margin: 0;
}

.dashboard-card {
  margin-bottom: 20px;
  height: 100%;
}

.card-header {
  font-weight: bold;
}

.card-body {
  padding: 10px 0;
}

.metric {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.metric-value {
  font-size: 24px;
  font-weight: bold;
  color: #303133;
}

.market-status {
  display: flex;
  align-items: center;
}

.status-indicator {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  margin-right: 10px;
}

.status-success {
  background-color: #67C23A;
}

.status-warning {
  background-color: #E6A23C;
}

.status-error {
  background-color: #F56C6C;
}

.status-info {
  background-color: #909399;
}

.empty-data {
  text-align: center;
  color: #909399;
  padding: 20px 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
}

@media (max-width: 768px) {
  .welcome-content {
    flex-direction: column;
    text-align: center;
  }
  
  .welcome-actions {
    margin-top: 15px;
  }
  
  .metric {
    flex-direction: column;
    text-align: center;
  }
  
  .market-status {
    justify-content: center;
  }
}
</style> 