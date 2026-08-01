<template>
  <div class="mx-auto flex min-h-full w-full max-w-md flex-col justify-center py-10">
    <Card
      :title="'修改密码'"
      :description="auth.mustChangePassword ? '首次登录，请修改初始密码后继续使用系统。' : '定期更换密码有助于保障账号安全。'"
    >
      <form class="space-y-4" @submit.prevent="onSubmit">
        <div class="space-y-1.5">
          <Label for="old-password">原密码</Label>
          <Input
            id="old-password"
            v-model="form.old_password"
            type="password"
            autocomplete="current-password"
            placeholder="请输入当前密码"
          />
        </div>
        <div class="space-y-1.5">
          <Label for="new-password">新密码</Label>
          <Input
            id="new-password"
            v-model="form.new_password"
            type="password"
            autocomplete="new-password"
            placeholder="至少 6 位"
          />
        </div>
        <div class="space-y-1.5">
          <Label for="confirm-password">确认新密码</Label>
          <Input
            id="confirm-password"
            v-model="form.confirm_password"
            type="password"
            autocomplete="new-password"
            placeholder="再次输入新密码"
          />
        </div>

        <p v-if="errorMsg" class="flex items-start gap-1.5 text-sm text-destructive" role="alert">
          <TriangleAlert class="mt-0.5 h-4 w-4 shrink-0" />
          <span>{{ errorMsg }}</span>
        </p>

        <Button type="submit" class="w-full" :disabled="loading">
          <Spinner v-if="loading" class="mr-1.5 h-4 w-4" />
          {{ loading ? '提交中…' : '确认修改' }}
        </Button>
      </form>
    </Card>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import { TriangleAlert } from 'lucide-vue-next'
import Button from '@/components/ui/button.vue'
import Input from '@/components/ui/input.vue'
import Label from '@/components/ui/label.vue'
import Spinner from '@/components/ui/spinner.vue'
import Card from '@/components/ui/card.vue'

const router = useRouter()
const auth = useAuthStore()
const { success } = useToast()

const form = reactive({ old_password: '', new_password: '', confirm_password: '' })
const loading = ref(false)
const errorMsg = ref('')

async function onSubmit() {
  if (loading.value) return
  errorMsg.value = ''
  const { old_password, new_password, confirm_password } = form
  if (!old_password || !new_password) {
    errorMsg.value = '请填写原密码与新密码'
    return
  }
  if (new_password.length < 6) {
    errorMsg.value = '新密码长度不能少于 6 位'
    return
  }
  if (new_password !== confirm_password) {
    errorMsg.value = '两次输入的新密码不一致'
    return
  }
  if (old_password === new_password) {
    errorMsg.value = '新密码不能与原密码相同'
    return
  }
  loading.value = true
  try {
    await auth.changePassword(old_password, new_password)
    success('密码修改成功')
    // 改密成功后 must_change_password 已清除，守卫自动放行，回到首页。
    router.replace('/')
  } catch {
    // 后端 400（原密码错误等）由 http 拦截器提示，这里仅清空提交态。
  } finally {
    loading.value = false
  }
}
</script>
