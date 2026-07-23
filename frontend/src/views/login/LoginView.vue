<template>
  <div class="login-screen">
    <!-- 背景装饰：柔光球，呼应全局设计语言 -->
    <div class="login-bg" aria-hidden="true">
      <div class="blob blob-1"></div>
      <div class="blob blob-2"></div>
      <div class="blob blob-3"></div>
    </div>

    <div class="login-card glass">
      <div class="brand">
        <div class="brand-logo"><RackLogo class="h-7 w-7" /></div>
        <h1 class="brand-title">RackVisio</h1>
        <p class="brand-sub">RackVisio · 机房机柜三维可视化与资产管理</p>
      </div>

      <form class="login-form" @submit.prevent="onSubmit">
        <div class="field">
          <Label for="username">用户名</Label>
          <div class="input-wrap">
            <User class="field-icon" />
            <Input
              id="username"
              v-model="form.username"
              class="pl-9"
              placeholder="请输入用户名"
              autocomplete="username"
              @keyup.enter="onSubmit"
            />
          </div>
        </div>

        <div class="field">
          <Label for="password">密码</Label>
          <div class="input-wrap">
            <Lock class="field-icon" />
            <Input
              id="password"
              v-model="form.password"
              type="password"
              class="pl-9"
              placeholder="请输入密码"
              autocomplete="current-password"
              @keyup.enter="onSubmit"
            />
          </div>
        </div>

        <p v-if="errorMsg" class="login-error" role="alert">
          <CircleAlert class="h-4 w-4 shrink-0" />
          <span>{{ errorMsg }}</span>
        </p>

        <Button
          type="submit"
          class="w-full"
          :disabled="loading"
          @click="onSubmit"
        >
          <Spinner v-if="loading" class="mr-1.5 h-4 w-4" />
          {{ loading ? '登录中…' : '登 录' }}
        </Button>
      </form>

      <p class="login-hint">默认管理员账号：<code>admin</code> / <code>admin123</code>（首次登录后请尽快修改）</p>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import { User, Lock, CircleAlert } from 'lucide-vue-next'
import Button from '@/components/ui/button.vue'
import Input from '@/components/ui/input.vue'
import Label from '@/components/ui/label.vue'
import Spinner from '@/components/ui/spinner.vue'
import RackLogo from '@/components/RackLogo.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { success } = useToast()

const form = reactive({ username: '', password: '' })
const loading = ref(false)
const errorMsg = ref('')

const redirect = computed(() => route.query.redirect || '/')

async function onSubmit() {
  if (loading.value) return
  errorMsg.value = ''
  const username = form.username.trim()
  const password = form.password
  if (!username || !password) {
    errorMsg.value = '请输入用户名和密码'
    return
  }
  loading.value = true
  try {
    await auth.login(username, password)
    success('登录成功')
    router.replace(redirect.value)
  } catch (e) {
    // 拦截器已 toast 具体原因（如「用户名或密码错误」），这里仅做内联提示兜底。
    errorMsg.value = (e && e.message) || '登录失败，请重试'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-screen {
  position: relative;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  overflow: hidden;
  background:
    radial-gradient(1200px 600px at 15% -10%, hsl(var(--primary) / 0.12), transparent 60%),
    radial-gradient(1000px 500px at 110% 110%, hsl(var(--primary) / 0.1), transparent 55%),
    hsl(var(--background));
}

.login-bg {
  position: absolute;
  inset: 0;
  pointer-events: none;
}
.blob {
  position: absolute;
  border-radius: 9999px;
  filter: blur(70px);
  opacity: 0.5;
}
.blob-1 {
  width: 380px;
  height: 380px;
  top: -120px;
  left: -80px;
  background: hsl(var(--primary) / 0.45);
}
.blob-2 {
  width: 320px;
  height: 320px;
  bottom: -100px;
  right: -60px;
  background: hsl(280 70% 60% / 0.35);
}
.blob-3 {
  width: 260px;
  height: 260px;
  top: 40%;
  right: 20%;
  background: hsl(190 80% 50% / 0.3);
}

.login-card {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 400px;
  padding: 36px 32px 28px;
  border-radius: 20px;
  background: hsl(var(--card) / 0.7);
  border: 1px solid hsl(var(--border));
  box-shadow: 0 30px 70px -30px rgb(15 23 42 / 0.45);
  animation: card-in 0.4s cubic-bezier(0.16, 1, 0.3, 1) both;
}
@keyframes card-in {
  from {
    opacity: 0;
    transform: translateY(14px) scale(0.98);
  }
  to {
    opacity: 1;
    transform: none;
  }
}

.brand {
  text-align: center;
  margin-bottom: 26px;
}
.brand-logo {
  width: 52px;
  height: 52px;
  margin: 0 auto 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 14px;
  background: linear-gradient(135deg, hsl(var(--primary)), hsl(var(--primary) / 0.7));
  color: #fff;
  font-weight: 700;
  font-size: 18px;
  box-shadow: 0 10px 26px -8px hsl(var(--primary) / 0.7);
}
.brand-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  letter-spacing: 0.02em;
}
.brand-sub {
  margin: 6px 0 0;
  font-size: 12.5px;
  color: hsl(var(--muted-foreground));
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 7px;
}
.input-wrap {
  position: relative;
}
.field-icon {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  width: 16px;
  height: 16px;
  color: hsl(var(--muted-foreground));
  pointer-events: none;
}

.login-error {
  display: flex;
  align-items: center;
  gap: 7px;
  margin: -2px 0 0;
  padding: 9px 12px;
  border-radius: 10px;
  background: hsl(var(--destructive) / 0.1);
  color: hsl(var(--destructive));
  font-size: 13px;
  animation: fade-in 0.2s ease;
}
@keyframes fade-in {
  from {
    opacity: 0;
    transform: translateY(-4px);
  }
  to {
    opacity: 1;
    transform: none;
  }
}

.login-hint {
  margin: 18px 0 0;
  text-align: center;
  font-size: 12px;
  color: hsl(var(--muted-foreground));
}
.login-hint code {
  padding: 1px 6px;
  border-radius: 6px;
  background: hsl(var(--muted));
  font-size: 12px;
}
</style>
