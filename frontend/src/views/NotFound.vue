<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { FileQuestion, Home, ArrowLeft } from 'lucide-vue-next'
import Button from '@/components/ui/button.vue'

const route = useRoute()
const router = useRouter()

// 展示用户实际访问的路径，便于反馈"你点的是什么"。
const attemptedPath = computed(() => route.fullPath || '/')
</script>

<template>
  <div
    class="relative flex min-h-screen items-center justify-center overflow-hidden bg-background px-4 text-foreground"
  >
    <!-- 背景柔光装饰：呼应登录页设计语言 -->
    <div class="pointer-events-none absolute inset-0 -z-10 overflow-hidden" aria-hidden="true">
      <div class="nf-blob nf-blob-1"></div>
      <div class="nf-blob nf-blob-2"></div>
    </div>

    <div class="glass relative z-10 w-full max-w-md rounded-2xl px-8 py-12 text-center shadow-xl">
      <div
        class="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-muted text-muted-foreground"
      >
        <FileQuestion class="h-12 w-12" />
      </div>

      <h1
        class="bg-gradient-to-r from-brand-500 to-brand-700 bg-clip-text text-6xl font-extrabold tracking-tight text-transparent"
      >
        404
      </h1>
      <h2 class="mt-2 text-2xl font-semibold">页面走丢了</h2>

      <p class="mt-3 text-sm text-muted-foreground">
        你访问的路径
        <code class="rounded bg-muted px-1.5 py-0.5 font-mono text-xs text-foreground">{{
          attemptedPath
        }}</code>
        不存在或已被移动。
      </p>

      <div class="mt-8 flex items-center justify-center gap-3">
        <Button @click="router.push('/')">
          <Home class="h-4 w-4" /> 返回首页
        </Button>
        <Button variant="outline" @click="router.back()">
          <ArrowLeft class="h-4 w-4" /> 返回上页
        </Button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.nf-blob {
  position: absolute;
  border-radius: 9999px;
  filter: blur(60px);
  opacity: 0.25;
}
.nf-blob-1 {
  top: -6rem;
  left: -6rem;
  height: 24rem;
  width: 24rem;
  background: #38bdf8;
}
.nf-blob-2 {
  bottom: -6rem;
  right: -6rem;
  height: 24rem;
  width: 24rem;
  background: #818cf8;
}
</style>
