import { defineStore } from 'pinia'
import metaApi from '@/api/meta'
// 直接写回 reactive 常量映射：一处同步即覆盖全站 15+ 处 usage（审查报告#345/#349）。
// 常量内默认值即离线兜底，后端不可达时渲染仍正确。
import {
  RACK_STATUS_COLORS,
  RACK_STATUS_LABELS,
  DEVICE_TYPE_COLORS,
  DEVICE_TYPE_LABELS,
  DEVICE_STATUS_COLORS,
  DEVICE_STATUS_LABELS,
  FACILITY_TYPES,
} from '@/utils/constants'

// 界面元数据（标签 / 颜色 / 阈值）单一数据源。
// 后端 /meta 为权威源，本 store 在登录后拉取一次；constants.js 仅作离线兜底。
// 消除前后端双源（审查报告规范#2）与前端硬编码阈值魔法数字（审查报告#347）。
export const useMetaStore = defineStore('meta', {
  state: () => ({
    deviceStatus: [], // [{ value, label, color }]
    deviceType: [], // [{ value, label, color }]
    rackStatus: [], // [{ value, label, color }]
    facilityTypes: [], // 设施类型集合（非资产），如 ['patch','odf','other_facility']
    usageThresholds: { warn: 30, crit: 80 }, // 离线兜底默认值
    usageColors: { ok: '#67C23A', warn: '#E6A23C', crit: '#F56C6C' }, // 离线兜底三档色
    loaded: false,
  }),
  getters: {
    // 设备状态值 → 颜色（未知值回退灰色）。
    deviceStatusColor: (s) => (v) =>
      (s.deviceStatus.find((x) => x.value === v) || {}).color || '#909399',
    // 设备类型值 → 颜色。
    deviceTypeColor: (s) => (v) =>
      (s.deviceType.find((x) => x.value === v) || {}).color || '#909399',
    // 机柜状态值 → 颜色。
    rackStatusColor: (s) => (v) =>
      (s.rackStatus.find((x) => x.value === v) || {}).color || '#909399',
    // 使用率 warn 阈值（%）。
    usageWarn: (s) => s.usageThresholds.warn,
    // 使用率 crit 阈值（%）。
    usageCrit: (s) => s.usageThresholds.crit,
    // 机柜使用率 → 三档配色（审查报告#352）。兼容两种传参：ratio ∈ [0,1] 或百分比 [0,100]，
    // 按 warn/crit 阈值取 ok/warn/crit。移除各视图内联的 `>0.8?'#F56C6C':...` 魔法色。
    usageColor: (s) => (ratio) => {
      const r = Number(ratio)
      if (!isFinite(r)) return s.usageColors.ok
      const pct = r > 1 ? r : r * 100
      const warn = s.usageThresholds.warn
      const crit = s.usageThresholds.crit
      if (pct >= crit) return s.usageColors.crit
      if (pct >= warn) return s.usageColors.warn
      return s.usageColors.ok
    },
  },
  actions: {
    async load() {
      const data = await metaApi.get()
      // 1) 写入 store 数组（getter 直接取色）。
      this.deviceStatus = data.device_status || []
      this.deviceType = data.device_type || []
      this.rackStatus = data.rack_status || []
      this.facilityTypes = data.facility_types || []
      this.usageThresholds = data.usage_thresholds || { warn: 30, crit: 80 }
      this.usageColors = data.usage_colors || {
        ok: '#67C23A',
        warn: '#E6A23C',
        crit: '#F56C6C',
      }
      // 设施类型集合写回常量：保证 isFacilityType / isAssetDevice 与后端权威源一致。
      FACILITY_TYPES.clear()
      for (const t of this.facilityTypes) FACILITY_TYPES.add(t)
      // 2) 同步写回 reactive 常量映射：覆盖全站既有 import 这些映射的组件，无需逐文件改。
      //    仅覆盖后端返回的值，未返回的 key 保留常量默认值（离线兜底）。
      for (const it of this.deviceStatus) {
        if (!it || it.value == null) continue
        DEVICE_STATUS_COLORS[it.value] = it.color || DEVICE_STATUS_COLORS[it.value]
        DEVICE_STATUS_LABELS[it.value] = it.label || DEVICE_STATUS_LABELS[it.value]
      }
      for (const it of this.deviceType) {
        if (!it || it.value == null) continue
        DEVICE_TYPE_COLORS[it.value] = it.color || DEVICE_TYPE_COLORS[it.value]
        DEVICE_TYPE_LABELS[it.value] = it.label || DEVICE_TYPE_LABELS[it.value]
      }
      for (const it of this.rackStatus) {
        if (!it || it.value == null) continue
        RACK_STATUS_COLORS[it.value] = it.color || RACK_STATUS_COLORS[it.value]
        RACK_STATUS_LABELS[it.value] = it.label || RACK_STATUS_LABELS[it.value]
      }
      this.loaded = true
    },
  },
})
