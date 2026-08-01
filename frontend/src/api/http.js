import axios from 'axios'
import { useToast } from '@/composables/useToast'
import { getToken, clearToken } from '@/utils/auth-token'

const { error: toastError } = useToast()

// 统一 Axios 实例：所有请求走 /api 前缀（vite 代理到后端 :8000）。
const http = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
})

/**
 * 后端统一响应信封（L-11：JSDoc 类型标注，供各 api 文件参考；本系统 code===0 表示成功）。
 * @typedef {Object} ApiEnvelope
 * @property {number} code    业务码（0=成功；422=参数校验失败；401/403/404/409/429 等）
 * @property {string} message 可读消息
 * @property {*}      data    业务负载（分页时为 { items, total, page, size }）
 */

// 请求拦截器：自动附带 Bearer 令牌（令牌由登录接口签发，存于 sessionStorage，键名 rv_token）。
http.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// M-06：请求竞态取消支持——调用方可传 `{ signal }`（AbortSignal）。
// 列表页快速切换筛选时，旧请求被 abort，避免慢响应晚到覆盖新数据。
// 用法：const ctrl = new AbortController(); api.list(params, { signal: ctrl.signal }); // 卸载/新筛选时 ctrl.abort()
// 注：axios 同时支持 config.signal 与 config.cancelToken（signal 为现代 API）。

// 响应拦截器：统一解包后端 `{"code":0,"message":"ok","data":<payload>}` 信封。
// - code === 0：业务代码只消费解包后的 data（对象或分页对象）。
// - code !== 0：useToast().error 提示，并 reject。
// - 网络 / HTTP 错误：归一为相同行为。
http.interceptors.response.use(
  (response) => {
    const body = response.data
    // 防御：极少数情况返回非信封结构。
    // L-10：信封判定收紧——除「含 code 键」外还要求 code 为 number，
    // 避免误伤业务 data 中恰含 code 字段的对象（如某实体自带 code 属性）。
    if (body && typeof body === 'object' && 'code' in body && typeof body.code === 'number') {
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
        // 关键（C-01）：必须同步清空 auth store 的 token state，而不仅是 sessionStorage——
        // 路由守卫用 auth.isLoggedIn（=!!store.token）判断「已登录访问登录页→回首页」，
        // 只清存储会导致 401→push /login→守卫弹回首页→首页再 401 的无限重定向循环。
        // 复用 logout() 语义（清 token + user + 持久化筛选，后续扩展的全量 store 重置一并生效）。
        import('@/stores/auth')
          .then((m) => m.useAuthStore().logout())
          .catch(() => clearToken())
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
