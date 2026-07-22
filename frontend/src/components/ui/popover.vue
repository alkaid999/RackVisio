<script setup>
import { PopoverRoot, PopoverTrigger } from 'reka-ui'

const props = defineProps({
  modelValue: { type: Boolean, required: false, default: undefined },
  defaultOpen: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])
</script>

<template>
  <PopoverRoot :open="modelValue" :default-open="defaultOpen" @update:open="(v) => emit('update:modelValue', v)">
    <PopoverTrigger as-child>
      <slot name="trigger" />
    </PopoverTrigger>
    <slot />
  </PopoverRoot>
</template>
