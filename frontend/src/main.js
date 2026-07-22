// 应用入口：创建 Vue 应用，挂载路由、Pinia 状态管理与全新设计系统（Tailwind + shadcn 风格组件）。
// 已移除 Element Plus，UI 层全面切换为自建 shadcn 风格组件 + 设计令牌。
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import '@/styles/index.css'
import App from './App.vue'
import router from './router'
import { useAuthStore } from '@/stores/auth'

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
