import axios from 'axios'
import { useToast } from '@/composables/useToast'
import { getToken, clearToken } from '@/utils/auth-token'

const { error: toastError } = useToast()

// 统一 Axios 实例：所有请求走 /api 前缀（vite 代理到后端 :8000）。
const http = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
})

// 请求拦截器：自动附带 Bearer 令牌（令牌由登录接口签发，存于 localStorage）。
http.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器：统一解包后端 `{"code":0,"message":"ok","data":<payload>}` 信封。
// - code === 0：业务代码只消费解包后的 data（对象或分页对象）。
// - code !== 0：useToast().error 提示，并 reject。
// - 网络 / HTTP 错误：归一为相同行为。
http.interceptors.response.use(
  (response) => {
    const body = response.data
    // 防御：极少数情况返回非信封结构。
    if (body && typeof body === 'object' && 'code' in body) {
      if (body.code === 0) {
        return body.data // 直接返回 data，业务侧无需再 .data.data
      }
      // 业务错误：提示可读 message 后 reject。
      toastError(body.message || '请求失败')
      return Promise.reject(new Error(body.message || '请求失败'))
    }
    // 非信封结构（如 /health 等）原样返回。
    return body
  },
  (error) => {
    const resp = error.response
    // 401：未登录 / 令牌失效。登录接口自身返回的 401（用户名或密码错误）不跳转，仅提示。
    if (resp && resp.status === 401) {
      const url = (error.config && error.config.url) || ''
      if (!url.includes('/auth/login')) {
        clearToken()
        // 动态导入路由以避免与本模块循环依赖；跳转前确认不在登录页。
        import('@/router')
          .then((m) => {
            const r = m.default
            if (r.currentRoute.value.path !== '/login') r.push('/login')
          })
          .catch(() => {})
      }
    }
    let message = '网络异常，请稍后重试'
    if (resp && resp.data) {
      if (typeof resp.data === 'object' && 'message' in resp.data) {
        message = resp.data.message
        // 校验错误（422）可能携带 data 为错误详情数组。
        if (resp.status === 422 && Array.isArray(resp.data.data)) {
          const first = resp.data.data[0]
          if (first && first.msg) {
            message = `参数校验失败：${first.msg}`
          }
        }
      } else if (typeof resp.data === 'string') {
        message = resp.data
      }
    } else if (error.code === 'ECONNABORTED') {
      message = '请求超时，请稍后重试'
    }
    toastError(message)
    return Promise.reject(error)
  }
)

export default http
