<template>
  <div class="link-list">
    <div class="page-head">
      <div>
        <h2 class="page-title">链路总览</h2>
        <p class="page-sub">设备间物理连接全景（本端/对端设备与接口、连接介质、线缆长度）；可勾选「孤儿口」查看尚未连线的接口</p>
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
      class="alert-hint mb-4 flex items-start gap-3 rounded-lg px-4 py-4 text-sm"
    >
      <TriangleAlert class="mt-0.5 h-5 w-5 shrink-0 text-warning" />
      <div>
        <p class="font-semibold">尚不满足建链条件</p>
        <p class="mt-1 leading-relaxed opacity-90">{{ gateHint }}</p>
      </div>
    </div>

    <!-- 筛选工具栏 -->
    <div class="toolbar">
      <div class="flex flex-wrap items-end gap-4">
        <div class="flex flex-col gap-1">
          <Label>关键字</Label>
          <Input v-model="filter.keyword" placeholder="设备名 / 接口名" class="w-48" @keyup.enter="loadAll" @update:model-value="onKeywordInput" />
        </div>
        <div class="flex flex-col gap-1">
          <Label>连接介质</Label>
          <Select v-model="filter.medium" class="w-36" @update:model-value="loadAll">
            <SelectTrigger placeholder="全部" />
            <SelectContent>
              <SelectItem :value="SELECT_ALL">全部</SelectItem>
              <SelectItem v-for="m in LINK_MEDIUM_OPTIONS" :key="m.value" :value="m.value">{{ m.label }}</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div class="flex flex-col gap-1">
          <Label>连接器</Label>
          <Select v-model="filter.connector" class="w-36" :disabled="!connectorOptions.length" @update:model-value="loadAll">
            <SelectTrigger placeholder="全部" />
            <SelectContent>
              <SelectItem :value="SELECT_ALL">全部</SelectItem>
              <SelectItem v-for="c in connectorOptions" :key="c.value" :value="c.value">{{ c.label }}</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div class="flex items-center gap-2 pb-1">
          <Button @click="loadAll">查询</Button>
          <Button variant="outline" @click="resetFilter">重置</Button>
        </div>
        <label class="flex items-center gap-2 pb-1 text-sm text-muted-foreground">
          <Switch v-model="filter.showOrphans" @update:model-value="loadAll" />
          显示孤儿口（未连线）
        </label>
      </div>
    </div>

    <!-- 链路总览（按本端设备分组折叠） -->
    <Card class="mb-5">
      <template #header>
        <div class="flex items-center justify-between">
          <span class="section-title">链路总览（{{ totalCount }} 条 · {{ groupedRows.length }} 台设备）</span>
          <div v-if="groupedRows.length > 1" class="flex items-center gap-1">
            <Button variant="ghost" size="sm" @click="expandAll"><ChevronsUpDown class="mr-1 h-3.5 w-3.5" />全部展开</Button>
            <Button variant="ghost" size="sm" @click="collapseAll"><ChevronsDownUp class="mr-1 h-3.5 w-3.5" />全部折叠</Button>
          </div>
        </div>
      </template>

      <div v-if="loading" class="flex justify-center py-16">
        <Spinner class="h-6 w-6 text-primary" />
      </div>

      <!-- 空状态 -->
      <div v-else-if="groupedRows.length === 0" class="py-16 text-center text-sm text-muted-foreground">
        暂无符合条件的连接。点击右上角「新建链路」添加设备间物理连接。
      </div>

      <!-- 分组表 -->
      <Table v-else>
        <TableHeader>
          <TableRow>
            <TableHead class="w-36">本端设备</TableHead>
            <TableHead class="w-28">本端接口</TableHead>
            <TableHead class="w-32">介质</TableHead>
            <TableHead class="w-24">连接器</TableHead>
            <TableHead class="w-24">线缆长度</TableHead>
            <TableHead class="w-36">对端设备</TableHead>
            <TableHead class="w-28">对端接口</TableHead>
            <TableHead class="w-40">备注</TableHead>
            <TableHead class="text-right">操作</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody v-for="group in groupedRows" :key="group.deviceId">
          <!-- 分组头：设备名 + 链路数 + 折叠图标 -->
          <TableRow class="group-header" @click="toggleGroup(group.deviceId)">
            <TableCell :colspan="9" class="py-2">
              <div class="flex items-center gap-2">
                <ChevronRight class="h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200" :class="{ 'rotate-90': !isCollapsed(group.deviceId) }" />
                <span class="text-sm font-semibold">{{ group.deviceName }}</span>
                <span class="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">{{ group.rows.length }} 条链路</span>
              </div>
            </TableCell>
          </TableRow>
          <!-- 分组内链路行（折叠时隐藏） -->
          <template v-if="!isCollapsed(group.deviceId)">
            <TableRow
              v-for="row in group.rows"
              :key="row.key"
              :class="{ 'row--orphan': row.kind === 'orphan' }"
            >
              <TableCell>
                <button class="link-device" @click="goDevice(row.localDeviceId)">{{ row.localDeviceName }}</button>
              </TableCell>
              <TableCell>{{ row.localInterfaceName }}</TableCell>
              <TableCell>
                <template v-if="row.kind === 'link'">
                  <Badge
                    :style="{ backgroundColor: (LINK_MEDIUM_COLORS[row.medium] || '#909399') + '22', color: LINK_MEDIUM_COLORS[row.medium] || '#909399' }"
                    variant="outline"
                    class="whitespace-nowrap"
                  >{{ LINK_MEDIUM_LABELS[row.medium] || row.medium }}</Badge>
                </template>
                <span v-else class="text-xs text-muted-foreground">—</span>
              </TableCell>
              <TableCell>
                <template v-if="row.kind === 'link' && row.connectorType">
                  <span class="font-mono text-xs">{{ CONNECTOR_TYPE_LABELS[row.connectorType] || row.connectorType }}</span>
                </template>
                <span v-else class="text-xs text-muted-foreground">—</span>
              </TableCell>
              <TableCell>
                <span v-if="row.kind === 'link' && row.cableLength">{{ row.cableLength }}</span>
                <span v-else class="text-xs text-muted-foreground">—</span>
              </TableCell>
              <TableCell>
                <template v-if="row.kind === 'link'">
                  <span v-if="row.peerDeviceId" class="link-device" @click="goDevice(row.peerDeviceId)">{{ row.peerDeviceName }}</span>
                  <span v-else>{{ row.peerDeviceName }}</span>
                </template>
                <span v-else>
                  <span class="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs font-medium" style="background: hsl(var(--muted)); color: hsl(var(--muted-foreground))">
                    <Unplug class="h-3 w-3" />未连线
                  </span>
                </span>
              </TableCell>
              <TableCell>
                <span v-if="row.kind === 'link'">{{ row.peerInterfaceName || '—' }}</span>
                <span v-else class="text-xs text-muted-foreground">—</span>
              </TableCell>
              <TableCell class="truncate" :title="row.kind === 'link' ? row.remark : ''">
                <span v-if="row.kind === 'link'">{{ row.remark || '—' }}</span>
                <span v-else class="text-xs text-muted-foreground">尚未建立连接的接口</span>
              </TableCell>
              <TableCell class="text-right">
                <div class="flex justify-end gap-1">
                  <template v-if="row.kind === 'link'">
                    <Button v-if="canEdit" variant="ghost" size="icon" aria-label="编辑" title="编辑" @click="openEdit(row)"><Pencil class="h-4 w-4" /></Button>
                    <Button v-if="canEdit" variant="ghost" size="icon" class="text-destructive hover:text-destructive" aria-label="断开" title="断开" @click="onDelete(row)"><Unplug class="h-4 w-4" /></Button>
                  </template>
                  <Button v-else variant="ghost" size="icon" aria-label="查看设备" title="查看设备" @click="goDevice(row.localDeviceId)"><ExternalLink class="h-4 w-4" /></Button>
                </div>
              </TableCell>
            </TableRow>
          </template>
        </TableBody>
      </Table>
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
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import { usePersistentFilter } from '@/composables/usePersistentFilter'
import linkApi from '@/api/link'
import interfaceApi from '@/api/interface'
import deviceApi from '@/api/device'
import { useAuthStore } from '@/stores/auth'
import LinkFormDialog from '@/views/link/LinkFormDialog.vue'
import { Pencil, Unplug, TriangleAlert, ExternalLink, ChevronRight, ChevronsUpDown, ChevronsDownUp } from 'lucide-vue-next'
import {
  LINK_MEDIUM_LABELS,
  LINK_MEDIUM_COLORS,
  LINK_MEDIUM_OPTIONS,
  CONNECTOR_TYPE_LABELS,
  CONNECTOR_TYPE_TP_OPTIONS,
  CONNECTOR_TYPE_FIBER_OPTIONS,
  SELECT_ALL,
} from '@/utils/constants'
import Button from '@/components/ui/button.vue'
import Input from '@/components/ui/input.vue'
import Label from '@/components/ui/label.vue'
import Select from '@/components/ui/select.vue'
import SelectTrigger from '@/components/ui/select-trigger.vue'
import SelectContent from '@/components/ui/select-content.vue'
import SelectItem from '@/components/ui/select-item.vue'
import Switch from '@/components/ui/switch.vue'
import Card from '@/components/ui/card.vue'
import Table from '@/components/ui/table.vue'
import TableHeader from '@/components/ui/table-header.vue'
import TableBody from '@/components/ui/table-body.vue'
import TableRow from '@/components/ui/table-row.vue'
import TableHead from '@/components/ui/table-head.vue'
import TableCell from '@/components/ui/table-cell.vue'
import Badge from '@/components/ui/badge.vue'
import Spinner from '@/components/ui/spinner.vue'

const { success } = useToast()
const { confirm } = useConfirm()
const auth = useAuthStore()
const router = useRouter()
// 新建 / 编辑 / 断开链路需 link:edit；只读用户隐藏全部写操作按钮。
const canEdit = computed(() => auth.hasPermission('link:edit'))

// 连接器筛选选项：双绞线与光纤连接器合并（不随介质联动，仅作宽松过滤）。
const connectorOptions = computed(() => [
  ...CONNECTOR_TYPE_TP_OPTIONS,
  ...CONNECTOR_TYPE_FIBER_OPTIONS,
])

// 全量链路（按筛选条件拉取后客户端归一直表）。
const allLinks = ref([])
const loading = ref(false)

// 关键字输入防抖（H-11）：全量拉取开销大，逐键触发会造成请求风暴；
// 停止输入 400ms 后才查询。回车（keyup.enter）仍即时查询。
let keywordTimer = null
function onKeywordInput() {
  clearTimeout(keywordTimer)
  keywordTimer = setTimeout(() => {
    loadAll()
  }, 400)
}

// 竞态保护（M-06）：记录请求序号，旧请求晚返回时不覆盖新结果。
let loadSeq = 0

// 孤儿口（未连线接口）。
const orphans = ref([])

// 筛选条件（H-03：持久化到 sessionStorage，刷新/返回后恢复）。
const { filter, clear: clearPersisted } = usePersistentFilter('LinkList', () => ({
  keyword: '',
  medium: SELECT_ALL,
  connector: SELECT_ALL,
  showOrphans: false,
}))

// 扁平表行：链路 +（可选）孤儿口，统一形状便于渲染。
const rows = computed(() => {
  const linkRows = allLinks.value.map((lk) => ({
    key: 'l-' + lk.id,
    kind: 'link',
    id: lk.id,
    sourceDeviceId: lk.source_device_id,
    sourceDeviceName: lk.source_device_name,
    sourceInterfaceName: lk.source_interface_name,
    targetDeviceId: lk.target_device_id,
    targetDeviceName: lk.target_device_name,
    targetInterfaceName: lk.target_interface_name,
    medium: lk.medium,
    connectorType: lk.connector_type,
    cableLength: lk.cable_length,
    remark: lk.remark,
  }))
  // 孤儿口仅在「无介质/连接器筛选」时混入（孤儿口无介质，必然不匹配介质/连接器条件）。
  if (filter.showOrphans && filter.medium === SELECT_ALL && filter.connector === SELECT_ALL) {
    const orphanRows = orphans.value.map((o) => ({
      key: 'o-' + o.interface_id,
      kind: 'orphan',
      sourceDeviceId: o.device_id,
      sourceDeviceName: o.device_name,
      sourceInterfaceName: o.interface_name,
    }))
    return [...linkRows, ...orphanRows]
  }
  return linkRows
})

// 全量条数（含孤儿口）。
const totalCount = computed(() => rows.value.length)

// === 分组折叠逻辑 ===
// 折叠阈值：链路数超过此值的分组默认折叠。
const COLLAPSE_THRESHOLD = 5
// 折叠状态映射：deviceId -> true(折叠)。仅记录用户手动切换过的分组，
// 未记录的分组按阈值自动判定。
const collapsedMap = ref({})
// 数据加载后自动初始化折叠状态（超过阈值的分组默认折叠）。
function initCollapseState() {
  const map = {}
  for (const g of groupedRows.value) {
    map[g.deviceId] = g.rows.length > COLLAPSE_THRESHOLD
  }
  collapsedMap.value = map
}
function isCollapsed(deviceId) {
  return !!collapsedMap.value[deviceId]
}
function toggleGroup(deviceId) {
  collapsedMap.value[deviceId] = !collapsedMap.value[deviceId]
}
function expandAll() {
  for (const g of groupedRows.value) collapsedMap.value[g.deviceId] = false
}
function collapseAll() {
  for (const g of groupedRows.value) collapsedMap.value[g.deviceId] = true
}

// 每台设备独立成组，展示其参与的所有链路（无论做本端还是对端）。
// 一条链路两端都是内部设备时，在本端和对端分组中各出现一次；
// 对端为外部端点（无 deviceId）时仅在本端分组出现一次；
// 孤儿口按所属设备归组。
// 展示视角：每组内链路行以分组设备为「本端」，若原始数据中该设备实际是 target，
// 则翻转展示列（local/peer），但操作仍用原始 id 和方向调用 API。
const groupedRows = computed(() => {
  const allRows = rows.value
  const groups = new Map()
  function ensureGroup(deviceId, deviceName) {
    const key = deviceId || '__unknown__'
    if (!groups.has(key)) {
      groups.set(key, { deviceId: key, deviceName: deviceName || '未知设备', rows: [] })
    }
    return groups.get(key)
  }
  // 为链路生成「设备视角」展示字段：local = 分组设备侧，peer = 对侧。
  function viewForRow(row, groupId) {
    if (row.kind === 'orphan') {
      // 孤儿口：本设备即本端，无对端。
      return { ...row, localDeviceId: row.sourceDeviceId, localDeviceName: row.sourceDeviceName, localInterfaceName: row.sourceInterfaceName, peerDeviceId: null, peerDeviceName: null, peerInterfaceName: null }
    }
    const isSource = row.sourceDeviceId === groupId
    if (isSource) {
      // 原始方向：本端 = source，对端 = target。
      return { ...row, localDeviceId: row.sourceDeviceId, localDeviceName: row.sourceDeviceName, localInterfaceName: row.sourceInterfaceName, peerDeviceId: row.targetDeviceId, peerDeviceName: row.targetDeviceName, peerInterfaceName: row.targetInterfaceName }
    }
    // 翻转：分组设备实际是 target，展示时作为「本端」。
    return { ...row, localDeviceId: row.targetDeviceId, localDeviceName: row.targetDeviceName, localInterfaceName: row.targetInterfaceName, peerDeviceId: row.sourceDeviceId, peerDeviceName: row.sourceDeviceName, peerInterfaceName: row.sourceInterfaceName }
  }
  for (const row of allRows) {
    if (row.kind === 'orphan') {
      ensureGroup(row.sourceDeviceId, row.sourceDeviceName).rows.push(viewForRow(row, row.sourceDeviceId))
      continue
    }
    // 本端设备分组。
    ensureGroup(row.sourceDeviceId, row.sourceDeviceName).rows.push(viewForRow(row, row.sourceDeviceId))
    // 对端为内部设备时，对端分组也加入（翻转视角）。
    if (row.targetDeviceId) {
      ensureGroup(row.targetDeviceId, row.targetDeviceName).rows.push(viewForRow(row, row.targetDeviceId))
    }
  }
  // 按设备名中文排序，组内保持原有接口顺序。
  return [...groups.values()].sort((a, b) => a.deviceName.localeCompare(b.deviceName, 'zh-CN'))
})

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

// 拉取「全部」符合条件的链路（并发翻页），再客户端归一直表。
// H-11：原实现串行循环翻页（每页 200 条），链路量大时 N 次串行请求耗时长；
// 改为「第一页拿 total → 并发拉取剩余页」后合并，总耗时接近单次请求。
async function loadAll() {
  const seq = ++loadSeq
  loading.value = true
  try {
    const size = 200
    const params = {
      page: 1,
      size,
      keyword: filter.keyword || undefined,
      medium: filter.medium === SELECT_ALL ? undefined : filter.medium,
      connector_type: filter.connector === SELECT_ALL ? undefined : filter.connector,
    }
    // 第一页：既取数据也拿 total（后端分页信封含 total）。
    const first = await linkApi.list(params)
    const items = (first && first.items) || []
    const total = (first && first.total) || 0
    const pages = Math.ceil(total / size)
    // 剩余页并发拉取（后端有全局限流但远低于此量级）。
    if (pages > 1) {
      const rest = await Promise.all(
        Array.from({ length: pages - 1 }, (_, i) =>
          linkApi.list({ ...params, page: i + 2 }).then((d) => (d && d.items) || [])
        )
      )
      for (const r of rest) items.push(...r)
    }
    // 旧请求（已被更新的触发取代）结果丢弃。
    if (seq !== loadSeq) return
    allLinks.value = items
    // 孤儿口：仅在开关开启且未做介质/连接器筛选时拉取。
    if (filter.showOrphans && filter.medium === SELECT_ALL && filter.connector === SELECT_ALL) {
      try {
        const u = await interfaceApi.unlinked()
        orphans.value = Array.isArray(u) ? u : []
      } catch (e) {
        orphans.value = []
      }
    } else {
      orphans.value = []
    }
    // 数据就绪后初始化折叠状态（超过阈值的分组默认折叠）。
    initCollapseState()
  } finally {
    loading.value = false
  }
}
function resetFilter() {
  // 重置并清掉持久化（H-03），否则下次进入仍会恢复旧筛选。
  clearPersisted()
  orphans.value = []
  loadAll()
}
// 点击本端/对端设备（系统内）跳转到对应设备详情页；外部对端 target_device_id 为空，不渲染链接。
function goDevice(id) {
  if (!id) return
  router.push(`/devices/${id}`)
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
  // LinkFormDialog 编辑模式读取 snake_case 字段（source_device_name 等），
  // 而 rows 是 camelCase 子集；须从原始 allLinks 取回后端对象再传，否则端点卡本端/对端设备名全空。
  editLink.value = allLinks.value.find((l) => l.id === row.id) || row
  dialogVisible.value = true
}
async function onDelete(row) {
  const ok = await confirm({
    title: '断开链路',
    description: `确认断开「${row.localDeviceName} ↔ ${row.peerDeviceName}」？断开后两端接口状态将回落为未连接。`,
    variant: 'danger',
    confirmText: '断开',
    cancelText: '取消',
  })
  if (!ok) return
  try {
    await linkApi.remove(row.id)
    success('已断开')
    loadAll()
  } catch (e) {
    // 拦截器提示
  }
}
function onSaved() {
  loadAll()
}

onMounted(async () => {
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
  color: hsl(var(--primary));
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
/* 孤儿口行：弱化呈现，与已连接链路区分 */
.row--orphan {
  background: oklch(var(--muted) / 0.35);
}
.row--orphan:hover {
  background: oklch(var(--muted) / 0.55);
}
/* 分组头行：轻量背景 + 手型光标，视觉层次清晰但不喧宾夺主 */
.group-header {
  cursor: pointer;
  background: oklch(var(--muted) / 0.25);
}
.group-header:hover {
  background: oklch(var(--muted) / 0.45);
}
</style>
