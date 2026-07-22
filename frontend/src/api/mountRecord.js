import http from './http'

// 上下架记录集中管理接口（与设备详情页同源：MountRecord 表 + 同一事件展开逻辑）。
export default {
  // 列表（分页 + 筛选）。data = {items, total, page, size}
  // params = {device_name?, device_code?, op_type?, start_time?, end_time?, page, size}
  list(params = {}) {
    return http.get('/mount-records', { params })
  },
  // 导出全量（export=true 忽略分页）。data = [event, ...]
  exportAll(params = {}) {
    return http.get('/mount-records', { params: { ...params, export: true } })
  },
}
