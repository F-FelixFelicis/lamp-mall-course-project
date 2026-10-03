<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { clearToken, currentAdmin, login, token, type User } from './api'
import ReviewDesk from './ReviewDesk.vue'

const account = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')
const user = ref<User | null>(null)

async function loadCurrent() {
  if (!token()) return
  try { user.value = await currentAdmin() }
  catch { clearToken(); user.value = null }
}

async function submit() {
  error.value = ''
  loading.value = true
  try {
    await login(account.value, password.value)
    user.value = await currentAdmin()
  } catch (cause) {
    clearToken()
    error.value = cause instanceof Error ? cause.message : '登录失败'
  } finally { loading.value = false }
}

function logout() { clearToken(); user.value = null; password.value = '' }
onMounted(loadCurrent)
</script>

<template>
  <ReviewDesk v-if="user" :name="user.display_name" @logout="logout" />
  <div v-else class="app-shell">
    <aside class="brand-panel">
      <div class="brand"><span class="brand-mark">◉</span> LUMIÈRE <span class="brand-sub">灯具商城</span></div>
      <div class="brand-copy">
        <span class="eyebrow">STORE OPERATIONS</span>
        <h1>让每盏灯，<br />都有清晰的来处。</h1>
        <p>商家认证、商品与报价审核，以及后续订单运营，都从同一套可信的数据开始。</p>
      </div>
      <span class="brand-foot">课程综合项目 · 管理端 v0.1</span>
    </aside>
    <main class="main-panel">
      <div v-if="!user" class="card">
        <span class="eyebrow dark">ADMIN CONSOLE</span>
        <h2>欢迎回来</h2>
        <p class="subtitle">使用管理员账号登录，开始管理灯具商城。</p>
        <form @submit.prevent="submit">
          <label>账号<input v-model.trim="account" autocomplete="username" placeholder="管理员用户名" required /></label>
          <label>密码<input v-model="password" type="password" autocomplete="current-password" placeholder="请输入密码" required /></label>
          <p v-if="error" class="error" role="alert">{{ error }}</p>
          <button :disabled="loading" type="submit">{{ loading ? '正在验证…' : '登录管理端' }} <span>→</span></button>
        </form>
        <p class="hint">首次管理员账号由项目组在后端命令行创建。</p>
      </div>
    </main>
  </div>
</template>
