import http from './http'

// 日志清理：手动触发，删除保留期之前的「操作日志 + 登录日志」。
// 自动周期清理已在后端移除（改由用户在前端界面手动触发），避免误删。
export const LOG_DEFAULT_RETENTION_DAYS = 180

export default {
  // 清理；days 不传则后端按默认保留期（180 天）计算 cutoff。
  // 返回 { operation_deleted, login_deleted, cutoff }。
  cleanup(payload = {}) {
    return http.post('/logs/cleanup', payload)
  },
}
