import http from './http'

// 接口相关接口（路由挂在 /devices/{id}/interfaces 与 /interfaces/{id}）。
// 字段统一：interface_no / interface_type / role / speed / status（status 由链路事务维护，不接受修改）。
export default {
  // 设备接口列表。data = [InterfaceOut]
  list(deviceId) {
    return http.get(`/devices/${deviceId}/interfaces`)
  },
  // 创建单个接口。payload = {name, interface_type, speed?, role?, interface_no?}
  create(deviceId, payload) {
    return http.post(`/devices/${deviceId}/interfaces`, payload)
  },
  // 批量生成接口（大型交换机多组混合端口类型）。payload = { groups: [{count, naming_pattern?, interface_type?, speed?, role?}] }
  batchCreate(deviceId, payload) {
    return http.post(`/devices/${deviceId}/interfaces/batch`, payload)
  },
  // 更新接口（全部可选，不含 status）。
  update(interfaceId, payload) {
    return http.put(`/interfaces/${interfaceId}`, payload)
  },
  // 删除接口。
  remove(interfaceId) {
    return http.delete(`/interfaces/${interfaceId}`)
  },
  // 查询某接口当前所在 active 链路（无则 null）。data = LinkDetailOut | null
  linkByInterface(interfaceId) {
    return http.get(`/links/by-interface/${interfaceId}`)
  },
}
