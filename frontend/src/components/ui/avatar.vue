<script setup>
import { cn } from '@/lib/utils'

const props = defineProps({
  class: { type: null, required: false },
  src: { type: String, default: '' },
  alt: { type: String, default: '' },
  size: { type: String, default: 'md' },
})

const sizes = {
  xs: 'h-7 w-7 text-[11px]',
  sm: 'h-8 w-8 text-xs',
  md: 'h-10 w-10 text-sm',
  lg: 'h-12 w-12 text-base',
}
</script>

<template>
  <span
    :class="
      cn(
        'relative inline-flex shrink-0 overflow-hidden rounded-full bg-muted items-center justify-center font-medium text-muted-foreground select-none',
        sizes[size],
        props.class
      )
    "
  >
    <img v-if="src" :src="src" :alt="alt" class="h-full w-full object-cover" />
    <slot v-else />
  </span>
</template>
