import Vue from 'vue'
import VueRouter from 'vue-router'
import store from '../store'

Vue.use(VueRouter)

// 路由懒加载
const Login = () => import('../views/Login.vue')
const Register = () => import('../views/Register.vue')
const Dashboard = () => import('../views/Dashboard.vue')
const FilterStart = () => import('../views/filter/FilterStart.vue')
const FilterResult = () => import('../views/filter/FilterResult.vue')
const FilterResultDetail = () => import('../views/filter/FilterResultDetail.vue')
const StockDetail = () => import('../views/stock/StockDetail.vue')
const TaskList = () => import('../views/task/TaskList.vue')
const TaskCreate = () => import('../views/task/TaskCreate.vue')
const UserSettings = () => import('../views/user/UserSettings.vue')

// 路由配置
const routes = [
  {
    path: '/login',
    name: 'Login',
    component: Login,
    meta: { requiresAuth: false }
  },
  {
    path: '/register',
    name: 'Register',
    component: Register,
    meta: { requiresAuth: false }
  },
  {
    path: '/',
    name: 'Dashboard',
    component: Dashboard,
    meta: { requiresAuth: true }
  },
  {
    path: '/filter/start',
    name: 'FilterStart',
    component: FilterStart,
    meta: { requiresAuth: true }
  },
  {
    path: '/filter/results',
    name: 'FilterResults',
    component: FilterResult,
    meta: { requiresAuth: true }
  },
  {
    path: '/filter/results/:id',
    name: 'FilterResultDetail',
    component: FilterResultDetail,
    meta: { requiresAuth: true }
  },
  {
    path: '/stock/:code',
    name: 'StockDetail',
    component: StockDetail,
    meta: { requiresAuth: true }
  },
  {
    path: '/tasks',
    name: 'TaskList',
    component: TaskList,
    meta: { requiresAuth: true }
  },
  {
    path: '/tasks/create',
    name: 'TaskCreate',
    component: TaskCreate,
    meta: { requiresAuth: true }
  },
  {
    path: '/settings',
    name: 'UserSettings',
    component: UserSettings,
    meta: { requiresAuth: true }
  },
  {
    // 未匹配到路由时重定向到首页
    path: '*',
    redirect: '/'
  }
]

const router = new VueRouter({
  mode: 'history',
  base: process.env.BASE_URL,
  routes
})

// 全局导航守卫
router.beforeEach((to, from, next) => {
  // 检查路由是否需要身份验证
  if (to.matched.some(record => record.meta.requiresAuth)) {
    // 如果需要身份验证，检查是否已登录
    if (!store.getters.isLoggedIn) {
      // 未登录，重定向到登录页
      next({
        path: '/login',
        query: { redirect: to.fullPath }
      })
    } else {
      // 已登录，允许访问
      next()
    }
  } else {
    // 不需要身份验证的路由
    // 如果已登录且尝试访问登录/注册页，重定向到首页
    if (store.getters.isLoggedIn && (to.path === '/login' || to.path === '/register')) {
      next('/')
    } else {
      // 其他情况正常访问
      next()
    }
  }
})

export default router 