import http from '@/api/http'

// 认证相关接口。所有请求经 http 拦截器解包，直接返回 data 字段。
export default {
  // 用户名 + 密码登录 → { token, user }
  login(username, password) {
    return http.post('/auth/login', { username, password })
  },
  // 获取当前登录用户信息（含权限集）
  me() {
    return http.get('/auth/me')
  },
}
