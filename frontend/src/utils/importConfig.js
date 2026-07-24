// 导入配置（单一事实来源）：三模块的导入字段、模板表头、导出列、以及值归一化。
// field.key 必须与后端 *ImportItem 字段名完全一致（后端据此校验 + 落库）。
// field.label 即模板/文件表头中文名（读取时按 label 反查 key）。
import {
  ROOM_STATUS_OPTIONS,
  RACK_STATUS_OPTIONS,
  DEVICE_TYPE_OPTIONS,
  DEVICE_STATUS_OPTIONS,
  DEVICE_POWER_OPTIONS,
} from './constants'

// 把中文标签 / 英文枚举值统一映射到后端枚举值（找不到则原样返回，交给后端校验）。
function normalizeViaOptions(value, options) {
  if (value == null || value === '') return undefined
  const s = String(value).trim()
  const byVal = options.find((o) => o.value === s)
  if (byVal) return byVal.value
  const byLabel = options.find((o) => o.label === s)
  if (byLabel) return byLabel.value
  return s
}

function toBool(value) {
  if (value == null || value === '') return undefined
  const s = String(value).trim().toLowerCase()
  return s === 'true' || s === '是' || s === '1' || s === 'yes' || s === 'y'
}

// ====================== 机房 ======================
export const roomImportConfig = {
  module: 'room',
  title: '机房',
  // 导入字段（key 对齐 RoomImportItem）
  fields: [
    { key: 'name', label: '名称', required: true, hint: '机房名称' },
    { key: 'code', label: '编号', required: true, hint: '唯一，建议 ROOM-001' },
    { key: 'alias', label: '别名', required: false },
    { key: 'area', label: '区域', required: false },
    { key: 'building', label: '楼宇', required: false },
    { key: 'floor', label: '楼层', required: false },
    { key: 'address', label: '地址', required: false },
    {
      key: 'status',
      label: '状态',
      required: false,
      hint: 'active/disabled 或 启用/停用，默认启用',
    },
  ],
  // 导出列：与 fields 逐字一致（同 key / 同 label / 同顺序），
  // 保证「导出文件列 == 导入模板列 == 回导期望列」，形成完整 round-trip 闭环。
  exportColumns: [
    { key: 'name', label: '名称' },
    { key: 'code', label: '编号' },
    { key: 'alias', label: '别名' },
    { key: 'area', label: '区域' },
    { key: 'building', label: '楼宇' },
    { key: 'floor', label: '楼层' },
    { key: 'address', label: '地址' },
    { key: 'status', label: '状态' },
  ],
  transformItem(item) {
    const out = { ...item }
    out.status = normalizeViaOptions(item.status, ROOM_STATUS_OPTIONS) || item.status
    return out
  },
}

// ====================== 机柜 ======================
export const rackImportConfig = {
  module: 'rack',
  title: '机柜',
  fields: [
    {
      key: 'room_code',
      label: '机房编号',
      required: true,
      hint: '所属机房的编号 code，用于定位机房',
    },
    { key: 'name', label: '名称', required: false },
    { key: 'code', label: '编号', required: true, hint: '机柜编号，建议 RACK-001' },
    { key: 'column_code', label: '列号', required: true, hint: '列编号（如 A），与机柜编号共同定位' },
    { key: 'total_u', label: 'U数', required: false, type: 'integer', hint: '整数，默认 42' },
    { key: 'rack_group', label: '分组', required: false },
    {
      key: 'status',
      label: '状态',
      required: false,
      hint: '可用/空闲/维护中/空调柜/电柜，默认可用',
    },
    { key: 'grid_row', label: '平面行', required: false, type: 'integer' },
    { key: 'grid_col', label: '平面列', required: false, type: 'integer' },
  ],
  // 导出列：与 fields 逐字一致（同 key / 同 label / 同顺序）。
  // 注：导出用「机房编号」(room_code) 而非"所属机房名称"，与导入定位字段一致。
  exportColumns: [
    { key: 'room_code', label: '机房编号' },
    { key: 'name', label: '名称' },
    { key: 'code', label: '编号' },
    { key: 'column_code', label: '列号' },
    { key: 'total_u', label: 'U数' },
    { key: 'rack_group', label: '分组' },
    { key: 'status', label: '状态' },
    { key: 'grid_row', label: '平面行' },
    { key: 'grid_col', label: '平面列' },
  ],
  transformItem(item) {
    const out = { ...item }
    out.status = normalizeViaOptions(item.status, RACK_STATUS_OPTIONS) || item.status
    return out
  },
}

// ====================== 设备 ======================
export const deviceImportConfig = {
  module: 'device',
  title: '设备',
  fields: [
    { key: 'name', label: '设备名称', required: true },
    {
      key: 'device_type',
      label: '设备类型',
      required: true,
      hint: 'server/switch/... 或中文（服务器/交换机…）',
    },
    { key: 'u_height', label: 'U数', required: false, type: 'integer', hint: '整数，默认 1' },
    { key: 'model', label: '型号', required: false },
    { key: 'device_code', label: '设备编号', required: false, hint: '留空自动生成' },
    { key: 'sn', label: '序列号', required: false },
    { key: 'ip_address', label: 'IP地址', required: false, hint: '需带 CIDR，如 1.2.3.4/24' },
    { key: 'warranty_expire', label: '保修到期', required: false, hint: 'YYYY-MM-DD' },
    { key: 'status', label: '设备状态', required: false, hint: '在库/已上架/待报废/借出' },
    { key: 'power_status', label: '开关机', required: false, hint: '开机/关机' },
    {
      key: 'is_asset',
      label: '是否资产',
      required: false,
      type: 'boolean',
      hint: 'true/false；设施填 false',
    },
    { key: 'remark', label: '备注', required: false },
  ],
  // 导出列：与 fields 逐字一致（同 key / 同 label / 同顺序）。
  // 列出全部可导入的固有字段（型号标签统一为「型号」，与导入 fields 一致）。
  exportColumns: [
    { key: 'name', label: '设备名称' },
    { key: 'device_type', label: '设备类型' },
    { key: 'u_height', label: 'U数' },
    { key: 'model', label: '型号' },
    { key: 'device_code', label: '设备编号' },
    { key: 'sn', label: '序列号' },
    { key: 'ip_address', label: 'IP地址' },
    { key: 'warranty_expire', label: '保修到期' },
    { key: 'status', label: '设备状态' },
    { key: 'power_status', label: '开关机' },
    { key: 'is_asset', label: '是否资产' },
    { key: 'remark', label: '备注' },
  ],
  transformItem(item) {
    const out = { ...item }
    out.device_type = normalizeViaOptions(item.device_type, DEVICE_TYPE_OPTIONS)
    out.status = normalizeViaOptions(item.status, DEVICE_STATUS_OPTIONS)
    out.power_status = normalizeViaOptions(item.power_status, DEVICE_POWER_OPTIONS)
    const b = toBool(item.is_asset)
    if (b !== undefined) out.is_asset = b
    else delete out.is_asset
    return out
  },
}

export const importConfigMap = {
  room: roomImportConfig,
  rack: rackImportConfig,
  device: deviceImportConfig,
}

// 生成模板的「列定义」：必填字段表头追加「 *」标记。
export function templateColumns(config) {
  return config.fields.map((f) => ({
    key: f.key,
    label: f.label + (f.required ? ' *' : ''),
  }))
}

// 前端预校验：检查每行的必填字段是否为空（后端仍会做完整校验）。
// 返回 [{ row, errors:[string] }]，row 为 1-based 数据行号。
export function validateRequired(rows, config) {
  const required = config.fields.filter((f) => f.required)
  const failures = []
  rows.forEach((row, idx) => {
    const errors = []
    for (const f of required) {
      const v = row[f.label]
      if (v == null || String(v).trim() === '') {
        errors.push(`必填字段「${f.label}」为空`)
      }
    }
    if (errors.length) failures.push({ row: idx + 1, errors })
  })
  return failures
}
