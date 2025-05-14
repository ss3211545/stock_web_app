<template>
  <div id="app">
    <el-container v-if="isLoggedIn">
      <el-aside width="220px">
        <app-sidebar />
      </el-aside>
      <el-container>
        <el-header height="60px">
          <app-header />
        </el-header>
        <el-main>
          <router-view/>
        </el-main>
        <el-footer height="40px">
          <app-footer />
        </el-footer>
      </el-container>
    </el-container>
    
    <!-- 未登录状态只显示登录/注册页 -->
    <div v-else>
      <router-view/>
    </div>
  </div>
</template>

<script>
import AppHeader from '@/components/layout/AppHeader.vue'
import AppSidebar from '@/components/layout/AppSidebar.vue'
import AppFooter from '@/components/layout/AppFooter.vue'
import { mapGetters } from 'vuex'

export default {
  name: 'App',
  components: {
    AppHeader,
    AppSidebar,
    AppFooter
  },
  computed: {
    ...mapGetters(['isLoggedIn'])
  },
  created() {
    // 从localStorage恢复登录状态
    this.$store.dispatch('checkAuth')
  }
}
</script>

<style>
#app {
  font-family: 'Helvetica Neue', Helvetica, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  height: 100vh;
  color: #2c3e50;
  margin: 0;
  padding: 0;
}

body {
  margin: 0;
  padding: 0;
}

.el-header {
  background-color: #fff;
  color: #333;
  line-height: 60px;
  border-bottom: 1px solid #e6e6e6;
}

.el-aside {
  background-color: #304156;
  color: #fff;
}

.el-main {
  background-color: #f0f2f5;
  padding: 20px;
  height: calc(100vh - 100px);
  overflow: auto;
}

.el-footer {
  background-color: #fff;
  color: #999;
  text-align: center;
  line-height: 40px;
  font-size: 12px;
  border-top: 1px solid #e6e6e6;
}
</style> 