<script setup>
import { cn } from '@/lib/utils'

const props = defineProps({
  class: { type: null, required: false },
  for: { type: String, default: undefined },
})
</script>

<template>
  <label :for="for" :class="cn('text-sm font-medium leading-none text-foreground', props.class)">
    <slot />
  </label>
</template>
