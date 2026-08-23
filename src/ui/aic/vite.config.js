import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Backend isn't live yet (see docs/ui-react-rewrite-plan.md §10.4) — the
// app talks to src/api/dummy.js until VITE_API_BASE_URL points somewhere
// real. Kept here, unused, so wiring a dev proxy later is a one-line change.
// const apiBaseUrl = process.env.VITE_API_BASE_URL

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    allowedHosts: ["aic_fe.serverhub.id.vn"]
  }
  
})
