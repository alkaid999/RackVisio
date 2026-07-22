import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// Vite 配置：Vue 插件 + `@` 别名指向 src + 开发期 /api 代理到后端（:8000）。
const apiProxy = {
  // 将前端 /api 请求代理到后端 uvicorn 服务，便于联调。
  '/api': {
    target: 'http://127.0.0.1:8000',
    changeOrigin: true,
    // 保留 /api 前缀，后端路由挂在 /api/v1 下。
    rewrite: (path) => path,
  },
}

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      // @antv/algorithm@0.1.26 发布的 es 构建缺少 es/index.js（module 字段指向的文件），
      // 导致 Vite 预打包时 esbuild 报 "Failed to resolve entry"。
      // 该包 lib（CJS）入口完好，别名到 lib/index.js 即可，esbuild 仍可正确做具名导入互操作。
      '@antv/algorithm': fileURLToPath(new URL('./node_modules/@antv/algorithm/lib/index.js', import.meta.url)),
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
    port: 5174,
    strictPort: true,
    proxy: apiProxy,
  },
  preview: {
    host: '0.0.0.0',
    port: 4173,
    proxy: apiProxy,
  },
  build: {
    // 提高 chunk 警告阈值，避免大依赖（echarts / g6）触发告警。
    chunkSizeWarningLimit: 1500,
    outDir: 'dist',
  },
})
