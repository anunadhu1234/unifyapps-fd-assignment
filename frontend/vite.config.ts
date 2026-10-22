import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Development: /api is proxied to the local backend (VITE_DEV_PROXY_TARGET in frontend/.env).
// Production: FastAPI serves this build, so the API is same-origin.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_')
  return {
    plugins: [react(), tailwindcss()],
    server: {
      port: 5173,
      proxy: { '/api': { target: env.VITE_DEV_PROXY_TARGET || 'http://localhost:8000', changeOrigin: true } },
    },
  }
})
