import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// VITE_BASE is the path the site is served from: "/" when the API serves it,
// "/InsightPulse/" on GitHub Pages. VITE_API_URL (read in src/api.js) points a
// static build at the hosted API.
export default defineConfig({
  base: process.env.VITE_BASE || '/',
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': 'http://localhost:8000', '/health': 'http://localhost:8000' },
  },
})
