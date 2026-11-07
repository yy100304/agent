<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'

import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

const formRef = ref<FormInstance>()
const loading = ref(false)

const form = reactive({
  username: '',
  email: '',
  password: '',
  confirm: '',
})

const validateConfirm = (_rule: any, value: string, callback: any) => {
  if (value !== form.password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const rules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 32, message: '长度 3 - 32 字符', trigger: 'blur' },
  ],
  email: [
    { type: 'email', message: '邮箱格式不正确', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 64, message: '长度 6 - 64 字符', trigger: 'blur' },
  ],
  confirm: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    { validator: validateConfirm, trigger: 'blur' },
  ],
}

async function onSubmit() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    loading.value = true
    try {
      await userStore.doRegister({
        username: form.username,
        password: form.password,
        email: form.email || undefined,
      })
      ElMessage.success('注册成功，已自动登录')
      router.push('/dashboard')
    } catch (e) {
      console.error(e)
    } finally {
      loading.value = false
    }
  })
}

function goLogin() {
  router.push({ name: 'Login' })
}
</script>

<template>
  <div class="auth-page">
    <div class="auth-bg" />

    <div class="auth-card">
      <div class="auth-header">
        <div class="brand-mark">S</div>
        <h1 class="brand-title">创建账号</h1>
        <p class="brand-subtitle">开启你的智能学习之旅</p>
      </div>

      <el-form ref="formRef" :model="form" :rules="rules" size="large" class="auth-form" @keyup.enter="onSubmit">
        <el-form-item prop="username">
          <el-input v-model="form.username" placeholder="用户名（3-32 位）" :prefix-icon="'User'" clearable />
        </el-form-item>
        <el-form-item prop="email">
          <el-input v-model="form.email" placeholder="邮箱（可选）" :prefix-icon="'Message'" clearable />
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="密码（至少 6 位）"
            :prefix-icon="'Lock'"
            show-password
          />
        </el-form-item>
        <el-form-item prop="confirm">
          <el-input
            v-model="form.confirm"
            type="password"
            placeholder="再次输入密码"
            :prefix-icon="'Lock'"
            show-password
          />
        </el-form-item>
        <el-button type="primary" :loading="loading" class="submit-btn" @click="onSubmit">
          注册并登录
        </el-button>
      </el-form>

      <div class="auth-footer">
        <span class="muted">已有账号？</span>
        <el-link type="primary" :underline="false" @click="goLogin">返回登录</el-link>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
@use '@/styles/variables.scss' as *;

.auth-page {
  position: relative;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: $gap-lg;
  overflow: hidden;
}

.auth-bg {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse at top left, rgba(124, 92, 255, 0.16), transparent 55%),
    radial-gradient(ellipse at bottom right, rgba(79, 124, 247, 0.18), transparent 55%),
    $bg-page;
  z-index: 0;
}

.auth-card {
  position: relative;
  z-index: 1;
  width: 460px;
  max-width: 100%;
  background: $bg-card;
  border-radius: $radius-lg;
  padding: 40px 36px;
  box-shadow: $shadow-lg;
  border: 1px solid $border-light;
}

.auth-header {
  text-align: center;
  margin-bottom: 24px;
}

.brand-mark {
  width: 48px;
  height: 48px;
  border-radius: 14px;
  margin: 0 auto 12px;
  background: linear-gradient(135deg, #4f7cf7, #7c5cff);
  color: #fff;
  font-size: 20px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
}

.brand-title {
  margin: 0;
  font-size: 22px;
  font-weight: 600;
  color: $text-primary;
}

.brand-subtitle {
  margin: 6px 0 0;
  color: $text-secondary;
  font-size: 13px;
}

.auth-form {
  display: flex;
  flex-direction: column;
}

.submit-btn {
  width: 100%;
  height: 44px;
  font-size: 15px;
  margin-top: 4px;
}

.auth-footer {
  margin-top: 18px;
  text-align: center;
  font-size: 13px;
}

.muted {
  color: $text-secondary;
  margin-right: 4px;
}
</style>