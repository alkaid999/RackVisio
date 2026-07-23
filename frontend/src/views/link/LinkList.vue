<template>
  <div class="link-list">
    <div class="page-head">
      <div>
        <h2 class="page-title">链路管理</h2>
        <p class="page-sub">记录设备间物理连接（本端/对端设备与接口、连接介质、线缆长度）</p>
      </div>
      <Button
        v-if="canEdit"
        :disabled="devicesLoaded && !hasEligibleDevice"
        :title="(devicesLoaded && !hasEligibleDevice) ? (gateHint || '尚不满足建链条件') : ''"
        @click="openCreate"
      >新建链路</Button>
    </div>

    <!-- 链路资格门控提示：设备资格数据加载完毕后，无「已上架且含接口」的设备时给出具体原因 -->
    <div
      v-if="devicesLoaded && gateHint"
      class="mb-4 rounded-md border border-amber-300/50 bg-amber-500/10 px-4 py-3 text-sm text-amber-200 dark:text-amber-300"
    >
      <p class="font-medium">尚不满足建链条件</p>
      <p class="mt-1">{{ gateHint }}</p>
    </div>

    <!-- 筛选工具栏 -->
    <div class="toolbar">
      <div class="flex flex-wrap items-end gap-4">
        <div class="flex flex-col gap-1">
          <Label>关键字</Label>
          <Input v-model="filter.keyword" placeholder="设备名 / 接口名" class="w-48" @keyup.enter="loadAll" />
        </div>
        <div class="flex flex-col gap-1">
          <Label>机房</Label>
          <Select v-model="filter.roomId" class="w-40" @update:model-value="onRoomChange">
            <SelectTrigger placeholder="全部" />
            <SelectContent>
              <SelectItem :value="SELECT_ALL">全部</SelectItem>
              <SelectItem v-for="r in roomOptions" :key="r.id" :value="r.id">{{ r.name }}（{{ r.code }}）</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div class="flex flex-col gap-1">
          <Label>机柜</Label>
          <Select v-model="filter.rackId" class="w-40" :disabled="!toFilterParam(filter.roomId)" @update:model-value="loadAll">
            <SelectTrigger placeholder="全部" />
            <SelectContent>
              <SelectItem :value="SELECT_ALL">全部</SelectItem>
              <SelectItem v-for="r in rackOptions" :key="r.id" :value="r.id">{{ r.code }} {{ r.name }}</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div class="flex items-center gap-2 pb-1">
          <Button @click="loadAll">查询</Button>
          <Button variant="outline" @click="resetFilter">重置</Button>
        </div>
      </div>
    </div>

    <!-- 链路分组（按设备折叠） -->
    <Card class="mb-5">
      <template #header>
        <div class="flex items-center justify-between gap-3">
          <span class="section-title">链路列表（{{ total }} 条 · {{ groups.length }} 个设备）</span>
          <button
            v-if="groups.length"
            class="text-xs text-primary hover:underline"
            @click="allExpanded ? collapseAll() : expandAll()"
          >{{ allExpanded ? '收起全部' : '展开全部' }}</button>
        </div>
      </template>

      <div v-if="loading" class="flex justify-center py-16">
        <Spinner class="h-6 w-6 text-primary" />
      </div>

      <!-- 空状态 -->
      <div v-else-if="groups.length === 0" class="py-16 text-center text-sm text-muted-foreground">
        暂无符合条件的链路。点击右上角「新建链路」添加设备间物理连接。
      </div>

      <!-- 设备分组 -->
      <div v-else class="link-groups">
        <section v-for="g in groups" :key="g.id" class="link-group">
          <!-- 一级标题：设备名（可点击折叠/展开） -->
          <button class="link-group__head" :aria-expanded="!!expanded[g.id]" @click="toggleDevice(g.id)">
            <ChevronRight class="link-group__chevron" :class="{ 'rotate-90': expanded[g.id] }" />
            <span class="link-group__name">{{ g.name }}</span>
            <Badge variant="secondary" class="link-group__count">{{ g.links.length }}</Badge>
          </button>

          <!-- 二级菜单：该设备下的所有链路 -->
          <div v-if="expanded[g.id]" class="link-group__body">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead class="w-36">对端设备</TableHead>
                  <TableHead class="w-28">本端接口</TableHead>
                  <TableHead class="w-28">对端接口</TableHead>
                  <TableHead class="w-28">连接介质</TableHead>
                  <TableHead class="w-24">连接器</TableHead>
                  <TableHead class="w-24">线缆长度</TableHead>
                  <TableHead class="w-40">备注</TableHead>
                  <TableHead class="text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow v-for="lk in g.links" :key="lk.id">
                  <TableCell>
                    <span v-if="lk.peerId" class="link-device" @click="goDevice(lk.peerId)">{{ lk.peerName }}</span>
                    <span v-else>{{ lk.peerName || '—' }}</span>
                  </TableCell>
                  <TableCell>{{ lk.localIface }}</TableCell>
                  <TableCell>{{ lk.peerIface || '—' }}</TableCell>
                  <TableCell>
                    <Badge
                      :style="{ backgroundColor: (LINK_MEDIUM_COLORS[lk.medium] || '#909399') + '22', color: LINK_MEDIUM_COLORS[lk.medium] || '#909399' }"
                      variant="outline"
                    >
                      {{ LINK_MEDIUM_LABELS[lk.medium] || lk.medium }}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <span v-if="lk.connector_type" class="font-mono text-xs">{{ CONNECTOR_TYPE_LABELS[lk.connector_type] || lk.connector_type }}</span>
                    <span v-else class="text-xs text-muted-foreground">—</span>
                  </TableCell>
                  <TableCell>{{ lk.cable_length || '—' }}</TableCell>
                  <TableCell class="truncate" :title="lk.remark">{{ lk.remark || '—' }}</TableCell>
                  <TableCell class="text-right">
                    <div class="flex justify-end gap-1">
                      <Button variant="ghost" size="icon" aria-label="查看" title="查看" @click="openView(lk)"><Eye class="h-4 w-4" /></Button>
                      <Button v-if="canEdit" variant="ghost" size="icon" aria-label="编辑" title="编辑" @click="openEdit(lk)"><Pencil class="h-4 w-4" /></Button>
                      <Button v-if="canEdit" variant="ghost" size="icon" class="text-destructive hover:text-destructive" aria-label="删除" title="删除" @click="onDelete(lk)"><Trash2 class="h-4 w-4" /></Button>
                    </div>
                  </TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </div>
        </section>
      </div>
    </Card>

    <!-- 新建 / 编辑链路弹窗 -->
    <LinkFormDialog
      v-model:visible="dialogVisible"
      :mode="dialogMode"
      :view-mode="dialogViewMode"
      :link-id="editLinkId"
      :link="editLink"
      @saved="onSaved"
    />
  </div>
</template>

<script setup>
import { reactive, ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import linkApi from '@/api/link'
import deviceApi from '@/api/device'
import roomApi from '@/api/room'
import { useRoomStore } from '@/stores/room'
import { useAuthStore } from '@/stores/auth'
import LinkFormDialog from '@/views/link/LinkFormDialog.vue'
import { ChevronRight, Eye, Pencil, Trash2 } from 'lucide-vue-next'
import {
  LINK_MEDIUM_LABELS,
  LINK_MEDIUM_COLORS,
  CONNECTOR_TYPE_LABELS,
  SELECT_ALL,
  toFilterParam,
} from '@/utils/constants'
import Button from '@/components/ui/button.vue'
import Input from '@/components/ui/input.vue'
import Label from '@/components/ui/label.vue'
import Select from '@/components/ui/select.vue'
import SelectTrigger from '@/components/ui/select-trigger.vue'
import SelectContent from '@/components/ui/select-content.vue'
import SelectItem from '@/components/ui/select-item.vue'
import Card from '@/components/ui/card.vue'
import Table from '@/components/ui/table.vue'
import TableHeader from '@/components/ui/table-header.vue'
import TableBody from '@/components/ui/table-body.vue'
import TableRow from '@/components/ui/table-row.vue'
import TableHead from '@/components/ui/table-head.vue'
import TableCell from '@/components/ui/table-cell.vue'
import Badge from '@/components/ui/badge.vue'
import Spinner from '@/components/ui/spinner.vue'

const roomStore = useRoomStore()

const { success } = useToast()
const { confirm } = useConfirm()
const auth = useAuthStore()
const router = useRouter()
// 新建 / 编辑 / 删除链路需 link:edit；只读用户隐藏全部写操作按钮。
const canEdit = computed(() => auth.hasPermission('link:edit'))

// 全量链路（按筛选条件拉取后客户端分组）。
const allLinks = ref([])
const total = ref(0)
const loading = ref(false)

// 折叠状态：默认全部折叠。key = 设备 id，value = 是否展开。
const expanded = ref({})
const toggleDevice = (id) => { expanded.value[id] = !expanded.value[id] }
const expandAll = () => {
  const e = {}
  groups.value.forEach((g) => { e[g.id] = true })
  expanded.value = e
}
const collapseAll = () => { expanded.value = {} }
const allExpanded = computed(() => groups.value.length > 0 && groups.value.every((g) => expanded.value[g.id]))

// 按设备分组：链路归属到它连接的两端（source / target），故一条链路可能出现在两个设备分组下。
const groups = computed(() => {
  const map = new Map()
  const ensure = (id, name) => {
    if (!map.has(id)) map.set(id, { id, name: name || '未知设备', links: [] })
    return map.get(id)
  }
  for (const link of allLinks.value) {
    if (link.source_device_id) {
      const g = ensure(link.source_device_id, link.source_device_name)
      g.links.push({
        ...link,
        role: 'source',
        peerName: link.target_device_name,
        peerId: link.target_device_id,
        localIface: link.source_interface_name,
        peerIface: link.target_interface_name,
      })
    }
    if (link.target_device_id && link.target_device_id !== link.source_device_id) {
      const g = ensure(link.target_device_id, link.target_device_name)
      g.links.push({
        ...link,
        role: 'target',
        peerName: link.source_device_name,
        peerId: link.source_device_id,
        localIface: link.target_interface_name,
        peerIface: link.source_interface_name,
      })
    }
  }
  return [...map.values()].sort((a, b) => String(a.name).localeCompare(String(b.name)))
})

const roomOptions = computed(() => roomStore.rooms)
const rackOptions = computed(() => roomStore.racks)

// 链路资格：是否存在「已上架且含接口」的设备，决定「新建链路」是否可用。
const devices = ref([])
const devicesLoaded = ref(false)
const hasEligibleDevice = computed(() =>
  devicesLoaded.value && devices.value.some((d) => !!d.current_rack_id && (d.interface_count || 0) > 0)
)

// 门控原因统计：按设备实际状态给出具体提示（而非笼统三步前置）。
const gateSummary = computed(() => {
  const all = devices.value
  const mounted = all.filter((d) => !!d.current_rack_id)
  const mountedWithIface = mounted.filter((d) => (d.interface_count || 0) > 0)
  const mountedNoIface = mounted.filter((d) => !(d.interface_count || 0))
  const notMounted = all.filter((d) => !d.current_rack_id)
  return {
    total: all.length,
    eligible: mountedWithIface.length,
    mounted: mounted.length,
    mountedNoIface: mountedNoIface.length,
    notMounted: notMounted.length,
  }
})

// 具体原因提示：仅在没有任何「已上架且含接口」设备时给出（二级菜单统一提示）。
const gateHint = computed(() => {
  const s = gateSummary.value
  if (s.eligible > 0) return null
  if (s.total === 0)
    return '系统中还没有任何设备。请先在「设备管理」添加设备，再回来创建链路。'
  if (s.notMounted === s.total)
    return `当前共 ${s.total} 台设备都尚未上架机柜，无法创建链路。请先在「设备管理」将设备加入机柜并完成上架。`
  if (s.mounted > 0 && s.mountedNoIface === s.mounted)
    return `当前已上架的 ${s.mounted} 台设备都还没有添加接口，无法创建链路。请先为已上架设备添加接口。`
  const reasons = []
  if (s.notMounted > 0) reasons.push(`${s.notMounted} 台未上架`)
  if (s.mountedNoIface > 0) reasons.push(`${s.mountedNoIface} 台已上架但无接口`)
  return `当前没有可建链路的设备（${reasons.join('、')}）。请先在「设备管理」完成上架并添加接口。`
})

const dialogVisible = ref(false)
const dialogMode = ref('create')
const dialogViewMode = ref(false)
const editLinkId = ref('')
const editLink = ref(null)

const filter = reactive({ keyword: '', roomId: SELECT_ALL, rackId: SELECT_ALL })

// 拉取「全部」符合条件的链路（循环翻页直到取完），再客户端按设备分组。
// 链路数量在 IDC 规模下可控；分组视图天然不适合服务端分页，故一次性取全量。
async function loadAll() {
  loading.value = true
  try {
    const collected = []
    let page = 1
    const size = 200
    while (true) {
      const data = await linkApi.list({
        page,
        size,
        room_id: toFilterParam(filter.roomId),
        rack_id: toFilterParam(filter.rackId),
        keyword: filter.keyword || undefined,
      })
      const items = (data && data.items) || []
      collected.push(...items)
      total.value = (data && data.total) || 0
      if (items.length < size) break
      page += 1
    }
    allLinks.value = collected
  } finally {
    loading.value = false
  }
}
function resetFilter() {
  filter.keyword = ''
  filter.roomId = SELECT_ALL
  filter.rackId = SELECT_ALL
  roomStore.racks = []
  loadAll()
}
// 点击本端/对端设备（系统内）跳转到对应设备详情页；外部对端 target_device_id 为空，不渲染链接。
function goDevice(id) {
  if (!id) return
  router.push(`/devices/${id}`)
}
async function onRoomChange() {
  filter.rackId = SELECT_ALL
  if (toFilterParam(filter.roomId)) {
    await roomStore.fetchRacks(filter.roomId)
  } else {
    roomStore.racks = []
  }
  loadAll()
}
function openCreate() {
  dialogMode.value = 'create'
  editLinkId.value = ''
  editLink.value = null
  dialogVisible.value = true
}
function openEdit(row) {
  dialogMode.value = 'edit'
  dialogViewMode.value = false
  editLinkId.value = row.id
  editLink.value = row
  dialogVisible.value = true
}
// 查看模式：普通用户无需编辑权限即可只读浏览链路详情。
function openView(row) {
  dialogMode.value = 'edit'
  dialogViewMode.value = true
  editLinkId.value = row.id
  editLink.value = row
  dialogVisible.value = true
}
async function onDelete(row) {
  const ok = await confirm({
    title: '提示',
    description: `确认删除链路「${row.source_device_name} ↔ ${row.target_device_name}」？`,
    variant: 'danger',
    confirmText: '删除',
    cancelText: '取消',
  })
  if (!ok) return
  try {
    await linkApi.remove(row.id)
    success('删除成功')
    loadAll()
  } catch (e) {
    // 取消
  }
}
function onSaved() {
  loadAll()
}

onMounted(async () => {
  await roomStore.fetchList({ page: 1, size: 200 })
  loadAll()
  // 拉取设备用于链路资格判定（已上架 + 含接口）。
  try {
    const d = await deviceApi.list({ page: 1, size: 500 })
    devices.value = d.items || []
  } catch (e) {
    devices.value = []
  } finally {
    devicesLoaded.value = true
  }
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
  color: oklch(var(--muted-foreground));
  font-size: 13px;
}
.link-device {
  cursor: pointer;
  color: oklch(var(--primary));
}
.link-device:hover {
  opacity: 0.85;
  text-decoration: underline;
}
.toolbar {
  background: oklch(var(--card) / 0.8);
  border: 1px solid oklch(var(--border) / 0.6);
  border-radius: 10px;
  padding: 14px 16px;
  margin-bottom: 16px;
  backdrop-filter: blur(8px);
}
/* 设备分组折叠树 */
.link-groups {
  display: flex;
  flex-direction: column;
}
.link-group + .link-group {
  border-top: 1px solid oklch(var(--border) / 0.5);
}
.link-group__head {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 12px 16px;
  background: transparent;
  border: none;
  cursor: pointer;
  text-align: left;
  transition: background 0.15s ease;
}
.link-group__head:hover {
  background: oklch(var(--accent) / 0.5);
}
.link-group__chevron {
  flex: none;
  width: 16px;
  height: 16px;
  color: oklch(var(--muted-foreground));
  transition: transform 0.2s ease;
}
.link-group__name {
  font-size: 14px;
  font-weight: 600;
  color: oklch(var(--foreground));
}
.link-group__count {
  font-size: 12px;
}
.link-group__body {
  padding: 0 16px 12px;
}
</style>
