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
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js'
import { DEVICE_TYPE_COLORS, DEVICE_TYPE_LABELS, isFacilityType } from '@/utils/constants'
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

// 穿孔金属贴图（用于前门、侧板、后门）。全局单例共享：每台机柜多次引用同一贴图，
// 避免重复创建 Canvas + 重复上传 GPU（机柜多时为最大纹理开销来源之一）。
let _perfTexture = null
function perfTexture() {
  if (!_perfTexture) {
    _perfTexture = makeCanvasTexture(
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
    _perfTexture.__shared = true
  }
  return _perfTexture
}

// 方孔导轨贴图（竖向两列方孔 + 每个 U 编号），U1 在底部、向上递增（与设备落位方向一致）。
// 画布高度随 U 数动态加高，保证每个 U 的编号字号可读（不再像以前每 5U 才标一个）。
// 按 totalU 缓存共享：同 U 数机柜（绝大多数同机房一致）复用同一贴图，避免重复上传 GPU。
const _railTextureCache = new Map()
function railTexture(totalU = 42) {
  let tex = _railTextureCache.get(totalU)
  if (!tex) {
    const W = 64
    const H = 512 * Math.ceil(totalU / 21) // 每 ~21U 给 512px 高度，确保 11px 字号不拥挤
    tex = makeCanvasTexture(
      (ctx, w, h) => {
        ctx.fillStyle = '#9ca6b8'
        ctx.fillRect(0, 0, w, h)
        const hole = 7
        const pad = 12
        const mx = 10
        const gap = (h - 2 * pad) / totalU
        // 方孔 + U 编号：U1 在底部向上排布，每个 U 都标注
        ctx.font = 'bold 11px sans-serif'
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        for (let u = 1; u <= totalU; u++) {
          const y = h - pad - (u - 1) * gap
          // 方孔（左右两列）
          ctx.fillStyle = '#0b0f17'
          ctx.fillRect(mx, y, hole, hole)
          ctx.fillRect(w - mx - hole, y, hole, hole)
          // 每个 U 编号（深色，落在两列方孔之间）
          ctx.fillStyle = '#1a2333'
          ctx.fillText(String(u), w / 2, y + hole / 2)
        }
      },
      W,
      H
    )
    tex.__shared = true
    _railTextureCache.set(totalU, tex)
  }
  return tex
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

  // —— 几何合并：按材质分桶收集各部件几何（已烘焙其局部变换），
  //    构建完成后每个材质桶 merge 为单个 Mesh，将机柜 Draw Call 从 ~20 降到 ~8。
  //    关键：每个材质仍为「每台机柜独立实例」(不跨机柜共享)，否则 hover/选中的
  //    per-object 自发光高亮会串色（一台高亮、整片发光）。 ——
  const buckets = new Map()
  // addPart 直接对传入几何烘焙变换（每个部件独立 new 几何，不复用，避免二次平移错误）
  function addPart(mat, geo, x = 0, y = 0, z = 0, rx = 0, ry = 0, rz = 0) {
    if (rx) geo.rotateX(rx)
    if (ry) geo.rotateY(ry)
    if (rz) geo.rotateZ(rz)
    geo.translate(x, y, z)
    let arr = buckets.get(mat)
    if (!arr) { arr = []; buckets.set(mat, arr) }
    arr.push(geo)
  }

  // 每台机柜独立材质实例（不跨机柜共享，保证高亮不串色）
  const frameMat = frameMetal()
  const darkMat = darkMetal()
  const postMat = new THREE.MeshStandardMaterial({ color: 0x0b0f17, metalness: 0.7, roughness: 0.35 })

  // 1. 底座
  addPart(frameMat, new THREE.BoxGeometry(w * 1.04, plinthH, d * 1.04), 0, plinthH / 2, 0)

  // 2. 脚轮（参考图：四个带滚轮的支撑脚）
  if (showCasters) {
    const bracketMat = new THREE.MeshStandardMaterial({ color: 0x080a0e, metalness: 0.3, roughness: 0.8 })
    const wheelMat = new THREE.MeshStandardMaterial({ color: 0x7a7a7a, metalness: 0.7, roughness: 0.4 })
    const offsets = [
      [-halfW + 0.2, -halfD + 0.2],
      [halfW - 0.2, -halfD + 0.2],
      [-halfW + 0.2, halfD - 0.2],
      [halfW - 0.2, halfD - 0.2],
    ]
    offsets.forEach(([x, z]) => {
      addPart(bracketMat, new THREE.BoxGeometry(0.14, 0.14, 0.14), x, 0.08, z)
      addPart(wheelMat, new THREE.CylinderGeometry(0.07, 0.07, 0.1, 16), x, 0.07, z, 0, 0, Math.PI / 2)
    })
  }

  // 3. 四角立柱
  const postW = 0.12
  const postD = 0.12
  const px = halfW - postW / 2
  const pz = halfD - postD / 2
  ;[
    [-px, -pz],
    [px, -pz],
    [-px, pz],
    [px, pz],
  ].forEach(([x, z]) => {
    addPart(postMat, new THREE.BoxGeometry(postW, h, postD), x, y0 + h / 2, z)
  })

  // 4. 顶框与底框
  addPart(frameMat, new THREE.BoxGeometry(w * 1.02, 0.18, d * 1.02), 0, y0 + h + 0.09, 0)
  addPart(darkMat, new THREE.BoxGeometry(w, 0.1, d), 0, y0 + 0.05, 0)

  // 5. 前门（穿孔或玻璃）+ 门框 + 把手（总览视图 frontDoor 恒为 'none'，此处逻辑保留）
  let frontDoorMesh = null
  if (frontDoor !== 'none') {
    const doorW = w * 0.95
    const doorH = h * 0.98
    const doorZ = halfD + 0.02
    const doorMat = frontDoor === 'glass' ? glassMaterial() : perfMetal()
    addPart(doorMat, new THREE.PlaneGeometry(doorW, doorH), 0, y0 + h / 2, doorZ)
    // 门框 + 把手（与底框同为深金属，复用 darkMat；合并进同一材质桶）
    const frameThick = 0.08
    const frameDeep = 0.06
    addPart(darkMat, new THREE.BoxGeometry(doorW, frameThick, frameDeep), 0, y0 + h - frameThick / 2, doorZ)
    addPart(darkMat, new THREE.BoxGeometry(doorW, frameThick, frameDeep), 0, y0 + frameThick / 2, doorZ)
    addPart(darkMat, new THREE.BoxGeometry(frameThick, doorH, frameDeep), -doorW / 2 + frameThick / 2, y0 + h / 2, doorZ)
    addPart(darkMat, new THREE.BoxGeometry(frameThick, doorH, frameDeep), doorW / 2 - frameThick / 2, y0 + h / 2, doorZ)
    addPart(darkMat, new THREE.CylinderGeometry(0.025, 0.025, 0.55, 12), -doorW / 2 + 0.2, y0 + h / 2, doorZ + 0.06, 0, 0, Math.PI / 2)
  }

  // 6. 侧板
  const sideH = h * 0.98
  const sideD = d * 0.98
  let sideMat = null
  if (sidePanel === 'glass') sideMat = glassMaterial()
  else if (sidePanel === 'perforated') sideMat = perfMetal()
  else sideMat = new THREE.MeshStandardMaterial({ color: DARK_METAL, metalness: 0.55, roughness: 0.5, side: THREE.DoubleSide })
  addPart(sideMat, new THREE.PlaneGeometry(sideD, sideH), -halfW - 0.01, y0 + h / 2, 0, 0, Math.PI / 2, 0)
  addPart(sideMat, new THREE.PlaneGeometry(sideD, sideH), halfW + 0.01, y0 + h / 2, 0, 0, -Math.PI / 2, 0)

  // 7. 后门
  if (showBack) {
    const backMat =
      sidePanel === 'perforated'
        ? perfMetal()
        : new THREE.MeshStandardMaterial({ color: 0x101520, metalness: 0.5, roughness: 0.6, side: THREE.DoubleSide })
    addPart(backMat, new THREE.PlaneGeometry(w * 0.95, h * 0.98), 0, y0 + h / 2, -halfD - 0.01)
  }

  // 8. 安装导轨（前后各一对）
  if (showRails) {
    const railW = 0.16
    const railH = h * 0.96
    const railTex = railTexture(totalU)
    const railMat = new THREE.MeshStandardMaterial({
      map: railTex,
      color: 0xffffff,
      metalness: 0.5,
      roughness: 0.5,
      side: THREE.DoubleSide,
    })
    const rx = halfW - 0.18
    const zFront = halfD - 0.12
    const zBack = -halfD + 0.12
    ;[-1, 1].forEach((s) => {
      addPart(railMat, new THREE.PlaneGeometry(railW, railH), s * rx, y0 + h / 2, zFront)
      addPart(railMat, new THREE.PlaneGeometry(railW, railH), s * rx, y0 + h / 2, zBack)
    })
  }

  // 9. 顶部状态灯（前左上角）
  const ledMat = new THREE.MeshStandardMaterial({ color: statusColor, emissive: statusColor, emissiveIntensity: 1.8 })
  addPart(ledMat, new THREE.BoxGeometry(0.16, 0.07, 0.07), -halfW + 0.25, y0 + h + 0.12, halfD + 0.04)

  // 10. 前侧占用条（左侧立柱，按 occupancyRatio 显示高度）
  if (occupancyRatio > 0.001) {
    const stripH = Math.max(0.02, occupancyRatio * h * 0.92)
    const stripMat = new THREE.MeshStandardMaterial({ color: statusColor, emissive: statusColor, emissiveIntensity: 0.5, transparent: true, opacity: 0.92 })
    addPart(stripMat, new THREE.BoxGeometry(0.08, stripH, 0.04), -halfW + 0.06, y0 + 0.1 + stripH / 2, halfD + 0.03)
  }

  // —— 合并：每个材质桶 → 单个 Mesh（降 Draw Call）——
  const castMats = new Set([frameMat, darkMat, postMat]) // 仅实心金属件投射阴影
  buckets.forEach((geos, mat) => {
    const merged = mergeGeometries(geos, false)
    geos.forEach((g) => g.dispose())
    const mesh = new THREE.Mesh(merged, mat)
    mesh.castShadow = castMats.has(mat)
    mesh.receiveShadow = !mat.isMeshPhysicalMaterial // 玻璃不接收阴影（透明）
    group.add(mesh)
  })

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
// 判断 obj 是否位于「设备子树」内（机柜高亮/还原需跳过，避免覆盖设备选中高亮）。
function inDeviceSubtree(obj, root) {
  let o = obj
  while (o && o !== root) {
    if (o.userData && o.userData.kind === 'device') return true
    o = o.parent
  }
  return false
}
export function highlightCabinet(group, color = 0x38bdf8, intensity = 0.45) {
  storeBaseEmissive(group)
  group.traverse((obj) => {
    // 跳过设备子树：仅高亮机柜外壳，保护设备自身的选中/悬停高亮不被覆盖
    if (inDeviceSubtree(obj, group)) return
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
    if (inDeviceSubtree(obj, group)) return
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

// 选中态统一强调色：亮红——与所有类型色（蓝/绿/青/琥珀）均高对比，一眼可辨。
export const SELECT_COLOR = 0xef4444

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

// 统一「选中」视觉：选中色自发光（设备本体 + 真实前面板 + 类型标签徽标微微发光）
// + 书签高亮（若挂载）。前面板 / 徽标均为 MeshStandardMaterial，支持 emissive 辉光。
export function setDeviceSelected(group, on, color = SELECT_COLOR) {
  if (on) {
    setDeviceEmissive(group, color, 0.7)
  } else {
    clearDeviceEmissive(group)
  }
  // 真实前面板（厚设备）单独调低发光强度，避免 0.7 过曝冲淡端口细节
  const rf = group.userData?.realisticFace
  if (rf && rf.material && rf.material.emissive) {
    if (on) {
      rf.material.emissive.setHex(color)
      rf.material.emissiveIntensity = 0.45
    } else {
      rf.material.emissive.setHex(0x000000)
      rf.material.emissiveIntensity = 0
    }
    rf.material.needsUpdate = true
  }
  // 类型徽标（所有设备左上角常驻）：emissive 微微发光 + 选中态贴图切换为红底
  const plane = group.userData?.typeFacePlane
  if (plane && plane.material && plane.material.emissive) {
    if (on) {
      plane.material.emissive.setHex(color)
      plane.material.emissiveIntensity = 0.4
    } else {
      plane.material.emissive.setHex(0x000000)
      plane.material.emissiveIntensity = 0
    }
    plane.material.needsUpdate = true
  }
  if (plane && plane.material) {
    const d = group.userData.device
    const tex = badgeTexture(d, group.userData.accentHex, on, color)
    if (plane.material.map && !plane.material.map.__shared) plane.material.map.dispose()
    plane.material.map = tex
    plane.material.needsUpdate = true
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

// ====== 真实前面板（程序化 Canvas 贴图，单 mesh 高性能）======
// 所有设备（薄/厚统一）真实前面板：按类型绘制端口阵列 / SFP 笼 / 业务板卡槽 / LCD / 通风栅等细节。
// 不含英文铭牌（品牌以类型色细条暗示），设备身份交给左上角中文类型徽标。
// 选用 CanvasTexture 而非几何堆砌：每台设备仅 1 个 mesh，远轻于数十个端口方块，保持 60fps。

function roundRect(ctx, x, y, w, h, r) {
  const rr = Math.min(r, w / 2, h / 2)
  ctx.beginPath()
  ctx.moveTo(x + rr, y)
  ctx.arcTo(x + w, y, x + w, y + h, rr)
  ctx.arcTo(x + w, y + h, x, y + h, rr)
  ctx.arcTo(x, y + h, x, y, rr)
  ctx.arcTo(x, y, x + w, y, rr)
  ctx.closePath()
}

function drawLED(ctx, x, y, color, r = 7) {
  ctx.fillStyle = color
  ctx.beginPath()
  ctx.arc(x, y, r, 0, Math.PI * 2)
  ctx.fill()
  ctx.fillStyle = 'rgba(255,255,255,0.5)'
  ctx.beginPath()
  ctx.arc(x - r * 0.3, y - r * 0.3, r * 0.35, 0, Math.PI * 2)
  ctx.fill()
}

// 服务器：左通风栅 + 右硬盘托架 + 状态灯
function drawServerFace(ctx, W, H, ac) {
  const padX = W * 0.06
  const padY = H * 0.1
  const leftW = (W - 2 * padX) * 0.42
  // 通风栅
  ctx.fillStyle = '#0c1119'
  roundRect(ctx, padX, padY, leftW, H - 2 * padY, 10)
  ctx.fill()
  ctx.strokeStyle = 'rgba(255,255,255,0.08)'
  ctx.lineWidth = 3
  const slots = Math.max(6, Math.floor((H - 2 * padY) / 22))
  for (let i = 1; i < slots; i++) {
    const y = padY + (i * (H - 2 * padY)) / slots
    ctx.beginPath()
    ctx.moveTo(padX + 14, y)
    ctx.lineTo(padX + leftW - 14, y)
    ctx.stroke()
  }
  // 硬盘托架
  const rx = padX + leftW + W * 0.04
  const rw = W - padX - rx
  const rows = Math.max(2, Math.min(6, Math.floor((H - 2 * padY) / (H * 0.16))))
  const gap = ((H - 2 * padY) - rows * H * 0.11) / (rows + 1)
  for (let r = 0; r < rows; r++) {
    const y = padY + gap + r * (H * 0.11 + gap)
    ctx.fillStyle = '#1b2230'
    roundRect(ctx, rx, y, rw, H * 0.11, 8)
    ctx.fill()
    ctx.strokeStyle = ac
    ctx.lineWidth = 3
    ctx.stroke()
    ctx.fillStyle = 'rgba(255,255,255,0.12)'
    ctx.fillRect(rx + rw * 0.04, y + H * 0.045, rw * 0.5, H * 0.02)
  }
  drawLED(ctx, padX + 18, padY - 2, '#22c55e')
  drawLED(ctx, padX + 44, padY - 2, '#3b82f6')
}

// 交换机：RJ45 端口阵列 + SFP 笼 + 状态灯
function drawSwitchFace(ctx, W, H, ac) {
  const padX = W * 0.05
  const padY = H * 0.14
  const areaW = (W - 2 * padX) * 0.8
  const cols = W > 900 ? 24 : 16
  const rows = Math.max(2, Math.min(5, Math.floor((H - 2 * padY) / (H * 0.2))))
  const cw = areaW / cols
  const chh = (H - 2 * padY) / rows
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const x = padX + c * cw + cw * 0.15
      const y = padY + r * chh + chh * 0.2
      const pw = cw * 0.7
      const ph = chh * 0.6
      ctx.fillStyle = '#070b11'
      roundRect(ctx, x, y, pw, ph, 3)
      ctx.fill()
      ctx.strokeStyle = 'rgba(255,255,255,0.12)'
      ctx.lineWidth = 1.5
      ctx.stroke()
      ctx.fillStyle = c % 2 === 0 ? '#22c55e' : '#16a34a'
      ctx.beginPath()
      ctx.arc(x + pw * 0.5, y - 4, 2.5, 0, Math.PI * 2)
      ctx.fill()
    }
  }
  // SFP 笼
  const sx = padX + areaW + W * 0.02
  const sw = W - padX - sx
  const srows = Math.min(rows, 4)
  const sh = (H - 2 * padY) / srows
  for (let r = 0; r < srows; r++) {
    const y = padY + r * sh + sh * 0.15
    ctx.fillStyle = '#0a0f17'
    roundRect(ctx, sx, y, sw * 0.8, sh * 0.7, 4)
    ctx.fill()
    ctx.strokeStyle = ac
    ctx.lineWidth = 2
    ctx.stroke()
  }
  drawLED(ctx, padX + 10, padY - 6, '#22c55e')
  drawLED(ctx, padX + 36, padY - 6, '#eab308')
}

// 路由器：竖向业务板卡槽 + 底部管理口 + PSU 通风
function drawRouterFace(ctx, W, H, ac) {
  const padX = W * 0.05
  const padY = H * 0.1
  const blades = W > 900 ? 6 : 4
  const bw = (W - 2 * padX) / blades
  for (let i = 0; i < blades; i++) {
    const x = padX + i * bw + bw * 0.12
    ctx.fillStyle = '#11161f'
    roundRect(ctx, x, padY, bw * 0.76, H - 2 * padY - H * 0.12, 8)
    ctx.fill()
    ctx.strokeStyle = 'rgba(255,255,255,0.1)'
    ctx.lineWidth = 2
    ctx.stroke()
    ctx.fillStyle = ac
    ctx.fillRect(x + bw * 0.3, padY + 8, bw * 0.16, H * 0.05)
  }
  const by = H - padY - H * 0.1
  ctx.fillStyle = '#0c1119'
  roundRect(ctx, padX, by, W - 2 * padX, H * 0.08, 6)
  ctx.fill()
  for (let i = 0; i < 8; i++) {
    drawLED(ctx, padX + 20 + (i * (W - 2 * padX - 40)) / 8, by + H * 0.04, '#22c55e')
  }
}

// 安全设备：中央 LCD + 两侧端口簇 + 底部 PSU 通风
function drawSecurityFace(ctx, W, H, ac) {
  const padX = W * 0.05
  const padY = H * 0.12
  const lw = (W - 2 * padX) * 0.42
  const lx = (W - lw) / 2
  ctx.fillStyle = '#04141a'
  roundRect(ctx, lx, padY, lw, H - 2 * padY, 8)
  ctx.fill()
  ctx.strokeStyle = ac
  ctx.lineWidth = 3
  ctx.stroke()
  ctx.fillStyle = '#22d3ee'
  ctx.font = 'bold 26px monospace'
  ctx.textAlign = 'left'
  ctx.textBaseline = 'middle'
  ctx.fillText('> SECURE OS', lx + 16, padY + (H - 2 * padY) * 0.35)
  ctx.fillText('  STATUS: OK', lx + 16, padY + (H - 2 * padY) * 0.6)
  for (const side of [-1, 1]) {
    const px = side < 0 ? padX : W - padX - (W - 2 * padX) * 0.22
    const pw = (W - 2 * padX) * 0.22
    const rows = Math.min(4, Math.floor((H - 2 * padY) / (H * 0.18)))
    const chh = (H - 2 * padY) / rows
    for (let r = 0; r < rows; r++) {
      const y = padY + r * chh + chh * 0.25
      ctx.fillStyle = '#070b11'
      roundRect(ctx, px + pw * 0.2, y, pw * 0.6, chh * 0.5, 3)
      ctx.fill()
      drawLED(ctx, px + pw * 0.5, y - 4, '#22c55e')
    }
  }
  const by = H - padY - H * 0.08
  ctx.fillStyle = '#0c1119'
  roundRect(ctx, padX, by, W - 2 * padX, H * 0.07, 6)
  ctx.fill()
}

// 配线架（非资产）：高密度 RJ45 端口阵列（双排）+ 中部理线环，明显区别于交换机端口面。
function drawPatchFace(ctx, W, H, ac) {
  const padX = W * 0.05
  const padY = H * 0.16
  const rows = 2
  const cols = W > 900 ? 24 : 16
  const areaW = W - 2 * padX
  const cw = areaW / cols
  const chh = (H - 2 * padY) / rows
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const x = padX + c * cw + cw * 0.18
      const y = padY + r * chh + chh * 0.25
      const pw = cw * 0.64
      const ph = chh * 0.5
      // 端口方块（RJ45 轮廓）
      ctx.fillStyle = '#0a0f17'
      roundRect(ctx, x, y, pw, ph, 2)
      ctx.fill()
      ctx.strokeStyle = 'rgba(255,255,255,0.14)'
      ctx.lineWidth = 1.5
      ctx.stroke()
      // 端口内两束触点
      ctx.fillStyle = '#cbd5e1'
      ctx.fillRect(x + pw * 0.2, y + ph * 0.3, pw * 0.6, ph * 0.12)
      ctx.fillRect(x + pw * 0.2, y + ph * 0.55, pw * 0.6, ph * 0.12)
      // 端口指示灯
      ctx.fillStyle = c % 2 === 0 ? '#22c55e' : '#16a34a'
      ctx.beginPath()
      ctx.arc(x + pw * 0.5, y - 4, 2.5, 0, Math.PI * 2)
      ctx.fill()
    }
  }
  // 中部理线环（横贯，强调配线架特征）
  ctx.fillStyle = ac
  ctx.fillRect(padX, H / 2 - 3, areaW, 6)
}

// ODF配线架（非资产）：多排光纤适配器（圆耦合器，蓝/绿/琥珀区分单多模），区别于铜缆配线架。
function drawOdfFace(ctx, W, H, ac) {
  const padX = W * 0.06
  const padY = H * 0.12
  const rows = Math.max(3, Math.min(6, Math.floor((H - 2 * padY) / (H * 0.14))))
  const cols = 12
  const areaW = W - 2 * padX
  const cw = areaW / cols
  const chh = (H - 2 * padY) / rows
  const couplers = ['#3b82f6', '#22c55e', '#f59e0b'] // 蓝=单模 / 绿=OS2 / 琥珀=多模
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const cx = padX + c * cw + cw * 0.5
      const cy = padY + r * chh + chh * 0.5
      const rad = Math.min(cw, chh) * 0.3
      // 适配器面板底座
      ctx.fillStyle = '#0a0f17'
      roundRect(ctx, cx - rad * 1.4, cy - rad * 1.4, rad * 2.8, rad * 2.8, 3)
      ctx.fill()
      // 耦合器（圆，中心暗孔）
      ctx.fillStyle = couplers[(r + c) % couplers.length]
      ctx.beginPath()
      ctx.arc(cx, cy, rad, 0, Math.PI * 2)
      ctx.fill()
      ctx.fillStyle = '#0b0f17'
      ctx.beginPath()
      ctx.arc(cx, cy, rad * 0.45, 0, Math.PI * 2)
      ctx.fill()
    }
  }
  // 顶部类型标记条
  ctx.fillStyle = ac
  ctx.fillRect(0, H * 0.04, W, 6)
  drawLED(ctx, padX + 16, H * 0.1, '#22c55e')
}

// 其他/通用：简单端口列 + 通风
function drawGenericFace(ctx, W, H, ac) {  const padX = W * 0.1
  const padY = H * 0.15
  const cols = 6
  const rows = Math.max(2, Math.min(5, Math.floor((H - 2 * padY) / (H * 0.18))))
  const cw = (W - 2 * padX) / cols
  const chh = (H - 2 * padY) / rows
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const x = padX + c * cw + cw * 0.2
      const y = padY + r * chh + chh * 0.25
      ctx.fillStyle = '#070b11'
      roundRect(ctx, x, y, cw * 0.6, chh * 0.5, 3)
      ctx.fill()
      drawLED(ctx, x + cw * 0.3, y - 3, '#22c55e')
    }
  }
}

// 真实前面板贴图（按类型选择细节绘制）
// 真实前面板贴图：按「类型 + 粗粒度宽高比」缓存共享，避免逐设备重复上传 GPU
// （数百台设备 → 仅若干张贴图）。accent 由类型决定（DEVICE_TYPE_COLORS[type]），
// 同 key 内一致；选中态仅改材质 emissive，不替换此贴图，故可安全跨设备共享。
const _faceTextureCache = new Map()
function realisticFaceTexture(device, w, h, accentHex) {
  const type = device.device_type || 'other'
  const aspect = w / h
  const key = type + '@' + aspect.toFixed(2)
  let tex = _faceTextureCache.get(key)
  if (!tex) {
    const ac = '#' + (accentHex & 0xffffff).toString(16).padStart(6, '0')
    const cw = 1024
    const ch = Math.max(160, Math.round((1024 * h) / w))
    tex = makeCanvasTexture(
      (ctx, W, H) => {
        const grad = ctx.createLinearGradient(0, 0, 0, H)
        grad.addColorStop(0, '#222a38')
        grad.addColorStop(0.5, '#161c27')
        grad.addColorStop(1, '#0d1219')
        ctx.fillStyle = grad
        ctx.fillRect(0, 0, W, H)
        ctx.strokeStyle = 'rgba(255,255,255,0.06)'
        ctx.lineWidth = 4
        ctx.strokeRect(6, 6, W - 12, H - 12)
        // 顶部类型色品牌条（暗示类型/品牌，无英文）
        ctx.fillStyle = ac
        ctx.fillRect(0, 0, W, 10)
        if (type === 'server') drawServerFace(ctx, W, H, ac)
        else if (type === 'switch') drawSwitchFace(ctx, W, H, ac)
        else if (type === 'router') drawRouterFace(ctx, W, H, ac)
        else if (type === 'security') drawSecurityFace(ctx, W, H, ac)
        else if (type === 'patch') drawPatchFace(ctx, W, H, ac)
        else if (type === 'odf') drawOdfFace(ctx, W, H, ac)
        // 其他设施（非资产）前面板近似配线架
        else if (type === 'other_facility') drawPatchFace(ctx, W, H, ac)
        else drawGenericFace(ctx, W, H, ac)
      },
      cw,
      ch
    )
    tex.__shared = true
    _faceTextureCache.set(key, tex)
  }
  return tex
}

// 真实前面板平面（覆盖 bezel 前缘，支持选中 emissive 发光）
function makeRealisticFace(device, w, h, d, accentHex) {
  const tex = realisticFaceTexture(device, w, h, accentHex)
  const mat = new THREE.MeshStandardMaterial({
    map: tex,
    emissive: 0x000000,
    emissiveIntensity: 0,
    roughness: 0.5,
    metalness: 0.15,
  })
  const plane = new THREE.Mesh(new THREE.PlaneGeometry(w * 0.95, h * 0.9), mat)
  plane.position.set(0, 0, d / 2 + 0.025)
  return plane
}

// 左上角中文类型徽标贴图（紧凑圆角卡片，白字 + 类型色底；选中改红底）
function badgeTexture(device, accentHex, selected = false, selColor = SELECT_COLOR) {
  const cw = 256
  const ch = 96
  const selHex = typeof selColor === 'string' ? selColor : '#' + (selColor & 0xffffff).toString(16).padStart(6, '0')
  const ac = '#' + (accentHex & 0xffffff).toString(16).padStart(6, '0')
  const label = DEVICE_TYPE_LABELS[device.device_type] || '设备'
  return makeCanvasTexture(
    (ctx, W, H) => {
      ctx.clearRect(0, 0, W, H)
      ctx.fillStyle = selected ? selHex : ac
      roundRect(ctx, 4, 4, W - 8, H - 8, 16)
      ctx.fill()
      ctx.fillStyle = '#ffffff'
      ctx.font = 'bold 44px sans-serif'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText(label, W / 2, H / 2)
    },
    cw,
    ch
  )
}

// 左上角中文类型徽标平面（所有设备常驻，最外层 Z，选中发光）
// 尺寸默认按宽度取 w*0.26；但薄设备(1U/2U)高度受限，按机箱高度收敛为小标签，避免溢出。
function makeTypeBadge(device, w, h, d, accentHex) {
  const tex = badgeTexture(device, accentHex)
  const mat = new THREE.MeshStandardMaterial({
    map: tex,
    emissive: 0x000000,
    emissiveIntensity: 0,
    roughness: 0.4,
    metalness: 0.05,
    transparent: true,
  })
  const innerW = w * 0.9
  const innerH = h * 0.86
  const aspect = 256 / 96 // 徽标贴图宽高比（横版）
  let badgeW = w * 0.26
  let badgeH = badgeW / aspect
  const maxBH = innerH * 0.72 // 薄设备高度上限，超出则按高度收敛
  if (badgeH > maxBH) {
    badgeH = maxBH
    badgeW = badgeH * aspect
  }
  const plane = new THREE.Mesh(new THREE.PlaneGeometry(badgeW, badgeH), mat)
  // 左上角常驻（薄设备收敛后更小、更贴边）
  plane.position.set(-innerW / 2 + badgeW / 2 + w * 0.02, innerH / 2 - badgeH / 2 - h * 0.02, d / 2 + 0.06)
  return plane
}

// 构建单个设备（返回以自身几何中心为原点的独立 Group）。
// 该 Group 可单独移动、拾取、高亮；userData 包含 device 与 pickMesh。
export function buildDevice(device, opts = {}) {
  const type = device.device_type || 'other'
  const sizeU = device.u_height || 1
  const uHeight = opts.uHeight ?? opts.uH ?? U_H
  const width = opts.width ?? opts.w ?? RACK_W * 0.9
  const isFacility = isFacilityType(type)
  // 设施（非资产）机箱更浅（配线架/ODF 通常浅于服务器），与资产设备形成独立形态。
  const depth = (opts.depth ?? opts.d ?? RACK_D * 0.82) * (isFacility ? 0.8 : 1)
  const height = opts.height ?? opts.h ?? sizeU * uHeight * 0.92
  const accentHex = new THREE.Color(DEVICE_TYPE_COLORS[type] || '#909399').getHex()
  // 设施机箱用偏中性浅灰金属，区别于资产深枪灰；前面板纹理已按类型绘制。
  const chassisColor = isFacility ? 0x39414f : CHASSIS

  const g = new THREE.Group()

  // 设备主体合并：机箱 + 前面板 + 左右挂耳 合并为单个 Mesh（含材质数组），
  // Draw Call 由 4 降到 1，且保留独立可拾取对象（作为 pickMesh）。
  // 合并用 useGroups=true 保留各子几何的分组，使不同材质（机箱/面板/挂耳）各取所需，
  // 同时 setDeviceEmissive 仍可遍历材质数组对其统一施加选中自发光。
  const chassisMat = new THREE.MeshStandardMaterial({ color: chassisColor, metalness: 0.7, roughness: 0.42 })
  const faceMat = new THREE.MeshStandardMaterial({ color: BEZEL, metalness: 0.35, roughness: 0.6 })
  const earMat = new THREE.MeshStandardMaterial({ color: 0x151b26, metalness: 0.6, roughness: 0.5 })
  const chassisGeo = new THREE.BoxGeometry(width, height, depth)
  const faceGeo = new THREE.BoxGeometry(width * 0.95, height * 0.88, 0.03)
  const earGeo = new THREE.BoxGeometry(width * 0.04, height * 0.88, 0.05)
  const chassisMesh = new THREE.Mesh(chassisGeo)
  chassisMesh.castShadow = true
  chassisMesh.receiveShadow = true
  const faceMesh = new THREE.Mesh(faceGeo)
  faceMesh.position.z = depth / 2 + 0.005
  const earL = new THREE.Mesh(earGeo)
  earL.position.set(-width * 0.48, 0, depth / 2 + 0.01)
  const earR = new THREE.Mesh(earGeo)
  earR.position.set(width * 0.48, 0, depth / 2 + 0.01)
  const bodyParts = [chassisMesh, faceMesh, earL, earR]
  bodyParts.forEach((p) => p.updateMatrix())
  const bodyGeo = mergeGeometries(
    bodyParts.map((p) => p.geometry.clone().applyMatrix4(p.matrix)),
    true
  )
  // 释放源几何（合并后的 bodyGeo 已包含其数据）
  chassisGeo.dispose()
  faceGeo.dispose()
  earGeo.dispose()
  const body = new THREE.Mesh(bodyGeo, [chassisMat, faceMat, earMat, earMat])
  body.castShadow = true
  body.receiveShadow = true
  g.add(body)

  // 前面板：所有设备统一「真实前面板（程序化端口阵列）+ 左上角中文类型徽标」。
  // 薄设备(≤2U)徽标按机箱高度自动收敛为小标签，真实端口阵列照常绘制，不牺牲可读性。
  const realisticFace = makeRealisticFace(device, width, height, depth, accentHex)
  g.add(realisticFace)
  const labelMesh = makeTypeBadge(device, width, height, depth, accentHex)
  labelMesh.userData.isTypeFace = true
  g.add(labelMesh)

  g.userData = {
    kind: 'device',
    id: device.id,
    device,
    pickMesh: body,
    typeFacePlane: labelMesh,
    faceIsBadge: true,
    realisticFace,
    accentHex,
    faceW: width,
    faceH: height,
  }
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

// —— 冻结世界矩阵 ——
// 静态场景（机柜/设备/标签）构建完成后调用一次：先强制更新一次世界矩阵，
// 再对所有静态后代关闭 matrixAutoUpdate，使后续每帧渲染不再重算上千个对象的
// world matrix（此项在数百机柜场景下是 CPU 端最重的逐帧开销之一）。
// 动态对象（线缆 Line / 流动箭头）按其类型或 userData.dynamic 跳过，保持逐帧更新。
export function freezeWorld(group) {
  if (!group) return
  group.updateMatrixWorld(true)
  group.traverse((o) => {
    if (o === group) return // 保留根容器自身自动更新（如需整体平移仍可联动子节点）
    if (o.isLine || o.isLineSegments || o.userData?.dynamic) return // 跳过线缆等动态对象
    o.matrixAutoUpdate = false
  })
}
