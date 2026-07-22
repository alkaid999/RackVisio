<template>
  <div class="relative w-full" style="height: calc(100vh - 8.5rem)">
    <!-- 3D 画布 -->
    <div ref="canvasWrap" class="three-canvas-wrap">
      <div v-if="loading" class="three-loading">正在加载机柜三维视图…</div>
    </div>

    <!-- 顶部：面包屑（机房 > 机柜 > 设备） + 工具栏 -->
    <div class="absolute top-4 left-4 right-4 flex items-start justify-between gap-3 pointer-events-none">
      <nav class="glass-panel px-4 py-2 text-sm flex items-center gap-2 pointer-events-auto">
        <button type="button" class="link-quiet" @click="goRoom">机房：{{ roomName || '—' }}</button>
        <ChevronRight class="w-4 h-4 gp-sub" />
        <span class="text-slate-100 font-medium">{{ rack?.name || '机柜' }}</span>
        <template v-if="selectedDevice">
          <ChevronRight class="w-4 h-4 gp-sub" />
          <span class="text-brand-300 font-medium">{{ selectedDevice.name }}</span>
        </template>
      </nav>

      <div class="flex items-center gap-2 pointer-events-auto">
        <Button @click="goRoom"><ArrowLeft class="h-4 w-4" />返回机房</Button>
        <Button size="icon" title="重置视角" @click="resetView"><RotateCcw class="h-4 w-4" /></Button>
      </div>
    </div>

    <!-- 右侧信息面板：选中设备时展示设备详情，否则展示机柜元数据 -->
    <div class="absolute top-24 right-4 w-80 pointer-events-auto">
      <div class="glass-panel p-4">
        <template v-if="selectedDevice">
          <div class="gp-title text-sm mb-3 flex items-center gap-2">
            <Cpu class="w-4 h-4 text-brand-400" /> 设备详情
          </div>
          <DeviceInfoCard :device="selectedDevice" :rack="rack" />
        </template>
        <template v-else>
          <div class="gp-title text-sm mb-3 flex items-center gap-2">
            <Server class="w-4 h-4 text-brand-400" /> 机柜信息
          </div>
          <RackInfoCard v-if="rack" :rack="rack" :device-count="devices.length" />
          <p class="gp-sub text-xs mt-3 leading-relaxed">
            点击机柜内的设备块可查看其详细信息（名称 / 型号 / IP / 状态 / 所属业务 / 位置）。
          </p>
        </template>
      </div>
    </div>

    <!-- 底部操作提示 -->
    <div class="absolute bottom-3 left-1/2 -translate-x-1/2 pointer-events-none">
      <div class="glass-panel px-4 py-1.5 text-xs gp-sub">
        拖拽旋转 · 滚轮缩放 · 点击设备查看详情
      </div>
    </div>

    <div v-show="tooltipVisible" ref="tooltip" class="three-tooltip" :style="tooltipStyle" />

    <!-- 初始化失败兜底（如 WebGL 上下文不可用 / 未找到机柜） -->
    <div v-if="error" class="absolute inset-0 flex items-center justify-center pointer-events-auto">
      <div class="glass-panel p-6 max-w-md text-center">
        <div class="gp-title mb-2">无法显示三维视图</div>
        <p class="gp-sub text-sm">{{ error }}</p>
        <Button class="mt-4" @click="goRoom">返回机房总览</Button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ChevronRight, ArrowLeft, RotateCcw, Cpu, Server } from 'lucide-vue-next'
import * as THREE from 'three'
import rackApi from '@/api/rack'
import roomApi from '@/api/room'
import { createEngine, makeBookmarkLabel, makeRackNameLabel } from '@/utils/three-setup'
import {
  buildCabinet,
  buildDevice,
  setDevicePosition,
  findDeviceGroup,
  setDeviceSelected,
  setDeviceEmissive,
  clearDeviceEmissive,
  RACK_W,
  RACK_D,
  U_H,
  PLINTH_H,
} from '@/utils/device-models'
import RackInfoCard from '@/components/three/RackInfoCard.vue'
import DeviceInfoCard from '@/components/three/DeviceInfoCard.vue'
import { DEVICE_TYPE_LABELS, DEVICE_STATUS_LABELS, DEVICE_TYPE_COLORS } from '@/utils/constants'
import { escapeHtml } from '@/utils/escape'
import Button from '@/components/ui/button.vue'

const route = useRoute()
const router = useRouter()

const rack = ref(null)
const devices = ref([])
const roomName = ref('')
const loading = ref(false)
const error = ref('')

const canvasWrap = ref(null)
const tooltip = ref(null)
const tooltipVisible = ref(false)
const tooltipStyle = ref({ left: '0px', top: '0px' })

const selectedDeviceId = ref(null)
const selectedDevice = computed(() => devices.value.find((d) => d.id === selectedDeviceId.value) || null)

let engine = null
let worldGroup = null
const deviceMeshes = [] // 存放设备 Group（含 userData.device / pickMesh）
const raycaster = new THREE.Raycaster()
const pointer = new THREE.Vector2()
let hoveredMesh = null
let selectedMesh = null
let downPos = null

async function load() {
  loading.value = true
  error.value = ''
  try {
    // 路由标识为机柜 code（如 R1-C1），需先解析出真实 UUID 再加载详情。
    const slug = route.params.rackSlug
    const roomQ = route.query.room
    let target = null
    if (roomQ) {
      const list = await roomApi.racks(roomQ)
      target = (list || []).find((r) => r.code === slug || r.id === slug) || null
    }
    if (!target) {
      error.value = '未找到对应的机柜，请从「机房3D总览」进入。'
      return
    }
    const r = await rackApi.get(target.id)
    rack.value = r
    const devs = await rackApi.devices(target.id)
    devices.value = devs
    if (r.room_id) {
      try {
        const rm = await roomApi.get(r.room_id)
        roomName.value = rm.name
      } catch {
        roomName.value = ''
      }
    }
    if (engine) buildScene()
  } catch (e) {
    console.error('[Rack3D] load failed', e)
    error.value = '加载机柜数据失败：' + (e?.message || e)
  } finally {
    loading.value = false
  }
}

// 统一刷新高亮：选中（琥珀描边 + 自发光）> 悬停（蓝色）> 还原。
function refreshHighlights() {
  deviceMeshes.forEach((g) => {
    if (g === selectedMesh) setDeviceSelected(g, true)
    else if (g === hoveredMesh) setDeviceEmissive(g, 0x38bdf8, 0.5)
    else setDeviceSelected(g, false)
  })
}

function buildScene() {
  if (!engine || !rack.value) return
  if (worldGroup) {
    engine.scene.remove(worldGroup)
    disposeWorld(worldGroup)
    // 清除上一场景残留的 CSS2D 标签 DOM（机柜名 / 设备书签），避免重建后叠加。
    if (engine.clearLabels) engine.clearLabels()
  }
  worldGroup = new THREE.Group()
  engine.scene.add(worldGroup)
  deviceMeshes.length = 0
  selectedMesh = null
  hoveredMesh = null
  selectedDeviceId.value = null

  const r = rack.value
  const rackH = (r.total_u || 42) * U_H

  // 地面（承接阴影，强化空间真实感）
  const ground = new THREE.Mesh(
    new THREE.PlaneGeometry(RACK_W * 6, RACK_D * 6),
    new THREE.MeshStandardMaterial({ color: 0x0c1422, roughness: 0.85, metalness: 0.2 })
  )
  ground.rotation.x = -Math.PI / 2
  ground.receiveShadow = true
  worldGroup.add(ground)

  // 真实机柜：无前门，便于直视内部设备；保留立柱、导轨、侧板、后门、脚轮。
  const cabinet = buildCabinet({
    width: RACK_W,
    depth: RACK_D,
    height: rackH,
    uHeight: U_H,
    plinthHeight: PLINTH_H,
    totalU: r.total_u || 42,
    frontDoor: 'none',
    sidePanel: 'perforated',
    showBack: true,
    showRails: true,
    showCasters: true,
  })
  worldGroup.add(cabinet)

  // 设备：按类型建模为贴近真实的 3D 形态，并作为独立 Group 挂载到对应 U 位。
  const mdevs = []
  devices.value.forEach((d) => {
    if (d.current_start_u == null || d.u_height == null) return
    const w = RACK_W * 0.9
    const dDepth = RACK_D * 0.82
    const h = d.u_height * U_H * 0.92
    const dg = buildDevice(d, {
      uHeight: U_H,
      width: w,
      depth: dDepth,
      height: h,
    })
    setDevicePosition(dg, d.current_start_u, d.u_height, { uH: U_H, plinthH: PLINTH_H })
    worldGroup.add(dg)

    const uEnd = d.u_height ? d.current_start_u + d.u_height - 1 : d.current_start_u
    const typeColor = DEVICE_TYPE_COLORS[d.device_type] || '#38bdf8'
    mdevs.push({
      dg,
      d,
      yMid: dg.position.y, // 设备中心世界高度（worldGroup 无偏移）
      uPos: d.current_start_u,
      uEnd,
      typeColor,
      name: d.name,
    })
    deviceMeshes.push(dg)
  })

  // 机柜名称标签：头顶位置，与设备标签同款卡片组件，统一整体 UI 风格
  const rackNameLabel = makeRackNameLabel(rack.value.name || '机柜', { accentColor: '#38bdf8' })
  rackNameLabel.position.set(0, PLINTH_H + rackH + 0.55, 0)
  worldGroup.add(rackNameLabel)

  // 设备标签：右侧标签列 + 引线引出 + 「}」归纳分组，单行去堆叠
  buildDeviceLabels(mdevs, worldGroup)

  // 相机取景：按机柜实际尺寸自动适配，确保完整内容单屏可见
  frameRackView()
}

function resetView() {
  frameRackView()
}

// 生成一条 3D 折线（用于设备引线 / 归纳括号）。depthTest:false 保证在机柜外壳之上始终可见。
function makeLine(points, color, opacity) {
  const geo = new THREE.BufferGeometry().setFromPoints(points)
  const mat = new THREE.LineBasicMaterial({
    color,
    transparent: true,
    opacity,
    depthTest: false,
  })
  const line = new THREE.Line(geo, mat)
  line.renderOrder = 998
  return line
}

// 设备标签布局：统一置于机柜右侧标签列（xLabel），从设备右前缘以引线引出，
// 多个设备以「}」归纳括号跨接汇总，单行去堆叠避免缩小视图时标签互相覆盖。
//   mdevs  — 已上架设备信息数组（{ dg, uPos, uEnd, typeColor, name, yMid }）
//   parent — 标签/引线挂载的父 Group（worldGroup）
function buildDeviceLabels(mdevs, parent) {
  if (!mdevs.length) return
  const zFront = RACK_D * 0.35
  const xLabel = RACK_W / 2 + 0.5 // 标签卡片左缘锚定列
  const xBrace = RACK_W / 2 + 0.95 // 归纳括号所在列（标签右侧）
  const bow = 0.16 // 括号向右凸出量

  // 1) 单行去堆叠：按设备中心高度排序，施加最小竖直间距，再整体居中回移贴近设备
  const sorted = [...mdevs].sort((a, b) => a.yMid - b.yMid)
  const minGap = 0.34
  const labelY = sorted.map((m) => m.yMid)
  for (let i = 1; i < labelY.length; i++) {
    if (labelY[i] - labelY[i - 1] < minGap) labelY[i] = labelY[i - 1] + minGap
  }
  const meanOrig = sorted.reduce((s, m) => s + m.yMid, 0) / sorted.length
  const meanAdj = labelY.reduce((s, v) => s + v, 0) / labelY.length
  const shift = meanOrig - meanAdj
  sorted.forEach((m, i) => (m.labelY = labelY[i] + shift))

  // 2) 引线：设备右前缘 → 归纳括号列（斜向，体现设备归属连线）
  sorted.forEach((m) => {
    const pts = [
      new THREE.Vector3(RACK_W / 2 + 0.02, m.yMid, zFront),
      new THREE.Vector3(xBrace, m.labelY, zFront),
    ]
    parent.add(makeLine(pts, m.typeColor, 0.5))
  })

  // 3) 归纳括号「}」：跨所有设备，向右凸出，清晰呈现设备分组归属
  if (sorted.length >= 2) {
    const yTop = sorted[sorted.length - 1].labelY
    const yBot = sorted[0].labelY
    const span = yTop - yBot
    const ctrl = [
      new THREE.Vector3(xBrace, yTop, zFront),
      new THREE.Vector3(xBrace + bow, yTop - span * 0.22, zFront),
      new THREE.Vector3(xBrace + bow, (yTop + yBot) / 2, zFront),
      new THREE.Vector3(xBrace + bow, yBot + span * 0.22, zFront),
      new THREE.Vector3(xBrace, yBot, zFront),
    ]
    const curve = new THREE.CatmullRomCurve3(ctrl)
    parent.add(makeLine(curve.getPoints(24), 0x94a3b8, 0.85))
  }

  // 4) 标签卡片（单行）：左对齐锚定在标签列，并挂回设备 Group 供选中高亮联动
  sorted.forEach((m) => {
    const label = makeBookmarkLabel(m.uPos, m.name, { typeColor: m.typeColor, uEnd: m.uEnd })
    label.position.set(xLabel, m.labelY, zFront)
    parent.add(label)
    m.dg.userData.bookmark = label
  })
}

// 自动取景：以机柜包围球半径为基准，结合相机 FOV 与视口比例推导距离，
// 保证整个机柜（含底座与顶部设备标签）完整落在视锥内，单屏可见无需滚动。
function frameRackView() {
  if (!engine || !rack.value) return
  const rackH = (rack.value.total_u || 42) * U_H
  // 包围盒半尺寸：X 含右侧标签列 + 归纳括号余量；Y 含底座→柜顶+顶部机柜名标签；Z=机柜深
  const halfW = RACK_W / 2 + 1.2
  const halfH = (PLINTH_H + rackH + 1.4) / 2
  const halfD = (RACK_D * 1.5) / 2
  const R = Math.sqrt(halfW * halfW + halfH * halfH + halfD * halfD) // 包围球半径
  const fovRad = (engine.camera.fov || 50) * Math.PI / 180
  const aspect = engine.camera.aspect ||
    (engine.container.clientWidth / Math.max(1, engine.container.clientHeight))
  const halfFovV = fovRad / 2
  const halfFovH = Math.atan(Math.tan(halfFovV) * aspect)
  // 包围球同时适配竖直 / 水平视场，取较大者并留 8% 余量
  const distV = R / Math.sin(halfFovV)
  const distH = R / Math.sin(halfFovH)
  const baseDist = Math.max(distV, distH) * 1.08
  const targetY = PLINTH_H + rackH * 0.46
  engine.controls.target.set(0, targetY, 0)
  // 正对柜体、略偏右上（看清内部设备 + 顶部标签），距离由 fit 计算
  engine.camera.position.set(baseDist * 0.6, targetY + baseDist * 0.24, baseDist * 0.74)
  engine.controls.update()
}

function setPointer(e) {
  const rect = engine.container.getBoundingClientRect()
  pointer.x = ((e.clientX - rect.left) / rect.width) * 2 - 1
  pointer.y = -((e.clientY - rect.top) / rect.height) * 2 + 1
}

function onPointerMove(e) {
  if (!engine) return
  setPointer(e)
  raycaster.setFromCamera(pointer, engine.camera)
  const hits = raycaster.intersectObjects(deviceMeshes, true)
  if (hits.length) {
    const g = findDeviceGroup(hits[0].object)
    if (g && hoveredMesh !== g) {
      hoveredMesh = g
      refreshHighlights()
    }
    engine.setCursor('pointer')
    if (g) showTooltip(e, g.userData.device)
  } else {
    if (hoveredMesh) {
      hoveredMesh = null
      refreshHighlights()
    }
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
  const hits = raycaster.intersectObjects(deviceMeshes, true)
  if (hits.length) {
    const g = findDeviceGroup(hits[0].object)
    if (!g) return
    if (selectedMesh === g) {
      selectedMesh = null
      selectedDeviceId.value = null
    } else {
      selectedMesh = g
      selectedDeviceId.value = g.userData.id
    }
    refreshHighlights()
  } else {
    selectedMesh = null
    selectedDeviceId.value = null
    refreshHighlights()
  }
}

function showTooltip(e, d) {
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

function goRoom() {
  const rid = rack.value?.room_id
  router.push(rid ? { path: '/3d', query: { room: rid } } : '/3d')
}

function disposeWorld(group) {
  group.traverse((obj) => {
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

function initEngine() {
  if (!canvasWrap.value) return
  try {
    engine = createEngine(canvasWrap.value, {
      background: 0x0b1220,
      fog: false,
      targetY: 6,
      minDistance: 4,
      maxDistance: 120,
      cameraPosition: [9, 8, 14],
    })
  } catch (e) {
    console.error('[Rack3D] createEngine failed', e)
    error.value = '三维渲染初始化失败（WebGL 上下文不足或不可用），请返回后刷新重试。'
    return
  }
  const c = engine.renderer.domElement
  c.addEventListener('pointermove', onPointerMove)
  c.addEventListener('pointerdown', onPointerDown)
  c.addEventListener('pointerup', onPointerUp)
  // 仅开发环境暴露引擎，便于自动化自测读取相机位置
  if (import.meta.env && import.meta.env.DEV) {
    window.__rack3d = engine
  }
  if (rack.value) buildScene()
}

onMounted(async () => {
  try {
    await load()
    await nextTick()
    if (!error.value) initEngine()
  } catch (e) {
    console.error('[Rack3D] init failed', e)
    error.value = '机柜三维视图初始化失败：' + (e?.message || e)
  }
})

onBeforeUnmount(() => {
  if (engine) {
    try {
      const c = engine.renderer.domElement
      c.removeEventListener('pointermove', onPointerMove)
      c.removeEventListener('pointerdown', onPointerDown)
      c.removeEventListener('pointerup', onPointerUp)
    } catch (e) {
      /* noop */
    }
    engine.dispose()
    engine = null
  }
})
</script>
