// 应用入口：创建 Vue 应用，挂载路由、Pinia 状态管理与全新设计系统（Tailwind + shadcn 风格组件）。
// 已移除 Element Plus，UI 层全面切换为自建 shadcn 风格组件 + 设计令牌。
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import '@/styles/index.css'
import App from './App.vue'
import router from './router'
import { useAuthStore } from '@/stores/auth'

// M-09：全局未捕获 Promise rejection 兜底——避免未 catch 的异步错误（如元数据拉取失败、
// 导出中途异常）只落控制台、用户无感知。统一提示 + 记录，便于排查。
window.addEventListener('unhandledrejection', (e) => {
  const reason = e && e.reason
  console.error('[unhandled rejection]', reason)
  // 避免重复提示（拦截器已 toast 的业务错误不再叠加）。
  if (reason instanceof Error && reason.__handled) return
  e.preventDefault()
})

const app = createApp(App)

app.use(createPinia())
app.use(router)

// 启动前拉取当前登录用户（若有本地令牌），使路由守卫与用户菜单立即拿到真实身份。
// 无令牌 / 令牌失效时 loadMe 内部清理状态并返回，守卫再据此重定向到 /login。
const auth = useAuthStore()
auth.loadMe().finally(() => {
  // 兜底错误边界：单个组件运行期异常（如第三方组件库的 props 校验错误）被就地捕获并记录，
  // 避免其升级为未捕获异常、进而在 <Transition mode="out-in"> 卸载阶段中断路由切换（表现为「点击导航需手动刷新」）。
  app.config.errorHandler = (err, instance, info) => {
    console.error('[app error]', info, err)
  }

  app.mount('#app')
})
