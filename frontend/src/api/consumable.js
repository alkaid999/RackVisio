import http from './http'

// 耗材管理相关接口。注意：所有响应已被 http.js 拦截器解包为 data。
export default {
  // ===== 耗材类型 =====
  // 类型列表（含 category_count / item_count 汇总）。data = [ConsumableTypeOut]
  listTypes() {
    return http.get('/consumables/types')
  },
  createType(payload) {
    return http.post('/consumables/types', payload)
  },
  updateType(id, payload) {
    return http.put(`/consumables/types/${id}`, payload)
  },
  removeType(id) {
    return http.delete(`/consumables/types/${id}`)
  },

  // ===== 耗材分类（归属某类型）=====
  // 某类型下分类列表（含 item_count）。data = [ConsumableCategoryOut]
  listCategories(typeId) {
    return http.get(`/consumables/types/${typeId}/categories`)
  },
  createCategory(typeId, payload) {
    return http.post(`/consumables/types/${typeId}/categories`, payload)
  },
  updateCategory(id, payload) {
    return http.put(`/consumables/categories/${id}`, payload)
  },
  removeCategory(id) {
    return http.delete(`/consumables/categories/${id}`)
  },

  // ===== 具体耗材 =====
  // 列表（分页 + type_id / category_id / keyword 筛选）。data = {items, total, page, size}
  listItems(params = {}) {
    return http.get('/consumables/items', { params })
  },
  createItem(payload) {
    return http.post('/consumables/items', payload)
  },
  getItem(id) {
    return http.get(`/consumables/items/${id}`)
  },
  updateItem(id, payload) {
    return http.put(`/consumables/items/${id}`, payload)
  },
  removeItem(id) {
    return http.delete(`/consumables/items/${id}`)
  },

  // ===== 库存变动 =====
  // 发起一次库存变动（入库/领用/报废/盘点）。返回更新后的 ConsumableItemOut。
  adjustStock(id, payload) {
    return http.post(`/consumables/items/${id}/adjust`, payload)
  },

  // ===== 库存变动历史 =====
  // 某耗材变动记录（分页）。data = {items, total, page, size}
  itemRecords(id, params = {}) {
    return http.get(`/consumables/items/${id}/records`, { params })
  },
  // 全局变动记录（分页 + 类型/分类/耗材/操作类型筛选）。data = {items, total, page, size}
  allRecords(params = {}) {
    return http.get('/consumables/records', { params })
  },
}
