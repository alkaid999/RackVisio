<template>
  <div>
    <!-- 标题区 + 机房选择 -->
    <div class="page-head">
      <div>
        <h1 class="page-title">2D 机柜视图</h1>
        <p class="page-sub">选择机房查看机柜平面排布，悬停设备查看详细信息</p>
      </div>
      <div class="flex items-center gap-3">
        <Select v-model="selectedRoom" class="w-56" @update:model-value="onRoomChange">
          <SelectTrigger placeholder="选择机房" />
          <SelectContent>
            <SelectItem v-for="r in rooms" :key="r.id" :value="r.id">{{ r.name }}</SelectItem>
          </SelectContent>
        </Select>
        <Button variant="outline" :disabled="loading" title="导出机柜 U 位明细（按机柜行分组：每行以最高机柜为基准、整行向下对齐，矮机柜上方留「为空」占位，行间插间隔带）" @click="exportExcel">
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
          <span class="flex items-center gap-1.5 text-xs text-muted-foreground">
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
          <!-- 网格区域：行主序，与 FloorPlanBoard 绝对定位网格一一对应。
               每行首格嵌入行标签（column_code），行高随该行最高机柜自适应，标签天然对齐。
               机柜卡片高度按真实 U 数（rackPixelHeight）渲染，矮机柜顶部对齐、下方留白保留。 -->
          <div class="grid-main">
            <div v-for="(row, ri) in floorGrid" :key="'row-' + ri" class="grid-row">
              <div class="row-label-cell">{{ rowLabels[ri] }}</div>
              <div v-for="(slot, ci) in row" :key="'cell-' + ri + '-' + ci" class="grid-cell">
                <div v-if="slot" class="rack-col">
                  <!-- 机柜卡片：高度严格按真实 U 数（rackPixelHeight，统一 px/U 比例），
                       从底部（地板线）对齐，矮机柜落在高机柜对应 U 位置下方，U1 共用同一地板线。 -->
            <!-- 机柜头 -->
            <div
              class="rack-head"
              :class="{ 'is-special-rack': isSpecialRack(slot.status) }"
              :style="isSpecialRack(slot.status) ? { borderColor: RACK_STATUS_COLORS[slot.status], boxShadow: '0 0 0 1px ' + RACK_STATUS_COLORS[slot.status] } : null"
            >
              <div class="flex items-center justify-center gap-1 font-medium text-foreground truncate" :title="slot.name">
                <span v-if="isSpecialRack(slot.status)" class="mr-0.5" :style="{ color: RACK_STATUS_COLORS[slot.status], fontSize: '14px' }">{{ statusIcon(slot.status) }}</span>
                {{ slot.name }}
              </div>
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
                        :class="{ 'u-overlap': overlapIdsOf(slot).has(seg.device.id), 'is-facility': !isAssetDevice(seg.device) }"
                        :style="segStyle(seg, slot)"
                        @mouseenter="openPop(seg.device.id)"
                        @mouseleave="closePop()"
                        @click="openDetail(seg.device)"
                      >
                        <div class="seg-name" :class="{ 'is-1u': seg.size === 1, 'facility-name': !isAssetDevice(seg.device) }">{{ seg.device.name }}</div>
                        <div v-if="seg.size > 1" class="seg-meta">{{ seg.uStart }}U–{{ seg.uEnd }}U · {{ seg.size }}U</div>
                        <span v-if="overlapIdsOf(slot).has(seg.device.id)" class="u-overlap-mark">!</span>
                        <span v-if="isAssetDevice(seg.device)" class="status-dot" :style="{ background: powerDotColor(seg.device.power_status) }"></span>
                      </div>
                    </template>
                    <PopoverContent class="w-64 pointer-events-none">
                      <div class="pop">
                        <div class="flex items-center justify-between mb-2">
                          <span class="font-semibold text-foreground truncate">{{ seg.device.name }}</span>
                          <StatusBadge type="device" :value="seg.device.status" />
                        </div>
                        <div class="pop-row"><span>类型</span><span class="font-medium" :style="{ color: typeColor(seg.device.device_type) }">{{ DEVICE_TYPE_LABELS[seg.device.device_type] }}</span></div>
                        <template v-if="!isAssetDevice(seg.device)">
                          <div class="pop-row pop-row--note"><span>属性</span><span>基础设施（非资产）</span></div>
                          <div class="pop-row"><span>U 位</span><span>{{ seg.uStart }}U–{{ seg.uEnd }}U（{{ seg.size }}U）</span></div>
                          <div class="pop-row pop-row--note"><span>说明</span><span>占 U 位，不计入资产 / 不建接口</span></div>
                        </template>
                        <template v-else>
                          <div class="pop-row"><span>开关机</span><span class="font-medium" :style="{ color: (DEVICE_POWER_COLORS[seg.device.power_status] || DEVICE_POWER_COLORS['开机']) }">{{ DEVICE_POWER_LABELS[seg.device.power_status] || '开机' }}</span></div>
                          <div class="pop-row"><span>型号</span><span>{{ seg.device.model || '—' }}</span></div>
                          <div class="pop-row"><span>IP</span><span>{{ seg.device.ip_address || '—' }}</span></div>
                          <div class="pop-row"><span>设备编码</span><span>{{ seg.device.device_code || '—' }}</span></div>
                          <div class="pop-row"><span>U 位</span><span>{{ seg.uStart }}U–{{ seg.uEnd }}U（{{ seg.size }}U）</span></div>
                        </template>
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
                <div v-else class="rack-empty-slot" :title="'空位（行' + (ri + 1) + ' 列' + (ci + 1) + '）'"></div>
              </div>
            </div>
          </div>
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
        <div v-if="allOverlapIds.has(detailDevice.id)" class="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
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
import { useRoomStore } from '@/stores/room'
import StatusBadge from '@/components/common/StatusBadge.vue'
import {
  DEVICE_TYPE_OPTIONS,
  DEVICE_TYPE_LABELS,
  DEVICE_TYPE_COLORS,
  DEVICE_POWER_COLORS,
  DEVICE_POWER_LABELS,
  isAssetDevice,
  RACK_STATUS_COLORS,
  RACK_STATUS_ICONS,
  isSpecialRack,
  statusIcon,
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
const roomStore = useRoomStore()
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
  // 设施（非资产）：斜纹底纹 + 中性灰，与资产实心色块明确区分（不显示开关机圆点）。
  if (!isAssetDevice(d)) {
    const base = typeColor(d.device_type)
    return {
      height: (seg.size / rack.total_u) * 100 + '%',
      background: `repeating-linear-gradient(45deg, ${base}, ${base} 7px, rgba(255,255,255,0.12) 7px, rgba(255,255,255,0.12) 14px)`,
      boxShadow,
    }
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
// 机柜图形高度 = 真实 U 数 × 统一比例尺（15px/U），所有机柜共用同一比例，
// 因此 10U 机柜严格落在 24U/42U 机柜的「10U 位置」下方，绝不拉伸到统一高度。
// 配合 .rack-col 的 align-self:flex-end（底部/地板对齐），U1 全部对齐同一地板线。
function rackPixelHeight(total) {
  const t = total || 42
  return Math.round(t * 15) + 'px'
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

// 2D 视图布局：行主序二维网格，与 FloorPlanBoard（机房平面图）绝对定位网格完全一致。
// - 外层 = 行（grid_row 0→bounds.rows-1），内层 = 列（grid_col 0→bounds.cols-1）
// - 每个单元格 (row, col) 最多容纳一台机柜，无则为空槽位
// - 渲染时先行后列（左到右），与平面图从上到下、从左到右的阅读顺序一一对应
// - bounds 与 FloorPlanBoard.bounds 完全一致：rows=Math.max(3,maxR+2), cols=Math.max(4,maxC+2)
const bounds = computed(() => {
  let maxR = 0, maxC = 0
  for (const r of racks.value) {
    if (r.grid_row != null) maxR = Math.max(maxR, r.grid_row)
    if (r.grid_col != null) maxC = Math.max(maxC, r.grid_col)
  }
  return { rows: Math.max(3, maxR + 2), cols: Math.max(4, maxC + 2) }
})

// 行主序二维网格：grid[row][col] = rack | null
// 与 FloorPlanBoard.cellBox(grid_row, grid_col) 使用相同的 (row, col) 坐标系
const floorGrid = computed(() => {
  const b = bounds.value
  const grid = Array.from({ length: b.rows }, () => Array(b.cols).fill(null))
  for (const rack of racks.value) {
    const r = rack.grid_row ?? 0
    const c = rack.grid_col ?? 0
    if (r >= 0 && r < b.rows && c >= 0 && c < b.cols) {
      grid[r][c] = rack
    }
  }
  return grid
})

// 行标签：取该行所有机柜的 column_code 去重拼接（与 FloorPlanBoard.rowLabels 一致）
const rowLabels = computed(() => {
  const labels = []
  for (let r = 0; r < bounds.value.rows; r++) {
    const codes = [...new Set(racks.value.filter((x) => x.grid_row === r).map((x) => x.column_code))]
    labels.push(codes.length ? codes.join(' · ') : '')
  }
  return labels
})

// U 位明细功能已移除（该信息可由设备详情弹窗 / 设备列表覆盖），此处仅保留机柜图形与重叠告警。

// 选中机房后：同步到 room store（保持平面图 / 详情上下文一致），并写回 URL ?room=
// 以便刷新或直链仍能回到同一个机房（避免 2D 视图与平面图因默认机房不同而「看起来对不上」）。
function syncRoomQuery(id) {
  if (id && id !== route.query.room) {
    router.replace({ query: { ...route.query, room: id } })
  }
}
async function onRoomChange(val) {
  selectedRoom.value = val
  await loadRacks()
  const r = rooms.value.find((x) => x.id === val)
  if (r) roomStore.currentRoom = r
  syncRoomQuery(val)
}

async function loadRooms() {
  const data = await roomApi.list({ size: 200 })
  rooms.value = data.items || []
  // 预选优先级：URL ?room= > 当前正在查看的机房（平面图/详情已设置 roomStore.currentRoom）> 列表首个。
  // 这样从机房详情（含平面图）点进「机柜 2D 视图」时，默认就是同一个机房，与平面图完全一致。
  const inList = (id) => rooms.value.some((x) => x.id === id)
  const currentRoomId = roomStore.currentRoom?.id
  const preselect =
    route.query.room ||
    (currentRoomId && inList(currentRoomId) ? currentRoomId : '') ||
    (rooms.value.length ? rooms.value[0].id : '')
  if (preselect) {
    selectedRoom.value = preselect
    await loadRacks()
    syncRoomQuery(preselect)
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
// 按「机柜行」(grid_row) 分组，镜像机房平面图：
//   · 每行取该行最高机柜 total_u 作为基准行高（一行中最高机柜为准）；
//   · 行内所有机柜 U 位从 maxU → 1U 自上而下展开，矮机柜上方（u > 自身 total_u）渲染极淡
//     「为空」占位格，从而整行【向下对齐】（U1 共用底部基准线），与平面图底对齐一致；
//   · 每台机柜占 [U 编号列(宽4) | 设备列(宽20)]，机柜列之间留间隔列；
//   · 行与行之间插一条间隔带（间隔间隔）做视觉分隔；
//   · 设备占多 U 时竖向合并设备列、粗框线框住、按类型/重叠着色；悬停批注含完整信息。
async function exportExcel() {
  if (!racks.value.length) {
    warning('当前机房暂无机柜，无法导出 Excel')
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
  const EMPTY_FILL = 'FFF8FAFC' // 矮机柜上方「为空」占位（极淡）
  const GAP_FILL = 'FFF1F5F9'  // 间隔列 / 间隔带
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

  // 列布局：基于 floorGrid 的 grid_col 全局列（与平面图列位置一一对应），
  // 每个 grid_col 占 3 列 [U编号 | 设备 | 间隔]
  const fg = floorGrid.value
  const cols = fg[0].length
  const colOf = (gc) => ({ uCol: 1 + gc * 3, devCol: 2 + gc * 3, gapCol: 3 + gc * 3 })

  // 合并区保护（本布局理论上不会重叠，保留以防边界情况）
  const mergedRects = []
  const canRectMerge = (top, left, bottom, right) => {
    for (const r of mergedRects) {
      if (top <= r.bottom && bottom >= r.top && left <= r.right && right >= r.left) return false
    }
    mergedRects.push({ top, left, bottom, right })
    return true
  }

  const thin = { style: 'thin', color: { argb: GRID } }
  let excelRow = 1

  for (let ri = 0; ri < fg.length; ri++) {
    // 该行机柜（按 grid_col 从左到右），跳过空行
    const rowRacks = fg[ri].filter((x) => x)
    if (!rowRacks.length) continue
    const maxU = Math.max(0, ...rowRacks.map((r) => r.total_u || 0))
    if (!maxU) continue

    // —— 表头行：每台机柜合并 [U编号|设备] 列，深色底白字 ——
    const hRow = ws.getRow(excelRow)
    hRow.height = 30
    for (const rack of rowRacks) {
      const { uCol, devCol } = colOf(rack.grid_col ?? 0)
      if (canRectMerge(excelRow, uCol, excelRow, devCol)) {
        ws.mergeCells({ top: excelRow, left: uCol, bottom: excelRow, right: devCol })
      }
      const hCell = hRow.getCell(uCol)
      hCell.value = rack.code ? `${rack.name}\n${rack.code} · ${rack.used_u}/${rack.total_u}U` : `${rack.name}\n${rack.used_u}/${rack.total_u}U`
      hCell.font = { bold: true, color: { argb: HEAD_FONT }, size: 11 }
      hCell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: HEAD_FILL } }
      hCell.alignment = { horizontal: 'center', vertical: 'middle', wrapText: true }
      const hd = { style: 'medium', color: { argb: HEAD_FILL } }
      hCell.border = { top: hd, left: hd, bottom: hd, right: hd }
    }
    excelRow++

    // —— U 位行：maxU → 1U 自上而下（整行向下对齐，U1 在底部） ——
    for (let u = maxU; u >= 1; u--) {
      const r = ws.getRow(excelRow)
      r.height = 16
      for (const rack of rowRacks) {
        const { uCol, devCol } = colOf(rack.grid_col ?? 0)
        if (u > rack.total_u) {
          // 矮机柜上方「为空」占位：极淡填充 + 细边框，占住该列位置（与平面图矮机柜悬空一致）
          const uCell = r.getCell(uCol)
          uCell.value = ''
          uCell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: EMPTY_FILL } }
          uCell.border = { top: thin, left: thin, bottom: thin, right: thin }
          const dCell = r.getCell(devCol)
          dCell.value = ''
          dCell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: EMPTY_FILL } }
          dCell.border = { top: thin, left: thin, bottom: thin, right: thin }
          continue
        }
        // 左：U 编号（仅机柜自身 U 范围内显示）
        const uCell = r.getCell(uCol)
        uCell.value = u + 'U'
        uCell.font = { bold: true, color: { argb: U_FONT }, size: 9 }
        uCell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: U_FILL } }
        uCell.alignment = { horizontal: 'center', vertical: 'middle' }
        uCell.border = { top: thin, left: thin, bottom: thin, right: thin }
        // 右：设备 / 空闲
        const mCell = r.getCell(devCol)
        const info = devInfo[rack.id] || { devByU: {}, overlaps: new Set() }
        const d = info.devByU[u]
        if (!d) {
          mCell.value = ''
          mCell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: FREE_FILL } }
          mCell.alignment = { horizontal: 'center', vertical: 'middle' }
          mCell.border = { top: thin, left: thin, bottom: thin, right: thin }
          continue
        }
        const uTop = d.current_start_u + d.u_height - 1
        const uBottom = d.current_start_u
        if (u !== uTop) continue // 非顶部 U 行仅占位，由顶部 U 行统一绘制
        // —— 设备顶部 U 行：绘制整段占用区间 ——
        const isOverlap = info.overlaps.has(d.id)
        const typeBase = isOverlap ? '#ef4444' : DEVICE_TYPE_COLORS[d.device_type] || '#909399'
        const dark = toArgb(mixHex(typeBase, '000000', 0.22))
        const lightFill = toArgb(mixHex(typeBase, 'ffffff', 0.82))
        const typeLabel = DEVICE_TYPE_LABELS[d.device_type] || d.device_type
        const frame = { style: 'medium', color: { argb: 'FF1E293B' } }
        const topRow = excelRow
        const botRow = excelRow + (uTop - uBottom)
        for (let rr = topRow; rr <= botRow; rr++) {
          const c = ws.getRow(rr).getCell(devCol)
          const isTop = rr === topRow
          const isBot = rr === botRow
          c.border = {
            top: isTop ? frame : thin,
            left: frame,
            right: frame,
            bottom: isBot || isTop ? frame : thin,
          }
          c.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: lightFill } }
        }
        mCell.value = (isOverlap ? '⚠ ' : '') + d.name
        mCell.font = { bold: true, size: 9, color: { argb: dark } }
        mCell.alignment = { horizontal: 'center', vertical: 'middle', wrapText: true }
        const noteLines = [`设备：${d.name}`]
        const isFac = !isAssetDevice(d)
        const noteFields = isFac
          ? [
              ['类型', typeLabel],
              ['属性', '基础设施（非资产）'],
            ]
          : [
              ['类型', typeLabel],
              ['型号', d.model],
              ['序列号', d.sn],
              ['IP', d.ip_address],
              ['设备编码', d.device_code],
              ['开关机', DEVICE_POWER_LABELS[d.power_status] || '开机'],
            ]
        for (const [k, v] of noteFields) noteLines.push(`${k}：${v}`)
        if (isFac) noteLines.push('占 U 位，不计入资产统计 / 不建接口')
        noteLines.push(`占用：${uBottom}U–${uTop}U（${d.u_height}U）`)
        mCell.note = noteLines.join('\n')
        if (uBottom !== uTop && canRectMerge(topRow, devCol, botRow, devCol)) {
          ws.mergeCells({ top: topRow, left: devCol, bottom: botRow, right: devCol })
        }
      }
      excelRow++
    }

    // —— 行间隔带（间隔间隔）：整行 GAP_FILL 做视觉分隔 ——
    const sp = ws.getRow(excelRow)
    sp.height = 8
    for (let gc = 0; gc < cols; gc++) {
      const { uCol, devCol, gapCol } = colOf(gc)
      for (const c of [uCol, devCol, gapCol]) {
        const cell = sp.getCell(c)
        cell.value = ''
        cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: GAP_FILL } }
      }
    }
    excelRow++
  }

  // ════════════ 列宽 + 间隔列填充 ════════════
  for (let gc = 0; gc < cols; gc++) {
    const { uCol, devCol, gapCol } = colOf(gc)
    ws.getColumn(uCol).width = 4
    ws.getColumn(devCol).width = 20
    ws.getColumn(gapCol).width = 2
    for (let rr = 1; rr < excelRow; rr++) {
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
  /* 高度由内容自然撑开（头部 64px + rack-graphic 按真实 U 数动态高度），
     严格正比于 U 数——10U 矮、42U 高。
     关键：align-self: flex-end 使其在更高的行里【底部（地板）对齐】，
     矮机柜悬于高机柜下方，U1 共用同一地板线，而不是被拉伸填满或顶部对齐。 */
  align-self: flex-end;
  background: hsl(var(--card));
  border: 2px solid hsl(var(--foreground) / 0.28);
  border-radius: 12px;
  padding: 12px 12px 14px;
  box-shadow: 0 1px 3px hsl(var(--foreground) / 0.06);
}
/* 平面图空槽位占位：不强制高度，随所在行（由该行最高机柜决定）自然撑开，
   仅以极淡虚线边框提示"此处为预留空位"，保留平面图的空白网格空间。 */
.rack-empty-slot {
  width: 170px;
  flex-shrink: 0;
  border-radius: 12px;
  border: 1px dashed hsl(var(--border) / 0.3);
  box-sizing: border-box;
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
/* 设施名称：斜纹底上白色原名看不清，加半透明深灰底 pill 提升可读性（明暗模式通用）。 */
.seg-name.facility-name {
  background: rgba(15, 23, 42, 0.5);
  color: #e2e8f0;
  border-radius: 3px;
  padding: 1px 5px;
  text-shadow: 0 1px 1px rgba(0, 0, 0, 0.35);
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
/* 设施提示行（非资产说明）：弱化色，区别于常规取值 */
.pop-row--note span:last-child {
  color: oklch(var(--muted-foreground));
  font-weight: 500;
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
/* 镜像机房平面图：行主序二维网格（与 FloorPlanBoard 绝对定位网格一一对应），
   整体可横向滚动（列过多时不拆行） */
.floor-canvas {
  display: flex;
  flex-direction: row;
  align-items: flex-start;
  gap: 0;
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
/* 行标签：嵌入每个 grid-row 首格（动态行高下，独立列无法逐行对齐）。
   stretch 使其随行高撑开，内部文字垂直居中、右对齐贴近网格。 */
.row-label-cell {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  width: 36px;
  flex-shrink: 0;
  padding-right: 6px;
  font-size: 10px;
  font-weight: 500;
  color: oklch(var(--muted-foreground));
}
/* 网格主区域：所有行列 */
.grid-main {
  display: flex;
  flex-direction: column;
  gap: 14px; /* 行间距，对应平面图的 GAP */
}
.grid-row {
  display: flex;
  flex-direction: row;
  gap: 24px; /* 列间距，对应平面图的 GAP */
}
.grid-cell {
  display: flex;
  width: 170px;
  shrink: 0;
}
</style>
