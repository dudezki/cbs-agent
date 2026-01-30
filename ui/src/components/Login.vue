<script setup lang="ts">
import { ref, onMounted, onUnmounted, markRaw } from 'vue'
import { googleTokenLogin } from 'vue3-google-login'
import { SparklesIcon, ChartBarIcon, CpuChipIcon } from '@heroicons/vue/24/solid'


const emit = defineEmits(['login-success'])
const errorMsg = ref('')
const isVerifying = ref(false)
const isSuccess = ref(false)

const handleGoogleLogin = async () => {
  errorMsg.value = ''
  isVerifying.value = true
  try {
    const response = await googleTokenLogin()
    await verifyToken(response)
  } catch (error) {
    console.error("Google login failed", error)
    errorMsg.value = "Login cancelled or failed."
    isVerifying.value = false
  }
}

const verifyToken = async (response: any) => {
  const token = response.credential || response.access_token

  if (token) {
    isVerifying.value = true
    try {
      const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID
      let baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
      // Defensive check: if baseUrl contains spaces (pollution from other build args), take first part
      if (baseUrl.includes(' ')) {
        baseUrl = baseUrl.split(' ')[0]
      }
      // Ensure trailingslash-free base
      baseUrl = baseUrl.replace(/\/$/, '')
      const url = `${baseUrl}/auth/verify`
      console.log("Verifying token at:", url)
      const verifyRes = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          token: token,
          client_id: clientId
        })
      })

      if (verifyRes.ok) {
        const userData = await verifyRes.json()
        isVerifying.value = false
        isSuccess.value = true
        setTimeout(() => {
          emit('login-success', userData)
        }, 1500)
      } else {
        errorMsg.value = 'Failed to verify session.'
        isVerifying.value = false
      }
    } catch (e) {
      console.error(e)
      errorMsg.value = 'Network error verifying session.'
      isVerifying.value = false
    }
  }
}

// Carousel Logic
const currentSlide = ref(0)
const timer = ref<any>(null)

const slides = [
  {
    title: 'Orchestrate your<br/>Digital Workforce',
    highlight: 'Seamlessly',
    highlightClass: 'text-amber-500',
    description: 'Collaborate with multi-agent systems via Callbox. From drafting complex reports to analyzing data, specialized agents are ready to assist you.',
    bgClass: 'bg-amber-500/10',
    bgClassBottom: 'bg-blue-500/5',
    icon: markRaw(SparklesIcon),
    iconBgClass: 'bg-amber-500/10',
    iconColorClass: 'text-amber-500',
    featureTitle: 'Supercharged Productivity',
    featureDesc: 'Unlock insights faster with our advanced LLM-powered agents.'
  },
  {
    title: 'Data Powerhouse<br/>Integrated',
    highlight: 'BigQuery Native',
    highlightClass: 'text-blue-500',
    description: 'Directly query and analyze your massive datasets. Callbox brings the power of Google BigQuery right into your chat interface.',
    bgClass: 'bg-blue-500/10',
    bgClassBottom: 'bg-purple-500/5',
    icon: markRaw(ChartBarIcon),
    iconBgClass: 'bg-blue-500/10',
    iconColorClass: 'text-blue-500',
    featureTitle: 'Real-time Analytics',
    featureDesc: 'Visualize trends and extract value from your data in seconds.'
  },
  {
    title: 'Callbox + BigQuery<br/>+ Vertex AI =',
    highlight: 'Callie',
    highlightClass: 'text-purple-500 bg-clip-text text-transparent bg-gradient-to-r from-purple-400 to-pink-400',
    description: 'Experience the next generation of AI assistant. Callie combines deep reasoning with enterprise data access for unmatched capability.',
    bgClass: 'bg-purple-500/10',
    bgClassBottom: 'bg-amber-500/5',
    icon: markRaw(CpuChipIcon),
    iconBgClass: 'bg-purple-500/10',
    iconColorClass: 'text-purple-500',
    featureTitle: 'Vertex AI Powered',
    featureDesc: 'Leveraging the latest reasoning models for complex problem solving.'
  }
]

onMounted(() => {
  timer.value = setInterval(() => {
    currentSlide.value = (currentSlide.value + 1) % slides.length
  }, 10000)
})

onUnmounted(() => {
  if (timer.value) clearInterval(timer.value)
})
</script>

<template>
  <div class="grid grid-cols-1 md:grid-cols-2 h-screen w-full bg-white border-x border-gray-200">
    <!-- Left Column: Branding & Marketing - ALWAYS DARK -->
    <div
      class="hidden md:flex flex-col justify-between p-12 bg-gradient-to-br from-gray-900 via-gray-800 to-black text-white relative overflow-hidden">
      <!-- Decorative background elements -->
      <div
        class="absolute top-0 right-0 w-64 h-64 bg-amber-500/10 rounded-full blur-3xl -mr-16 -mt-16 pointer-events-none transition-all duration-1000"
        :class="slides[currentSlide].bgClass"></div>
      <div
        class="absolute bottom-0 left-0 w-96 h-96 bg-blue-500/5 rounded-full blur-3xl -ml-20 -mb-20 pointer-events-none transition-all duration-1000"
        :class="slides[currentSlide].bgClassBottom"></div>

      <div class="z-10 h-full flex flex-col justify-between">

        <!-- Callie Branding -->
        <div class="flex flex-col gap-6 mb-12">
          <div class="flex items-center gap-4 md:gap-6">
            <img src="/callbox-logo-white.svg" alt="Callbox" class="h-10 md:h-12 w-auto" />
            <div class="h-8 w-px bg-gray-700"></div>
            <img src="/callie-brand-logo.png" alt="Callie" class="h-10 md:h-12 w-auto object-contain" />
          </div>
          <hr class="border-gray-700" />
          <div class="flex flex-col lg:flex-row gap-6 lg:gap-20">
            <p class="text-xs md:text-sm text-blue-200 uppercase tracking-widest font-bold">
              Cognitive AI for Lifecycle & <br class="hidden lg:block" /> Intelligence Enablement
            </p>
            <p class="text-gray-300 text-base md:text-lg leading-relaxed max-w-lg font-light">
              Callie is Callbox’s AI platform that coordinates insights, actions, and decisions across teams and
              clients.
            </p>
          </div>
        </div>

        <!-- Carousel Content -->
        <div class="relative flex-1 flex flex-col justify-center">
          <transition enter-active-class="transition-all duration-700 ease-out"
            enter-from-class="opacity-0 translate-y-4" enter-to-class="opacity-100 translate-y-0"
            leave-active-class="transition-all duration-500 ease-in absolute inset-0"
            leave-from-class="opacity-100 translate-y-0" leave-to-class="opacity-0 -translate-y-4">
            <div :key="currentSlide" class="flex flex-col justify-center">
              <div>
                <h1 class="text-5xl font-extrabold leading-tight mb-6 text-white">
                  <span class="block mb-2" v-html="slides[currentSlide].title"></span>
                  <span :class="slides[currentSlide].highlightClass">{{ slides[currentSlide].highlight }}</span>
                </h1>
              </div>

              <div>
                <p class="text-lg text-gray-400 max-w-md leading-relaxed">
                  {{ slides[currentSlide].description }}
                </p>
              </div>

              <!-- Feature Card -->
              <div class="mt-12">
                <div
                  class="bg-white/5 backdrop-blur-sm p-6 rounded-xl border border-white/10 shadow-xl inline-block max-w-sm transform hover:scale-105 transition-transform duration-300">
                  <div class="flex items-start gap-4">
                    <div class="p-2 rounded-lg" :class="slides[currentSlide].iconBgClass">
                      <component :is="slides[currentSlide].icon" class="h-6 w-6"
                        :class="slides[currentSlide].iconColorClass" />
                    </div>
                    <div>
                      <h3 class="font-semibold text-white mb-1">{{ slides[currentSlide].featureTitle
                      }}</h3>
                      <p class="text-sm text-gray-400">{{ slides[currentSlide].featureDesc }}</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </transition>
        </div>

        <!-- Indicators -->
        <div class="mt-8 flex gap-3 z-10">
          <button v-for="(_, index) in slides" :key="index" @click="currentSlide = index"
            class="h-1 rounded-full transition-all duration-500 ease-out"
            :class="currentSlide === index ? 'w-8 bg-amber-500' : 'w-2 bg-gray-700 hover:bg-gray-600'"></button>
        </div>
      </div>
    </div>

    <!-- Right Column: Login Form - ALWAYS LIGHT -->
    <div class="flex flex-col items-center justify-center p-8 bg-white text-gray-900 relative">
      <div class="w-full max-w-sm">
        <!-- Mobile Logo Section -->
        <div class="flex items-center justify-center gap-4 mb-10 md:hidden">
          <img src="/callbox-logo.svg" alt="Callbox" class="h-8 w-auto" />
          <div class="h-6 w-px bg-gray-200"></div>
          <img src="/callie-brand-logo.png" alt="Callie" class="h-8 w-auto object-contain" />
        </div>
        <div class="mb-10 text-center md:text-left">
          <h2 class="text-3xl font-bold mb-2">Welcome back</h2>
          <p class="text-gray-500">Please sign in to access your sessions.</p>
        </div>
      </div>

      <div class="flex flex-col gap-4">
        <div class="w-full">
          <!-- Full Width Google Login Button -->
          <button @click="handleGoogleLogin" :disabled="isVerifying || isSuccess"
            class="w-full flex items-center justify-center relative font-medium py-3 px-4 rounded-full transition-all focus:ring-4 focus:outline-none disabled:cursor-not-allowed overflow-hidden shadow-sm hover:shadow-md active:scale-95 duration-300 bg-white text-gray-900 border border-gray-200 hover:bg-gray-50 focus:ring-gray-200">
            <!-- Success State -->
            <div v-if="isSuccess"
              class="absolute inset-0 flex items-center justify-center z-20 gap-2 animate-in fade-in zoom-in duration-300 bg-green-500 text-white">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 text-white" viewBox="0 0 20 20"
                fill="currentColor">
                <path fill-rule="evenodd"
                  d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                  clip-rule="evenodd" />
              </svg>
              <span class="font-bold">Success!</span>
            </div>

            <!-- Loading State (Absolute Overlay) -->
            <div v-if="isVerifying"
              class="absolute inset-0 bg-gray-100 flex items-center justify-center z-10 font-medium text-gray-700 gap-2">
              <svg class="animate-spin h-5 w-5 text-gray-700" xmlns="http://www.w3.org/2000/svg" fill="none"
                viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z">
                </path>
              </svg>
              <span>Verifying...</span>
            </div>

            <!-- Original Content -->
            <div class="flex items-center gap-3 transition-opacity duration-300"
              :class="{ 'opacity-0': isVerifying || isSuccess }">
              <!-- Google Icon -->
              <svg class="w-5 h-5" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                  fill="#4285F4" />
                <path
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                  fill="#34A853" />
                <path
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                  fill="#FBBC05" />
                <path
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                  fill="#EA4335" />
              </svg>

              <span>Sign in with Google</span>
            </div>
          </button>
        </div>

        <div v-if="errorMsg" class="p-3 text-sm text-red-500 bg-red-50 border border-red-200 rounded-md">
          {{ errorMsg }}
        </div>

        <div class="relative my-6" v-else>
          <div class="absolute inset-0 flex items-center">
            <div class="w-full border-t border-gray-200"></div>
          </div>
          <div class="relative flex justify-center text-sm">
            <span class="px-2 bg-white text-gray-500">Secure Access</span>
          </div>
        </div>
      </div>

      <p class="mt-8 text-center text-xs text-gray-500">
        By continuing, you verify that you are an authorized user of Callbox Inc.
      </p>
    </div>
  </div>
</template>
