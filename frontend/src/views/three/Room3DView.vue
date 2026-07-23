<template>
  <div class="relative w-full" :class="{ 'is-fullscreen': fullscreen }" :style="{ height: fullscreen ? '100vh' : 'calc(100vh - 8.5rem)' }">
    <!-- 3D 画布 -->
    <div ref="canvasWrap" class="three-canvas-wrap">
      <div v-if="loading" class="three-loading">正在加载机房三维场景…</div>
    </div>

    <!-- 顶部：居中图标控制条（选中机房 / 大屏(退出) / 视角重置） -->
    <div class="absolute top-3 left-1/2 -translate-x-1/2 z-30 pointer-events-auto">
      <div class="glass-panel flex items-center gap-1 rounded-2xl px-1.5 py-1.5 shadow-lg shadow-black/20">
        <!-- 选中机房 -->
        <Select v-model="roomId" class="w-[150px]" @update:model-value="onRoomChange">
          <SelectTrigger placeholder="选中机房" />
          <SelectContent>
            <SelectItem v-for="r in rooms" :key="r.id" :value="r.id">{{ r.name }}（{{ r.code }}）</SelectItem>
          </SelectContent>
        </Select>

        <div class="mx-1 h-5 w-px bg-border/50"></div>

        <!-- 大屏 / 退出大屏 -->
        <Tooltip v-if="!fullscreen" side="bottom">
          <template #trigger>
            <button
              type="button"
              class="flex h-9 w-9 items-center justify-center rounded-xl text-muted-foreground transition-colors hover:text-foreground hover:bg-accent"
              @click="goBigScreen"
            ><Monitor class="h-5 w-5" /></button>
          </template>
          大屏
        </Tooltip>
        <Tooltip v-else side="bottom">
          <template #trigger>
            <button
              type="button"
              class="flex h-9 w-9 items-center justify-center rounded-xl text-muted-foreground transition-colors hover:text-foreground hover:bg-accent"
              @click="backToRooms"
            ><ArrowLeft class="h-5 w-5" /></button>
          </template>
          退出大屏
        </Tooltip>

        <!-- 视角重置 -->
        <Tooltip side="bottom">
          <template #trigger>
            <button
              type="button"
              class="flex h-9 w-9 items-center justify-center rounded-xl text-muted-foreground transition-colors hover:text-foreground hover:bg-accent"
              @click="resetView"
            ><RotateCcw class="h-5 w-5" /></button>
          </template>
          视角重置
        </Tooltip>
      </div>
    </div>

    <!-- 左上角机房信息（修复此前消失的问题） -->
    <div v-if="room" class="room-info-panel absolute top-3 left-3 z-30 pointer-events-auto">
      <div class="glass-panel min-w-[180px] px-3 py-2.5">
        <div class="flex items-center gap-2">
          <span class="h-2.5 w-2.5 shrink-0 rounded-full" :style="{ backgroundColor: roomStatusColor }"></span>
          <span class="truncate text-sm font-semibold text-foreground">{{ room.name }}</span>
        </div>
        <div class="mt-0.5 text-xs text-muted-foreground">{{ room.code }}</div>
        <div class="mt-2 flex items-center gap-4 text-xs text-muted-foreground">
          <span>机柜 <b class="font-semibold text-foreground">{{ racks.length }}</b></span>
          <span>设备 <b class="font-semibold text-foreground">{{ allDevices.length }}</b></span>
        </div>
      </div>
    </div>

    <!-- 设备详情面板（选中设备后显示）：含可滚动接口列表与关联链路（对应 3D 动态线缆） -->
    <div
      v-if="selectedDeviceDetail"
      class="device-detail-panel absolute left-3 top-24 z-30 w-72 pointer-events-auto flex max-h-[74vh] flex-col"
    >
      <div class="glass-panel flex min-h-0 flex-1 flex-col p-3">
        <div class="mb-2 flex items-start justify-between gap-2">
          <div class="min-w-0">
            <div class="flex items-center gap-2">
              <span class="h-2.5 w-2.5 shrink-0 rounded-full" :style="{ backgroundColor: devStatusColor }"></span>
              <span class="truncate text-sm font-semibold text-foreground">{{ selectedDeviceDetail.device.name }}</span>
            </div>
            <div class="mt-0.5 text-[11px] text-muted-foreground">
              {{ devTypeLabel }}<template v-if="selectedDeviceDetail.device.model"> · {{ selectedDeviceDetail.device.model }}</template>
            </div>
          </div>
          <button class="rounded p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground" @click="clearDeviceSelection">
            <X class="h-4 w-4" />
          </button>
        </div>

        <!-- 关键信息 -->
        <div class="grid grid-cols-[3.5rem_1fr] gap-x-2 gap-y-1 text-[11px] text-muted-foreground">
          <span class="text-muted-foreground/70">IP</span><span class="truncate">{{ selectedDeviceDetail.device.ip_address || '—' }}</span>
          <span class="text-muted-foreground/70">机柜</span>
          <span class="truncate">
            {{ selectedDeviceDetail.device.current_rack_name || '未上架' }}
            <template v-if="selectedDeviceDetail.device.current_start_u != null"> · {{ selectedDeviceDetail.device.current_start_u }}U~{{ devUEnd }}U</template>
          </span>
        </div>

        <!-- 接口列表（交换机接口过多时可滚动，避免面板过长） -->
        <div class="mt-3 flex min-h-0 flex-1 flex-col">
          <div class="gp-title mb-1 flex items-center gap-1.5 text-[11px]">
            <Network class="h-3.5 w-3.5 text-brand-400" /> 接口（{{ selectedDeviceDetail.interfaces.length }}）
          </div>
          <div class="device-iface-scroll max-h-44 overflow-y-auto pr-1">
            <div
              v-for="p in selectedDeviceDetail.interfaces"
              :key="p.id"
              class="flex items-center justify-between gap-2 rounded px-2 py-1 text-[11px] hover:bg-accent"
            >
              <span class="truncate text-foreground/80">{{ p.name }}</span>
              <span class="flex shrink-0 items-center gap-1.5">
                <span class="text-muted-foreground">{{ INTERFACE_TYPE_LABELS[p.interface_type] || p.interface_type }}/{{ p.speed }}</span>
                <span class="h-1.5 w-1.5 rounded-full" :style="{ backgroundColor: INTERFACE_STATUS_COLORS[p.status] || '#909399' }"></span>
              </span>
            </div>
            <div v-if="!selectedDeviceDetail.interfaces.length" class="py-3 text-center text-muted-foreground/70">无接口</div>
          </div>
        </div>

        <!-- 关联链路（与 3D 动态线缆一一对应） -->
        <div class="mt-2">
          <div class="gp-title mb-1 flex items-center gap-1.5 text-[11px]">
            <Cable class="h-3.5 w-3.5 text-brand-400" /> 关联链路（{{ selectedDeviceDetail.links.length }}）
          </div>
          <div class="max-h-32 overflow-y-auto pr-1">
            <div v-for="(lk, i) in selectedDeviceDetail.links" :key="i" class="rounded px-2 py-1 text-[11px] hover:bg-accent">
              <div class="flex items-center gap-1.5">
                <span
                  class="rounded px-1 py-0.5 text-[10px] font-medium"
                  :style="{ backgroundColor: (LINK_MEDIUM_COLORS[lk.medium] || '#888') + '33', color: LINK_MEDIUM_COLORS[lk.medium] || '#ccc' }"
                >{{ LINK_MEDIUM_LABELS[lk.medium] || lk.medium }}</span>
                <span v-if="lk.peerName" class="truncate text-foreground/80">{{ lk.peerName }}</span>
                <span v-else class="truncate text-muted-foreground">{{ lk.peerLabel || '外部' }}</span>
              </div>
              <div class="mt-0.5 truncate text-muted-foreground/70">{{ lk.source_interface }} → {{ lk.target_interface }}</div>
            </div>
            <div v-if="!selectedDeviceDetail.links.length" class="py-3 text-center text-muted-foreground/70">无关联链路</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 右侧面板 -->
    <div class="absolute top-20 right-3 w-60 pointer-events-auto">
      <div class="glass-panel p-3">
        <!-- 标签切换：设备（默认，点选查看详情与链路）/ 机柜（跳转三维详情） -->
        <div class="flex mb-2 rounded-lg bg-accent/50 p-0.5 text-[11px]">
          <button
            type="button"
            class="flex-1 rounded-md py-1 font-medium transition-colors"
            :class="panelTab === 'device' ? 'bg-brand-500 text-white shadow' : 'text-muted-foreground hover:text-foreground'"
            @click="panelTab = 'device'"
          >设备</button>
          <button
            type="button"
            class="flex-1 rounded-md py-1 font-medium transition-colors"
            :class="panelTab === 'rack' ? 'bg-brand-500 text-white shadow' : 'text-muted-foreground hover:text-foreground'"
            @click="panelTab = 'rack'"
          >机柜</button>
        </div>

        <!-- 设备列表：按机柜分组，点击设备即在 3D 中选中并展示详情/链路 -->
        <template v-if="panelTab === 'device'">
          <div class="gp-title text-xs mb-2 flex items-center gap-2">
            <Cpu class="w-3.5 h-3.5 text-brand-400" /> 设备列表（{{ allDevices.length }}）
          </div>
          <div class="space-y-1 max-h-[56vh] overflow-y-auto pr-0.5">
            <div v-for="grp in racksWithDevices" :key="grp.rack.id" class="rounded-lg">
              <button
                type="button"
                class="w-full text-left rounded-lg px-2 py-1.5 transition-colors hover:bg-accent flex items-center justify-between gap-2"
                :class="{ 'bg-accent ring-1 ring-brand-400/40': hoveredRackId === grp.rack.id }"
                @mouseenter="onRackHover(grp.rack, $event, true)"
                @mouseleave="onRackHover(grp.rack, $event, false)"
                @click="toggleRackGroup(grp.rack.id)"
              >
                <span class="min-w-0">
                  <span class="block text-foreground text-[12px] font-medium truncate">{{ grp.rack.name }}</span>
                  <span class="block text-[11px] gp-sub truncate">{{ grp.devices.length }} 台设备</span>
                </span>
                <span class="flex items-center gap-1.5 shrink-0">
                  <StatusBadge type="rack" :value="grp.rack.status" />
                  <component :is="isRackGroupExpanded(grp.rack.id) ? ChevronDown : ChevronRight" class="w-3.5 h-3.5 text-muted-foreground" />
                </span>
              </button>
              <div v-if="isRackGroupExpanded(grp.rack.id)" class="ml-3 mt-1 space-y-1 border-l border-border pl-2">
                <button
                  v-for="d in grp.devices"
                  :key="d.id"
                  type="button"
                  class="w-full text-left rounded-md px-2 py-1 text-[11px] transition-colors hover:bg-accent flex items-center justify-between gap-2"
                  :class="{ 'bg-accent ring-1 ring-brand-400/30': selectedDeviceId === d.id || hoveredDeviceId === d.id }"
                  @mouseenter="onDeviceHover(d, $event, true)"
                  @mouseleave="onDeviceHover(d, $event, false)"
                  @click="selectDeviceFromList(d.id)"
                >
                  <span class="min-w-0">
                    <span class="block text-foreground/80 truncate">{{ d.name }}</span>
                    <span class="block gp-sub truncate">{{ DEVICE_TYPE_LABELS[d.device_type] || d.device_type }} · {{ d.current_start_u }}U~{{ d.current_start_u + (d.u_height || 1) - 1 }}U</span>
                  </span>
                  <StatusBadge type="device" :value="d.status" />
                </button>
              </div>
            </div>
            <EmptyState v-if="!allDevices.length" title="本机房暂无设备" />
          </div>
          <p class="gp-sub text-[11px] mt-2 leading-relaxed">
            提示：点击设备即可在 3D 中高亮定位，并展示接口与关联链路（动态线缆）；也可直接点选 3D 场景中的设备。
          </p>
        </template>

        <!-- 机柜列表：单击选中高亮（与设备高亮同存），双击或「进入」按钮跳转三维详情 -->
        <template v-else>
          <div class="gp-title text-xs mb-2 flex items-center gap-2">
            <Crosshair class="w-3.5 h-3.5 text-brand-400" /> 机柜列表（{{ racks.length }}）
          </div>
          <div class="space-y-1 max-h-[56vh] overflow-y-auto pr-0.5">
            <div
              v-for="r in racks"
              :key="r.id"
              type="button"
              class="w-full text-left rounded-lg px-2 py-1.5 transition-colors hover:bg-accent flex items-center justify-between gap-2 cursor-pointer"
              :class="{ 'bg-accent ring-1 ring-brand-400/40': hoveredRackId === r.id }"
              @mouseenter="onRackHover(r, $event, true)"
              @mouseleave="onRackHover(r, $event, false)"
              @click="goRack(r)"
            >
              <span class="min-w-0">
                <span class="block text-foreground text-[12px] font-medium truncate">{{ r.name }}</span>
                <span class="block text-[11px] gp-sub truncate">{{ r.column_code }} / {{ r.code }}</span>
              </span>
              <div class="flex items-center gap-1.5 shrink-0">
                <StatusBadge type="rack" :value="r.status" />
              </div>
            </div>
            <EmptyState v-if="!racks.length" title="暂无机柜" />
          </div>
          <p class="gp-sub text-[11px] mt-2 leading-relaxed">
            提示：单击机柜进入其三维详情 · 单击设备查看高亮与链路。
          </p>
        </template>
      </div>
    </div>

    <!-- 初始化失败兜底（如 WebGL 上下文不可用） -->
    <div v-if="error" class="absolute inset-0 flex items-center justify-center pointer-events-auto">
      <div class="glass-panel p-6 max-w-md text-center">
        <div class="gp-title mb-2">无法显示三维视图</div>
        <p class="gp-sub text-sm">{{ error }}</p>
        <Button class="mt-4" @click="backToRooms">返回机房总览</Button>
      </div>
    </div>

    <!-- 底部操作提示 -->
    <div class="absolute bottom-2.5 left-1/2 -translate-x-1/2 pointer-events-none">
      <div class="glass-panel px-3 py-1 text-[11px] gp-sub">
        拖拽旋转 · 滚轮缩放 · W/S 前后移动 · A/D 左右平移 · 单击机柜进入详情
      </div>
    </div>

    <!-- 缩放百分比实时显示（右下角） -->
    <div class="absolute bottom-2.5 right-3 z-30 pointer-events-auto">
      <div class="glass-panel flex items-center gap-1.5 px-2.5 py-1.5 text-xs">
        <span class="text-muted-foreground">缩放</span>
        <span class="min-w-[3rem] text-right font-semibold tabular-nums text-foreground">{{ zoomPercent }}%</span>
        <button
          type="button"
          class="ml-0.5 flex h-6 w-6 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
          title="重置视角"
          @click="resetView"
        ><RotateCcw class="h-3.5 w-3.5" /></button>
      </div>
    </div>

    <!-- 悬浮提示 -->
    <div v-show="tooltipVisible" ref="tooltip" class="three-tooltip" :style="tooltipStyle" />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useTheme } from '@/composables/useTheme'
import { RotateCcw, Crosshair, Cpu, ChevronRight, ChevronDown, Monitor, ArrowLeft, X, Network, Cable } from 'lucide-vue-next'
import * as THREE from 'three'
import { Line2 } from 'three/examples/jsm/lines/Line2.js'
import { LineGeometry } from 'three/examples/jsm/lines/LineGeometry.js'
import { LineMaterial } from 'three/examples/jsm/lines/LineMaterial.js'
import roomApi from '@/api/room'
import rackApi from '@/api/rack'
import deviceApi from '@/api/device'
import interfaceApi from '@/api/interface'
import http from '@/api/http'
import { createEngine, makeRackLabel, makeBookmarkLabel, makeCanvasTexture } from '@/utils/three-setup'
import {
  buildCabinet,
  buildDevice,
  setDevicePosition,
  highlightCabinet,
  restoreCabinet,
  findCabinetGroup,
  findDeviceGroup,
  setDeviceSelected,
  setDeviceEmissive,
  clearDeviceEmissive,
  RACK_W,
  RACK_D,
  U_H,
  PLINTH_H,
} from '@/utils/device-models'
import StatusBadge from '@/components/common/StatusBadge.vue'
import {
  RACK_STATUS_COLORS,
  RACK_STATUS_LABELS,
  DEVICE_TYPE_LABELS,
  DEVICE_STATUS_LABELS,
  DEVICE_STATUS_COLORS,
  DEVICE_TYPE_COLORS,
  INTERFACE_TYPE_LABELS,
  INTERFACE_STATUS_COLORS,
  LINK_MEDIUM_LABELS,
  LINK_MEDIUM_COLORS,
} from '@/utils/constants'
import { escapeHtml } from '@/utils/escape'
import Button from '@/components/ui/button.vue'
import Select from '@/components/ui/select.vue'
import SelectTrigger from '@/components/ui/select-trigger.vue'
import SelectContent from '@/components/ui/select-content.vue'
import SelectItem from '@/components/ui/select-item.vue'
import EmptyState from '@/components/ui/empty-state.vue'
import Tooltip from '@/components/ui/tooltip.vue'

const props = defineProps({
  // 全屏模式：由大屏页（/bigscreen）嵌入时传 true，根容器撑满视口
  fullscreen: { type: Boolean, default: false },
})

const route = useRoute()
const router = useRouter()

const viewMode = ref('room') // 固定机房总览模式（已移除机柜总览/设备总览切换）
const panelTab = ref('device') // 右侧面板标签：'device' 设备列表（默认，可点选查看链路）/ 'rack' 机柜列表（跳转详情）
const rooms = ref([])
const roomId = ref(route.query.room || '')
const room = ref(null)
const racks = ref([])
const stats = ref(null)
const loading = ref(false)
const deviceCountCache = ref({})
const rackDevices = ref({}) // rackId -> [device]
const selectedDeviceId = ref(null)
const selectedDeviceDetail = ref(null) // { device, interfaces, links }

const canvasWrap = ref(null)
const tooltip = ref(null)
const tooltipVisible = ref(false)
const tooltipStyle = ref({ left: '0px', top: '0px' })
const error = ref('')

const hoveredRackId = ref(null)
const hoveredDeviceId = ref(null)
const expandedGroups = ref({}) // 设备总览：机柜分组展开状态

// ── 主题切换：3D 场景随暗色/亮色模式联动 ──
const { isDark } = useTheme()

// 主题敏感材质引用（buildRoomScene 中赋值，供 apply3DTheme 复用）
let themeMaterials = null // { wallMat, wallEdgeMat, floorMat, hemisphere, ambient, key, fill }

function apply3DTheme(dark) {
  if (!engine) return
  const scene = engine.scene
  // 背景与雾
  const bg = dark ? 0x0b1220 : 0xe8ecf4
  scene.background.setHex(bg)
  if (scene.fog) { scene.fog.color.setHex(bg); scene.fog.far = dark ? 220 : 300 }
  // 材质
  if (themeMaterials) {
    const { wallMat, wallEdgeMat, floorMat, hemisphere, ambient, key, fill } = themeMaterials
    if (wallMat) { wallMat.color.setHex(dark ? 0x16223c : 0xd1d9e6); wallMat.opacity = dark ? 0.16 : 0.22 }
    if (wallEdgeMat) { wallEdgeMat.color.setHex(dark ? 0x2b3c5e : 0x8899b4); wallEdgeMat.emissive.setHex(dark ? 0x16335c : 0x4a5d7c); wallEdgeMat.emissiveIntensity = dark ? 0.5 : 0.25 }
    if (floorMat) floorMat.color.setHex(dark ? 0xffffff : 0xf0f2f5)
    // 灯光强度：亮模式更明亮柔和，暗模式偏深邃
    if (hemisphere) { hemisphere.intensity = dark ? 0.55 : 0.75 }
    if (ambient) ambient.intensity = dark ? 0.22 : 0.38
    if (key) key.intensity = dark ? 1.15 : 1.35
    if (fill) fill.intensity = dark ? 0.4 : 0.55
  }
  // CSS 画布背景渐变（与 Three.js 背景协调）
  if (canvasWrap.value) {
    canvasWrap.value.style.background = dark
      ? 'radial-gradient(120% 120% at 50% 0%, #16203a 0%, #0b1220 55%, #070b14 100%)'
      : 'radial-gradient(120% 120% at 50% 0%, #c5d1e6 0%, #a8b8d0 55%, #8e9db5 100%)'
  }
}

const allDevices = computed(() => flattenDevices())
// 左上角机房信息面板用的状态色
const roomStatusColor = computed(() => RACK_STATUS_COLORS[room.value?.status] || '#22d3ee')
const racksWithDevices = computed(() =>
  racks.value.map((r) => ({ rack: r, devices: rackDevices.value[r.id] || [] })).filter((g) => g.devices.length)
)

// 设备详情面板派生字段
const devStatusColor = computed(() => {
  const d = selectedDeviceDetail.value?.device
  return d ? DEVICE_STATUS_COLORS[d.status] || '#909399' : '#909399'
})
const devTypeLabel = computed(() => {
  const d = selectedDeviceDetail.value?.device
  return d ? DEVICE_TYPE_LABELS[d.device_type] || d.device_type || '' : ''
})
const devUEnd = computed(() => {
  const d = selectedDeviceDetail.value?.device
  if (!d || d.current_start_u == null) return null
  return d.current_start_u + (d.u_height || 1) - 1
})
function isRackGroupExpanded(id) {
  return !!expandedGroups.value[id]
}
function toggleRackGroup(id) {
  expandedGroups.value = { ...expandedGroups.value, [id]: !expandedGroups.value[id] }
}

let engine = null
let disposed = false // 卸载标记：防止异步初始化在组件已卸载后创建 WebGL 上下文
let worldGroup = null
// 选中设备的关联链路 3D 动态线缆：cables = [{curve, spheres, baseOffsets, speed}]
const cables = []
let cablesGroup = null
let cableClock = 0
const zoomPercent = ref(100) // 实时缩放百分比（100% = 取景适配距离）
let zoomRefDistance = 40 // 缩放 100% 参考距离（frameRoomView 取景距离）
const _up = new THREE.Vector3(0, 1, 0) // 复用：箭头朝向基准轴(+Y)
const _tan = new THREE.Vector3() // 复用：曲线切线
const rackGroups = [] // 机房总览：机柜 Group（拾取）
const deviceMeshes = [] // 设备总览：独立设备 Group（拾取）
const raycaster = new THREE.Raycaster()
const pointer = new THREE.Vector2()
let hoveredGroup = null // 悬停机柜
let hoveredDeviceMesh = null // 悬停设备
let downPos = null

const statusColor = (s) => RACK_STATUS_COLORS[s] || '#909399'

// 机房布局常量：过道加宽，避免查看具体机柜时被相邻列遮挡。
const AISLE = 6.0
const WALL_H = 8.5

// 机房布局：优先使用平面图网格坐标(grid_row/grid_col)渲染，使 3D 与 2D 平面图
// 完全一致（同一行 grid_row 的机柜沿 X 紧邻排成机柜行，行与行之间(z)留出过道）；
// 缺失网格坐标时回退到按列编号 column_code 分组推导（兼容历史数据）。
function computeRackLayout(ra) {
  const allGrid = ra.length > 0 && ra.every((r) => r.grid_row != null && r.grid_col != null)
  if (allGrid) {
    let maxR = 0
    let maxC = 0
    ra.forEach((r) => {
      maxR = Math.max(maxR, r.grid_row)
      maxC = Math.max(maxC, r.grid_col)
    })
    const cols = maxC + 1
    const rows = maxR + 1
    // 同一行(同 grid_row)的机柜沿 X 紧邻排布，行与行之间沿 Z 留出过道。
    const xPitch = RACK_W + 0.2
    const zPitch = RACK_D + AISLE
    const centerC = (cols - 1) / 2
    const centerR = (rows - 1) / 2
    const map = {}
    ra.forEach((r) => {
      const x = (r.grid_col - centerC) * xPitch
      const z = (r.grid_row - centerR) * zPitch
      map[r.id] = { x, z, rot: 0 }
    })
    // 走廊/过道位于行间（Z 方向），每对相邻行之间一条走廊。
    // 同一行的多列机柜共享同一条面向它们的过道，不会在列间重复绘制走廊标签。
    const rowZs = []
    for (let r = 0; r < rows; r++) rowZs.push((r - centerR) * zPitch)
    const aisleZs = [] // 行间走廊的 Z 坐标（行数 N → N-1 条走廊）
    for (let i = 0; i < rowZs.length - 1; i++) aisleZs.push((rowZs[i] + rowZs[i + 1]) / 2)
    const colXs = []
    for (let c = 0; c < cols; c++) colXs.push((c - centerC) * xPitch)
    const spanX = cols * xPitch - 0.2
    const spanZ = rows * zPitch - AISLE
    return { map, cols, rows, colXs, aisleZs, spanX, spanZ, colPitchX: xPitch }
  }
  // 回退：按列编号 column_code 分组（兼容无网格坐标的历史数据）
  const groups = {} // column_code -> [{rack, codeNum}]
  ra.forEach((rack) => {
    const col = rack.column_code || '?'
    const codeNum = parseInt(String(rack.code).replace(/\D/g, ''), 10) || 0
    if (!groups[col]) groups[col] = []
    groups[col].push({ rack, codeNum })
  })
  const colKeys = Object.keys(groups).sort()
  const map = {}
  let maxDepth = 0
  const colPitchX = RACK_W + AISLE // 列间（含过道）
  const colXs = [] // 每列机柜中心 X
  colKeys.forEach((ck, colIdx) => {
    const items = groups[ck].slice().sort((a, b) => a.codeNum - b.codeNum)
    maxDepth = Math.max(maxDepth, items.length)
    const x = (colIdx - (colKeys.length - 1) / 2) * colPitchX
    colXs.push(x)
    const n = items.length
    items.forEach((it, i) => {
      const z = (i - (n - 1) / 2) * RACK_D // 同列内沿 Z 紧密排布
      map[it.rack.id] = { x, z, rot: 0 }
    })
  })
  // 回退模式：列间已有间距，但行间无明确走廊概念，不渲染走廊标签。
  const aisleZs = []
  const cols = colKeys.length
  const rows = maxDepth
  const spanX = cols * colPitchX - AISLE
  const spanZ = rows * RACK_D
  return { map, cols, rows, colXs, aisleZs, spanX, spanZ, colPitchX }
}

// 程序化贴图：抬高地板瓷砖（深底 + 浅色瓷砖缝）。
function makeFloorTexture(repeatX, repeatZ) {
  return makeCanvasTexture(
    (ctx, w, h) => {
      ctx.fillStyle = '#0c1422'
      ctx.fillRect(0, 0, w, h)
      ctx.strokeStyle = 'rgba(130,150,180,0.30)'
      ctx.lineWidth = 4
      ctx.strokeRect(3, 3, w - 6, h - 6)
      ctx.strokeStyle = 'rgba(80,100,130,0.18)'
      ctx.lineWidth = 1
      ctx.strokeRect(14, 14, w - 28, h - 28)
    },
    128,
    128,
    [repeatX, repeatZ]
  )
}

// 走廊「走廊」字样贴图：透明底、teal 文字 + 方向箭头，用于「涂刷」在地面（非悬浮）。
function makeCorridorTextTexture() {
  return makeCanvasTexture(
    (ctx, w, h) => {
      ctx.clearRect(0, 0, w, h)
      ctx.fillStyle = 'rgba(94,234,212,0.9)'
      ctx.font = 'bold 150px "PingFang SC","Microsoft YaHei",sans-serif'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText('走廊', w / 2, h / 2)
      // 指向走廊走向（X 方向）的箭头
      ctx.strokeStyle = 'rgba(94,234,212,0.6)'
      ctx.lineWidth = 9
      ctx.beginPath()
      ctx.moveTo(w * 0.06, h * 0.5)
      ctx.lineTo(w * 0.9, h * 0.5)
      ctx.moveTo(w * 0.8, h * 0.36)
      ctx.lineTo(w * 0.95, h * 0.5)
      ctx.lineTo(w * 0.8, h * 0.64)
      ctx.stroke()
    },
    768,
    256
  )
}

// 走廊/过道地面引导带：半透明色带 + 方向箭头，文字以「涂刷」方式附着地面（非悬浮）。
function addCorridorGuides(layout, floorWidth) {
  const { aisleZs } = layout
  if (!aisleZs || aisleZs.length === 0) return

  const corridorW = Math.max(floorWidth - 4, 2)
  const bandH = AISLE * 0.82
  const corridorMat = new THREE.MeshBasicMaterial({
    color: 0x14b8a6,
    transparent: true,
    opacity: 0.07,
    depthWrite: false,
  })
  const lineMat = new THREE.MeshBasicMaterial({
    color: 0x2dd4bf,
    transparent: true,
    opacity: 0.16,
    depthWrite: false,
  })
  const textTex = makeCorridorTextTexture()
  const textMat = new THREE.MeshBasicMaterial({
    map: textTex,
    transparent: true,
    opacity: 0.72,
    depthWrite: false,
  })

  aisleZs.forEach((z) => {
    // 半透明地面引导带
    const strip = new THREE.Mesh(new THREE.PlaneGeometry(corridorW, bandH), corridorMat)
    strip.rotation.x = -Math.PI / 2
    strip.position.set(0, 0.03, z)
    worldGroup.add(strip)

    // 沿走廊走向（X 方向）的虚线中心线
    const line = new THREE.Mesh(new THREE.PlaneGeometry(corridorW, 0.12), lineMat)
    line.rotation.x = -Math.PI / 2
    line.position.set(0, 0.04, z)
    worldGroup.add(line)

    // 涂刷式「走廊」文字：贴地半透明平面，像印刷在地面上
    const textPlane = new THREE.Mesh(new THREE.PlaneGeometry(bandH * 3, bandH), textMat)
    textPlane.rotation.x = -Math.PI / 2
    textPlane.position.set(0, 0.05, z)
    textPlane.renderOrder = 2
    textPlane.userData.isCorridorText = true
    worldGroup.add(textPlane)
  })
}

async function loadRooms() {
  const d = await roomApi.list({ size: 200 })
  rooms.value = d.items || []
  if (!roomId.value && rooms.value.length) roomId.value = rooms.value[0].id
}

async function loadRoom(id) {
  if (!id) return
  loading.value = true
  try {
    const [r, rk, st] = await Promise.all([
      roomApi.get(id),
      roomApi.racks(id),
      roomApi.stats(id),
    ])
    room.value = r
    racks.value = rk
    stats.value = st
    // 加载每个机柜的设备（用于机房内挂载展示 + 设备总览）
    const devLists = await Promise.all(
      rk.map((rack) => rackApi.devices(rack.id).catch(() => []))
    )
    const map = {}
    const counts = {}
    rk.forEach((rack, i) => {
      map[rack.id] = devLists[i] || []
      counts[rack.id] = (devLists[i] || []).length
    })
    rackDevices.value = map
    deviceCountCache.value = counts
    if (engine) buildScene()
  } finally {
    loading.value = false
  }
}

function buildScene() {
  if (!engine) return

  // 重建前先清空上一批动态线缆（其对象属于旧 worldGroup，将被一并 dispose）
  clearCables()
  if (worldGroup) {
    engine.scene.remove(worldGroup)
    disposeWorld(worldGroup)
  }
  // 清除上一场景残留的 CSS2D 标签 DOM（防止来回切换时机柜名称重复残留）
  if (engine.clearLabels) engine.clearLabels()
  worldGroup = new THREE.Group()
  engine.scene.add(worldGroup)
  rackGroups.length = 0
  deviceMeshes.length = 0
  hoveredGroup = null
  hoveredDeviceMesh = null
  hoveredRackId.value = null
  hoveredDeviceId.value = null

  buildRoomScene()

  // 重建后恢复已选中设备的高亮（描边 + 自发光 + 书签高亮），避免切换场景后丢失
  if (selectedDeviceId.value) {
    const g = deviceMeshes.find((m) => m.userData.id === selectedDeviceId.value)
    if (g) setDeviceSelected(g, true)
    else selectedDeviceId.value = null // 设备已不在当前场景，清除脏选中态
  }

  // 若当前已选中设备，重建其关联链路 3D 线缆
  if (selectedDeviceId.value && selectedDeviceDetail.value) buildCables()
}

// —— 机房总览场景：机柜按真实比例建模、列内无间隙紧密排列、正面朝走廊，内部挂载设备 ——
function buildRoomScene() {
  const room_ = room.value
  const ra = racks.value
  if (!room_ || !ra.length) return

  const { map: layout, cols: colN, rows: rowN, aisleZs } = computeRackLayout(ra)

  const spanX = colN * RACK_W
  const spanZ = rowN * (RACK_D + AISLE) - AISLE
  const floorW = spanX + 12
  const floorD = spanZ + 12
  let maxH = 0

  // 地面（抬高地板瓷砖）
  const repX = Math.max(6, Math.round(floorW / 3))
  const repZ = Math.max(6, Math.round(floorD / 3))
  const floorTex = makeFloorTexture(repX, repZ)
  const floor = new THREE.Mesh(
    new THREE.PlaneGeometry(floorW, floorD),
    new THREE.MeshStandardMaterial({ map: floorTex, color: 0xffffff, roughness: 0.5, metalness: 0.3 })
  )
  floor.rotation.x = -Math.PI / 2
  floor.receiveShadow = true
  worldGroup.add(floor)

  // 走廊/过道指引：半透明地面带 + 方向标签
  addCorridorGuides({ aisleZs }, floorW)

  // 墙体（半透明，营造机房空间感）+ 顶部桥架走线
  const wallT = 0.3
  const wallMat = new THREE.MeshStandardMaterial({
    color: 0x16223c,
    transparent: true,
    opacity: 0.16,
    side: THREE.DoubleSide,
    roughness: 0.9,
  })
  const wallEdgeMat = new THREE.MeshStandardMaterial({ color: 0x2b3c5e, emissive: 0x16335c, emissiveIntensity: 0.5, roughness: 0.6 })
  const mkWall = (w, d, x, z) => {
    const m = new THREE.Mesh(new THREE.BoxGeometry(w, WALL_H, d), wallMat)
    m.position.set(x, WALL_H / 2, z)
    worldGroup.add(m)
    const edge = new THREE.Mesh(new THREE.BoxGeometry(w, 0.12, d), wallEdgeMat)
    edge.position.set(x, WALL_H, z)
    worldGroup.add(edge)
  }
  mkWall(floorW, wallT, 0, -floorD / 2)
  mkWall(floorW, wallT, 0, floorD / 2)
  mkWall(wallT, floorD, -floorW / 2, 0)
  mkWall(wallT, floorD, floorW / 2, 0)

  // 收集主题敏感材质与灯光引用（供 apply3DTheme 切换时复用，避免重建场景）
  const lights = engine.scene.children.filter((c) => c.isLight)
  themeMaterials = {
    wallMat,
    wallEdgeMat,
    floorMat: floor.material,
    hemisphere: lights.find((l) => l.isHemisphereLight),
    ambient: lights.find((l) => l.isAmbientLight),
    key: lights.find((l) => l.isDirectionalLight && l.castShadow),
    fill: lights.find((l) => l.isDirectionalLight && !l.castShadow),
  }
  // 场景建完后立即应用当前主题配色
  apply3DTheme(isDark.value)


  // 机柜：正面无门（直视内部设备），左右/后面为穿孔板遮挡；内部挂载设备；列内无间隙、正面朝走廊。
  ra.forEach((rack) => {
    const { x, z, rot } = layout[rack.id]
    const h = (rack.total_u || 42) * U_H
    maxH = Math.max(maxH, h)

    const sc = new THREE.Color(statusColor(rack.status)).getHex()
    const ratio = rack.total_u ? rack.used_u / rack.total_u : 0

    const g = buildCabinet({
      width: RACK_W,
      depth: RACK_D,
      height: h,
      uHeight: U_H,
      plinthHeight: PLINTH_H,
      totalU: rack.total_u || 42,
      frontDoor: 'none',
      sidePanel: 'perforated',
      showBack: true,
      showRails: true,
      showCasters: true,
      statusColor: sc,
      occupancyRatio: ratio,
    })
    g.position.set(x, 0, z)
    g.rotation.y = rot
    g.userData.rack = rack
    g.userData.id = rack.id

    // 机柜内挂载设备（设备与机柜关联完整呈现）
    const devs = rackDevices.value[rack.id] || []
    devs.forEach((d) => {
      if (d.current_start_u == null || d.u_height == null) return
      const dg = buildDevice(d, {
        uHeight: U_H,
        width: RACK_W * 0.9,
        depth: RACK_D * 0.82,
        height: d.u_height * U_H * 0.92,
      })
      setDevicePosition(dg, d.current_start_u, d.u_height, { uH: U_H, plinthH: PLINTH_H })
      g.add(dg)
      // 同时登记到 deviceMeshes，使总览模式下的设备悬停 / 选中高亮可定位（与设备总览模式共用同一注册表）
      deviceMeshes.push(dg)
    })

    rackGroups.push(g)
    worldGroup.add(g)

    // 机柜名称标签：与设备书签同款卡片（毛玻璃 + 3px 状态色左边框 + 圆角），
    // 悬浮于柜顶；CSS2D 始终正对相机且不被 3D 几何遮挡，随视角自适应可见。
    const rackLabel = makeRackLabel(rack.name, { accentColor: '#' + sc.toString(16).padStart(6, '0') })
    rackLabel.position.set(0, h + PLINTH_H + 0.45, 0)
    g.add(rackLabel)
  })

  // 相机取景（拉近以放大机房整体视觉占比）
  frameRoomView()
}

// —— 设备总览场景：设备按所属机柜的实际位置摆放在对应坐标（不构建机柜模型、不显示机柜名称标签） ——
function buildDevicesScene() {
  const ra = racks.value
  if (!ra.length) return

  const { map: layout, cols: colN, rows: rowN, aisleZs } = computeRackLayout(ra)

  const spanX = colN * RACK_W
  const spanZ = rowN * (RACK_D + AISLE) - AISLE
  const floorW = spanX + 10
  const floorD = spanZ + 10

  const ground = new THREE.Mesh(
    new THREE.PlaneGeometry(floorW, floorD),
    new THREE.MeshStandardMaterial({ color: 0x0c1422, roughness: 0.85, metalness: 0.2 })
  )
  ground.rotation.x = -Math.PI / 2
  ground.receiveShadow = true
  worldGroup.add(ground)

  // 走廊/过道指引（设备总览模式下同样可见）
  addCorridorGuides({ aisleZs }, floorW)

  // 设备 -> 所属机柜 id
  const devRackMap = {}
  ra.forEach((r) => (rackDevices.value[r.id] || []).forEach((d) => { devRackMap[d.id] = r.id }))

  const devs = flattenDevices()
  devs.forEach((d) => {
    // 仅渲染已上架（存在有效上架记录）的设备；在库设备无 U 位，跳过。
    if (d.current_start_u == null || d.u_height == null) return
    const rid = devRackMap[d.id]
    const pos = rid && layout[rid] ? layout[rid] : { x: 0, z: 0, rot: 0 }
    const h = (d.u_height || 1) * U_H * 0.92
    const dg = buildDevice(d, {
      uHeight: U_H,
      width: RACK_W * 0.9,
      depth: RACK_D * 0.82,
      height: h,
    })
    // 按 U 位计算高度，再落到所属机柜的世界坐标并应用相同旋转
    setDevicePosition(dg, d.current_start_u, d.u_height, { uH: U_H, plinthH: PLINTH_H })
    dg.position.x = pos.x
    dg.position.z = pos.z
    dg.rotation.y = pos.rot
    worldGroup.add(dg)
    deviceMeshes.push(dg)

    // 书签式 U 位标签（设备上方，显示 U 位 + 名称 + 类型色条）
    const uEnd = d.u_height ? d.current_start_u + d.u_height - 1 : d.current_start_u
    const typeColor = DEVICE_TYPE_COLORS[d.device_type] || '#38bdf8'
    const bookmark = makeBookmarkLabel(d.current_start_u, d.name, { typeColor, uEnd })
    bookmark.position.set(0, h / 2 + 0.2, 0)
    dg.add(bookmark)
    dg.userData.bookmark = bookmark
  })

  // 在每个机柜位置放置半透明底座，标示设备所属机柜位置（不显示机柜模型与名称）
  ra.forEach((rack) => {
    const { x, z, rot } = layout[rack.id]
    const pad = new THREE.Mesh(
      new THREE.BoxGeometry(RACK_W, 0.04, RACK_D),
      new THREE.MeshStandardMaterial({ color: 0x2563eb, transparent: true, opacity: 0.12, metalness: 0.2, roughness: 0.8 })
    )
    pad.position.set(x, 0.02, z)
    pad.rotation.y = rot
    worldGroup.add(pad)
  })

  frameRoomView()
}

// 相机取景：基于场景包围球拟合所需距离，并以固定「抬高的前上方」视角方向放置相机，
// 确保整个机房（含最高机柜）完整显示在单屏内，且俯角合理（约 30°），避免前排机柜遮挡后排。
function frameRoomView() {
  if (!engine || !room.value) return
  if (!racks.value.length) return

  const layout = computeRackLayout(racks.value)
  const { spanX, spanZ } = layout

  // 场景包围盒：宽度(X)、高度(Y=地面→最高机柜顶)、深度(Z)
  const maxH = racks.value.reduce((m, r) => Math.max(m, (r.total_u || 42) * U_H), 0)
  const objW = Math.max(spanX, RACK_W * 1.5)
  const objH = maxH + PLINTH_H + 0.6     // 含底座与顶部标签空间
  const objD = Math.max(spanZ, RACK_D * 1.5)

  // 包围球半径：保证整场景（无论长宽高哪一维最大）都落在视锥内
  const radius = 0.5 * Math.sqrt(objW * objW + objH * objH + objD * objD)

  // 由相机 FOV 与视口宽高比推导所需距离（取竖直/水平 FOV 较小者，确保球体完全可见）
  const fovRad = (engine.camera.fov || 50) * Math.PI / 180
  const aspect = engine.camera.aspect ||
    (engine.container.clientWidth / Math.max(1, engine.container.clientHeight))
  const tanV = Math.tan(fovRad / 2)
  const tanH = tanV * aspect
  const fovMin = Math.min(fovRad, 2 * Math.atan(tanH)) // 较小 FOV（弧度）
  let dist = (radius / Math.sin(fovMin / 2)) * 1.08     // 8% 安全边距
  // 智能缩放限制：
  //  · 放大上限提高 —— minDistance 大幅下调，允许更大倍率放大以观察设备细节。
  //  · 机房区域缩小上限提升 —— maxDistance = 取景适配距离 × 1.8（保留一定缩小空间以纵观全局，
  //    同时设上限避免视图丢失关键内容）。
  engine.controls.minDistance = Math.max(2, dist * 0.05)
  engine.controls.maxDistance = dist * 1.8
  // 受 OrbitControls 距离限制约束，避免初始位置被控制器拉回
  dist = THREE.MathUtils.clamp(dist, engine.controls.minDistance, engine.controls.maxDistance)

  // 视角方向：从前侧偏右、抬高俯视（az=32°、el=30°），符合机房巡检习惯，俯角足够大以避免遮挡
  const az = THREE.MathUtils.degToRad(32)
  const el = THREE.MathUtils.degToRad(30)
  const dir = new THREE.Vector3(
    Math.cos(el) * Math.sin(az),
    Math.sin(el),
    Math.cos(el) * Math.cos(az),
  ).normalize()

  const targetY = Math.min(PLINTH_H + maxH * 0.42, 14)
  engine.controls.target.set(0, targetY, 0)
  engine.camera.position.set(
    dir.x * dist,
    targetY + dir.y * dist,
    dir.z * dist,
  )
  engine.controls.update()
  zoomRefDistance = dist // 记录 100% 缩放参考距离

  // 自由移动边界：以「取景适配距离」为基准外扩，既允许飞出机房纵览全局，
  // 又硬性封顶（不可无限远离 / 无限升空），且始终容纳初始取景机位，避免按键时回弹突跳。
  const reach = Math.max(engine.controls.maxDistance * 1.1, 30)
  engine.setMoveBounds({
    minX: -reach, maxX: reach,
    minZ: -reach, maxZ: reach,
    minY: 0.5,
    maxY: targetY + reach * 0.6,
  })
}

function resetView() {
  frameRoomView()
}

// —— 交互：机房 / 设备 两种模式 ——
function setPointer(e) {
  const rect = engine.container.getBoundingClientRect()
  pointer.x = ((e.clientX - rect.left) / rect.width) * 2 - 1
  pointer.y = -((e.clientY - rect.top) / rect.height) * 2 + 1
}

function onPointerMove(e) {
  if (!engine) return
  setPointer(e)
  raycaster.setFromCamera(pointer, engine.camera)
  // 机房总览：优先高亮悬停的设备（点中设备即选中），否则高亮机柜
  const hits = raycaster.intersectObjects(rackGroups, true)
    let devGroup = null
    for (const h of hits) {
      const dg = findDeviceGroup(h.object)
      if (dg && dg.userData.device) {
        devGroup = dg
        break
      }
    }
    if (devGroup) {
      // 选中设备保持琥珀高亮，hover 不覆盖；其余悬停设备给蓝色反馈
      const isSel = devGroup.userData.id === selectedDeviceId.value
      if (hoveredDeviceMesh !== devGroup) {
        if (hoveredDeviceMesh) clearDeviceEmissive(hoveredDeviceMesh)
        if (hoveredGroup) {
          restoreCabinet(hoveredGroup)
          hoveredGroup = null
        }
        if (isSel) hoveredDeviceMesh = null
        else {
          hoveredDeviceMesh = devGroup
          setDeviceEmissive(devGroup, 0x38bdf8, 0.5)
        }
      }
      engine.setCursor('pointer')
      hoveredDeviceId.value = devGroup.userData.id
      showDeviceTooltip(e, devGroup.userData.device)
    } else if (hits.length) {
      const g = findCabinetGroup(hits[0].object)
      if (g && hoveredGroup !== g) {
        if (hoveredGroup) restoreCabinet(hoveredGroup)
        if (hoveredDeviceMesh) {
          clearDeviceEmissive(hoveredDeviceMesh)
          hoveredDeviceMesh = null
          hoveredDeviceId.value = null
          tooltipVisible.value = false
        }
        hoveredGroup = g
        highlightCabinet(g, 0x38bdf8, 0.45)
      }
      engine.setCursor('pointer')
      hoveredRackId.value = g?.userData?.rack?.id || null
      if (g) showRackTooltip(e, g.userData.rack)
    } else {
      if (hoveredGroup) {
        restoreCabinet(hoveredGroup)
        hoveredGroup = null
      }
      if (hoveredDeviceMesh) {
        clearDeviceEmissive(hoveredDeviceMesh)
        hoveredDeviceMesh = null
      }
      hoveredRackId.value = null
      hoveredDeviceId.value = null
      engine.setCursor('grab')
      tooltipVisible.value = false
    }
}

function onPointerDown(e) {
  downPos = { x: e.clientX, y: e.clientY }
}
function onPointerUp(e) {
  if (!downPos) return
  const moved = Math.hypot(e.clientX - downPos.x, e.clientY - downPos.y)
  downPos = null
  if (moved > 5 || !engine) return
  setPointer(e)
  raycaster.setFromCamera(pointer, engine.camera)
  // 机房总览：设备为机柜子节点。优先判定是否点中设备 → 选中并展示详情/链路；
  // 否则点中机柜本体 → 进入机柜三维详情。
    const hits = raycaster.intersectObjects(rackGroups, true)
    let devGroup = null
    for (const h of hits) {
      const dg = findDeviceGroup(h.object)
      if (dg && dg.userData.device) {
        devGroup = dg
        break
      }
    }
    if (devGroup) {
      selectDeviceFromList(devGroup.userData.id)
    } else if (hits.length) {
      const g = findCabinetGroup(hits[0].object)
      // 单击机柜直接进入其三维详情
      if (g) goRack(g.userData.rack)
    } else {
      // 点击空白处：清空设备选中态（保留旋转/平移由 OrbitControls 处理，仅 click 不 drag 时触发）
      clearDeviceSelection()
    }
}

// 双击机柜 → 进入其三维详情视图（与单击效果一致，作为兜底）
function onDblClick(e) {
  if (!engine) return
  setPointer(e)
  raycaster.setFromCamera(pointer, engine.camera)
  const hits = raycaster.intersectObjects(rackGroups, true)
  if (hits.length) {
    const g = findCabinetGroup(hits[0].object)
    if (g) goRack(g.userData.rack)
  }
}

// 设备高亮（setDeviceEmissive / clearDeviceEmissive / setDeviceSelected 已统一在 device-models.js 实现）

function showRackTooltip(e, rack) {
  const dc = deviceCountCache.value[rack.id]
  tooltip.value.innerHTML = `
    <div style="font-weight:700;margin-bottom:2px">${escapeHtml(rack.name)}</div>
    <div style="color:#94a3b8">${escapeHtml(rack.column_code)} / ${escapeHtml(rack.code)}</div>
    <div style="margin-top:4px">状态：${escapeHtml(RACK_STATUS_LABELS[rack.status] || rack.status)} · ${rack.used_u}/${rack.total_u} U</div>
    <div>设备数：${dc != null ? dc : '…'}</div>`
  tooltipVisible.value = true
  tooltipStyle.value = { left: e.clientX + 14 + 'px', top: e.clientY + 14 + 'px' }
}

function showDeviceTooltip(e, d) {
  const uEnd = d.u_height ? d.current_start_u + d.u_height - 1 : d.current_start_u
  tooltip.value.innerHTML = `
    <div style="font-weight:700;margin-bottom:2px">${escapeHtml(d.name)}</div>
    <div style="color:#94a3b8">${escapeHtml(DEVICE_TYPE_LABELS[d.device_type] || d.device_type)}${d.model ? ' · ' + escapeHtml(d.model) : ''}</div>
    <div style="margin-top:4px">U 位：${d.current_start_u}U ~ ${uEnd}U</div>
    <div>状态：${escapeHtml(DEVICE_STATUS_LABELS[d.status] || d.status)}</div>
    <div>IP：${escapeHtml(d.ip_address) || '—'}</div>`
  tooltipVisible.value = true
  tooltipStyle.value = { left: e.clientX + 14 + 'px', top: e.clientY + 14 + 'px' }
}

function onRackHover(rack, e, on) {
  if (on) {
    hoverRoster(rack.id, true)
    showRackTooltip(e, rack)
  } else {
    hoverRoster(rack.id, false)
    tooltipVisible.value = false
  }
}

function onDeviceHover(d, e, on) {
  if (on) {
    hoverDeviceFromList(d.id, true)
    showDeviceTooltip(e, d)
  } else {
    hoverDeviceFromList(d.id, false)
    tooltipVisible.value = false
  }
}

function hoverRoster(id, on) {
  hoveredRackId.value = on ? id : hoveredRackId.value === id ? null : hoveredRackId.value
  const g = rackGroups.find((group) => group.userData.rack.id === id)
  if (!g) return
  if (on) {
    if (hoveredGroup && hoveredGroup !== g) restoreCabinet(hoveredGroup)
    hoveredGroup = g
    highlightCabinet(g, 0x38bdf8, 0.45)
  } else if (hoveredGroup === g) {
    hoveredGroup = null
    restoreCabinet(g)
  }
}

function hoverDeviceFromList(id, on) {
  // 选中态优先：悬停不改变已选中设备的外观（避免蓝色 hover 覆盖琥珀选中高亮）
  if (selectedDeviceId.value === id) return
  hoveredDeviceId.value = on ? id : hoveredDeviceId.value === id ? null : hoveredDeviceId.value
  const g = deviceMeshes.find((m) => m.userData.id === id)
  if (!g) return
  if (on) {
    if (hoveredDeviceMesh && hoveredDeviceMesh !== g) clearDeviceEmissive(hoveredDeviceMesh)
    hoveredDeviceMesh = g
    setDeviceEmissive(g, 0x38bdf8, 0.5)
  } else if (hoveredDeviceMesh === g) {
    clearDeviceEmissive(hoveredDeviceMesh)
    hoveredDeviceMesh = null
  }
}

// 列表 / 3D 场景点击设备：明显的琥珀选中高亮（描边 + 自发光）+ 拉取详情并绘制 3D 动态线缆
function selectDeviceFromList(id) {
  if (selectedDeviceId.value === id) {
    clearDeviceSelection()
    return
  }
  // 还原上一个选中设备
  if (selectedDeviceId.value) {
    const prev = deviceMeshes.find((m) => m.userData.id === selectedDeviceId.value)
    if (prev) setDeviceSelected(prev, false)
    if (hoveredDeviceMesh === prev) hoveredDeviceMesh = null
  }
  selectedDeviceId.value = id
  const g = deviceMeshes.find((m) => m.userData.id === id)
  if (g) setDeviceSelected(g, true)
  // 选中后不再把该设备视为悬停目标：否则鼠标移开时 onPointerMove 的清理逻辑
  // 会误将选中设备的琥珀高亮一并 clearDeviceEmissive 掉，导致高亮消失。
  if (hoveredDeviceMesh === g) hoveredDeviceMesh = null
  if (hoveredDeviceId.value === id) hoveredDeviceId.value = null
  fetchDeviceDetail(id)
}

// 清空设备选中态：取消高亮 + 移除详情面板与 3D 线缆
function clearDeviceSelection() {
  if (selectedDeviceId.value) {
    const g = deviceMeshes.find((m) => m.userData.id === selectedDeviceId.value)
    if (g) setDeviceSelected(g, false)
  }
  if (hoveredDeviceMesh && hoveredDeviceMesh.userData.id === selectedDeviceId.value) hoveredDeviceMesh = null
  selectedDeviceId.value = null
  selectedDeviceDetail.value = null
  clearCables()
}

// 拉取设备详情：设备本体 + 接口列表 + 单设备拓扑（关联链路）。
async function fetchDeviceDetail(id) {
  try {
    const [device, interfaces, topo] = await Promise.all([
      deviceApi.get(id),
      interfaceApi.list(id),
      http.get(`/topology/device/${id}`),
    ])
    const nodeMap = {}
    ;(topo.nodes || []).forEach((n) => {
      nodeMap[n.id] = n
    })
    const links = (topo.edges || [])
      // 跳过设备自连（source==target）的冗余自环链路
      .filter((e) => e.source !== e.target)
      .map((e) => {
        const peerId = e.source === id ? e.target : e.source
        const peer = nodeMap[peerId]
        return {
          medium: e.medium,
          status: e.status,
          source_interface: e.source_interface,
          target_interface: e.target_interface,
          peerId,
          peerName: peer ? peer.name : null,
          peerLabel: e.target_interface ? null : '外部',
        }
      })
    selectedDeviceDetail.value = { device, interfaces: interfaces || [], links }
    buildCables()
  } catch (e) {
    selectedDeviceDetail.value = null
    clearCables()
  }
}

// 计算设备在世界坐标系中的「U 位中心」位置（用于线缆端点精确对应机柜 U 高度）。
// 机房总览（设备为机柜子节点）与设备总览（设备居于机柜坐标）下，设备几何中心的世界坐标
// 均为 (rackX, PLINTH_H + (startU-1+uH/2)*U_H, rackZ)，与机柜绕 Y 旋转无关（中心在旋转轴上）。
function deviceWorldCenter(d) {
  if (!d || d.current_rack_id == null || d.current_start_u == null) return null
  const layout = computeRackLayout(racks.value)
  const pos = layout.map[d.current_rack_id]
  if (!pos) return null
  const y = PLINTH_H + (d.current_start_u - 1 + (d.u_height || 1) / 2) * U_H
  return new THREE.Vector3(pos.x, y, pos.z)
}

// 绘制选中设备与所有「同在本机房且已上架」的关联目标设备之间的动态线缆。
function buildCables() {
  clearCables()
  if (!worldGroup || !selectedDeviceDetail.value) return
  const sel = selectedDeviceDetail.value.device

  const roomDevMap = {}
  flattenDevices().forEach((d) => {
    roomDevMap[d.id] = d
  })

  const group = new THREE.Group()
  group.userData.isCableGroup = true
  const aEnds = deviceCableEnds(sel)
  if (!aEnds) return
  selectedDeviceDetail.value.links.forEach((lk) => {
    if (!lk.peerId) return // 外部链路无目标设备，不在 3D 内连线
    const peer = roomDevMap[lk.peerId]
    if (!peer || peer.current_start_u == null) return // 目标不在本机房 / 未上架，跳过
    const bEnds = deviceCableEnds(peer)
    if (!bEnds) return
    addCable(group, aEnds, bEnds, lk.medium)
  })
  worldGroup.add(group)
  cablesGroup = group
}

// 设备线缆端点：设备 U 位中心（接入点）+ 从机柜正面（过道侧）伸出的出线点。
// 线缆从正面出线、升至顶部走线架、沿走线架水平敷设、再降至目标正面进入设备，
// 全程走机房净空（走线架/过道），不穿透任何机柜本体，符合实际上架布线。
function deviceCableEnds(d) {
  const center = deviceWorldCenter(d)
  if (!center) return null
  const layout = computeRackLayout(racks.value)
  const pos = layout.map[d.current_rack_id]
  const rot = (pos && pos.rot) || 0
  // 机柜正面朝向（局部 +Z 经绕 Y 旋转 rot）：实际布局 rot 恒为 0 → 正面即 +Z
  const fd = new THREE.Vector3(Math.sin(rot), 0, Math.cos(rot))
  const off = RACK_D / 2 + 0.3 // 伸出机柜正面至过道
  const front = new THREE.Vector3(center.x + fd.x * off, center.y, center.z + fd.z * off)
  return { center, front }
}

// 走线架高度：略高于本机房最高机柜顶部，线缆沿顶部净空水平敷设，不接触机柜本体。
// 比原先固定在 WALL_H-0.5(=8.0) 更接近机柜，观感更贴近实际上架布线（不再「过高悬空」）。
function cableTrayY() {
  let maxRackH = PLINTH_H
  for (const r of racks.value) {
    const u = r.total_u || 42
    maxRackH = Math.max(maxRackH, PLINTH_H + u * U_H)
  }
  return maxRackH + 0.7
}

// 单条线缆：直角（正交）路由 + 沿走线架敷设 + 流动光点表示数据流向。
function addCable(group, a, b, medium) {
  const isFiber = medium === 'smf' || medium === 'mmf'
  const color = isFiber ? 0x22d3ee : 0xf59e0b // 光纤青 / 铜缆琥珀
  // 走线架高度：略高于本机房最高机柜（而非固定在 WALL_H-0.5），贴近实际布线
  const trayY = cableTrayY()
  const aT = new THREE.Vector3(a.front.x, trayY, a.front.z)
  const bT = new THREE.Vector3(b.front.x, trayY, b.front.z)
  // 走线架上的直角拐点：先沿 X 再沿 Z（均为 90° 拐弯）
  const mid = new THREE.Vector3(b.front.x, trayY, a.front.z)

  // 路径点（全为轴对齐线段，直角连接）：
  // 设备→正面出线→升至走线架→走线架水平敷设→降至目标正面→进入设备
  const pts = [a.center, a.front, aT, mid, bT, b.front, b.center]
  const flat = []
  for (const p of pts) flat.push(p.x, p.y, p.z)
  // 用于流动光点定位（按弧长参数化）
  const curve = new THREE.CurvePath()
  for (let i = 0; i < pts.length - 1; i++) {
    curve.add(new THREE.LineCurve3(pts[i].clone(), pts[i + 1].clone()))
  }

  // 可见线缆：采用 Line2 + LineMaterial（屏幕空间像素宽度，worldUnits:false）。
  // 线宽随相机距离动态钳制：拉远 → 固定最小像素宽度（不再无限变细消失）；
  // 拉近 → 线宽随之增大（更醒目）。这同时满足「过粗」与「无线缩小」两方面的诉求。
  const lineGeo = new LineGeometry()
  lineGeo.setPositions(flat)
  const lineMat = new LineMaterial({
    color,
    linewidth: 3, // 屏幕像素（worldUnits=false 时）
    worldUnits: false,
    transparent: true,
    opacity: 0.95,
    dashed: false,
  })
  lineMat.resolution.set(
    engine ? engine.renderer.domElement.clientWidth || window.innerWidth : window.innerWidth,
    engine ? engine.renderer.domElement.clientHeight || window.innerHeight : window.innerHeight
  )
  const line = new Line2(lineGeo, lineMat)
  line.computeLineDistances()
  line.userData.isCable = true
  group.add(line)

  // 流动箭头（数据流向）：沿整条直角路径均匀分布、循环流动；锥体尖端指向流动方向。
  // 尺寸较此前球体更小、更贴近线缆（request：球体过大 → 改用更小箭头样式）。
  // 进一步缩小：1U 设备高 ≈ U_H*0.92 ≈ 0.115，箭头高度须 < 此值以避免穿透相邻机柜/设备。
  const flowColor = isFiber ? 0xa5f3fc : 0xfde68a
  const flowMat = new THREE.MeshBasicMaterial({ color: flowColor })
  const arrowGeo = new THREE.ConeGeometry(0.018, 0.05, 8) // radius / height / segments（< 1U 设备）
  const COUNT = 9
  const arrows = []
  const baseOffsets = []
  for (let i = 0; i < COUNT; i++) {
    const m = new THREE.Mesh(arrowGeo, flowMat)
    group.add(m)
    arrows.push(m)
    baseOffsets.push(i / COUNT)
  }
  // speed 调低（0.3 → 0.15），线缆流动更舒缓、不「过快」
  cables.push({ curve, line, lineMat, arrows, baseOffsets, speed: 0.15 })
}

// 释放全部线缆资源。
function clearCables() {
  cables.length = 0
  if (cablesGroup && worldGroup) {
    worldGroup.remove(cablesGroup)
    cablesGroup.traverse((o) => {
      if (o.geometry) o.geometry.dispose()
      if (o.material) {
        const ms = Array.isArray(o.material) ? o.material : [o.material]
        ms.forEach((m) => m.dispose())
      }
    })
  }
  cablesGroup = null
}

// 每帧驱动线缆流动箭头（由引擎 onTick 回调）。
const _lineRes = new THREE.Vector2()
function tickCables(dt) {
  // 实时更新缩放百分比（无论是否选中设备，均随相机距离刷新）
  updateZoomUI()
  if (!cables.length) return
  cableClock += dt
  // 当前缩放距离 → 归一化系数：拉远(dist 大)趋近下限、拉近(dist 小)增大
  const cam = engine ? engine.camera : null
  const tgt = engine ? engine.controls.target : null
  const dist = cam && tgt ? cam.position.distanceTo(tgt) : 40
  const zoom = THREE.MathUtils.clamp(40 / dist, 0.3, 1.2)
  const lineW = THREE.MathUtils.clamp(3 * zoom, 2, 6.5) // 屏幕像素宽度（拉远=固定最小 2px）
  const flowScale = zoom // 流动箭头随缩放同步放大/固定下限，避免拉远时消失
  const el = engine ? engine.renderer.domElement : null
  if (el) _lineRes.set(el.clientWidth || window.innerWidth, el.clientHeight || window.innerHeight)
  for (const c of cables) {
    if (c.lineMat) {
      c.lineMat.linewidth = lineW
      if (el) c.lineMat.resolution.copy(_lineRes)
    }
    for (let i = 0; i < c.arrows.length; i++) {
      const t = (c.baseOffsets[i] + cableClock * c.speed) % 1
      const p = c.curve.getPointAt(t)
      c.curve.getTangentAt(t, _tan).normalize() // 切线即流动方向（源设备→对端）
      c.arrows[i].position.copy(p)
      c.arrows[i].quaternion.setFromUnitVectors(_up, _tan) // 锥尖(+Y)对齐切线
      c.arrows[i].scale.setScalar(flowScale)
    }
  }
}

// 实时计算缩放百分比：以取景适配距离为 100% 基准；
// 机房区域已禁用缩小 → 实际缩放恒 ≥100%（仅可放大）。
function updateZoomUI() {
  if (!engine) return
  const d = engine.camera.position.distanceTo(engine.controls.target)
  const ref = zoomRefDistance || d
  const pct = Math.round((ref / d) * 100)
  if (pct !== zoomPercent.value) zoomPercent.value = pct
}

function goRack(rack) {
  router.push({ path: `/3d/rack/${rack.id}`, query: { room: roomId.value } })
}

// 打开全屏数据大屏展示页（无导航栏冗余 UI）
function goBigScreen() {
  router.push({ path: '/bigscreen', query: roomId.value ? { room: roomId.value } : {} })
}

function onRoomChange(id) {
  hoveredRackId.value = null
  hoveredGroup = null
  clearDeviceSelection()
  expandedGroups.value = {}
  loadRoom(id)
}

function disposeWorld(group) {
  group.traverse((obj) => {
    // 清理 CSS2D 标签 DOM（元素挂在 labelRenderer 层，需主动移除避免残留）
    if (obj.isCSS2DObject && obj.element && obj.element.parentNode) {
      obj.element.parentNode.removeChild(obj.element)
    }
    if (obj.geometry) obj.geometry.dispose()
    if (obj.material) {
      const mats = Array.isArray(obj.material) ? obj.material : [obj.material]
      mats.forEach((m) => {
        for (const key in m) {
          const val = m[key]
          if (val && val.isTexture) val.dispose()
        }
        m.dispose()
      })
    }
  })
}

let reinitGuard = false
function rebuildEngine() {
  if (reinitGuard || disposed) return
  reinitGuard = true
  try {
    if (engine) {
      engine.dispose()
      engine = null
    }
    initEngine()
  } finally {
    reinitGuard = false
  }
}

function initEngine() {
  if (!canvasWrap.value) return
  if (disposed) return // 组件已卸载，放弃初始化，避免挂载后创建游离 WebGL 上下文
  try {
    engine = createEngine(canvasWrap.value, {
      background: 0x0b1220,
      fog: true,
      fogNear: 40,
      fogFar: 220,
      targetY: 6,
      minDistance: 8,
      maxDistance: 260,
      cameraPosition: [34, 28, 42],
      freeMove: true,
      moveSpeed: 26,
      // 上下文恢复后整体重建引擎（最稳妥，避免空白）
      onContextRestored: () => rebuildEngine(),
    })
    // 仅开发环境暴露引擎，便于自动化自测读取相机位置
    if (import.meta.env && import.meta.env.DEV) {
      window.__room3d = engine
      window.__room3dSelect = (id) => selectDeviceFromList(id)
      window.__room3dDebug = () => ({
        selected: selectedDeviceId.value,
        cables: cables.length,
        hasDetail: !!selectedDeviceDetail.value,
        linkCount: selectedDeviceDetail.value ? selectedDeviceDetail.value.links.length : 0,
        zoom: zoomPercent.value,
        maxDistance: engine ? +engine.controls.maxDistance.toFixed(2) : null,
        minDistance: engine ? +engine.controls.minDistance.toFixed(2) : null,
      })
    }
    // 每帧驱动选中设备的关联链路流动光效
    engine.setOnTick(tickCables)
  } catch (e) {
    console.error('[Room3D] createEngine failed', e)
    error.value = '三维渲染初始化失败（WebGL 上下文不足或不可用），请返回后刷新重试。'
    return
  }
  const c = engine.renderer.domElement
  c.addEventListener('pointermove', onPointerMove)
  c.addEventListener('pointerdown', onPointerDown)
  c.addEventListener('pointerup', onPointerUp)
  c.addEventListener('dblclick', onDblClick)
  if (room.value) buildScene()
}

function backToRooms() {
  router.push(roomId.value ? { path: '/3d', query: { room: roomId.value } } : '/3d')
}

function flattenDevices() {
  const out = []
  for (const rid in rackDevices.value) out.push(...(rackDevices.value[rid] || []))
  return out
}

// 主题切换时实时更新 3D 场景配色（不重建场景，仅替换材质/灯光/背景）
watch(isDark, (dark) => apply3DTheme(dark), { immediate: false })

onMounted(async () => {
  try {
    await loadRooms()
    if (roomId.value) await loadRoom(roomId.value)
    await nextTick()
    if (disposed) return // 等待异步数据期间已被卸载，跳过初始化
    initEngine()
  } catch (e) {
    console.error('[Room3D] init failed', e)
    error.value = '机房三维场景加载失败：' + (e?.message || e)
  }
})

onBeforeUnmount(() => {
  disposed = true // 先置位，阻断任何进行中的异步初始化
  if (engine) {
    try {
      const c = engine.renderer.domElement
      c.removeEventListener('pointermove', onPointerMove)
      c.removeEventListener('pointerdown', onPointerDown)
      c.removeEventListener('pointerup', onPointerUp)
      c.removeEventListener('dblclick', onDblClick)
    } catch (e) {
      /* noop */
    }
    engine.dispose()
    engine = null
  }
})
</script>

<style scoped>
/* 设备详情面板：接口列表等内部可滚动区域使用细滚动条，交换机接口过多时仍可流畅浏览 */
.device-iface-scroll::-webkit-scrollbar,
.device-detail-panel ::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
.device-iface-scroll::-webkit-scrollbar-thumb,
.device-detail-panel ::-webkit-scrollbar-thumb {
  background: rgba(148, 163, 184, 0.4);
  border-radius: 9999px;
}
.device-iface-scroll::-webkit-scrollbar-thumb:hover,
.device-detail-panel ::-webkit-scrollbar-thumb:hover {
  background: rgba(148, 163, 184, 0.6);
}
.device-iface-scroll,
.device-detail-panel * {
  scrollbar-width: thin;
  scrollbar-color: rgba(148, 163, 184, 0.4) transparent;
}
</style>
