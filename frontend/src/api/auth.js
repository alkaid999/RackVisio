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
  // 公开探针：默认管理员(admin)是否仍使用初始密码（登录页智能隐藏默认凭证提示）
  defaultCredentialsActive() {
    return http.get('/auth/default-credentials-active')
  },
  // 当前登录用户修改自己的密码（S-02 强制改密落地）→ { token, user }
  changePassword(oldPassword, newPassword) {
    return http.post('/auth/change-password', {
      old_password: oldPassword,
      new_password: newPassword,
    })
  },
}
