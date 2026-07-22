<script setup>
import { cn } from '@/lib/utils'

const props = defineProps({
  class: { type: null, required: false },
  type: { type: String, default: 'text' },
})
// 支持 v-model；type=number 时自动转为数值，对齐原 el-input-number 行为。
const model = defineModel({
  set(v) {
    if (props.type === 'number') return v === '' || v === null ? '' : Number(v)
    return v
  },
})
</script>

<template>
  <input
    v-model="model"
    :type="type"
    :class="
      cn(
        'flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-50',
        props.class
      )
    "
  />
</template>
