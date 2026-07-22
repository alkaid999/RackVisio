// HTML 转义工具：防止用户可控字段（设备名/IP/型号等）经 innerHTML 注入。
// 用法：tooltip.innerHTML = `<div>${escapeHtml(d.name)}</div>`

export function escapeHtml(value) {
  if (value === null || value === undefined) return ''
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

export default escapeHtml
