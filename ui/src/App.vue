<script setup lang="ts">
import { ref, shallowRef, markRaw, onMounted, nextTick, watch, computed } from 'vue'
import MarkdownIt from 'markdown-it'
import Login from './components/Login.vue'

const md = new MarkdownIt({
  html: true,
  linkify: true,
  typographer: true,
  breaks: true
})

// API Configuration
const getBaseUrl = () => {
  const envUrl = import.meta.env.VITE_API_URL
  if (envUrl && envUrl.trim()) {
    // If it's a full URL, use it (and trim trailing slash)
    return envUrl.trim().replace(/\/$/, '')
  }
  // Fallback for local development: use relative path to leverage Vite proxy
  return import.meta.env.DEV ? '' : 'http://127.0.0.1:8080'
}

const API_URL = getBaseUrl()
console.log(`[v1.2.9] API Base URL: "${API_URL || '(relative)'}"`)

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

// Agent State
interface Agent {
  id: string
  name: string
  display_name: string
  description: string
  personality: string
  steps: string
  avatar: string
  suggestions: string
}

const agents = ref<Agent[]>([])
const selectedAgent = ref<Agent | null>(null)
const isAgentsModalOpen = ref(false)
const appName = computed(() => selectedAgent.value ? selectedAgent.value.name : 'agent_sm')

// User State (Auth)
const user = shallowRef<any>(null)
const userId = computed(() => user.value ? user.value.email : 'default_user')

// Check for existing session & agent
console.log(`[v1.2.9] App mounted. API Base: "${API_URL || '(relative)'}"`)
const storedUser = localStorage.getItem('cbx_user')
if (storedUser) {
  try {
    user.value = JSON.parse(storedUser)
  } catch (e) {
    console.error("Failed to parse stored user", e)
  }
}

const storedAgent = localStorage.getItem('cbx_agent')
if (storedAgent) {
  try {
    selectedAgent.value = JSON.parse(storedAgent)
  } catch (e) {
    console.error("Failed to parse stored agent", e)
  }
}

const socket = shallowRef<WebSocket | null>(null)
const sessions = ref<Session[]>([])
const currentSessionId = ref<string | null>(null)
const chatHistory = ref<Message[]>([])
const agentThinking = ref<AgentEvent[]>([])
const isThinking = ref(false)
const userInput = ref('')
const isConnected = ref(false)
const connectionStatus = ref<'connecting' | 'connected' | 'disconnected'>('disconnected')
const isHistoryLoading = ref(false)
const isSessionsLoading = ref(false)
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
      app_name: appName.value,
      user_id: userId.value,
      session_id: sessionId
    }))
  }
}

const fetchAgents = async () => {
  try {
    let baseUrl = import.meta.env.VITE_API_URL || ''
    // Defensive check: if baseUrl contains spaces (pollution from other build args), take first part
    if (baseUrl.includes(' ')) {
      baseUrl = baseUrl.split(' ')[0]
    }
    // Ensure trailingslash-free base
    baseUrl = baseUrl.replace(/\/$/, '')
    const url = `${baseUrl}/api/agents`
    console.log("Fetching agents from:", url)
    const resp = await fetch(url)
    if (resp.ok) {
      agents.value = await resp.json()
      // Default to first agent if none selected or if selected agent not in list anymore
      if (!selectedAgent.value && agents.value.length > 0) {
        selectAgent(agents.value[0])
      }
    }
  } catch (e) {
    console.error("Failed to fetch agents", e)
  }
}

const selectAgent = (agent: Agent) => {
  if (selectedAgent.value?.name === agent.name) {
    return
  }

  selectedAgent.value = agent
  localStorage.setItem('cbx_agent', JSON.stringify(agent))

  // Reset chat state for new agent
  currentSessionId.value = null
  chatHistory.value = []
  agentThinking.value = []
  processedEventIds.value.clear()

  // Reload sessions for new agent
  if (isConnected.value) {
    listSessions()
  }
}

const listSessions = () => {
  if (!socket.value) return
  isSessionsLoading.value = true
  socket.value.send(JSON.stringify({
    type: 'list_sessions',
    app_name: appName.value,
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
      app_name: appName.value,
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
    app_name: appName.value,
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
    isSessionsLoading.value = false
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
  console.log("Connect to API:", API_URL)
  let baseUrl = API_URL
  // Defensive check: if baseUrl contains spaces (pollution from other build args), take first part
  if (baseUrl.includes(' ')) {
    baseUrl = baseUrl.split(' ')[0]
  }
  let targetUrl = ''

  if (baseUrl) {
    // Standardize to ws/wss and absolute path
    const wsBase = baseUrl.replace(/^http/, 'ws')
    targetUrl = `${wsBase}/api/ws`
  } else {
    // Relative path (localhost:5173/api/ws) -> handled by Vite proxy
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    targetUrl = `${protocol}//${window.location.host}/api/ws`
  }

  console.log(`[v1.2.9] Attempting WebSocket connection: ${targetUrl}`)
  connectionStatus.value = 'connecting'
  
  try {
    const ws = new WebSocket(targetUrl)
    socket.value = markRaw(ws)
  } catch (err) {
    console.error(`[v1.2.9] Failed to create WebSocket:`, err)
    connectionStatus.value = 'disconnected'
    return
  }

  socket.value.onopen = () => {
    console.log('Connected to WebSocket')
    isConnected.value = true
    connectionStatus.value = 'connected'
    listSessions()
  }

  socket.value.onmessage = (event: MessageEvent) => {
    const data = JSON.parse(event.data)
    handleMessage(data)
  }

  socket.value.onclose = () => {
    console.log('Disconnected from WebSocket')
    isConnected.value = false
    connectionStatus.value = 'disconnected'
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
  selectedAgent.value = null
  localStorage.removeItem('cbx_user')
  localStorage.removeItem('cbx_agent')
  localStorage.removeItem('theme')
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

// Theme State (Dark Mode)
const isDarkMode = ref(localStorage.getItem('theme') !== 'light')

const toggleTheme = () => {
  isDarkMode.value = !isDarkMode.value
  localStorage.setItem('theme', isDarkMode.value ? 'dark' : 'light')
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
const isSettingsMenuOpen = ref(false)
const isHelpModalOpen = ref(false)
const isSidebarCollapsed = ref(false)

const toggleUserMenu = () => {
  isUserMenuOpen.value = !isUserMenuOpen.value
}

const toggleSettingsMenu = () => {
  isSettingsMenuOpen.value = !isSettingsMenuOpen.value
}

const toggleSidebar = () => {
  isSidebarCollapsed.value = !isSidebarCollapsed.value
}

// Close menus when clicking outside
const closeMenus = (e: MouseEvent) => {
  const target = e.target as HTMLElement
  if (!target.closest('.user-menu-container')) {
    isUserMenuOpen.value = false
  }
  if (!target.closest('.settings-menu-container')) {
    isSettingsMenuOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', closeMenus)
  fetchAgents()
  if (user.value) {
    connectWebSocket()
  }
})

// Clean up listener
import { onUnmounted } from 'vue'
onUnmounted(() => {
  document.removeEventListener('click', closeMenus)
})
</script>

<template>
  <div :class="{ 'dark': isDarkMode }"
    class="h-screen bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 font-sans overflow-hidden transition-colors duration-300">
    <Transition name="page-fade" mode="out-in">
      <Login v-if="!user" :is-dark-mode="isDarkMode" @login-success="handleLogin" />
      <div v-else class="flex h-full w-full">
        <!-- Left Sidebar: Sessions -->
        <div
          class="bg-gray-50 dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 flex flex-col flex-shrink-0 transition-all duration-300"
          :class="isSidebarCollapsed ? 'w-20 overflow-hidden' : 'w-64'">
          <div class="p-6 flex items-center" :class="isSidebarCollapsed ? 'justify-center' : 'justify-between'">
            <button @click="toggleSidebar"
              class="p-2 rounded-xl hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400 transition-colors"
              :title="isSidebarCollapsed ? 'Expand Sidebar' : 'Collapse Sidebar'">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24"
                stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
            <!-- Connection Status Indicator -->
            <div v-if="!isSidebarCollapsed" class="relative" 
              :title="connectionStatus === 'connected' ? 'Connected' : connectionStatus === 'connecting' ? 'Connecting...' : 'Disconnected'"
            >
              <!-- Signal Icon -->
              <svg class="w-5 h-5" :class="{
                'text-green-500': connectionStatus === 'connected',
                'text-red-500': connectionStatus !== 'connected',
                'animate-pulse': connectionStatus === 'connecting'
              }" fill="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <!-- Signal bars -->
                <path d="M2 20h2v-4H2v4zm5 0h2v-8H7v8zm5 0h2V10h-2v10zm5 0h2V4h-2v16z" opacity="1"/>
                <!-- Weakest bar (always visible when any status) -->
                <path d="M2 20h2v-4H2v4z" :opacity="connectionStatus === 'disconnected' ? '0.3' : '1'"/>
                <!-- Medium bar -->
                <path d="M7 20h2v-8H7v8z" :opacity="connectionStatus === 'disconnected' ? '0.3' : '1'"/>
                <!-- Strong bar -->
                <path d="M12 20h2V10h-2v10z" :opacity="connectionStatus === 'disconnected' ? '0.3' : (connectionStatus === 'connecting' ? '0.5' : '1')"/>
                <!-- Strongest bar -->
                <path d="M17 20h2V4h-2v16z" :opacity="connectionStatus === 'connected' ? '1' : '0.3'"/>
              </svg>
            </div>
          </div>

          <div class="px-4 pb-4">
            <button @click="createSession"
              class="w-full flex items-center transition-all font-medium group shadow-sm overflow-hidden" :class="[
                isSidebarCollapsed ? 'p-3 justify-center rounded-full' : 'py-3 px-4 gap-3 rounded-2xl border border-gray-200 dark:border-gray-700 hover:border-blue-400 dark:hover:border-gray-600',
                'bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-200 hover:text-blue-600 dark:hover:text-white'
              ]" :title="isSidebarCollapsed ? 'New Chat' : ''">
              <div
                class="w-6 h-6 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-white shadow-inner group-hover:scale-110 transition-transform shrink-0">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
                  <path fill-rule="evenodd"
                    d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z"
                    clip-rule="evenodd" />
                </svg>
              </div>
              <span v-if="!isSidebarCollapsed" class="whitespace-nowrap">New Chat</span>
            </button>
          </div>

          <div v-if="!isSidebarCollapsed" class="flex-1 overflow-y-auto px-2 custom-scrollbar">
            <div v-if="isSessionsLoading" class="space-y-2 px-3 py-4">
              <div v-for="i in 6" :key="i" class="animate-pulse p-3 rounded-xl bg-gray-50/50 dark:bg-gray-800/30 border border-gray-100 dark:border-gray-700/30">
                <div class="h-3.5 bg-gray-200 dark:bg-gray-700 rounded-lg w-3/4 mb-2"></div>
                <div class="h-2.5 bg-gray-100 dark:bg-gray-800 rounded-md w-1/2"></div>
              </div>
            </div>
            <div v-else-if="sessions.length === 0" class="text-gray-500 text-center py-4 text-sm">
              No sessions yet
            </div>
            <ul v-else class="space-y-1 px-2">
              <li v-for="session in sessions" :key="session.id">
                <button @click="selectSession(session.id)" :session-id="session.id"
                  class="w-full text-left py-3 px-4 rounded-xl text-sm transition-colors group flex items-center justify-between gap-2"
                  :class="currentSessionId === session.id ? 'bg-blue-50 dark:bg-gray-700 shadow-sm' : 'hover:bg-gray-100 dark:hover:bg-gray-700/50'">
                  <div class="flex flex-col gap-0.5 min-w-0 flex-1">
                    <span class="font-medium truncate"
                      :class="currentSessionId === session.id ? 'text-blue-600 dark:text-white' : 'text-gray-600 dark:text-gray-400 group-hover:text-gray-900 dark:group-hover:text-gray-200'">{{
                        session.state?.title || session.id }}</span>
                    <span class="text-xs"
                      :class="currentSessionId === session.id ? 'text-blue-400 dark:text-gray-400' : 'text-gray-400 dark:text-gray-500 group-hover:text-gray-500 dark:group-hover:text-gray-400'">
                      {{ formatSessionTime(session.last_update_time) }}
                    </span>
                  </div>
                  <div @click.stop="deleteSession(session.id)"
                    class="opacity-0 group-hover:opacity-100 p-1.5 hover:bg-red-500/20 hover:text-red-400 rounded transition-all text-gray-500"
                    title="Delete Session">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                      <path fill-rule="evenodd"
                        d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z"
                        clip-rule="evenodd" />
                    </svg>
                  </div>
                </button>
              </li>
            </ul>
          </div>

          <!-- Sidebar Footer -->
          <div v-if="!isSidebarCollapsed" class="mt-auto p-4 border-t border-gray-200 dark:border-gray-700">
            <div class="relative settings-menu-container">
              <!-- Dropup Menu -->
              <Transition name="dropdown">
                <div v-if="isSettingsMenuOpen"
                  class="absolute bottom-full left-0 mb-3 w-64 bg-white dark:bg-[#28292c] rounded-2xl shadow-2xl border border-gray-200 dark:border-gray-700 overflow-hidden z-50 transform origin-bottom transition-all">
                  <div class="p-2 space-y-1">
                    <div class="px-3 py-2 border-b border-gray-100 dark:border-gray-700/50 mb-1">
                      <span class="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Configuration</span>
                    </div>
                    <button @click="isAgentsModalOpen = true; isSettingsMenuOpen = false"
                      class="w-full flex items-center justify-between px-3 py-3 rounded-xl text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors group">
                      <div class="flex items-center gap-3">
                        <div
                          class="w-8 h-8 rounded-lg bg-purple-500/10 flex items-center justify-center text-purple-500">
                          <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24"
                            stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                              d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                          </svg>
                        </div>
                        <span class="font-medium">Switch Agent</span>
                      </div>
                      <svg xmlns="http://www.w3.org/2000/svg"
                        class="h-4 w-4 text-gray-400 group-hover:translate-x-0.5 transition-transform" fill="none"
                        viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                      </svg>
                    </button>

                    <button @click="isHelpModalOpen = true; isSettingsMenuOpen = false"
                      class="w-full flex items-center gap-3 px-3 py-3 rounded-xl text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors group">
                      <div class="w-8 h-8 rounded-lg bg-blue-500/10 flex items-center justify-center text-blue-500">
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24"
                          stroke="currentColor">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                            d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                      </div>
                      <span class="font-medium">Help Center</span>
                    </button>
                  </div>
                </div>
              </Transition>

              <button @click="toggleSettingsMenu"
                class="w-full text-left py-2.5 px-4 rounded-xl text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 transition-all flex items-center gap-3 group relative overflow-hidden"
                :class="isSettingsMenuOpen ? 'bg-gray-100 dark:bg-gray-800 ring-2 ring-blue-500/20' : ''">
                <div
                  class="h-6 w-6 rounded-lg overflow-hidden shrink-0 border border-gray-200 dark:border-gray-700 shadow-sm transition-transform group-hover:scale-110">
                  <img v-if="selectedAgent?.avatar" :src="selectedAgent.avatar" class="w-full h-full object-cover" />
                  <svg v-else xmlns="http://www.w3.org/2000/svg"
                    class="h-full w-full p-1 text-gray-400 group-hover:text-blue-500 transition-colors" fill="none"
                    viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                      d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                      d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                </div>
                <div class="flex flex-col min-w-0">
                  <span class="font-medium transition-colors"
                    :class="isSettingsMenuOpen ? 'text-blue-600 dark:text-blue-400' : ''">Settings & Help</span>
                  <span v-if="selectedAgent"
                    class="text-[10px] text-purple-500 dark:text-purple-400 font-black tracking-[0.1em] uppercase leading-tight mt-1 whitespace-normal break-words">{{
                      selectedAgent.display_name }}</span>
                </div>
              </button>
            </div>

            <div
              class="mt-3 flex items-center justify-between px-4 py-2.5 bg-gray-100/50 dark:bg-gray-900/50 rounded-2xl border border-gray-200 dark:border-gray-700/50">
              <span class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">Theme</span>
              <button @click="toggleTheme"
                class="p-2 rounded-xl bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 shadow-sm border border-gray-200 dark:border-gray-700 hover:text-blue-500 transition-colors group">
                <svg v-if="isDarkMode" xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20"
                  fill="currentColor">
                  <path fill-rule="evenodd"
                    d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 000 2h1z"
                    clip-rule="evenodd" />
                </svg>
                <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                  <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z" />
                </svg>
              </button>
            </div>
          </div>
        </div>

        <!-- Right Main: Chat -->
        <div class="flex-1 flex flex-col bg-white dark:bg-gray-900 relative min-w-0">
          <!-- Top Absolute Header with Fade -->
          <div v-if="user" class="absolute top-0 left-0 right-0 z-40 pointer-events-none">
            <!-- Smooth Gradient Overlay: Top (Solid) to Bottom (Transparent) -->
            <div
              class="absolute inset-x-0 top-0 h-40 bg-gradient-to-b from-white via-white/80 to-transparent dark:from-gray-900 dark:via-gray-900/80 dark:to-transparent transition-colors duration-500">
            </div>

            <!-- Header Content -->
            <header class="relative h-24 flex items-center justify-between px-6 pt-6 pointer-events-auto">
              <div class="flex-1"></div>
              <div class="flex items-center gap-3 user-menu-container">
                <div class="relative">
                  <button @click="toggleUserMenu"
                    class="flex items-center gap-4 focus:outline-none p-2 pl-6 pr-2 rounded-full border border-gray-200 dark:border-gray-700 bg-white/80 dark:bg-gray-800/80 backdrop-blur-sm transition-all hover:border-gray-300 dark:hover:border-gray-600 shadow-md active:scale-95 group">
                    <img :src="isDarkMode ? '/callbox-logo-white.svg' : '/callbox-logo.svg'" alt="Callbox"
                      class="h-9" />
                    <div
                      class="w-10 h-10 rounded-full overflow-hidden border border-gray-100 dark:border-gray-700 shadow-inner group-hover:scale-105 transition-transform">
                      <img :src="user.picture" class="w-full h-full object-cover" v-if="user.picture"
                        referrerpolicy="no-referrer" />
                      <div
                        class="w-full h-full bg-blue-500 flex items-center justify-center text-white font-bold text-base"
                        v-else>{{ user.name ? user.name[0] : 'U' }}</div>
                    </div>
                  </button>

                  <!-- Dropdown -->
                  <Transition name="dropdown">
                    <div v-if="isUserMenuOpen"
                      class="absolute right-0 top-full mt-3 w-80 bg-white dark:bg-[#28292c] rounded-[2rem] shadow-2xl border border-gray-200 dark:border-gray-700/50 overflow-hidden z-50 transform origin-top-right transition-all">

                      <div class="flex flex-col items-center pt-8 px-8 relative">
                        <button @click="toggleUserMenu"
                          class="absolute right-6 top-6 text-gray-400 hover:text-gray-600 dark:hover:text-white transition-colors">
                          <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24"
                            stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                              d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        </button>
                        <div class="text-gray-800 dark:text-gray-200 text-sm font-semibold truncate max-w-full px-4">{{
                          user.email }}</div>
                        <div class="text-gray-500 dark:text-gray-400 text-[11px] mt-1">Managed by callboxinc.com</div>
                      </div>

                      <div class="flex flex-col items-center py-6 px-8">
                        <div class="relative mb-6">
                          <div
                            class="w-24 h-24 rounded-full overflow-hidden border-4 border-gray-50 dark:border-gray-700/50 shadow-xl bg-amber-400 flex items-center justify-center text-4xl text-white font-bold">
                            <img :src="user.picture" class="w-full h-full object-cover" v-if="user.picture"
                              referrerpolicy="no-referrer" />
                            <span v-else>{{ user.name ? user.name[0] : 'U' }}</span>
                          </div>
                          <div
                            class="absolute bottom-0 right-0 bg-white dark:bg-gray-800 rounded-full p-2 border border-gray-200 dark:border-gray-700 shadow-md">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-gray-600 dark:text-gray-300"
                              fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                                d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                                d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
                            </svg>
                          </div>
                        </div>
                        <h2 class="text-2xl font-normal text-gray-900 dark:text-white text-center">Hi, {{ user.name }} !
                        </h2>
                      </div>

                      <div class="px-8 pb-8 flex flex-col items-center gap-4">
                        <a href="https://myaccount.google.com/" target="_blank"
                          class="block w-full text-center py-3 px-6 rounded-full border border-gray-200 dark:border-gray-600 text-blue-600 dark:text-[#a8c7fa] hover:bg-gray-50 dark:hover:bg-gray-700/50 text-[13px] font-semibold transition-all shadow-sm">
                          Manage your Google Account
                        </a>
                        <button @click="handleLogout"
                          class="mt-2 text-gray-500 dark:text-gray-400 hover:text-red-500 transition-colors text-xs font-medium uppercase tracking-widest bg-gray-100 dark:bg-gray-800 px-4 py-2 rounded-lg text-center w-full">
                          Sign out
                        </button>
                      </div>

                      <div
                        class="bg-gray-50 dark:bg-gray-900/30 py-3 px-6 text-center text-[10px] text-gray-400 flex items-center justify-center gap-3">
                        <a href="#" class="hover:text-gray-600 dark:hover:text-gray-200 transition-colors">Privacy
                          Policy</a>
                        <span class="w-1 h-1 rounded-full bg-gray-300 dark:bg-gray-700"></span>
                        <a href="#" class="hover:text-gray-600 dark:hover:text-gray-200 transition-colors">Terms of
                          Service</a>
                      </div>
                    </div>
                  </Transition>
                </div>
              </div>
            </header>
          </div>

          <!-- Messages Area -->
          <div ref="chatContainer"
            class="h-full overflow-y-auto p-6 pt-24 pb-48 space-y-6 scroll-smooth custom-scrollbar"
            @click="handleChatClick">
            <div v-if="!currentSessionId"
              class="h-full flex flex-col items-center justify-center text-center p-8 relative overflow-hidden">
              <div class="relative z-10 max-w-2xl">
                <h1 class="text-6xl font-semibold mb-6">
                  <span
                    class="bg-clip-text text-transparent bg-gradient-to-r from-blue-500 via-purple-500 to-red-500 dark:from-blue-400 dark:via-purple-400 dark:to-red-400">Hello,
                    {{ user ? user.name.split(' ')[0] : 'Human' }}</span>
                </h1>
                <p class="text-2xl text-gray-500 dark:text-gray-400 mb-12 font-light">How can I help you today?</p>

                <button @click="createSession"
                  class="px-8 py-4 bg-gray-50 dark:bg-gray-100/10 hover:bg-gray-100 dark:hover:bg-gray-100/20 border border-gray-200 dark:border-white/10 rounded-2xl text-lg backdrop-blur-md transition-all hover:scale-105 hover:shadow-2xl hover:shadow-blue-500/20 flex items-center gap-3 mx-auto shadow-sm">
                  <div
                    class="w-8 h-8 rounded-full bg-gradient-to-r from-blue-500 to-purple-600 flex items-center justify-center">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-white" viewBox="0 0 20 20"
                      fill="currentColor">
                      <path fill-rule="evenodd"
                        d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z"
                        clip-rule="evenodd" />
                    </svg>
                  </div>
                  <span class="text-gray-700 dark:text-white">Start a new conversation</span>
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
              <div v-if="chatHistory.length === 0 && !isThinking"
                class="h-full flex flex-col items-center justify-center -mt-20">
                <div class="mb-10 text-center">
                  <h1 class="text-5xl font-medium mb-3">
                    <span class="bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-teal-400">Callie
                      Assistant</span>
                  </h1>
                  <p class="text-xl text-gray-400 font-light">I'm ready whenever you are.</p>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-3 gap-4 w-full max-w-4xl px-4">
                  <button v-for="(suggestion, idx) in selectedAgent?.suggestions.split(';')" :key="idx"
                    @click="userInput = suggestion; sendMessage()"
                    class="text-left p-6 bg-white dark:bg-gray-800/50 hover:bg-gray-50 dark:hover:bg-gray-800 border border-gray-200 dark:border-gray-700/50 hover:border-blue-500/50 rounded-2xl transition-all hover:-translate-y-1 group shadow-sm hover:shadow-xl hover:shadow-blue-500/10 active:scale-95">
                    <div
                      class="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center text-blue-500 mb-4 group-hover:scale-110 transition-transform">
                      <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24"
                        stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                          d="M13 10V3L4 14h7v7l9-11h-7z" />
                      </svg>
                    </div>
                    <h3
                      class="text-gray-900 dark:text-white font-bold mb-2 group-hover:text-blue-500 transition-colors">
                      {{ suggestion.split(' ').slice(0, 2).join(' ') }}
                    </h3>
                    <p class="text-sm text-gray-500 dark:text-gray-400 line-clamp-2 leading-relaxed">{{ suggestion }}
                    </p>
                  </button>
                </div>
              </div>

              <div v-for="(msg, index) in chatHistory" :key="index" class="flex flex-col gap-1 max-w-5xl mx-auto">

                <!-- User Message -->
                <div v-if="msg.role === 'user'" class="self-end max-w-[80%]">
                  <div class="text-[10px] uppercase tracking-widest text-gray-400 font-bold mb-1.5 flex items-center gap-2 justify-end">
                    <span class="text-blue-500 dark:text-blue-400">You</span>
                    <span class="w-1 h-1 rounded-full bg-gray-300 dark:bg-gray-600"></span>
                    <span>{{ msg.timestamp }}</span>
                  </div>
                  <div class="bg-blue-600 text-white px-5 py-3 rounded-2xl rounded-br-none shadow-lg">
                    {{ msg.text }}
                  </div>
                </div>

                <!-- Model Message -->
                <div v-else-if="msg.role === 'model'" class="self-start max-w-[80%]">
                  <div class="flex items-start gap-4">
                    <div
                      class="w-14 h-14 overflow-hidden flex-shrink-0 flex items-center justify-center transition-transform hover:scale-110">
                      <img :src="selectedAgent?.avatar || '/callie-avatar.png'"
                        :alt="selectedAgent?.display_name || 'Callie'" class="w-full h-full object-cover" />
                    </div>
                    <div class="flex-1 min-w-0">
                      <div class="text-[10px] uppercase tracking-widest font-bold mb-1.5 flex items-center gap-2">
                        <span class="text-amber-500 dark:text-amber-400">{{ selectedAgent?.display_name?.split(' (')[0] || 'Callie' }}</span>
                        <span v-if="msg.author" class="text-gray-400">({{ msg.author }})</span>
                        <span class="w-1 h-1 rounded-full bg-gray-300 dark:bg-gray-600"></span>
                        <span class="text-gray-400">{{ msg.timestamp }}</span>
                      </div>
                      <div
                        class="bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-gray-900 dark:text-gray-100 px-5 py-3.5 rounded-2xl rounded-tl-none shadow-sm prose dark:prose-invert prose-sm max-w-none break-words prose-headings:text-gray-800 dark:prose-headings:text-gray-100 prose-a:text-blue-600 dark:prose-a:text-blue-400 prose-strong:text-gray-900 dark:prose-strong:text-white prose-code:text-pink-600 dark:prose-code:text-pink-300 prose-pre:bg-gray-900 prose-pre:border prose-pre:border-gray-700 prose-th:px-3 prose-th:py-2 prose-td:px-3 prose-td:py-2 prose-table:border-collapse prose-tr:border-b prose-tr:border-gray-200 dark:prose-tr:border-gray-700/50">
                        <div v-html="renderMarkdown(msg.text)"></div>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- Error Message -->
                <div v-else-if="msg.role === 'error'"
                  class="self-center bg-red-900/50 text-red-200 px-4 py-2 rounded-lg border border-red-800 text-sm">
                  {{ msg.text }}
                </div>

              </div>

              <!-- Thinking Container (Live Stream) -->
              <div v-if="isThinking || agentThinking.length > 0"
                class="max-w-5xl mx-auto w-full mt-4 mb-8 transition-all duration-500 ease-in-out">
                <!-- ... existing thinking UI ... -->
                <div v-if="!isComplexWorkflow"
                  class="flex items-center gap-3 px-4 py-2 bg-blue-50/80 dark:bg-gray-800/30 rounded-full w-fit mx-auto border border-blue-100 dark:border-gray-700/30 backdrop-blur-sm animate-pulse shadow-sm">
                  <div class="relative flex h-4 w-4">
                    <span
                      class="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                    <span class="relative inline-flex rounded-full h-4 w-4 bg-blue-500"></span>
                  </div>
                  <span class="text-sm text-gray-600 dark:text-gray-400 font-medium">{{
                    selectedAgent?.display_name.split(' (')[0] ||
                    'Callie' }} is thinking...</span>
                </div>

                <details v-else
                  class="group bg-gray-50 dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700/50 rounded-2xl overflow-hidden transition-all duration-300 open:bg-white dark:open:bg-gray-800/80 shadow-sm"
                  open>
                  <summary
                    class="flex items-center gap-3 px-6 py-4 cursor-pointer select-none text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200 transition-colors list-none">
                    <div v-if="isThinking" class="relative flex h-3 w-3">
                      <span
                        class="animate-ping absolute inline-flex h-full w-full rounded-full bg-purple-400 opacity-75"></span>
                      <span class="relative inline-flex rounded-full h-3 w-3 bg-purple-500"></span>
                    </div>
                    <div v-else class="w-3 h-3 rounded-full bg-gray-500"></div>

                    <span
                      class="font-medium bg-clip-text text-transparent bg-gradient-to-r from-purple-400 to-pink-400 animate-pulse">
                      {{ isThinking ? 'Workflow Active: Generating Report...' : 'Workflow Complete' }}
                    </span>
                    <span
                      class="ml-auto text-[10px] font-bold uppercase tracking-wider bg-gray-200 dark:bg-gray-700 px-2.5 py-1 rounded-full text-gray-500 dark:text-gray-400 group-open:text-gray-700 dark:group-open:text-gray-300 transition-colors">
                      {{ agentThinking.length }} steps
                    </span>
                    <svg class="w-4 h-4 transition-transform group-open:rotate-180 text-gray-500" fill="none"
                      viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
                    </svg>
                  </summary>
                  <div
                    class="p-6 border-t border-gray-100 dark:border-gray-700/50 bg-gray-50/50 dark:bg-gray-900/50 font-mono text-[11px] text-gray-500 dark:text-gray-400 overflow-x-auto max-h-80 custom-scrollbar">
                    <div v-for="(event, idx) in agentThinking" :key="idx"
                      class="mb-3 last:mb-0 hover:bg-white dark:hover:bg-gray-800/50 p-4 rounded-xl transition-all border-l-4 shadow-sm"
                      :class="['content_creator', 'auditor', 'critic', 'refiner'].includes(event.author || '') ? 'border-purple-500/50 bg-purple-50/50 dark:bg-purple-900/10' : 'border-gray-200 dark:border-gray-700 bg-white dark:bg-transparent'">
                      <div class="flex gap-2 mb-1 justify-between">
                        <div class="flex gap-2">
                          <span class="font-bold uppercase tracking-wider text-[10px]" :class="{
                            'text-purple-400': ['content_creator', 'refiner'].includes(event.author || ''),
                            'text-red-400': event.author === 'critic',
                            'text-yellow-400': event.author === 'auditor',
                            'text-blue-400': !['content_creator', 'auditor', 'critic', 'refiner'].includes(event.author || '')
                          }">
                            {{ event.author }}
                          </span>
                          <span class="text-gray-400 dark:text-gray-600 tracking-tighter">{{ event.timestamp ? new
                            Date(event.timestamp *
                              1000).toLocaleTimeString().split(' ')[0] : '' }}</span>
                        </div>
                      </div>
                      <div v-if="event.actions" class="pl-2">
                        <div v-if="event.actions.thought"
                          class="text-gray-600 dark:text-gray-300 mb-1 italic leading-relaxed">
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

          <!-- Bottom Absolute Input with Fade (Gemini Style) -->
          <div v-if="currentSessionId"
            class="absolute bottom-0 left-0 right-0 z-30 pointer-events-none transition-all duration-500">
            <!-- Smooth Gradient Overlay: Bottom (Solid) to Top (Transparent) -->
            <div
              class="absolute inset-x-0 bottom-0 h-64 bg-gradient-to-t from-white via-white/80 to-transparent dark:from-gray-900 dark:via-gray-900/80 dark:to-transparent">
            </div>

            <!-- Input Container Content -->
            <div class="relative max-w-4xl mx-auto p-6 pb-10 pointer-events-auto">
              <div class="group relative">
                <!-- Inner Pill Container -->
                <div
                  class="relative flex items-center gap-2 bg-[#f0f4f9] dark:bg-[#1e1f20] rounded-[32px] px-4 py-3 shadow-sm border border-transparent focus-within:shadow-lg focus-within:bg-white dark:focus-within:bg-[#282a2d] transition-all duration-300">

                  <!-- Left Accessory: Plus Icon -->
                  <button
                    class="p-2.5 rounded-full hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400 transition-colors shrink-0 active:scale-95">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24"
                      stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
                    </svg>
                  </button>

                  <!-- Main Input: Growing Textarea -->
                  <textarea v-model="userInput" @keydown.enter.exact.prevent="sendMessage"
                    class="flex-1 bg-transparent text-gray-800 dark:text-gray-100 placeholder-gray-500 dark:placeholder-gray-400 px-2 py-2 focus:outline-none transition-all resize-none text-base max-h-64 custom-scrollbar"
                    rows="1" placeholder="Message Callie..." :disabled="isThinking" @input="(e: Event) => {
                      const target = e.target as HTMLTextAreaElement;
                      target.style.height = 'auto';
                      target.style.height = target.scrollHeight + 'px'
                    }"></textarea>

                  <!-- Right Accessory: Unified Send Action -->
                  <div class="flex items-center gap-1 shrink-0">
                    <button @click="sendMessage" :disabled="!userInput.trim() || isThinking"
                      class="p-3 rounded-full transition-all duration-300 flex items-center justify-center active:scale-90"
                      :class="userInput.trim()
                        ? 'bg-blue-600 text-white shadow-md hover:bg-blue-700'
                        : 'text-gray-400 dark:text-gray-500 hover:bg-gray-200 dark:hover:bg-gray-700'">
                      <svg v-if="!isThinking" xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none"
                        viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                          d="M5 10l7-7m0 0l7 7m-7-7v18" />
                      </svg>
                      <div v-else
                        class="h-6 w-6 border-2 border-t-transparent border-gray-400 rounded-full animate-spin">
                      </div>
                    </button>
                  </div>
                </div>
              </div>
              <!-- Disclaimer -->
              <div class="text-center mt-3 text-[11px] text-gray-500 dark:text-gray-400 font-normal">
                Callie’s responses depend on the request and available data. Please verify important information.
              </div>
            </div>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Agents Modal -->
    <Transition name="page-fade">
      <div v-if="isAgentsModalOpen"
        class="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-gray-950/60 backdrop-blur-md">
        <div
          class="bg-white dark:bg-gray-800 w-full max-w-6xl rounded-[2.5rem] shadow-2xl border border-gray-200 dark:border-gray-700 overflow-hidden flex flex-col max-h-[90vh]">
          <div
            class="px-8 pt-8 pb-4 flex items-center justify-between border-b border-gray-100 dark:border-gray-700/50">
            <div>
              <h2 class="text-2xl font-semibold text-gray-900 dark:text-white">Choose an Assistant</h2>
              <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">Select the specialized Callie that fits your
                task.
              </p>
            </div>
            <button @click="isAgentsModalOpen = false"
              class="p-2 rounded-full hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-400 transition-colors">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24"
                stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <div class="flex-1 overflow-y-auto p-8 custom-scrollbar">
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              <button v-for="agent in agents" :key="agent.id" @click="selectAgent(agent)"
                class="w-full text-left p-8 rounded-[2.5rem] border-2 transition-all flex flex-col gap-6 group relative overflow-hidden"
                :class="selectedAgent?.id === agent.id
                  ? 'border-blue-500 bg-blue-50/50 dark:bg-blue-500/10'
                  : 'border-gray-100 dark:border-gray-700/50 hover:border-gray-300 dark:hover:border-gray-600 bg-gray-50/50 dark:bg-gray-800/50'">

                <div class="flex items-start gap-5 w-full">
                  <div
                    class="w-16 h-16 rounded-2xl flex-shrink-0 flex items-center justify-center transition-transform group-hover:scale-110 overflow-hidden shadow-md"
                    :class="selectedAgent?.id === agent.id ? ' ring-2 ring-blue-500 ring-offset-2 dark:ring-offset-gray-800' : 'bg-gray-200 dark:bg-gray-700'">
                    <img :src="agent.avatar" class="w-full h-full object-cover" />
                  </div>

                  <div class="flex-1 min-w-0">
                    <div class="flex items-center justify-between mb-2">
                      <h3 class="font-bold text-2xl dark:text-white"
                        :class="selectedAgent?.id === agent.id ? 'text-blue-600' : 'text-gray-900'">{{
                          agent.display_name }}
                      </h3>
                    </div>
                    <p class="text-sm text-gray-500 dark:text-gray-400 leading-relaxed">{{ agent.description }}</p>
                  </div>
                </div>

                <div v-if="selectedAgent?.id === agent.id"
                  class="absolute top-0 right-0 w-24 h-24 pointer-events-none overflow-hidden">
                  <div
                    class="absolute top-4 -right-10 w-32 bg-blue-600 text-white text-[10px] font-black uppercase tracking-[0.2em] py-1.5 shadow-xl transform rotate-45 text-center">
                    Active
                  </div>
                </div>

                <div
                  class="grid grid-cols-1 md:grid-cols-2 gap-4 w-full pt-4 border-t border-gray-200/50 dark:border-gray-700/50">
                  <div>
                    <span
                      class="text-[10px] font-bold text-gray-400 uppercase tracking-widest block mb-2">Personality</span>
                    <p class="text-xs text-gray-600 dark:text-gray-300 italic">"{{ agent.personality }}"</p>
                  </div>
                  <div>
                    <span class="text-[10px] font-bold text-gray-400 uppercase tracking-widest block mb-2">Workflow
                      Path</span>
                    <div class="flex flex-wrap gap-1">
                      <span v-for="(step, idx) in agent.steps.split(' -> ')" :key="idx"
                        class="text-[9px] px-2 py-1 rounded-md bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 font-medium">
                        {{ step }}
                      </span>
                    </div>
                  </div>
                </div>
              </button>
            </div>
          </div>

          <div
            class="px-8 py-6 bg-gray-50 dark:bg-gray-900/50 border-t border-gray-100 dark:border-gray-700/50 flex justify-end">
            <button @click="isAgentsModalOpen = false"
              class="px-6 py-2.5 rounded-full bg-gray-900 dark:bg-white text-white dark:text-gray-900 font-semibold hover:opacity-90 transition-opacity">
              Close
            </button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Help Modal -->
    <Transition name="page-fade">
      <div v-if="isHelpModalOpen"
        class="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-gray-950/60 backdrop-blur-md">
        <div
          class="bg-white dark:bg-gray-800 w-full max-w-lg rounded-[2.5rem] shadow-2xl border border-gray-200 dark:border-gray-700 overflow-hidden flex flex-col">
          <div
            class="px-8 pt-8 pb-4 flex items-center justify-between border-b border-gray-100 dark:border-gray-700/50">
            <div>
              <h2 class="text-2xl font-semibold text-gray-900 dark:text-white">Help Center</h2>
              <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">Application Information & Support</p>
            </div>
            <button @click="isHelpModalOpen = false"
              class="p-2 rounded-full hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-400 transition-colors">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24"
                stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <div class="p-8 space-y-6">
            <div
              class="flex flex-col items-center text-center p-6 bg-blue-50 dark:bg-blue-500/5 rounded-3xl border border-blue-100 dark:border-blue-500/10">
              <div
                class="w-16 h-16 bg-white dark:bg-gray-800 rounded-2xl flex items-center justify-center shadow-lg mb-4">
                <img :src="isDarkMode ? '/callbox-logo-white.svg' : '/callbox-logo.svg'" class="h-8" />
              </div>
              <h3 class="text-xl font-bold text-gray-900 dark:text-white">Callie Agent Platform</h3>
              <p class="text-[10px] text-gray-500 font-mono opacity-50 select-none">v1.2.9 &bull; Direct Response Mode Enabled</p>
            </div>

            <div class="grid grid-cols-1 gap-4">
              <div
                class="flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-900/40 rounded-2xl border border-gray-100 dark:border-gray-700/50">
                <span class="text-sm font-medium text-gray-500">Ownership</span>
                <span class="text-sm font-bold text-gray-900 dark:text-white">Callbox Inc.</span>
              </div>
              <div
                class="flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-900/40 rounded-2xl border border-gray-100 dark:border-gray-700/50">
                <span class="text-sm font-medium text-gray-500 text-left">Author</span>
                <span class="text-[13px] font-bold text-gray-900 dark:text-white text-right">
                  Lucky John F. Faderon
                  <span class="block text-[10px] text-gray-500 dark:text-gray-400 font-normal tracking-tight">Cloud & AI Solutions Architect</span>
                </span>
              </div>
              <div
                class="flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-900/40 rounded-2xl border border-gray-100 dark:border-gray-700/50">
                <span class="text-sm font-medium text-gray-500 text-left">Department</span>
                <span class="text-[13px] font-bold text-gray-900 dark:text-white text-right">
                  Software Development
                  <span class="block text-[10px] text-blue-500 dark:text-blue-400 font-normal">luckyf@callboxinc.com</span>
                </span>
              </div>
              <div
                class="flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-900/40 rounded-2xl border border-gray-100 dark:border-gray-700/50">
                <span class="text-sm font-medium text-gray-500">Status</span>
                <div class="flex items-center gap-1.5 text-xs font-bold text-green-500 uppercase tracking-widest">
                  <div class="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
                  System Online
                </div>
              </div>
            </div>
          </div>

        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
/* Page Transition */
.page-fade-enter-active,
.page-fade-leave-active {
  transition: all 0.8s ease-in-out;
}

.page-fade-enter-from {
  opacity: 0;
  transform: scale(0.95);
  filter: blur(10px);
}

.page-fade-leave-to {
  opacity: 0;
  transform: scale(1.05);
  filter: blur(10px);
}

/* Dropdown Animation */
.dropdown-enter-active,
.dropdown-leave-active {
  transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.dropdown-enter-from,
.dropdown-leave-to {
  opacity: 0;
  transform: scale(0.9) translateY(-10px);
  filter: blur(4px);
}

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
  color: #e5e7eb;
  /* text-gray-200 */
  font-weight: 600;
  border-bottom-width: 1px;
  border-color: #4b5563;
  /* border-gray-600 */
}

.prose td {
  padding: 0.5em;
}

.prose ul>li::marker {
  color: #9ca3af;
  /* text-gray-400 */
}

.prose ol>li::marker {
  color: #9ca3af;
  /* text-gray-400 */
}

/* Reduce default spacing */
.prose p {
  margin-top: 0.5em;
  margin-bottom: 0.5em;
}

.prose ul,
.prose ol {
  margin-top: 0.5em;
  margin-bottom: 0.5em;
  padding-left: 1.5em;
}

.prose li {
  margin-top: 0.25em;
  margin-bottom: 0.25em;
}
</style>
