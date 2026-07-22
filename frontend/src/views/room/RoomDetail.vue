<template>
  <div class="room-detail">
    <div v-if="loading" class="flex justify-center py-16">
      <Spinner class="h-6 w-6 text-primary" />
    </div>
    <template v-else-if="room">
      <!-- 标题栏 -->
      <div class="page-head">
        <div>
          <h2 class="page-title">
            {{ room.name }}
            <small class="text-slate-400 font-normal">（{{ room.code }}）</small>
          </h2>
          <p class="page-sub">
            编号：{{ room.code }} · 状态：
            <Badge :variant="room.status === 'active' ? 'success' : 'secondary'">
              {{ room.status === 'active' ? '启用' : '停用' }}
            </Badge>
          </p>
        </div>
        <div class="flex gap-2">
          <Button variant="outline" @click="goPlan">平面图</Button>
          <Button v-if="canEditRoom" variant="ghost" size="icon" aria-label="编辑" title="编辑" @click="roomFormVisible = true"><Pencil class="h-4 w-4" /></Button>
          <Button v-if="canEditRoom" variant="ghost" size="icon" class="text-destructive hover:text-destructive" aria-label="删除" title="删除" @click="onDeleteRoom"><Trash2 class="h-4 w-4" /></Button>
          <Button variant="outline" @click="goBack"><ChevronLeft class="h-4 w-4" />返回</Button>
        </div>
      </div>

      <!-- 基本信息 -->
      <Card class="mb-5">
        <template #header><span class="section-title flex items-center gap-1.5"><ClipboardList class="h-4 w-4" />基本信息</span></template>
        <div class="grid grid-cols-1 gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
          <div class="flex gap-2"><span class="shrink-0 text-muted-foreground flex items-center gap-1"><Heading class="h-3.5 w-3.5" />名称</span><span>{{ room.name }}</span></div>
          <div class="flex gap-2"><span class="shrink-0 text-muted-foreground flex items-center gap-1"><Hash class="h-3.5 w-3.5" />编号</span><span class="font-mono">{{ room.code }}</span></div>
          <div class="flex gap-2"><span class="shrink-0 text-muted-foreground flex items-center gap-1"><Tag class="h-3.5 w-3.5" />别名</span><span>{{ room.alias || '—' }}</span></div>
          <div class="flex gap-2"><span class="shrink-0 text-muted-foreground flex items-center gap-1"><MapPin class="h-3.5 w-3.5" />区域</span><span>{{ room.area || '—' }}</span></div>
          <div class="flex gap-2"><span class="shrink-0 text-muted-foreground flex items-center gap-1"><Building2 class="h-3.5 w-3.5" />所属楼宇</span><span>{{ room.building || '—' }}</span></div>
          <div class="flex gap-2"><span class="shrink-0 text-muted-foreground flex items-center gap-1"><Layers class="h-3.5 w-3.5" />所在楼层</span><span>{{ room.floor || '—' }}</span></div>
          <div class="flex gap-2"><span class="shrink-0 text-muted-foreground flex items-center gap-1"><Map class="h-3.5 w-3.5" />机房地址</span><span>{{ room.address || '—' }}</span></div>
          <div class="flex gap-2"><span class="shrink-0 text-muted-foreground flex items-center gap-1"><Signal class="h-3.5 w-3.5" />状态</span><Badge :variant="room.status === 'active' ? 'success' : 'secondary'">{{ room.status === 'active' ? '启用' : '停用' }}</Badge></div>
        </div>
      </Card>

      <!-- 容量统计 -->
      <StatsPanel v-if="stats" :stats="stats" class="mb-5" />

      <!-- 机柜列表 -->
      <Card class="mb-5">
        <template #header>
          <div class="flex items-center justify-between">
            <span class="section-title">机柜列表（{{ racks.length }}）</span>
            <div class="flex items-center gap-2">
              <div class="inline-flex rounded-lg border border-border bg-muted p-0.5">
                <button
                  type="button"
                  class="flex h-8 items-center gap-1.5 rounded-md px-3 text-sm transition-all"
                  :class="rackView === 'card' ? 'bg-background text-foreground shadow-soft' : 'text-muted-foreground hover:text-foreground'"
                  @click="rackView = 'card'"
                >
                  <LayoutGrid class="h-4 w-4" />卡片
                </button>
                <button
                  type="button"
                  class="flex h-8 items-center gap-1.5 rounded-md px-3 text-sm transition-all"
                  :class="rackView === 'table' ? 'bg-background text-foreground shadow-soft' : 'text-muted-foreground hover:text-foreground'"
                  @click="rackView = 'table'"
                >
                  <List class="h-4 w-4" />表格
                </button>
              </div>
              <Button v-if="canEditRack" size="sm" @click="openCreateRack"><Plus class="h-4 w-4" />新增机柜</Button>
            </div>
          </div>
        </template>

        <!-- 卡片视图 -->
        <div v-if="rackView === 'card'" class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
          <div
            v-for="r in racks"
            :key="r.id"
            class="rack-mini-card group cursor-pointer"
            @click="goRack(r.id)"
          >
            <div class="flex items-center justify-between mb-2">
              <span class="font-semibold text-slate-800 truncate">{{ r.name }}</span>
              <StatusBadge type="rack" :value="r.status" />
            </div>
            <div class="text-xs text-slate-400">{{ r.column_code }} / {{ r.code }}</div>
            <div class="text-xs text-slate-500 mt-1 flex items-center gap-1">
              <MapPin class="w-3 h-3" />
              <span v-if="r.rack_group">{{ r.rack_group }}</span>
              <span v-else class="text-slate-400">未分组</span>
            </div>
            <div class="mt-2 flex items-center justify-between text-xs text-slate-500 tabular-nums">
              <span>{{ r.used_u }} / {{ r.total_u }}U</span>
              <span class="font-medium text-slate-700">{{ fillPct(r) }}%</span>
            </div>
            <div class="rack-mini-bar">
              <div class="rack-mini-fill" :style="{ width: fillPct(r) + '%', background: capColor(r) }" />
            </div>
            <div class="mt-2 flex justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
              <EntityActions :show-edit="canEditRack" :show-delete="canEditRack" @view="() => goRack(r.id)" @edit="() => onEditRack(r)" @delete="() => onDeleteRack(r)" />
            </div>
          </div>
          <EmptyState v-if="!racks.length" title="暂无机柜" class="col-span-full" />
        </div>

        <!-- 表格视图 -->
        <Table v-else>
          <TableHeader>
            <TableRow>
              <TableHead class="w-28">列/编号</TableHead>
              <TableHead>名称</TableHead>
              <TableHead class="w-28">分组</TableHead>
              <TableHead class="w-40">容量</TableHead>
              <TableHead class="w-28">状态</TableHead>
              <TableHead class="text-right">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow v-for="row in racks" :key="row.id">
              <TableCell class="font-medium">{{ row.column_code }} / {{ row.code }}</TableCell>
              <TableCell>{{ row.name }}</TableCell>
              <TableCell class="text-muted-foreground">{{ row.rack_group || '—' }}</TableCell>
              <TableCell>{{ row.used_u }} / {{ row.total_u }}U</TableCell>
              <TableCell><StatusBadge type="rack" :value="row.status" /></TableCell>
              <TableCell class="text-right">
                <EntityActions :show-edit="canEditRack" :show-delete="canEditRack" @view="() => goRack(row.id)" @edit="() => onEditRack(row)" @delete="() => onDeleteRack(row)" />
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </Card>
    </template>

    <!-- 编辑机房弹窗 -->
    <RoomForm v-model:visible="roomFormVisible" mode="edit" :room-id="roomId" @saved="onRoomSaved" />
    <!-- 新增机柜弹窗（锁定到当前机房） -->
    <RackForm v-model:visible="rackFormVisible" :mode="rackFormMode" :rack-id="rackFormRackId" :locked-room-id="rackFormMode === 'create' ? roomId : ''" @saved="onRackSaved" />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { LayoutGrid, List, Map, MapPin, Plus, Pencil, Trash2, ChevronLeft, Heading, Hash, Tag, Building2, Layers, Signal, ClipboardList } from 'lucide-vue-next'
import { useRoomStore } from '@/stores/room'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import StatsPanel from '@/components/room/StatsPanel.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import EntityActions from '@/components/common/EntityActions.vue'
import RoomForm from '@/views/room/RoomForm.vue'
import RackForm from '@/views/rack/RackForm.vue'
import rackApi from '@/api/rack'
import Button from '@/components/ui/button.vue'
import Card from '@/components/ui/card.vue'
import Badge from '@/components/ui/badge.vue'
import Table from '@/components/ui/table.vue'
import TableHeader from '@/components/ui/table-header.vue'
import TableBody from '@/components/ui/table-body.vue'
import TableRow from '@/components/ui/table-row.vue'
import TableHead from '@/components/ui/table-head.vue'
import TableCell from '@/components/ui/table-cell.vue'
import EmptyState from '@/components/ui/empty-state.vue'
import Spinner from '@/components/ui/spinner.vue'
import { useMetaStore } from '@/stores/meta'

const route = useRoute()
const router = useRouter()
const store = useRoomStore()
const { success } = useToast()
const { confirm } = useConfirm()
const roomId = route.params.id
const auth = useAuthStore()
// 编辑机房需 room:edit；新增 / 编辑 / 删除机柜需 rack:edit。
const canEditRoom = computed(() => auth.hasPermission('room:edit'))
const canEditRack = computed(() => auth.hasPermission('rack:edit'))
const meta = useMetaStore()

const room = computed(() => store.currentRoom)
const stats = computed(() => store.stats)
const racks = computed(() => store.racks)
// 本地加载态：编辑机房时 RoomForm 内部 fetchOne 会翻转 store.loading，
// 若 loading 直接绑定 store.loading 将触发本页内容区卸载/重挂循环导致预填失效（同机柜详情陷阱）。
const loading = ref(true)

const rackView = ref('card')
const roomFormVisible = ref(false)
const rackFormVisible = ref(false)
const rackFormMode = ref('create')
const rackFormRackId = ref('')

function capColor(r) {
  const ratio = r.total_u ? r.used_u / r.total_u : 0
  // 使用率配色统一走 meta.usageColor（审查报告#352）。
  return meta.usageColor(ratio)
}
function fillPct(r) {
  return r.total_u ? Math.round((r.used_u / r.total_u) * 100) : 0
}

function goRack(id) {
  router.push(`/racks/${id}`)
}
function openCreateRack() {
  rackFormMode.value = 'create'
  rackFormRackId.value = ''
  rackFormVisible.value = true
}
function onEditRack(rack) {
  rackFormMode.value = 'edit'
  rackFormRackId.value = rack.id
  rackFormVisible.value = true
}
function goBack() {
  router.back()
}
function goPlan() {
  router.push(`/rooms/${roomId}/plan`)
}
async function onDeleteRack(rack) {
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
    await store.fetchRacks(roomId)
  } catch (e) {
    // 拦截器提示（如仍有设备占用）
  }
}
// 机房信息变更后刷新详情与统计
async function onRoomSaved() {
  await Promise.all([store.fetchOne(roomId), store.fetchStats(roomId)])
}
// 删除机房：软删除（status=disabled），其下机柜一并失效；需 room:edit 权限。
async function onDeleteRoom() {
  const ok = await confirm({
    title: '删除机房',
    description: `确认删除机房「${room.value?.name}」？删除后其下机柜一并失效，操作不可恢复。`,
    variant: 'danger',
    confirmText: '删除',
  })
  if (!ok) return
  try {
    await store.remove(roomId)
    success('删除成功')
    router.push('/rooms')
  } catch (e) {
    // 拦截器提示（如仍有未下架设备等）
  }
}
// 新增机柜后刷新机柜列表
async function onRackSaved() {
  await store.fetchRacks(roomId)
}

onMounted(async () => {
  try {
    await store.fetchOne(roomId)
    await Promise.all([store.fetchStats(roomId), store.fetchRacks(roomId)])
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.rack-mini-card {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 12px;
  background: #fff;
  transition: box-shadow 0.2s, transform 0.2s, border-color 0.2s;
}
.rack-mini-card:hover {
  box-shadow: 0 8px 30px -12px rgb(15 23 42 / 0.18);
  transform: translateY(-2px);
  border-color: #cbd5e1;
}
.rack-mini-bar {
  margin-top: 8px;
  height: 6px;
  border-radius: 9999px;
  background: #f1f5f9;
  overflow: hidden;
}
.rack-mini-fill {
  height: 100%;
  transition: width 0.3s ease;
}
</style>
