<script setup>
import { SelectRoot } from 'reka-ui'

const props = defineProps({
  modelValue: { type: [String, Number, Boolean, Object, null], required: false, default: undefined },
})
const emit = defineEmits(['update:modelValue'])
</script>

<template>
  <SelectRoot :model-value="modelValue" @update:model-value="(v) => emit('update:modelValue', v)">
    <slot />
  </SelectRoot>
</template>
