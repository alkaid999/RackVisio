<template>
  <div class="stats-panel card-soft p-5">
    <div class="kpi-grid">
      <div class="kpi-card">
        <span class="kpi-label">机柜总数</span>
        <span class="kpi-value">{{ stats.rack_count }}</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-label">总 U 位</span>
        <span class="kpi-value">{{ stats.total_u }}</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-label">已用 U 位</span>
        <span class="kpi-value">{{ stats.used_u }}</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-label">利用率</span>
        <span class="kpi-value" :style="{ color: utilColor }">{{ stats.utilization }}%</span>
      </div>
    </div>
    <div class="mt-4">
      <div class="h-3.5 w-full overflow-hidden rounded-full bg-muted">
        <div class="h-full rounded-full transition-all" :style="{ width: clampedUtil + '%', backgroundColor: utilColor }" />
      </div>
      <div class="mt-1 text-right text-xs text-muted-foreground">{{ stats.utilization }}%</div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useMetaStore } from '@/stores/meta'

const props = defineProps({
  // RoomStats: {rack_count, total_u, used_u, utilization}
  stats: { type: Object, default: () => ({ rack_count: 0, total_u: 0, used_u: 0, utilization: 0 }) },
})

const meta = useMetaStore()

const clampedUtil = computed(() => Math.min(100, Math.max(0, props.stats.utilization || 0)))
const utilColor = computed(() => {
  const u = props.stats.utilization || 0
  // 使用率配色统一走 meta.usageColor（审查报告#352）。
  return meta.usageColor(u)
})
</script>
