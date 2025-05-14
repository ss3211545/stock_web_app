<template>
  <div class="login-container">
    <div class="login-card">
      <div class="login-header">
        <h2>尾盘选股系统</h2>
        <p>基于八大步骤的专业选股策略</p>
      </div>
      
      <el-form :model="loginForm" :rules="loginRules" ref="loginForm" class="login-form">
        <el-form-item prop="username">
          <el-input 
            v-model="loginForm.username" 
            prefix-icon="el-icon-user" 
            placeholder="用户名或邮箱"
            @keyup.enter.native="submitForm"
          ></el-input>
        </el-form-item>
        
        <el-form-item prop="password">
          <el-input 
            v-model="loginForm.password" 
            prefix-icon="el-icon-lock" 
            type="password" 
            placeholder="密码"
            @keyup.enter.native="submitForm"
          ></el-input>
        </el-form-item>
        
        <el-form-item>
          <el-button 
            type="primary" 
            :loading="loading" 
            class="login-button" 
            @click="submitForm"
          >登录</el-button>
        </el-form-item>
      </el-form>
      
      <div class="login-options">
        <router-link to="/register">注册新账号</router-link>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'Login',
  data() {
    return {
      loginForm: {
        username: '',
        password: ''
      },
      loginRules: {
        username: [
          { required: true, message: '请输入用户名或邮箱', trigger: 'blur' }
        ],
        password: [
          { required: true, message: '请输入密码', trigger: 'blur' },
          { min: 8, message: '密码长度不能小于8个字符', trigger: 'blur' }
        ]
      },
      loading: false
    }
  },
  methods: {
    async submitForm() {
      try {
        await this.$refs.loginForm.validate()
        
        this.loading = true
        const result = await this.$store.dispatch('login', this.loginForm)
        this.loading = false
        
        if (result.success) {
          // 登录成功，重定向到首页或指定的URL
          const redirectPath = this.$route.query.redirect || '/'
          this.$router.push(redirectPath)
          this.$message.success('登录成功')
        } else {
          this.$message.error(result.error)
        }
      } catch (error) {
        // 表单验证失败
        this.loading = false
        console.error('表单验证失败', error)
      }
    }
  }
}
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background-color: #f0f2f5;
}

.login-card {
  width: 400px;
  padding: 40px;
  background-color: #fff;
  border-radius: 4px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}

.login-header {
  text-align: center;
  margin-bottom: 30px;
}

.login-header h2 {
  font-size: 24px;
  color: #409EFF;
  margin-bottom: 10px;
}

.login-header p {
  color: #909399;
  font-size: 14px;
}

.login-form {
  margin-top: 20px;
}

.login-button {
  width: 100%;
}

.login-options {
  margin-top: 20px;
  text-align: center;
}

.login-options a {
  color: #409EFF;
  text-decoration: none;
}
</style> 