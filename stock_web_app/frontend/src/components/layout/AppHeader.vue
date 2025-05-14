<template>
  <div class="app-header">
    <div class="app-header__left">
      <h1 class="app-title">尾盘选股系统</h1>
      <span class="app-version">v1.0</span>
    </div>
    <div class="app-header__right">
      <el-dropdown trigger="click" @command="handleCommand">
        <span class="el-dropdown-link">
          {{ user.username }} <i class="el-icon-arrow-down"></i>
        </span>
        <el-dropdown-menu slot="dropdown">
          <el-dropdown-item command="settings">设置</el-dropdown-item>
          <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
        </el-dropdown-menu>
      </el-dropdown>
    </div>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'

export default {
  name: 'AppHeader',
  computed: {
    ...mapGetters(['user'])
  },
  methods: {
    handleCommand(command) {
      if (command === 'logout') {
        this.$store.dispatch('logout')
        this.$router.push('/login')
      } else if (command === 'settings') {
        this.$router.push('/settings')
      }
    }
  }
}
</script>

<style scoped>
.app-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 100%;
  padding: 0 20px;
}

.app-header__left {
  display: flex;
  align-items: center;
}

.app-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #3498db;
}

.app-version {
  margin-left: 10px;
  font-size: 12px;
  color: #999;
}

.el-dropdown-link {
  cursor: pointer;
  color: #409EFF;
}
</style> 