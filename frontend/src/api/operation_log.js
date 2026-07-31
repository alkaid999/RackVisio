import http from './http'

// 操作日志接口（请求级，中间件自动写入写请求）。响应由 http.js 解包为 data（{items, total, page, size}）。
export default {
  // 列表（分页 + 关键字 / 方法 / 操作人 / 状态码 / 时间范围筛选）。data = {items, total, page, size}
  list(params = {}) {
    return http.get('/logs/operations', { params })
  },
}
