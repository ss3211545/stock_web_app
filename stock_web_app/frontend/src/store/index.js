import Vue from 'vue'
import Vuex from 'vuex'
import axios from 'axios'
import jwt_decode from 'jwt-decode'

Vue.use(Vuex)

export default new Vuex.Store({
  state: {
    token: localStorage.getItem('token') || '',
    user: JSON.parse(localStorage.getItem('user') || '{}'),
    filterResults: [],
    currentFilterTask: null,
    scheduledTasks: [],
    activeStockCode: null,
    activeStockData: null,
    markets: ['SH', 'SZ', 'BJ', 'HK', 'US']
  },
  getters: {
    isLoggedIn: state => !!state.token,
    token: state => state.token,
    user: state => state.user,
    filterResults: state => state.filterResults,
    currentFilterTask: state => state.currentFilterTask,
    scheduledTasks: state => state.scheduledTasks,
    activeStockCode: state => state.activeStockCode,
    activeStockData: state => state.activeStockData,
    markets: state => state.markets
  },
  mutations: {
    // 用户相关
    setToken(state, token) {
      state.token = token
      localStorage.setItem('token', token)
    },
    setUser(state, user) {
      state.user = user
      localStorage.setItem('user', JSON.stringify(user))
    },
    clearAuth(state) {
      state.token = ''
      state.user = {}
      localStorage.removeItem('token')
      localStorage.removeItem('user')
    },
    
    // 筛选结果相关
    setFilterResults(state, results) {
      state.filterResults = results
    },
    setCurrentFilterTask(state, task) {
      state.currentFilterTask = task
    },
    
    // 定时任务相关
    setScheduledTasks(state, tasks) {
      state.scheduledTasks = tasks
    },
    
    // 股票详情相关
    setActiveStockCode(state, code) {
      state.activeStockCode = code
    },
    setActiveStockData(state, data) {
      state.activeStockData = data
    }
  },
  actions: {
    // 用户认证相关
    async login({ commit }, credentials) {
      try {
        const response = await axios.post('/auth/login', credentials)
        const token = response.data.access_token
        const user = response.data.user
        
        commit('setToken', token)
        commit('setUser', user)
        
        return {
          success: true,
          data: response.data
        }
      } catch (error) {
        return {
          success: false,
          error: error.response?.data?.error || '登录失败'
        }
      }
    },
    
    async register({ commit }, userData) {
      try {
        const response = await axios.post('/auth/register', userData)
        const token = response.data.access_token
        const user = response.data.user
        
        commit('setToken', token)
        commit('setUser', user)
        
        return {
          success: true,
          data: response.data
        }
      } catch (error) {
        return {
          success: false,
          error: error.response?.data?.error || '注册失败'
        }
      }
    },
    
    logout({ commit }) {
      commit('clearAuth')
    },
    
    // 检查存储的令牌是否有效
    checkAuth({ commit, state }) {
      if (!state.token) {
        return
      }
      
      try {
        // 解码令牌以检查是否过期
        const decodedToken = jwt_decode(state.token)
        const currentTime = Date.now() / 1000
        
        if (decodedToken.exp < currentTime) {
          // 令牌已过期
          commit('clearAuth')
        }
      } catch (error) {
        // 令牌无效
        commit('clearAuth')
      }
    },
    
    // 筛选相关
    async startFilter({ commit }, filterParams) {
      try {
        const response = await axios.post('/filter/run', filterParams)
        commit('setCurrentFilterTask', {
          id: response.data.task_id,
          status: 'PENDING',
          progress: 0
        })
        
        return {
          success: true,
          taskId: response.data.task_id
        }
      } catch (error) {
        return {
          success: false,
          error: error.response?.data?.error || '启动筛选失败'
        }
      }
    },
    
    async getFilterTaskStatus({ commit }, taskId) {
      try {
        const response = await axios.get(`/filter/status/${taskId}`)
        commit('setCurrentFilterTask', response.data)
        
        return {
          success: true,
          data: response.data
        }
      } catch (error) {
        return {
          success: false,
          error: error.response?.data?.error || '获取任务状态失败'
        }
      }
    },
    
    async getFilterResults({ commit }, page = 1) {
      try {
        const response = await axios.get('/filter/results', {
          params: { page, per_page: 10 }
        })
        
        commit('setFilterResults', response.data)
        
        return {
          success: true,
          data: response.data
        }
      } catch (error) {
        return {
          success: false,
          error: error.response?.data?.error || '获取筛选结果失败'
        }
      }
    },
    
    // 定时任务相关
    async getScheduledTasks({ commit }) {
      try {
        const response = await axios.get('/tasks')
        commit('setScheduledTasks', response.data.tasks)
        
        return {
          success: true,
          data: response.data
        }
      } catch (error) {
        return {
          success: false,
          error: error.response?.data?.error || '获取定时任务失败'
        }
      }
    },
    
    // 股票相关
    async getStockData({ commit }, stockCode) {
      try {
        const response = await axios.get(`/stocks/${stockCode}`)
        commit('setActiveStockCode', stockCode)
        commit('setActiveStockData', response.data)
        
        return {
          success: true,
          data: response.data
        }
      } catch (error) {
        return {
          success: false,
          error: error.response?.data?.error || '获取股票数据失败'
        }
      }
    }
  }
}) 