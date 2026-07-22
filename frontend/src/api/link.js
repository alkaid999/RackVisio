import http from './http'

// 链路相关接口。
export default {
  // 列表（分页 + room_id / rack_id 筛选）。data = {items, total, page, size}
  list(params = {}) {
    return http.get('/links', { params })
  },
  // 创建链路。payload = {source_interface_id, target_interface_id?, target_external?, remark?, medium?, cable_length?}
  create(payload) {
    return http.post('/links', payload)
  },
  // 更新链路（remark? / medium? / cable_length? / status? 可选）。
  update(id, payload) {
    return http.put(`/links/${id}`, payload)
  },
  // 删除链路。
  remove(id) {
    return http.delete(`/links/${id}`)
  },
}
