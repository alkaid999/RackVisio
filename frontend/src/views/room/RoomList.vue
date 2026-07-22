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
                <span class="h-2 w-2 rounded-full" :style="{ backgroundColor: room.status === 'active' ? '#67C23A' : '#909399' }"></span>
                {{ room.status === 'active' ? '启用' : '停用' }}
              </span>
            </div>
            <div class="space-y-1.5 text-sm text-muted-foreground">
              <div class="flex justify-between"><span>编号</span><span class="text-foreground">{{ room.code }}</span></div>
              <div class="flex justify-between"><span>别名</span><span class="text-foreground">{{ room.alias || '—' }}</span></div>
              <div class="flex justify-between"><span>区域</span><span class="text-foreground">{{ room.area || '—' }}</span></div>
              <div class="flex justify-between"><span>楼宇/楼层</span><span class="text-foreground">{{ [room.building, room.floor].filter(Boolean).join(' / ') || '—' }}</span></div>
              <div class="flex justify-between"><span>地址</span><span class="text-foreground truncate max-w-[12rem]">{{ room.address || '—' }}</span></div>
            </div>
            <div class="mt-2.5 flex flex-wrap justify-end gap-1 border-t border-border pt-2.5">
              <Button variant="ghost" size="sm" @click.stop="goPlan(room.id)"><Map class="h-3.5 w-3.5" />平面图</Button>
              <EntityActions v-if="canEdit" variant="full" :show-view="false" @view="() => goDetail(room.id)" @edit="() => openEdit(room.id)" @delete="() => onDelete(room)" />
            </div>
          </Card>
        </div>
      </div>

      <!-- 表格视图 -->
      <div v-else>
        <div v-if="!store.rooms.length">
          <EmptyState :icon="Server" title="暂无机房" />
        </div>
        <Table v-else>
          <TableHeader>
            <TableRow>
              <TableHead v-for="col in roomColumns" :key="col.key">{{ col.label }}</TableHead>
              <TableHead class="w-32 text-right">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow v-for="room in store.rooms" :key="room.id">
              <TableCell v-for="col in roomColumns" :key="col.key" :class="isMutedCol(col.key) ? 'text-muted-foreground' : ''">
                <template v-if="col.key === 'name'">
                  <button class="font-medium text-primary hover:underline" @click="goDetail(room.id)">{{ room.name }}</button>
                </template>
                <template v-else-if="col.key === 'code'">{{ room.code }}</template>
                <template v-else-if="col.key === 'alias'">{{ room.alias || '—' }}</template>
                <template v-else-if="col.key === 'area'">{{ room.area || '—' }}</template>
                <template v-else-if="col.key === 'building_floor'">{{ [room.building, room.floor].filter(Boolean).join(' / ') || '—' }}</template>
                <template v-else-if="col.key === 'address'">{{ room.address || '—' }}</template>
                <template v-else-if="col.key === 'status'">
                  <span class="inline-flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
                    <span class="h-2 w-2 rounded-full" :style="{ backgroundColor: room.status === 'active' ? '#67C23A' : '#909399' }"></span>
                    {{ room.status === 'active' ? '启用' : '停用' }}
                  </span>
                </template>
              </TableCell>
              <TableCell class="text-right">
                <div class="flex justify-end gap-1">
                  <Button variant="ghost" size="sm" @click.stop="goPlan(room.id)">平面图</Button>
                  <EntityActions v-if="canEdit" @view="() => goDetail(room.id)" @edit="() => openEdit(room.id)" @delete="() => onDelete(room)" />
                </div>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </div>
    </template>

    <!-- 分页（卡片/表格共用，跟随当前视图模式每页条数） -->
    <ListPager v-if="store.total > 0" :total="store.total" :page="page" :page-size="pageSize" @change="goPage" />

    <!-- 新建 / 编辑机房弹窗 -->
    <RoomForm v-model:visible="formVisible" :mode="formMode" :room-id="formRoomId" @saved="load" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { LayoutGrid, List, Plus, Server, Search, Filter, Undo2, MapPin, Map, Activity } from 'lucide-vue-next'
import { useRoomStore } from '@/stores/room'
import { useAuthStore } from '@/stores/auth'
import RoomForm from '@/views/room/RoomForm.vue'
import roomApi from '@/api/room'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import { usePersistentFilter } from '@/composables/usePersistentFilter'
import { ROOM_STATUS_OPTIONS, SELECT_ALL, toFilterParam } from '@/utils/constants'
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
const pageSize = computed(() => (viewMode.value === 'card' ? 12 : 10))
const totalPages = computed(() => Math.max(1, Math.ceil(store.total / pageSize.value)))
function setView(mode) {
  if (viewMode.value === mode) return
  viewMode.value = mode
  page.value = 1
  load()
}

// 机房列表表格固定列（移除「显示字段」配置功能）。
const roomColumns = [
  { key: 'name', label: '名称' },
  { key: 'code', label: '编号' },
  { key: 'alias', label: '别名' },
  { key: 'area', label: '区域' },
  { key: 'building_floor', label: '楼宇/楼层' },
  { key: 'address', label: '地址' },
  { key: 'status', label: '状态' },
]
// 名称列以强调样式呈现，其余文本列用 muted。
const EMPHASIS_ROOM_COLS = new Set(['name'])
function isMutedCol(key) {
  return !EMPHASIS_ROOM_COLS.has(key)
}

const formVisible = ref(false)
const formMode = ref('create')
const formRoomId = ref('')

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
  // 末页被删空则回退到有效页
  if (store.rooms.length === 0 && page.value > 1 && store.total > 0) {
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
function goPlan(id) {
  router.push(`/rooms/${id}/plan`)
}
async function onDelete(room) {
  const ok = await confirm({
    title: '删除机房',
    description: `确认删除机房「${room.name}」？该操作不可撤销，其下机柜与设备将一并影响。`,
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
.toolbar {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 10px;
  padding: 14px 16px;
  margin-bottom: 16px;
}
.grid-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 16px;
}
</style>
