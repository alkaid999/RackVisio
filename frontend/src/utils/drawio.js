// 机房拓扑导出为 draw.io（diagrams.net）格式：生成一段 mxGraphModel XML。
// 直接使用 draw.io 自带的「机架图形」stencil，无需自绘 SVG：
//   - 机柜：mxgraph.rackGeneral.rackCabinet3（含 childLayout=rack，自动按 U 绘制刻度）
//   - 设备：mxgraph.rack.dell.* / mxgraph.rack.f5.* 等真实机架设备图形，按 U 位精确落位
// 双击 .drawio 即可在 diagrams.net 中打开，设备图形可继续编辑/替换。
// 设备类型标签自包含（与 constants.js 同源，避免导出工具依赖 vue reactive 常量）。
const DEVICE_TYPE_LABELS = {
  server: '服务器',
  switch: '交换机',
  firewall: '防火墙',
  router: '路由器',
  waf: 'WAF',
  security: '安全设备',
  other: '其他',
}

// draw.io 机架 stencil 几何参数（与示例文件一致）
const RACK_W = 204
const RACK_UNIT = 14.8 // 每 U 像素高
const M = { top: 21, bottom: 22, left: 33, right: 9 }
const INNER_W = RACK_W - M.left - M.right // 162
const GAP = 56
const COLS = 5
const TITLE_H = 26
const ROOM_TITLE_H = 40

// 设备类型 → draw.io 内置机架设备 stencil：
//   server/router/switch/other → Dell PowerEdge 系列（1U/2U/4U 变体）
//   firewall/waf/security      → F5 安全设备系列（真实机架外观）
function stencilFor(type, uH) {
  const dell = {
    1: 'mxgraph.rack.dell.dell_poweredge_1u',
    2: 'mxgraph.rack.dell.dell_poweredge_2u',
    4: 'mxgraph.rack.dell.dell_poweredge_4u',
  }
  const dellShape = dell[uH] || (uH >= 3 ? dell[4] : dell[2])
  const f5 = uH <= 2 ? 'mxgraph.rack.f5.big_ip_2x00' : 'mxgraph.rack.f5.viprion_4800'
  switch (type) {
    case 'firewall':
    case 'waf':
    case 'security':
      return f5
    default:
      return dellShape
  }
}

// XML 转义（& < > "），保证 value 内的 HTML 与用户文本不会破坏 mxGraphModel 结构。
function escapeXml(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

// 多行文本：逐行转义后以 <br> 连接（style 含 html=1，draw.io 加载后按 HTML 渲染）。
function textBlock(lines) {
  return lines.filter(Boolean).map(escapeXml).join('<br>')
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
    'container=1;collapsible=0;childLayout=rack;allowGaps=1;' +
    'marginLeft=' + M.left + ';marginRight=' + M.right + ';marginTop=' + M.top + ';marginBottom=' + M.bottom + ';' +
    'textColor=#666666;numDisp=ascend;'
  )
}

function deviceStyle(stencil) {
  return (
    'strokeColor=#666666;html=1;labelPosition=right;align=left;spacingLeft=15;shadow=0;' +
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

  // 先算每台机柜高度与最大高度，用于网格排版
  const layout = ordered.map((rack, i) => {
    const totalU = rack.total_u || 42
    const cabH = M.top + totalU * RACK_UNIT + M.bottom
    return { rack, col: i % COLS, row: Math.floor(i / COLS), totalU, cabH }
  })
  const maxCabH = layout.reduce((m, l) => Math.max(m, l.cabH), 0)
  const strideX = RACK_W + GAP
  const strideY = maxCabH + TITLE_H + GAP

  // 机房标题
  cells.push(
    cell(
      nid(),
      textBlock([
        `<b>${room?.name || '机房'}</b>`,
        `机柜 ${racks?.length || 0} 台 · 导出自 RackVisio`,
      ]),
      'text;html=1;fillColor=none;strokeColor=none;verticalAlign=middle;fontSize=18;',
      20,
      0,
      400,
      ROOM_TITLE_H
    )
  )

  for (const { rack, col, row, totalU, cabH } of layout) {
    const cabX = 20 + col * strideX
    const cabY = ROOM_TITLE_H + TITLE_H + row * strideY
    const titleY = ROOM_TITLE_H + row * strideY

    // 机柜标题（名称 / 编号 / 已用U）
    const used = rack.used_u ?? 0
    cells.push(
      cell(
        nid(),
        textBlock([
          `<b>${escapeXml(rack.name || '机柜')}</b>`,
          `${escapeXml(rack.code || '')}${totalU ? ' · ' + used + '/' + totalU + 'U' : ''}`,
        ]),
        'text;html=1;fillColor=none;strokeColor=none;verticalAlign=middle;align=left;fontSize=12;',
        cabX,
        titleY,
        RACK_W,
        TITLE_H
      )
    )

    // 机柜本体（draw.io 内置机架图形）
    const cabId = nid()
    cells.push(cell(cabId, '', cabinetStyle(totalU), cabX, cabY, RACK_W, cabH))

    // 设备：按 U 位精确落位（U1 在底，numDisp=ascend 向上递增）
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
      const label = DEVICE_TYPE_LABELS[d.device_type] || d.device_type || ''
      const lines = [`<b>${d.name || '未命名设备'}</b>`]
      if (label || d.model) lines.push(`${label}${d.model ? ' · ' + d.model : ''}`)
      if (d.ip_address) lines.push('IP ' + d.ip_address)
      cells.push(cell(nid(), textBlock(lines), deviceStyle(stencilFor(d.device_type, uH)), M.left, y, INNER_W, h, cabId))
    }
  }

  return (
    `<?xml version="1.0" encoding="UTF-8"?>\n` +
    `<mxGraphModel dx="800" dy="600" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="0" pageScale="1" pageWidth="1200" pageHeight="1600" math="0" shadow="0">\n` +
    `  <root>\n    ${cells.join('\n    ')}\n  </root>\n</mxGraphModel>`
  )
}
