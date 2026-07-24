// 机房拓扑导出为 draw.io（diagrams.net）格式：生成一段 mxGraphModel XML。
// 直接使用 draw.io 自带的「机架图形」stencil：
//   - 机柜：mxgraph.rackGeneral.rackCabinet3（diagrams.net「Numbered Rack Cabinet」；U 数编号由 numDisp 参数控制：
//            ascend=升序 / descend=降序 / off=关闭。用 numDisp=descend 使顶端标最大 U、底端标 1U，与设备 U1 在底向上递增一致）
//   - 交换机：HPE Aruba 机架 stencil（用户指定，按 U 高分层：<5U=Aruba 6300M，≥5U=Aruba CX 6410）
//   - 服务器：Dell PowerEdge（1U/2U/4U 真实硬件图；≥5U=Oracle Netra CT900 刀片机箱）
//   - 路由器：Cisco（<5U=7603；≥5U=ASR 9006）
//   - 安全设备：F5（1-2U=ARX 500；3-4U=BIG-IP 110x0；≥5U=VIPRION 4400）
//   - 设施（非资产）：配线架=cat5e_enhanced_patch_panel_48_ports；ODF配线架=sun_zfs_storage_7320；其他设施=sun_storage_2500-m2_array
//   - 多 U 框式/刀片设备（≥5U）：自定义内联机箱图形（矢量 SVG，按槽位高度缩放，含模块槽位装饰），避免真实硬件图被拉伸变形
// 设备标签为彩色文本框（沿用类型配色），仅含设备名称；
// 机柜名称文本框居中显示于机柜顶部；机房名称居中显示于机房正上方。
// 设备类型配色/标签自包含（与 constants.js 同源，避免导出工具依赖 vue reactive 常量）。
const DEVICE_TYPE_COLORS = {
  server: '#409EFF',
  switch: '#67C23A',
  router: '#13C2C2',
  security: '#E6A23C',
  other: '#909399',
  // 基础设施（非资产）
  patch: '#64748b',
  odf: '#64748b',
  other_facility: '#94a3b8',
}
const DEVICE_TYPE_LABELS = {
  server: '服务器',
  switch: '交换机',
  router: '路由器',
  security: '安全设备',
  other: '其他设备',
  patch: '配线架',
  odf: 'ODF配线架',
  other_facility: '其他设施',
}

// draw.io 机架 stencil 几何参数（与示例文件一致）
const RACK_W = 204
const RACK_UNIT = 14.8 // 每 U 像素高
const M = { top: 21, bottom: 22, left: 33, right: 9 }
const INNER_W = RACK_W - M.left - M.right // 162
// 机柜横向间距：设备标签 labelPosition=right 向右延伸，间距需足够大，避免下一台机柜遮挡本柜设备标签。
const GAP = 180
const COLS = 5
const TITLE_H = 26
const ROOM_TITLE_H = 66 // 机房标题占用的顶部区域（含与下方机柜的间隔）
const ROOM_TITLE_BLOCK_H = 44 // 机房标题文本框实际高度（小于 ROOM_TITLE_H → 下方留出间隔）

// 设备图形选择（分层，精确到具体图形）：
//   1) 逐设备精确指定：数据携带 stencil 字段 → 直接作为 draw.io 机架 stencil ID 使用
//   2) 型号映射表：按 model 命中 MODEL_STENCIL_MAP（前端可自由扩展）
//   3) 高度感知兜底：≥5U 框式/刀片 → 自定义内联机箱图形；≤4U → 真实固定 U 硬件图形
// 返回：stencil ID 字符串，或 '__chassis__'（自定义内联机箱图形标记）

// 各类型按 U 高的精确图形映射（用户指定）：
//   服务器  1U=dell_poweredge_1u / 2U=dell_poweredge_2u / 3-4U=dell_poweredge_4u / ≥5U=oracle.netra_ct900_atca_blade_server
//   路由器  <5U=cisco_7603_router / ≥5U=cisco_asr_9006
//   安全设备 1-2U=f5.arx_500 / 3-4U=f5.big_ip_110x0 / ≥5U=f5.viprion_4400
//   其它/未知 → 自定义内联机箱图形（__chassis__）
function typeStencil(type, uH) {
  switch (type) {
    case 'server':
      if (uH === 1) return 'mxgraph.rack.dell.dell_poweredge_1u'
      if (uH === 2) return 'mxgraph.rack.dell.dell_poweredge_2u'
      if (uH <= 4) return 'mxgraph.rack.dell.dell_poweredge_4u'
      return 'mxgraph.rack.oracle.netra_ct900_atca_blade_server'
    case 'router':
      return uH >= 5 ? 'mxgraph.rack.cisco.cisco_asr_9006' : 'mxgraph.rack.cisco.cisco_7603_router'
    case 'security':
      if (uH <= 2) return 'mxgraph.rack.f5.arx_500'
      if (uH <= 4) return 'mxgraph.rack.f5.big_ip_110x0'
      return 'mxgraph.rack.f5.viprion_4400'
    // 基础设施（非资产）：用户指定精确机架 stencil
    case 'patch':
      return 'mxgraph.rack.general.cat5e_enhanced_patch_panel_48_ports'
    case 'odf':
      return 'mxgraph.rack.oracle.sun_zfs_storage_7320'
    case 'other_facility':
      return 'mxgraph.rack.oracle.sun_storage_2500-m2_array'
    default:
      return '__chassis__'
  }
}

// 前端型号 → 图形映射表（按 model 不区分大小写命中，可自由增删）。
//   kind:'chassis' → 自定义内联机箱图形（多 U 框式/刀片/机箱级设备，避免真实硬件图被拉伸）
//   kind:'stencil' → 直接使用指定 draw.io 通用机架设备图形 ID（mxgraph.rack.*，为缩放设计）
const MODEL_STENCIL_MAP = [
  // 框式/刀片 数据中心级交换机、机箱级设备 → 自定义机箱图形
  { test: /nexus\s*7|nexus\s*9|ce128|s12500|cloudengine|框式|刀片|chassis|qsfp|机箱|srx[0-9]000/i, kind: 'chassis' },
  // 具体型号 → 精确通用图形（draw.io 自带，可扩展更多）
  { test: /nexus\s*[23]|catalyst\s*9|s[567]\d{3}/i, kind: 'stencil', id: 'mxgraph.rack.switch' },
  { test: /netapp|emc|unity|storeeasy|存储阵列|array/i, kind: 'stencil', id: 'mxgraph.rack.storage' },
  { test: /patch|配线架|patchpanel/i, kind: 'stencil', id: 'mxgraph.rack.patchPanel' },
  { test: /ups|不间断电源/i, kind: 'stencil', id: 'mxgraph.rack.ups' },
  { test: /pdu|电源分配/i, kind: 'stencil', id: 'mxgraph.rack.pdu' },
  { test: /kvm/i, kind: 'stencil', id: 'mxgraph.rack.kvm' },
]

function matchModel(model) {
  if (!model) return null
  const m = String(model)
  for (const e of MODEL_STENCIL_MAP) {
    if (e.test.test(m)) return e
  }
  return null
}

// 自定义内联机箱图形：矢量 SVG（按设备类型配色），含顶部把手条 + 模块槽位装饰，
// 用 data:image/svg+xml 内联，draw.io 以 shape=image 渲染并按槽位高度缩放，不被拉伸变形。
function chassisSvg(type, uH) {
  const c = DEVICE_TYPE_COLORS[type] || DEVICE_TYPE_COLORS.other
  const W = 162
  const H = 100
  const slots = Math.max(3, Math.min(8, Math.round(uH / 2)))
  const top = 22
  const gap = (H - top - 6) / slots
  let lines = ''
  for (let i = 0; i < slots; i++) {
    const y = top + 4 + i * gap
    lines +=
      `<rect x='8' y='${y.toFixed(1)}' width='${W - 16}' height='${(gap * 0.55).toFixed(1)}' rx='2' fill='#000000' fill-opacity='0.14'/>`
  }
  const svg =
    `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 ${W} ${H}' preserveAspectRatio='none'>` +
    `<rect x='1.5' y='1.5' width='${W - 3}' height='${H - 3}' rx='7' fill='${c}' stroke='#000000' stroke-opacity='0.4' stroke-width='1.5'/>` +
    `<rect x='1.5' y='1.5' width='${W - 3}' height='18' rx='7' fill='#000000' fill-opacity='0.2'/>` +
    `<circle cx='16' cy='10.5' r='3' fill='#ffffff' fill-opacity='0.65'/>` +
    `<circle cx='28' cy='10.5' r='3' fill='#ffffff' fill-opacity='0.65'/>` +
    lines +
    `</svg>`
  return 'data:image/svg+xml,' + encodeURIComponent(svg)
}

function chassisStyle(type, uH) {
  return 'shape=image;image=' + chassisSvg(type, uH) + ';html=1;labelPosition=right;align=left;spacingLeft=8;shadow=0;'
}

// 交换机专用图形：用户指定的 HPE Aruba 机架 stencil（按 U 高分层）
//   <5U → Aruba 6300M（48×1GbE + 4×SFP56）
//   ≥5U → Aruba CX 6410（机箱级框式）
// 这些 shape 字符串来自 draw.io 内置「Rack」图形库，直接引用即可，无需内嵌图片。
const SWITCH_STENCIL_LT5U =
  'mxgraph.rack.hpe_aruba.switches.jl663a_aruba_6300m_48_port_1gbe_and_4_port_sfp56_switch'
const SWITCH_STENCIL_GE5U = 'mxgraph.rack.hpe_aruba.switches.r0x27a_aruba_cx_6410_switch'

function stencilFor(d) {
  // 1) 逐设备精确指定（数据携带 stencil 字段时优先）
  if (d.stencil) return d.stencil
  // 2) 交换机：按用户指定的 HPE Aruba stencil（高度感知）
  if (d.device_type === 'switch') {
    return (d.u_height || 1) >= 5 ? SWITCH_STENCIL_GE5U : SWITCH_STENCIL_LT5U
  }
  // 3) 型号映射表
  const hit = matchModel(d.model)
  if (hit) return hit.kind === 'chassis' ? '__chassis__' : hit.id
  // 4) 按类型的精确 U 高映射
  return typeStencil(d.device_type, d.u_height || 1)
}

// XML 转义（& < > "），保证生成的 mxGraphModel 属性合法。
function escapeXml(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}
const esc = escapeXml

// 转义规则（关键，避免 draw.io 显示原始 HTML 标签）：
//   1) 调用方负责把「用户文本」用 esc() 转义；
//   2) 结构标签（<b> / <br>）以【真实标签】形式拼入（不参与 esc）；
//   3) cell() 对整段 value 再做【一次】escapeXml —— 全程仅转义一次。
// draw.io 加载时反转义一次，即得到 <b>..</b><br>.. 并当 HTML 渲染（style 含 html=1）。
// textBlock 仅用 <br> 连接已准备好的成品 HTML 行，自身不再转义。
function textBlock(lines) {
  return lines.filter(Boolean).join('<br>')
}

function cell(id, value, style, x, y, w, h, parent) {
  return (
    `<mxCell id="${id}" value="${escapeXml(value)}" style="${style}" vertex="1" parent="${parent || '1'}">` +
    `<mxGeometry x="${x}" y="${y}" width="${w}" height="${h}" as="geometry"/></mxCell>`
  )
}

function cabinetStyle(totalU) {
  return (
    'strokeColor=#666666;html=1;verticalLabelPosition=bottom;labelBackgroundColor=#ffffff;' +
    'verticalAlign=top;outlineConnect=0;shadow=0;dashed=0;' +
    'shape=mxgraph.rackGeneral.rackCabinet3;rackUnitSize=' + RACK_UNIT + ';fillColor2=#f4f4f4;' +
    'container=1;collapsible=0;childLayout=rack;allowGaps=1;numDisp=descend;' +
    'marginLeft=' + M.left + ';marginRight=' + M.right + ';marginTop=' + M.top + ';marginBottom=' + M.bottom + ';' +
    'textColor=#666666;'
  )
}

function deviceStyle(stencil) {
  return (
    'strokeColor=#666666;html=1;labelPosition=right;align=left;spacingLeft=8;shadow=0;' +
    'dashed=0;outlineConnect=0;shape=' + stencil + ';'
  )
}

// 主入口：根据当前机房数据生成完整 .drawio XML 文本。
//   room:        { name, ... }
//   racks:       [{ id, name, code, total_u, used_u, grid_col, grid_row, status, ... }]
//   rackDevices: { [rackId]: [device, ...] }   device 含 current_start_u/u_height/device_type/name/model/sn/ip_address/device_code/power_status
export function buildRoomDrawioXml({ room, racks, rackDevices }) {
  let seq = 0
  const nid = () => `n${++seq}`
  const cells = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>']

  const ordered = [...(racks || [])].sort(
    (a, b) => (a.grid_row ?? 0) - (b.grid_row ?? 0) || (a.grid_col ?? 0) - (b.grid_col ?? 0)
  )

  // 按机房真实站位（grid_row × grid_col）排布，而非强制一行/固定每行数量。
  // 所有机柜均有有效站位时，用真实坐标计算行列；否则退化为顺序换行布局。
  const hasGrid = ordered.length > 0 && ordered.every((r) => r.grid_col != null && r.grid_row != null)
  let posOf
  if (hasGrid) {
    const minCol = Math.min(...ordered.map((r) => r.grid_col))
    const minRow = Math.min(...ordered.map((r) => r.grid_row))
    posOf = (r) => ({ col: r.grid_col - minCol, row: r.grid_row - minRow })
  } else {
    posOf = (r, i) => ({ col: i % COLS, row: Math.floor(i / COLS) })
  }

  // 先算每台机柜高度与最大高度，用于网格排版
  const layout = ordered.map((rack, i) => {
    const totalU = rack.total_u || 42
    const cabH = M.top + totalU * RACK_UNIT + M.bottom
    const p = posOf(rack, i)
    return { rack, col: p.col, row: p.row, totalU, cabH }
  })
  const maxCol = layout.reduce((m, l) => Math.max(m, l.col), 0)
  const maxRow = layout.reduce((m, l) => Math.max(m, l.row), 0)
  const maxCabH = layout.reduce((m, l) => Math.max(m, l.cabH), 0)
  const strideX = RACK_W + GAP
  const strideY = maxCabH + TITLE_H + GAP
  const colCount = maxCol + 1
  const rowCount = maxRow + 1
  const diagramW = colCount * RACK_W + (colCount - 1) * GAP

  // 机房名称：居中显示于机房正上方（y=0 顶部，不遮挡下方机柜）
  cells.push(
    cell(
      nid(),
      textBlock([
        `<b style='font-size:22px;'>${esc(room?.name || '机房')}</b>`,
        `<span style='font-size:12px;font-weight:400;opacity:0.8;'>机柜 ${racks?.length || 0} 台 · 导出自 RackVisio</span>`,
      ]),
      'text;html=1;align=center;verticalAlign=middle;',
      20,
      0,
      diagramW,
      ROOM_TITLE_BLOCK_H
    )
  )

  for (const { rack, col, row, totalU, cabH } of layout) {
    const cabX = 20 + col * strideX
    const cabY = ROOM_TITLE_H + TITLE_H + row * strideY
    const titleY = ROOM_TITLE_H + row * strideY

    // 机柜名称文本框：居中显示于机柜顶部，与机柜作为一个整体
    const used = rack.used_u ?? 0
    const rackNameBits = [esc(rack.name || '机柜')]
    if (rack.code) rackNameBits.push(esc(rack.code))
    cells.push(
      cell(
        nid(),
        rackNameBits.join(' · '),
        'text;html=1;align=center;verticalAlign=middle;rounded=1;fillColor=#1E293B;strokeColor=#334155;fontColor=#F8FAFC;fontSize=12;',
        cabX,
        titleY,
        RACK_W,
        TITLE_H
      )
    )

    // 机柜本体（draw.io 内置机架图形）
    const cabId = nid()
    cells.push(cell(cabId, '', cabinetStyle(totalU), cabX, cabY, RACK_W, cabH))

    // 设备：按 U 位精确落位（U1 在底，向上递增）
    const devs = (rackDevices?.[rack.id] || [])
      .filter((d) => d.current_start_u != null)
      .sort((a, b) => b.current_start_u - a.current_start_u)
    for (const d of devs) {
      const uH = d.u_height || 1
      const startU = d.current_start_u
      const topU = startU + uH - 1
      // 子图形坐标相对机柜本体（parent=cabId）
      const y = M.top + (totalU - topU) * RACK_UNIT
      const h = uH * RACK_UNIT
      const c = DEVICE_TYPE_COLORS[d.device_type] || DEVICE_TYPE_COLORS.other
      // 设备标签＝彩色文本框（沿用类型配色），仅显示设备名称
      const labelHtml =
        `<div style='background:${c};color:#fff;border-radius:4px;padding:2px 8px;` +
        `font-size:11px;font-weight:600;white-space:nowrap;display:inline-block;'>` +
        `${esc(d.name || '未命名设备')}</div>`
      // 图形：自定义机箱图形(__chassis__) 或 draw.io 机架 stencil（含逐设备精确指定/型号映射/高度兜底）
      const sf = stencilFor(d)
      const devStyle = sf === '__chassis__' ? chassisStyle(d.device_type, uH) : deviceStyle(sf)
      // childLayout=rack 模式下，子节点坐标以机柜本体（parent=cabId）左上角为 (0,0)。
      // 机柜内部 U 槽位区域左缘 = marginLeft（与 cabinetStyle 的 marginLeft 一致），
      // 故设备 x 必须 = M.left（即 marginLeft=33），宽度 = INNER_W（= RACK_W - marginLeft - marginRight）。
      // 若 x=0，设备会从机柜最左缘（含左侧边框/导轨区）开始，整体偏左并溢出机柜。
      cells.push(cell(nid(), labelHtml, devStyle, M.left, y, INNER_W, h, cabId))
    }
  }

  return (
    `<?xml version="1.0" encoding="UTF-8"?>\n` +
    `<mxGraphModel dx="800" dy="600" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="0" pageScale="1" pageWidth="1200" pageHeight="1600" math="0" shadow="0">\n` +
    `  <root>\n    ${cells.join('\n    ')}\n  </root>\n</mxGraphModel>`
  )
}
