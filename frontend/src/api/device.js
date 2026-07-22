import http from './http'

// 设备相关接口。
export default {
  // 列表（分页 + room_id / rack_id / device_type / status 筛选）。
  // data = {items, total, page, size}
  list(params = {}) {
    return http.get('/devices', { params })
  },
  // 创建设备（仅固有属性；位置由上架记录表管理）。
  // payload = {device_code?, name, device_type, u_height, model?, sn?, ip_address?, warranty_expire?, remark?, status?}
  create(payload) {
    return http.post('/devices', payload)
  },
  // 详情。data = DeviceOut
  get(id) {
    return http.get(`/devices/${id}`)
  },
  // 更新（全部可选）。
  update(id, payload) {
    return http.put(`/devices/${id}`, payload)
  },
  // 删除（删除后后端重算 used_u）。
  remove(id) {
    return http.delete(`/devices/${id}`)
  },
  // 上下架操作流水（按时间倒序）。data = [{id, event_type:'上架'|'下架', operated_at, operator, rack_id, rack_name, room_name, start_u, occupied_u, record_status}]
  mountHistory(id) {
    return http.get(`/devices/${id}/mount-history`)
  },
  // 编辑上架记录（上架人 / 下架人）。payload = {mounted_by?, unmounted_by?}
  updateMountRecord(recordId, payload) {
    return http.patch(`/mount-records/${recordId}`, payload)
  },
  // 删除上架记录（二次确认在前端完成）。
  deleteMountRecord(recordId) {
    return http.delete(`/mount-records/${recordId}`)
  },
}
