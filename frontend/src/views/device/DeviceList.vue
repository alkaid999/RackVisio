<template>
  <div class="device-list">
    <div class="page-head">
      <div>
        <h2 class="page-title">设备列表</h2>
        <p class="page-sub">共 {{ store.total }} 台设备 · 支持按机房/类型/状态筛选与关键字（名称/型号/SN）搜索</p>
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
        <Button v-if="canEdit" class="ml-auto" @click="openCreate"><CirclePlus class="h-4 w-4" />新增设备</Button>
      </div>
    </div>

    <!-- 筛选工具栏 -->
    <div class="toolbar">
      <div class="flex flex-wrap items-end gap-4">
        <div class="flex flex-col gap-1">
          <Label>关键字</Label>
          <div class="relative">
            <Search class="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input v-model="filter.keyword" placeholder="名称 / 型号 / SN" class="w-52 pl-9" @keyup.enter="reload" />
          </div>
        </div>
        <div class="flex flex-col gap-1">
          <Label class="flex items-center gap-1"><Building class="h-3.5 w-3.5 text-muted-foreground" />机房</Label>
          <Select v-model="filter.roomId" class="w-40" @update:model-value="onRoomChange">
            <SelectTrigger placeholder="全部" />
            <SelectContent>
              <SelectItem :value="SELECT_ALL">全部</SelectItem>
              <SelectItem v-for="r in roomOptions" :key="r.id" :value="r.id">{{ r.name }}（{{ r.code }}）</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div class="flex flex-col gap-1">
          <Label class="flex items-center gap-1"><Boxes class="h-3.5 w-3.5 text-muted-foreground" />机柜</Label>
          <Select v-model="filter.rackId" class="w-40" :disabled="!toFilterParam(filter.roomId)" @update:model-value="reload">
            <SelectTrigger placeholder="全部" />
            <SelectContent>
              <SelectItem :value="SELECT_ALL">全部</SelectItem>
              <SelectItem v-for="r in rackOptions" :key="r.id" :value="r.id">{{ r.name }}</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div class="flex flex-col gap-1">
          <Label class="flex items-center gap-1"><SlidersHorizontal class="h-3.5 w-3.5 text-muted-foreground" />类型</Label>
          <Select v-model="filter.deviceType" class="w-32" @update:model-value="reload">
            <SelectTrigger placeholder="全部" />
            <SelectContent>
              <SelectItem :value="SELECT_ALL">全部</SelectItem>
              <SelectItem v-for="o in DEVICE_TYPE_OPTIONS" :key="o.value" :value="o.value">{{ o.label }}</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div class="flex flex-col gap-1">
          <Label class="flex items-center gap-1"><Activity class="h-3.5 w-3.5 text-muted-foreground" />状态</Label>
          <Select v-model="filter.status" class="w-32" @update:model-value="reload">
            <SelectTrigger placeholder="全部" />
            <SelectContent>
              <SelectItem :value="SELECT_ALL">全部</SelectItem>
              <SelectItem v-for="o in DEVICE_STATUS_OPTIONS" :key="o.value" :value="o.value">{{ o.label }}</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div class="flex flex-col gap-1">
          <Label class="flex items-center gap-1"><ServerCog class="h-3.5 w-3.5 text-muted-foreground" />资产范围</Label>
          <button
            type="button"
            class="h-9 rounded-md border px-3 text-sm transition-colors"
            :class="showFacility ? 'border-primary bg-primary/10 text-primary' : 'border-border bg-muted text-muted-foreground hover:text-foreground'"
            :title="showFacility ? '当前包含基础设施（配线架/ODF配线架/其他设施）' : '仅显示资产设备，隐藏基础设施'"
            @click="toggleFacility"
          >
            {{ showFacility ? '含设施' : '仅资产' }}
          </button>
        </div>
        <div class="flex items-center gap-2 pb-1">
          <Button @click="load"><Filter class="h-4 w-4" />查询</Button>
          <Button variant="outline" @click="resetFilter"><Undo2 class="h-4 w-4" />重置</Button>
        </div>
      </div>
    </div>

    <!-- 卡片视图 -->
    <div v-if="viewMode === 'card'">
      <div v-if="store.loading" class="flex justify-center py-16">
        <Spinner class="h-6 w-6 text-primary" />
      </div>
      <template v-else>
        <div v-if="store.devices.length" class="grid-cards">
          <DeviceCard
            v-for="d in store.devices"
            :key="d.id"
            :device="d"
            :can-edit="canEdit"
            @view="goDetail"
            @edit="onEdit"
            @delete="onDelete"
          />
        </div>
        <EmptyState v-else title="暂无设备" />
      </template>
    </div>

    <!-- 表格视图 -->
    <div v-else>
      <div v-if="store.loading" class="flex justify-center py-16">
        <Spinner class="h-6 w-6 text-primary" />
      </div>
      <Table v-else>
        <TableHeader>
          <TableRow>
            <TableHead v-for="col in deviceColumns" :key="col.key" :class="colWidthClass(col.key)">
              {{ col.label }}
            </TableHead>
            <TableHead class="w-32 text-right">操作</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow v-for="d in store.devices" :key="d.id">
            <TableCell
              v-for="col in deviceColumns"
              :key="col.key"
              :class="[isMutedCol(col.key) ? 'text-muted-foreground' : '', colWidthClass(col.key)]"
            >
              <template v-if="col.key === 'name'">
                <button class="font-medium text-primary hover:underline" @click="goDetail(d.id)">{{ d.name }}</button>
              </template>
              <template v-else-if="col.key === 'device_type'"><DeviceTypeTag :type="d.device_type" /></template>
              <template v-else-if="col.key === 'status'"><StatusBadge type="device" :value="d.status" /></template>
              <template v-else-if="col.key === 'device_code'">{{ d.device_code || '—' }}</template>
              <template v-else-if="col.key === 'model'">{{ d.model || '—' }}</template>
              <template v-else-if="col.key === 'ip_address'">{{ d.ip_address || '—' }}</template>
              <template v-else-if="col.key === 'u_height'">{{ d.u_height ? d.u_height + 'U' : '—' }}</template>
            </TableCell>
            <TableCell class="text-right">
              <div class="flex justify-end gap-1">
                <EntityActions :show-edit="canEdit" :show-delete="canEdit" @view="() => goDetail(d.id)" @edit="() => onEdit(d)" @delete="() => onDelete(d)" />
              </div>
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </div>

    <!-- 分页（卡片/表格共用，跟随当前视图模式每页条数） -->
    <ListPager v-if="store.total > 0" :total="store.total" :page="page" :page-size="pageSize" @change="goPage" />

    <!-- 新增 / 编辑设备弹窗（open 由 openDeviceForm() 在按钮手势内同步触发） -->
    <DeviceForm @saved="load" />
  </div>
</template>

<script setup>
import { reactive, ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import { openDeviceForm } from '@/composables/useDeviceFormState'
import { useDeviceStore } from '@/stores/device'
import { useRoomStore } from '@/stores/room'
import { useAuthStore } from '@/stores/auth'
import { usePersistentFilter } from '@/composables/usePersistentFilter'
import roomApi from '@/api/room'
import DeviceCard from '@/components/device/DeviceCard.vue'
import DeviceForm from '@/views/device/DeviceForm.vue'
import EntityActions from '@/components/common/EntityActions.vue'
import DeviceTypeTag from '@/components/device/DeviceTypeTag.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import Table from '@/components/ui/table.vue'
import TableHeader from '@/components/ui/table-header.vue'
import TableBody from '@/components/ui/table-body.vue'
import TableRow from '@/components/ui/table-row.vue'
import TableHead from '@/components/ui/table-head.vue'
import TableCell from '@/components/ui/table-cell.vue'
import { DEVICE_TYPE_OPTIONS, DEVICE_STATUS_OPTIONS, SELECT_ALL, toFilterParam } from '@/utils/constants'
import { CirclePlus, Search, Filter, Undo2, Building, Boxes, SlidersHorizontal, Activity, LayoutGrid, List, ServerCog } from 'lucide-vue-next'
import Button from '@/components/ui/button.vue'
import Input from '@/components/ui/input.vue'
import Label from '@/components/ui/label.vue'
import Select from '@/components/ui/select.vue'
import SelectTrigger from '@/components/ui/select-trigger.vue'
import SelectContent from '@/components/ui/select-content.vue'
import SelectItem from '@/components/ui/select-item.vue'
import EmptyState from '@/components/ui/empty-state.vue'
import Spinner from '@/components/ui/spinner.vue'
import ListPager from '@/components/common/ListPager.vue'

const router = useRouter()
const store = useDeviceStore()
const roomStore = useRoomStore()
const auth = useAuthStore()

const { success } = useToast()
const { confirm } = useConfirm()
// 编辑（新增 / 删除）设备需 device:edit；只读用户隐藏全部写操作按钮。
const canEdit = computed(() => auth.hasPermission('device:edit'))

const { filter, clear } = usePersistentFilter(
  'DeviceList',
  () => ({ keyword: '', roomId: SELECT_ALL, rackId: SELECT_ALL, deviceType: SELECT_ALL, status: SELECT_ALL }),
  onFilterRestored
)

// 恢复筛选后：若已选定机房，重新加载机柜下拉（否则机柜筛选项为空）。
function onFilterRestored(f) {
  if (toFilterParam(f.roomId)) {
    roomStore.fetchRacks(f.roomId)
  }
}
const roomOptions = computed(() => roomStore.rooms)
const rackOptions = computed(() => roomStore.racks)
const viewMode = ref('card')
// 资产范围：默认仅资产（隐藏设施），切换后包含基础设施（配线架/ODF配线架/其他设施）。
const showFacility = ref(false)
function toggleFacility() {
  showFacility.value = !showFacility.value
  reload()
}

// 分页：卡片模式每页 12 条，表格模式每页 10 条（服务端分页）。
const page = ref(1)
const pageSize = computed(() => (viewMode.value === 'card' ? 12 : 10))
const totalPages = computed(() => Math.max(1, Math.ceil(store.total / pageSize.value)))
function setView(mode) {
  if (viewMode.value === mode) return
  viewMode.value = mode
  page.value = 1
  load()
}

// 设备列表表格固定列：移除「显示字段」配置功能，统一默认展示以下核心字段。
const deviceColumns = [
  { key: 'name', label: '设备名称' },
  { key: 'device_type', label: '设备类型' },
  { key: 'model', label: '设备型号' },
  { key: 'status', label: '设备状态' },
  { key: 'device_code', label: '设备编号' },
  { key: 'ip_address', label: 'IP地址' },
  { key: 'u_height', label: '设备U数' },
]
// 名称 / 类型 / 状态 以强调样式呈现，其余文本列用 muted。
const EMPHASIS_COLS = new Set(['name', 'device_type', 'status'])
function isMutedCol(key) {
  return !EMPHASIS_COLS.has(key)
}
// 表格列宽：编号 / IP / U 数等文本列设最小宽度，避免内容换行。
const COL_WIDTH = {
  device_code: 'min-w-[11rem]',
  ip_address: 'min-w-[9rem]',
  u_height: 'min-w-[6rem]',
}
function colWidthClass(key) {
  return COL_WIDTH[key] || ''
}

function buildParams() {
  return {
    page: page.value,
    size: pageSize.value,
    room_id: toFilterParam(filter.roomId),
    rack_id: toFilterParam(filter.rackId),
    device_type: toFilterParam(filter.deviceType),
    status: toFilterParam(filter.status),
    keyword: filter.keyword || undefined,
    // 默认仅资产（隐藏设施）；开启「含设施」后不过滤 is_asset，展示全部。
    is_asset: showFacility.value ? undefined : true,
  }
}
async function load() {
  await store.fetchList(buildParams())
  // 末页被删空则回退到有效页，避免停留在空页
  if (store.devices.length === 0 && page.value > 1 && store.total > 0) {
    page.value = Math.max(1, totalPages.value)
    await store.fetchList(buildParams())
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
  roomStore.racks = []
  reload()
}
// 切换机房时加载其机柜，并清空已选机柜。
async function onRoomChange() {
  filter.rackId = SELECT_ALL
  if (toFilterParam(filter.roomId)) {
    await roomStore.fetchRacks(filter.roomId)
  } else {
    roomStore.racks = []
  }
  reload()
}
function openCreate() {
  openDeviceForm({ mode: 'create', presetRackId: toFilterParam(filter.rackId) })
}
function goDetail(id) {
  router.push(`/devices/${id}`)
}
function onEdit(device) {
  openDeviceForm({ mode: 'edit', deviceId: device.id })
}
async function onDelete(device) {
  const ok = await confirm({
    title: '提示',
    description: `确认删除设备「${device.name}」？删除后其端口与链路将一并清理。`,
    variant: 'danger',
    confirmText: '删除',
    cancelText: '取消',
  })
  if (!ok) return
  try {
    await store.remove(device.id)
    success('删除成功')
    load()
  } catch (e) {
    // 取消或错误
  }
}

onMounted(async () => {
  await roomStore.fetchList({ page: 1, size: 200 })
  load()
})
</script>

<style scoped>
.page-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}
.page-title {
  margin: 0 0 6px;
  font-size: 22px;
  font-weight: 600;
}
.page-sub {
  margin: 0;
  color: #606266;
  font-size: 13px;
}
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
.col-span-full {
  grid-column: 1 / -1;
}
</style>
