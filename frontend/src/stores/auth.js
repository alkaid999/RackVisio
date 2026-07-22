import { defineStore } from 'pinia'
import authApi from '@/api/auth'
import { getToken, setToken, clearToken } from '@/utils/auth-token'
import { defaultPermissions, expandPermissions } from '@/utils/constants'
import { clearAllPersistedFilters } from '@/composables/usePersistentFilter'

// 认证状态：令牌、当前用户、权限映射。
// - token 持久化在 localStorage（见 utils/auth-token.js），刷新页面后自动恢复登录态。
// - user 字段结构：{ id, username, display_name, role, role_label, permissions }
//   其中 permissions 为「权限映射」：{ module: { view: bool, edit: bool }, ... }
//   （管理员恒全权限，后端返回全 true 映射；前端仅依赖映射，无需感知是否为管理员）。
export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: getToken() || '',
    user: null,
    // 启动后是否已尝试拉取 /auth/me（避免重复拉取与守卫竞态）。
    initialized: false,
  }),
  getters: {
    isLoggedIn: (s) => !!s.token,
    // 权限映射（缺省回退全模块只读，避免渲染空值）。
    permissions: (s) => (s.user && s.user.permissions) || defaultPermissions(),
    isAdmin: (s) => !!(s.user && s.user.role === 'admin'),
    userName: (s) => (s.user && (s.user.display_name || s.user.username)) || '未登录',
    // 展开后的扁平权限键集合（如 ["room:view","device:edit"]），用于门控判断。
    effectivePermissions: (s) => {
      const user = s.user
      if (!user) return []
      return expandPermissions(user.permissions, user.role === 'admin')
    },
  },
  actions: {
    async login(username, password) {
      const data = await authApi.login(username, password)
      setToken(data.token)
      this.token = data.token
      this.user = data.user
      this.initialized = true
      return data.user
    },
    logout() {
      clearToken()
      this.token = ''
      this.user = null
      this.initialized = true
      // 退出登录时清空全部持久化列表筛选（需求：筛选保留至重置或退出登录）。
      clearAllPersistedFilters()
    },
    // 应用启动时调用：若本地有 token 则拉取最新用户信息，否则标记未登录。
    async loadMe() {
      if (!this.token) {
        this.initialized = true
        this.user = null
        return null
      }
      try {
        const data = await authApi.me()
        this.user = data
        this.initialized = true
        return data
      } catch (e) {
        // token 失效 / 账号被禁用：清理登录态。
        this.logout()
        return null
      }
    },
    hasPermission(perm) {
      return this.effectivePermissions.includes(perm)
    },
  },
})
