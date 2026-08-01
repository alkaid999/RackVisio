import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

// Vite 配置：Vue 插件 + `@` 别名指向 src + 开发期 /api 代理到后端。
// 默认代理到 8000；联调时可经环境变量 VITE_API_TARGET 覆盖（如本地另起新版本后端在 8001）。
const apiTarget = process.env.VITE_API_TARGET || 'http://127.0.0.1:8000'
const apiProxy = {
  // 将前端 /api 请求代理到后端 uvicorn 服务，便于联调。
  '/api': {
    target: apiTarget,
    changeOrigin: true,
    // 保留 /api 前缀，后端路由挂在 /api/v1 下。
    rewrite: (path) => path,
  },
}

export default defineConfig({
  // Tailwind CSS v4：使用官方 @tailwindcss/vite 插件（CSS-first 配置，
  // 不再需要 postcss.config.js / tailwind.config.js）。
  plugins: [vue(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  optimizeDeps: {
    // 预置 three 的子模块依赖，避免 HMR 期间新发现依赖触发重优化时，
    // Vite 删除 .vite/deps_temp_* 被 safe-delete 守卫拦截而崩。（现场已踩坑）
    include: [
      'three',
      'three/examples/jsm/controls/OrbitControls.js',
      'three/examples/jsm/renderers/CSS2DRenderer.js',
      'three/examples/jsm/environments/RoomEnvironment.js',
      // 机柜 2D 视图导出用的 ExcelJS：未在 include 中时，首次进入该页面会触发
      // Vite 重新优化，使进行中的动态 import 返回 504(Outdated Optimize Dep)，
      // 导致 RouterView 组件加载失败、点击导航"无响应"。预打包后消除该问题。
      'exceljs',
    ],
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: false,
    proxy: apiProxy,
  },
  preview: {
    host: '0.0.0.0',
    port: 4173,
    proxy: apiProxy,
  },
  build: {
    // H-08：不再抬阈值掩盖问题——exceljs vendor 最大（约 930KB），阈值设为 950，
    // 业务 chunk 超 600KB 仍会告警，而「有意拆分的独立 vendor」不产生噪音。
    chunkSizeWarningLimit: 950,
    outDir: 'dist',
    rollupOptions: {
      output: {
        // 注意：本项目 Vite 8（rolldown 驱动）的 manualChunks 仅接受函数形式，
        // 不接受对象形式（经典 rollup 的 `{ vendor: ['x'] }` 写法会报
        // "manualChunks is not a function"）。
        manualChunks(id) {
          // echarts：按需引入后仍约 400KB（含 zrender 依赖），独立 chunk 便于缓存与告警。
          if (id.includes('node_modules/echarts') || id.includes('node_modules/zrender')) return 'echarts'
          // three：Room3DView / Rack3DView / BigScreenView 三处共享，独立缓存。
          if (id.includes('node_modules/three')) return 'three'
          // exceljs：仅机柜 2D 导出使用（约 900KB），独立 chunk 避免污染业务包。
          if (id.includes('node_modules/exceljs')) return 'exceljs'
        },
      },
    },
  },
})
