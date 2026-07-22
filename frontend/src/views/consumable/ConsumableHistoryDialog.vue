<template>
  <Dialog
    :model-value="visible"
    :title="`变动历史 — ${item ? item.name : ''}`"
    class="max-w-3xl"
    @update:model-value="(v) => emit('update:visible', v)"
  >
    <div v-if="item" class="mb-3 flex items-center gap-2 text-sm text-muted-foreground">
      <span>当前结存</span>
      <span class="font-semibold text-foreground">{{ item.current_quantity }} {{ item.unit || '个' }}</span>
      <span class="ml-2 rounded-full bg-muted px-2 py-0.5 text-xs">共 {{ store.recordTotal }} 条记录</span>
    </div>

    <div v-if="store.recordLoading" class="flex justify-center py-16">
      <Spinner class="h-6 w-6 text-primary" />
    </div>
    <div v-else-if="!store.records.length" class="py-16">
      <EmptyState :icon="History" title="暂无变动记录" />
    </div>
    <Table v-else>
      <TableHeader>
        <TableRow>
          <TableHead>操作时间</TableHead>
          <TableHead>操作类型</TableHead>
          <TableHead class="text-right">数量</TableHead>
          <TableHead>原因 / 备注</TableHead>
          <TableHead>操作人</TableHead>
          <TableHead class="text-right">变动后结存</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow v-for="r in store.records" :key="r.id">
          <TableCell class="text-muted-foreground">{{ formatTime(r.operation_time) }}</TableCell>
          <TableCell>
            <span
              class="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium"
              :style="{ backgroundColor: (CONSUMABLE_OP_COLORS[r.operation_type] || '#909399') + '22', color: CONSUMABLE_OP_COLORS[r.operation_type] || '#909399' }"
            >
              <span class="h-1.5 w-1.5 rounded-full" :style="{ backgroundColor: CONSUMABLE_OP_COLORS[r.operation_type] || '#909399' }"></span>
              {{ r.operation_type }}
            </span>
          </TableCell>
          <TableCell class="text-right font-semibold" :style="{ color: qtyColor(r) }">{{ qtyText(r) }}</TableCell>
          <TableCell class="max-w-[12rem] truncate text-muted-foreground" :title="r.reason">{{ r.reason || '—' }}</TableCell>
          <TableCell class="text-muted-foreground">{{ r.operator || '—' }}</TableCell>
          <TableCell class="text-right font-medium text-foreground">{{ r.balance_after }}</TableCell>
        </TableRow>
      </TableBody>
    </Table>

    <template #footer>
      <div class="flex items-center justify-between">
        <ListPager
          v-if="store.recordTotal > 0"
          :total="store.recordTotal"
          :page="page"
          :page-size="pageSize"
          @change="goPage"
        />
        <Button variant="outline" @click="emit('update:visible', false)">关闭</Button>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useConsumableStore } from '@/stores/consumable'
import Dialog from '@/components/ui/dialog.vue'
import Button from '@/components/ui/button.vue'
import Table from '@/components/ui/table.vue'
import TableHeader from '@/components/ui/table-header.vue'
import TableBody from '@/components/ui/table-body.vue'
import TableRow from '@/components/ui/table-row.vue'
import TableHead from '@/components/ui/table-head.vue'
import TableCell from '@/components/ui/table-cell.vue'
import Spinner from '@/components/ui/spinner.vue'
import EmptyState from '@/components/ui/empty-state.vue'
import ListPager from '@/components/common/ListPager.vue'
import { History } from 'lucide-vue-next'
import { CONSUMABLE_OP_COLORS } from '@/utils/constants'

const props = defineProps({
  visible: { type: Boolean, default: false },
  item: { type: Object, default: null },
})
const emit = defineEmits(['update:visible'])

const store = useConsumableStore()

// 历史记录分页（每页 10 条，翻页重新拉取）。
const page = ref(1)
const pageSize = 10
function loadRecords(id, p = 1) {
  page.value = p
  store.fetchRecords(id, { page: p, size: pageSize })
}
function goPage(p) {
  if (props.item) loadRecords(props.item.id, p)
}

// 时间格式化统一委托给全局工具（上海时区呈现）。
import { formatDateTime } from '@/utils/datetime'
const formatTime = formatDateTime
// 数量展示符号：入库 +、领用/报废 -、盘点 =。
function qtyText(r) {
  if (r.operation_type === '入库') return `+${r.quantity}`
  if (r.operation_type === '领用' || r.operation_type === '报废') return `-${r.quantity}`
  return `=${r.quantity}`
}
function qtyColor(r) {
  if (r.operation_type === '入库') return '#22c55e'
  if (r.operation_type === '领用' || r.operation_type === '报废') return '#ef4444'
  return '#e6a23c'
}

watch(
  () => [props.visible, props.item && props.item.id],
  async ([v, id]) => {
    if (v && id) {
      loadRecords(id, 1)
    }
  },
  { immediate: false }
)
</script>
