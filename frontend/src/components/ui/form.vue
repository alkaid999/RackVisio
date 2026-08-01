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

// M-02：validateField 支持 async——规则对象可携带 `validator: async (value) => string|true`，
// 返回错误文案字符串或 true。async 校验（如远程唯一性检查）不再只能等后端 422。
async function validateField(name) {
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
    // 自定义 validator：返回值 false / 非空字符串视为校验失败（async 兼容）。
    if (r.validator) {
      try {
        const res = await r.validator(value, props.model)
        if (res === false || (typeof res === 'string' && res.length > 0)) {
          err = typeof res === 'string' ? res : r.message
          break
        }
      } catch (e) {
        err = r.message
        break
      }
    }
  }
  errors[name] = err
  return !err
}

// validate 兼容两种调用风格：
// 1) 同步回调：formRef.value.validate((valid) => {...})
// 2) await：await formRef.value.validate(async (valid) => {...}) 或 await formRef.value.validate()
// M-02：内部 async 化——含 validator 的字段校验完成后再回调，避免回调早于异步校验结束。
async function validate(callback) {
  let valid = true
  const keys = Object.keys(props.rules)
  for (const key of keys) {
    const ok = await validateField(key)
    if (!ok) valid = false
  }
  if (typeof callback === 'function') callback(valid)
  return valid
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
