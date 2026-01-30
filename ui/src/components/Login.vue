<script setup lang="ts">
import { ref } from 'vue'

const emit = defineEmits(['login-success'])
const errorMsg = ref('')

const callback = async (response: any) => {
  console.log("Logged in with google", response)
  if (response.credential) {
     try {
        const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID
        console.log('Verifying with Client ID:', clientId)
        
        const verifyRes = await fetch('http://localhost:8000/auth/verify', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                token: response.credential,
                client_id: clientId 
            })
        })
        
        if (verifyRes.ok) {
            const userData = await verifyRes.json()
            emit('login-success', userData)
        } else {
            errorMsg.value = 'Failed to verify session.'
        }
     } catch (e) {
        console.error(e)
        errorMsg.value = 'Network error verifying session.'
     }
  }
}
</script>

<template>
  <div class="grid grid-cols-1 md:grid-cols-2 h-screen w-full bg-gray-900 border-x border-gray-700">
    <!-- Left Column: Branding & Marketing -->
    <div class="hidden md:flex flex-col justify-between p-12 bg-gradient-to-br from-gray-900 via-gray-800 to-black text-white relative overflow-hidden">
       <!-- Decorative background elements -->
       <div class="absolute top-0 right-0 w-64 h-64 bg-amber-500/10 rounded-full blur-3xl -mr-16 -mt-16 pointer-events-none"></div>
       <div class="absolute bottom-0 left-0 w-96 h-96 bg-blue-500/5 rounded-full blur-3xl -ml-20 -mb-20 pointer-events-none"></div>

       <div class="z-10">
          <div class="flex items-center gap-3 mb-8">
             <div class="w-10 h-10 bg-gradient-to-br from-amber-400 to-amber-600 rounded-lg flex items-center justify-center shadow-lg shadow-amber-900/20">
               <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 text-white" viewBox="0 0 20 20" fill="currentColor">
                 <path d="M2 5a2 2 0 012-2h7a2 2 0 012 2v4a2 2 0 01-2 2H9l-3 3v-3H4a2 2 0 01-2-2V5z" />
                 <path d="M15 7v2a4 4 0 01-4 4H9.828l-1.766 1.767c.28.149.599.233.938.233h2l3 3v-3h2a2 2 0 002-2V9a2 2 0 00-2-2h-1z" />
               </svg>
             </div>
             <span class="text-2xl font-bold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-amber-200 to-amber-500">Callbox Assistant</span>
          </div>
          
          <h1 class="text-5xl font-extrabold leading-tight mb-6 text-white">
             Orchestrate your <br/>
             <span class="text-amber-500">Digital Workforce</span>
          </h1>
          <p class="text-lg text-gray-400 max-w-md leading-relaxed">
             Seamlessly collaborate with multi-agent systems. From drafting complex reports to analyzing data, specialized agents are ready to assist you.
          </p>
       </div>

       <div class="z-10 mt-12">
          <div class="bg-gray-800/50 backdrop-blur-sm p-6 rounded-xl border border-gray-700/50 shadow-xl">
             <div class="flex items-start gap-4">
               <div class="p-2 bg-amber-500/10 rounded-lg">
                  <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
               </div>
               <div>
                  <h3 class="font-semibold text-white mb-1">Supercharged Productivity</h3>
                  <p class="text-sm text-gray-400">Unlock insights faster with our advanced LLM-powered agents.</p>
               </div>
             </div>
          </div>
          <div class="mt-8 flex gap-2">
             <span class="h-1 w-8 bg-amber-500 rounded-full"></span>
             <span class="h-1 w-2 bg-gray-700 rounded-full"></span>
             <span class="h-1 w-2 bg-gray-700 rounded-full"></span>
          </div>
       </div>
    </div>

    <!-- Right Column: Login Form -->
    <div class="flex flex-col items-center justify-center p-8 bg-gray-950 text-white relative">
       <div class="w-full max-w-sm">
          <div class="mb-10 text-center md:text-left">
             <h2 class="text-3xl font-bold mb-2">Welcome back</h2>
             <p class="text-gray-400">Please sign in to access your sessions.</p>
          </div>

          <div class="flex flex-col gap-4">
             <div class="flex justify-center md:justify-start">
               <!-- Google Login Component -->
               <GoogleLogin :callback="callback" theme="filled_black" shape="pill" />
             </div>

             <div v-if="errorMsg" class="p-3 text-sm text-red-400 bg-red-900/20 border border-red-900/50 rounded-md">
               {{ errorMsg }}
             </div>

             <div class="relative my-6" v-else>
               <div class="absolute inset-0 flex items-center">
                 <div class="w-full border-t border-gray-800"></div>
               </div>
               <div class="relative flex justify-center text-sm">
                 <span class="px-2 bg-gray-950 text-gray-500">Secure Access</span>
               </div>
             </div>
          </div>
          
          <p class="mt-8 text-center text-xs text-gray-600">
             By continuing, you verify that you are an authorized user of Callbox Inc.
          </p>
       </div>
    </div>
  </div>
</template>
