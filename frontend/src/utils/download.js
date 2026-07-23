// 浏览器下载 Blob：兼容 iframe 沙箱（预览环境）下的静默下载失败。
// 策略（按可用性逐级回退）：
//   1) 同域 iframe：在顶层文档触发锚点下载（顶层上下文不受 iframe 沙箱下载限制）；
//   2) 跨域 iframe / 顶层不可访问：改用 window.open 顶层标签页打开 blob；
//   3) 弹窗被拦截：退回当前窗口锚点（尽力）。
export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const makeAnchor = (doc) => {
    if (!doc || !doc.body) return false
    const a = doc.createElement('a')
    a.href = url
    a.download = filename
    a.style.display = 'none'
    doc.body.appendChild(a)
    a.click()
    a.remove()
    return true
  }
  let ok = false
  try {
    if (window.top && window.top !== window && window.top.document) {
      ok = makeAnchor(window.top.document)
    } else {
      ok = makeAnchor(window.document)
    }
  } catch (e) {
    ok = false
  }
  if (!ok) {
    try {
      ok = !!window.open(url, '_blank')
    } catch (e) {
      ok = false
    }
    if (!ok) ok = makeAnchor(window.document)
  }
  // 顶层标签页/弹窗会异步读取 blob，延长回收时间避免下载中断。
  setTimeout(() => URL.revokeObjectURL(url), 30000)
}
