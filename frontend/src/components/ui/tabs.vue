<script setup>
import { TabsRoot } from 'reka-ui'

const props = defineProps({
  modelValue: { type: [String, Number], required: false, default: undefined },
  defaultValue: { type: [String, Number], required: false, default: undefined },
})
const emit = defineEmits(['update:modelValue'])
</script>

<template>
  <TabsRoot :model-value="modelValue" :default-value="defaultValue" @update:model-value="(v) => emit('update:modelValue', v)">
    <slot />
  </TabsRoot>
</template>
