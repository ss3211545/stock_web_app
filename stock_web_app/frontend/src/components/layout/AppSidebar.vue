<template>
  <div class="app-sidebar">
    <div class="app-sidebar__logo">
      <img src="@/assets/logo.png" alt="Logo" class="logo-img">
    </div>
    <el-menu
      default-active="1"
      class="el-menu-vertical"
      background-color="#304156"
      text-color="#bfcbd9"
      active-text-color="#409EFF"
      :router="true"
      :unique-opened="true"
      :collapse-transition="false"
    >
      <el-menu-item index="/">
        <i class="el-icon-s-home"></i>
        <span slot="title">首页</span>
      </el-menu-item>
      
      <el-submenu index="2">
        <template slot="title">
          <i class="el-icon-s-operation"></i>
          <span>股票筛选</span>
        </template>
        <el-menu-item index="/filter/start">
          <i class="el-icon-menu"></i>
          <span slot="title">开始筛选</span>
        </el-menu-item>
        <el-menu-item index="/filter/results">
          <i class="el-icon-s-data"></i>
          <span slot="title">筛选结果</span>
        </el-menu-item>
      </el-submenu>
      
      <el-menu-item index="/tasks">
        <i class="el-icon-time"></i>
        <span slot="title">定时任务</span>
      </el-menu-item>
      
      <el-menu-item index="/settings">
        <i class="el-icon-setting"></i>
        <span slot="title">设置</span>
      </el-menu-item>
    </el-menu>
  </div>
</template>

<script>
export default {
  name: 'AppSidebar'
}
</script>

<style scoped>
.app-sidebar {
  height: 100%;
  overflow-y: auto;
}

.app-sidebar__logo {
  height: 60px;
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: #263445;
}

.logo-img {
  height: 40px;
}

.el-menu {
  border-right: none;
}

.el-menu-vertical {
  height: calc(100vh - 60px);
}
</style> 