import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

// 路由表：登录页为全屏独立页（meta.fullscreen），其余业务页统一包在 App 布局内。
// 业务路由统一 requiresAuth（M-10 约定：新增业务路由必须显式 requiresAuth: true，
// 否则守卫不拦截即公开）；带 meta.permission 的路由在进入前校验当前用户权限，
// 无权限则回退至首页并提示（后端同样有依赖级 RBAC 兜底）。
const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/LoginView.vue'),
    meta: { title: '登录', fullscreen: true, public: true },
  },
  { path: '/', redirect: '/dashboard' },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('@/views/dashboard/Dashboard.vue'),
    meta: { title: '仪表盘', requiresAuth: true },
  },
  {
    path: '/rooms',
    name: 'RoomList',
    component: () => import('@/views/room/RoomList.vue'),
    meta: { title: '机房列表', requiresAuth: true, permission: 'room:view' },
  },
  {
    path: '/rooms/:id',
    name: 'RoomDetail',
    component: () => import('@/views/room/RoomDetail.vue'),
    meta: { title: '机房详情', requiresAuth: true, permission: 'room:view' },
  },
  {
    path: '/racks',
    name: 'RackList',
    component: () => import('@/views/rack/RackList.vue'),
    meta: { title: '机柜列表', requiresAuth: true, permission: 'rack:view' },
  },
  {
    path: '/racks/:id',
    name: 'RackDetail',
    component: () => import('@/views/rack/RackDetail.vue'),
    meta: { title: '机柜详情', requiresAuth: true, permission: 'rack:view' },
  },
  {
    path: '/rack-view',
    name: 'RackView2D',
    component: () => import('@/views/rack/RackView2D.vue'),
    meta: { title: '机柜 2D 视图', requiresAuth: true, permission: 'rack:view' },
  },
  {
    path: '/devices',
    name: 'DeviceList',
    component: () => import('@/views/device/DeviceList.vue'),
    meta: { title: '设备列表', requiresAuth: true, permission: 'device:view' },
  },
  {
    path: '/devices/:id',
    name: 'DeviceDetail',
    component: () => import('@/views/device/DeviceDetail.vue'),
    meta: { title: '设备详情', requiresAuth: true, permission: 'device:view' },
  },
  {
    path: '/mount-records',
    name: 'MountRecordList',
    component: () => import('@/views/device/MountRecordList.vue'),
    meta: { title: '上下架记录', requiresAuth: true, permission: 'device:view' },
  },
  {
    path: '/links',
    name: 'LinkList',
    component: () => import('@/views/link/LinkList.vue'),
    meta: { title: '链路总览', requiresAuth: true, permission: 'link:view' },
  },
  {
    path: '/3d',
    name: 'Room3D',
    component: () => import('@/views/three/Room3DView.vue'),
    meta: { title: '机房 3D 总览', requiresAuth: true, permission: 'room:view' },
  },
  {
    path: '/3d/rack/:rackSlug',
    name: 'Rack3D',
    component: () => import('@/views/three/Rack3DView.vue'),
    meta: { title: '机柜3D详情', requiresAuth: true, permission: 'rack:view' },
  },
  {
    path: '/bigscreen',
    name: 'BigScreen',
    component: () => import('@/views/three/BigScreenView.vue'),
    meta: { title: '机房数据大屏', requiresAuth: true, permission: 'room:view' },
  },
  {
    path: '/accounts',
    name: 'AccountList',
    component: () => import('@/views/account/AccountList.vue'),
    meta: { title: '账号管理', requiresAuth: true, permission: 'account:view' },
  },
  {
    path: '/change-password',
    name: 'ChangePassword',
    component: () => import('@/views/account/ChangePasswordView.vue'),
    // 任何登录用户（含初始管理员首次登录强制改密）均可访问，无权限要求。
    meta: { title: '修改密码', requiresAuth: true },
  },
  {
    path: '/logs/operations',
    name: 'OperationLog',
    component: () => import('@/views/log/OperationLog.vue'),
    meta: { title: '操作日志', requiresAuth: true, permission: 'account:view' },
  },
  {
    path: '/logs/logins',
    name: 'LoginLog',
    component: () => import('@/views/log/LoginLog.vue'),
    meta: { title: '登录日志', requiresAuth: true, permission: 'account:view' },
  },
  {
    path: '/consumables',
    name: 'ConsumableList',
    component: () => import('@/views/consumable/ConsumableList.vue'),
    meta: { title: '耗材管理', requiresAuth: true, permission: 'consumable:view' },
  },
  {
    path: '/consumables/types',
    name: 'ConsumableTypeManager',
    component: () => import('@/views/consumable/ConsumableTypeManager.vue'),
    meta: { title: '类型与分类', requiresAuth: true, permission: 'consumable:edit' },
  },
  // 全捕获路由：访问任何未注册的子路径都给到 404 反馈，而非白屏。
  // 标记为 fullscreen + public，不走侧边栏布局、未登录也直接展示。
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/NotFound.vue'),
    meta: { title: '页面不存在', fullscreen: true, public: true },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  // 滚动定位（M-xx 修复）：vue-router 4 默认在路由切换后【不重置滚动位置】，
  // 导致从已滚动的页面（如仪表盘 / 机房详情 / 设备列表下方）钻取到详情页时，
  // 滚动容器 <main> 的 scrollTop 被继承，页面打开即停留在中部区域（偶发「跳到接口面板」）。
  // 注意：本项目滚动容器是布局中的 <main>（overflow-y-auto），body/html 不滚动
  // （App.vue 根容器 h-screen overflow-hidden），因此不能用 vue-router 默认的
  // window/document 滚动（{ top: 0 } 只滚 window），必须直接操作滚动容器元素。
  // 实现说明：router 在「导航确认后、新组件挂载前」调用本函数，此时离场页
  // （page-leave-active position:absolute）可能仍在过渡中，DOM 布局未稳定，
  // 因此用 requestAnimationFrame 延后到下一帧执行置顶，确保对新页面生效。
  scrollBehavior(to, from, savedPosition) {
    const scrollEl = () =>
      document.querySelector('main.overflow-y-auto') || document.scrollingElement || document.documentElement
    const apply = (top) => {
      const el = scrollEl()
      if (el && el.scrollTo) el.scrollTo({ top, left: 0, behavior: 'auto' })
    }
    if (savedPosition) {
      // 浏览器前进 / 后退：恢复原滚动位置（符合直觉）。
      requestAnimationFrame(() => apply(savedPosition.top || 0))
      return
    }
    if (to.hash) {
      // 显式锚点跳转：优先滚动容器内查找目标元素。
      requestAnimationFrame(() => {
        const el = document.querySelector(to.hash)
        if (el) {
          const c = scrollEl()
          c.scrollTo({ top: el.offsetTop, behavior: 'smooth' })
        } else {
          apply(0)
        }
      })
      return
    }
    // 常规导航：滚动容器回到顶部（保证详情页从「基本信息」开始展示）。
    requestAnimationFrame(apply.bind(null, 0))
  },
})

// 全局前置守卫：鉴权 + 权限门控 + 强制改密。
// - 未登录访问受保护页 → 跳转登录（携带 redirect）。
// - 已登录访问登录页 → 回首页。
// - 已登录但无 meta.permission 所需权限 → 回首页（已登录用户至少能看仪表盘）。
// - 已登录但 must_change_password=true（初始管理员首次登录）→ 强制跳转改密页，
//   完成改密前无法进入任何业务页（S-02）。
router.beforeEach(async (to) => {
  const auth = useAuthStore()
  // 确保应用启动期间已拉取过用户信息（main.js 已 await，这里兜底）。
  if (!auth.initialized) {
    await auth.loadMe()
  }

  if (to.meta.requiresAuth && !auth.isLoggedIn) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  if (to.path === '/login' && auth.isLoggedIn) {
    return { path: '/' }
  }
  if (auth.isLoggedIn && to.meta.permission && !auth.hasPermission(to.meta.permission)) {
    return { path: '/' }
  }
  // 强制改密拦截：除改密页外一律重定向（改密页自身放行）。
  if (auth.isLoggedIn && auth.mustChangePassword && to.name !== 'ChangePassword') {
    return { path: '/change-password' }
  }
  return true
})

router.afterEach((to) => {
  document.title = to.meta?.title ? `${to.meta.title} | RackVisio` : 'RackVisio'
})

export default router
