<script setup lang="ts">
import { ref, onMounted, nextTick, watch } from 'vue'
import MarkdownIt from 'markdown-it'

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
  
  // Use a unique ID for the code block content if needed, but simple DOM traversal works for copy
  const content = md.utils.escapeHtml(token.content)
  
  return `
    <div class="my-4 rounded-lg overflow-hidden border border-gray-700 bg-gray-950/50 shadow-md group code-block">
      <div class="flex items-center justify-between px-3 py-1.5 bg-gray-800/80 border-b border-gray-700/50 text-xs text-gray-400 select-none backdrop-blur-sm">
        <span class="font-mono font-medium opacity-80">${langName || 'text'}</span>
        <button 
          class="copy-code-btn flex items-center gap-1.5 hover:text-white transition-colors focus:outline-none opacity-60 hover:opacity-100"
          title="Copy code"
        >
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

interface Message {
  role: 'user' | 'model' | 'error'
  text: string
  timestamp?: string
  isComplete?: boolean
  author?: string
}

// Minimal definition for Event based on usage
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

const handleChatClick = async (event: MouseEvent) => {
  const target = event.target as HTMLElement
  const copyBtn = target.closest('.copy-code-btn')
  
  if (copyBtn) {
    // Find the code block sibling
    const codeBlock = copyBtn.closest('.code-block')
    const codeElement = codeBlock?.querySelector('code')
    
    if (codeElement && codeElement.textContent) {
      try {
        await navigator.clipboard.writeText(codeElement.textContent)
        
        // Visual feedback
        const originalHtml = copyBtn.innerHTML
        copyBtn.innerHTML = `
          <svg class="w-3.5 h-3.5 text-green-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
          </svg>
          <span class="text-green-400">Copied!</span>
        `
        
        setTimeout(() => {
          copyBtn.innerHTML = originalHtml
        }, 2000)
      } catch (err) {
        console.error('Failed to copy:', err)
      }
    }
  }
}

const socket = ref<WebSocket | null>(null)
const sessions = ref<Session[]>([])
const currentSessionId = ref<string | null>(null)
const chatHistory = ref<Message[]>([])
const agentThinking = ref<AgentEvent[]>([]) // Stores intermediate events
const isThinking = ref(false)
const userInput = ref('')
const appName = 'agent_sm' // Matching the folder name
const userId = 'user_001'
const isConnected = ref(false)

// Connect to WebSocket
const connectWebSocket = () => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const wsUrl = `${protocol}//${window.location.host}/ui/ws`
  
  // For development (if running via vite dev server proxying to 8000 or direct)
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
    // formatting retry logic could go here
    setTimeout(connectWebSocket, 3000)
  }

  socket.value.onerror = (error: Event) => {
    console.error('WebSocket error:', error)
  }
}

const handleMessage = (data: any) => {
  if (data.type === 'session_created') {
    sessions.value.unshift(data.session)
    selectSession(data.session.id)
  } else if (data.type === 'sessions_list') {
    sessions.value = data.sessions.sort((a: Session, b: Session) => {
      const timeA = a.last_update_time || 0
      const timeB = b.last_update_time || 0
      return timeB - timeA
    })
  } else if (data.type === 'session_updated') {
     // Find and update the session in the list
     const idx = sessions.value.findIndex(s => s.id === data.session.id)
     if (idx !== -1) {
       sessions.value[idx] = data.session
       // Re-sort?
       sessions.value.sort((a, b) => (b.last_update_time || 0) - (a.last_update_time || 0))
     }
  } else if (data.type === 'agent_event') {
    processAgentEvent(data.event)
  } else if (data.type === 'chat_complete') {
    isThinking.value = false
  } else if (data.type === 'error') {
    console.error('Server error:', data.message)
    isThinking.value = false
    // Display error in chat?
    chatHistory.value.push({
      role: 'error',
      text: `Error: ${data.message}`
    })
  }
}

const processedEventIds = ref(new Set<string>())

const processAgentEvent = (event: AgentEvent) => {
  // Deduplicate based on ID if available
  if (event.id && processedEventIds.value.has(event.id)) {
    return
  }
  if (event.id) {
    processedEventIds.value.add(event.id)
  }

  // Logic to separate "thinking" (tool calls, thoughts) from "response" (model text)
  // This depends on the event structure from ADK.
  
  if (event.actions && (event.actions.tool_calls || event.actions.thought)) {
    agentThinking.value.push(event)
  }
  
  if (event.content && event.content.parts) {
    // Correctly handle roles. 
    // If it's a 'user' event (echoed back), we shouldn't display it as a model bubble
    // because we added the user message optimistically.
    // If it's a 'user' event, we need to handle it carefully.
    // During live chat, we added it optimistically, so we should ignore the echo if it matches.
    // During history load, there is no optimistic message, so we must add it.
    const role = event.content.role || 'model'
    const textPart = event.content.parts.find(p => p.text)
    
    if (role === 'user') {
      const text = textPart && textPart.text ? textPart.text : ''
      if (!text) return

      const lastMsg = chatHistory.value[chatHistory.value.length - 1]
      
      // Check if this is likely the optimistic update we just made
      // Condition: Last message is user, texts match. 
      // Note: This matches if we *just* sent it.
      // If we are loading history, chatHistory was cleared, so this won't match (unless duplicate events in history).
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
    
    // Model/Agent logic
    if (textPart && textPart.text) {
      // ADK user_id logic: author="writer" or "model" or "root_agent"
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

const sendMessage = () => {
  if (!userInput.value.trim() || !currentSessionId.value || !socket.value) return

  const text = userInput.value
  userInput.value = ''
  
  // Add user message to UI immediately
  chatHistory.value.push({
    role: 'user',
    text: text,
    timestamp: new Date().toLocaleTimeString()
  })

  agentThinking.value = [] // Clear previous thinking
  isThinking.value = true
  processedEventIds.value.clear() // Clear for new turn (optional, but safe for new stream)

  socket.value.send(JSON.stringify({
    type: 'chat',
    app_name: appName,
    user_id: userId,
    session_id: currentSessionId.value,
    new_message: { role: 'user', parts: [{ text: text }] }
  }))
}

const createSession = () => {
  if (!socket.value) return
  
  // Prevent creating new session if we are already in an empty one
  if (currentSessionId.value && chatHistory.value.length === 0) {
    return
  }

  socket.value.send(JSON.stringify({
    type: 'create_session',
    app_name: appName,
    user_id: userId
  }))
}

const listSessions = () => {
  if (!socket.value) return
  socket.value.send(JSON.stringify({
    type: 'list_sessions',
    app_name: appName,
    user_id: userId
  }))
}

const selectSession = (sessionId: string) => {
  currentSessionId.value = sessionId
  chatHistory.value = [] 
  agentThinking.value = []
  processedEventIds.value.clear()
  
  // Load history
  if (socket.value && socket.value.readyState === WebSocket.OPEN) {
      socket.value.send(JSON.stringify({
        type: 'load_history',
        app_name: appName,
        user_id: userId,
        session_id: sessionId
      }))
  }
}

// Auto-scroll chat
const chatContainer = ref<HTMLElement | null>(null)
watch(chatHistory, () => {
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  })
}, { deep: true })

onMounted(() => {
  connectWebSocket()
})
</script>

<template>
  <div class="flex h-screen bg-gray-900 text-gray-100 font-sans">
    <!-- Left Sidebar: Sessions -->
    <div class="w-64 bg-gray-800 border-r border-gray-700 flex flex-col">
      <div class="p-4 border-b border-gray-700 flex justify-between items-center">
        <h1 class="text-xl font-semibold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-teal-400">Callbox</h1>
        <div v-if="isConnected" class="w-3 h-3 rounded-full bg-green-500 shadow-[0_0_8px_rgba(74,222,128,0.6)]"></div>
        <div v-else class="w-3 h-3 rounded-full bg-red-500"></div>
      </div>
      
      <div class="p-4">
        <button 
          @click="createSession"
          class="w-full py-3 px-4 bg-gray-800 hover:bg-gray-750 border border-gray-700 hover:border-gray-600 rounded-full transition-all flex items-center gap-3 font-medium text-gray-300 hover:text-white group shadow-sm"
        >
          <div class="w-6 h-6 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-white shadow-inner group-hover:scale-110 transition-transform">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" clip-rule="evenodd" />
            </svg>
          </div>
          <span>New Chat</span>
        </button>
      </div>

      <div class="flex-1 overflow-y-auto px-2">
        <div v-if="sessions.length === 0" class="text-gray-500 text-center py-4 text-sm">
          No sessions yet
        </div>
        <ul v-else class="space-y-1">
          <li v-for="session in sessions" :key="session.id">
            <button
              @click="selectSession(session.id)"
              class="w-full text-left py-3 px-4 rounded-md text-sm transition-colors group flex flex-col gap-0.5"
              :class="currentSessionId === session.id ? 'bg-gray-700 shadow-sm' : 'hover:bg-gray-700/50'"
            >
              <span class="font-medium truncate w-full" :class="currentSessionId === session.id ? 'text-white' : 'text-gray-400 group-hover:text-gray-200'">{{ session.state?.title || session.id }}</span>
              <span class="text-xs" :class="currentSessionId === session.id ? 'text-gray-400' : 'text-gray-500 group-hover:text-gray-400'">
                {{ formatSessionTime(session.last_update_time) }}
              </span>
            </button>
          </li>
        </ul>
      </div>
    </div>

    <!-- Right Main: Chat -->
    <div class="flex-1 flex flex-col bg-gray-900 relative">
      <!-- Chat Header -->
      <header v-if="currentSessionId" class="h-16 border-b border-gray-800 flex items-center px-6 bg-gray-900/50 backdrop-blur-md sticky top-0 z-10">
        <h2 class="text-lg font-medium text-gray-200">
           Session <span class="text-gray-500 font-normal text-sm ml-2">{{ currentSessionId }}</span>
        </h2>
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
              <span class="bg-clip-text text-transparent bg-gradient-to-r from-blue-400 via-purple-400 to-red-400">Hello, Human</span>
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
                    <div class="bg-gray-800 border border-gray-700 text-gray-100 px-5 py-3 rounded-2xl rounded-tl-none shadow-sm prose prose-invert prose-sm max-w-none break-words prose-code:before:content-none prose-code:after:content-none">
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
          <div v-if="isThinking || agentThinking.length > 0" class="max-w-5xl mx-auto w-full mt-4 mb-8">
            <details class="group bg-gray-800/50 border border-gray-700/50 rounded-lg overflow-hidden transition-all duration-300 open:bg-gray-800/80">
              <summary class="flex items-center gap-3 px-4 py-3 cursor-pointer select-none text-sm text-gray-400 hover:text-gray-200 transition-colors list-none">
                 <div v-if="isThinking" class="relative flex h-3 w-3">
                  <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-teal-400 opacity-75"></span>
                  <span class="relative inline-flex rounded-full h-3 w-3 bg-teal-500"></span>
                </div>
                <div v-else class="w-3 h-3 rounded-full bg-gray-500"></div>
                
                <span class="font-medium">
                  {{ isThinking ? 'Agent is working...' : 'Processing steps' }}
                </span>
                <span class="ml-auto text-xs bg-gray-700 px-2 py-0.5 rounded-full text-gray-400 group-open:text-gray-300">
                  {{ agentThinking.length }} events
                </span>
                <svg class="w-4 h-4 transition-transform group-open:rotate-180 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
                </svg>
              </summary>
              <div class="p-4 border-t border-gray-700/50 bg-gray-900/50 font-mono text-xs text-gray-400 overflow-x-auto max-h-60 custom-scrollbar">
                <div v-for="(event, idx) in agentThinking" :key="idx" class="mb-2 last:mb-0 hover:bg-gray-800/50 p-1 rounded">
                   <div class="flex gap-2 mb-1">
                      <span class="text-blue-400 font-bold">[{{ event.author }}]</span>
                      <span class="text-gray-500">{{ event.timestamp || 'Just now' }}</span>
                   </div>
                   <div v-if="event.actions" class="pl-4 border-l-2 border-gray-700">
                      <div v-if="event.actions.thought" class="text-yellow-300/80 mb-1">
                         Thinking: {{ event.actions.thought }}
                      </div>
                       <div v-if="event.actions.tool_use" class="text-pink-300/80">
                         Tool Call: {{ event.actions.tool_use }}
                      </div>
                   </div>
                    <pre v-if="event.content" class="pl-4 text-gray-300 whitespace-pre-wrap">{{ JSON.stringify(event.content, null, 2) }}</pre>
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
</style>
