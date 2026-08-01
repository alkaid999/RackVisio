<script setup>
import { buttonVariants } from './button-variants'
import { cn } from '@/lib/utils'
import Spinner from './spinner.vue'

const props = defineProps({
  variant: { type: String, default: 'default' },
  size: { type: String, default: 'default' },
  type: { type: String, default: 'button' },
  disabled: { type: Boolean, default: false },
  // loading（C-02）：显示 Spinner 并自动禁用，避免提交期间重复点击产生并发请求。
  // 此前大量调用方传 :loading 但组件不认，属性 fallthrough 成原生 `<button loading>`
  // （无视觉效果、不禁用），双击「保存/上架/库存提交」会重复提交。
  loading: { type: Boolean, default: false },
  class: { type: null, required: false },
})
</script>

<template>
  <button
    :type="type"
    :disabled="disabled || loading"
    :aria-busy="loading || undefined"
    :class="cn(buttonVariants({ variant, size }), props.class)"
  >
    <span v-if="loading" class="mr-2 inline-flex items-center">
      <Spinner class="h-4 w-4" />
    </span>
    <slot />
  </button>
</template>
