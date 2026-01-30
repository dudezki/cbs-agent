<script setup lang="ts">
import { ref, onMounted, nextTick, watch, computed } from 'vue'
import MarkdownIt from 'markdown-it'
import Login from './components/Login.vue'

const md = new MarkdownIt({
  html: true,
  linkify: true,
  typographer: true,
  breaks: true
})

// Custom fence renderer for code blocks
md.renderer.rules.fence = (tokens, idx, _options, _env, _self) => {
  const token = tokens[idx]
  const info = token.info ? md.utils.unescapeAll(token.info).trim() : ''
  const langName = info.split(/\s+/g)[0]
  const content = md.utils.escapeHtml(token.content)
  
  return `
    <div class="my-4 rounded-lg overflow-hidden border border-gray-700 bg-gray-950/50 shadow-md group code-block">
      <div class="flex items-center justify-between px-3 py-1.5 bg-gray-800/80 border-b border-gray-700/50 text-xs text-gray-400 select-none backdrop-blur-sm">
        <span class="font-mono font-medium opacity-80">${langName || 'text'}</span>
        <button class="copy-code-btn flex items-center gap-1.5 hover:text-white transition-colors focus:outline-none opacity-60 hover:opacity-100" title="Copy code">
          <svg class="w-3.5 h-3.5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
          </svg>
          <span>Copy</span>
        </button>
      </div>
      <div class="relative w-full">
        <pre class="!p-4 !m-0 !bg-transparent !rounded-none text-sm leading-relaxed font-mono whitespace-pre-wrap break-words text-gray-300 overflow-x-auto w-full"><code class="language-${langName} !bg-transparent !p-0 !m-0 !text-gray-300 font-mono">${content}</code></pre>
      </div>
    </div>
  `
}

const renderMarkdown = (text: string) => {
  return md.render(text || '')
}

interface Session {
  id: string
  last_update_time?: number
  state?: {
    title?: string
  }
}

interface Message {
  role: 'user' | 'model' | 'error'
  text: string
  timestamp?: string
  isComplete?: boolean
  author?: string
}

interface AgentEvent {
  id?: string
  author?: string
  timestamp?: number
  actions?: {
    tool_calls?: any
    thought?: string
    tool_use?: string
  }
  content?: {
    role?: string
    parts?: Array<{ text?: string }>
  }
}

// User State (Auth)
const user = ref<any>(null)
const appName = 'agent_sm'
const userId = computed(() => user.value ? user.value.email : 'default_user')

// Check for existing session
const storedUser = localStorage.getItem('cbx_user')
if (storedUser) {
    try {
        user.value = JSON.parse(storedUser)
    } catch (e) {
        console.error("Failed to parse stored user", e)
    }
}

const socket = ref<WebSocket | null>(null)
const sessions = ref<Session[]>([])
const currentSessionId = ref<string | null>(null)
const chatHistory = ref<Message[]>([])
const agentThinking = ref<AgentEvent[]>([]) 
const isThinking = ref(false)
const userInput = ref('')
const isConnected = ref(false)
const isHistoryLoading = ref(false)
const chatContainer = ref<HTMLElement | null>(null)

const complexAgents = ['content_creator', 'auditor', 'critic', 'refiner']
const isComplexWorkflow = computed(() => {
  return agentThinking.value.some(event => 
    event.author && complexAgents.includes(event.author)
  )
})

const processedEventIds = ref(new Set<string>())

// Helpers
const formatSessionTime = (timestamp?: number) => {
  if (!timestamp) return ''
  const date = new Date(timestamp * 1000)
  const now = new Date()
  const diff = (now.getTime() - date.getTime()) / 1000
  
  if (diff < 60) return 'Just now'
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return date.toLocaleDateString()
}

const handleChatClick = async (event: MouseEvent) => {
  const target = event.target as HTMLElement
  const copyBtn = target.closest('.copy-code-btn')
  
  if (copyBtn) {
    const codeBlock = copyBtn.closest('.code-block')
    const codeElement = codeBlock?.querySelector('code')
    
    if (codeElement && codeElement.textContent) {
      try {
        await navigator.clipboard.writeText(codeElement.textContent)
        const originalHtml = copyBtn.innerHTML
        copyBtn.innerHTML = `<span class="text-green-400">Copied!</span>`
        setTimeout(() => { copyBtn.innerHTML = originalHtml }, 2000)
      } catch (err) { console.error('Failed to copy:', err) }
    }
  }
}

const processAgentEvent = (event: AgentEvent) => {
  if (event.id && processedEventIds.value.has(event.id)) return
  if (event.id) processedEventIds.value.add(event.id)

  if (event.actions && (event.actions.tool_calls || event.actions.thought)) {
    agentThinking.value.push(event)
  }
  
  if (event.content && event.content.parts) {
    const role = event.content.role || 'model'
    const textPart = event.content.parts.find(p => p.text)
    
    if (role === 'user') {
      const text = textPart && textPart.text ? textPart.text : ''
      if (!text) return

      const lastMsg = chatHistory.value[chatHistory.value.length - 1]
      // Check for optimistic update match usually only needed if we don't clear history on load, but here we do.
      // However during streaming, we receive the user message back.
      if (lastMsg && lastMsg.role === 'user' && lastMsg.text === text) {
         return
      }

      chatHistory.value.push({
        role: 'user',
        text: text,
        timestamp: event.timestamp ? new Date(event.timestamp * 1000).toLocaleTimeString() : new Date().toLocaleTimeString()
      })
      return
    }
    
    if (textPart && textPart.text) {
      const author = event.author || 'AI'
      const lastMsg = chatHistory.value[chatHistory.value.length - 1]
      
      if (lastMsg && lastMsg.role === 'model' && lastMsg.author === author) {
         lastMsg.text += textPart.text
      } else {
         chatHistory.value.push({
           role: 'model',
           text: textPart.text,
           author: author,
           timestamp: event.timestamp ? new Date(event.timestamp * 1000).toLocaleTimeString() : new Date().toLocaleTimeString()
         })
      }
    }
  }
}

const selectSession = (sessionId: string) => {
  currentSessionId.value = sessionId
  chatHistory.value = [] 
  agentThinking.value = []
  processedEventIds.value.clear()
  isHistoryLoading.value = true 
  isThinking.value = false 
  
  if (socket.value && socket.value.readyState === WebSocket.OPEN) {
      socket.value.send(JSON.stringify({
        type: 'load_history',
        app_name: appName,
        user_id: userId.value,
        session_id: sessionId
      }))
  }
}

const listSessions = () => {
  if (!socket.value) return
  socket.value.send(JSON.stringify({
    type: 'list_sessions',
    app_name: appName,
    user_id: userId.value
  }))
}

const createSession = () => {
  if (currentSessionId.value === 'new') return
  
  // Create temporary local session
  const newSession: Session = { id: 'new', state: { title: 'New Chat' } }
  sessions.value.unshift(newSession)
  currentSessionId.value = 'new'
  chatHistory.value = []
  agentThinking.value = []
  processedEventIds.value.clear()
}

const deleteSession = (sessionId: string) => {
  if (!socket.value) return
  if (confirm('Are you sure you want to delete this session?')) {
    socket.value.send(JSON.stringify({
      type: 'delete_session',
      app_name: appName,
      user_id: userId.value,
      session_id: sessionId
    }))
  }
}

const sendMessage = () => {
  if (!userInput.value.trim() || !currentSessionId.value || !socket.value) return

  const text = userInput.value
  userInput.value = ''
  
  chatHistory.value.push({
    role: 'user',
    text: text,
    timestamp: new Date().toLocaleTimeString()
  })

  agentThinking.value = [] 
  isThinking.value = true
  processedEventIds.value.clear() 

  const sessionIdToSend = currentSessionId.value === 'new' ? null : currentSessionId.value

  socket.value.send(JSON.stringify({
    type: 'chat',
    app_name: appName,
    user_id: userId.value,
    session_id: sessionIdToSend,
    new_message: { role: 'user', parts: [{ text: text }] }
  }))
}

const handleMessage = (data: any) => {
  if (data.type === 'session_created') {
    // Use optional chaining or check for existence
    if (data.session && data.session.id) {
       // If we were in a temporary 'new' session, replace it
       if (currentSessionId.value === 'new') {
           sessions.value = sessions.value.filter(s => s.id !== 'new')
           sessions.value.unshift(data.session)
           currentSessionId.value = data.session.id
       } else {
           // Standard push if we weren't in 'new' (e.g. maybe created from another tab?)
           sessions.value.unshift(data.session)
       }
    }
  } else if (data.type === 'sessions_list') {
    sessions.value = data.sessions.sort((a: Session, b: Session) => {
      const timeA = a.last_update_time || 0
      const timeB = b.last_update_time || 0
      return timeB - timeA
    })
  } else if (data.type === 'session_updated') {
     const idx = sessions.value.findIndex(s => s.id === data.session.id)
     if (idx !== -1) {
       sessions.value[idx] = data.session
       sessions.value.sort((a, b) => (b.last_update_time || 0) - (a.last_update_time || 0))
     }
  } else if (data.type === 'agent_event') {
    if (data.session_id === currentSessionId.value) {
        processAgentEvent(data.event)
    }
  } else if (data.type === 'chat_complete') {
    if (data.session_id === currentSessionId.value) {
        isThinking.value = false
    }
  } else if (data.type === 'history_complete') {
    if (data.session_id === currentSessionId.value) {
        isHistoryLoading.value = false
    }
  } else if (data.type === 'error') {
    console.error('Server error:', data.message)
    if (data.session_id === currentSessionId.value) {
        isThinking.value = false
        isHistoryLoading.value = false
        chatHistory.value.push({ role: 'error', text: `Error: ${data.message}` })
    }
  } else if (data.type === 'session_deleted') {
     sessions.value = sessions.value.filter(s => s.id !== data.session_id)
     if (currentSessionId.value === data.session_id) {
       currentSessionId.value = null
       chatHistory.value = []
       agentThinking.value = []
       isThinking.value = false
       isHistoryLoading.value = false
     }
  }
}

const connectWebSocket = () => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const wsUrl = `${protocol}//${window.location.host}/ui/ws`
  const targetUrl = import.meta.env.DEV ? 'ws://localhost:8000/ui/ws' : wsUrl

  socket.value = new WebSocket(targetUrl)

  socket.value.onopen = () => {
    console.log('Connected to WebSocket')
    isConnected.value = true
    listSessions()
  }

  socket.value.onmessage = (event: MessageEvent) => {
    const data = JSON.parse(event.data)
    handleMessage(data)
  }

  socket.value.onclose = () => {
    console.log('Disconnected from WebSocket')
    isConnected.value = false
    if (user.value) { // Only reconnect if logged in
        setTimeout(connectWebSocket, 3000)
    }
  }

  socket.value.onerror = (error: Event) => {
    console.error('WebSocket error:', error)
  }
}

const disconnectWebSocket = () => {
    if (socket.value) {
        socket.value.close()
        socket.value = null
    }
    isConnected.value = false
    sessions.value = []
    currentSessionId.value = null
    chatHistory.value = []
}

const handleLogin = (userData: any) => {
    user.value = userData
    localStorage.setItem('cbx_user', JSON.stringify(userData))
    connectWebSocket()
}

const handleLogout = () => {
    user.value = null
    localStorage.removeItem('cbx_user')
    disconnectWebSocket()
}

// Watchers
watch(chatHistory, () => {
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  })
}, { deep: true })

const isUserMenuOpen = ref(false)

const toggleUserMenu = () => {
  isUserMenuOpen.value = !isUserMenuOpen.value
}

// Close user menu when clicking outside
const closeUserMenu = (e: MouseEvent) => {
  const target = e.target as HTMLElement
  if (!target.closest('.user-menu-container')) {
    isUserMenuOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', closeUserMenu)
  if (user.value) {
    connectWebSocket()
  }
})

// Clean up listener
import { onUnmounted } from 'vue'
onUnmounted(() => {
    document.removeEventListener('click', closeUserMenu)
})
</script>

<template>
  <div class="h-screen bg-gray-900 text-gray-100 font-sans">
    <Login v-if="!user" @login-success="handleLogin" />
    <div v-else class="flex h-full">
        <!-- Left Sidebar: Sessions -->
        <div class="w-64 bg-gray-800 border-r border-gray-700 flex flex-col">
          <div class="p-4 flex justify-between items-center">
            <h1 class="text-xl font-semibold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-teal-400">Callbox</h1>
            <div v-if="isConnected" class="w-2 h-2 rounded-full bg-green-500 shadow-[0_0_8px_rgba(74,222,128,0.6)]" title="Connected"></div>
            <div v-else class="w-2 h-2 rounded-full bg-red-500" title="Disconnected"></div>
          </div>
          
          <div class="px-4 pb-2">
            <button 
              @click="createSession"
              class="w-full py-3 px-4 bg-gray-800 hover:bg-gray-750 border border-gray-700 hover:border-gray-600 rounded-full transition-all flex items-center gap-3 font-medium text-gray-300 hover:text-white group shadow-sm"
            >
              <!-- ... existing New Chat button ... -->
              <div class="w-6 h-6 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-white shadow-inner group-hover:scale-110 transition-transform">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
                  <path fill-rule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" clip-rule="evenodd" />
                </svg>
              </div>
              <span>New Chat</span>
            </button>
          </div>

          <div class="flex-1 overflow-y-auto px-2">
             <!-- ... existing sessions list ... -->
            <div v-if="sessions.length === 0" class="text-gray-500 text-center py-4 text-sm">
              No sessions yet
            </div>
            <ul v-else class="space-y-1">
              <li v-for="session in sessions" :key="session.id">
                <button
                  @click="selectSession(session.id)"
                  :session-id="session.id"
                  class="w-full text-left py-3 px-4 rounded-md text-sm transition-colors group flex items-center justify-between gap-2"
                  :class="currentSessionId === session.id ? 'bg-gray-700 shadow-sm' : 'hover:bg-gray-700/50'"
                >
                  <div class="flex flex-col gap-0.5 min-w-0 flex-1">
                     <span class="font-medium truncate" :class="currentSessionId === session.id ? 'text-white' : 'text-gray-400 group-hover:text-gray-200'">{{ session.state?.title || session.id }}</span>
                     <span class="text-xs" :class="currentSessionId === session.id ? 'text-gray-400' : 'text-gray-500 group-hover:text-gray-400'">
                       {{ formatSessionTime(session.last_update_time) }}
                     </span>
                  </div>
                  <div 
                    @click.stop="deleteSession(session.id)"
                    class="opacity-0 group-hover:opacity-100 p-1.5 hover:bg-red-500/20 hover:text-red-400 rounded transition-all text-gray-500"
                    title="Delete Session"
                  >
                     <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                      <path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clip-rule="evenodd" />
                    </svg>
                  </div>
                </button>
              </li>
            </ul>
          </div>
        </div>

        <!-- Right Main: Chat -->
        <div class="flex-1 flex flex-col bg-gray-900 relative">
          <!-- Transparent Header with User Menu -->
          <header class="h-16 flex items-center justify-between px-6 sticky top-0 z-20 pointer-events-none">
            <!-- Title (Left) - Only show if session active -->
            <div class="pointer-events-auto">
                <h2 v-if="currentSessionId" class="text-lg font-medium text-gray-200 opacity-0 lg:opacity-100 transition-opacity">
                   <!-- Hidden on mobile/small screens or just kept simple -->
                </h2>
            </div>
            
            <!-- User Menu (Right) -->
            <div class="relative pointer-events-auto user-menu-container">
                <button @click="toggleUserMenu" class="flex items-center gap-2 focus:outline-none p-1 rounded-full hover:bg-gray-800 transition-colors">
                     <img :src="user.picture" class="w-8 h-8 rounded-full ring-2 ring-gray-700" v-if="user.picture" referrerpolicy="no-referrer" />
                     <div class="w-8 h-8 rounded-full bg-blue-500 ring-2 ring-gray-700 flex items-center justify-center text-white font-bold" v-else>
                         {{ user.name ? user.name[0] : 'U' }}
                     </div>
                </button>
                
                <!-- Dropdown -->
                <div v-if="isUserMenuOpen" class="absolute right-0 top-full mt-2 w-72 bg-gray-800 rounded-2xl shadow-xl border border-gray-700 overflow-hidden z-50 transform origin-top-right transition-all">
                    <div class="p-4 border-b border-gray-700/50 flex flex-col items-center">
                         <img :src="user.picture" class="w-16 h-16 rounded-full mb-3 ring-4 ring-gray-700" v-if="user.picture" referrerpolicy="no-referrer" />
                         <div class="w-16 h-16 rounded-full bg-blue-500 mb-3 ring-4 ring-gray-700 flex items-center justify-center text-white font-bold text-2xl" v-else>
                             {{ user.name ? user.name[0] : 'U' }}
                         </div>
                         <div class="text-white font-medium text-lg">{{ user.name }}</div>
                         <div class="text-gray-400 text-sm">{{ user.email }}</div>
                    </div>
                    <div class="p-2">
                        <a href="https://myaccount.google.com/" target="_blank" class="block w-full text-center py-2 px-4 rounded-full border border-gray-600 text-gray-300 hover:bg-gray-700 text-sm font-medium transition-colors mb-2">
                            Manage your Google Account
                        </a>
                        <button @click="handleLogout" class="w-full text-left py-2 px-4 rounded-xl text-gray-300 hover:bg-gray-700 flex items-center gap-3 transition-colors text-sm">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                            </svg>
                            Sign out
                        </button>
                    </div>
                    <div class="bg-gray-900/50 py-2 px-4 text-center text-xs text-gray-500">
                        <a href="#" class="hover:text-gray-300">Privacy Policy</a> • <a href="#" class="hover:text-gray-300">Terms of Service</a>
                    </div>
                </div>
            </div>
          </header>

          <!-- Messages Area -->
          <div 
            ref="chatContainer"
            class="flex-1 overflow-y-auto p-6 space-y-6 scroll-smooth"
            @click="handleChatClick"
          >
            <div v-if="!currentSessionId" class="h-full flex flex-col items-center justify-center text-center p-8 relative overflow-hidden">
              <!-- Background Decoration -->
              <div class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-gradient-to-tr from-blue-500/10 to-purple-500/10 rounded-full blur-3xl pointer-events-none"></div>

              <div class="relative z-10 max-w-2xl">
                <h1 class="text-6xl font-semibold mb-6">
                  <span class="bg-clip-text text-transparent bg-gradient-to-r from-blue-400 via-purple-400 to-red-400">Hello, {{ user ? user.name.split(' ')[0] : 'Human' }}</span>
                </h1>
                <p class="text-2xl text-gray-400 mb-12 font-light">How can I help you today?</p>
                
                <button 
                   @click="createSession"
                   class="px-8 py-4 bg-gray-100/10 hover:bg-gray-100/20 border border-white/10 rounded-2xl text-lg backdrop-blur-md transition-all hover:scale-105 hover:shadow-2xl hover:shadow-blue-500/20 flex items-center gap-3 mx-auto"
                >
                  <div class="w-8 h-8 rounded-full bg-gradient-to-r from-blue-500 to-purple-600 flex items-center justify-center">
                     <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-white" viewBox="0 0 20 20" fill="currentColor">
                      <path fill-rule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" clip-rule="evenodd" />
                    </svg>
                  </div>
                  <span>Start a new conversation</span>
                </button>
              </div>
            </div>

            <div v-else-if="isHistoryLoading" class="h-full flex items-center justify-center">
               <div class="flex flex-col items-center gap-3">
                 <div class="w-8 h-8 border-2 border-t-transparent border-blue-500 rounded-full animate-spin"></div>
                 <span class="text-gray-500 text-sm">Loading history...</span>
               </div>
            </div>

            <template v-else>
              <!-- Welcome Message (Empty State) -->
              <div v-if="chatHistory.length === 0 && !isThinking" class="h-full flex flex-col items-center justify-center -mt-20">
                 <div class="mb-10 text-center">
                    <h1 class="text-5xl font-medium mb-3">
                       <span class="bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-teal-400">Callbox Assistant</span>
                    </h1>
                    <p class="text-xl text-gray-400 font-light">I'm ready whenever you are.</p>
                 </div>
                 
                 <div class="grid grid-cols-2 gap-4 w-full max-w-2xl px-4">
                    <button @click="userInput = 'Analyze the sales performance in Q4'; sendMessage()" class="text-left p-4 bg-gray-800/50 hover:bg-gray-800 border border-gray-700/50 hover:border-gray-600 rounded-xl transition-all hover:-translate-y-1 group">
                       <h3 class="text-blue-300 font-medium mb-1 group-hover:text-blue-200">Analyze Sales</h3>
                       <p class="text-sm text-gray-500 line-clamp-2">Review performance metrics for the last quarter</p>
                    </button>
                    <button @click="userInput = 'Draft a marketing report regarding our latest campaign'; sendMessage()" class="text-left p-4 bg-gray-800/50 hover:bg-gray-800 border border-gray-700/50 hover:border-gray-600 rounded-xl transition-all hover:-translate-y-1 group">
                       <h3 class="text-purple-300 font-medium mb-1 group-hover:text-purple-200">Draft Report</h3>
                       <p class="text-sm text-gray-500 line-clamp-2">Create a comprehensive marketing summary</p>
                    </button>
                     <button @click="userInput = 'Check the CRM data for inconsistencies'; sendMessage()" class="text-left p-4 bg-gray-800/50 hover:bg-gray-800 border border-gray-700/50 hover:border-gray-600 rounded-xl transition-all hover:-translate-y-1 group">
                       <h3 class="text-pink-300 font-medium mb-1 group-hover:text-pink-200">Audit Data</h3>
                       <p class="text-sm text-gray-500 line-clamp-2">Scan datasets for potential errors or gaps</p>
                    </button>
                     <button @click="userInput = 'Help me plan the strategy for next month'; sendMessage()" class="text-left p-4 bg-gray-800/50 hover:bg-gray-800 border border-gray-700/50 hover:border-gray-600 rounded-xl transition-all hover:-translate-y-1 group">
                       <h3 class="text-yellow-300 font-medium mb-1 group-hover:text-yellow-200">Plan Strategy</h3>
                       <p class="text-sm text-gray-500 line-clamp-2">Outline key objectives and action items</p>
                    </button>
                 </div>
              </div>

              <div v-for="(msg, index) in chatHistory" :key="index" class="flex flex-col gap-1 max-w-5xl mx-auto">
                 
                <!-- User Message -->
                <div v-if="msg.role === 'user'" class="self-end max-w-[80%]">
                  <div class="bg-blue-600 text-white px-5 py-3 rounded-2xl rounded-br-none shadow-lg">
                    {{ msg.text }}
                  </div>
                  <div class="text-xs text-gray-500 mt-1 text-right">{{ msg.timestamp }}</div>
                </div>
                
                <!-- Model Message -->
                <div v-else-if="msg.role === 'model'" class="self-start max-w-[80%]">
                   <div class="flex items-start gap-3">
                     <div class="w-8 h-8 rounded-full bg-gradient-to-br from-teal-400 to-blue-500 flex-shrink-0 flex items-center justify-center text-white font-bold text-xs select-none shadow-md">
                       {{ msg.author ? msg.author.slice(0, 2).toUpperCase() : 'AI' }}
                     </div>
                     <div>
                        <div class="bg-gray-800 border border-gray-700 text-gray-100 px-5 py-3 rounded-2xl rounded-tl-none shadow-sm prose prose-invert prose-sm max-w-none break-words prose-headings:text-gray-100 prose-a:text-blue-400 prose-strong:text-white prose-code:text-pink-300 prose-pre:bg-gray-900 prose-pre:border prose-pre:border-gray-700 prose-th:px-3 prose-th:py-2 prose-td:px-3 prose-td:py-2 prose-table:border-collapse prose-tr:border-b prose-tr:border-gray-700/50">
                           <div v-html="renderMarkdown(msg.text)"></div>
                        </div>
                        <div class="text-xs text-gray-500 mt-1 flex items-center gap-2">
                          <span v-if="msg.author" class="font-semibold text-blue-300/80">{{ msg.author }}</span>
                          <span>{{ msg.timestamp }}</span>
                        </div>
                     </div>
                   </div>
                </div>

                 <!-- Error Message -->
                <div v-else-if="msg.role === 'error'" class="self-center bg-red-900/50 text-red-200 px-4 py-2 rounded-lg border border-red-800 text-sm">
                    {{ msg.text }}
                </div>

              </div>

              <!-- Thinking Container (Live Stream) -->
              <div v-if="isThinking || agentThinking.length > 0" class="max-w-5xl mx-auto w-full mt-4 mb-8 transition-all duration-500 ease-in-out">
                
                <!-- Simple Mode: For Casual/Manager interactions -->
                <div v-if="!isComplexWorkflow" class="flex items-center gap-3 px-4 py-2 bg-gray-800/30 rounded-full w-fit mx-auto border border-gray-700/30 backdrop-blur-sm animate-pulse">
                   <div class="relative flex h-4 w-4">
                      <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                      <span class="relative inline-flex rounded-full h-4 w-4 bg-blue-500"></span>
                   </div>
                   <span class="text-sm text-gray-400 font-medium">Callbox is thinking...</span>
                </div>

                <!-- Complex Mode: For Report Workflow -->
                <details v-else class="group bg-gray-800/50 border border-gray-700/50 rounded-lg overflow-hidden transition-all duration-300 open:bg-gray-800/80" open>
                  <summary class="flex items-center gap-3 px-4 py-3 cursor-pointer select-none text-sm text-gray-400 hover:text-gray-200 transition-colors list-none">
                     <div v-if="isThinking" class="relative flex h-3 w-3">
                      <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-purple-400 opacity-75"></span>
                      <span class="relative inline-flex rounded-full h-3 w-3 bg-purple-500"></span>
                    </div>
                    <div v-else class="w-3 h-3 rounded-full bg-gray-500"></div>
                    
                    <span class="font-medium bg-clip-text text-transparent bg-gradient-to-r from-purple-400 to-pink-400 animate-pulse">
                      {{ isThinking ? 'Workflow Active: Generating Report...' : 'Workflow Complete' }}
                    </span>
                    <span class="ml-auto text-xs bg-gray-700 px-2 py-0.5 rounded-full text-gray-400 group-open:text-gray-300">
                      {{ agentThinking.length }} steps
                    </span>
                    <svg class="w-4 h-4 transition-transform group-open:rotate-180 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
                    </svg>
                  </summary>
                  <div class="p-4 border-t border-gray-700/50 bg-gray-900/50 font-mono text-xs text-gray-400 overflow-x-auto max-h-80 custom-scrollbar">
                    <div v-for="(event, idx) in agentThinking" :key="idx" class="mb-2 last:mb-0 hover:bg-gray-800/50 p-2 rounded transition-colors border-l-2" 
                         :class="['content_creator', 'auditor', 'critic', 'refiner'].includes(event.author || '') ? 'border-purple-500/50 bg-purple-900/10' : 'border-gray-700'">
                       <div class="flex gap-2 mb-1 justify-between">
                          <div class="flex gap-2">
                            <span class="font-bold uppercase tracking-wider text-[10px]" 
                                  :class="{'text-purple-400': ['content_creator', 'refiner'].includes(event.author || ''), 
                                           'text-red-400': event.author === 'critic',
                                           'text-yellow-400': event.author === 'auditor',
                                           'text-blue-400': !['content_creator', 'auditor', 'critic', 'refiner'].includes(event.author || '')}">
                              {{ event.author }}
                            </span>
                            <span class="text-gray-600">{{ event.timestamp ? new Date(event.timestamp * 1000).toLocaleTimeString().split(' ')[0] : '' }}</span>
                          </div>
                       </div>
                       <div v-if="event.actions" class="pl-2">
                          <div v-if="event.actions.thought" class="text-gray-300 mb-1 italic">
                             "{{ event.actions.thought }}"
                          </div>
                           <div v-if="event.actions.tool_use" class="text-emerald-400/80 font-medium">
                             Tool: <span class="text-emerald-300">{{ event.actions.tool_use }}</span>
                          </div>
                       </div>
                    </div>
                  </div>
                </details>
              </div>
            </template>
          </div>

          <!-- Input Area -->
          <div v-if="currentSessionId" class="p-6 bg-transparent pb-8">
            <div class="max-w-4xl mx-auto relative group">
               <div class="absolute -inset-0.5 bg-gradient-to-r from-blue-500/20 to-purple-500/20 rounded-3xl blur opacity-0 group-focus-within:opacity-100 transition duration-1000"></div>
               
               <div class="relative bg-gray-800 rounded-3xl border border-gray-700 shadow-xl overflow-hidden focus-within:border-gray-600 transition-colors">
                  <textarea
                    v-model="userInput"
                    @keydown.enter.exact.prevent="sendMessage"
                    class="w-full bg-transparent text-gray-100 placeholder-gray-500 px-6 py-4 pr-16 focus:outline-none transition-all resize-none text-base max-h-64 custom-scrollbar"
                    rows="1"
                    placeholder="Message Callbox..."
                    :disabled="isThinking"
                    @input="(e: Event) => { 
                      const target = e.target as HTMLTextAreaElement;
                      target.style.height = 'auto'; 
                      target.style.height = target.scrollHeight + 'px' 
                    }"
                  ></textarea>
                  
                   <div class="absolute right-2 bottom-2 flex items-center">
                    <button 
                      @click="sendMessage"
                      :disabled="!userInput.trim() || isThinking"
                      class="p-2.5 rounded-full text-white transition-all disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-700 active:scale-95 flex items-center justify-center"
                      :class="userInput.trim() ? 'bg-blue-600 hover:bg-blue-500' : 'bg-transparent text-gray-500 hover:bg-gray-700'"
                    >
                      <svg v-if="!isThinking" xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                         <path d="M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.429A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z" />
                      </svg>
                      <div v-else class="h-5 w-5 border-2 border-t-transparent border-gray-400 rounded-full animate-spin"></div>
                    </button>
                  </div>
               </div>
            </div>
            <div class="text-center mt-3 text-xs text-gray-500 font-medium">
              Callbox can make mistakes. Please double check responses.
            </div>
          </div>
        </div>
    </div>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #4b5563;
  border-radius: 3px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: #6b7280;
}

/* Markdown Overrides */
.prose table {
  margin-top: 0.5em;
  margin-bottom: 0.5em;
  width: 100%;
}
.prose thead th {
  color: #e5e7eb; /* text-gray-200 */
  font-weight: 600;
  border-bottom-width: 1px;
  border-color: #4b5563; /* border-gray-600 */
}
.prose td {
  padding: 0.5em;
}
.prose ul > li::marker {
  color: #9ca3af; /* text-gray-400 */
}
.prose ol > li::marker {
  color: #9ca3af; /* text-gray-400 */
}
/* Reduce default spacing */
.prose p {
  margin-top: 0.5em;
  margin-bottom: 0.5em;
}
.prose ul, .prose ol {
  margin-top: 0.5em;
  margin-bottom: 0.5em;
  padding-left: 1.5em;
}
.prose li {
  margin-top: 0.25em;
  margin-bottom: 0.25em;
}
</style>
