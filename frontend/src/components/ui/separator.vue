<script setup>
import { cn } from '@/lib/utils'

const props = defineProps({
  class: { type: null, required: false },
  orientation: { type: String, default: 'horizontal' },
  label: { type: String, default: '' },
})
</script>

<template>
  <div
    v-if="label"
    role="separator"
    :class="cn('flex items-center gap-3 text-xs text-muted-foreground', props.class)"
  >
    <span class="h-px flex-1 bg-border" />
    <span>{{ label }}</span>
    <span class="h-px flex-1 bg-border" />
  </div>
  <div
    v-else
    role="separator"
    :class="cn('bg-border', props.orientation === 'vertical' ? 'h-full w-px' : 'h-px w-full', props.class)"
  />
</template>
