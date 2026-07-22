import http from '@/api/http'

// 账号管理接口（增删改查）。受后端 RBAC 保护：
// - 列表需 account:view（管理员）
// - 创建/编辑/删除需 account:edit（管理员）
// 返回结构统一解包为 data：列表为 { items, total, page, size }，单条为账号对象。
export default {
  list(params = {}) {
    return http.get('/accounts', { params })
  },
  create(payload) {
    return http.post('/accounts', payload)
  },
  update(id, payload) {
    return http.put(`/accounts/${id}`, payload)
  },
  remove(id) {
    return http.delete(`/accounts/${id}`)
  },
}
