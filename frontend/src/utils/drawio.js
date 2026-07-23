// 机房拓扑导出为 draw.io（diagrams.net）格式：生成一段 mxGraphModel XML。
// 布局采用「平面列表式」：机房标题 → 按 grid_col/grid_row 排序的机柜分组，
// 每组机柜表头 + 其下设备列表；每台设备用「类型专属 SVG 图标 + 信息标签」渲染，
// 双击 .drawio 即可在 diagrams.net 中打开并继续编辑。
// 设备类型配色/标签自包含（与 constants.js 同源，避免导出工具依赖 vue reactive 常量）。
const DEVICE_TYPE_COLORS = {
  server: '#409EFF',
  switch: '#67C23A',
  firewall: '#F97316',
  router: '#13C2C2',
  waf: '#EB4895',
  security: '#E6A23C',
  other: '#909399',
}
const DEVICE_TYPE_LABELS = {
  server: '服务器',
  switch: '交换机',
  firewall: '防火墙',
  router: '路由器',
  waf: 'WAF',
  security: '安全设备',
  other: '其他',
}

// —— 设备类型 SVG 图标（内联 data URI，打开即得、跨版本稳定）——
function svgWrap(inner) {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32">${inner}</svg>`
}
function iconSvg(type) {
  const c = DEVICE_TYPE_COLORS[type] || DEVICE_TYPE_COLORS.other
  switch (type) {
    case 'server':
      return svgWrap(
        `<rect x="4" y="4" width="24" height="24" rx="2" fill="${c}"/>` +
          `<rect x="7" y="8" width="18" height="3" rx="1" fill="#fff" opacity="0.85"/>` +
          `<rect x="7" y="14" width="18" height="3" rx="1" fill="#fff" opacity="0.85"/>` +
          `<circle cx="9" cy="22" r="1.6" fill="#fff"/>` +
          `<rect x="13" y="20.5" width="12" height="3" rx="1" fill="#fff" opacity="0.6"/>`
      )
    case 'switch':
      return svgWrap(
        `<rect x="4" y="6" width="24" height="20" rx="2" fill="${c}"/>` +
          Array.from({ length: 6 })
            .map((_, i) => `<rect x="${6 + i * 4}" y="10" width="2.4" height="6" fill="#fff" opacity="0.85"/>`)
            .join('') +
          `<rect x="6" y="20" width="20" height="2.4" rx="1" fill="#fff" opacity="0.5"/>`
      )
    case 'firewall':
      return svgWrap(
        `<rect x="4" y="5" width="24" height="22" rx="2" fill="${c}"/>` +
          `<path d="M4 11h24M4 17h24M10 5v22M17 5v22M24 5v22" stroke="#fff" stroke-width="1.4" opacity="0.7"/>`
      )
    case 'router':
      return svgWrap(
        `<rect x="5" y="12" width="22" height="12" rx="2" fill="${c}"/>` +
          `<path d="M16 12V6" stroke="${c}" stroke-width="2"/>` +
          `<circle cx="16" cy="5" r="2" fill="${c}"/>` +
          `<circle cx="10" cy="18" r="1.6" fill="#fff"/>` +
          `<circle cx="16" cy="18" r="1.6" fill="#fff"/>` +
          `<circle cx="22" cy="18" r="1.6" fill="#fff"/>`
      )
    case 'waf':
      return svgWrap(
        `<path d="M16 3l11 4v7c0 7-5 11-11 14C10 25 5 21 5 14V7z" fill="${c}"/>` +
          `<text x="16" y="18" font-size="7" fill="#fff" text-anchor="middle" font-family="Arial">WAF</text>`
      )
    case 'security':
      return svgWrap(
        `<path d="M16 3l11 4v7c0 7-5 11-11 14C10 25 5 21 5 14V7z" fill="${c}"/>` +
          `<path d="M11 15l3.5 3.5L22 11" stroke="#fff" stroke-width="2" fill="none"/>`
      )
    default:
      return svgWrap(
        `<rect x="5" y="7" width="22" height="18" rx="2" fill="${c}"/>` +
          `<rect x="8" y="11" width="16" height="3" rx="1" fill="#fff" opacity="0.7"/>` +
          `<circle cx="10" cy="20" r="1.5" fill="#fff"/>`
      )
  }
}
function iconDataUri(type) {
  return 'data:image/svg+xml,' + encodeURIComponent(iconSvg(type))
}

// XML 转义（& < > "），保证 value 内的 HTML 与用户文本不会破坏 mxGraphModel 结构。
function escapeXml(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function deviceValue(d) {
  const type = d.device_type
  const c = DEVICE_TYPE_COLORS[type] || DEVICE_TYPE_COLORS.other
  const label = DEVICE_TYPE_LABELS[type] || type
  const uri = iconDataUri(type)
  const lines = []
  lines.push(`<div style='font-weight:700;font-size:13px;color:${c};'>${d.name || '未命名设备'}</div>`)
  lines.push(`<div style='font-size:11px;color:#475569;'>${label}${d.model ? ' · ' + d.model : ''}</div>`)
  if (d.ip_address) {
    lines.push(`<div style='font-size:11px;color:#475569;'>IP ${d.ip_address}</div>`)
  }
  const meta = []
  if (d.device_code) meta.push('编码 ' + d.device_code)
  if (d.sn) meta.push('SN ' + d.sn)
  if (d.power_status) meta.push(d.power_status)
  if (meta.length) {
    lines.push(`<div style='font-size:10px;color:#94a3b8;'>${meta.join(' · ')}</div>`)
  }
  return (
    `<div style='display:flex;align-items:center;gap:8px;padding:4px;'>` +
    `<img src='${uri}' style='width:34px;height:34px;flex:0 0 auto;'/>` +
    `<div style='min-width:0;'>${lines.join('')}</div></div>`
  )
}

function deviceStyle(d) {
  const c = DEVICE_TYPE_COLORS[d.device_type] || DEVICE_TYPE_COLORS.other
  return `rounded=1;whiteSpace=wrap;html=1;fillColor=#F8FAFC;strokeColor=${c};strokeWidth=1.5;verticalAlign=middle;shadow=0;`
}

function cell(id, value, style, x, y, w, h, parent) {
  // 整段 value 统一 XML 转义一次：内含的 HTML 标签(<div>/<img>)会被转义存储，
  // draw.io 加载时反转义并作为 HTML 渲染（style 含 html=1）。
  return (
    `<mxCell id="${id}" value="${escapeXml(value)}" style="${style}" vertex="1" parent="${parent || '1'}">` +
    `<mxGeometry x="${x}" y="${y}" width="${w}" height="${h}" as="geometry"/></mxCell>`
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

  const X = 20
  const COL_W = 320
  let y = 20

  // 机房标题
  const title = room?.name || '机房'
  cells.push(
    cell(
      nid(),
      `<div style='font-weight:700;font-size:18px;'>${title}</div>` +
        `<div style='font-size:12px;color:#64748b;'>机柜 ${racks.length} 台 · 导出自 RackVisio</div>`,
      'text;html=1;fillColor=none;strokeColor=none;verticalAlign=middle;',
      X,
      y,
      COL_W,
      44
    )
  )
  y += 44 + 14

  // 机柜按 grid_col / grid_row 排序，保持与 3D 总览一致的空间次序
  const ordered = [...(racks || [])].sort(
    (a, b) => (a.grid_col ?? 0) - (b.grid_col ?? 0) || (a.grid_row ?? 0) - (b.grid_row ?? 0)
  )

  for (const rack of ordered) {
    const used = rack.used_u ?? 0
    const total = rack.total_u ?? 0
    const headerVal =
      `<div style='font-weight:700;font-size:13px;color:#fff;'>${rack.name || '机柜'}</div>` +
      `<div style='font-size:11px;color:#cbd5e1;'>${rack.code || ''}${
        total ? ' · ' + used + '/' + total + 'U' : ''
      }</div>`
    cells.push(
      cell(
        nid(),
        headerVal,
        'rounded=1;whiteSpace=wrap;html=1;fillColor=#1E293B;strokeColor=#334155;verticalAlign=middle;shadow=0;',
        X,
        y,
        COL_W,
        36
      )
    )
    y += 36 + 8

    const devs = (rackDevices?.[rack.id] || [])
      .filter((d) => d.current_start_u != null)
      .sort((a, b) => b.current_start_u - a.current_start_u)
    if (!devs.length) {
      cells.push(
        cell(
          nid(),
          `<div style='font-size:11px;color:#94a3b8;padding:4px;'>（无上架设备）</div>`,
          'rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#E2E8F0;dashed=1;verticalAlign=middle;',
          X,
          y,
          COL_W,
          28
        )
      )
      y += 28 + 6
    } else {
      for (const d of devs) {
        cells.push(cell(nid(), deviceValue(d), deviceStyle(d), X, y, COL_W, 64))
        y += 64 + 6
      }
    }
    y += 14 // 机柜之间留白
  }

  return (
    `<?xml version="1.0" encoding="UTF-8"?>\n` +
    `<mxGraphModel dx="800" dy="600" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="0" pageScale="1" pageWidth="850" pageHeight="1200" math="0" shadow="0">\n` +
    `  <root>\n    ${cells.join('\n    ')}\n  </root>\n</mxGraphModel>`
  )
}
