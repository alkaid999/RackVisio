<template>
  <Dialog
    :model-value="visible"
    :title="`变动历史 — ${item ? item.name : ''}`"
    class="max-w-3xl"
    @update:model-value="(v) => emit('update:visible', v)"
  >
    <div v-if="item" class="mb-3 flex items-center gap-2 text-sm text-muted-foreground">
      <span>当前状态</span>
      <span class="font-semibold" :style="{ color: HARDWARE_STATUS_COLORS[item.status] || '#909399' }">{{ item.status }}</span>
      <span v-if="item.status === '已安装' && item.assigned_device_name" class="text-muted-foreground">· 已安装于 {{ item.assigned_device_name }}</span>
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
          <TableHead>关联设备</TableHead>
          <TableHead>原因 / 备注</TableHead>
          <TableHead>操作人</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow v-for="r in store.records" :key="r.id">
          <TableCell class="text-muted-foreground">{{ formatTime(r.operation_time) }}</TableCell>
          <TableCell>
            <span
              class="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium"
              :style="{ backgroundColor: (HARDWARE_OP_COLORS[r.operation_type] || '#909399') + '22', color: HARDWARE_OP_COLORS[r.operation_type] || '#909399' }"
            >
              <span class="h-1.5 w-1.5 rounded-full" :style="{ backgroundColor: HARDWARE_OP_COLORS[r.operation_type] || '#909399' }"></span>
              {{ r.operation_type }}
            </span>
          </TableCell>
          <TableCell class="text-muted-foreground">{{ r.device_name || '—' }}</TableCell>
          <TableCell class="max-w-[16rem] truncate text-muted-foreground" :title="r.reason">{{ r.reason || '—' }}</TableCell>
          <TableCell class="text-muted-foreground">{{ r.operator || '—' }}</TableCell>
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
import { useHardwareStore } from '@/stores/hardware'
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
import { HARDWARE_OP_COLORS, HARDWARE_STATUS_COLORS } from '@/utils/constants'
import { formatDateTime } from '@/utils/datetime'

const props = defineProps({
  visible: { type: Boolean, default: false },
  item: { type: Object, default: null },
})
const emit = defineEmits(['update:visible'])

const store = useHardwareStore()
const formatTime = formatDateTime

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
