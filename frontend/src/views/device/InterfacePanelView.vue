<template>
  <div class="interface-panel-view">
    <div class="page-head">
      <div>
        <h2 class="page-title">接口面板</h2>
        <p class="page-sub">集中查看所有设备的物理接口，按设备分组、可折叠，点击接口直接编辑</p>
      </div>
    </div>

    <!-- 筛选工具栏 -->
    <div class="toolbar">
      <div class="flex flex-wrap items-end gap-4">
        <div class="flex flex-col gap-1">
          <Label>关键字</Label>
          <Input v-model="filter.keyword" placeholder="设备名 / 接口名" class="w-56" @keyup.enter="onSearch" />
        </div>
        <div class="flex items-center gap-2 pb-1">
          <Button @click="onSearch">查询</Button>
          <Button variant="outline" @click="onReset">重置</Button>
        </div>
      </div>
    </div>

    <Card class="mb-5">
      <template #header>
        <div class="flex items-center justify-between gap-3">
          <span class="section-title">接口面板（{{ total }} 个接口 · {{ displayGroups.length }} 台设备）</span>
          <button
            v-if="displayGroups.length"
            class="text-xs text-primary hover:underline"
            @click="allExpanded ? collapseAll() : expandAll()"
          >{{ allExpanded ? '收起全部' : '展开全部' }}</button>
        </div>
      </template>

      <div v-if="loading" class="flex justify-center py-16">
        <Spinner class="h-6 w-6 text-primary" />
      </div>

      <!-- 空状态 -->
      <div v-else-if="displayGroups.length === 0" class="py-16 text-center text-sm text-muted-foreground">
        暂无符合条件的接口。
      </div>

      <!-- 设备分组（可折叠） -->
      <div v-else class="device-panels">
        <section v-for="g in displayGroups" :key="g.deviceId" class="device-panel">
          <!-- 一级标题：设备名（点击展开/收起；点击名称跳设备详情） -->
          <div class="device-panel__head">
            <button class="device-panel__toggle" :aria-expanded="!!expanded[g.deviceId]" @click="toggleDevice(g.deviceId)">
              <ChevronRight class="device-panel__chevron" :class="{ 'rotate-90': expanded[g.deviceId] }" />
              <span class="device-panel__name">{{ g.deviceName }}</span>
              <Badge variant="secondary" class="device-panel__count">{{ g.interfaces.length }}</Badge>
            </button>
            <button class="device-panel__goto" title="查看设备详情" @click="goDevice(g.deviceId)">
              <Server class="h-3.5 w-3.5" />
            </button>
          </div>

          <!-- 二级：该设备的接口表格 -->
          <div v-if="expanded[g.deviceId]" class="device-panel__body">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead class="w-40">接口名称</TableHead>
                  <TableHead class="w-24">前面板序号</TableHead>
                  <TableHead class="w-24">类型</TableHead>
                  <TableHead class="w-20">角色</TableHead>
                  <TableHead class="w-20">速率</TableHead>
                  <TableHead class="w-24">状态</TableHead>
                  <TableHead class="w-36">IP 地址</TableHead>
                  <TableHead class="text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow
                  v-for="itf in g.interfaces"
                  :key="itf.id"
                  class="cursor-pointer hover:bg-accent/40"
                  @click="onRowClick(itf, g)"
                >
                  <TableCell>
                    <span class="iface-name">{{ itf.name }}</span>
                  </TableCell>
                  <TableCell class="text-muted-foreground">#{{ itf.interface_no || '—' }}</TableCell>
                  <TableCell>{{ INTERFACE_TYPE_LABELS[itf.interface_type] || itf.interface_type || '—' }}</TableCell>
                  <TableCell>{{ INTERFACE_ROLE_LABELS[itf.role] || itf.role || '—' }}</TableCell>
                  <TableCell>{{ itf.speed || '—' }}</TableCell>
                  <TableCell>
                    <span class="status-pill" :style="{ color: statusColor('interface', itf.status), background: hexA(statusColor('interface', itf.status), 0.12) }">
                      <i class="status-dot" :style="{ background: statusColor('interface', itf.status) }"></i>
                      {{ statusLabel('interface', itf.status) }}
                    </span>
                  </TableCell>
                  <TableCell>
                    <span v-if="itf.ip_address" class="font-mono text-xs truncate">{{ itf.ip_address }}</span>
                    <span v-else class="text-xs text-muted-foreground">—</span>
                  </TableCell>
                  <TableCell class="text-right">
                    <div class="flex justify-end gap-1" @click.stop>
                      <Button variant="ghost" size="icon" aria-label="查看" title="查看" @click="openView(itf)"><Eye class="h-4 w-4" /></Button>
                      <Button v-if="canEdit" variant="ghost" size="icon" aria-label="编辑" title="编辑" @click="openEdit(itf, g)"><Pencil class="h-4 w-4" /></Button>
                      <Button v-if="canEdit" variant="ghost" size="icon" class="text-destructive hover:text-destructive" aria-label="删除" title="删除" @click="onDelete(itf)"><Trash2 class="h-4 w-4" /></Button>
                    </div>
                  </TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </div>
        </section>
      </div>
    </Card>

    <!-- 编辑接口弹窗：点击接口直接打开，不再跳转到设备详情 -->
    <InterfaceFormModal
      v-model:model-value="editOpen"
      :device-id="editDeviceId"
      :iface="editIface"
      :interfaces="editInterfaces"
      @saved="onSaved"
    />
    <!-- 查看接口弹窗（只读） -->
    <InterfaceDetailDialog
      v-model:model-value="viewOpen"
      :iface="viewIface"
      view-mode
      :can-edit="false"
      :can-edit-link="false"
      @mutated="onSaved"
    />
  </div>
</template>

<script setup>
import { reactive, ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'
import { useAuthStore } from '@/stores/auth'
import interfaceApi from '@/api/interface'
import InterfaceFormModal from '@/components/device/InterfaceFormModal.vue'
import InterfaceDetailDialog from '@/components/device/InterfaceDetailDialog.vue'
import { ChevronRight, Eye, Pencil, Trash2, Server } from 'lucide-vue-next'
import {
  INTERFACE_TYPE_LABELS,
  INTERFACE_ROLE_LABELS,
  statusColor,
  statusLabel,
} from '@/utils/constants'
import Button from '@/components/ui/button.vue'
import Input from '@/components/ui/input.vue'
import Label from '@/components/ui/label.vue'
import Card from '@/components/ui/card.vue'
import Spinner from '@/components/ui/spinner.vue'
import Badge from '@/components/ui/badge.vue'
import Table from '@/components/ui/table.vue'
import TableHeader from '@/components/ui/table-header.vue'
import TableBody from '@/components/ui/table-body.vue'
import TableRow from '@/components/ui/table-row.vue'
import TableHead from '@/components/ui/table-head.vue'
import TableCell from '@/components/ui/table-cell.vue'

const router = useRouter()
const { success } = useToast()
const { confirm } = useConfirm()
const auth = useAuthStore()
// 编辑 / 删除接口需 device:edit；只读用户仅可查看。
const canEdit = computed(() => auth.hasPermission('device:edit'))

const total = ref(0)
const loading = ref(false)
const items = ref([])
const filter = reactive({ keyword: '' })

// 折叠状态：默认全部折叠。key = 设备 id。
const expanded = ref({})
const toggleDevice = (id) => { expanded.value[id] = !expanded.value[id] }
const expandAll = () => {
  const e = {}
  groups.value.forEach((g) => { e[g.deviceId] = true })
  expanded.value = e
}
const collapseAll = () => { expanded.value = {} }
const allExpanded = computed(() => groups.value.length > 0 && groups.value.every((g) => expanded.value[g.deviceId]))

// 展示分组：有关键字时仅保留「设备名命中」或「任一接口名命中」的设备，避免无关设备噪声。
const displayGroups = computed(() => {
  const kw = (filter.keyword || '').trim().toLowerCase()
  if (!kw) return groups.value
  return groups.value.filter((g) => {
    if (String(g.deviceName).toLowerCase().includes(kw)) return true
    return g.interfaces.some((itf) => String(itf.name || '').toLowerCase().includes(kw))
  })
})

// 按设备分组：同一设备的接口归入一组，复用表格展示。
const groups = computed(() => {
  const map = new Map()
  for (const itf of items.value) {
    const id = itf.device_id
    if (!map.has(id)) {
      map.set(id, { deviceId: id, deviceName: itf.device_name || '未知设备', interfaces: [] })
    }
    map.get(id).interfaces.push(itf)
  }
  return [...map.values()].sort((a, b) => String(a.deviceName).localeCompare(String(b.deviceName)))
})

// 拉取全部接口（循环翻页取全量后客户端按设备分组，避免分页割裂同一设备的接口）。
async function loadAll() {
  loading.value = true
  try {
    const collected = []
    let page = 1
    const size = 500
    while (true) {
      const data = await interfaceApi.listAll({ keyword: filter.keyword || undefined, page, size })
      const rows = (data && data.items) || []
      collected.push(...rows)
      total.value = (data && data.total) || 0
      if (rows.length < size) break
      page += 1
    }
    items.value = collected
  } finally {
    loading.value = false
  }
}
function onSearch() {
  loadAll()
}
function onReset() {
  filter.keyword = ''
  loadAll()
}

// 点击接口行：有编辑权限直接打开编辑；只读用户打开查看弹窗。
function onRowClick(itf, g) {
  if (canEdit.value) openEdit(itf, g)
  else openView(itf)
}
function goDevice(id) {
  if (id) router.push(`/devices/${id}`)
}

// 编辑弹窗状态
const editOpen = ref(false)
const editIface = ref(null)
const editDeviceId = ref('')
const editInterfaces = ref([])
function openEdit(itf, g) {
  editIface.value = itf
  editDeviceId.value = itf.device_id
  editInterfaces.value = (g && g.interfaces) || items.value.filter((x) => x.device_id === itf.device_id)
  editOpen.value = true
}
// 查看弹窗状态（只读）
const viewOpen = ref(false)
const viewIface = ref(null)
function openView(itf) {
  viewIface.value = itf
  viewOpen.value = true
}
async function onDelete(itf) {
  const ok = await confirm({
    title: '提示',
    description: `确认删除接口「${itf.name}」？该操作不可撤销。`,
    variant: 'danger',
    confirmText: '删除',
    cancelText: '取消',
  })
  if (!ok) return
  try {
    await interfaceApi.remove(itf.id)
    success('删除成功')
    loadAll()
  } catch (e) {
    // 取消或失败由拦截器统一提示
  }
}
function onSaved() {
  loadAll()
}

// 状态色转 rgba（小圆点 / 标签底色）。
function hexA(hex, a) {
  const h = String(hex).replace('#', '')
  if (h.length !== 6) return `rgba(144,147,153,${a})`
  const n = parseInt(h, 16)
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`
}

onMounted(loadAll)
</script>

<style scoped>
/* P0 风格统一：page-head/page-title/page-sub/toolbar 移交给全局 @utility（index.css）。 */
.device-panels {
  display: flex;
  flex-direction: column;
}
.device-panel + .device-panel {
  border-top: 1px solid hsl(var(--border) / 0.5);
}
.device-panel__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
}
.device-panel__toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0;
  background: transparent;
  border: none;
  cursor: pointer;
  text-align: left;
}
.device-panel__chevron {
  flex: none;
  width: 16px;
  height: 16px;
  color: hsl(var(--muted-foreground));
  transition: transform 0.2s ease;
}
.device-panel__name {
  font-size: 14px;
  font-weight: 600;
  color: hsl(var(--foreground));
}
.device-panel__name:hover {
  color: hsl(var(--primary));
  text-decoration: underline;
}
.device-panel__count {
  font-size: 12px;
}
.device-panel__goto {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  color: hsl(var(--muted-foreground));
  background: transparent;
  border: 1px solid hsl(var(--border) / 0.6);
  cursor: pointer;
  transition: color 0.15s ease, border-color 0.15s ease;
}
.device-panel__goto:hover {
  color: hsl(var(--primary));
  border-color: hsl(var(--primary) / 0.6);
}
.device-panel__body {
  padding: 0 16px 12px;
}
.iface-name {
  font-weight: 600;
  color: hsl(var(--foreground));
}
.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}
.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}
</style>
