<script setup>
import { CollapsibleRoot } from 'reka-ui'

const props = defineProps({
  modelValue: { type: Boolean, required: false, default: undefined },
  defaultOpen: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])
</script>

<template>
  <CollapsibleRoot
    :open="modelValue"
    :default-open="defaultOpen"
    @update:open="(v) => emit('update:modelValue', v)"
  >
    <slot />
  </CollapsibleRoot>
</template>
