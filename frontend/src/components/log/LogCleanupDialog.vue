<script setup>
import { ref } from 'vue'
import { Trash2 } from 'lucide-vue-next'
import { useToast } from '@/composables/useToast'
import logApi, { LOG_DEFAULT_RETENTION_DAYS } from '@/api/log'
import Button from '@/components/ui/button.vue'
import Input from '@/components/ui/input.vue'
import Label from '@/components/ui/label.vue'

// 手动清理日志对话框：触发按钮 + 确认弹窗。清理成功后 emits「cleaned」，
// 父页面据此刷新列表。保留期默认 180 天，可覆盖。
const emit = defineEmits(['cleaned'])

const open = ref(false)
const loading = ref(false)
const days = ref('')
const { success, error: toastError } = useToast()

async function confirm() {
  loading.value = true
  try {
    const payload = {}
    const d = Number(days.value)
    if (days.value !== '' && Number.isFinite(d) && d >= 1) {
      payload.days = Math.floor(d)
    }
    const res = await logApi.cleanup(payload)
    const data = res?.data ?? res
    // 后端 ok() 返回的字段为 operation_logs_deleted / login_logs_deleted（带 _logs_），
    // 此前误读为 operation_deleted / login_deleted 导致计数恒为 0（成功也显示「0 条」）。
    const op = data?.operation_logs_deleted ?? 0
    const lg = data?.login_logs_deleted ?? 0
    // 无过期日志（保留期内全部完好）时给明确提示，避免「0 条」让人误以为出错。
    if (op === 0 && lg === 0) {
      success('当前没有超过保留期的日志，无需清理')
    } else {
      success(`已清理操作日志 ${op} 条、登录日志 ${lg} 条`)
    }
    open.value = false
    days.value = ''
    emit('cleaned')
  } catch (e) {
    toastError(e?.message || '清理失败，请重试')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <Button variant="outline" @click="open = true">
    <Trash2 class="h-4 w-4" /> 清理日志
  </Button>

  <!-- 确认弹窗：Teleport 到 body，避免被布局祖先的 overflow/transform 裁剪 -->
  <Teleport to="body">
    <div v-if="open" class="cleanup-mask" @click.self="open = false">
      <div class="cleanup-panel" role="dialog" aria-modal="true">
        <div class="cleanup-head">
          <h3 class="cleanup-title">清理日志</h3>
          <button class="cleanup-close" @click="open = false" aria-label="关闭">×</button>
        </div>
        <div class="cleanup-body">
          <p class="text-sm text-muted-foreground">
            将永久删除保留期之前的<strong>操作日志</strong>与<strong>登录日志</strong>。此操作不可恢复，请确认后再执行。
          </p>
          <div class="flex flex-col gap-1.5 mt-4">
            <Label>保留天数（默认 {{ LOG_DEFAULT_RETENTION_DAYS }} 天）</Label>
            <Input
              v-model="days"
              type="number"
              min="1"
              :placeholder="`${LOG_DEFAULT_RETENTION_DAYS}`"
            />
          </div>
        </div>
        <div class="cleanup-foot">
          <Button variant="outline" :disabled="loading" @click="open = false">取消</Button>
          <Button :loading="loading" @click="confirm">确认清理</Button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.cleanup-mask {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.45);
  backdrop-filter: blur(2px);
}
.cleanup-panel {
  width: min(520px, 92vw);
  display: flex;
  flex-direction: column;
  background: hsl(var(--card));
  border: 1px solid hsl(var(--border));
  /* P2：圆角归一 20px → rounded-2xl(16px)，阴影走 shadow-card 令牌 */
  border-radius: 16px;
  box-shadow: var(--shadow-card);
  overflow: hidden;
}
.cleanup-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid hsl(var(--border) / 0.6);
}
.cleanup-title {
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 0.01em;
}
.cleanup-close {
  border: none;
  background: transparent;
  font-size: 16px;
  line-height: 1;
  color: hsl(var(--muted-foreground));
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 8px;
}
.cleanup-close:hover {
  background: hsl(var(--muted) / 0.6);
  color: hsl(var(--foreground));
}
.cleanup-body {
  padding: 16px 20px 20px;
}
.cleanup-foot {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 14px 20px;
  border-top: 1px solid hsl(var(--border) / 0.6);
}
</style>
