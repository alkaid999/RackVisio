<script setup>
import { Teleport, watch, onMounted, onUnmounted } from 'vue'
import { X } from 'lucide-vue-next'
import { cn } from '@/lib/utils'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, default: '' },
  description: { type: String, default: '' },
  class: { type: null, required: false },
  hideClose: { type: Boolean, default: false },
  // 是否允许点击遮罩/ESC 关闭（表单类弹窗建议 false，避免误触丢失填写内容）
  dismissible: { type: Boolean, default: true },
  // 容器层级：默认 z-50；确认对话框等需要高于其它弹窗时传入更高值（如 z-[60]）。
  zIndex: { type: String, default: 'z-50' },
})
const emit = defineEmits(['update:modelValue'])

// 多弹窗嵌套时共享的打开计数：仅当没有任何弹窗打开时才恢复背景滚动，
// 避免「详情弹窗内再弹确认框」时确认框关闭误把背景解锁。
let openCount = 0

function syncScroll() {
  if (typeof document === 'undefined') return
  document.body.style.overflow = openCount > 0 ? 'hidden' : ''
}
function close() {
  emit('update:modelValue', false)
}
function onOverlay() {
  if (props.dismissible) close()
}
function onKeydown(e) {
  if (e.key === 'Escape' && props.dismissible) close()
}

// 打开时锁定背景滚动 + 监听 ESC；关闭时还原（引用计数）。
watch(
  () => props.modelValue,
  (v) => {
    if (v) openCount++
    else if (openCount > 0) openCount--
    syncScroll()
  }
)
onMounted(() => {
  if (typeof window !== 'undefined') window.addEventListener('keydown', onKeydown)
})
onUnmounted(() => {
  if (typeof window !== 'undefined') window.removeEventListener('keydown', onKeydown)
  if (props.modelValue && openCount > 0) openCount--
  syncScroll()
})
</script>

<template>
  <Teleport to="body">
    <div
      v-if="modelValue"
      :class="cn('fixed inset-0 flex items-center justify-center p-4', zIndex)"
      role="dialog"
      aria-modal="true"
    >
      <div class="absolute inset-0 bg-black/50 backdrop-blur-sm" @click="onOverlay"></div>
      <div
        :class="
          cn(
            'relative z-10 grid w-full max-w-lg gap-4 border border-border bg-card p-6 shadow-card rounded-xl max-h-[90vh] overflow-y-auto',
            props.class
          )
        "
      >
        <h2 v-if="title" class="text-lg font-semibold tracking-tight pr-8">{{ title }}</h2>
        <p v-if="description" class="text-sm text-muted-foreground">{{ description }}</p>

        <slot />
        <slot name="footer" />

        <button
          v-if="!hideClose"
          type="button"
          class="absolute right-4 top-4 rounded-md p-1 text-muted-foreground opacity-70 transition hover:opacity-100 hover:bg-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          @click="close"
        >
          <X class="h-4 w-4" />
          <span class="sr-only">关闭</span>
        </button>
      </div>
    </div>
  </Teleport>
</template>
