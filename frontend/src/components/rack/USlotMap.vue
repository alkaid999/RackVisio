<template>
  <div class="u-slot-map">
    <svg
      v-if="uMap"
      ref="svgEl"
      :width="svgWidth"
      :height="svgHeight"
      :viewBox="`0 0 ${svgWidth} ${svgHeight}`"
      class="u-svg"
      :class="{ 'is-drop-target': dragOver }"
      @dragover.prevent="onDragOver"
      @dragleave="onDragLeave"
      @drop.prevent="onDrop"
    >
      <!-- 网格横线：每 U 一条浅色分隔，便于逐位辨识 -->
      <line
        v-for="u in totalU"
        :key="`gl-${u}`"
        :x1="labelW"
        :x2="svgWidth"
        :y1="uTop(u)"
        :y2="uTop(u)"
        :stroke="u === totalU ? '#cbd5e1' : '#eef2f7'"
        stroke-width="1"
      />

      <!-- 左侧 U 数标尺：逐 U 显示（从 1U 到 totalU），小字标注 -->
      <text
        v-for="u in totalU"
        :key="`rk-${u}`"
        :x="labelW - 7"
        :y="uTop(u) + unitH / 2"
        text-anchor="end"
        dominant-baseline="middle"
        class="u-label"
      >{{ u }}U</text>

      <!-- 合并后的设备 / 空闲块（自顶向下：索引 0 = 最高 U） -->
      <g v-for="seg in segments" :key="seg.key">
        <!-- 空闲块（每个空闲 U 独立成行，1U 高） -->
        <g v-if="!seg.deviceId">
          <rect
            :x="labelW"
            :y="seg.y"
            :width="unitW"
            :height="seg.h - gap"
            rx="4"
            fill="#f4f6fa"
            stroke="#dcdfe6"
            stroke-width="1"
            stroke-dasharray="3 3"
            class="u-rect free"
            @click="onRectClick(seg)"
          >
            <title>点击在 {{ seg.uStart }}U 添加设备</title>
          </rect>
          <text
            :x="labelW + unitW / 2"
            :y="seg.y + seg.h / 2"
            text-anchor="middle"
            dominant-baseline="middle"
            class="u-free"
            @click="onRectClick(seg)"
          >+ 添加</text>
        </g>

        <!-- 设备块（合并高 U 设备为整块） -->
        <g v-else class="u-dev-group" @mouseenter="onEnter(seg)" @mouseleave="onLeave">
          <rect
            :x="labelW"
            :y="seg.y"
            :width="unitW"
            :height="seg.h - gap"
            rx="4"
            :fill="deviceColor(seg.deviceType)"
            stroke="#303133"
            stroke-width="1"
            :class="overlapIds.has(seg.deviceId) ? 'u-rect occupied u-overlap' : 'u-rect occupied'"
            @click="onRectClick(seg)"
          >
            <title>{{ seg.deviceName }}</title>
          </rect>

          <!-- 设备名称：在 U 位区域内水平 + 垂直居中。多 U 块再补一行 U 区间（同样居中）。 -->
          <text
            :x="labelW + unitW / 2"
            :y="seg.size >= 2 ? seg.y + seg.h / 2 - 8 : seg.y + seg.h / 2"
            text-anchor="middle"
            dominant-baseline="middle"
            class="u-device"
            @click="onRectClick(seg)"
          >{{ truncate(seg.deviceName) }}</text>
          <text
            v-if="seg.size >= 2"
            :x="labelW + unitW / 2"
            :y="seg.y + seg.h / 2 + 9"
            text-anchor="middle"
            dominant-baseline="middle"
            class="u-range"
            @click="onRectClick(seg)"
          >{{ seg.uStart }}U–{{ seg.uEnd }}U · {{ seg.size }}U</text>

          <!-- 状态色点：左上角 -->
          <circle
            v-if="statusOf(seg.deviceId)"
            :cx="labelW + 14"
            :cy="seg.y + 14"
            r="4.5"
            :fill="statusOf(seg.deviceId)"
            class="u-dot"
            @click="onRectClick(seg)"
          />

          <!-- 重叠告警：红圈 + ⚠（始终可见，提示 U 位冲突 / 遮挡） -->
          <g v-if="overlapIds.has(seg.deviceId)" class="u-overlap-mark" @click.stop="onRectClick(seg)">
            <circle :cx="labelW + 30" :cy="seg.y + 14" r="8" fill="rgba(239, 68, 68, 0.96)" />
            <text :x="labelW + 30" :y="seg.y + 14" text-anchor="middle" dominant-baseline="middle" class="u-overlap-text">!</text>
          </g>

          <!-- 悬停显隐的下架按钮（右上角）：点击触发 unmount-device，停冒泡避免误触导航 -->
          <g
            v-if="hoveredId === seg.deviceId"
            class="u-unmount"
            @click.stop="onUnmount(seg)"
          >
            <rect
              :x="labelW + unitW - 58"
              :y="seg.y + 6"
              width="50"
              height="22"
              rx="11"
              fill="rgba(239, 68, 68, 0.95)"
              stroke="#fff"
              stroke-width="1"
            />
            <text
              :x="labelW + unitW - 33"
              :y="seg.y + 17"
              text-anchor="middle"
              dominant-baseline="middle"
              class="u-unmount-text"
            >下架</text>
          </g>
        </g>
      </g>

      <!-- 拖拽放置指示（仅拖拽悬停时） -->
      <text
        v-if="dragOver"
        :x="labelW + unitW / 2"
        :y="svgHeight - 8"
        text-anchor="middle"
        class="u-drop-hint"
      >松开以在此上架</text>
    </svg>
    <EmptyState v-else title="暂无 U 位数据" />

    <!-- 悬停设备详情 tooltip（HTML 覆盖层，避免 SVG 文字换行遮挡） -->
    <div
      v-if="hoverDevice"
      class="u-tooltip"
      :style="{ left: tooltipX + 'px', top: tooltipY + 'px' }"
    >
      <div class="u-tooltip-title">
        {{ hoverDevice.name }}
        <span
          class="u-tooltip-dot"
          :style="{ background: statusOf(hoverDevice.id) || '#909399' }"
        ></span>
      </div>
      <div class="u-tooltip-row"><span>类型</span>{{ DEVICE_TYPE_LABELS[hoverDevice.device_type] || hoverDevice.device_type }}</div>
      <div class="u-tooltip-row"><span>位置</span>{{ hoverDevice.current_start_u }}U ~ {{ hoverDevice.current_start_u + (hoverDevice.u_height || 1) - 1 }}U</div>
      <div class="u-tooltip-row"><span>状态</span>{{ hoverDevice.status }}</div>
      <div v-if="hoverDevice.ip_address" class="u-tooltip-row"><span>IP</span>{{ hoverDevice.ip_address }}</div>
      <div v-if="hoverDevice.model" class="u-tooltip-row"><span>型号</span>{{ hoverDevice.model }}</div>
      <div v-if="hoverDevice.sn" class="u-tooltip-row"><span>SN</span>{{ hoverDevice.sn }}</div>
      <div v-if="overlapIds.has(hoverDevice.id)" class="u-tooltip-row u-tooltip-warn"><span>⚠</span>U 位与其他设备重叠</div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { DEVICE_TYPE_COLORS, DEVICE_STATUS_COLORS, DEVICE_TYPE_LABELS } from '@/utils/constants'
import EmptyState from '@/components/ui/empty-state.vue'

const props = defineProps({
  // RackUMap: {rack_id, total_u, used_u, status, slots:[{u, device_id, device_name, device_type}]}
  uMap: { type: Object, default: null },
  // 设备列表（含完整信息，用于悬停详情与状态色点）；元素含 {id, status, ...}
  devices: { type: Array, default: () => [] },
})
const emit = defineEmits(['add-device', 'select-device', 'unmount-device', 'mount-device'])

const labelW = 48
const unitW = 304
const gap = 4
const svgWidth = labelW + unitW

const svgEl = ref(null)
const dragOver = ref(false)
const hoverDevice = ref(null)
const hoverSeg = ref(null)
const hoveredId = ref(null)
const tooltipX = ref(0)
const tooltipY = ref(0)
// 提示框估算尺寸（CSS 中 width=220）；用于在机柜右侧垂直居中锚定。
const TOOLTIP_W = 220
const TOOLTIP_H = 160

const totalU = computed(() => (props.uMap ? props.uMap.total_u : 0))
// 每 U 高度：下限 40px，确保 1U 设备（24px 下架按钮 + 设备名）完整容纳且留余量，
// 不再被 U 数标签或相邻行遮挡，也不会因高度不足而「超出 1U 显示范围」。
// 短机柜放大到更易读（上限 56px），长机柜以最小 40px 为准；
// 超出单屏的部分由外层滚动容器承载（见 RackDetail 的 .u-map-scroll）。
const unitH = computed(() => {
  const t = totalU.value
  if (!t) return 32
  return Math.max(40, Math.min(56, 820 / t))
})
// 某 U 槽顶部的 y 坐标（U1 在底部）。
function uTop(u) {
  return (totalU.value - u) * unitH.value
}

// 将逐 U 的槽位转为块：设备合并为高 U 整块；空闲 U 每个独立成 1U 行。
const segments = computed(() => {
  if (!props.uMap) return []
  const slots = [...props.uMap.slots].sort((a, b) => b.u - a.u) // 自顶向下
  const segs = []
  let cur = null
  for (const s of slots) {
    if (s.device_id) {
      if (cur && cur.deviceId === s.device_id) {
        cur.uStart = Math.min(cur.uStart, s.u)
        cur.uEnd = Math.max(cur.uEnd, s.u)
      } else {
        if (cur) segs.push(cur)
        cur = {
          key: 'd-' + s.device_id,
          deviceId: s.device_id,
          deviceName: s.device_name,
          deviceType: s.device_type,
          uStart: s.u,
          uEnd: s.u,
        }
      }
    } else {
      if (cur) segs.push(cur)
      cur = { key: 'f-' + s.u, deviceId: null, uStart: s.u, uEnd: s.u }
      segs.push(cur)
      cur = null
    }
  }
  if (cur) segs.push(cur)
  return segs.map((seg) => {
    const size = seg.uEnd - seg.uStart + 1
    return {
      ...seg,
      size,
      y: (totalU.value - seg.uEnd) * unitH.value,
      h: size * unitH.value,
    }
  })
})

const svgHeight = computed(() => (props.uMap ? props.uMap.total_u * unitH.value : 0))

const deviceStatusMap = computed(() => {
  const m = {}
  for (const d of props.devices || []) m[d.id] = d
  return m
})
function statusOf(id) {
  const d = deviceStatusMap.value[id]
  return d ? DEVICE_STATUS_COLORS[d.status] || '#909399' : null
}
function fullDevice(id) {
  return deviceStatusMap.value[id] || null
}

// 重叠检测：基于已上架设备的 current_start_u + u_height 计算占用区间，
// 任意两台区间相交即标记为重叠（U 位冲突 / 遮挡），用于视觉告警。
const overlapIds = computed(() => {
  const devs = (props.devices || []).filter(
    (d) => d.current_start_u != null && d.u_height
  )
  const ranges = devs.map((d) => ({
    id: d.id,
    s: d.current_start_u,
    e: d.current_start_u + d.u_height - 1,
  }))
  const bad = new Set()
  for (let i = 0; i < ranges.length; i++) {
    for (let j = i + 1; j < ranges.length; j++) {
      const a = ranges[i]
      const b = ranges[j]
      if (a.s <= b.e && b.s <= a.e) {
        bad.add(a.id)
        bad.add(b.id)
      }
    }
  }
  return bad
})

function deviceColor(type) {
  return DEVICE_TYPE_COLORS[type] || '#909399'
}
function truncate(name) {
  if (!name) return ''
  return name.length > 18 ? name.slice(0, 17) + '…' : name
}
function onRectClick(seg) {
  if (seg.deviceId) {
    emit('select-device', seg.deviceId)
  } else {
    emit('add-device', seg.uStart)
  }
}

// —— 悬停详情 ——
// 提示框固定在「机柜（SVG）右侧」，垂直方向对齐被悬停设备的中心，
// 确保不会遮挡机柜内的下架按钮（按钮位于 SVG 右侧设备块内，提示框在其外部）。
function onEnter(seg) {
  const d = fullDevice(seg.deviceId)
  if (!d) return
  hoverDevice.value = d
  hoverSeg.value = seg
  hoveredId.value = seg.deviceId
  const top = seg.y + seg.h / 2 - TOOLTIP_H / 2
  tooltipX.value = svgWidth + 12
  tooltipY.value = Math.max(4, Math.min(top, Math.max(4, svgHeight.value - TOOLTIP_H - 4)))
}
function onLeave() {
  hoverDevice.value = null
  hoverSeg.value = null
  hoveredId.value = null
}
// 悬停下架按钮：将设备 id 冒泡给父组件（RackDetail 的 @unmount-device → onUnmountId）。
function onUnmount(seg) {
  emit('unmount-device', seg.deviceId)
}

// —— 拖拽上架 ——
function onDragOver() {
  dragOver.value = true
}
function onDragLeave(e) {
  // 仅当真正离开 SVG 时清除（避免子元素冒泡抖动）
  if (!e.currentTarget.contains(e.relatedTarget)) dragOver.value = false
}
function onDrop(e) {
  dragOver.value = false
  const id = e.dataTransfer?.getData('text/plain') || e.dataTransfer?.getData('device_id')
  if (!id) return
  const rect = svgEl.value.getBoundingClientRect()
  const y = (e.clientY - rect.top) * (svgHeight.value / rect.height)
  let topU = totalU.value - Math.floor(y / unitH.value)
  topU = Math.max(1, Math.min(totalU.value, topU))
  // 拖拽体尺寸（多 U 设备以顶部对齐，换算起始 U 位）
  const dev = fullDevice(id)
  const size = (dev && dev.u_height) || 1
  const startU = Math.max(1, topU - size + 1)
  emit('mount-device', { device_id: id, start_u: startU })
}
</script>

<style scoped>
.u-slot-map {
  position: relative;
}
.u-svg {
  display: block;
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 6px;
}
.u-svg.is-drop-target {
  outline: 2px dashed #409eff;
  outline-offset: -3px;
  background: #f5faff;
}
.u-label {
  font-size: 11px;
  fill: #909399;
  font-variant-numeric: tabular-nums;
  font-weight: 500;
}
.u-device {
  font-size: 12.5px;
  fill: #fff;
  font-weight: 600;
  pointer-events: none;
}
.u-range {
  font-size: 10.5px;
  fill: rgba(255, 255, 255, 0.92);
  pointer-events: none;
}
.u-free {
  font-size: 12px;
  fill: #c0c4cc;
  pointer-events: none;
}
.u-rect {
  cursor: pointer;
  transition: opacity 0.15s, filter 0.15s;
}
.u-rect:hover {
  filter: brightness(1.05);
}
.u-dot {
  pointer-events: none;
}
.u-drop-hint {
  font-size: 12px;
  fill: #409eff;
  font-weight: 600;
  pointer-events: none;
}
.u-unmount {
  cursor: pointer;
}
.u-unmount-text {
  font-size: 11.5px;
  font-weight: 700;
  fill: #fff;
  pointer-events: none;
}
.u-overlap {
  stroke: #ef4444 !important;
  stroke-width: 2;
  stroke-dasharray: 4 2;
}
.u-overlap-mark {
  cursor: pointer;
}
.u-overlap-text {
  font-size: 11px;
  font-weight: 800;
  fill: #fff;
  pointer-events: none;
}
.u-tooltip-warn {
  color: #fca5a5;
  font-weight: 600;
}

/* 悬停详情 tooltip */
.u-tooltip {
  position: absolute;
  z-index: 20;
  width: 220px;
  padding: 10px 12px;
  background: rgba(17, 24, 39, 0.96);
  color: #e5e7eb;
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
  font-size: 12px;
  pointer-events: none;
}
.u-tooltip-title {
  font-size: 13px;
  font-weight: 700;
  color: #fff;
  margin-bottom: 6px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.u-tooltip-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}
.u-tooltip-row {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  line-height: 1.7;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.u-tooltip-row span {
  color: #9ca3af;
  flex-shrink: 0;
}
</style>
