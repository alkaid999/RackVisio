import http from './http'

// 仪表盘总览统计接口。响应已被 http.js 解包为 data（StatsOverview）。
export default {
  overview() {
    return http.get('/stats/overview')
  },
}
