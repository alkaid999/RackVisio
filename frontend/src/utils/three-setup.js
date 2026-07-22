// 共享的 Three.js 引擎与工具函数。
// 本文件为「机房3D总览 / 机柜3D详情」两个视图共用的底层：
//   · createEngine  —— 创建渲染器 / 场景 / 相机 / 控制器 / 灯光 / 环境反射 / 标签层 / 自适应 / 释放
//   · makeLabel     —— 创建 CSS2D 文字标签（机柜编号 / 设备名）
//   · makeCanvasTexture —— 程序化 Canvas 贴图（地面瓷砖 / 穿孔板 / 导轨孔）
//
// 视图层只依赖这三个导出，不关心 WebGL 细节。

import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { CSS2DRenderer, CSS2DObject } from 'three/examples/jsm/renderers/CSS2DRenderer.js'
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js'

// —— 程序化 Canvas 贴图 ——
// draw(ctx, w, h) 内自由绘制；repeat 为 [x, y] 平铺次数（地板用）。
export function makeCanvasTexture(draw, w = 256, h = 256, repeat) {
  const canvas = document.createElement('canvas')
  canvas.width = w
  canvas.height = h
  const ctx = canvas.getContext('2d')
  draw(ctx, w, h)
  const tex = new THREE.CanvasTexture(canvas)
  tex.wrapS = THREE.RepeatWrapping
  tex.wrapT = THREE.RepeatWrapping
  tex.colorSpace = THREE.SRGBColorSpace
  if (repeat) tex.repeat.set(repeat[0], repeat[1])
  tex.anisotropy = 4
  tex.needsUpdate = true
  return tex
}

// —— CSS2D 文字标签 ——
// 返回可直接 add 到 Object3D 的标签对象；样式由 .three-label(.is-rack|.is-device) 控制。
export function makeLabel(text, className = '') {
  const div = document.createElement('div')
  div.className = 'three-label ' + (className || '')
  div.textContent = text
  const obj = new CSS2DObject(div)
  // 避免标签被后期处理影响；保持屏幕像素清晰
  obj.center.set(0.5, 0.5)
  return obj
}

// —— 创建引擎 ——
// 返回 { renderer, scene, camera, controls, container, setCursor, dispose }
export function createEngine(container, opts = {}) {
  const background = opts.background ?? 0x0b1220
  const fog = opts.fog ?? false
  const fogNear = opts.fogNear ?? 40
  const fogFar = opts.fogFar ?? 220
  const targetY = opts.targetY ?? 6
  const minDistance = opts.minDistance ?? 8
  const maxDistance = opts.maxDistance ?? 260
  const cameraPosition = opts.cameraPosition ?? [34, 28, 42]
  const fov = opts.fov ?? 50
  const freeMove = opts.freeMove ?? true
  const moveSpeed = opts.moveSpeed ?? 26
  let onTick = typeof opts.onTick === 'function' ? opts.onTick : null

  const getW = () => Math.max(1, container.clientWidth || window.innerWidth)
  const getH = () => Math.max(1, container.clientHeight || window.innerHeight)

  // 场景
  const scene = new THREE.Scene()
  scene.background = new THREE.Color(background)
  if (fog) scene.fog = new THREE.Fog(background, fogNear, fogFar)

  // 相机
  const camera = new THREE.PerspectiveCamera(fov, getW() / getH(), 0.1, 4000)
  camera.position.set(cameraPosition[0], cameraPosition[1], cameraPosition[2])

  // 渲染器
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: 'high-performance' })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))
  renderer.setSize(getW(), getH())
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFSoftShadowMap
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.05
  renderer.outputColorSpace = THREE.SRGBColorSpace
  renderer.domElement.style.display = 'block'
  renderer.domElement.style.width = '100%'
  renderer.domElement.style.height = '100%'
  container.appendChild(renderer.domElement)

  // 环境贴图（真实金属反射）—— RoomEnvironment 经 PMREM 预滤波
  const pmrem = new THREE.PMREMGenerator(renderer)
  pmrem.compileEquirectangularShader()
  let envRT = null
  try {
    envRT = pmrem.fromScene(new RoomEnvironment(), 0.04)
    scene.environment = envRT.texture
  } catch (e) {
    console.warn('[three-setup] environment map failed', e)
  }

  // CSS2D 标签层（叠在 canvas 之上，不拦截指针）
  const labelRenderer = new CSS2DRenderer()
  labelRenderer.setSize(getW(), getH())
  labelRenderer.domElement.style.position = 'absolute'
  labelRenderer.domElement.style.top = '0'
  labelRenderer.domElement.style.left = '0'
  labelRenderer.domElement.style.pointerEvents = 'none'
  container.appendChild(labelRenderer.domElement)

  // 灯光（半球 + 环境 + 主光投影 + 补光 + 轮廓光）
  scene.add(new THREE.HemisphereLight(0xbcd4ff, 0x141c2c, 0.55))
  scene.add(new THREE.AmbientLight(0xffffff, 0.22))

  const key = new THREE.DirectionalLight(0xffffff, 1.15)
  key.position.set(24, 44, 28)
  key.castShadow = true
  key.shadow.mapSize.set(2048, 2048)
  key.shadow.camera.near = 1
  key.shadow.camera.far = 300
  key.shadow.camera.left = -80
  key.shadow.camera.right = 80
  key.shadow.camera.top = 80
  key.shadow.camera.bottom = -80
  key.shadow.bias = -0.0004
  scene.add(key)

  const fill = new THREE.DirectionalLight(0x88aaff, 0.4)
  fill.position.set(-28, 22, -18)
  scene.add(fill)

  const rim = new THREE.DirectionalLight(0xffffff, 0.3)
  rim.position.set(0, 12, -34)
  scene.add(rim)

  // 控制器
  const controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.dampingFactor = 0.08
  controls.target.set(0, targetY, 0)
  controls.minDistance = minDistance
  controls.maxDistance = maxDistance
  // 垂直旋转范围：保留「近乎 360°」的巡检体验（可仰望天花板 / 俯视地板），
  // 但给极角留极小余量（epsilon），避免恰好对准天顶/地底时 OrbitControls 出现
  // 「万向节死锁」式视角突跳——拖拽到顶/底时画面会突然翻转（即用户反馈的
  // 「放大贴近机柜后上下拖拽镜头被改变」异常）。epsilon 仅约 1°，肉眼无感。
  const minPolarAngle = opts.minPolarAngle ?? 0.02
  const maxPolarAngle = opts.maxPolarAngle ?? Math.PI - 0.02
  controls.minPolarAngle = minPolarAngle
  controls.maxPolarAngle = maxPolarAngle
  controls.update()

  // —— 第一人称「看转」(FPS look)：左键拖拽绕相机自身原地旋转（yaw + pitch），
  //    替代 OrbitControls 默认的「绕 target 公转」。后者在相机贴近机柜时，target 仍在
  //    机房中心，一拖拽相机就被甩到中心四周 —— 表现为「莫名跳到另一个镜头」。
  //    实现要点：拖拽时只改相机朝向(原位旋转)，并把 controls.target 同步到相机正前方
  //    lookDist 处，使 OrbitControls.update() 每帧 camera.lookAt(target) 复现同一朝向、
  //    且「相机→target」距离恒定（缩放/平移不跳变）。滚轮缩放、右键平移仍由 OrbitControls 负责。
  controls.enableRotate = false // 关闭默认左键公转，改由下方自定义原地看转接管
  const _fwd = new THREE.Vector3()
  const _euler = new THREE.Euler(0, 0, 0, 'YXZ')
  let lookYaw = 0
  let lookPitch = 0
  let lookDist = camera.position.distanceTo(controls.target) || (minDistance || 8)
  const LOOK_SENS = 0.0026 // 鼠标像素 → 弧度 灵敏度
  const LOOK_EPS = 0.02 // 俯仰限位（避开天顶/地底万向节死锁）
  function syncLookAnglesFromCamera() {
    camera.getWorldDirection(_fwd)
    lookYaw = Math.atan2(-_fwd.x, -_fwd.z)
    lookPitch = Math.asin(THREE.MathUtils.clamp(_fwd.y, -1, 1))
  }
  function applyLook() {
    lookPitch = Math.max(-Math.PI / 2 + LOOK_EPS, Math.min(Math.PI / 2 - LOOK_EPS, lookPitch))
    _euler.set(lookPitch, lookYaw, 0, 'YXZ')
    camera.quaternion.setFromEuler(_euler)
    // target 置于相机正前方 lookDist：OrbitControls.update 据此复现朝向且距离不变
    _fwd.set(0, 0, -1).applyEuler(_euler)
    controls.target.copy(camera.position).add(_fwd.multiplyScalar(lookDist))
  }
  syncLookAnglesFromCamera()
  applyLook() // 初始化：把 target 拉到相机正前方，后续看转才是在位旋转
  let lookDragging = false
  let lastPX = 0
  let lastPY = 0
  function onLookPointerDown(e) {
    if (e.button !== 0) return // 仅左键接管看转（右键留给 OrbitControls 平移）
    lookDragging = true
    lastPX = e.clientX
    lastPY = e.clientY
    lookDist = camera.position.distanceTo(controls.target) || lookDist
    try { renderer.domElement.setPointerCapture(e.pointerId) } catch (_) { /* noop */ }
  }
  function onLookPointerMove(e) {
    if (!lookDragging) return
    const dx = e.clientX - lastPX
    const dy = e.clientY - lastPY
    lastPX = e.clientX
    lastPY = e.clientY
    lookYaw -= dx * LOOK_SENS
    lookPitch -= dy * LOOK_SENS
    applyLook()
  }
  function onLookPointerUp(e) {
    if (e.button !== 0) return
    lookDragging = false
    lookDist = camera.position.distanceTo(controls.target) || lookDist
  }
  renderer.domElement.addEventListener('pointerdown', onLookPointerDown)
  renderer.domElement.addEventListener('pointermove', onLookPointerMove)
  window.addEventListener('pointerup', onLookPointerUp)

  // —— 自由视角移动（受边界约束）：
  //    W/S = 沿「当前视线方向」前进 / 后退（第一人称 fly，含俯仰分量）；
  //    ↑/↓ = 沿「世界 Y 轴」垂直平移视角（上移 / 下移），与视线俯仰无关；
  //    A/D（或 ←/→）= 沿「相机右向」左右平移（strafe）；
  //    旋转改为第一人称原地看转（见上方自定义左键拖拽 look 逻辑：绕相机自身旋转而非绕
  //    target 公转），缩放(拉近/拉远)由滚轮负责、右键平移由 OrbitControls 负责。
  //    关键修复：移动时「保持相机→目标(target)偏移不变」——无论怎么移动、是否撞到边界，
  //    相机到目标的距离恒定，因此缩放百分比(zoom)绝不会随移动跳变（移动与缩放彻底解耦）。
  //    边界由 createEngine({ moveBounds }) 或 setMoveBounds() 注入，确保「既能飞出机房纵览、
  //    又不会无限远离」的合理范围。moveBounds 缺省时给出较大兜底边界。 ——
  const moveKeys = new Set()
  let lastMoveT = performance.now()
  const _right = new THREE.Vector3()
  const _upCam = new THREE.Vector3() // 占位（extractBasis 需要）
  const _back = new THREE.Vector3() // 占位（extractBasis 需要）
  const _worldUp = new THREE.Vector3(0, 1, 0) // 世界上方向：↑/↓ 沿世界 Y 垂直平移视角
  const _look = new THREE.Vector3() // 视线方向 = -Z（相机看向方向）：W/S 前进/后退
  const _offset = new THREE.Vector3() // 当前「相机→目标」偏移（移动时保持不变以维持缩放）
  const _move = new THREE.Vector3()
  // 移动边界：未注入时使用兜底值，保证任何情况下都「非无限」。
  let moveBounds = opts.moveBounds || {
    minX: -200, maxX: 200,
    minZ: -200, maxZ: 200,
    minY: 0.5, maxY: 120,
  }
  function clampVec(v, b) {
    if (b.minX != null) v.x = Math.min(b.maxX, Math.max(b.minX, v.x))
    if (b.minY != null) v.y = Math.min(b.maxY, Math.max(b.minY, v.y))
    if (b.minZ != null) v.z = Math.min(b.maxZ, Math.max(b.minZ, v.z))
  }
  function onKeyDown(e) {
    if (freeMove === false) return
    const t = e.target
    const tag = (t && t.tagName) || ''
    if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') return
    const k = (e.key || '').toLowerCase()
    if (['w', 'a', 's', 'd', 'arrowup', 'arrowdown', 'arrowleft', 'arrowright'].includes(k)) {
      moveKeys.add(k)
      if (k.indexOf('arrow') === 0) e.preventDefault()
    }
  }
  function onKeyUp(e) {
    moveKeys.delete((e.key || '').toLowerCase())
  }
  window.addEventListener('keydown', onKeyDown)
  window.addEventListener('keyup', onKeyUp)

  function applyKeyMove() {
    if (freeMove === false || moveKeys.size === 0) {
      lastMoveT = performance.now()
      return
    }
    const now = performance.now()
    const dt = Math.min(0.1, (now - lastMoveT) / 1000)
    lastMoveT = now
    const step = moveSpeed * dt
    camera.updateMatrixWorld()
    camera.matrixWorld.extractBasis(_right, _upCam, _back) // 列0=右, 列1=上, 列2=后(+Z)
    _look.copy(_back).multiplyScalar(-1) // 视线 = -Z（相机看向方向）
    _move.set(0, 0, 0)
    // W/S 沿视线前进/后退（第一人称 fly，含俯仰分量）；
    // ↑/↓ 沿世界 Y 轴垂直上移/下移（与视线俯仰无关）；
    // A/D（←/→）沿相机右向左右 strafe。旋转=鼠标拖拽，缩放=滚轮。
    if (moveKeys.has('w')) _move.add(_look)
    if (moveKeys.has('s')) _move.sub(_look)
    if (moveKeys.has('arrowup')) _move.add(_worldUp)
    if (moveKeys.has('arrowdown')) _move.sub(_worldUp)
    if (moveKeys.has('d') || moveKeys.has('arrowright')) _move.add(_right)
    if (moveKeys.has('a') || moveKeys.has('arrowleft')) _move.sub(_right)
    if (_move.lengthSq() > 0) {
      _move.normalize().multiplyScalar(step)
      // 关键：先记录移动前的「相机→目标」偏移，移动后按此偏移反推目标点，
      // 保证相机到目标的距离恒定 —— 缩放(zoom)因此与 WASD 移动完全解耦，绝不跳变。
      _offset.copy(camera.position).sub(controls.target)
      camera.position.add(_move)
      controls.target.add(_move)
      // 仅夹紧相机位置到机房边界（目标点由偏移反推，不单独 clamp，避免破坏距离）
      clampVec(camera.position, moveBounds)
      controls.target.copy(camera.position).sub(_offset)
    }
  }

  // 指针光标
  function setCursor(c) {
    renderer.domElement.style.cursor = c
    labelRenderer.domElement.style.cursor = c
  }

  // 清除所有残留的 CSS2D 标签 DOM（切换场景时防止机柜名称等标签重复残留）
  function clearLabels() {
    const layer = labelRenderer.domElement
    if (!layer) return
    const els = layer.querySelectorAll('.three-label')
    for (let i = 0; i < els.length; i++) els[i].remove()
  }

  // 渲染循环
  let rafId = 0
  let disposed = false
  let lastFrameT = performance.now()
  function animate() {
    if (disposed) return
    rafId = requestAnimationFrame(animate)
    const now = performance.now()
    const dt = Math.min(0.05, (now - lastFrameT) / 1000)
    lastFrameT = now
    if (typeof onTick === 'function') onTick(dt)
    applyKeyMove()
    controls.update()
    renderer.render(scene, camera)
    labelRenderer.render(scene, camera)
  }
  animate()

  // 自适应尺寸
  function onResize() {
    const w = getW()
    const h = getH()
    camera.aspect = w / h
    camera.updateProjectionMatrix()
    renderer.setSize(w, h)
    labelRenderer.setSize(w, h)
  }
  let ro = null
  if (typeof ResizeObserver !== 'undefined') {
    ro = new ResizeObserver(onResize)
    ro.observe(container)
  } else {
    window.addEventListener('resize', onResize)
  }

  // 彻底释放（重点：forceContextLoss 避免 SPA 反复进出导致 WebGL 上下文触顶 → 后续页面空白）
  function dispose() {
    if (disposed) return
    disposed = true
    try {
      cancelAnimationFrame(rafId)
    } catch (e) {
      /* noop */
    }
    try {
      if (ro) ro.disconnect()
      else window.removeEventListener('resize', onResize)
    } catch (e) {
      /* noop */
    }
    try {
      window.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('keyup', onKeyUp)
    } catch (e) {
      /* noop */
    }
    try {
      renderer.domElement.removeEventListener('pointerdown', onLookPointerDown)
      renderer.domElement.removeEventListener('pointermove', onLookPointerMove)
      window.removeEventListener('pointerup', onLookPointerUp)
    } catch (e) {
      /* noop */
    }
    try {
      controls.dispose()
    } catch (e) {
      /* noop */
    }
    try {
      scene.traverse((o) => {
        if (o.geometry) o.geometry.dispose()
        if (o.material) {
          const mats = Array.isArray(o.material) ? o.material : [o.material]
          mats.forEach((m) => {
            for (const k in m) {
              const v = m[k]
              if (v && v.isTexture) v.dispose()
            }
            m.dispose()
          })
        }
      })
    } catch (e) {
      /* noop */
    }
    try {
      if (envRT) envRT.dispose()
    } catch (e) {
      /* noop */
    }
    try {
      pmrem.dispose()
    } catch (e) {
      /* noop */
    }
    try {
      renderer.forceContextLoss()
    } catch (e) {
      /* noop */
    }
    try {
      renderer.domElement.removeEventListener('webglcontextlost', onContextLost, false)
      renderer.domElement.removeEventListener('webglcontextrestored', onContextRestored, false)
    } catch (e) {
      /* noop */
    }
    try {
      renderer.dispose()
    } catch (e) {
      /* noop */
    }
    try {
      if (renderer.domElement.parentNode) renderer.domElement.parentNode.removeChild(renderer.domElement)
    } catch (e) {
      /* noop */
    }
    try {
      if (labelRenderer.domElement.parentNode) labelRenderer.domElement.parentNode.removeChild(labelRenderer.domElement)
    } catch (e) {
      /* noop */
    }
  }

  function setOnTick(fn) {
    onTick = typeof fn === 'function' ? fn : null
  }

  // 注入/更新移动边界（由具体视图根据机房/机柜实际尺寸计算后调用）。
  function setMoveBounds(b) {
    if (b && typeof b === 'object') moveBounds = b
  }

  // WebGL 上下文丢失/恢复兜底：SPA 反复进出 3D 页面可能导致上下文耗尽而整页空白。
  // 监听 contextlost 并 preventDefault（允许浏览器后续恢复），contextrestored 时回调重建。
  function onContextLost(e) {
    try { e.preventDefault() } catch (_) { /* noop */ }
    console.warn('[three-setup] WebGL context lost')
    if (typeof opts.onContextLost === 'function') opts.onContextLost()
  }
  function onContextRestored() {
    console.warn('[three-setup] WebGL context restored')
    if (typeof opts.onContextRestored === 'function') opts.onContextRestored()
  }
  renderer.domElement.addEventListener('webglcontextlost', onContextLost, false)
  renderer.domElement.addEventListener('webglcontextrestored', onContextRestored, false)

  return { renderer, scene, camera, controls, container, setCursor, clearLabels, setOnTick, setMoveBounds, dispose }
}
