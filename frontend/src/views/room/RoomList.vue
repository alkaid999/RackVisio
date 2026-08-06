<template>
  <div class="room-list">
    <div class="page-head">
      <div>
        <h2 class="page-title">机房列表</h2>
        <p class="page-sub">共 {{ store.total }} 个机房 · 支持按区域/状态筛选与关键字（名称/编号/别名）搜索</p>
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
        <!-- 导出（保留当前筛选与字段顺序） -->
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
        <!-- 导入（需 room:edit） -->
        <Button v-if="canEdit" variant="outline" @click="importVisible = true">
          <Upload class="h-4 w-4" />导入
        </Button>
        <Button v-if="canEdit" class="ml-auto" @click="openCreate"><Plus class="h-4 w-4" />新建机房</Button>
      </div>
    </div>

    <!-- 筛选工具栏 -->
    <div class="toolbar">
      <div class="flex flex-wrap items-end gap-4">
        <div class="flex flex-col gap-1">
          <Label>关键字</Label>
          <div class="relative">
            <Search class="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input v-model="filter.keyword" placeholder="名称 / 编号 / 别名" class="w-52 pl-9" @keyup.enter="reload" />
          </div>
        </div>
        <div class="flex flex-col gap-1">
          <Label class="flex items-center gap-1"><MapPin class="h-3.5 w-3.5 text-muted-foreground" />区域</Label>
          <Select v-model="filter.area" class="w-36" @update:model-value="reload">
            <SelectTrigger placeholder="全部" />
            <SelectContent>
              <SelectItem :value="SELECT_ALL">全部</SelectItem>
              <SelectItem v-for="a in areaOptions" :key="a" :value="a">{{ a }}</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div class="flex flex-col gap-1">
          <Label class="flex items-center gap-1"><Activity class="h-3.5 w-3.5 text-muted-foreground" />状态</Label>
          <Select v-model="filter.status" class="w-32" @update:model-value="reload">
            <SelectTrigger placeholder="全部" />
            <SelectContent>
              <SelectItem :value="SELECT_ALL">全部</SelectItem>
              <SelectItem v-for="o in ROOM_STATUS_OPTIONS" :key="o.value" :value="o.value">{{ o.label }}</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div class="flex items-center gap-2 pb-1">
          <Button @click="load"><Filter class="h-4 w-4" />查询</Button>
          <Button variant="outline" @click="resetFilter"><Undo2 class="h-4 w-4" />重置</Button>
        </div>
      </div>
    </div>

    <!-- 加载态 -->
    <div v-if="store.loading" class="flex justify-center py-20">
      <Spinner class="h-6 w-6 text-primary" />
    </div>

    <template v-else>
      <!-- 卡片视图 -->
      <div v-if="viewMode === 'card'">
        <div v-if="!store.rooms.length">
          <EmptyState :icon="Server" title="暂无机房" />
        </div>
        <div v-else class="grid-cards">
          <Card
            v-for="room in store.rooms"
            :key="room.id"
            hover
            class="group cursor-pointer"
            @click="goDetail(room.id)"
          >
            <div class="mb-3 flex items-start justify-between gap-2">
              <div class="flex min-w-0 items-center gap-2">
                <span class="truncate text-base font-semibold text-foreground">{{ room.name }}</span>
              </div>
              <span class="inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap text-sm font-medium text-muted-foreground">
                <!-- P1：状态点收敛到语义令牌色（success=启用 / muted-foreground=停用） -->
                <span
                  class="h-2 w-2 rounded-full"
                  :class="room.status === 'active' ? 'bg-success' : 'bg-muted-foreground/60'"
                ></span>
                {{ room.status === 'active' ? '启用' : '停用' }}
              </span>
            </div>
            <!-- 信息区：每行「小图标 + 文本」（与机柜列表卡片一致） -->
            <div class="mt-2 space-y-1.5 text-xs text-muted-foreground">
              <div class="flex items-center gap-1">
                <MapPin class="h-3.5 w-3.5 shrink-0" />
                <span class="truncate">编号：{{ room.code || '—' }}</span>
              </div>
              <div class="flex items-center gap-1">
                <Tag class="h-3.5 w-3.5 shrink-0" />
                <span class="truncate">别名：{{ room.alias || '—' }}</span>
              </div>
              <div class="flex items-center gap-1">
                <MapIcon class="h-3.5 w-3.5 shrink-0" />
                <span class="truncate">区域：{{ room.area || '—' }}</span>
              </div>
              <div class="flex items-center gap-1">
                <Building2 class="h-3.5 w-3.5 shrink-0" />
                <span class="truncate">楼宇 / 楼层：{{ [room.building, room.floor].filter(Boolean).join(' / ') || '—' }}</span>
              </div>
              <div v-if="room.address" class="flex items-center gap-1">
                <MapPin class="h-3.5 w-3.5 shrink-0" />
                <span class="truncate">地址：{{ room.address }}</span>
              </div>
            </div>
            <div class="mt-2.5 flex flex-wrap justify-end gap-1 border-t border-border pt-2.5">
              <EntityActions v-if="canEdit" variant="full" :show-view="false" @view="() => goDetail(room.id)" @edit="() => openEdit(room.id)" @delete="() => onDelete(room)" />
            </div>
          </Card>
        </div>
      </div>

      <!-- 表格视图（与硬件列表标准表格一致） -->
      <div v-else>
        <div v-if="store.loading" class="flex justify-center py-16">
          <Spinner class="h-6 w-6 text-primary" />
        </div>
        <template v-else>
          <div v-if="!store.rooms.length">
            <EmptyState :icon="Server" title="暂无机房" />
          </div>
          <Table v-else class="table-fixed w-full">
            <TableHeader>
              <TableRow>
                <TableHead v-for="col in roomColumns" :key="col.key" :class="col.width">{{ col.label }}</TableHead>
                <TableHead class="w-32 text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow v-for="room in store.rooms" :key="room.id">
                <TableCell v-for="col in roomColumns" :key="col.key" :class="isMutedCol(col.key) ? 'text-muted-foreground' : ''">
                  <template v-if="col.key === 'name'">
                    <button class="block w-full truncate font-medium text-primary hover:underline" @click="goDetail(room.id)">{{ room.name }}</button>
                  </template>
                <template v-else-if="col.key === 'code'">{{ room.code }}</template>
                <template v-else-if="col.key === 'alias'">{{ room.alias || '—' }}</template>
                <template v-else-if="col.key === 'area'">{{ room.area || '—' }}</template>
                <template v-else-if="col.key === 'building_floor'">{{ [room.building, room.floor].filter(Boolean).join(' / ') || '—' }}</template>
                <template v-else-if="col.key === 'address'">{{ room.address || '—' }}</template>
                <template v-else-if="col.key === 'status'">
                  <span class="inline-flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
                    <!-- P1：状态点收敛到语义令牌色 -->
                    <span
                      class="h-2 w-2 rounded-full"
                      :class="room.status === 'active' ? 'bg-success' : 'bg-muted-foreground/60'"
                    ></span>
                    {{ room.status === 'active' ? '启用' : '停用' }}
                  </span>
                </template>
              </TableCell>
              <TableCell class="text-right">
                <div class="flex justify-end gap-1">
                  <EntityActions v-if="canEdit" @view="() => goDetail(room.id)" @edit="() => openEdit(room.id)" @delete="() => onDelete(room)" />
                </div>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
        </template>
      </div>
    </template>

    <!-- 分页（卡片/表格共用，跟随当前视图模式每页条数） -->
    <ListPager v-if="store.total > 0" :total="store.total" :page="page" :page-size="pageSize" @change="goPage" />

    <!-- 新建 / 编辑机房弹窗 -->
    <RoomForm v-model:visible="formVisible" :mode="formMode" :room-id="formRoomId" @saved="load" />

    <!-- 批量导入弹窗 -->
    <DataImportDialog
      v-model:visible="importVisible"
      :config="roomImportConfig"
      :import-fn="(items) => roomApi.import(items)"
      @imported="load"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { LayoutGrid, List, Plus, Server, Search, Filter, Undo2, MapPin, Activity, Download, Upload, ChevronDown, FileSpreadsheet, FileText, Tag, Map as MapIcon, Building2 } from 'lucide-vue-next'
import { useRoomStore } from '@/stores/room'
import { useAuthStore } from '@/stores/auth'
import RoomForm from '@/views/room/RoomForm.vue'
import roomApi from '@/api/room'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import { usePersistentFilter } from '@/composables/usePersistentFilter'
import { backToValidPage } from '@/composables/useListReload'
import { ROOM_STATUS_OPTIONS, SELECT_ALL, toFilterParam } from '@/utils/constants'
import { exportData } from '@/utils/excel'
import { roomImportConfig } from '@/utils/importConfig'
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
import Spinner from '@/components/ui/spinner.vue'
import EmptyState from '@/components/ui/empty-state.vue'
import EntityActions from '@/components/common/EntityActions.vue'
import ListPager from '@/components/common/ListPager.vue'
import Select from '@/components/ui/select.vue'
import SelectTrigger from '@/components/ui/select-trigger.vue'
import SelectContent from '@/components/ui/select-content.vue'
import SelectItem from '@/components/ui/select-item.vue'
import DropdownMenu from '@/components/ui/dropdown-menu.vue'
import DropdownMenuContent from '@/components/ui/dropdown-menu-content.vue'
import DropdownMenuItem from '@/components/ui/dropdown-menu-item.vue'
import DataImportDialog from '@/components/common/DataImportDialog.vue'

const router = useRouter()
const store = useRoomStore()
const auth = useAuthStore()
const { success } = useToast()
const { confirm } = useConfirm()

// 编辑（新增 / 删除）机房需 room:edit；只读用户隐藏全部操作按钮，避免点击后 403。
const canEdit = computed(() => auth.hasPermission('room:edit'))

// 筛选持久化：按路由名 RoomList 存 sessionStorage，返回上级再回来保留筛选；logout 统一清空。
const { filter, clear } = usePersistentFilter('RoomList', () => ({ keyword: '', area: SELECT_ALL, status: SELECT_ALL }))
const viewMode = ref('card')

// 分页：卡片每页 12，表格每页 10（服务端分页）。
const page = ref(1)
const pageSize = computed(() => (viewMode.value === 'card' ? 12 : 20))
const totalPages = computed(() => Math.max(1, Math.ceil(store.total / pageSize.value)))
function setView(mode) {
  if (viewMode.value === mode) return
  viewMode.value = mode
  page.value = 1
  load()
}

// 机房列表表格固定列（移除「显示字段」配置功能）。
const roomColumns = [
  { key: 'name', label: '名称', width: 'w-36' },
  { key: 'code', label: '编号', width: 'w-24' },
  { key: 'alias', label: '别名', width: 'w-24' },
  { key: 'area', label: '区域', width: 'w-24' },
  { key: 'building_floor', label: '楼宇/楼层', width: 'w-32' },
  { key: 'address', label: '地址', width: 'w-40' },
  { key: 'status', label: '状态', width: 'w-20' },
]
// 名称列以强调样式呈现，其余文本列用 muted。
const EMPHASIS_ROOM_COLS = new Set(['name'])
function isMutedCol(key) {
  return !EMPHASIS_ROOM_COLS.has(key)
}

const formVisible = ref(false)
const formMode = ref('create')
const formRoomId = ref('')

// 导出 / 导入状态
const exporting = ref(false)
const importVisible = ref(false)
async function onExport(type) {
  // 防重（M-03）：导出期间忽略重复点击（配合 Button :loading 禁用）。
  if (exporting.value) return
  exporting.value = true
  try {
    const rows = await roomApi.exportAll(buildParams())
    await exportData({
      rows,
      columns: roomImportConfig.exportColumns,
      filename: '机房列表',
      type,
    })
    success('导出成功')
  } catch (e) {
    // 导出失败由统一拦截器提示
  } finally {
    exporting.value = false
  }
}

// 区域下拉选项：从全量机房去重得到（不受当前筛选影响）。
const allRooms = ref([])
const areaOptions = computed(() => {
  const set = new Set()
  for (const r of allRooms.value) if (r.area) set.add(r.area)
  return [...set].sort()
})

function buildParams() {
  return {
    page: page.value,
    size: pageSize.value,
    keyword: filter.keyword || undefined,
    area: toFilterParam(filter.area),
    status: toFilterParam(filter.status),
  }
}
async function load() {
  await store.fetchList(buildParams())
  // M-04：末页被删空则回退到有效页（统一 backToValidPage 计算）。
  if (store.rooms.length === 0 && page.value > 1 && store.total > 0) {
    page.value = backToValidPage(page.value, store.total, pageSize.value)
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
  reload()
}

function openCreate() {
  formMode.value = 'create'
  formRoomId.value = ''
  formVisible.value = true
}
function openEdit(id) {
  formMode.value = 'edit'
  formRoomId.value = id
  formVisible.value = true
}
function goDetail(id) {
  router.push(`/rooms/${id}`)
}
async function onDelete(room) {
  const ok = await confirm({
    title: '删除机房',
    description: `确认删除机房「${room.name}」？将永久删除该机房及其下空机柜。若机房内仍有已上架设备则无法删除（需先下架）。`,
    variant: 'danger',
    confirmText: '删除',
  })
  if (!ok) return
  try {
    await roomApi.remove(room.id)
    success('删除成功')
    load()
  } catch (e) {
    // 接口报错已由统一拦截器提示
  }
}

onMounted(async () => {
  const data = await roomApi.list({ size: 200 })
  allRooms.value = data.items || []
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
</style>
