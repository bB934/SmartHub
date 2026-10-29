import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

// 开发期把 /api、/health 代理到 FastAPI；生产构建产物由 FastAPI 直接托管
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const target = env.VITE_API_TARGET || 'http://127.0.0.1:8000'

  return {
    plugins: [vue()],
    server: {
      port: 5173,
      proxy: {
        // /health 也要代理，否则侧边栏的“后端服务在线”在开发模式永远是离线
        '/api': { target, changeOrigin: true },
        '/health': { target, changeOrigin: true },
      },
    },
  }
})
