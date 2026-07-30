<template>
  <!-- 渲染兜底：任意子组件同步/异步渲染抛错都会被 onErrorCaptured 捕获，
       避免单个视图崩溃导致整站白屏；提供「重试」与「返回首页」两种恢复路径。 -->
  <div v-if="error" class="flex min-h-[40vh] w-full items-center justify-center p-6">
    <div
      class="w-full max-w-lg rounded-2xl border border-destructive/25 bg-card/80 p-8 text-center shadow-soft backdrop-blur"
      role="alert"
    >
      <div
        class="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-destructive/10 text-destructive"
      >
        <TriangleAlert class="h-6 w-6" />
      </div>
      <h2 class="text-lg font-semibold text-foreground">页面渲染出错了</h2>
      <p class="mt-2 text-sm text-muted-foreground">
        该模块遇到了意外错误，但其它功能仍可正常使用。可尝试重试，或返回首页。
      </p>
      <p class="mt-3 break-words font-mono text-xs text-destructive/80">{{ message }}</p>
      <pre
        v-if="details"
        class="mt-3 max-h-40 overflow-auto rounded-lg bg-muted/70 p-3 text-left font-mono text-[11px] leading-relaxed text-muted-foreground scroll-thin"
        >{{ details }}</pre
      >
      <div class="mt-6 flex items-center justify-center gap-3">
        <Button variant="outline" @click="goHome">返回首页</Button>
        <Button @click="reset">重试</Button>
      </div>
    </div>
  </div>
  <slot v-else />
</template>

<script setup>
import { ref, onErrorCaptured } from 'vue'
import { useRouter } from 'vue-router'
import { TriangleAlert } from 'lucide-vue-next'
import Button from '@/components/ui/button.vue'

const router = useRouter()
const error = ref(null)
const message = ref('')
const details = ref('')

function reset() {
  error.value = null
  message.value = ''
  details.value = ''
}

function goHome() {
  reset()
  router.push('/')
}

// 捕获子树渲染错误：记录日志并返回 false 阻止错误继续向上冒泡（避免整站崩溃）。
onErrorCaptured((err, _instance, info) => {
  console.error('[ErrorBoundary] 捕获到渲染错误:', err, info)
  message.value = err?.message || '发生未知错误'
  details.value = (err?.stack || String(err)).toString().slice(0, 1200)
  return false
})
</script>
