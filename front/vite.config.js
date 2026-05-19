import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const backendTarget = process.env.VITE_BACKEND_TARGET || 'http://127.0.0.1:8000'
const userServiceTarget = process.env.VITE_USER_SERVICE_TARGET || 'http://127.0.0.1:8001'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 3000,
    host: true, // 允许局域网访问
    proxy: {
      // AI相关接口代理到8000端口
      '/api/agent': {
        target: backendTarget,
        changeOrigin: true,
        ws: true
      },
      '/api/rag': {
        target: backendTarget,
        changeOrigin: true
      },
      '/api/session': {
        target: backendTarget,
        changeOrigin: true
      },
      '/knowledge/': {
        target: backendTarget,
        changeOrigin: true
      },
      '/chat': {
        target: backendTarget,
        changeOrigin: true
      },
      '/health': {
        target: backendTarget,
        changeOrigin: true
      },
      // 用户相关接口代理到8001端口
      '/user': {
        target: userServiceTarget,
        changeOrigin: true
      },
      '/file': {
        target: userServiceTarget,
        changeOrigin: true
      }
    }
  }
})
