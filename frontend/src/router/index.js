import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

// 路由表：登录页为全屏独立页（meta.fullscreen），其余业务页统一包在 App 布局内。
// 业务路由统一 requiresAuth；带 meta.permission 的路由在进入前校验当前用户权限，
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
    path: '/rooms/:id/plan',
    name: 'RoomFloorPlan',
    component: () => import('@/views/room/RoomFloorPlan.vue'),
    meta: { title: '机房平面图', requiresAuth: true, permission: 'room:view' },
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
    meta: { title: '链路管理', requiresAuth: true, permission: 'link:view' },
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
    path: '/consumables',
    name: 'ConsumableList',
    component: () => import('@/views/consumable/ConsumableList.vue'),
    meta: { title: '耗材管理', requiresAuth: true, permission: 'consumable:view' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 全局前置守卫：鉴权 + 权限门控。
// - 未登录访问受保护页 → 跳转登录（携带 redirect）。
// - 已登录访问登录页 → 回首页。
// - 已登录但无 meta.permission 所需权限 → 回首页（已登录用户至少能看仪表盘）。
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
  return true
})

router.afterEach((to) => {
  document.title = to.meta?.title ? `${to.meta.title} | RackVisio 机柜 3D 可视化` : 'RackVisio 机柜 3D 可视化'
})

export default router
