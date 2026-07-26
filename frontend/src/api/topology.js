import http from './http'

// 拓扑相关接口（设备 / 链路关系图）。后端 /topology 已聚合 nodes + edges。
export default {
  // 拓扑数据（可按 room_id / rack_id / device_id 过滤）。
  // data = { nodes:[{id,name,device_type,status,rack_id}], edges:[{id,source,target,source_interface,target_interface,remark,medium,cable_length}] }
  list(params = {}) {
    return http.get('/topology', { params })
  },
  // 单设备视角拓扑（本设备 + 一跳邻居）。
  byDevice(deviceId) {
    return http.get(`/topology/device/${deviceId}`)
  },
}
