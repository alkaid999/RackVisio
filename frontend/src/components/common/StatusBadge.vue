<template>
  <!-- 通用状态徽章：语义图标 + 彩色圆点 + 中文标签，外裹柔和色片 -->
  <span class="status-chip" :style="{ color, backgroundColor: tint }">
    <component :is="iconComp" v-if="iconComp" class="status-icon" />
    <span class="status-dot"></span>
    <span class="status-text">{{ label }}</span>
  </span>
</template>

<script setup>
import { computed } from 'vue'
import { statusColor, statusLabel } from '@/utils/constants'
import {
  CircleDashed,
  CircleDot,
  PackageCheck,
  CircleCheckBig,
  CircleSlash,
  Wrench,
  ArchiveX,
  ArrowUpCircle,
} from 'lucide-vue-next'

const props = defineProps({
  // 状态类型：rack | device | interface | link
  type: { type: String, required: true },
  // 状态值（对应后端枚举字符串）
  value: { type: String, default: '' },
})

const color = computed(() => statusColor(props.type, props.value))
// 兜底逻辑（修复「链路状态无法正常显示」）：
// - 链路状态为严格闭集（active/inactive）。若值为空或属于上一版本遗留的非法历史值
//   （如 connected/disconnected 等），统一回退为「未知」，绝不渲染成空白状态芯片。
// - 其它类型（设备/机柜/接口）保留原有回退行为，避免影响「已下架」等历史中文状态展示。
const label = computed(() => {
  return statusLabel(props.type, props.value) || '未知'
})
// 6 位 hex 追加 alpha，得到约 13% 透明度的浅色底（兼容所有浏览器）。
const tint = computed(() => `${color.value}22`)

// 每个状态值映射一个语义图标（与颜色保持一致），全局统一以保证可识别性。
function statusIcon(type, value) {
  const map = {
    rack: { empty: CircleDashed, partial: CircleDot, full: PackageCheck },
    device: {
      在库: CircleDashed,
      已上架: CircleCheckBig,
      已下架: CircleSlash,
      待报废: ArchiveX,
    },
    port: { up: ArrowUpCircle, down: CircleSlash },
    interface: { up: ArrowUpCircle, down: CircleSlash },
  }
  return (map[type] && map[type][value]) || null
}
const iconComp = computed(() => statusIcon(props.type, props.value))
</script>

<style scoped>
.status-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 10px 2px 8px;
  border-radius: 9999px;
  font-size: 12px;
  font-weight: 500;
  line-height: 18px;
  white-space: nowrap;
}
.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background-color: currentColor;
}
.status-icon {
  width: 13px;
  height: 13px;
  flex-shrink: 0;
}
.status-text {
  color: inherit;
}
</style>
