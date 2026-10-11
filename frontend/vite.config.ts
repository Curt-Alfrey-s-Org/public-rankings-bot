import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'
import path from 'path'

// https://vitejs.dev/config/
// For path-based hosting (e.g. example.com/rankings-bot): set VITE_BASE_PATH=/rankings-bot when building
const basePath = process.env.VITE_BASE_PATH || ''
export default defineConfig({
  base: basePath ? (basePath.endsWith('/') ? basePath : basePath + '/') : '/',
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      // Only favicon; assets/*.png is already precached via globPatterns (adding it here causes Workbox "add-to-cache-list-conflicting-entries" for alfa-head.png).
      includeAssets: ['favicon.ico'],
      manifest: {
        name: 'Rankings Bot',
        short_name: 'Rankings',
        description: 'Professional pool rankings — WPBA, WPA, and more',
        theme_color: '#0f172a',
        background_color: '#020617',
        display: 'standalone',
        start_url: basePath || '/',
        icons: [
          { src: '/vite.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any' },
        ],
      },
      workbox: {
        // Do not precache hashed JS/CSS — avoids SW holding stale chunks after deploy; browser HTTP cache + immutable assets suffice.
        // Exclude /branding/ — stable ALFa avatar URL must refresh after deploy (see alfaAvatarSrc.ts).
        globPatterns: ['**/*.{html,ico,svg,woff2}', 'assets/**/*.{png,svg}'],
        cleanupOutdatedCaches: true,
        navigateFallback: basePath
          ? `${basePath.endsWith('/') ? basePath : `${basePath}/`}index.html`
          : '/index.html',
        navigateFallbackDenylist: [/^\/api/, /^\/ws/],
        runtimeCaching: [
          {
            // Splash config changes should appear immediately after admin updates.
            urlPattern: /^https?:\/\/.*\/api\/splash-config(\?.*)?$/i,
            handler: 'NetworkOnly',
          },
          {
            // ALFa avatar (stable path; cache-bust query from VITE_API_BUILD_HASH).
            urlPattern: /^https?:\/\/.*\/branding\//i,
            handler: 'NetworkOnly',
          },
          {
            urlPattern: /^https:\/\/.*\/api\/.*/i,
            handler: 'NetworkFirst',
            options: {
              cacheName: 'api-cache',
              expiration: { maxEntries: 50, maxAgeSeconds: 60 * 5 },
              cacheableResponse: { statuses: [0, 200] },
              networkTimeoutSeconds: 10,
            },
          },
        ],
      },
    }),
  ],
  server: {
    port: 5174,
    open: false, // Disable Vite's auto-open browser (start_gui.sh handles it)
    proxy: {
      '/api': {
        target: 'http://localhost:8003',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8003',
        ws: true,
      },
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
})
