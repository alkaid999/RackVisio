// 设备 / 机柜的「真实形态」3D 建模工具。
// 设计目标：按真实 19 英寸机柜（宽约 600mm、深约 1000mm、1U=44.45mm）的比例放大建模，
// 同时让每台设备作为独立 Group 存在，可被单独挂载、移动、拾取、高亮。
//
// 参考图片特征：
//   · 黑色/深灰金属框架，四柱结构，前后门，侧板/后门为穿孔网板或玻璃门
//   · 顶部通风栅格，底部带脚轮
//   · 内部方孔安装导轨，设备按 U 位堆叠
//
// 视图层只需调用 buildCabinet / buildDevice / setDevicePosition，并摆放返回的 Group。
import * as THREE from 'three'
import { DEVICE_TYPE_COLORS, DEVICE_STATUS_COLORS } from '@/utils/constants'
import { makeCanvasTexture } from '@/utils/three-setup'

// 视觉放大系数：在保持真实长宽高比例的前提下，让机柜在屏幕中清晰可辨。
// 1 单位 ≈ 0.357 真实米，因此 600mm 宽机柜≈1.68 单位，1U≈0.125 单位。
export const VISUAL_SCALE = 2.8
export const RACK_W = 0.6 * VISUAL_SCALE        // 机柜外宽 ≈ 1.68
export const RACK_D = 1.0 * VISUAL_SCALE        // 机柜外深 ≈ 2.8
export const U_H = 0.04445 * VISUAL_SCALE       // 1U 高度 ≈ 0.125
export const PLINTH_H = 0.12 * VISUAL_SCALE     // 底座高度 ≈ 0.34（含脚轮支架）

// 常用颜色
const CHASSIS = 0x1a202c      // 机箱本体（深枪灰）
const BEZEL = 0x0d1117        // 前面板内嵌深色
const FRAME = 0x11151d        // 机柜框架
const DARK_METAL = 0x1f2633   // 金属件

// 穿孔金属贴图（用于前门、侧板、后门）。每次新建，避免 dispose 时误删共享纹理。
function perfTexture() {
  return makeCanvasTexture(
    (ctx, w, h) => {
      ctx.fillStyle = '#2a3242'
      ctx.fillRect(0, 0, w, h)
      ctx.fillStyle = '#070a10'
      const step = 9
      for (let y = step / 2; y < h; y += step) {
        for (let x = step / 2; x < w; x += step) {
          ctx.beginPath()
          ctx.arc(x, y, 2.0, 0, Math.PI * 2)
          ctx.fill()
        }
      }
    },
    64,
    128
  )
}

// 方孔导轨贴图（竖向两列方孔 + 每 5U 编号）
function railTexture() {
  return makeCanvasTexture(
    (ctx, w, h) => {
      ctx.fillStyle = '#9ca6b8'
      ctx.fillRect(0, 0, w, h)
      ctx.fillStyle = '#0b0f17'
      const hole = 7
      const gap = 12
      const mx = 10
      const holes = Math.floor((h - 24) / gap)
      for (let i = 0; i < holes; i++) {
        const y = 12 + i * gap
        ctx.fillRect(mx, y, hole, hole)
        ctx.fillRect(w - mx - hole, y, hole, hole)
      }
      // U 刻度编号
      ctx.fillStyle = '#1a2333'
      ctx.font = 'bold 11px sans-serif'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      for (let u = 1; u <= 42; u += 5) {
        const y = 12 + (u - 1) * gap
        ctx.fillText(String(u), w / 2, y + hole / 2)
      }
    },
    64,
    512
  )
}

// 材质工厂
function darkMetal() {
  return new THREE.MeshStandardMaterial({ color: DARK_METAL, metalness: 0.65, roughness: 0.45 })
}
function frameMetal() {
  return new THREE.MeshStandardMaterial({ color: FRAME, metalness: 0.55, roughness: 0.5 })
}
// 穿孔金属板：使用程序化穿孔贴图作为不透明 map（孔洞为深色而非真正透明），
// 既保留「穿孔网板」观感，又能在左右/后面正确遮挡视线，避免半透明导致的「镂空」与透明排序异常。
function perfMetal() {
  return new THREE.MeshStandardMaterial({
    map: perfTexture(),
    color: 0xffffff,
    metalness: 0.5,
    roughness: 0.55,
    side: THREE.DoubleSide,
  })
}
function glassMaterial() {
  return new THREE.MeshPhysicalMaterial({
    color: 0x9fbfff,
    metalness: 0.1,
    roughness: 0.05,
    transparent: true,
    opacity: 0.12,
    transmission: 0.6,
    thickness: 0.02,
    side: THREE.DoubleSide,
  })
}

// 构建真实机柜。返回一个以底面 y=0、x/z 几何中心为原点的 Group。
// options:
//   width/depth/height/uHeight/plinthHeight/totalU: 尺寸
//   frontDoor: 'none' | 'perforated' | 'glass'
//   sidePanel: 'solid' | 'perforated' | 'glass'
//   showBack/showRails/showCasters: 是否显示对应部件
//   statusColor: 顶部状态灯颜色（hex 数值）
//   occupancyRatio: 0~1，用于前侧占用条高度
export function buildCabinet(options = {}) {
  const w = options.width ?? RACK_W
  const d = options.depth ?? RACK_D
  const uH = options.uHeight ?? U_H
  const plinthH = options.plinthHeight ?? PLINTH_H
  const totalU = options.totalU ?? 42
  const h = options.height ?? totalU * uH
  const frontDoor = options.frontDoor ?? 'perforated'
  const sidePanel = options.sidePanel ?? 'perforated'
  const showBack = options.showBack !== false
  const showRails = options.showRails !== false
  const showCasters = options.showCasters !== false
  const statusColor = options.statusColor ?? 0x67c23a
  const occupancyRatio = Math.max(0, Math.min(1, options.occupancyRatio ?? 0))

  const group = new THREE.Group()
  const halfW = w / 2
  const halfD = d / 2
  const y0 = plinthH

  // 1. 底座
  const plinthGeo = new THREE.BoxGeometry(w * 1.04, plinthH, d * 1.04)
  const plinth = new THREE.Mesh(plinthGeo, frameMetal())
  plinth.position.y = plinthH / 2
  plinth.receiveShadow = true
  group.add(plinth)

  // 2. 脚轮（参考图：四个带滚轮的支撑脚）
  if (showCasters) {
    const bracketMat = new THREE.MeshStandardMaterial({ color: 0x080a0e, metalness: 0.3, roughness: 0.8 })
    const wheelMat = new THREE.MeshStandardMaterial({ color: 0x7a7a7a, metalness: 0.7, roughness: 0.4 })
    const bracketGeo = new THREE.BoxGeometry(0.14, 0.14, 0.14)
    const wheelGeo = new THREE.CylinderGeometry(0.07, 0.07, 0.1, 16)
    const offsets = [
      [-halfW + 0.2, -halfD + 0.2],
      [halfW - 0.2, -halfD + 0.2],
      [-halfW + 0.2, halfD - 0.2],
      [halfW - 0.2, halfD - 0.2],
    ]
    offsets.forEach(([x, z]) => {
      const b = new THREE.Mesh(bracketGeo, bracketMat)
      b.position.set(x, 0.08, z)
      group.add(b)
      const wheel = new THREE.Mesh(wheelGeo, wheelMat)
      wheel.rotation.z = Math.PI / 2
      wheel.position.set(x, 0.07, z)
      group.add(wheel)
    })
  }

  // 3. 四角立柱
  const postW = 0.12
  const postD = 0.12
  const postGeo = new THREE.BoxGeometry(postW, h, postD)
  const postMat = new THREE.MeshStandardMaterial({ color: 0x0b0f17, metalness: 0.7, roughness: 0.35 })
  const px = halfW - postW / 2
  const pz = halfD - postD / 2
  ;[
    [-px, -pz],
    [px, -pz],
    [-px, pz],
    [px, pz],
  ].forEach(([x, z]) => {
    const p = new THREE.Mesh(postGeo, postMat)
    p.position.set(x, y0 + h / 2, z)
    p.castShadow = true
    group.add(p)
  })

  // 4. 顶框与底框
  const topCap = new THREE.Mesh(new THREE.BoxGeometry(w * 1.02, 0.18, d * 1.02), frameMetal())
  topCap.position.set(0, y0 + h + 0.09, 0)
  topCap.castShadow = true
  group.add(topCap)

  const bottomFrame = new THREE.Mesh(new THREE.BoxGeometry(w, 0.1, d), darkMetal())
  bottomFrame.position.set(0, y0 + 0.05, 0)
  group.add(bottomFrame)

  // 5. 前门（穿孔或玻璃）+ 门框 + 把手
  let frontDoorMesh = null
  if (frontDoor !== 'none') {
    const doorW = w * 0.95
    const doorH = h * 0.98
    const doorZ = halfD + 0.02
    const doorMat = frontDoor === 'glass' ? glassMaterial() : perfMetal()
    const door = new THREE.Mesh(new THREE.PlaneGeometry(doorW, doorH), doorMat)
    door.position.set(0, y0 + h / 2, doorZ)
    group.add(door)
    frontDoorMesh = door

    // 门框
    const frameMat = darkMetal()
    const frameThick = 0.08
    const frameDeep = 0.06
    const fTop = new THREE.Mesh(new THREE.BoxGeometry(doorW, frameThick, frameDeep), frameMat)
    fTop.position.set(0, y0 + h - frameThick / 2, doorZ)
    group.add(fTop)
    const fBot = new THREE.Mesh(new THREE.BoxGeometry(doorW, frameThick, frameDeep), frameMat)
    fBot.position.set(0, y0 + frameThick / 2, doorZ)
    group.add(fBot)
    const fLeft = new THREE.Mesh(new THREE.BoxGeometry(frameThick, doorH, frameDeep), frameMat)
    fLeft.position.set(-doorW / 2 + frameThick / 2, y0 + h / 2, doorZ)
    group.add(fLeft)
    const fRight = new THREE.Mesh(new THREE.BoxGeometry(frameThick, doorH, frameDeep), frameMat)
    fRight.position.set(doorW / 2 - frameThick / 2, y0 + h / 2, doorZ)
    group.add(fRight)

    // 把手（左侧竖柄）
    const handle = new THREE.Mesh(new THREE.CylinderGeometry(0.025, 0.025, 0.55, 12), frameMat)
    handle.position.set(-doorW / 2 + 0.2, y0 + h / 2, doorZ + 0.06)
    group.add(handle)
  }

  // 6. 侧板
  const sideH = h * 0.98
  const sideD = d * 0.98
  let sideMat = null
  if (sidePanel === 'glass') sideMat = glassMaterial()
  else if (sidePanel === 'perforated') sideMat = perfMetal()
  else sideMat = new THREE.MeshStandardMaterial({ color: DARK_METAL, metalness: 0.55, roughness: 0.5, side: THREE.DoubleSide })

  const sideGeo = new THREE.PlaneGeometry(sideD, sideH)
  const left = new THREE.Mesh(sideGeo, sideMat)
  left.rotation.y = Math.PI / 2
  left.position.set(-halfW - 0.01, y0 + h / 2, 0)
  group.add(left)
  const right = new THREE.Mesh(sideGeo, sideMat)
  right.rotation.y = -Math.PI / 2
  right.position.set(halfW + 0.01, y0 + h / 2, 0)
  group.add(right)

  // 7. 后门
  if (showBack) {
    const backMat =
      sidePanel === 'perforated'
        ? perfMetal()
        : new THREE.MeshStandardMaterial({ color: 0x101520, metalness: 0.5, roughness: 0.6, side: THREE.DoubleSide })
    const back = new THREE.Mesh(new THREE.PlaneGeometry(w * 0.95, h * 0.98), backMat)
    back.position.set(0, y0 + h / 2, -halfD - 0.01)
    group.add(back)
  }

  // 8. 安装导轨（前后各一对）
  if (showRails) {
    const railW = 0.16
    const railH = h * 0.96
    const railTex = railTexture()
    const railMat = new THREE.MeshStandardMaterial({
      map: railTex,
      color: 0xffffff,
      metalness: 0.5,
      roughness: 0.5,
      side: THREE.DoubleSide,
    })
    const railGeo = new THREE.PlaneGeometry(railW, railH)
    const rx = halfW - 0.18
    const zFront = halfD - 0.12
    const zBack = -halfD + 0.12
    ;[-1, 1].forEach((s) => {
      const frontRail = new THREE.Mesh(railGeo, railMat)
      frontRail.position.set(s * rx, y0 + h / 2, zFront)
      group.add(frontRail)
      const backRail = new THREE.Mesh(railGeo, railMat)
      backRail.position.set(s * rx, y0 + h / 2, zBack)
      group.add(backRail)
    })
  }

  // 9. 顶部状态灯（前左上角）
  const ledMat = new THREE.MeshStandardMaterial({ color: statusColor, emissive: statusColor, emissiveIntensity: 1.8 })
  const led = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.07, 0.07), ledMat)
  led.position.set(-halfW + 0.25, y0 + h + 0.12, halfD + 0.04)
  group.add(led)

  // 10. 前侧占用条（左侧立柱，按 occupancyRatio 显示高度）
  if (occupancyRatio > 0.001) {
    const stripH = Math.max(0.02, occupancyRatio * h * 0.92)
    const strip = new THREE.Mesh(
      new THREE.BoxGeometry(0.08, stripH, 0.04),
      new THREE.MeshStandardMaterial({ color: statusColor, emissive: statusColor, emissiveIntensity: 0.5, transparent: true, opacity: 0.92 })
    )
    strip.position.set(-halfW + 0.06, y0 + 0.1 + stripH / 2, halfD + 0.03)
    group.add(strip)
  }

  group.userData = { kind: 'cabinet', pickMesh: frontDoorMesh }
  return group
}

// 高亮/还原整个机柜 Group 的 emissive，用于 hover 反馈。
function storeBaseEmissive(group) {
  group.traverse((obj) => {
    if (obj.material) {
      const mats = Array.isArray(obj.material) ? obj.material : [obj.material]
      mats.forEach((m) => {
        if (m.__baseEmissive === undefined) {
          m.__baseEmissive = m.emissive ? m.emissive.getHex() : 0x000000
          m.__baseIntensity = m.emissiveIntensity ?? 1
        }
      })
    }
  })
}
export function highlightCabinet(group, color = 0x38bdf8, intensity = 0.45) {
  storeBaseEmissive(group)
  group.traverse((obj) => {
    if (obj.material) {
      const mats = Array.isArray(obj.material) ? obj.material : [obj.material]
      mats.forEach((m) => {
        if (m.emissive) {
          m.emissive.setHex(color)
          m.emissiveIntensity = intensity
        }
      })
    }
  })
}
export function restoreCabinet(group) {
  group.traverse((obj) => {
    if (obj.material) {
      const mats = Array.isArray(obj.material) ? obj.material : [obj.material]
      mats.forEach((m) => {
        if (m.__baseEmissive !== undefined && m.emissive) {
          m.emissive.setHex(m.__baseEmissive)
          m.emissiveIntensity = m.__baseIntensity
        }
      })
    }
  })
}

// ====== 设备选中高亮（机房总览 / 机柜详情 共用统一风格）======

// 选中态统一强调色：琥珀金——与场景蓝调 hover 形成强对比，从任意视角都醒目。
export const SELECT_COLOR = 0xfbbf24

// 缓存材质原始 emissive（仅首次），供还原使用。
function ensureBaseEmissive(mat) {
  if (mat.__baseEmissive === undefined) {
    mat.__baseEmissive = mat.emissive ? mat.emissive.getHex() : 0x000000
    mat.__baseIntensity = mat.emissiveIntensity ?? 1
  }
}

// 对设备 Group 全部 mesh 施加/还原自发光，使选中时光晕覆盖整个设备本体
// （而非仅 chassis——前面板会遮挡 chassis，导致此前仅描边框可见、本体无光晕）。
export function setDeviceEmissive(group, hex, intensity) {
  group.traverse((obj) => {
    const mats = obj.material ? (Array.isArray(obj.material) ? obj.material : [obj.material]) : []
    mats.forEach((m) => {
      ensureBaseEmissive(m)
      if (m.emissive) {
        m.emissive.setHex(hex)
        m.emissiveIntensity = intensity
      }
    })
  })
}

export function clearDeviceEmissive(group) {
  group.traverse((obj) => {
    const mats = obj.material ? (Array.isArray(obj.material) ? obj.material : [obj.material]) : []
    mats.forEach((m) => {
      if (m.__baseEmissive !== undefined && m.emissive) {
        m.emissive.setHex(m.__baseEmissive)
        m.emissiveIntensity = m.__baseIntensity
      }
    })
  })
}

// 在设备 Group 外围生成发光描边框（LineSegments），挂到 group.parent 上随设备移动。
// depthTest:false 使描边穿透机柜外壳始终可见，确保「明显」的高亮。
export function attachSelectionBox(group, color = SELECT_COLOR) {
  detachSelectionBox(group)
  group.updateWorldMatrix(true, true)
  const box = new THREE.Box3().setFromObject(group)
  if (box.isEmpty()) return null
  const size = new THREE.Vector3()
  const center = new THREE.Vector3()
  box.getSize(size)
  box.getCenter(center)
  const geo = new THREE.BoxGeometry(size.x + 0.16, size.y + 0.16, size.z + 0.16)
  const edges = new THREE.EdgesGeometry(geo)
  const mat = new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.95, depthTest: false })
  const box3 = new THREE.LineSegments(edges, mat)
  box3.renderOrder = 999
  const parent = group.parent
  if (parent) {
    box3.position.copy(parent.worldToLocal(center.clone()))
  } else {
    box3.position.copy(center)
  }
  box3.userData.isSelectionBox = true
  group.userData.selectionBox = box3
  if (parent) parent.add(box3)
  return box3
}

export function detachSelectionBox(group) {
  const box3 = group.userData.selectionBox
  if (box3) {
    if (box3.parent) box3.parent.remove(box3)
    box3.geometry.dispose()
    box3.material.dispose()
    group.userData.selectionBox = null
  }
}

// 统一「选中」视觉：琥珀色自发光 + 外围发光描边框 + 书签高亮（若挂载）。
export function setDeviceSelected(group, on, color = SELECT_COLOR) {
  if (on) {
    setDeviceEmissive(group, color, 0.7)
    attachSelectionBox(group, color)
  } else {
    clearDeviceEmissive(group)
    detachSelectionBox(group)
  }
  const bm = group.userData.bookmark
  if (bm && bm.element && bm.element.classList) bm.element.classList.toggle('is-selected', on)
}

// 从任意子对象回溯到机柜 Group（用于射线拾取）。
export function findCabinetGroup(obj) {
  let o = obj
  while (o && !(o.userData && o.userData.kind === 'cabinet')) o = o.parent
  return o || null
}

// ====== 独立设备建模 ======

// 服务器前面板：左侧通风栅，右侧硬盘托架阵列。
function addServerFront(g, w, h, d, sizeU, accentHex, statusHex) {
  const frontZ = d / 2 + 0.02
  const ventW = w * 0.36
  const ventH = h * 0.78
  const ventMat = new THREE.MeshStandardMaterial({ color: 0x080c12, metalness: 0.3, roughness: 0.85 })
  const vent = new THREE.Mesh(new THREE.BoxGeometry(ventW, ventH, 0.02), ventMat)
  vent.position.set(-w * 0.22, 0, frontZ)
  g.add(vent)

  // 横向栅条
  const slatMat = new THREE.MeshStandardMaterial({ color: 0x252d3d, metalness: 0.5, roughness: 0.5 })
  const n = 6
  for (let i = 0; i < n; i++) {
    const slat = new THREE.Mesh(new THREE.BoxGeometry(ventW * 0.9, h * 0.015, 0.03), slatMat)
    slat.position.set(-w * 0.22, -ventH / 2 + (i + 0.5) * (ventH / n), frontZ + 0.02)
    g.add(slat)
  }

  // 右侧硬盘托架
  const rows = Math.max(2, Math.round(sizeU * 1.5))
  const cols = 3
  const bayW = w * 0.36
  const bayH = h * 0.78
  const bayMat = new THREE.MeshStandardMaterial({ color: 0x121820, metalness: 0.4, roughness: 0.55 })
  const ledMat = new THREE.MeshStandardMaterial({ color: 0x22c55e, emissive: 0x22c55e, emissiveIntensity: 1.2 })
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const bx = w * 0.18 + (c - (cols - 1) / 2) * (bayW / cols)
      const by = -bayH / 2 + (r + 0.5) * (bayH / rows)
      const drive = new THREE.Mesh(new THREE.BoxGeometry((bayW / cols) * 0.78, (bayH / rows) * 0.65, 0.03), bayMat)
      drive.position.set(bx, by, frontZ + 0.015)
      g.add(drive)
      const led = new THREE.Mesh(new THREE.BoxGeometry(0.04, 0.025, 0.015), ledMat)
      led.position.set(bx + (bayW / cols) * 0.3, by, frontZ + 0.035)
      g.add(led)
    }
  }

  // 状态灯（电源 / 运行）
  const ledMat2 = new THREE.MeshStandardMaterial({ color: statusHex, emissive: statusHex, emissiveIntensity: 2 })
  const led1 = new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.05, 0.02), ledMat2)
  led1.position.set(w * 0.42, h * 0.33, frontZ + 0.03)
  g.add(led1)
}

// 交换机前面板：多行多列端口 + 状态灯。
function addSwitchFront(g, w, h, d, accentHex, statusHex, isRouter = false) {
  const frontZ = d / 2 + 0.02
  const cols = isRouter ? 6 : 12
  const rows = 2
  const portW = (w * 0.62) / cols
  const portH = (h * 0.42) / rows
  const portMat = new THREE.MeshStandardMaterial({ color: 0x05070a, metalness: 0.2, roughness: 0.8 })
  const ledMat = new THREE.MeshStandardMaterial({ color: accentHex, emissive: accentHex, emissiveIntensity: 1.5 })
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const px = -w * 0.3 + (c + 0.5) * portW
      const py = -h * 0.05 + (r - (rows - 1) / 2) * (portH + 0.02)
      const port = new THREE.Mesh(new THREE.BoxGeometry(portW * 0.7, portH * 0.6, 0.03), portMat)
      port.position.set(px, py, frontZ + 0.015)
      g.add(port)
      const led = new THREE.Mesh(new THREE.BoxGeometry(portW * 0.22, 0.02, 0.012), ledMat)
      led.position.set(px + portW * 0.2, py + portH * 0.42, frontZ + 0.035)
      g.add(led)
    }
  }
  // Console / 管理口
  const consMat = new THREE.MeshStandardMaterial({ color: 0x111826, metalness: 0.4, roughness: 0.6 })
  const cons = new THREE.Mesh(new THREE.BoxGeometry(w * 0.08, h * 0.12, 0.03), consMat)
  cons.position.set(-w * 0.42, h * 0.08, frontZ + 0.02)
  g.add(cons)

  // 状态灯
  const ledMat2 = new THREE.MeshStandardMaterial({ color: statusHex, emissive: statusHex, emissiveIntensity: 2 })
  const led1 = new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.05, 0.02), ledMat2)
  led1.position.set(w * 0.42, h * 0.33, frontZ + 0.03)
  g.add(led1)
}

// 通用设备（防火墙/其他）：少量端口 + 指示灯列。
function addGenericFront(g, w, h, d, accentHex, statusHex) {
  const frontZ = d / 2 + 0.02
  const portMat = new THREE.MeshStandardMaterial({ color: accentHex, metalness: 0.3, roughness: 0.5 })
  for (let i = 0; i < 6; i++) {
    const port = new THREE.Mesh(new THREE.BoxGeometry(w * 0.06, h * 0.18, 0.03), portMat)
    port.position.set(-w * 0.3 + i * w * 0.09, h * 0.02, frontZ + 0.02)
    g.add(port)
  }
  const ledMat = new THREE.MeshStandardMaterial({ color: statusHex, emissive: statusHex, emissiveIntensity: 2 })
  const led1 = new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.05, 0.02), ledMat)
  led1.position.set(w * 0.42, h * 0.33, frontZ + 0.03)
  g.add(led1)
}

// 构建单个设备（返回以自身几何中心为原点的独立 Group）。
// 该 Group 可单独移动、拾取、高亮；userData 包含 device 与 pickMesh。
export function buildDevice(device, opts = {}) {
  const type = device.device_type || 'other'
  const status = device.status || '在库'
  const sizeU = device.u_height || 1
  const uHeight = opts.uHeight ?? opts.uH ?? U_H
  const width = opts.width ?? opts.w ?? RACK_W * 0.9
  const depth = opts.depth ?? opts.d ?? RACK_D * 0.82
  const height = opts.height ?? opts.h ?? sizeU * uHeight * 0.92
  const accentHex = new THREE.Color(DEVICE_TYPE_COLORS[type] || '#909399').getHex()
  const statusHex = new THREE.Color(DEVICE_STATUS_COLORS[status] || '#909399').getHex()

  const g = new THREE.Group()

  // 机箱本体（拾取 + 高亮目标）
  const chassis = new THREE.Mesh(
    new THREE.BoxGeometry(width, height, depth),
    new THREE.MeshStandardMaterial({ color: CHASSIS, metalness: 0.7, roughness: 0.42 })
  )
  chassis.castShadow = true
  chassis.receiveShadow = true
  g.add(chassis)

  // 前面板（内嵌）
  const face = new THREE.Mesh(
    new THREE.BoxGeometry(width * 0.95, height * 0.88, 0.03),
    new THREE.MeshStandardMaterial({ color: BEZEL, metalness: 0.35, roughness: 0.6 })
  )
  face.position.z = depth / 2 + 0.005
  g.add(face)

  // 挂耳（左右安装耳，前侧）
  const earMat = new THREE.MeshStandardMaterial({ color: 0x151b26, metalness: 0.6, roughness: 0.5 })
  const earGeo = new THREE.BoxGeometry(width * 0.04, height * 0.88, 0.05)
  ;[-1, 1].forEach((s) => {
    const ear = new THREE.Mesh(earGeo, earMat)
    ear.position.set(s * width * 0.48, 0, depth / 2 + 0.01)
    g.add(ear)
  })

  // 类型化前面板细节
  if (type === 'server') addServerFront(g, width, height, depth, sizeU, accentHex, statusHex)
  else if (type === 'switch') addSwitchFront(g, width, height, depth, accentHex, statusHex, false)
  else if (type === 'router') addSwitchFront(g, width, height, depth, accentHex, statusHex, true)
  else addGenericFront(g, width, height, depth, accentHex, statusHex)

  // 类型色条（顶部，便于快速识别类型）
  const bar = new THREE.Mesh(
    new THREE.BoxGeometry(width * 0.88, 0.05, 0.015),
    new THREE.MeshStandardMaterial({ color: accentHex, emissive: accentHex, emissiveIntensity: 0.4 })
  )
  bar.position.set(0, height * 0.44, depth / 2 + 0.04)
  g.add(bar)

  // 型号名牌（左下）
  const plate = new THREE.Mesh(
    new THREE.BoxGeometry(width * 0.28, height * 0.12, 0.015),
    new THREE.MeshStandardMaterial({ color: 0xc7d2e6, emissive: 0x223047, emissiveIntensity: 0.25, roughness: 0.7 })
  )
  plate.position.set(-width * 0.28, -height * 0.34, depth / 2 + 0.03)
  g.add(plate)

  g.userData = { kind: 'device', id: device.id, device, pickMesh: chassis }
  return g
}

// 将设备 Group 按 start_u / size_u 精确挂载到机柜坐标系。
// 设备中心点位于该机柜的 U 位中心高度，便于后续单独拖拽/调整。
export function setDevicePosition(deviceGroup, startU, sizeU, { uH = U_H, plinthH = PLINTH_H } = {}) {
  const y = plinthH + (startU - 1 + sizeU / 2) * uH
  deviceGroup.position.y = y
  deviceGroup.userData.startU = startU
  deviceGroup.userData.sizeU = sizeU
}

// 从任意子网格回溯到携带 device 元数据的设备 Group。
export function findDeviceGroup(obj) {
  let o = obj
  while (o && !(o.userData && o.userData.device)) o = o.parent
  return o || null
}
