// ECharts 明暗双主题令牌：随当前主题返回配色，供 BaseChart 注入。
export function chartTheme(dark) {
  if (dark) {
    return {
      text: '#c7cdda',
      split: 'rgba(148,163,184,0.10)',
      axis: 'rgba(148,163,184,0.28)',
      tooltipBg: 'rgba(20,23,32,0.94)',
      tooltipText: '#e4e7ef',
      border: 'rgba(148,163,184,0.18)',
      palette: ['#60a5fa', '#34d399', '#fbbf24', '#f87171', '#a78bfa', '#22d3ee', '#fb923c'],
    }
  }
  return {
    text: '#475569',
    split: 'rgba(15,23,42,0.06)',
    axis: 'rgba(15,23,42,0.18)',
    tooltipBg: 'rgba(255,255,255,0.96)',
    tooltipText: '#334155',
    border: 'rgba(15,23,42,0.08)',
    palette: ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#f97316'],
  }
}
