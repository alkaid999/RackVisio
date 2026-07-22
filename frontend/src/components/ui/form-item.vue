<script setup>
import { inject, computed } from 'vue'
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

function onValidate() {
  ctx && ctx.validateField(props.name)
}
</script>

<template>
  <div :class="cn('space-y-1.5', props.class)">
    <label v-if="label" class="text-sm font-medium text-foreground flex items-center gap-1.5">
      <component :is="icon" v-if="icon" class="h-3.5 w-3.5 text-muted-foreground" />
      {{ label }}
    </label>
    <div @focusout="onValidate">
      <slot />
    </div>
    <p v-if="hasError" class="text-xs font-medium text-destructive animate-fade-in">{{ ctx.errors[name] }}</p>
  </div>
</template>
