<template>
  <button
    type="button"
    role="checkbox"
    :aria-checked="indeterminate ? 'mixed' : modelValue ? 'true' : 'false'"
    :disabled="disabled"
    class="ckb"
    :class="{ 'ckb--on': modelValue, 'ckb--ind': indeterminate, 'ckb--disabled': disabled }"
    @click="toggle"
  >
    <Check v-if="modelValue && !indeterminate" class="ckb-ic" :stroke-width="3" />
    <Minus v-else-if="indeterminate" class="ckb-ic" :stroke-width="3" />
  </button>
</template>

<script setup>
import { Check, Minus } from 'lucide-vue-next'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  indeterminate: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])

function toggle() {
  if (props.disabled) return
  emit('update:modelValue', !props.modelValue)
}
</script>

<style scoped>
.ckb {
  width: 18px;
  height: 18px;
  flex: none;
  border-radius: 6px;
  border: 1.5px solid hsl(var(--border));
  background: hsl(var(--background));
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  cursor: pointer;
  color: hsl(var(--primary-foreground));
  transition: background 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
}
.ckb:hover:not(.ckb--disabled) {
  border-color: hsl(var(--primary));
}
.ckb:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px hsl(var(--primary) / 0.3);
}
.ckb--on,
.ckb--ind {
  background: hsl(var(--primary));
  border-color: hsl(var(--primary));
}
.ckb--disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.ckb-ic {
  width: 13px;
  height: 13px;
}
</style>
