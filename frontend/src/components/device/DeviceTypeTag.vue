<template>
  <!-- 设备类型标签：按类型着色（server 蓝 / switch 绿 / router 青 / other 灰） -->
  <span class="device-type-tag" :style="{ backgroundColor: color, color: '#fff' }">
    {{ label }}
  </span>
</template>

<script setup>
import { computed } from 'vue'
import { DEVICE_TYPE_COLORS, DEVICE_TYPE_LABELS } from '@/utils/constants'

const props = defineProps({
  type: { type: String, required: true },
})
const color = computed(() => DEVICE_TYPE_COLORS[props.type] || '#909399')
const label = computed(() => DEVICE_TYPE_LABELS[props.type] || props.type)
</script>

<style scoped>
.device-type-tag {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 10px;
  font-size: 12px;
  line-height: 18px;
  white-space: nowrap;
}
</style>
