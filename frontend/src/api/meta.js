import http from './http'

// 界面元数据（标签 / 颜色 / 阈值）接口。后端为权威源，前端启动时拉取一次。
// 响应已被 http.js 拦截器解包为 data：{ device_status, device_type, rack_status, usage_thresholds }
export default {
  get() {
    return http.get('/meta')
  },
}
