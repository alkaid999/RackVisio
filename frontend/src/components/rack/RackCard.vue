<template>
  <Card
    hover
    class="rack-card group relative flex h-full cursor-pointer flex-col overflow-hidden transition-transform hover:-translate-y-0.5"
    @click="emit('view', rack.id)"
  >
    <!-- 头部：机柜名称 + 统一状态徽标 -->
    <div class="flex items-start justify-between gap-2">
      <span class="truncate text-base font-semibold text-foreground">{{ rack.name }}</span>
      <StatusBadge type="rack" :value="rack.status" />
    </div>

    <!-- 固定信息区（始终渲染占位，保证底部分割线位置不随缺字段上移） -->
    <div class="mt-2 space-y-1.5 text-xs text-muted-foreground">
      <div class="flex items-center gap-1">
        <MapPin class="h-3.5 w-3.5 shrink-0" />
        <span class="truncate">{{ rack.column_code }} / {{ rack.code }}</span>
      </div>
      <div class="flex items-center gap-1">
        <Users class="h-3.5 w-3.5 shrink-0" />
        <span class="truncate">分组：{{ rack.rack_group || '—' }}</span>
      </div>
      <div class="flex items-center gap-1">
        <Building2 class="h-3.5 w-3.5 shrink-0" />
        <span class="truncate">机房：{{ rack.room_name || '—' }}</span>
      </div>
    </div>

    <!-- U 位占用（始终渲染） -->
    <div class="mt-3 flex items-center justify-between text-xs text-muted-foreground">
      <span class="flex items-center gap-1"><Ruler class="h-3.5 w-3.5" />{{ rack.used_u }} / {{ rack.total_u }}U</span>
      <span class="font-medium text-foreground">{{ util }}%</span>
    </div>
    <div class="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-muted">
      <div class="h-full rounded-full transition-all" :style="{ width: util + '%', backgroundColor: utilColor }" />
    </div>

    <!-- 底部操作：图标 + 文字，删除为红色（与「耗材列表」卡片一致；卡片可点击查看，故隐藏冗余「查看」） -->
    <div class="mt-2.5 flex justify-end gap-1 border-t border-border pt-2.5">
      <EntityActions
        variant="full"
        :show-view="false"
        :show-edit="canEdit"
        :show-delete="canEdit"
        @view="emit('view', rack.id)"
        @edit="emit('edit', rack)"
        @delete="emit('delete', rack.id)"
      />
    </div>
  </Card>
</template>

<script setup>
import { computed } from 'vue'
import { MapPin, Ruler, Users, Building2 } from 'lucide-vue-next'
import StatusBadge from '@/components/common/StatusBadge.vue'
import EntityActions from '@/components/common/EntityActions.vue'
import Card from '@/components/ui/card.vue'
import { useMetaStore } from '@/stores/meta'

const props = defineProps({
  // RackListItem：{id, name, code, column_code, total_u, used_u, status, rack_group, room_name, ...}
  rack: { type: Object, required: true },
  // 是否允许编辑 / 删除（无 rack:edit 权限时隐藏写操作，避免点击后 403）。
  canEdit: { type: Boolean, default: true },
})
const emit = defineEmits(['view', 'edit', 'delete'])
const meta = useMetaStore()

const util = computed(() =>
  props.rack.total_u > 0 ? Math.min(100, Math.round((props.rack.used_u / props.rack.total_u) * 100)) : 0
)
// 使用率配色统一走 meta.usageColor（后端阈值/颜色单一数据源，审查报告#352）。
const utilColor = computed(() => {
  const u = props.rack.total_u > 0 ? props.rack.used_u / props.rack.total_u : 0
  return meta.usageColor(u)
})
</script>
