// 鉴权令牌的本地持久化（sessionStorage 单键）。
// 抽出为独立模块，使 store 与 http 拦截器互相解耦，避免循环依赖。
//
// 安全说明：原先使用 localStorage，令牌可被任意 XSS 脚本读取并外发（持久化劫持面）。
// 改为 sessionStorage 后，令牌仅在当前标签页会话内可用、关闭标签页即清除，
// 不再跨标签页/跨会话长期驻留，显著降低 XSS 令牌窃取风险（P0 缓解项）。
// 注：更彻底的防御应使用 HttpOnly Cookie，但本项目为无状态 JWT + SPA，暂以
// sessionStorage 作为务实缓解；根因（XSS）已在各视图层通过转义消除。

const TOKEN_KEY = 'rv_token'

export function getToken() {
  try {
    return sessionStorage.getItem(TOKEN_KEY) || ''
  } catch {
    return ''
  }
}

export function setToken(token) {
  try {
    sessionStorage.setItem(TOKEN_KEY, token || '')
  } catch {
    /* 隐私模式等场景静默失败 */
  }
}

export function clearToken() {
  try {
    sessionStorage.removeItem(TOKEN_KEY)
  } catch {
    /* ignore */
  }
}
