import { createApp } from 'vue'
import './style.css'
import App from './App.vue'
import vue3GoogleLogin from 'vue3-google-login'
import { MotionPlugin } from '@vueuse/motion'

const app = createApp(App)

app.use(vue3GoogleLogin, {
    clientId: import.meta.env.VITE_GOOGLE_CLIENT_ID || 'mock-client-id'
})

app.use(MotionPlugin)

app.mount('#app')
