<script setup>
import { buttonVariants } from './button-variants'
import { cn } from '@/lib/utils'

const props = defineProps({
  variant: { type: String, default: 'default' },
  size: { type: String, default: 'default' },
  type: { type: String, default: 'button' },
  disabled: { type: Boolean, default: false },
  class: { type: null, required: false },
})
</script>

<template>
  <button :type="type" :disabled="disabled" :class="cn(buttonVariants({ variant, size }), props.class)">
    <slot />
  </button>
</template>
