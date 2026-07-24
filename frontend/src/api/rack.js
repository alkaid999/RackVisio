import http from './http'

// 机柜相关接口。
export default {
  // 机柜管理列表（可全局，也可按机房过滤）。data = {items, total, page, size}
  list(params = {}) {
    return http.get('/racks', { params })
  },
  // 详情。data = RackOut
  get(id) {
    return http.get(`/racks/${id}`)
  },
  // 创建机柜（全局入口，room_id 置于请求体；机房下创建走 roomApi.createRack）。
  create(payload) {
    return http.post('/racks', payload)
  },
  // 批量新增机柜：一次请求一个事务。payload = {room_id,total_u,status,rack_group,items:[{column_code,code,name?}]}
  // data = {created:[RackOut], failed:[{index,column_code,code,name,error}]}
  batchCreate(payload) {
    return http.post('/racks/batch', payload)
  },
  // 更新机柜（全部可选字段）。
  update(id, payload) {
    return http.put(`/racks/${id}`, payload)
  },
  // 删除（硬删除，需先校验无设备）。
  remove(id) {
    return http.delete(`/racks/${id}`)
  },
  // 机柜下设备列表。data = [DeviceOut]
  devices(id) {
    return http.get(`/racks/${id}/devices`)
  },
  // U 位图。data = {rack_id, total_u, used_u, status, slots:[{u, device_id, device_name, device_type}]}
  uMap(id) {
    return http.get(`/racks/${id}/u-map`)
  },
  // U 位冲突检查。payload = {start_u, size_u?, exclude_device_id?}
  // data = {rack_id, start_u, size_u, conflict, conflict_u, conflict_device, error}
  checkU(id, payload) {
    return http.post(`/racks/${id}/check-u`, payload)
  },
  // 上架设备到指定 U 位。payload = {device_id, start_u}
  mount(id, payload) {
    return http.post(`/racks/${id}/mount`, payload)
  },
  // 下架设备。payload = {device_id}
  unmount(id, payload) {
    return http.post(`/racks/${id}/unmount`, payload)
  },
  // 候选上架设备（未挂载到任何机柜的设备池）。data = [DeviceOut]
  candidates(id) {
    return http.get(`/racks/${id}/candidate-devices`)
  },
  // 批量更新机柜网格坐标（2D 平面图拖拽持久化）。payload = {positions:[{id,grid_row,grid_col}]}
  updatePositions(payload) {
    return http.post('/racks/positions', payload)
  },
  // 导出（按当前筛选返回全量）。params = {room_id, keyword, status}。data = [RackListItem]
  exportAll(params = {}) {
    return http.get('/racks/export', { params })
  },
  // 批量导入（前端解析后的 JSON 行）。payload = { items: [RackImportItem] }。data = ImportResult
  import(items) {
    return http.post('/racks/import', { items })
  },
}
