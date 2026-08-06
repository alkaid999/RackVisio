<template>
  <div class="hardware-list">
    <div class="page-head">
      <div>
        <h2 class="page-title">硬件管理</h2>
        <p class="page-sub">共 {{ store.total }} 件硬件 · 每件均为独立管理单元（SN 单独编号），可分配至设备，生命周期全程留痕</p>
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
        <!-- 导出（保留当前筛选条件，与机柜/机房一致） -->
        <DropdownMenu>
          <template #trigger>
            <Button variant="outline" :loading="exporting">
              <Download class="h-4 w-4" />导出<ChevronDown class="h-4 w-4" />
            </Button>
          </template>
          <DropdownMenuContent align="end" class="w-40">
            <DropdownMenuItem @click="onExport('xlsx')"><FileSpreadsheet class="h-4 w-4" />Excel (.xlsx)</DropdownMenuItem>
            <DropdownMenuItem @click="onExport('csv')"><FileText class="h-4 w-4" />CSV (.csv)</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
        <!-- 导入（需 hardware:edit） -->
        <Button v-if="canEdit" variant="outline" @click="importVisible = true"><Upload class="h-4 w-4" />导入</Button>
        <Button v-if="canEdit" @click="openCreate"><Plus class="h-4 w-4" />新建硬件</Button>
      </div>
    </div>

    <!-- 筛选工具栏 -->
    <div class="toolbar">
      <div class="flex flex-wrap items-end gap-4">
        <div class="flex flex-col gap-1">
          <Label class="flex items-center gap-1"><Cpu class="h-3.5 w-3.5 text-muted-foreground" />硬件类型</Label>
          <Select v-model="filter.typeId" class="w-40" @update:model-value="onTypeChange">
            <SelectTrigger placeholder="全部类型" />
            <SelectContent>
              <SelectItem :value="SELECT_ALL">全部类型</SelectItem>
              <SelectItem v-for="t in store.types" :key="t.id" :value="t.id">{{ t.name }}</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div class="flex flex-col gap-1">
          <Label class="flex items-center gap-1"><Layers class="h-3.5 w-3.5 text-muted-foreground" />分类</Label>
          <Select
            v-model="filter.categoryId"
            class="w-40"
            :disabled="!typeSelected"
            @update:model-value="reload"
          >
            <SelectTrigger :placeholder="typeSelected ? '全部分类' : '请先选类型'" />
            <SelectContent>
              <SelectItem :value="SELECT_ALL">全部分类</SelectItem>
              <SelectItem v-for="c in store.categories" :key="c.id" :value="c.id">{{ c.name }}</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div class="flex flex-col gap-1">
          <Label>状态</Label>
          <Select v-model="filter.status" class="w-32" @update:model-value="reload">
            <SelectTrigger placeholder="全部状态" />
            <SelectContent>
              <SelectItem :value="SELECT_ALL">全部状态</SelectItem>
              <SelectItem v-for="s in HARDWARE_STATUS_OPTIONS" :key="s.value" :value="s.value">{{ s.label }}</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div class="flex flex-col gap-1">
          <Label>关键字</Label>
          <div class="relative">
            <Search class="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input v-model="filter.keyword" placeholder="名称 / 品牌 / SN / 规格" class="w-56 pl-9" @keyup.enter="reload" />
          </div>
        </div>
        <div class="flex items-center gap-2 pb-1">
          <Button @click="load"><Filter class="h-4 w-4" />查询</Button>
          <Button variant="outline" @click="resetFilter"><Undo2 class="h-4 w-4" />重置</Button>
        </div>
      </div>
    </div>

    <!-- 批量操作条：仅表格模式支持批量删除（与机柜/机房列表一致） -->
    <div v-if="canEdit && viewMode === 'table' && selected.size" class="batch-bar">
      <span class="batch-count">已选 <b>{{ selected.size }}</b> 项</span>
      <Button size="sm" variant="destructive" @click="batchDelete"><Trash2 class="h-4 w-4" />批量删除</Button>
      <Button size="sm" variant="ghost" @click="toggleAllPage(true)">全选本页</Button>
      <Button size="sm" variant="ghost" @click="clearSelection">取消选择</Button>
    </div>

    <!-- 加载态 -->
    <div v-if="store.loading" class="flex justify-center py-20">
      <Spinner class="h-6 w-6 text-primary" />
    </div>

    <template v-else>
      <!-- 卡片视图 -->
      <div v-if="viewMode === 'card'">
        <div v-if="!store.items.length">
          <EmptyState :icon="Cpu" title="暂无硬件" />
        </div>
        <div v-else class="grid-cards">
          <Card v-for="item in store.items" :key="item.id" hover class="group">
            <!-- 标题行：名称 + 类型徽章（品牌移入信息区，取消圆标） -->
            <div class="flex items-center justify-between gap-2">
              <span class="truncate text-base font-semibold text-foreground">{{ item.name }}</span>
              <span
                class="shrink-0 rounded-full border px-2 py-0.5 text-xs font-medium"
                :style="typeBadgeStyle(item.type_id)"
              >{{ item.type_name }}</span>
            </div>

            <!-- 信息区：每行「小图标 + 文本」（与机柜 / 设备列表卡片一致） -->
            <div class="mt-2 space-y-1.5 text-xs text-muted-foreground">
              <div class="flex items-center gap-1">
                <Factory class="h-3.5 w-3.5 shrink-0" />
                <span class="truncate">品牌：{{ item.brand || '—' }}</span>
              </div>
              <div class="flex items-center gap-1">
                <Package class="h-3.5 w-3.5 shrink-0" />
                <span class="truncate">分类：{{ item.category_name || '—' }}</span>
              </div>
              <div class="flex items-center gap-1">
                <Activity class="h-3.5 w-3.5 shrink-0" />
                <span class="truncate">
                  状态：{{ item.status || '—' }}
                  <button
                    v-if="item.status === '已安装' && item.assigned_device_id"
                    class="ml-0.5 inline-flex items-center gap-0.5 font-medium text-primary hover:underline"
                    :title="`查看设备 ${item.assigned_device_name || ''}`"
                    @click.stop="goDevice(item.assigned_device_id)"
                  ><HardDrive class="h-3 w-3 shrink-0" />{{ item.assigned_device_name || '设备' }}</button>
                </span>
              </div>
              <div class="flex items-center gap-1">
                <Ruler class="h-3.5 w-3.5 shrink-0" />
                <span class="truncate">规格 / 型号：{{ item.spec || '—' }}</span>
              </div>
              <div class="flex items-center gap-1">
                <Barcode class="h-3.5 w-3.5 shrink-0" />
                <span class="truncate font-mono">SN：{{ item.sn || '—' }}</span>
                <button
                  v-if="item.sn"
                  class="ml-auto shrink-0 text-muted-foreground/60 transition-colors hover:text-primary"
                  title="复制 SN"
                  @click.stop="copySn(item.sn)"
                ><Copy class="h-3 w-3" /></button>
              </div>
            </div>

            <!-- 底部操作：图标 + 文字（与机柜 / 设备列表一致），历史走 extra 动作 -->
            <div class="mt-2.5 flex justify-end gap-1 border-t border-border pt-2.5">
              <EntityActions
                variant="full"
                :extra-actions="rowExtraActions(item)"
                :show-view="false"
                :show-edit="canEdit"
                :show-delete="canEdit"
                @view="openHistory(item)"
                @edit="openEdit(item.id)"
                @delete="onDelete(item)"
              />
            </div>
          </Card>
        </div>
      </div>

      <!-- 表格视图 -->
      <div v-else>
        <div v-if="!store.items.length">
          <EmptyState :icon="Cpu" title="暂无硬件" />
        </div>
        <Table v-else class="table-fixed w-full">
          <TableHeader>
            <TableRow>
              <TableHead v-if="canEdit" class="w-10">
                <Checkbox
                  :model-value="allPageSelected"
                  :indeterminate="allPageIndeterminate"
                  aria-label="全选本页"
                  @update:model-value="(v) => toggleAllPage(v)"
                />
              </TableHead>
              <TableHead class="w-36">名称</TableHead>
              <TableHead class="w-48">类型 / 分类</TableHead>
              <TableHead class="w-32">品牌</TableHead>
              <TableHead class="w-28">SN 号</TableHead>
              <TableHead class="w-32">规格 / 型号</TableHead>
              <TableHead class="w-36">状态 / 所属设备</TableHead>
              <TableHead class="w-32 text-right">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow v-for="item in store.items" :key="item.id" :class="isSelected(item.id) ? 'bg-primary/5' : ''">
              <TableCell v-if="canEdit">
                <Checkbox :model-value="isSelected(item.id)" aria-label="选择行" @update:model-value="() => toggleRow(item.id)" />
              </TableCell>
              <TableCell>
                <!-- 名称单独（不与规格合并，与卡片一致） -->
                <button class="block w-full truncate font-medium text-primary hover:underline" @click="openHistory(item)">
                  {{ item.name }}
                </button>
              </TableCell>
              <TableCell>
                <!-- 类型徽章 + 分类徽章（灰底次级）；table-fixed 下分类长名 truncate 防溢出 -->
                <div class="flex items-center gap-1">
                  <span
                    class="shrink-0 rounded-full border px-2 py-0.5 text-xs font-medium"
                    :style="typeBadgeStyle(item.type_id)"
                  >{{ item.type_name }}</span>
                  <span class="max-w-[5rem] truncate rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">{{ item.category_name || '—' }}</span>
                </div>
              </TableCell>
              <TableCell>
                <span v-if="item.brand" class="block min-w-0 max-w-[7rem] truncate text-muted-foreground">{{ item.brand }}</span>
                <span v-else class="text-muted-foreground">—</span>
              </TableCell>
              <TableCell>
                <span v-if="item.sn" class="flex items-center gap-1">
                  <span class="block min-w-0 truncate font-mono text-muted-foreground">{{ item.sn }}</span>
                  <button
                    class="shrink-0 text-muted-foreground/60 transition-colors hover:text-primary"
                    title="复制 SN"
                    @click="copySn(item.sn)"
                  ><Copy class="h-3.5 w-3.5" /></button>
                </span>
                <span v-else class="text-muted-foreground">—</span>
              </TableCell>
              <TableCell>
                <span class="block w-full truncate text-muted-foreground">{{ item.spec || '—' }}</span>
              </TableCell>
              <TableCell>
                <div class="flex items-center gap-1.5">
                  <span
                    class="inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium"
                    :style="{ backgroundColor: (HARDWARE_STATUS_COLORS[item.status] || '#909399') + '22', color: HARDWARE_STATUS_COLORS[item.status] || '#909399' }"
                  >
                    <span class="h-1.5 w-1.5 rounded-full" :style="{ backgroundColor: HARDWARE_STATUS_COLORS[item.status] || '#909399' }"></span>
                    {{ item.status }}
                  </span>
                  <button
                    v-if="item.status === '已安装' && item.assigned_device_id"
                    class="inline-flex max-w-[5rem] items-center gap-0.5 truncate text-xs font-medium text-primary hover:underline"
                    :title="`查看设备 ${item.assigned_device_name || ''}`"
                    @click="goDevice(item.assigned_device_id)"
                  ><HardDrive class="h-3 w-3 shrink-0" />{{ item.assigned_device_name || '设备' }}</button>
                </div>
              </TableCell>
              <TableCell class="text-right">
                <div class="flex justify-end gap-1">
                  <EntityActions
                    :extra-actions="rowExtraActions(item)"
                    :show-view="false"
                    :show-edit="canEdit"
                    :show-delete="canEdit"
                    @edit="openEdit(item.id)"
                    @delete="onDelete(item)"
                  />
                </div>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </div>
    </template>

    <!-- 分页 -->
    <ListPager v-if="store.total > 0" :total="store.total" :page="page" :page-size="pageSize" @change="goPage" />

    <!-- 新建 / 编辑硬件弹窗 -->
    <HardwareForm v-model:visible="formVisible" :mode="formMode" :item-id="formItemId" @saved="load" />
    <!-- 变动历史弹窗 -->
    <HardwareHistoryDialog v-model:visible="historyVisible" :item="historyItem" />
    <!-- 批量导入弹窗（与 DataImportDialog v-model:visible 绑定；与机柜/机房一致） -->
    <DataImportDialog
      v-model:visible="importVisible"
      :config="hardwareImportConfig"
      :import-fn="(items) => hardwareApi.import(items)"
      @imported="load"
    />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  LayoutGrid, List, Plus, Cpu, Search, Filter, Undo2,
  History, Layers, Copy, HardDrive,
  Package, Ruler, Barcode, Activity, Factory,
  Download, Upload, ChevronDown, FileSpreadsheet, FileText, Trash2,
} from 'lucide-vue-next'
import hardwareApi from '@/api/hardware'
import { useHardwareStore } from '@/stores/hardware'
import { useAuthStore } from '@/stores/auth'
import HardwareForm from '@/views/hardware/HardwareForm.vue'
import HardwareHistoryDialog from '@/views/hardware/HardwareHistoryDialog.vue'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import { usePersistentFilter } from '@/composables/usePersistentFilter'
import { backToValidPage } from '@/composables/useListReload'
import { exportData } from '@/utils/excel'
import { hardwareImportConfig } from '@/utils/importConfig'
import {
  SELECT_ALL, toFilterParam,
  HARDWARE_STATUS_OPTIONS, HARDWARE_STATUS_COLORS,
  hardwareTypeBadgeStyle as typeBadgeStyle, setHardwareTypeOrder,
} from '@/utils/constants'
import Button from '@/components/ui/button.vue'
import Input from '@/components/ui/input.vue'
import Label from '@/components/ui/label.vue'
import Card from '@/components/ui/card.vue'
import Table from '@/components/ui/table.vue'
import TableHeader from '@/components/ui/table-header.vue'
import TableBody from '@/components/ui/table-body.vue'
import TableRow from '@/components/ui/table-row.vue'
import TableHead from '@/components/ui/table-head.vue'
import TableCell from '@/components/ui/table-cell.vue'
import Checkbox from '@/components/ui/checkbox.vue'
import Spinner from '@/components/ui/spinner.vue'
import EmptyState from '@/components/ui/empty-state.vue'
import ListPager from '@/components/common/ListPager.vue'
import EntityActions from '@/components/common/EntityActions.vue'
import DataImportDialog from '@/components/common/DataImportDialog.vue'
import DropdownMenu from '@/components/ui/dropdown-menu.vue'
import DropdownMenuContent from '@/components/ui/dropdown-menu-content.vue'
import DropdownMenuItem from '@/components/ui/dropdown-menu-item.vue'
import Select from '@/components/ui/select.vue'
import SelectTrigger from '@/components/ui/select-trigger.vue'
import SelectContent from '@/components/ui/select-content.vue'
import SelectItem from '@/components/ui/select-item.vue'

const store = useHardwareStore()
const auth = useAuthStore()
const router = useRouter()
const { success } = useToast()
const { confirm } = useConfirm()

// 跳转设备详情（硬件列表「所属设备」联动）。
function goDevice(deviceId) {
  router.push(`/devices/${deviceId}`)
}
// 复制 SN：优先 Clipboard API，http 非安全上下文回退 execCommand 临时 textarea。
async function copySn(sn) {
  if (!sn) return
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(sn)
    } else {
      const ta = document.createElement('textarea')
      ta.value = sn
      ta.style.position = 'fixed'
      ta.style.opacity = '0'
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
    }
    success('SN 已复制')
  } catch (e) {
    // 复制失败静默（拦截器不提示，避免打扰）
  }
}

// 硬件类型配色基于「全量类型有序列表」统一计算（与耗材独立映射，避免串色）。
watch(
  () => store.types,
  (list) => setHardwareTypeOrder((list || []).map((t) => t.id)),
  { immediate: true },
)

// 写操作（新建 / 编辑 / 删除 / 分配回收）均需 hardware:edit。
const canEdit = computed(() => auth.hasPermission('hardware:edit'))

const { filter, clear } = usePersistentFilter('HardwareList', () => ({
  typeId: SELECT_ALL,
  categoryId: SELECT_ALL,
  status: SELECT_ALL,
  keyword: '',
}))
const viewMode = ref('card')

const page = ref(1)
const pageSize = computed(() => (viewMode.value === 'card' ? 12 : 20))
const totalPages = computed(() => Math.max(1, Math.ceil(store.total / pageSize.value)))

const typeSelected = computed(() => filter.typeId && filter.typeId !== SELECT_ALL)

function setView(mode) {
  if (viewMode.value === mode) return
  viewMode.value = mode
  page.value = 1
  load()
}

function buildParams() {
  return {
    page: page.value,
    size: pageSize.value,
    type_id: toFilterParam(filter.typeId),
    category_id: toFilterParam(filter.categoryId),
    status: toFilterParam(filter.status),
    keyword: filter.keyword || undefined,
  }
}
async function load() {
  await store.fetchItems(buildParams())
  // M-04：末页被删空则回退到有效页（统一 backToValidPage 计算）。
  if (store.items.length === 0 && page.value > 1 && store.total > 0) {
    page.value = backToValidPage(page.value, store.total, pageSize.value)
    await store.fetchItems(buildParams())
  }
}
function reload() {
  page.value = 1
  load()
}
function goPage(p) {
  if (p < 1 || p > totalPages.value) return
  page.value = p
  load()
}
function resetFilter() {
  clear()
  reload()
}
async function onTypeChange() {
  // 切换类型时清空分类并重新拉取该类型下的分类选项。
  filter.categoryId = SELECT_ALL
  await store.fetchCategories(typeSelected.value ? filter.typeId : '')
  reload()
}

// ===== 弹窗控制 =====
const formVisible = ref(false)
const formMode = ref('create')
const formItemId = ref('')
const historyVisible = ref(false)
const historyItem = ref(null)
const importVisible = ref(false)

// ===== 批量选择（仅表格模式，与机柜/机房列表一致）=====
const selected = ref(new Set())
function isSelected(id) {
  return selected.value.has(id)
}
function toggleRow(id) {
  const next = new Set(selected.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  selected.value = next
}
function toggleAllPage(v) {
  const next = new Set(selected.value)
  const ids = store.items.map((i) => i.id)
  if (v) ids.forEach((id) => next.add(id))
  else ids.forEach((id) => next.delete(id))
  selected.value = next
}
function clearSelection() {
  selected.value = new Set()
}
const allPageSelected = computed(() => store.items.length > 0 && store.items.every((i) => selected.value.has(i.id)))
const allPageIndeterminate = computed(() => {
  const n = store.items.filter((i) => selected.value.has(i.id)).length
  return n > 0 && n < store.items.length
})
// 批量删除：对选中硬件逐个调用删除接口（含 confirm 确认流程，与机柜/机房一致）。
async function batchDelete() {
  if (!selected.value.size) return
  const ids = [...selected.value]
  const ok = await confirm({
    title: '批量删除硬件',
    description: `确认删除选中的 ${ids.length} 件硬件？其全部变动记录将一并删除，此操作不可撤销。`,
    variant: 'danger',
    confirmText: '删除',
    cancelText: '取消',
  })
  if (!ok) return
  try {
    const results = await Promise.allSettled(ids.map((id) => hardwareApi.removeItem(id)))
    const failed = results.filter((r) => r.status === 'rejected').length
    if (failed === 0) success(`已删除 ${ids.length} 件硬件`)
    else success(`已删除 ${ids.length - failed} 件，失败 ${failed} 件`)
    clearSelection()
    await load()
  } catch (e) {
    // Promise.allSettled 不会 reject，此处仅兜底
  }
}

// ===== 导出 / 导入（与机柜/机房列表一致）=====
const exporting = ref(false)
async function onExport(type) {
  exporting.value = true
  try {
    const rows = await hardwareApi.exportAll({
      type_id: toFilterParam(filter.typeId),
      category_id: toFilterParam(filter.categoryId),
      status: toFilterParam(filter.status),
      keyword: filter.keyword || undefined,
    })
    await exportData({
      rows,
      columns: hardwareImportConfig.exportColumns,
      filename: '硬件列表',
      type,
    })
    success('导出成功')
  } catch (e) {
    // 导出失败由统一拦截器提示
  } finally {
    exporting.value = false
  }
}

function openCreate() {
  formMode.value = 'create'
  formItemId.value = ''
  formVisible.value = true
}
function openEdit(id) {
  formMode.value = 'edit'
  formItemId.value = id
  formVisible.value = true
}
function openHistory(item) {
  historyItem.value = item
  historyVisible.value = true
}
// 表格操作列的扩展动作（变动历史），复用 EntityActions 紧凑图标按钮样式。
function rowExtraActions(item) {
  return [{ key: 'history', label: '变动历史', icon: History, onClick: () => openHistory(item) }]
}

async function onDelete(item) {
  const ok = await confirm({
    title: '删除硬件',
    description: `确认删除硬件「${item.name}」${item.sn ? `（SN: ${item.sn}）` : ''}？其全部变动记录将一并删除，且不可撤销。`,
    variant: 'danger',
    confirmText: '删除',
  })
  if (!ok) return
  try {
    await store.removeItem(item.id)
    success('删除成功')
    load()
  } catch (e) {
    // 拦截器已提示（如已安装到设备须先回收）
  }
}

onMounted(async () => {
  await store.fetchTypes()
  await store.fetchCategories(typeSelected.value ? filter.typeId : '')
  load()
})
</script>

<style scoped>
/* P0 风格统一：toolbar 移交给全局 @utility（index.css）。 */
.grid-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 16px;
}
/* 批量操作条（与机柜/机房/设备列表一致） */
.batch-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  margin-bottom: 14px;
  border-radius: 12px;
  border: 1px solid hsl(var(--destructive) / 0.3);
  background: hsl(var(--destructive) / 0.08);
  animation: slide-in-up 0.3s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.batch-count {
  font-size: 13px;
  color: var(--muted-foreground);
}
.batch-count b {
  color: var(--foreground);
  font-weight: 600;
}
</style>
