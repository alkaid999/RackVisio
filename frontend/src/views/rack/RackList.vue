<template>
  <div>
    <!-- 标题区 -->
    <div class="page-head">
      <div>
        <h1 class="page-title">机柜列表</h1>
        <p class="page-sub">共 {{ total }} 个机柜 · 支持按机房/状态筛选与关键字（名称/编号）搜索</p>
      </div>
      <div class="flex items-center gap-2">
        <div class="inline-flex rounded-lg border border-border bg-muted p-0.5">
          <button
            type="button"
            class="flex h-8 items-center gap-1.5 rounded-md px-3 text-sm transition-all"
            :class="viewMode === 'card' ? 'bg-background text-foreground shadow-soft' : 'text-muted-foreground hover:text-foreground'"
            @click="setView('card')"
          >
            <LayoutGrid class="h-4 w-4" />卡片
          </button>
          <button
            type="button"
            class="flex h-8 items-center gap-1.5 rounded-md px-3 text-sm transition-all"
            :class="viewMode === 'table' ? 'bg-background text-foreground shadow-soft' : 'text-muted-foreground hover:text-foreground'"
            @click="setView('table')"
          >
            <List class="h-4 w-4" />表格
          </button>
        </div>
        <Button v-if="canEdit" variant="outline" class="ml-auto" @click="openBatchCreate"><Layers class="h-4 w-4" />批量新增</Button>
        <Button v-if="canEdit" @click="openCreate"><Plus class="h-4 w-4" />新增机柜</Button>
      </div>
    </div>

    <!-- 筛选工具栏 -->
    <div class="toolbar">
      <div class="flex flex-wrap items-end gap-4">
        <div class="flex flex-col gap-1">
          <Label>关键字</Label>
          <div class="relative">
            <Search class="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input v-model="filter.keyword" placeholder="名称 / 编号" class="w-52 pl-9" @keyup.enter="reload" />
          </div>
        </div>
        <div class="flex flex-col gap-1">
          <Label class="flex items-center gap-1"><Building2 class="h-3.5 w-3.5 text-muted-foreground" />所属机房</Label>
          <Select v-model="filter.roomId" class="w-40" @update:model-value="reload">
            <SelectTrigger placeholder="全部" />
            <SelectContent>
              <SelectItem :value="SELECT_ALL">全部</SelectItem>
              <SelectItem v-for="r in rooms" :key="r.id" :value="r.id">{{ r.name }}（{{ r.code }}）</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div class="flex flex-col gap-1">
          <Label class="flex items-center gap-1"><Activity class="h-3.5 w-3.5 text-muted-foreground" />状态</Label>
          <Select v-model="filter.status" class="w-32" @update:model-value="reload">
            <SelectTrigger placeholder="全部" />
            <SelectContent>
              <SelectItem :value="SELECT_ALL">全部</SelectItem>
              <SelectItem v-for="o in RACK_STATUS_OPTIONS" :key="o.value" :value="o.value">{{ o.label }}</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div class="flex items-center gap-2 pb-1">
          <Button @click="load"><Filter class="h-4 w-4" />查询</Button>
          <Button variant="outline" @click="resetFilter"><Undo2 class="h-4 w-4" />重置</Button>
        </div>
      </div>
    </div>

    <!-- 批量操作条：仅表格模式支持批量删除（卡片模式点击=进入，不做批量选择） -->
    <div v-if="canEdit && viewMode === 'table' && selected.size" class="batch-bar">
      <span class="batch-count">已选 <b>{{ selected.size }}</b> 项</span>
      <Button size="sm" variant="destructive" @click="batchDelete"><Trash2 class="h-4 w-4" />批量删除</Button>
      <Button size="sm" variant="ghost" @click="toggleAllPage(true)">全选本页</Button>
      <Button size="sm" variant="ghost" @click="clearSelection">取消选择</Button>
    </div>

    <!-- 卡片视图 -->
    <div v-if="viewMode === 'card'">
      <div v-if="loading" class="flex justify-center py-16">
        <Spinner class="h-6 w-6 text-primary" />
      </div>
      <template v-else>
        <div v-if="racks.length" class="grid-cards">
          <RackCard
            v-for="rack in racks"
            :key="rack.id"
            :rack="rack"
            :can-edit="canEdit"
            @view="goRack"
            @edit="onEdit"
            @delete="() => onDelete(rack)"
          />
        </div>
        <EmptyState v-else title="暂无机柜数据" />
      </template>
    </div>

    <!-- 表格视图 -->
    <div v-else>
      <div v-if="loading" class="flex justify-center py-16">
        <Spinner class="h-6 w-6 text-primary" />
      </div>
      <Table v-else>
        <TableHeader>
          <TableRow>
            <TableHead class="w-10 text-center">
              <Checkbox
                :model-value="allPageSelected"
                :indeterminate="allPageIndeterminate"
                @update:model-value="(v) => toggleAllPage(v)"
              />
            </TableHead>
            <TableHead v-for="col in rackColumns" :key="col.key">{{ col.label }}</TableHead>
            <TableHead class="w-32 text-right">操作</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow v-for="row in racks" :key="row.id" :data-state="isSelected(row.id) ? 'selected' : null">
            <TableCell class="w-10 text-center">
              <Checkbox :model-value="isSelected(row.id)" @update:model-value="() => toggleRow(row.id)" />
            </TableCell>
            <TableCell v-for="col in rackColumns" :key="col.key">
              <template v-if="col.key === 'name'">
                <button class="font-medium text-primary hover:underline" @click="goRack(row.id)">{{ row.name }}</button>
              </template>
              <template v-else-if="col.key === 'col_code'">{{ row.column_code }} / {{ row.code }}</template>
              <template v-else-if="col.key === 'rack_group'">{{ row.rack_group || '—' }}</template>
              <template v-else-if="col.key === 'room_name'">{{ row.room_name || '—' }}</template>
              <template v-else-if="col.key === 'capacity'">{{ row.used_u }} / {{ row.total_u }}U</template>
              <template v-else-if="col.key === 'usage'">
                <div class="h-2.5 w-full overflow-hidden rounded-full bg-muted">
                  <div class="h-full rounded-full" :style="{ width: fillPct(row) + '%', backgroundColor: capacityColor(row.used_u / row.total_u) }" />
                </div>
              </template>
              <template v-else-if="col.key === 'status'"><StatusBadge type="rack" :value="row.status" /></template>
            </TableCell>
            <TableCell class="text-right">
              <div class="flex justify-end gap-1">
                <EntityActions :show-edit="canEdit" :show-delete="canEdit" @view="() => goRack(row.id)" @edit="() => onEdit(row)" @delete="() => onDelete(row)" />
              </div>
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </div>

    <!-- 分页（卡片/表格共用，跟随当前视图模式每页条数） -->
    <ListPager v-if="total > 0" :total="total" :page="page" :page-size="pageSize" @change="goPage" />

    <!-- 新增 / 编辑机柜弹窗 -->
    <RackForm v-model:visible="rackFormVisible" :mode="formMode" :rack-id="editRackId" @saved="load" />

    <!-- 批量新增机柜弹窗 -->
    <RackBatchCreate v-model:visible="batchCreateVisible" :rooms="rooms" @saved="onBatchSaved" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Building2, LayoutGrid, List, Search, Plus, Filter, Undo2, Activity, Layers, Trash2 } from 'lucide-vue-next'
import roomApi from '@/api/room'
import rackApi from '@/api/rack'
import { useAuthStore } from '@/stores/auth'
import { useMetaStore } from '@/stores/meta'
import RackCard from '@/components/rack/RackCard.vue'
import EntityActions from '@/components/common/EntityActions.vue'
import RackForm from '@/views/rack/RackForm.vue'
import RackBatchCreate from '@/views/rack/RackBatchCreate.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import Checkbox from '@/components/ui/checkbox.vue'
import { SELECT_ALL, RACK_STATUS_OPTIONS, toFilterParam } from '@/utils/constants'
import { useConfirm } from '@/composables/useConfirm'
import { useToast } from '@/composables/useToast'
import { usePersistentFilter } from '@/composables/usePersistentFilter'
import Button from '@/components/ui/button.vue'
import Input from '@/components/ui/input.vue'
import Label from '@/components/ui/label.vue'
import Select from '@/components/ui/select.vue'
import SelectTrigger from '@/components/ui/select-trigger.vue'
import SelectContent from '@/components/ui/select-content.vue'
import SelectItem from '@/components/ui/select-item.vue'
import Table from '@/components/ui/table.vue'
import TableHeader from '@/components/ui/table-header.vue'
import TableBody from '@/components/ui/table-body.vue'
import TableRow from '@/components/ui/table-row.vue'
import TableHead from '@/components/ui/table-head.vue'
import TableCell from '@/components/ui/table-cell.vue'
import EmptyState from '@/components/ui/empty-state.vue'
import Spinner from '@/components/ui/spinner.vue'
import ListPager from '@/components/common/ListPager.vue'

const { confirm } = useConfirm()
const { success } = useToast()
const router = useRouter()
const auth = useAuthStore()
const meta = useMetaStore()
// 编辑（新增 / 删除）机柜需 rack:edit；只读用户隐藏全部写操作按钮。
const canEdit = computed(() => auth.hasPermission('rack:edit'))

const rooms = ref([])
const racks = ref([])
const total = ref(0)
const loading = ref(false)
// 筛选持久化：按路由名 RackList 存 sessionStorage，返回上级再回来保留筛选；logout 统一清空。
const { filter, clear } = usePersistentFilter('RackList', () => ({ keyword: '', roomId: SELECT_ALL, status: SELECT_ALL }))
const viewMode = ref('card')
// 分页：卡片每页 12，表格每页 10（服务端分页）。
const page = ref(1)
const pageSize = computed(() => (viewMode.value === 'card' ? 12 : 10))
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
function setView(mode) {
  if (viewMode.value === mode) return
  viewMode.value = mode
  // 卡片模式不支持批量选择/删除，离开表格模式时清空选择，避免残留选中态。
  if (mode === 'card') clearSelection()
  page.value = 1
  load()
}
// 机柜列表表格固定列（移除「显示字段」配置功能）。
const rackColumns = [
  { key: 'name', label: '名称' },
  { key: 'col_code', label: '列/编号' },
  { key: 'rack_group', label: '分组' },
  { key: 'room_name', label: '所属机房' },
  { key: 'capacity', label: '容量' },
  { key: 'usage', label: '使用率' },
  { key: 'status', label: '状态' },
]
const rackFormVisible = ref(false)
const formMode = ref('create')
const editRackId = ref('')
// 批量新增弹窗 & 批量选择状态
const batchCreateVisible = ref(false)
const selected = ref(new Set())

function capacityColor(ratio) {
  // 使用率配色统一走 meta.usageColor（兼容 0..1 与 0..100 传参，审查报告#352）。
  return meta.usageColor(ratio)
}
function fillPct(rack) {
  return rack.total_u ? Math.round((rack.used_u / rack.total_u) * 100) : 0
}

function goRack(id) {
  router.push(`/racks/${id}`)
}
function openCreate() {
  formMode.value = 'create'
  editRackId.value = ''
  rackFormVisible.value = true
}
function openBatchCreate() {
  batchCreateVisible.value = true
}
// 批量新增完成后刷新列表并清空选择
function onBatchSaved() {
  clearSelection()
  load()
}

// —— 批量选择 ——
function isSelected(id) {
  return selected.value.has(id)
}
function toggleRow(id) {
  const next = new Set(selected.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  selected.value = next
}
function clearSelection() {
  selected.value = new Set()
}
const allPageSelected = computed(() => racks.value.length > 0 && racks.value.every((r) => selected.value.has(r.id)))
const allPageIndeterminate = computed(() => {
  const n = racks.value.filter((r) => selected.value.has(r.id)).length
  return n > 0 && n < racks.value.length
})
// val=true 选中本页全部，false 取消本页全部（不影响其它页已选）。
function toggleAllPage(val) {
  const next = new Set(selected.value)
  for (const r of racks.value) {
    if (val) next.add(r.id)
    else next.delete(r.id)
  }
  selected.value = next
}
function onEdit(rack) {
  formMode.value = 'edit'
  editRackId.value = rack.id
  rackFormVisible.value = true
}
async function onDelete(rack) {
  const ok = await confirm({
    title: '删除机柜',
    description: `确认删除机柜「${rack.name}」？删除前需先下架其内所有设备。`,
    variant: 'danger',
    confirmText: '删除',
  })
  if (!ok) return
  try {
    await rackApi.remove(rack.id)
    success('删除成功')
    load()
  } catch (e) {
    // 接口报错已由统一拦截器提示
  }
}

// 批量删除：对选中机柜逐个调用删除接口，结束后统一刷新并反馈结果。
async function batchDelete() {
  if (!selected.value.size) return
  const ids = [...selected.value]
  const ok = await confirm({
    title: '批量删除机柜',
    description: `确认删除选中的 ${ids.length} 个机柜？删除前需先下架其内所有设备，此操作不可撤销。`,
    variant: 'danger',
    confirmText: '删除',
    cancelText: '取消',
  })
  if (!ok) return
  try {
    const results = await Promise.allSettled(ids.map((id) => rackApi.remove(id)))
    const failed = results.filter((r) => r.status === 'rejected').length
    if (failed === 0) success(`已删除 ${ids.length} 个机柜`)
    else success(`已删除 ${ids.length - failed} 个，失败 ${failed} 个`)
    clearSelection()
    load()
  } catch (e) {
    // Promise.allSettled 不会 reject，此处仅兜底
  }
}

async function load() {
  loading.value = true
  try {
    const data = await rackApi.list({
      page: page.value,
      size: pageSize.value,
      room_id: toFilterParam(filter.roomId),
      keyword: filter.keyword || undefined,
      status: toFilterParam(filter.status),
    })
    racks.value = data.items || []
    total.value = data.total || 0
    // 末页被删空则回退到有效页
    if (racks.value.length === 0 && page.value > 1 && total.value > 0) {
      page.value = Math.max(1, totalPages.value)
      await load()
    }
  } finally {
    loading.value = false
  }
}
// 筛选条件变化：页码归 1 后重新加载
function reload() {
  page.value = 1
  load()
}
// 翻页：边界校验后更新页码并重新加载对应页
function goPage(p) {
  if (p < 1 || p > totalPages.value) return
  page.value = p
  load()
}
function resetFilter() {
  clear()
  reload()
}

onMounted(async () => {
  const data = await roomApi.list({ size: 200 })
  rooms.value = data.items || []
  load()
})
</script>

<style scoped>
.toolbar {
  background: oklch(var(--card) / 0.8);
  border: 1px solid oklch(var(--border) / 0.6);
  border-radius: 10px;
  padding: 14px 16px;
  margin-bottom: 16px;
  backdrop-filter: blur(8px);
}
.grid-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 16px;
}
.batch-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  margin-bottom: 14px;
  border-radius: 12px;
  border: 1px solid hsl(var(--destructive) / 0.3);
  background: hsl(var(--destructive) / 0.08);
  animation: batch-in 0.16s ease;
}
@keyframes batch-in {
  from { opacity: 0; transform: translateY(-4px); }
  to { opacity: 1; transform: translateY(0); }
}
.batch-count {
  font-size: 13px;
  color: hsl(var(--foreground));
}
.batch-count b {
  color: hsl(var(--destructive));
  font-weight: 700;
}
/* 表格中被选中的行高亮 */
:deep(tr[data-state='selected']) {
  background: hsl(var(--primary) / 0.06);
}
</style>
