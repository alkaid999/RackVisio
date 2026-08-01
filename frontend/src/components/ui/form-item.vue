<script setup>
import { inject, computed, provide, ref } from 'vue'
import { cn } from '@/lib/utils'

const props = defineProps({
  name: { type: String, required: true },
  label: { type: String, default: '' },
  // 可选图标组件，渲染在 label 文字之前（如 lucide 的 Component）。
  icon: { type: [Object, Function, null], default: null },
  class: { type: null, required: false },
})

const ctx = inject('formContext', null)
const hasError = computed(() => ctx && !!ctx.errors[props.name])

// M-02/M-12：生成唯一 id 关联 label 与输入框（for/id 配对 + aria-invalid + aria-describedby）。
// 输入组件（input.vue）通过 inject('formItemContext') 消费，实现无障碍关联。
let uid = 0
const inputId = `fi-${Math.random().toString(36).slice(2, 8)}-${++uid}`
const errorId = `${inputId}-error`
provide('formItemContext', {
  inputId,
  errorId,
  hasError,
})

function onValidate() {
  ctx && ctx.validateField(props.name)
}
</script>

<template>
  <div :class="cn('space-y-1.5', props.class)">
    <label v-if="label" :for="inputId" class="text-sm font-medium text-foreground flex items-center gap-1.5">
      <component :is="icon" v-if="icon" class="h-3.5 w-3.5 text-muted-foreground" />
      {{ label }}
    </label>
    <div @focusout="onValidate">
      <slot />
    </div>
    <p v-if="hasError" :id="errorId" class="text-xs font-medium text-destructive animate-fade-in" role="alert">
      {{ ctx.errors[name] }}
    </p>
  </div>
</template>
