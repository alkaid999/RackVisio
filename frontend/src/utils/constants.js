// 前端枚举镜像（与 backend/app/core/enums.py 取值严格一致）+ 颜色映射。
// 颜色规则见架构文档 §8 与 PRD F1.5。
//
// 注意：RACK_/DEVICE_TYPE_/DEVICE_STATUS_ 的 COLORS / LABELS 用 Vue `reactive()` 包裹，
// 作为「后端 /meta 颜色单一数据源」的可变镜像——metaStore.load() 会把后端下发的值
// 直接写回这些对象，从而实现「一处同步、全站 15+ 处 usage 自动更新」，无需逐文件改 import
// （审查报告#345/#349）。常量内的默认值即离线兜底：后端不可达时渲染仍正确。
import { reactive } from 'vue'

// ============ 筛选哨兵（重要）============
// reka-ui 的 <SelectItem> 不允许 value 为空字符串（空字符串被保留用于 Select 的「未选择」占位）。
// 筛选器的「全部 / 不限」选项必须用此哨兵值，否则组件会在 setup 阶段抛错，
// 进而在路由切换（<Transition mode="out-in">）卸载时连带崩溃，导致目标页面永远不挂载（需手动刷新）。
export const SELECT_ALL = '__all__'

// 将筛选模型值转换为后端查询参数：空值或 SELECT_ALL 哨兵均视为「无筛选」(undefined)。
export function toFilterParam(v) {
  return v && v !== SELECT_ALL ? v : undefined
}

// ============ 机房 ============
export const ROOM_STATUS_OPTIONS = [
  { value: 'active', label: '启用' },
  { value: 'disabled', label: '停用' },
]

// ============ 机柜业务状态（用户维护枚举，支持后续扩展）============
// 可用=绿、空闲=浅绿、维护中=橙、空调柜=蓝、电柜=琥珀（与后端 RackBizStatus 取值严格一致）
export const RACK_STATUS_OPTIONS = [
  { value: '可用', label: '可用' },
  { value: '空闲', label: '空闲' },
  { value: '维护中', label: '维护中' },
  { value: '空调柜', label: '空调柜' },
  { value: '电柜', label: '电柜' },
]
export const RACK_STATUS_COLORS = reactive({
  可用: '#22c55e',
  空闲: '#67c23a',
  维护中: '#e6a23c',
  空调柜: '#38bdf8',
  电柜: '#f59e0b',
})
export const RACK_STATUS_LABELS = reactive({
  可用: '可用',
  空闲: '空闲',
  维护中: '维护中',
  空调柜: '空调柜',
  电柜: '电柜',
})

// ============ 设备类型（与 backend DeviceType 取值严格一致）============
// 其中 patch / odf / other_facility 为「基础设施（非资产）」，见 FACILITY_TYPES 注释。
export const DEVICE_TYPE_OPTIONS = [
  { value: 'server', label: '服务器' },
  { value: 'switch', label: '交换机' },
  { value: 'router', label: '路由器' },
  { value: 'security', label: '安全设备' },
  { value: 'other', label: '其他设备' },
  { value: 'patch', label: '配线架' },
  { value: 'odf', label: 'ODF配线架' },
  { value: 'other_facility', label: '其他设施' },
]
export const DEVICE_TYPE_LABELS = reactive({
  server: '服务器',
  switch: '交换机',
  router: '路由器',
  security: '安全设备',
  other: '其他设备',
  // 基础设施（非资产）
  patch: '配线架',
  odf: 'ODF配线架',
  other_facility: '其他设施',
})
export const DEVICE_TYPE_COLORS = reactive({
  server: '#409EFF',
  switch: '#67C23A',
  router: '#13C2C2',
  security: '#E6A23C',
  other: '#909399',
  // 基础设施（非资产，中性灰）
  patch: '#64748b',
  odf: '#64748b',
  other_facility: '#94a3b8',
})

// ============ 基础设施（非资产）============
// 配线架 / ODF配线架 / 其他设施：占 U 位但不进资产统计、不建接口、不显设备编码。
// 与后端 meta.FACILITY_TYPES 严格一致；DeviceList 默认隐藏，设备类型下拉仍可选。
export const FACILITY_TYPES = new Set(['patch', 'odf', 'other_facility'])

// 判断某设备类型是否为基础设施（非资产）。
export function isFacilityType(type) {
  return FACILITY_TYPES.has(type)
}

// 判断某设备是否为资产（设施返回 false）。
// 优先用后端下发的 is_asset 字段，回退到类型判断（兼容历史数据缺该字段的情况）。
export function isAssetDevice(device) {
  if (!device) return true
  if (typeof device.is_asset === 'boolean') return device.is_asset
  return !isFacilityType(device.device_type)
}

// ============ 设备状态（资产生命周期，与后端 DeviceStatus 取值严格一致）============
// 在库=灰、已上架=绿、待报废=红、借出=紫。
// 注：「已下架」为历史遗留状态，下架后设备退回「在库」，故从可选项（筛选/编辑）中移除；
// DEVICE_STATUS_LABELS / DEVICE_STATUS_COLORS 仍保留该值，便于历史数据展示回退。
export const DEVICE_STATUS_OPTIONS = [
  { value: '在库', label: '在库' },
  { value: '已上架', label: '已上架' },
  { value: '待报废', label: '待报废' },
  { value: '借出', label: '借出' },
]
export const DEVICE_STATUS_LABELS = reactive({
  在库: '在库',
  已上架: '已上架',
  已下架: '已下架',
  待报废: '待报废',
  借出: '借出',
})
export const DEVICE_STATUS_COLORS = reactive({
  在库: '#909399',
  已上架: '#67C23A',
  已下架: '#E6A23C',
  待报废: '#F56C6C',
  借出: '#8b5cf6',
})

// ============ 设备开关机状态（仅「在架」设备有意义；在库设备不涉及）============
// 语义：红色专用于「关机」告警，不得用于常规状态色。
// 2D 机柜视图中，设备块「底色」保留设备类型色（typeColor，不覆盖设备本身颜色），
// 「开关机」用左上角小圆圈（status-dot）标注：开机 = 绿、关机 = 红。
export const DEVICE_POWER_OPTIONS = [
  { value: '开机', label: '开机' },
  { value: '关机', label: '关机' },
]
export const DEVICE_POWER_LABELS = {
  开机: '开机',
  关机: '关机',
}
export const DEVICE_POWER_COLORS = {
  开机: '#22c55e',
  关机: '#ef4444',
}

// ============ 接口类型 / 角色 / 速率 / 状态 ============
// 物理接口类型：电口（RJ-45）/ 管理口（Console，RJ-45 或 DB9）/ 光模块插槽（SFP/QSFP）/ 其他。
// 旧值 electrical/optical 仅作兼容展示，运行时已由迁移脚本转换为 rj45/sfp。
export const INTERFACE_TYPE_OPTIONS = [
  { value: 'rj45', label: 'RJ-45（电口）' },
  { value: 'console', label: 'Console（管理口）' },
  { value: 'sfp', label: 'SFP 插槽（光口）' },
  { value: 'qsfp', label: 'QSFP 插槽（光口）' },
  { value: 'other', label: '其他' },
]
export const INTERFACE_TYPE_LABELS = {
  rj45: 'RJ-45（电口）',
  console: 'Console（管理口）',
  sfp: 'SFP 插槽（光口）',
  qsfp: 'QSFP 插槽（光口）',
  other: '其他',
  // 历史兼容
  electrical: '电口',
  optical: '光口',
}
// 接口类型展示色（用于分组标题、前面板图例等）。
export const INTERFACE_TYPE_COLORS = {
  rj45: '#3b82f6',
  console: '#8b5cf6',
  sfp: '#f59e0b',
  qsfp: '#10b981',
  other: '#909399',
}
// 接口角色（数据口/管理口），与 interface_type（物理介质）正交。
export const INTERFACE_ROLE_OPTIONS = [
  { value: 'data', label: '数据口' },
  { value: 'mgmt', label: '管理口' },
]
export const INTERFACE_ROLE_LABELS = {
  data: '数据口',
  mgmt: '管理口',
}
export const SPEED_OPTIONS = [
  { value: '1G', label: '1G' },
  { value: '10G', label: '10G' },
  { value: '25G', label: '25G' },
  { value: '40G', label: '40G' },
  { value: '100G', label: '100G' },
]
// 接口状态：up=已连线（建链自动置位），down=未连线（默认）。
export const INTERFACE_STATUS_OPTIONS = [
  { value: 'up', label: '已连线' },
  { value: 'down', label: '未连线' },
]
export const INTERFACE_STATUS_COLORS = {
  up: '#67C23A',
  down: '#909399',
}

// ============ 连接介质（细分物理介质）============
// 与后端 LinkMedium 枚举取值保持一致。用户可选范围严格限定为：单模光纤 / 多模光纤 / 双绞线。
// 旧值 copper/fiber/coax/dac/aoc 仅作历史展示兼容（LABELS/COLORS 保留，OPTIONS 不暴露）。
export const LINK_MEDIUM_OPTIONS = [
  { value: 'smf', label: '单模光纤' },
  { value: 'mmf', label: '多模光纤' },
  { value: 'tp', label: '双绞线' },
]
export const LINK_MEDIUM_LABELS = {
  smf: '单模光纤',
  mmf: '多模光纤',
  tp: '双绞线',
  // 历史兼容（历史数据展示回退）
  copper: '网线',
  fiber: '光纤',
  coax: '同轴电缆',
  dac: '直连铜缆（DAC）',
  aoc: '有源光缆（AOC）',
}
export const LINK_MEDIUM_COLORS = {
  smf: '#13C2C2',
  mmf: '#36CFC9',
  tp: '#909399',
  // 历史兼容
  copper: '#909399',
  fiber: '#13C2C2',
  coax: '#d48806',
  dac: '#7c3aed',
  aoc: '#eb2f96',
}

// ============ 连接器类型（按连接介质动态联动，均为必选）============
// 双绞线（tp）记录的是「线缆类别」：CAT5 / CAT5e / CAT6 / CAT6a（RJ-45 是所有双绞线两端
// 统一的物理插头，不单独作为连接器类型）；光纤（单模/多模）需选择光纤连接器组合。
export const CONNECTOR_TYPE_FIBER_OPTIONS = [
  { value: 'lc-lc', label: 'LC-LC' },
  { value: 'lc-fc', label: 'LC-FC' },
  { value: 'lc-sc', label: 'LC-SC' },
  { value: 'sc-sc', label: 'SC-SC' },
  { value: 'sc-fc', label: 'SC-FC' },
  { value: 'st-st', label: 'ST-ST' },
  { value: 'other', label: '其他' },
]
// 双绞线类别（必选）：线缆类别，建链时需手动选择。
export const CONNECTOR_TYPE_TP_OPTIONS = [
  { value: 'cat5', label: 'CAT5' },
  { value: 'cat5e', label: 'CAT5e' },
  { value: 'cat6', label: 'CAT6' },
  { value: 'cat6a', label: 'CAT6a' },
  { value: 'other', label: '其他' },
]
// 按连接介质返回可选连接器列表；其它/历史介质返回空数组。
export function connectorTypeOptionsFor(medium) {
  if (medium === 'smf' || medium === 'mmf') return CONNECTOR_TYPE_FIBER_OPTIONS
  if (medium === 'tp') return CONNECTOR_TYPE_TP_OPTIONS
  return []
}
// 全部连接器标签，用于列表展示与编辑回显。
export const CONNECTOR_TYPE_LABELS = {
  'lc-lc': 'LC-LC',
  'lc-fc': 'LC-FC',
  'lc-sc': 'LC-SC',
  'sc-sc': 'SC-SC',
  'sc-fc': 'SC-FC',
  'st-st': 'ST-ST',
  cat5: 'CAT5',
  cat5e: 'CAT5e',
  cat6: 'CAT6',
  cat6a: 'CAT6a',
  other: '其他',
}
// 连接器类型补充说明（选中后展示，帮助用户理解所选类别含义）。
export const CONNECTOR_TYPE_DESC = {
  cat5: '百兆以太网',
  cat5e: '千兆以太网（最常用）',
  cat6: '千兆 / 万兆短距',
  cat6a: '万兆以太网',
  'lc-lc': '小方头 — 小方头',
  'lc-fc': '小方头 — 圆头(FC)',
  'lc-sc': '小方头 — 大方头(SC)',
  'sc-sc': '大方头 — 大方头',
  'sc-fc': '大方头 — 圆头(FC)',
  'st-st': '卡接式(ST) — 卡接式(ST)',
  other: '其他 / 自定义',
}

// 根据状态值取通用颜色（用于 StatusBadge）。
export function statusColor(type, value) {
  switch (type) {
    case 'rack':
      return RACK_STATUS_COLORS[value] || '#909399'
    case 'device':
      return DEVICE_STATUS_COLORS[value] || '#909399'
    case 'interface':
      return INTERFACE_STATUS_COLORS[value] || '#909399'
    default:
      return '#909399'
  }
}

// 根据状态值取通用中文标签（用于 StatusBadge）。
export function statusLabel(type, value) {
  switch (type) {
    case 'rack':
      return (RACK_STATUS_OPTIONS.find((o) => o.value === value) || {}).label || value
    case 'device':
      return (DEVICE_STATUS_OPTIONS.find((o) => o.value === value) || {}).label || value
    case 'interface':
      return (INTERFACE_STATUS_OPTIONS.find((o) => o.value === value) || {}).label || value
    default:
      return value
  }
}

// ============ 账号 / 角色 / 权限 ============
// 与后端 app/core/rbac.py 权限目录严格一致（单一数据源镜像）。
export const ROLE_OPTIONS = [
  { value: 'admin', label: '管理员' },
  { value: 'user', label: '普通用户' },
]
export const ROLE_LABELS = {
  admin: '管理员',
  user: '普通用户',
}

// 权限目录（声明式单一数据源；新增模块 / 操作只需在此扩展，前后端同步）。
// 顺序即界面展示顺序。
export const PERMISSION_MODULES = ['room', 'rack', 'device', 'link', 'account', 'consumable']
export const PERMISSION_OPERATIONS = ['view', 'edit']

// 权限模块中文名（权限键形如 "<module>:<action>"）。
export const PERMISSION_MODULE_LABELS = {
  room: '机房',
  rack: '机柜',
  device: '设备',
  link: '链路',
  account: '账号',
  consumable: '耗材',
}
// 权限动作中文名。
export const PERMISSION_ACTION_LABELS = {
  view: '查看',
  edit: '编辑',
}

// 普通用户缺省权限映射：全模块只读（view=true, edit=false）。
export function defaultPermissions() {
  const map = {}
  for (const m of PERMISSION_MODULES) {
    map[m] = { view: true, edit: false }
  }
  return map
}

// 将权限映射（{module:{view,edit}}）展开为扁平权限键集合（如 ["room:view","device:edit"]）。
// isAdmin=true 时返回全集（管理员恒全权限）。非法模块 / 操作自动忽略。
export function expandPermissions(map, isAdmin = false) {
  if (isAdmin) {
    const all = []
    for (const m of PERMISSION_MODULES) {
      for (const o of PERMISSION_OPERATIONS) all.push(`${m}:${o}`)
    }
    return all
  }
  const set = new Set()
  const src = map || {}
  for (const m of PERMISSION_MODULES) {
    const entry = src[m]
    if (!entry) continue
    for (const o of PERMISSION_OPERATIONS) {
      if (entry[o]) set.add(`${m}:${o}`)
    }
  }
  return [...set]
}

// 将权限键格式化为可读标签，例如 "room:edit" → "机房编辑"。
export function formatPermission(perm) {
  const [mod, action] = String(perm || '').split(':')
  const m = PERMISSION_MODULE_LABELS[mod] || mod || ''
  const a = PERMISSION_ACTION_LABELS[action] || action || ''
  return a ? `${m}${a}` : m
}

// 权限摘要：将权限映射按「模块 → 层级标签」聚合，用于表格快速展示。
// 返回 [{module, label, level}]，level ∈ 'full' | 'view' | 'none'。
export function permissionSummary(map, isAdmin = false) {
  if (isAdmin) {
    return PERMISSION_MODULES.map((m) => ({ module: m, label: '完全访问', level: 'full' }))
  }
  const src = map || {}
  return PERMISSION_MODULES.map((m) => {
    const entry = src[m] || {}
    if (entry.edit) return { module: m, label: '读写', level: 'full' }
    if (entry.view) return { module: m, label: '只读', level: 'view' }
    return { module: m, label: '无权限', level: 'none' }
  })
}

// ============ 耗材库存变动操作类型（中文取值，与后端 ConsumableOpType 严格一致）============
// 入库=绿（增加）、领用=蓝（扣减）、报废=红（扣减）、盘点=橙（重设结存）。
export const CONSUMABLE_OP_OPTIONS = [
  { value: '入库', label: '入库' },
  { value: '领用', label: '领用' },
  { value: '报废', label: '报废' },
  { value: '盘点', label: '盘点' },
]
export const CONSUMABLE_OP_LABELS = {
  入库: '入库',
  领用: '领用',
  报废: '报废',
  盘点: '盘点',
}
export const CONSUMABLE_OP_COLORS = {
  入库: '#22c55e',
  领用: '#409EFF',
  报废: '#ef4444',
  盘点: '#e6a23c',
}
// 各操作类型下「数量」字段的语义提示：入库/领用/报废为本次变动量(≥1)，盘点为盘点后实际结存(≥0)。
export function consumableOpQuantityHint(op) {
  switch (op) {
    case '入库':
      return '本次入库数量（≥1）'
    case '领用':
      return '本次领用数量（≥1）'
    case '报废':
      return '本次报废数量（≥1）'
    case '盘点':
      return '盘点后实际结存（≥0）'
    default:
      return '数量'
  }
}

// ============ 耗材类型配色（同类同色、类型间唯一）============
// 同一 typeId 永远得到同一种颜色（同类耗材同色）；不同 typeId 通过「在全量类型有序列表中的
// 下标」映射到黄金角（137.508°）分隔的色相，保证任意两个类型颜色互不相同（唯一），且不依赖后端存储。
// 配色由 setConsumableTypeOrder(全量类型 id 列表) 统一计算，所有视图共用同一映射，确保一致。

// typeId -> 色相(0~360) 的全局映射。
let _typeColorHues = new Map()

// 以全量类型 id 的有序集合计算配色：排序后按下标取黄金角色相，相邻类型色相差最大、永不重复。
export function setConsumableTypeOrder(ids) {
  const sorted = Array.from(new Set(ids || [])).sort()
  _typeColorHues = new Map()
  sorted.forEach((id, i) => {
    _typeColorHues.set(id, (i * 137.508) % 360)
  })
}

// 取某类型的色相；未登记时回退到基于 id 的稳定哈希（仍保证同类同色）。
function typeHue(typeId) {
  if (!typeId) return null
  if (_typeColorHues.has(typeId)) return _typeColorHues.get(typeId)
  let h = 0
  for (let i = 0; i < typeId.length; i++) {
    h = (h * 31 + typeId.charCodeAt(i)) >>> 0
  }
  return h % 360
}

export function consumableTypeColor(typeId) {
  const hue = typeHue(typeId)
  if (hue === null) return '#909399'
  return `hsl(${hue.toFixed(1)}, 72%, 45%)`
}

// 类型徽章样式：底色 = 类型色 + 透明度，文字 = 类型色，边框 = 类型色 + 透明度。
export function consumableTypeBadgeStyle(typeId) {
  const hue = typeHue(typeId)
  if (hue === null) return { backgroundColor: '#90939922', color: '#909399', borderColor: '#90939955' }
  const c = `hsl(${hue.toFixed(1)}, 72%, 45%)`
  return {
    backgroundColor: `hsla(${hue.toFixed(1)}, 72%, 45%, 0.14)`,
    color: c,
    borderColor: `hsla(${hue.toFixed(1)}, 72%, 45%, 0.45)`,
  }
}
