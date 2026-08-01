<script setup>
import { computed, inject } from 'vue'
import { cn } from '@/lib/utils'

const props = defineProps({
  class: { type: null, required: false },
  type: { type: String, default: 'text' },
})
// 支持 v-model；type=number 时自动转为数值，对齐原 el-input-number 行为。
const model = defineModel({
  set(v) {
    if (props.type === 'number') return v === '' || v === null ? '' : Number(v)
    return v
  },
})

// M-12：消费 form-item 提供的上下文，实现 label for / aria-invalid / aria-describedby 关联
// （无障碍：读屏可辨识「该输入属于哪个表单项」及校验错误）。
const formItem = inject('formItemContext', null)
const inputId = computed(() => (formItem ? formItem.inputId : undefined))
const ariaInvalid = computed(() => (formItem && formItem.hasError.value ? 'true' : undefined))
const ariaDescribedby = computed(() => (formItem && formItem.hasError.value ? formItem.errorId : undefined))
</script>

<template>
  <input
    v-model="model"
    :id="inputId"
    :type="type"
    :aria-invalid="ariaInvalid"
    :aria-describedby="ariaDescribedby"
    :class="
      cn(
        'flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-50',
        props.class
      )
    "
  />
</template>

<style scoped>
/* 隐藏数字输入框的原生上下数量加减按钮，与其他 UI 组件风格保持一致 */
input[type='number']::-webkit-outer-spin-button,
input[type='number']::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}
input[type='number'] {
  -moz-appearance: textfield;
  appearance: textfield;
}
</style>
