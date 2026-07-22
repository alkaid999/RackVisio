/**
 * 统一时间格式化工具。
 *
 * 后端所有时间字段统一以 naive UTC 存储与返回（ISO 字符串不带时区标记）。
 * 若直接交给浏览器 ``new Date()``，不同浏览器/系统时区会把它当成「本地时间」
 * 解析，导致差 8 小时（如上海用户看到 UTC 时间被当本地时间显示）。
 *
 * 本工具强制把 naive 输入按 UTC 解析，再以 **Asia/Shanghai (UTC+8)** 呈现，
 * 与用户「时间使用上海」的预期一致；同时兼容已带时区标记的输入（Z / +08:00），
 * 避免双重偏移。
 *
 * @param {string|Date|null|undefined} t 时间值
 * @returns {string} 形如 ``2026-07-22 21:48:30`` 的上海本地时间，无效值返回 ``—``
 */
export function formatDateTime(t) {
  if (!t) return '—'
  const s =
    typeof t === 'string' &&
    !/[Zz]$/.test(t) &&
    !/[+-]\d{2}:?\d{2}$/.test(t)
      ? t + 'Z'
      : t
  const d = new Date(s)
  if (isNaN(d.getTime())) return '—'
  return d
    .toLocaleString('zh-CN', {
      timeZone: 'Asia/Shanghai',
      hour12: false,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
    .replace(/\//g, '-')
}
