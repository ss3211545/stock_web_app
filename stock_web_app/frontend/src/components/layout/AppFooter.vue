<template>
  <div class="app-footer">
    <div>尾盘选股系统 &copy; {{ currentYear }} | 版本: v1.0</div>
  </div>
</template>

<script>
export default {
  name: 'AppFooter',
  computed: {
    currentYear() {
      return new Date().getFullYear()
    }
  }
}
</script>

<style scoped>
.app-footer {
  text-align: center;
  color: #909399;
  font-size: 12px;
}
</style> 