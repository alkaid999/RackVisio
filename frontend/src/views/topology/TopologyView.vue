<template>
  <div class="topo-page">
    <div class="page-head">
      <div>
        <h2 class="page-title">拓扑视图</h2>
        <p class="page-sub">
          设备与链路关系力导向图（手写 SVG，零额外依赖）。拖拽节点重组布局、滚轮缩放、拖拽空白处平移；悬停高亮邻居，点击设备跳详情。
        </p>
      </div>
      <div class="flex items-center gap-2">
        <Badge variant="outline" class="tabular-nums">{{ nodes.length }} 节点</Badge>
        <Badge variant="outline" class="tabular-nums">{{ edges.length }} 链路</Badge>
      </div>
    </div>

    <!-- 筛选工具栏 -->
    <div class="toolbar">
      <div class="flex flex-wrap items-end gap-4">
        <div class="flex flex-col gap-1">
          <Label>机房</Label>
          <Select :model-value="filter.roomId" @update:model-value="onRoomChange" class="w-44">
            <SelectTrigger :placeholder="rooms.length ? '全部机房' : '加载中…'" />
            <SelectContent>
              <SelectItem value="">全部机房</SelectItem>
              <SelectItem v-for="r in rooms" :key="r.id" :value="r.id">{{ r.name }}</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div class="flex flex-col gap-1">
          <Label>机柜</Label>
          <Select :model-value="filter.rackId" @update:model-value="onRackChange" :disabled="!filter.roomId" class="w-44">
            <SelectTrigger :placeholder="filter.roomId ? (racks.length ? '全部机柜' : '无机柜') : '先选机房'" />
            <SelectContent>
              <SelectItem value="">全部机柜</SelectItem>
              <SelectItem v-for="rk in racks" :key="rk.id" :value="rk.id">{{ rk.name || rk.code }}</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div class="flex items-center gap-2 pb-0.5">
          <Button variant="outline" size="sm" @click="reLayout">
            <RefreshCw class="mr-1.5 h-4 w-4" />重新布局
          </Button>
          <Button variant="outline" size="sm" @click="fit">
            <Maximize2 class="mr-1.5 h-4 w-4" />适应视图
          </Button>
        </div>
      </div>
    </div>

    <!-- 图区 + 浮层 -->
    <Card class="topo-card">
      <div class="topo-stage">
        <!-- 加载 -->
        <div v-if="loading" class="topo-center">
          <Spinner class="h-7 w-7 text-primary" />
          <span class="mt-2 text-sm text-muted-foreground">拓扑数据加载中…</span>
        </div>

        <!-- 空态 -->
        <EmptyState
          v-else-if="nodes.length === 0"
          title="暂无拓扑数据"
          description="当前范围内没有可上架设备或未建立任何链路。先在「连接总览」创建链路，再回到此处可视化。"
          :icon="Network"
          class="topo-center"
        />

        <!-- 错误 -->
        <div v-else-if="error" class="topo-center text-sm text-destructive">{{ error }}</div>

        <!-- 力导向图 -->
        <svg
          v-else
          ref="svgRef"
          class="topo-svg"
          @pointerdown="onBgPointerDown"
          @wheel.prevent="onWheel"
        >
          <g :transform="`translate(${view.tx},${view.ty}) scale(${view.scale})`">
            <!-- 边 -->
            <line
              v-for="e in edges"
              :key="'e-' + e.id"
              :x1="nodeById.get(e.source)?.x || 0"
              :y1="nodeById.get(e.source)?.y || 0"
              :x2="nodeById.get(e.target)?.x || 0"
              :y2="nodeById.get(e.target)?.y || 0"
              :stroke="mediumColor(e.medium)"
              :stroke-width="edgeWidth(e)"
              :stroke-opacity="edgeOpacity(e)"
              :stroke-linecap="isEdgeActive(e) ? 'round' : 'butt'"
              :class="{ 'topo-edge--active': isEdgeActive(e) }"
            />
            <!-- 节点 -->
            <g
              v-for="n in nodes"
              :key="'n-' + n.id"
              :transform="`translate(${n.x},${n.y})`"
              class="topo-node"
              :class="{ 'topo-node--dim': !isNodeActive(n) }"
              @pointerdown="onNodePointerDown($event, n)"
              @mouseenter="onHover(n.id)"
              @mouseleave="onLeave"
              @click.stop
            >
              <circle
                :r="NODE_R"
                :fill="deviceColor(n.device_type)"
                :stroke="statusColor(n.status)"
                :stroke-width="hoveredId === n.id ? 4 : 3"
              />
              <text :y="NODE_R + 13" text-anchor="middle" class="topo-label">{{ n.name }}</text>
            </g>
          </g>
        </svg>

        <!-- 悬浮设备信息卡 -->
        <transition name="fade">
          <div v-if="hoveredNode" class="topo-info glass-soft">
            <div class="flex items-center justify-between gap-2">
              <span class="text-sm font-semibold truncate">{{ hoveredNode.name }}</span>
              <button class="topo-info-close" @click="onLeave" aria-label="关闭">
                <X class="h-3.5 w-3.5" />
              </button>
            </div>
            <div class="mt-1.5 flex flex-wrap gap-1.5">
              <span class="chip" :style="{ background: deviceColor(hoveredNode.device_type) + '22', color: deviceColor(hoveredNode.device_type) }">
                {{ typeLabel(hoveredNode.device_type) }}
              </span>
              <span class="chip" :style="{ background: statusColor(hoveredNode.status) + '22', color: statusColor(hoveredNode.status) }">
                {{ statusLabel(hoveredNode.status) }}
              </span>
            </div>
            <div class="mt-1.5 text-xs text-muted-foreground">
              连接数：{{ (adj.get(hoveredNode.id)?.size) || 0 }} · 点击查看详情
            </div>
          </div>
        </transition>

        <!-- 缩放控制 -->
        <div v-if="nodes.length" class="topo-zoom glass-soft">
          <button class="topo-zoom-btn" @click="zoomBy(1.2)" aria-label="放大"><ZoomIn class="h-4 w-4" /></button>
          <div class="topo-zoom-val">{{ Math.round(view.scale * 100) }}%</div>
          <button class="topo-zoom-btn" @click="zoomBy(1 / 1.2)" aria-label="缩小"><ZoomOut class="h-4 w-4" /></button>
        </div>

        <!-- 图例 -->
        <div v-if="nodes.length" class="topo-legend glass-soft">
          <div class="legend-title">设备类型</div>
          <div class="legend-grid">
            <div v-for="t in meta.deviceType" :key="'lt-' + t.value" class="legend-item">
              <span class="legend-dot" :style="{ background: t.color }" />
              <span class="legend-text">{{ t.label }}</span>
            </div>
          </div>
          <div class="legend-title mt-2">连接介质</div>
          <div class="legend-grid">
            <div v-for="m in LINK_MEDIUM_OPTIONS" :key="'lm-' + m.value" class="legend-item">
              <span class="legend-line" :style="{ background: LINK_MEDIUM_COLORS[m.value] || '#909399' }" />
              <span class="legend-text">{{ m.label }}</span>
            </div>
          </div>
          <div class="legend-title mt-2">状态环</div>
          <div class="legend-grid">
            <div v-for="s in meta.deviceStatus" :key="'ls-' + s.value" class="legend-item">
              <span class="legend-ring" :style="{ borderColor: s.color }" />
              <span class="legend-text">{{ s.label }}</span>
            </div>
          </div>
        </div>
      </div>
    </Card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useMetaStore } from '@/stores/meta'
import topologyApi from '@/api/topology'
import roomApi from '@/api/room'
import { LINK_MEDIUM_COLORS, LINK_MEDIUM_OPTIONS } from '@/utils/constants'
import { ZoomIn, ZoomOut, Maximize2, RefreshCw, Network, X } from 'lucide-vue-next'
import Button from '@/components/ui/button.vue'
import Select from '@/components/ui/select.vue'
import SelectTrigger from '@/components/ui/select-trigger.vue'
import SelectContent from '@/components/ui/select-content.vue'
import SelectItem from '@/components/ui/select-item.vue'
import Label from '@/components/ui/label.vue'
import Badge from '@/components/ui/badge.vue'
import EmptyState from '@/components/ui/empty-state.vue'
import Spinner from '@/components/ui/spinner.vue'
import Card from '@/components/ui/card.vue'

const router = useRouter()
const meta = useMetaStore()

const NODE_R = 16

// ---------- 数据 ----------
const loading = ref(false)
const error = ref('')
const rawNodes = ref([])
const rawEdges = ref([])

// ---------- 筛选 ----------
const rooms = ref([])
const racks = ref([])
const filter = reactive({ roomId: '', rackId: '' })

// ---------- 仿真状态 ----------
const nodes = ref([]) // 响应对象：{id,name,device_type,status,rack_id,x,y,vx,vy,fx,fy}
const edges = ref([])
const adj = ref(new Map())
let nodeById = new Map() // 非响应：id -> 节点对象（持有响应式引用）

// ---------- 视图变换 ----------
const svgRef = ref(null)
const size = reactive({ w: 800, h: 560 })
const view = reactive({ tx: 400, ty: 280, scale: 1 })

const hoveredId = ref(null)
const hoveredNode = computed(() => nodes.value.find((n) => n.id === hoveredId.value) || null)

// ---------- 物理参数 ----------
const SIM = {
  kRep: 420,
  springK: 0.05,
  restLen: 95,
  gravK: 0.03,
  friction: 0.42,
  alpha: 1,
  alphaMin: 0.02,
  alphaDecay: 0.0228,
  minDist: 12,
}
let rafId = null
let dragging = null
let ro = null

// ---------- 着色 ----------
const deviceColor = (t) => meta.deviceTypeColor(t)
const statusColor = (s) => meta.deviceStatusColor(s)
const mediumColor = (m) => LINK_MEDIUM_COLORS[m] || '#909399'
const typeLabel = (v) => (meta.deviceType.find((t) => t.value === v) || {}).label || v || ''
const statusLabel = (v) => (meta.deviceStatus.find((t) => t.value === v) || {}).label || v || ''

// ---------- 高亮判定 ----------
function neighborSet(id) {
  return adj.value.get(id) || new Set()
}
function isNodeActive(n) {
  if (!hoveredId.value) return true
  if (n.id === hoveredId.value) return true
  return neighborSet(hoveredId.value).has(n.id)
}
function isEdgeActive(e) {
  if (!hoveredId.value) return false
  return e.source === hoveredId.value || e.target === hoveredId.value
}
function nodeOpacity(n) {
  return isNodeActive(n) ? 1 : 0.22
}
function edgeOpacity(e) {
  if (!hoveredId.value) return 0.55
  return isEdgeActive(e) ? 0.95 : 0.1
}
function edgeWidth(e) {
  return isEdgeActive(e) ? 2.6 : 1.6
}

// ---------- 数据加载 ----------
async function loadRooms() {
  try {
    const d = await roomApi.list()
    rooms.value = (d && d.items) || []
  } catch (e) {
    rooms.value = []
  }
}
async function onRoomChange(v) {
  filter.roomId = v || ''
  filter.rackId = ''
  racks.value = []
  if (filter.roomId) {
    try {
      const r = await roomApi.racks(filter.roomId)
      racks.value = Array.isArray(r) ? r : r.items || []
    } catch (e) {
      racks.value = []
    }
  }
  loadTopology()
}
function onRackChange(v) {
  filter.rackId = v || ''
  loadTopology()
}

async function loadTopology() {
  loading.value = true
  error.value = ''
  try {
    const params = {}
    if (filter.roomId) params.room_id = filter.roomId
    if (filter.rackId) params.rack_id = filter.rackId
    const data = await topologyApi.list(params)
    rawNodes.value = data.nodes || []
    rawEdges.value = data.edges || []
    if (rawNodes.value.length === 0) {
      nodes.value = []
      edges.value = []
      nodeById = new Map()
      adj.value = new Map()
    } else {
      buildGraph()
    }
  } catch (e) {
    error.value = '拓扑数据加载失败，请稍后重试'
    nodes.value = []
    edges.value = []
  } finally {
    loading.value = false
  }
}

// ---------- 构建图并启动仿真 ----------
function buildGraph() {
  const ns = rawNodes.value.map((n) => ({
    id: n.id,
    name: n.name,
    device_type: n.device_type,
    status: n.status,
    rack_id: n.rack_id,
    x: (Math.random() - 0.5) * Math.min(size.w, size.h) * 0.5,
    y: (Math.random() - 0.5) * Math.min(size.w, size.h) * 0.5,
    vx: 0,
    vy: 0,
    fx: null,
    fy: null,
  }))
  const idset = new Set(ns.map((n) => n.id))
  const es = rawEdges.value
    .filter((e) => idset.has(e.source) && idset.has(e.target))
    .map((e) => ({ ...e }))

  nodeById = new Map()
  ns.forEach((n) => nodeById.set(n.id, n))
  const m = new Map()
  ns.forEach((n) => m.set(n.id, new Set()))
  es.forEach((e) => {
    m.get(e.source)?.add(e.target)
    m.get(e.target)?.add(e.source)
  })

  nodes.value = ns
  edges.value = es
  adj.value = m

  view.tx = size.w / 2
  view.ty = size.h / 2
  view.scale = 1
  SIM.alpha = 1
  startSim()
}

// ---------- 力导向仿真 ----------
function startSim() {
  if (rafId) cancelAnimationFrame(rafId)
  SIM.alpha = Math.max(SIM.alpha, 0.3)
  rafId = requestAnimationFrame(loop)
}
function reheat() {
  SIM.alpha = Math.max(SIM.alpha, 0.3)
  if (!rafId) rafId = requestAnimationFrame(loop)
}
function loop() {
  tick()
  rafId = SIM.alpha > SIM.alphaMin ? requestAnimationFrame(loop) : null
}
function tick() {
  const ns = nodes.value
  const es = edges.value
  const n = ns.length
  if (!n) return
  SIM.alpha += (0 - SIM.alpha) * SIM.alphaDecay

  const fx = new Float64Array(n)
  const fy = new Float64Array(n)
  const a = SIM.alpha

  // 向心力（朝原点）
  for (let i = 0; i < n; i++) {
    fx[i] += (0 - ns[i].x) * SIM.gravK * a
    fy[i] += (0 - ns[i].y) * SIM.gravK * a
  }
  // 斥力 O(n^2)
  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      let dx = ns[i].x - ns[j].x
      let dy = ns[i].y - ns[j].y
      let d2 = dx * dx + dy * dy
      if (d2 < SIM.minDist * SIM.minDist) {
        d2 = SIM.minDist * SIM.minDist
        dx = (Math.random() - 0.5) * SIM.minDist
        dy = (Math.random() - 0.5) * SIM.minDist
      }
      const d = Math.sqrt(d2)
      const f = (SIM.kRep / d2) * a
      const ux = dx / d
      const uy = dy / d
      fx[i] += f * ux
      fy[i] += f * uy
      fx[j] -= f * ux
      fy[j] -= f * uy
    }
  }
  // 弹簧（沿边）
  for (const e of es) {
    const si = nodeById.get(e.source)
    const ti = nodeById.get(e.target)
    if (!si || !ti) continue
    let dx = ti.x - si.x
    let dy = ti.y - si.y
    let d = Math.sqrt(dx * dx + dy * dy) || 0.01
    const f = SIM.springK * (d - SIM.restLen) * a
    const ux = dx / d
    const uy = dy / d
    // 对两端施加相向拉力（累加为速度增量）
    fxForce(si, f * ux, f * uy)
    fxForce(ti, -f * ux, -f * uy)
  }
  // 积分
  const keep = 1 - SIM.friction
  for (let i = 0; i < n; i++) {
    const node = ns[i]
    if (node.fx != null) {
      node.x = node.fx
      node.y = node.fy
      node.vx = 0
      node.vy = 0
      continue
    }
    node.vx = (node.vx + fx[i]) * keep
    node.vy = (node.vy + fy[i]) * keep
    node.x += node.vx
    node.y += node.vy
  }
}
// 弹簧力累加（直接改速度，等价于力 * dt=1）
function fxForce(node, fxv, fyv) {
  node.vx += fxv
  node.vy += fyv
}

// ---------- 交互：拖拽 / 平移 / 缩放 ----------
function clientToGraph(clientX, clientY) {
  const rect = svgRef.value.getBoundingClientRect()
  return {
    x: (clientX - rect.left - view.tx) / view.scale,
    y: (clientY - rect.top - view.ty) / view.scale,
  }
}
function onNodePointerDown(e, node) {
  e.stopPropagation()
  e.preventDefault()
  dragging = { type: 'node', id: node.id, moved: false, sx: e.clientX, sy: e.clientY }
  window.addEventListener('pointermove', onPointerMove)
  window.addEventListener('pointerup', onPointerUp)
}
function onBgPointerDown(e) {
  if (e.button !== 0) return
  dragging = { type: 'pan', sx: e.clientX, sy: e.clientY, tx0: view.tx, ty0: view.ty }
  window.addEventListener('pointermove', onPointerMove)
  window.addEventListener('pointerup', onPointerUp)
}
function onPointerMove(e) {
  if (!dragging) return
  if (dragging.type === 'pan') {
    view.tx = dragging.tx0 + (e.clientX - dragging.sx)
    view.ty = dragging.ty0 + (e.clientY - dragging.sy)
  } else {
    const g = clientToGraph(e.clientX, e.clientY)
    const node = nodeById.get(dragging.id)
    if (node) {
      node.fx = g.x
      node.fy = g.y
    }
    if (Math.abs(e.clientX - dragging.sx) > 3 || Math.abs(e.clientY - dragging.sy) > 3) {
      dragging.moved = true
    }
    reheat()
  }
}
function onPointerUp() {
  window.removeEventListener('pointermove', onPointerMove)
  window.removeEventListener('pointerup', onPointerUp)
  if (dragging && dragging.type === 'node') {
    const node = nodeById.get(dragging.id)
    if (node) {
      node.fx = null
      node.fy = null
    }
    if (!dragging.moved) {
      router.push(`/devices/${dragging.id}`)
    }
  }
  dragging = null
}
function onWheel(e) {
  const rect = svgRef.value.getBoundingClientRect()
  const cx = e.clientX - rect.left
  const cy = e.clientY - rect.top
  const factor = e.deltaY < 0 ? 1.12 : 1 / 1.12
  zoomAt(cx, cy, factor)
}
function zoomAt(cx, cy, factor) {
  const ns = Math.min(4, Math.max(0.2, view.scale * factor))
  const gx = (cx - view.tx) / view.scale
  const gy = (cy - view.ty) / view.scale
  view.tx = cx - gx * ns
  view.ty = cy - gy * ns
  view.scale = ns
}
function zoomBy(factor) {
  zoomAt(size.w / 2, size.h / 2, factor)
}
function reLayout() {
  const r = Math.min(size.w, size.h) * 0.4
  nodes.value.forEach((n) => {
    n.x = (Math.random() - 0.5) * 2 * r
    n.y = (Math.random() - 0.5) * 2 * r
    n.vx = 0
    n.vy = 0
    n.fx = null
    n.fy = null
  })
  view.tx = size.w / 2
  view.ty = size.h / 2
  view.scale = 1
  startSim()
}
function fit() {
  if (!nodes.value.length) return
  let minX = Infinity,
    minY = Infinity,
    maxX = -Infinity,
    maxY = -Infinity
  nodes.value.forEach((n) => {
    minX = Math.min(minX, n.x)
    minY = Math.min(minY, n.y)
    maxX = Math.max(maxX, n.x)
    maxY = Math.max(maxY, n.y)
  })
  const pad = 70
  const gw = maxX - minX || 1
  const gh = maxY - minY || 1
  const s = Math.min((size.w - 2 * pad) / gw, (size.h - 2 * pad) / gh, 2)
  view.scale = Math.max(0.2, s)
  view.tx = size.w / 2 - ((minX + maxX) / 2) * view.scale
  view.ty = size.h / 2 - ((minY + maxY) / 2) * view.scale
}

// ---------- 悬停 ----------
function onHover(id) {
  hoveredId.value = id
}
function onLeave() {
  hoveredId.value = null
}

// ---------- 尺寸测量 ----------
function measure() {
  const el = svgRef.value
  if (!el) return
  const r = el.getBoundingClientRect()
  if (r.width) size.w = r.width
  if (r.height) size.h = r.height
}

onMounted(async () => {
  await nextTick()
  measure()
  ro = new ResizeObserver(() => measure())
  if (svgRef.value) ro.observe(svgRef.value)
  loadRooms()
  loadTopology()
})
onBeforeUnmount(() => {
  if (rafId) cancelAnimationFrame(rafId)
  if (ro) ro.disconnect()
  window.removeEventListener('pointermove', onPointerMove)
  window.removeEventListener('pointerup', onPointerUp)
})
</script>

<style scoped>
.topo-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.page-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
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
  max-width: 70ch;
}
.toolbar {
  background: oklch(var(--card) / 0.8);
  border: 1px solid oklch(var(--border) / 0.6);
  border-radius: 10px;
  padding: 14px 16px;
  backdrop-filter: blur(8px);
}
.topo-card {
  overflow: hidden;
}
.topo-stage {
  position: relative;
  width: 100%;
  height: 62vh;
  min-height: 460px;
  background:
    radial-gradient(circle at 20% 18%, hsl(var(--primary) / 0.06), transparent 42%),
    radial-gradient(circle at 82% 80%, hsl(var(--primary) / 0.05), transparent 45%),
    oklch(var(--muted) / 0.25);
  background-image:
    linear-gradient(oklch(var(--border) / 0.35) 1px, transparent 1px),
    linear-gradient(90deg, oklch(var(--border) / 0.35) 1px, transparent 1px);
  background-size: 26px 26px, 26px 26px;
}
.topo-center {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 24px;
}
.topo-svg {
  width: 100%;
  height: 100%;
  display: block;
  touch-action: none;
  cursor: grab;
}
.topo-svg:active {
  cursor: grabbing;
}
.topo-node {
  cursor: pointer;
  transition: opacity 0.18s ease;
}
.topo-node circle {
  transition: stroke-width 0.15s ease;
}
.topo-node--dim {
  opacity: 0.22;
}
.topo-label {
  font-size: 11px;
  fill: hsl(var(--foreground));
  paint-order: stroke;
  stroke: hsl(var(--card));
  stroke-width: 3px;
  stroke-linejoin: round;
  pointer-events: none;
  user-select: none;
}
.topo-edge--active {
  filter: drop-shadow(0 0 3px currentColor);
}
/* 玻璃浮层通用 */
.glass-soft {
  background: hsl(var(--popover) / 0.82);
  backdrop-filter: blur(14px) saturate(150%);
  -webkit-backdrop-filter: blur(14px) saturate(150%);
  border: 1px solid hsl(var(--border));
  box-shadow: 0 16px 40px -18px rgba(15, 23, 42, 0.4);
  border-radius: 12px;
}
.topo-info {
  position: absolute;
  top: 14px;
  left: 14px;
  width: 220px;
  padding: 10px 12px;
}
.topo-info-close {
  display: inline-flex;
  color: hsl(var(--muted-foreground));
}
.topo-info-close:hover {
  color: hsl(var(--foreground));
}
.chip {
  display: inline-flex;
  align-items: center;
  padding: 1px 8px;
  border-radius: 9999px;
  font-size: 11px;
  font-weight: 600;
}
.topo-zoom {
  position: absolute;
  right: 14px;
  bottom: 14px;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 6px;
  gap: 4px;
}
.topo-zoom-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 8px;
  color: hsl(var(--foreground));
  transition: background 0.15s ease;
}
.topo-zoom-btn:hover {
  background: hsl(var(--accent));
}
.topo-zoom-val {
  font-size: 11px;
  color: hsl(var(--muted-foreground));
  font-variant-numeric: tabular-nums;
}
.topo-legend {
  position: absolute;
  left: 14px;
  bottom: 14px;
  padding: 10px 12px;
  max-width: 240px;
}
.legend-title {
  font-size: 11px;
  font-weight: 600;
  color: hsl(var(--muted-foreground));
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.legend-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px 12px;
  margin-top: 5px;
}
.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: hsl(var(--foreground));
}
.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 9999px;
  flex-shrink: 0;
}
.legend-line {
  width: 14px;
  height: 3px;
  border-radius: 2px;
  flex-shrink: 0;
}
.legend-ring {
  width: 11px;
  height: 11px;
  border-radius: 9999px;
  border: 2px solid;
  flex-shrink: 0;
}
.legend-text {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.18s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
