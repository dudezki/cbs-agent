import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

// https://vitejs.dev/config/
export default defineConfig({
    plugins: [
        vue(),
        tailwindcss(),
    ],
    server: {
        proxy: {
            '/api': {
                target: process.env.VITE_API_URL || 'http://127.0.0.1:8080',
                changeOrigin: true
            },
            '/api/ws': {
                target: (process.env.VITE_API_URL || 'http://127.0.0.1:8080').replace(/^http/, 'ws'),
                ws: true
            }
        }
    }
})
