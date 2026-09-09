import vue from '@vitejs/plugin-vue'
import frappeui from 'frappe-ui/vite'
import path from 'path'
import { defineConfig } from 'vite'

// Frappe app layout: <app>/frontend (this dir) and <app>/doom_manager (python
// package). Paths are explicit so the build behaves the same on the host and
// inside the Docker node stage, where there is no bench to auto-detect.
export default defineConfig({
  plugins: [
    vue(),
    frappeui({
      // Dev server proxies /api, /assets, /login... to the compose stack on 8099
      // (FRAPPE_WEB_SERVER_PORT is set by the `dev` script).
      frappeProxy: { port: 5173 },
      lucideIcons: true,
      jinjaBootData: true,
      buildConfig: {
        outDir: '../doom_manager/public/frontend',
        indexHtmlPath: '../doom_manager/www/doom.html',
        baseUrl: '/assets/doom_manager/frontend/',
      },
    }),
  ],
  server: { allowedHosts: true },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
      'tailwind.config.js': path.resolve(__dirname, 'tailwind.config.js'),
    },
  },
  optimizeDeps: {
    include: ['frappe-ui > feather-icons', 'tailwind.config.js', 'engine.io-client'],
  },
})
