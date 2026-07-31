import http from './http'

// 登录日志接口（认证端点写入登录 / 注销行为）。响应由 http.js 解包为 data（{items, total, page, size}）。
export default {
  // 列表（分页 + 关键字 / 动作 / 状态 / 时间范围筛选）。data = {items, total, page, size}
  list(params = {}) {
    return http.get('/logs/logins', { params })
  },
}
