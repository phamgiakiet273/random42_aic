import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 10000,
    host: true,
    allowedHosts: ["aic_fe.serverhub.id.vn"]
  }
})
