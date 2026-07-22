<template>
  <div class="space-y-3">
    <div class="flex items-center justify-between gap-2">
      <div class="min-w-0">
        <div class="text-base font-semibold text-slate-800 truncate">{{ rack.name }}</div>
        <div class="text-xs text-slate-400 mt-0.5">{{ rack.code }}</div>
      </div>
      <StatusBadge type="rack" :value="rack.status" />
    </div>

    <div class="grid grid-cols-[7rem_1fr] gap-x-3 gap-y-2 text-sm">
      <span class="text-muted-foreground flex items-center gap-1"><Tag class="h-3.5 w-3.5" />机柜编号</span>
      <span>{{ rack.code }}</span>
      <span class="text-muted-foreground flex items-center gap-1"><LocateFixed class="h-3.5 w-3.5" />物理位置</span>
      <span>{{ rack.column_code }} / {{ rack.code }}</span>
      <span class="text-muted-foreground flex items-center gap-1"><Package class="h-3.5 w-3.5" />设备数量</span>
      <span>{{ deviceCount != null ? deviceCount : '—' }}</span>
    </div>

    <div>
      <div class="flex items-center justify-between text-xs text-slate-500 mb-1">
        <span class="flex items-center gap-1"><Ruler class="h-3.5 w-3.5" />U 位使用率</span>
        <span class="font-medium tabular-nums" :style="{ color: capColor }">
          {{ pct }}% · {{ rack.used_u }}/{{ rack.total_u }}U
        </span>
      </div>
      <div class="h-2 w-full overflow-hidden rounded-full bg-muted">
        <div class="h-full rounded-full transition-all" :style="{ width: pct + '%', backgroundColor: capColor }" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Tag, LocateFixed, Package, Ruler } from 'lucide-vue-next'
import StatusBadge from '@/components/common/StatusBadge.vue'
import { useMetaStore } from '@/stores/meta'

const props = defineProps({
  rack: { type: Object, required: true },
  deviceCount: { type: Number, default: null },
})

const meta = useMetaStore()
const pct = computed(() => {
  const { used_u, total_u } = props.rack
  return total_u ? Math.round((used_u / total_u) * 100) : 0
})
// 使用率配色统一走 meta.usageColor（审查报告#352）。
const capColor = computed(() => meta.usageColor(pct.value / 100))
</script>
