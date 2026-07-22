<script setup>
import { ref, provide, reactive } from 'vue'
import { cn } from '@/lib/utils'

// 轻量表单容器：兼容原 el-form 的 validate(callback) / clearValidate() 用法，
// 使既有表单逻辑（如 RoomForm.onSubmit）几乎零改动迁移。
const props = defineProps({
  model: { type: Object, required: true },
  rules: { type: Object, default: () => ({}) },
  class: { type: null, required: false },
})
const emit = defineEmits(['submit'])

const errors = reactive({})
const formRef = ref(null)

function validateField(name) {
  const rule = props.rules[name]
  if (!rule) return true
  const rulesArr = Array.isArray(rule) ? rule : [rule]
  const value = props.model[name]
  let err = ''
  for (const r of rulesArr) {
    if (r.required) {
      const empty =
        value === '' || value === null || value === undefined || (Array.isArray(value) && value.length === 0)
      if (empty) {
        err = r.message
        break
      }
    }
    if (r.type === 'number' && value !== '' && value !== null && value !== undefined) {
      const num = Number(value)
      if (Number.isNaN(num)) {
        err = r.message
        break
      }
      if (r.min !== undefined && num < r.min) {
        err = r.message
        break
      }
      if (r.max !== undefined && num > r.max) {
        err = r.message
        break
      }
    }
    if (r.pattern && value) {
      if (!r.pattern.test(String(value))) {
        err = r.message
        break
      }
    }
  }
  errors[name] = err
  return !err
}

function validate(callback) {
  let valid = true
  for (const key in props.rules) {
    if (!validateField(key)) valid = false
  }
  if (typeof callback === 'function') callback(valid)
  return Promise.resolve(valid)
}

function clearValidate() {
  for (const k in errors) delete errors[k]
}

provide('formContext', { errors, validateField, model: props.model, rules: props.rules })
defineExpose({ validate, clearValidate, validateField })
</script>

<template>
  <form ref="formRef" :class="cn('space-y-4', props.class)" @submit.prevent="emit('submit')">
    <slot />
  </form>
</template>
