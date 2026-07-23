<template>
  <div>
    <!-- 标题区 + 机房选择 -->
    <div class="page-head">
      <div>
        <h1 class="page-title">2D 机柜视图</h1>
        <p class="page-sub">选择机房查看机柜平面排布，悬停设备查看详细信息</p>
      </div>
      <div class="flex items-center gap-3">
        <Select v-model="selectedRoom" class="w-56" @update:model-value="loadRacks">
          <SelectTrigger placeholder="选择机房" />
          <SelectContent>
            <SelectItem v-for="r in rooms" :key="r.id" :value="r.id">{{ r.name }}</SelectItem>
          </SelectContent>
        </Select>
        <Button variant="outline" :disabled="loading" title="导出机柜 U 位明细（1:1 镜像 2D 视图：按 grid_col 分列、grid_row 堆叠，每台机柜=U编号列+设备列）" @click="exportExcel">
          <Download class="h-4 w-4 mr-1.5" />导出 Excel
        </Button>
      </div>
    </div>

    <!-- 概览条 -->
    <div v-if="racks.length" class="toolbar flex flex-wrap items-center gap-x-8 gap-y-2">
      <div class="flex items-center gap-2 text-sm">
        <Server class="w-4 h-4 text-brand-500" />
        <span class="text-muted-foreground">机柜</span>
        <span class="font-semibold text-foreground">{{ racks.length }}</span>
      </div>
      <div class="flex items-center gap-2 text-sm">
        <Layers class="w-4 h-4 text-brand-500" />
        <span class="text-muted-foreground">平均使用率</span>
        <span class="font-semibold text-foreground">{{ avgUtilization }}%</span>
      </div>
      <!-- 设备类型图例 + 运行状态图例 -->
      <div class="flex flex-wrap items-center gap-x-5 gap-y-2 ml-auto">
        <div class="flex flex-wrap items-center gap-3">
          <span class="text-xs text-muted-foreground/70">类型</span>
          <span v-for="t in DEVICE_TYPE_OPTIONS" :key="t.value" class="flex items-center gap-1.5 text-xs text-muted-foreground">
            <span class="w-3 h-3 rounded" :style="{ background: DEVICE_TYPE_COLORS[t.value] }"></span>
            {{ t.label }}
          </span>
        </div>
        <div class="flex flex-wrap items-center gap-3 pl-5 border-l border-border/50">
          <span class="text-xs text-muted-foreground/70">运行状态</span>
          <span class="flex items-center gap-1.5 text-xs text-muted-foreground">
            <span class="w-3 h-3 rounded-full" :style="{ background: DEVICE_POWER_COLORS['开机'] }"></span>开机
          </span>
          <span class="flex items-center gap-1.5 text-xs text-slate-500">
            <span class="w-3 h-3 rounded-full" :style="{ background: DEVICE_POWER_COLORS['关机'] }"></span>关机
          </span>
        </div>
      </div>
    </div>

    <!-- 2D 机柜画布：卡片不锁高度（高度交给页面纵向滚动）；内部 floor-canvas 负责横向滚动 -->
    <div class="card-soft p-5">
      <div v-if="loading" class="flex justify-center py-16">
        <Spinner class="h-6 w-6 text-primary" />
      </div>
      <template v-else>
        <div v-if="racks.length" class="floor-canvas" @wheel="onFloorWheel">
          <section v-for="col in floorColumns" :key="col.grid_col" class="floor-col">
            <!-- 该平面列按 grid_row 逐行排布，与平面图行一一对应；无设备的行显示空位(row-empty) -->
            <div class="col-inner rows">
              <div v-for="(slot, si) in col.slots" :key="si" class="row-slot">
                <div v-if="slot" class="rack-col">
            <!-- 机柜头 -->
            <div class="rack-head">
              <div class="font-medium text-foreground truncate" :title="slot.name">{{ slot.name }}</div>
              <div class="text-xs text-muted-foreground mt-0.5">{{ slot.code }} · {{ slot.used_u }}/{{ slot.total_u }}U</div>
            </div>
            <!-- 机柜图形：左侧 U 数标识 + 右侧 U 位体 -->
            <div class="rack-graphic" :style="{ height: rackPixelHeight(slot.total_u) }">
              <div class="rack-gutter">
                <span
                  v-for="u in uTicks(slot.total_u)"
                  :key="u"
                  :class="u % 5 === 0 ? 'u-tick major' : 'u-tick'"
                  :style="tickStyle(slot.total_u, u)"
                >{{ u }}U</span>
              </div>
              <div class="rack-body">
                <template v-for="(seg, i) in segmentsOf(slot)" :key="i">
                  <!-- 设备块（高 U 设备自动合并为一整块） -->
                  <Popover v-if="seg.kind === 'device'" :open="hoveredId === seg.device.id">
                    <template #trigger>
                      <div
                        class="seg dev group"
                        :class="{ 'u-overlap': overlapIdsOf(slot).has(seg.device.id) }"
                        :style="segStyle(seg, slot)"
                        @mouseenter="openPop(seg.device.id)"
                        @mouseleave="closePop()"
                        @click="openDetail(seg.device)"
                      >
                        <div class="seg-name" :class="{ 'is-1u': seg.size === 1 }">{{ seg.device.name }}</div>
                        <div v-if="seg.size > 1" class="seg-meta">{{ seg.uStart }}U–{{ seg.uEnd }}U · {{ seg.size }}U</div>
                        <span v-if="overlapIdsOf(slot).has(seg.device.id)" class="u-overlap-mark">!</span>
                        <span class="status-dot" :style="{ background: powerDotColor(seg.device.power_status) }"></span>
                      </div>
                    </template>
                    <PopoverContent class="w-64 pointer-events-none">
                      <div class="pop">
                        <div class="flex items-center justify-between mb-2">
                          <span class="font-semibold text-foreground truncate">{{ seg.device.name }}</span>
                          <StatusBadge type="device" :value="seg.device.status" />
                        </div>
                        <div class="pop-row"><span>类型</span><span class="font-medium" :style="{ color: typeColor(seg.device.device_type) }">{{ DEVICE_TYPE_LABELS[seg.device.device_type] }}</span></div>
                        <div class="pop-row"><span>开关机</span><span class="font-medium" :style="{ color: (DEVICE_POWER_COLORS[seg.device.power_status] || DEVICE_POWER_COLORS['开机']) }">{{ DEVICE_POWER_LABELS[seg.device.power_status] || '开机' }}</span></div>
                        <div class="pop-row"><span>型号</span><span>{{ seg.device.model || '—' }}</span></div>
                        <div class="pop-row"><span>IP</span><span>{{ seg.device.ip_address || '—' }}</span></div>
                        <div class="pop-row"><span>设备编码</span><span>{{ seg.device.device_code || '—' }}</span></div>
                        <div class="pop-row"><span>U 位</span><span>{{ seg.uStart }}U–{{ seg.uEnd }}U（{{ seg.size }}U）</span></div>
                        <div v-if="overlapIdsOf(slot).has(seg.device.id)" class="pop-row pop-row--warn">
                          <span>⚠ 冲突</span><span>该设备 U 位与其他设备重叠</span>
                        </div>
                        <div class="pop-hint">点击查看完整详情</div>
                      </div>
                    </PopoverContent>
                  </Popover>
                  <!-- 空闲块 -->
                  <div v-else class="seg free" :style="{ height: (seg.size / slot.total_u) * 100 + '%' }">
                    <span class="text-[11px] text-muted-foreground/60">空闲</span>
                  </div>
                </template>
              </div>
            </div>
                </div>
              </div>
            </div>
          </section>
        </div>
        <EmptyState v-else title="该机房暂无机柜" />
      </template>
    </div>

    <!-- 设备详情弹窗：点击设备块打开，独立于悬浮提示，不被机柜区域裁剪，可交互 -->
    <Dialog v-model="detailVisible" :title="detailDevice ? detailDevice.name : '设备详情'">
      <div v-if="detailDevice" class="space-y-3 text-sm">
        <div class="flex items-center gap-2">
          <span class="h-3 w-3 rounded" :style="{ background: typeColor(detailDevice.device_type) }"></span>
          <span class="font-medium text-foreground">{{ DEVICE_TYPE_LABELS[detailDevice.device_type] || detailDevice.device_type }}</span>
          <StatusBadge type="device" :value="detailDevice.status" />
        </div>
        <div class="grid grid-cols-2 gap-x-4 gap-y-2">
          <div><div class="text-xs text-muted-foreground">型号</div><div class="text-foreground">{{ detailDevice.model || '—' }}</div></div>
          <div><div class="text-xs text-muted-foreground">IP</div><div class="text-foreground">{{ detailDevice.ip_address || '—' }}</div></div>
          <div v-if="detailDevice.current_rack_id"><div class="text-xs text-muted-foreground">开关机</div><div class="text-foreground">{{ DEVICE_POWER_LABELS[detailDevice.power_status] || '开机' }}</div></div>
          <div><div class="text-xs text-muted-foreground">设备编码</div><div class="text-foreground">{{ detailDevice.device_code || '—' }}</div></div>
          <div><div class="text-xs text-muted-foreground">U 位</div><div class="text-foreground">{{ detailDevice.current_start_u }}U–{{ detailDevice.current_start_u + (detailDevice.u_height || 1) - 1 }}U（{{ detailDevice.u_height }}U）</div></div>
        </div>
        <div v-if="allOverlapIds.has(detailDevice.id)" class="rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-400">
          ⚠ 该设备 U 位与其他设备重叠，请检查上架位置。
        </div>
      </div>
      <template #footer>
        <div class="flex justify-end gap-2">
          <Button variant="outline" @click="detailVisible = false">关闭</Button>
          <Button v-if="detailDevice" @click="goDetail(detailDevice.id)">查看完整详情</Button>
        </div>
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Server, Layers, Download } from 'lucide-vue-next'
import ExcelJS from 'exceljs'
import { downloadBlob } from '@/utils/download'
import { useToast } from '@/composables/useToast'
import roomApi from '@/api/room'
import deviceApi from '@/api/device'
import StatusBadge from '@/components/common/StatusBadge.vue'
import {
  DEVICE_TYPE_OPTIONS,
  DEVICE_TYPE_LABELS,
  DEVICE_TYPE_COLORS,
  DEVICE_POWER_COLORS,
  DEVICE_POWER_LABELS,
} from '@/utils/constants'
import Select from '@/components/ui/select.vue'
import SelectTrigger from '@/components/ui/select-trigger.vue'
import SelectContent from '@/components/ui/select-content.vue'
import SelectItem from '@/components/ui/select-item.vue'
import Popover from '@/components/ui/popover.vue'
import PopoverContent from '@/components/ui/popover-content.vue'
import EmptyState from '@/components/ui/empty-state.vue'
import Spinner from '@/components/ui/spinner.vue'
import Button from '@/components/ui/button.vue'
import Dialog from '@/components/ui/dialog.vue'

const route = useRoute()
const router = useRouter()
const { warning } = useToast()

// 悬停设备块：受控打开 Popover 显示详情（悬停而非点击，避免与跳转冲突）。
const hoveredId = ref('')
let popCloseTimer = null
function openPop(id) {
  if (popCloseTimer) {
    clearTimeout(popCloseTimer)
    popCloseTimer = null
  }
  hoveredId.value = id
}
function closePop() {
  if (popCloseTimer) clearTimeout(popCloseTimer)
  popCloseTimer = setTimeout(() => {
    hoveredId.value = ''
  }, 120)
}
function goDetail(id) {
  router.push('/devices/' + id)
}

// 2D 机柜视图：鼠标纵向滚轮 → 卡片内横向滚动（机柜左右移）。
// 已为横向手势（触控板横滑 deltaX）或到达左右边界时放行，交给页面纵向滚动，避免滚死。
function onFloorWheel(e) {
  const el = e.currentTarget
  if (e.deltaX !== 0) return // 已是横向手势，原生处理
  const max = el.scrollWidth - el.clientWidth
  if (max <= 0) return // 无横向溢出，页面正常纵向滚
  let delta = e.deltaY
  if (e.deltaMode === 1) delta *= 16 // 行模式 → 像素近似
  else if (e.deltaMode === 2) delta *= el.clientWidth // 页模式
  const atStart = el.scrollLeft <= 0
  const atEnd = el.scrollLeft >= max - 1
  const goingRight = delta > 0
  if ((goingRight && atEnd) || (!goingRight && atStart)) return // 到边界，放行页面纵向滚动
  e.preventDefault()
  el.scrollLeft += delta
}

// 点击设备块：打开独立详情弹窗（不再依赖悬浮提示，避免被机柜区域裁剪 / 无法点击）。
const detailVisible = ref(false)
const detailDevice = ref(null)
function openDetail(device) {
  hoveredId.value = ''
  detailDevice.value = device
  detailVisible.value = true
}

const rooms = ref([])
const selectedRoom = ref('')
const racks = ref([])
const loading = ref(false)
// 全机房范围内重叠设备集合（用于详情弹窗告警）。
const allOverlapIds = computed(() => {
  const s = new Set()
  for (const r of racks.value) for (const id of overlapIdsOf(r)) s.add(id)
  return s
})

function typeColor(type) {
  return DEVICE_TYPE_COLORS[type] || '#909399'
}
// 开关机小圆圈颜色：开机=绿，关机=红（红色专用于停机告警）。
function powerDotColor(power) {
  return DEVICE_POWER_COLORS[power] || DEVICE_POWER_COLORS['开机']
}
// 设备块样式：底色保留「设备类型色」（不覆盖设备本身颜色），开关机由左上角小圆圈
// （status-dot）标注；重叠时叠加红色描边告警。2D 视图只渲染在架设备，在库设备不出现。
function segStyle(seg, rack) {
  const d = seg.device
  const isOverlap = overlapIdsOf(rack).has(d.id)
  let boxShadow = 'inset 0 0 0 1px rgba(255,255,255,0.25)'
  if (isOverlap) {
    boxShadow = 'inset 0 0 0 2px #ef4444, 0 0 0 1px rgba(239,68,68,0.45)'
  }
  return {
    height: (seg.size / rack.total_u) * 100 + '%',
    background: typeColor(d.device_type),
    boxShadow,
  }
}
// 检测同一机柜内设备 U 位重叠：返回重叠设备的 id 集合（用于视觉告警）。
// 设备位置来自上架记录派生的 current_start_u / u_height；当两台设备的 U 区间相交即判为重叠。
function overlapIdsOf(rack) {
  const segs = (rack.devices || []).filter((d) => d.current_start_u != null && d.u_height)
  const ids = new Set()
  for (let i = 0; i < segs.length; i++) {
    for (let j = i + 1; j < segs.length; j++) {
      const a = segs[i]
      const b = segs[j]
      const aStart = a.current_start_u
      const aEnd = a.current_start_u + a.u_height - 1
      const bStart = b.current_start_u
      const bEnd = b.current_start_u + b.u_height - 1
      if (aStart <= bEnd && bStart <= aEnd) {
        ids.add(a.id)
        ids.add(b.id)
      }
    }
  }
  return ids
}

// 将机柜 U 位切分为「设备块（按 u_height 合并）+ 空闲块」，自顶向下排列。
// 设备位置来自上架记录表派生的 current_start_u / u_height（设备不再内嵌机柜字段）。
function segmentsOf(rack) {
  const total = rack.total_u || 0
  const devices = [...(rack.devices || [])]
    .filter((d) => d.current_start_u != null && d.u_height)
    .sort((a, b) => a.current_start_u - b.current_start_u)
  const segs = []
  let p = 1
  for (const d of devices) {
    if (d.current_start_u > p) segs.push({ kind: 'free', uStart: p, uEnd: d.current_start_u - 1 })
    segs.push({ kind: 'device', uStart: d.current_start_u, uEnd: d.current_start_u + d.u_height - 1, device: d })
    p = d.current_start_u + d.u_height
  }
  if (p <= total) segs.push({ kind: 'free', uStart: p, uEnd: total })
  segs.forEach((s) => (s.size = s.uEnd - s.uStart + 1))
  return segs.reverse()
}

// U 数标识刻度：逐个显示每一个 U 的位置编号（U1、U2 …… U{total}），不再跨多个 U 合并。
function uTicks(total) {
  const ticks = []
  for (let u = 1; u <= (total || 0); u++) ticks.push(u)
  return ticks
}
// 机柜图形高度随 U 数自适应：U 越多越高，保证逐 U 编号不重叠（每 U 至少约 14px）。
function rackPixelHeight(total) {
  const t = total || 42
  const perU = t > 30 ? 15 : t > 18 ? 16 : 18
  return Math.min(1040, Math.max(520, Math.round(t * perU))) + 'px'
}
// 刻度竖向位置：以 U 槽中心对齐（u=total 靠近顶部，u=1 靠近底部）。
function tickStyle(total, u) {
  const pct = (1 - (u - 0.5) / total) * 100
  return { top: pct + '%' }
}

const avgUtilization = computed(() => {
  if (!racks.value.length) return 0
  const sum = racks.value.reduce((acc, r) => {
    const ratio = r.total_u ? (r.used_u / r.total_u) * 100 : 0
    return acc + ratio
  }, 0)
  return Math.round(sum / racks.value.length)
})

// 2D 视图布局镜像机房平面图（RoomFloorPlan）：以「平面图列坐标 grid_col」分列、
// 以「行坐标 grid_row」逐行排布，使 2D 视图的行列与平面图一一对应（列头已取消，仅保留网格与平面图一致）。
// - 列：按 grid_col 升序（左→右与平面图一致），对应现场运维所称的「A列/B列」机柜成排布局。
// - 行：每列按全局最大 grid_row + 1 预留「行槽(slots)」，设备落到其 grid_row 对应的槽位，
//   无设备的行显示空位（row-empty）——因此平面图中某列从 2 行拖成 4 行，2D 视图该列即出现 4 个行槽。
const planRowCount = computed(() => {
  let max = 0
  for (const r of racks.value) max = Math.max(max, r.grid_row ?? 0)
  return max + 1
})
const floorColumns = computed(() => {
  const list = racks.value || []
  if (!list.length) return []
  const byCol = {}
  for (const r of list) {
    const gc = r.grid_col ?? 0
    ;(byCol[gc] ||= []).push(r)
  }
  const cols = Object.keys(byCol).map(Number).sort((a, b) => a - b)
  const rowCount = planRowCount.value
  return cols.map((gc) => {
    const racksInCol = byCol[gc].slice().sort((x, y) => (x.grid_row ?? 0) - (y.grid_row ?? 0))
    const rowMap = {}
    for (const r of racksInCol) rowMap[r.grid_row ?? 0] = r
    const slots = []
    // 2D 视图只渲染实际存在的机柜，不留平面图空槽位（避免出现多余灰色方块）
    for (let i = 0; i < rowCount; i++) { const r = rowMap[i]; if (r) slots.push(r) }
    return { grid_col: gc, racks: racksInCol, slots }
  })
})

// U 位明细功能已移除（该信息可由设备详情弹窗 / 设备列表覆盖），此处仅保留机柜图形与重叠告警。

async function loadRooms() {
  const data = await roomApi.list({ size: 200 })
  rooms.value = data.items || []
  const preselect = route.query.room || (rooms.value.length ? rooms.value[0].id : '')
  if (preselect) {
    selectedRoom.value = preselect
    await loadRacks()
  }
}

async function loadRacks() {
  if (!selectedRoom.value) {
    racks.value = []
    return
  }
  loading.value = true
  try {
    const rackList = await roomApi.racks(selectedRoom.value)
    if (!rackList.length) {
      racks.value = []
      return
    }
    // 按机房批量拉取全部设备（单页上限 200，超出自动翻页），替代原「每机柜 1 次」N+1 请求。
    const devices = await fetchRoomDevices(selectedRoom.value)
    const byRack = {}
    for (const d of devices) {
      if (!d.current_rack_id) continue
      ;(byRack[d.current_rack_id] ||= []).push(d)
    }
    racks.value = rackList.map((r) => ({ ...r, devices: byRack[r.id] || [] }))
  } finally {
    loading.value = false
  }
}

// 按机房拉取全部设备：后端单页 size 上限 200，超过则翻页直到取完（仍然远少于每机柜一次）。
async function fetchRoomDevices(roomId) {
  const size = 200
  let page = 1
  let all = []
  while (true) {
    const data = await deviceApi.list({ room_id: roomId, page, size })
    const items = (data && data.items) || []
    if (!items.length) break
    all = all.concat(items)
    const total = (data && data.total) || 0
    if (all.length >= total) break
    page++
  }
  return all
}

// —— 颜色工具：hex 混色，用于导出 Excel 时按设备类型给 U 位单元格上浅色底，便于直观区分类型 ——
function hexToRgb(hex) {
  const h = hex.replace('#', '')
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)]
}
function rgbToHex(rgb) {
  return rgb
    .map((x) => Math.max(0, Math.min(255, Math.round(x))).toString(16).padStart(2, '0'))
    .join('')
}
function mixHex(hex, target, t) {
  const a = hexToRgb(hex)
  const b = hexToRgb(target)
  return rgbToHex(a.map((v, i) => v + (b[i] - v) * t))
}
// 6 位 hex → ExcelJS 需要的 8 位 ARGB（不透明前缀 FF）
function toArgb(hex) {
  return 'FF' + hex.replace('#', '').toUpperCase()
}

// 浏览器下载逻辑已抽取到 src/utils/download.js（downloadBlob），本页直接复用，避免重复实现。

// 导出机柜 U 位明细为 Excel（ExcelJS，支持单元格着色 + 合并 + 悬停批注）：
// 布局 1:1 镜像「机柜 2D 视图」的渲染结构（floorColumns），不做任何按机柜名的排序 / 分组 / 重组：
//   · 按 grid_col 分「竖向 section」（界面里的机柜列），section 间留间隔列；
//   · 每个 section 内按 grid_row 逐行堆叠机柜（界面里同一机的上下排列），每台机柜占 [U 编号列(宽4) | 设备列(宽20)]；
//   · 每个机柜竖向展开：表头行(机柜名/编号/已用U，30 磅高、深色底) + 自上而下 本机柜 total_u→1U。
// 设备占多 U 时竖向合并设备列、粗框线框住、按类型/重叠着色；悬停批注含完整信息。
async function exportExcel() {
  if (!racks.value.length) {
    warning('当前机房暂无机柜，无法导出 Excel')
    return
  }
  const maxU = Math.max(0, ...racks.value.map((r) => r.total_u || 0))
  if (!maxU) {
    warning('当前机房的机柜缺少 U 位信息，无法导出')
    return
  }
  const wb = new ExcelJS.Workbook()
  wb.creator = 'RackVisio'
  wb.created = new Date()
  const ws = wb.addWorksheet('机柜U位明细')

  // 样式常量
  const HEAD_FILL = 'FF1E293B' // slate-800 深色表头
  const HEAD_FONT = 'FFFFFFFF' // 白字
  const U_FILL = 'FFF1F5F9'    // slate-100 浅灰 U 位底
  const U_FONT = 'FF334155'    // slate-700 U 位字
  const FREE_FILL = 'FFFFFFFF' // 白底空闲
  const GAP_FILL = 'FFF8FAFC'  // 间隔列
  const GRID = 'FFE2E8F0'      // slate-200 细边框

  // 预计算每个机柜的 U → 设备映射与重叠集合
  const devInfo = {}
  for (const rack of racks.value) {
    const devByU = {}
    const overlaps = overlapIdsOf(rack)
    for (const d of rack.devices || []) {
      if (d.current_start_u == null || !d.u_height) continue
      const end = d.current_start_u + d.u_height - 1
      for (let u = d.current_start_u; u <= end; u++) devByU[u] = d
    }
    devInfo[rack.id] = { devByU, overlaps }
  }

  // 1:1 镜像「机柜 2D 视图」渲染结构（floorColumns），不按机柜名排序 / 分组 / 重组：
  //   · 按 grid_col 分「竖向 section」，每个 section 内按 grid_row 逐行堆叠机柜
  //   · 每个 section 占 2 列（U 编号列 + 设备列），section 之间留 1 间隔列
  //   · 每个机柜在自己的 2 列内竖向展开：表头行（机柜名/编号/已用U，30 磅高、深色底）
  //     + 自上而下 本机柜 total_u → 1U；同 grid_col 的多台机柜直接上下堆叠（B2-01 自然落在 A-01 下方）。
  const sections = floorColumns.value
  const sectionCols = sections.map((sec, ci) => ({
    sec,
    uCol: 1 + ci * 3,
    devCol: 2 + ci * 3,
    gapCol: 3 + ci * 3,
  }))
  const gapCols = new Set(sectionCols.map((s) => s.gapCol))
  // 记录已合并的矩形区域，避免任意合并区间相互重叠导致 ExcelJS 抛 "Cannot merge already merged cells"
  // （同一 section 内多机柜纵向共享同一组 Excel 列，设备 U 位重叠时尤其容易发生）
  const mergedRects = []
  const canRectMerge = (top, left, bottom, right) => {
    for (const r of mergedRects) {
      if (top <= r.bottom && bottom >= r.top && left <= r.right && right >= r.left) return false
    }
    mergedRects.push({ top, left, bottom, right })
    return true
  }

  // 逐 section 渲染：每个 section 在各自 2 列内，机柜从上到下堆叠（与 2D 视图行槽直接堆叠一致）
  for (const { sec, uCol, devCol } of sectionCols) {
    let row = 1 // 每个 section 从首行起（与 2D 视图各 floor-col 顶部对齐一致）
    for (const rack of sec.racks) {
      // —— 机柜表头行（合并 U 列与设备列，深色底白字，30 磅高） ——
      const hRow = ws.getRow(row)
      hRow.height = 30
      if (canRectMerge(row, uCol, row, devCol)) ws.mergeCells({ top: row, left: uCol, bottom: row, right: devCol })
      const hCell = hRow.getCell(uCol)
      hCell.value = rack.code ? `${rack.name}\n${rack.code} · ${rack.used_u}/${rack.total_u}U` : `${rack.name}\n${rack.used_u}/${rack.total_u}U`
      hCell.font = { bold: true, color: { argb: HEAD_FONT }, size: 11 }
      hCell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: HEAD_FILL } }
      hCell.alignment = { horizontal: 'center', vertical: 'middle', wrapText: true }
      const hd = { style: 'medium', color: { argb: HEAD_FILL } }
      hCell.border = { top: hd, left: hd, bottom: hd, right: hd }
      row++

      // —— U 位行：自上而下 本机柜 total_u → 1U（与机柜图形方向一致） ——
      const info = devInfo[rack.id] || { devByU: {}, overlaps: new Set() }
      for (let u = rack.total_u; u >= 1; u--) {
        const r = ws.getRow(row)
        r.height = 16
        const thin = { style: 'thin', color: { argb: GRID } }
        // 左：U 编号
        const uCell = r.getCell(uCol)
        uCell.value = u + 'U'
        uCell.font = { bold: true, color: { argb: U_FONT }, size: 9 }
        uCell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: U_FILL } }
        uCell.alignment = { horizontal: 'center', vertical: 'middle' }
        uCell.border = { top: thin, left: thin, bottom: thin, right: thin }
        // 右：设备
        const mCell = r.getCell(devCol)
        mCell.border = { top: thin, left: thin, bottom: thin, right: thin }
        const d = info.devByU[u]
        if (!d) {
          mCell.value = ''
          mCell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: FREE_FILL } }
          mCell.alignment = { horizontal: 'center', vertical: 'middle' }
          row++
          continue
        }
        const uTop = d.current_start_u + d.u_height - 1
        const uBottom = d.current_start_u
        if (u !== uTop) { row++; continue } // 仅顶部 U 行写内容，其余由合并呈现
        const isOverlap = info.overlaps.has(d.id)
        const typeBase = isOverlap ? '#ef4444' : DEVICE_TYPE_COLORS[d.device_type] || '#909399'
        const dark = toArgb(mixHex(typeBase, '000000', 0.22))
        const lightFill = toArgb(mixHex(typeBase, 'ffffff', 0.82))
        const typeLabel = DEVICE_TYPE_LABELS[d.device_type] || d.device_type
        mCell.value = (isOverlap ? '⚠ ' : '') + d.name
        mCell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: lightFill } }
        mCell.font = { bold: true, size: 9, color: { argb: dark } }
        mCell.alignment = { horizontal: 'center', vertical: 'middle', wrapText: true }
        const thick = { style: 'medium', color: { argb: 'FF1E293B' } }
        mCell.border = { top: thick, left: thick, bottom: thick, right: thick }
        // 悬停批注
        const noteLines = [`设备：${d.name}`]
        const noteFields = [
          ['类型', typeLabel],
          ['型号', d.model],
          ['序列号', d.sn],
          ['IP', d.ip_address],
          ['设备编码', d.device_code],
          ['开关机', DEVICE_POWER_LABELS[d.power_status] || '开机'],
        ].filter(([, v]) => v != null && String(v).trim() !== '')
        for (const [k, v] of noteFields) noteLines.push(`${k}：${v}`)
        noteLines.push(`占用：${uBottom}U–${uTop}U（${d.u_height}U）`)
        mCell.note = noteLines.join('\n')
        if (uBottom !== uTop) {
          // 循环自上而下写：uTop 写在当前行 row，uBottom 写在 row + (uTop - uBottom)。
          // 合并区间须向下覆盖设备自身占用的全部 U 行，而非向上并入更高 U 的空行。
          const topRow = row
          const botRow = row + (uTop - uBottom)
          if (canRectMerge(topRow, devCol, botRow, devCol)) {
            ws.mergeCells({ top: topRow, left: devCol, bottom: botRow, right: devCol })
          }
        }
        row++
      }
      // 机柜之间插入间隔行（视觉分隔同一 section 内纵向堆叠的机柜，B2-01 仍在 A-01 下方仅多一行空白）
      if (rack !== sec.racks[sec.racks.length - 1]) {
        const spacer = ws.getRow(row)
        spacer.height = 8
        const sU = spacer.getCell(uCol)
        const sD = spacer.getCell(devCol)
        sU.value = ''
        sD.value = ''
        sU.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: GAP_FILL } }
        sD.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: GAP_FILL } }
        const sep = { style: 'thin', color: { argb: GRID } }
        sU.border = { top: sep, bottom: sep, left: sep, right: sep }
        sD.border = { top: sep, bottom: sep, left: sep, right: sep }
        row++
      }
    }
  }

  // ════════════ 列宽 + 间隔列填充 ════════════
  for (const { uCol, devCol, gapCol } of sectionCols) {
    ws.getColumn(uCol).width = 4  // U 编号列
    ws.getColumn(devCol).width = 20 // 设备内容列
    ws.getColumn(gapCol).width = 2
    for (let rr = 1; rr <= ws.rowCount; rr++) {
      const gap = ws.getRow(rr).getCell(gapCol)
      gap.value = ''
      gap.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: GAP_FILL } }
    }
  }

  const buffer = await wb.xlsx.writeBuffer()
  const blob = new Blob([buffer], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  })
  const room = rooms.value.find((r) => r.id === selectedRoom.value)
  const safeName = (room?.name || '机房').replace(/[\\/:*?"<>|]/g, '_')
  const ts = new Date().toISOString().slice(0, 10)
  downloadBlob(blob, `机柜U位明细_${safeName}_${ts}.xlsx`)
}

onMounted(loadRooms)
</script>

<style scoped>
.rack-col {
  width: 170px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
}
.rack-head {
  height: 64px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  text-align: center;
  padding: 0 4px;
  border-bottom: 2px solid oklch(var(--border));
  margin-bottom: 10px;
  border-radius: 8px;
}
.rack-graphic {
  /* 高度由 rackPixelHeight 按 total_u 自适应，确保逐 U 编号完整不重叠 */
  display: flex;
  gap: 6px;
  align-items: stretch;
}
.rack-gutter {
  position: relative;
  width: 30px;
  height: 100%;
  flex-shrink: 0;
}
.u-tick {
  position: absolute;
  right: 0;
  transform: translateY(-50%);
  font-size: 10px;
  font-weight: 500;
  line-height: 1;
  color: oklch(var(--muted-foreground) / 0.7);
  font-variant-numeric: tabular-nums;
  text-align: right;
  width: 100%;
}
.u-tick.major {
  color: oklch(var(--muted-foreground));
  font-weight: 700;
  font-size: 11px;
}
.rack-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 0;
  background: oklch(var(--card));
  border: 1px solid oklch(var(--border) / 0.6);
  border-radius: 8px;
  overflow: hidden;
  box-sizing: border-box;
}
.seg {
  box-sizing: border-box;
  border-bottom: 1px solid oklch(var(--border) / 0.4);
  border-radius: 3px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  overflow: hidden;
  min-height: 0;
  position: relative;
}
.seg.dev {
  color: #fff;
  cursor: pointer;
  border-bottom-color: rgba(255, 255, 255, 0.35);
  transition: filter 0.15s;
}
.seg.dev:hover {
  filter: brightness(1.08);
}
.seg.dev.u-overlap {
  /* 红色描边由 segStyle 内联 boxShadow 统一绘制（含类型色条），此处仅保留圆角裁切。 */
}
.u-overlap-mark {
  position: absolute;
  top: 4px;
  left: 4px;
  width: 16px;
  height: 16px;
  border-radius: 9999px;
  background: #ef4444;
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  line-height: 16px;
  text-align: center;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
}
.seg-name {
  font-size: 13px;
  font-weight: 600;
  line-height: 1.2;
  padding: 0 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}
/* 1U 设备空间极窄：缩小字号、收紧行高，仅展示设备名称（U 数已省略）。 */
.seg-name.is-1u {
  font-size: 11px;
  line-height: 1.1;
  padding: 0 3px;
}
.seg-meta {
  font-size: 11px;
  opacity: 0.85;
}
.seg.free {
  background: oklch(var(--muted) / 0.4);
  cursor: default;
}
.status-dot {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 7px;
  height: 7px;
  border-radius: 9999px;
  box-shadow: 0 0 0 1.5px rgba(255, 255, 255, 0.6);
}
.pop-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 13px;
  padding: 3px 0;
  color: oklch(var(--muted-foreground));
}
.pop-row span:last-child {
  color: oklch(var(--foreground));
}
.pop-row--warn {
  color: #ef4444;
  font-weight: 600;
}
.pop-row--warn span {
  color: #ef4444 !important;
}
.pop-hint {
  margin-top: 8px;
  font-size: 11px;
  color: oklch(var(--muted-foreground) / 0.7);
  text-align: center;
}
/* 镜像机房平面图：各平面列并排（左→右=grid_col），整体可横向滚动（列过多时不拆断） */
.floor-canvas {
  display: flex;
  flex-direction: row;
  align-items: flex-start;
  gap: 24px;
  overflow-x: auto;
  padding-bottom: 8px;
  scrollbar-width: thin;
  scrollbar-color: oklch(var(--muted-foreground) / 0.3) transparent;
}
.floor-canvas::-webkit-scrollbar {
  height: 8px;
}
.floor-canvas::-webkit-scrollbar-thumb {
  background: oklch(var(--muted-foreground) / 0.3);
  border-radius: 9999px;
}
.floor-col {
  display: flex;
  flex-direction: column;
}
.col-inner {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.row-slot {
  display: flex;
}
</style>
