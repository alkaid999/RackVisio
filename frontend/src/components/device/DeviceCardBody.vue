<template>
  <div class="flex w-full min-w-0 gap-3" :class="list ? 'items-center' : 'flex-col'">
    <!-- 主信息：名称 + 状态灯 + 类型徽章 -->
    <div class="flex min-w-0 items-center gap-2">
      <span class="h-2.5 w-2.5 shrink-0 rounded-full" :style="{ backgroundColor: statusColor }"></span>
      <span class="truncate text-sm font-semibold text-foreground">{{ device.name }}</span>
      <span
        class="shrink-0 rounded px-1.5 py-0.5 text-[11px] font-medium"
        :style="{ backgroundColor: typeColor + '22', color: typeColor }"
      >{{ typeLabel }}</span>
    </div>

    <!-- 次级信息：IP + 机柜U位 -->
    <div class="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
      <span class="inline-flex items-center gap-1">
        <Globe class="h-3 w-3 text-muted-foreground" />{{ device.ip_address || '—' }}
      </span>
      <span v-if="device.current_rack_name" class="inline-flex items-center gap-1 text-slate-400">
        <Server class="h-3 w-3" />{{ device.current_rack_name }}
        <template v-if="device.current_start_u != null">· {{ device.current_start_u }}U~{{ uEnd }}U</template>
      </span>
      <span v-else class="text-muted-foreground">未上架</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Globe, Server } from 'lucide-vue-next'
import { DEVICE_TYPE_LABELS, DEVICE_TYPE_COLORS, DEVICE_STATUS_COLORS } from '@/utils/constants'

const props = defineProps({
  device: { type: Object, required: true },
  selected: { type: Boolean, default: false },
  list: { type: Boolean, default: false },
})

const typeLabel = computed(() => DEVICE_TYPE_LABELS[props.device.device_type] || props.device.device_type || '')
const typeColor = computed(() => DEVICE_TYPE_COLORS[props.device.device_type] || '#909399')
const statusColor = computed(() => DEVICE_STATUS_COLORS[props.device.status] || '#909399')
const uEnd = computed(() => {
  const s = props.device.current_start_u
  const h = props.device.u_height || 1
  return s != null ? s + h - 1 : s
})
</script>
