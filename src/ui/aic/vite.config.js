import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Everything the browser needs is proxied through this one origin, so remote
// use needs only port 10000 open and no server IP baked into the page.
const BACKEND = {
  hub: process.env.VITE_PROXY_HUB || 'http://127.0.0.1:9021',
  media: process.env.VITE_PROXY_MEDIA || 'http://127.0.0.1:9027',
  resultManager: process.env.VITE_PROXY_RESULT_MANAGER || 'http://127.0.0.1:9022',
}

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 10000,
    host: true,
    // The project lives on /mnt/e, a 9p/DrvFs mount where inotify events are
    // never delivered. Without polling, Vite's watcher never fires: HMR does
    // nothing and the module cache is never invalidated, so the dev server
    // keeps serving the version of each file it read at startup -- a browser
    // hard-refresh cannot fix that, because the staleness is server-side.
    watch: { usePolling: true, interval: 300, binaryInterval: 1000 },
    // Vite refuses requests with an unrecognised Host header; allow the hosts
    // this is actually reached by.
    allowedHosts: ['aic_fe.serverhub.id.vn', 'desktop-cs8oa5q-6', '.ts.net'],
    proxy: {
      '/hub': { target: BACKEND.hub, changeOrigin: true },
      '/result_manager': { target: BACKEND.resultManager, changeOrigin: true },
      // Media is large and range-requested; keep it streaming rather than buffered.
      // "/media/..." rather than "/img" or "/video": ad-blocker filter lists
      // block those generic paths, producing ERR_BLOCKED_BY_ADBLOCKER on
      // perfectly legitimate keyframe and clip requests.
      '/media': { target: BACKEND.media, changeOrigin: true },
    },
  },
})
