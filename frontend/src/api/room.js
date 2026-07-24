import http from './http'

// 机房相关接口。注意：所有响应已被 http.js 拦截器解包为 data。
export default {
  // 列表（分页 + 名称/分类筛选）。data = {items, total, page, size}
  list(params = {}) {
    return http.get('/rooms', { params })
  },
  // 创建机房。payload = {name, code, alias?, area?, building?, floor?, address?}
  create(payload) {
    return http.post('/rooms', payload)
  },
  // 详情。data = RoomOut
  get(id) {
    return http.get(`/rooms/${id}`)
  },
  // 更新。payload 全部可选。
  update(id, payload) {
    return http.put(`/rooms/${id}`, payload)
  },
  // 删除（软删除 status=disabled）。
  remove(id) {
    return http.delete(`/rooms/${id}`)
  },
  // 容量统计。data = {rack_count, total_u, used_u, utilization}
  stats(id) {
    return http.get(`/rooms/${id}/stats`)
  },
  // 机房下机柜列表。data = [RackOut]
  racks(id) {
    return http.get(`/rooms/${id}/racks`)
  },
  // 在机房下创建机柜（room_id 由路径提供）。
  createRack(id, payload) {
    return http.post(`/rooms/${id}/racks`, payload)
  },
  // 大屏聚合数据。data = RoomDashboard
  dashboard(id) {
    return http.get(`/rooms/${id}/dashboard`)
  },
  // 导出（按当前筛选返回全量）。params = {area, status, keyword}。data = [RoomOut]
  exportAll(params = {}) {
    return http.get('/rooms/export', { params })
  },
  // 批量导入（前端解析后的 JSON 行）。payload = { items: [RoomImportItem] }。data = ImportResult
  import(items) {
    return http.post('/rooms/import', { items })
  },
}
