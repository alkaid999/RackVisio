import http from './http'

// 操作审计日志接口。响应由 http.js 解包为 data（{items, total, page, size}）。
export default {
  // 列表（分页 + 模块/操作/关键字/操作人筛选）。data = {items, total, page, size}
  list(params = {}) {
    return http.get('/audit-logs', { params })
  },
  // 模块 / 操作枚举，供筛选下拉使用。
  meta() {
    return http.get('/audit-logs/meta')
  },
}
