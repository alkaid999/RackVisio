<script setup>
import { cn } from '@/lib/utils'

const props = defineProps({
  title: { type: String, default: '暂无数据' },
  icon: { type: [Object, Function], default: null },
  class: { type: null, required: false },
})
</script>

<template>
  <div :class="cn('flex flex-col items-center justify-center py-16 text-center', props.class)">
    <component v-if="icon" :is="icon" class="mb-3 h-10 w-10 text-muted-foreground/50" />
    <p class="text-sm text-muted-foreground">{{ title }}</p>
    <slot />
  </div>
</template>
