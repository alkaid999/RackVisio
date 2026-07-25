// 功率数值格式化工具
// 规则：>= 1000W 自动换算为 kW 显示；瓦的单位符号 W 必须大写。
export function formatPower(w) {
  if (w === null || w === undefined || w === '') return '—'
  const val = Number(w)
  if (Number.isNaN(val)) return '—'
  if (val === 0) return '0 W'
  if (Math.abs(val) >= 1000) {
    // 保留最多 2 位小数并去掉多余尾随零，如 5000 -> 5kW、1500 -> 1.5kW、1234 -> 1.23kW
    const kwStr = parseFloat((val / 1000).toFixed(2)).toString()
    return `${kwStr}kW`
  }
  return `${val} W`
}
