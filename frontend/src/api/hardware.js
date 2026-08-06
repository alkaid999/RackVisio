import http from './http'

// 硬件管理接口（独立个体模型：每件硬件单独记录、单独追踪）。
export default {
  // ===== 类型 =====
  listTypes() {
    return http.get('/hardwares/types')
  },
  createType(payload) {
    return http.post('/hardwares/types', payload)
  },
  updateType(id, payload) {
    return http.put(`/hardwares/types/${id}`, payload)
  },
  removeType(id) {
    return http.delete(`/hardwares/types/${id}`)
  },
  // 类型手动排序（按展示顺序传入 id 列表，持久化）。返回排序后的全量类型。
  reorderTypes(ids) {
    return http.post('/hardwares/types/reorder', { ids })
  },
  // ===== 分类 =====
  listCategories(typeId) {
    return http.get(`/hardwares/types/${typeId}/categories`)
  },
  createCategory(typeId, payload) {
    return http.post(`/hardwares/types/${typeId}/categories`, payload)
  },
  updateCategory(id, payload) {
    return http.put(`/hardwares/categories/${id}`, payload)
  },
  removeCategory(id) {
    return http.delete(`/hardwares/categories/${id}`)
  },
  // 分类手动排序（同类型内按展示顺序传入 id 列表，持久化）。返回排序后的分类列表。
  reorderCategories(typeId, ids) {
    return http.post(`/hardwares/types/${typeId}/categories/reorder`, { ids })
  },
  // ===== 硬件条目（独立个体）=====
  listItems(params) {
    return http.get('/hardwares/items', { params })
  },
  createItem(payload) {
    return http.post('/hardwares/items', payload)
  },
  getItem(id) {
    return http.get(`/hardwares/items/${id}`)
  },
  updateItem(id, payload) {
    return http.put(`/hardwares/items/${id}`, payload)
  },
  removeItem(id) {
    return http.delete(`/hardwares/items/${id}`)
  },
  // 导出（按筛选条件导出全部，不分页）。data = [HardwareItemOut]
  exportAll(params) {
    return http.get('/hardwares/export', { params })
  },
  // 批量导入（前端解析后的 JSON 行）。payload = { items: [HardwareImportItem] }。data = ImportResult
  import(items) {
    return http.post('/hardwares/import', { items })
  },
  // ===== 变动历史 =====
  itemRecords(id, params) {
    return http.get(`/hardwares/items/${id}/records`, { params })
  },
  allRecords(params) {
    return http.get('/hardwares/records', { params })
  },
  // ===== 设备硬件联动（一对一）=====
  deviceHardwares(deviceId) {
    return http.get(`/hardwares/devices/${deviceId}/hardwares`)
  },
  assignToDevice(deviceId, payload) {
    return http.post(`/hardwares/devices/${deviceId}/hardwares`, payload)
  },
  unassignFromDevice(deviceId, hardwareItemId) {
    return http.delete(`/hardwares/devices/${deviceId}/hardwares/${hardwareItemId}`)
  },
}
