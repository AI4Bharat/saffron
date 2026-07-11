<template>
  <div>
    <nav class="navbar navbar-expand-lg navbar-dark app-navbar py-0" style="min-height: 48px;">
      <div class="container">
        <div class="d-flex align-items-center me-auto">
          <router-link to="/" class="navbar-brand d-flex align-items-center py-0 me-3">
            <span class="brand-logo me-2" aria-hidden="true">
              <svg viewBox="0 0 32 32" width="26" height="26" fill="none" xmlns="http://www.w3.org/2000/svg">
                <defs>
                  <linearGradient id="sfrn" x1="4" y1="3" x2="28" y2="29" gradientUnits="userSpaceOnUse">
                    <stop stop-color="#f4a93c"/><stop offset="1" stop-color="#d8661b"/>
                  </linearGradient>
                </defs>
                <!-- three saffron stigmas radiating from a crocus base -->
                <path d="M16 16 C16 16 11 9 9 4 C13 6 15 11 16 16Z" fill="url(#sfrn)"/>
                <path d="M16 16 C16 16 21 9 23 4 C19 6 17 11 16 16Z" fill="url(#sfrn)"/>
                <path d="M16 16 C16 16 16 7 16 2 C17.6 6 17 11 16 16Z" fill="url(#sfrn)"/>
                <path d="M16 15 C10 16 6 20 5 27 C12 27 15 22 16 16 C17 22 20 27 27 27 C26 20 22 16 16 15Z" fill="url(#sfrn)" opacity="0.92"/>
              </svg>
            </span>
            <span class="brand-text">Saffron</span>
            <span class="brand-sub d-none d-md-inline">Annotation Studio</span>
          </router-link>
          
          <router-link
            v-if="isLoggedIn && route.path !== '/'"
            to="/"
            class="nav-pill nav-pill-ghost"
          >
            <i class="bi bi-arrow-left"></i>
            <span>Back</span>
          </router-link>
        </div>

        <button
          class="navbar-toggler"
          type="button"
          data-bs-toggle="collapse"
          data-bs-target="#navbar"
          aria-controls="navbar"
          aria-expanded="false"
          aria-label="Toggle navigation"
          style="padding: 0.2rem 0.4rem; font-size: 0.85rem;"
        >
          <span class="navbar-toggler-icon"></span>
        </button>

        <div class="collapse navbar-collapse" id="navbar">
          <div class="ms-auto d-flex align-items-center gap-2 nav-cluster py-2 py-lg-0">

            <!-- Admin dashboard (admin only) -->
            <router-link
              v-if="isLoggedIn && isAdmin && route.name !== 'DynamicTest'"
              to="/tracking"
              class="nav-pill"
            >
              <i class="bi bi-speedometer2"></i>
              <span>Dashboard</span>
            </router-link>

            <!-- Notification bell (annotators only) — its own spot, always visible -->
            <div v-if="isLoggedIn && !isAdmin && route.name !== 'DynamicTest'" class="notif-wrap">
              <button
                class="notif-bell"
                type="button"
                @click="toggleNotif"
                :aria-label="unreadCount ? unreadCount + ' new message(s)' : 'Messages'"
                :title="unreadCount ? unreadCount + ' new message(s)' : 'Messages from admin'"
              >
                <i class="bi" :class="[unreadCount ? 'bi-bell-fill' : 'bi-bell', { 'notif-shake': unreadCount }]"></i>
                <span v-if="unreadCount" class="notif-badge">{{ unreadCount > 9 ? '9+' : unreadCount }}</span>
              </button>
              <transition name="notif-fade">
                <div v-if="showNotif">
                  <div class="notif-backdrop" @click="showNotif = false"></div>
                  <div class="notif-panel shadow-lg">
                    <div class="notif-header d-flex align-items-center justify-content-between">
                      <span class="fw-bold text-dark d-flex align-items-center gap-2">
                        <i class="bi bi-inbox-fill text-primary"></i> Messages from admin
                      </span>
                      <button v-if="unreadCount" class="btn btn-sm btn-link p-0 text-decoration-none" @click="markAllRead" :disabled="isMarkingRead">Mark all read</button>
                    </div>
                    <div class="notif-body">
                      <div v-if="!messages.length" class="notif-empty">
                        <i class="bi bi-inbox d-block mb-1"></i>No messages yet.
                      </div>
                      <div v-for="m in messages" :key="m.id" class="notif-item" :class="[notifKind(m.category), { unread: !m.is_read }]">
                        <span class="notif-avatar flex-shrink-0" :class="notifKind(m.category)">
                          <i class="bi" :class="notifIcon(m.category)"></i>
                        </span>
                        <div class="flex-grow-1 min-w-0">
                          <div class="d-flex justify-content-between align-items-center gap-2 mb-1">
                            <span class="notif-cat-chip" :class="notifKind(m.category)">{{ notifLabel(m.category) }}</span>
                            <small class="notif-time flex-shrink-0">
                              <span v-if="!m.is_read" class="notif-dot"></span>{{ formatMsgDate(m.created_at) }}
                            </small>
                          </div>
                          <div class="notif-text">{{ m.body }}</div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </transition>
            </div>

            <!-- Divider between the bell and the account actions -->
            <span v-if="isLoggedIn && route.name !== 'DynamicTest'" class="nav-divider"></span>

            <!-- Logout -->
            <a
              v-if="isLoggedIn && route.name !== 'DynamicTest'"
              href="#"
              class="nav-pill nav-pill-danger"
              @click.prevent="logout"
            >
              <i class="bi bi-box-arrow-right"></i>
              <span>Logout</span>
            </a>

            <!-- Login / Signup (logged out) -->
            <router-link
              v-else-if="route.name !== 'DynamicTest'"
              :to="isLoginPage ? '/signup' : '/login'"
              class="nav-pill nav-pill-accent"
            >
              <i class="bi" :class="isLoginPage ? 'bi-person-plus-fill' : 'bi-box-arrow-in-right'"></i>
              <span>{{ isLoginPage ? 'Signup' : 'Log-in' }}</span>
            </router-link>
          </div>
        </div>
      </div>
    </nav>

    <div v-if="isBackendMaintenance" class="alert alert-warning text-center py-2" role="alert" style="margin-bottom: 0;">
      <i class="bi bi-exclamation-triangle-fill me-2 text-dark"></i>
      The backend server is currently unreachable. Trying to reconnect...
    </div>

    <router-view />
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { API_BASE_URL } from '@/config';

console.log('API Base URL:', API_BASE_URL);

// Router and Route
const router = useRouter()
const route = useRoute()

// State
const isLoggedIn = ref(false)
const isAdmin = ref(false)
const isLoginPage = computed(() => route.path === '/login')
const isBackendMaintenance = ref(false)

// ---- Annotator notifications (admin -> annotator messages) ----
const messages = ref([])
const unreadCount = ref(0)
const showNotif = ref(false)
const isMarkingRead = ref(false)
let msgPollId = null

const notifKind = (cat) =>
  cat === 'nudge' ? 'nudge' : cat === 'broadcast' ? 'broadcast' : 'message'
const notifIcon = (cat) =>
  cat === 'nudge' ? 'bi-bell-fill' : cat === 'broadcast' ? 'bi-stars' : 'bi-chat-left-text-fill'
const notifLabel = (cat) =>
  cat === 'nudge' ? 'Task reminder' : cat === 'broadcast' ? 'Announcement' : 'Message'
const formatMsgDate = (iso) => {
  if (!iso) return ''
  const d = new Date(iso)
  if (isNaN(d.getTime())) return ''
  return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

const fetchMessages = async () => {
  if (!isLoggedIn.value || isAdmin.value) return
  try {
    const token = localStorage.getItem('authToken')
    if (!token) return
    const resp = await fetch(`${API_BASE_URL}/rater/messages`, { headers: { 'Authorization': `Bearer ${token}` } })
    if (!resp.ok) return
    const data = await resp.json()
    messages.value = data.messages || []
    unreadCount.value = data.unread_count || 0
  } catch (e) { /* offline; ignore */ }
}

const markAllRead = async () => {
  if (isMarkingRead.value || !unreadCount.value) return
  isMarkingRead.value = true
  try {
    const token = localStorage.getItem('authToken')
    const resp = await fetch(`${API_BASE_URL}/rater/messages/read`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    })
    if (resp.ok) {
      messages.value = messages.value.map(m => ({ ...m, is_read: true }))
      unreadCount.value = 0
    }
  } catch (e) { /* ignore */ }
  finally { isMarkingRead.value = false }
}

const toggleNotif = () => {
  showNotif.value = !showNotif.value
  if (showNotif.value) {
    fetchMessages()
    // Let the annotator see which are new, then clear the badge.
    if (unreadCount.value) setTimeout(markAllRead, 1500)
  }
}

const startMsgPolling = () => {
  if (msgPollId || isAdmin.value || !isLoggedIn.value) return
  fetchMessages()
  msgPollId = setInterval(fetchMessages, 30000)
}
const stopMsgPolling = () => {
  if (msgPollId) { clearInterval(msgPollId); msgPollId = null }
  messages.value = []
  unreadCount.value = 0
  showNotif.value = false
}

// Methods
const checkLoginStatus = () => {
  try {
    const token = localStorage.getItem('authToken')
    isLoggedIn.value = !!token
    if (token) {
      try {
        const payload = JSON.parse(atob(token.split('.')[1]))
        isAdmin.value = (payload.username === 'admin')
      } catch (e) {
        isAdmin.value = false
      }
    } else {
      isAdmin.value = false
    }
  } catch (error) {
    console.error('Error accessing localStorage:', error)
    isLoggedIn.value = false
    isAdmin.value = false
  }
  // Start/stop the annotator message poll based on the resolved auth state.
  if (isLoggedIn.value && !isAdmin.value) startMsgPolling()
  else stopMsgPolling()
}

const checkTokenExpiration = () => {
  const token = localStorage.getItem('authToken')
  if (token) {
    try {
      const payload = JSON.parse(atob(token.split('.')[1]))
      const expiration = payload.exp * 1000 // Convert to milliseconds
      const now = Date.now()

      if (now >= expiration) {
        logout()
      }
    } catch (error) {
      console.error('Error decoding token:', error)
      logout()
    }
  }
}

const logout = async () => {
  try {
    localStorage.removeItem('authToken')
    isLoggedIn.value = false
    isAdmin.value = false
    stopMsgPolling()
    router.push('/login')
  } catch (error) {
    console.error('Error during logout:', error)
  }
}

const checkBackendStatus = async () => {
  try {
    const response = await fetch(`${API_BASE_URL}/`)
    console.log('Backend status response:', response)
    isBackendMaintenance.value = !response.ok
  } catch (error) {
    console.error('Error checking backend status:', error)
    isBackendMaintenance.value = true
  }
}

// Watch route changes to update login status
watch(() => route.path, () => {
  checkLoginStatus()
})

// Lifecycle Hooks
let tokenIntervalId
let backendIntervalId

onMounted(() => {
  if (route.path !== '/test') {
    checkLoginStatus()
    checkTokenExpiration()
    checkBackendStatus() // Initial check
    tokenIntervalId = setInterval(checkTokenExpiration, 120000) // Check every 2 minutes
    backendIntervalId = setInterval(checkBackendStatus, 300000) // Check every 5 minutes
  }
  else {
    checkBackendStatus()
    isLoggedIn.value = true
    isAdmin.value = false
    backendIntervalId = setInterval(checkBackendStatus, 300000) // Check every 5 minutes
  }
})

onUnmounted(() => {
  clearInterval(tokenIntervalId)
  clearInterval(backendIntervalId)
  stopMsgPolling()
})
</script>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {
  --primary-color: #d8661b;
  --text-color: #ffffff;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
    Oxygen-Sans, Ubuntu, Cantarell, 'Helvetica Neue', sans-serif;
}

.navbar-brand {
  display: flex;
  align-items: center;
}

.brand-text {
  color: var(--primary-color);
  font-weight: bold;
  font-size: 1.2rem;
}

.brand-logo {
  display: inline-flex;
  align-items: center;
  line-height: 0;
  filter: drop-shadow(0 1px 2px rgba(216, 102, 27, 0.35));
}

.brand-sub {
  color: #94a3b8;
  font-weight: 500;
  font-size: 0.78rem;
  margin-left: 0.5rem;
  padding-left: 0.6rem;
  border-left: 1px solid rgba(255, 255, 255, 0.18);
  letter-spacing: 0.02em;
}

.nav-link {
  color: var(--text-color);
  font-weight: bold;
  transition: opacity 0.3s ease;
}

.nav-link:hover {
  opacity: 0.8;
}

.alert {
  margin-bottom: 0;
}

@media (max-width: 768px) {
  .navbar-brand img {
    width: 40px;
  }

  .brand-text {
    font-size: 1rem;
  }
}

/* ---- Interesting dark top bar ---- */
.app-navbar {
  background: linear-gradient(90deg, #0f141d 0%, #1b2333 50%, #0f141d 100%);
  border-bottom: 1px solid rgba(255,255,255,0.06);
  position: relative;
  box-shadow: 0 2px 12px rgba(0,0,0,0.28);
}
.app-navbar::after {
  content: '';
  position: absolute;
  left: 0; right: 0; bottom: 0;
  height: 2px;
  background: linear-gradient(90deg, #f4a93c, #d8661b, #f4a93c);
  opacity: 0.9;
}

/* Pill-style nav actions (Back / Dashboard / Logout / Login) */
.nav-cluster { line-height: normal; }
.nav-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 34px;
  padding: 0 15px;
  border-radius: 999px;
  font-size: 0.82rem;
  font-weight: 600;
  color: #e2e8f0;
  text-decoration: none;
  border: 1px solid rgba(255,255,255,0.14);
  background: rgba(255,255,255,0.04);
  white-space: nowrap;
  transition: color .15s ease, background-color .15s ease, border-color .15s ease, transform .15s ease, box-shadow .15s ease, filter .15s ease;
}
.nav-pill:hover { color: #fff; background: rgba(255,255,255,0.12); border-color: rgba(255,255,255,0.28); transform: translateY(-1px); }
.nav-pill .bi { font-size: 0.95rem; }
.nav-pill-ghost { background: transparent; border-color: rgba(255,255,255,0.18); }
.nav-pill-danger:hover { background: #ef4444; border-color: #ef4444; color: #fff; box-shadow: 0 4px 12px rgba(239,68,68,0.35); }
.nav-pill-accent { background: linear-gradient(135deg, #f4a93c, #d8661b); border-color: transparent; color: #fff; }
.nav-pill-accent:hover { filter: brightness(1.08); color: #fff; box-shadow: 0 4px 12px rgba(216,102,27,0.4); }
.nav-divider { width: 1px; height: 24px; background: rgba(255,255,255,0.18); display: inline-block; }

/* ---- Notification bell + inbox panel ---- */
.notif-wrap { position: relative; display: inline-flex; align-items: center; }
.notif-bell {
  position: relative;
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.13);
  color: #f6c67a;
  font-size: 1.4rem;
  line-height: 1;
  width: 40px;
  height: 40px;
  cursor: pointer;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: color .15s ease, background-color .15s ease, border-color .15s ease, transform .15s ease, box-shadow .15s ease;
}
.notif-bell:hover {
  color: #fff;
  background-color: rgba(244,169,60,0.22);
  border-color: rgba(244,169,60,0.5);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.28);
}
.notif-badge {
  position: absolute;
  top: -3px;
  right: -3px;
  min-width: 18px;
  height: 18px;
  padding: 0 4px;
  background: #ef4444;
  color: #fff;
  font-size: 0.66rem;
  font-weight: 700;
  line-height: 18px;
  text-align: center;
  border-radius: 999px;
  box-shadow: 0 0 0 2px #131a26;
}
@keyframes notif-shake {
  0%, 92%, 100% { transform: rotate(0); }
  94% { transform: rotate(-12deg); }
  96% { transform: rotate(10deg); }
  98% { transform: rotate(-6deg); }
}
.notif-shake { animation: notif-shake 3s ease-in-out infinite; transform-origin: 50% 0; }

.notif-backdrop { position: fixed; inset: 0; z-index: 1040; background: transparent; }
.notif-panel {
  position: absolute;
  top: 52px;
  right: 0;
  width: 340px;
  max-width: 92vw;
  max-height: 440px;
  overflow-y: auto;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  z-index: 1050;
  line-height: 1.5;
  text-align: left;
}
.notif-header {
  position: sticky;
  top: 0;
  background: #fff;
  padding: 10px 14px;
  border-bottom: 1px solid #eef2f7;
  font-size: 0.9rem;
  z-index: 1;
}
.notif-body { padding: 4px 0; }
.notif-empty { text-align: center; color: #94a3b8; padding: 26px 12px; font-size: 0.85rem; }
.notif-empty .bi { font-size: 1.6rem; }
.notif-item {
  display: flex;
  gap: 11px;
  padding: 12px 14px;
  border-bottom: 1px solid #f1f5f9;
  font-weight: 400;
  transition: background-color .15s ease;
}
.notif-item:last-child { border-bottom: none; }
.notif-item:hover { background: #f8fafc; }
.notif-item.unread { background: #fff8f0; box-shadow: inset 3px 0 0 #d8661b; }
.notif-item.unread:hover { background: #fff3e6; }
/* Coloured avatar circle per message type */
.notif-avatar {
  width: 36px; height: 36px; border-radius: 50%;
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 1.02rem; color: #fff;
}
.notif-avatar.broadcast { background: linear-gradient(135deg, #f4a93c, #d8661b); }
.notif-avatar.nudge { background: linear-gradient(135deg, #fbbf24, #f59e0b); }
.notif-avatar.message { background: linear-gradient(135deg, #818cf8, #4f46e5); }
/* Category chip */
.notif-cat-chip {
  font-size: 0.64rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em;
  padding: 2px 9px; border-radius: 999px;
}
.notif-cat-chip.broadcast { background: #fff1e2; color: #c2410c; }
.notif-cat-chip.nudge { background: #fef3c7; color: #b45309; }
.notif-cat-chip.message { background: #e0e7ff; color: #4338ca; }
.notif-time { color: #94a3b8; font-size: 0.72rem; font-weight: 500; }
.notif-text { color: #334155; font-size: 0.84rem; white-space: pre-wrap; word-break: break-word; line-height: 1.55; }
.notif-dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: #ef4444; margin-right: 5px; vertical-align: middle; }
.min-w-0 { min-width: 0; }
.notif-fade-enter-active, .notif-fade-leave-active { transition: opacity .15s ease; }
.notif-fade-enter-from, .notif-fade-leave-to { opacity: 0; }

/* Stacked nav (mobile hamburger): drop the vertical divider, left-align actions */
@media (max-width: 991.98px) {
  .nav-cluster { align-items: flex-start !important; gap: 8px; padding-bottom: 10px; }
  .nav-divider { display: none; }
  .notif-panel { top: 48px; right: auto; left: 0; }
}

:global(body) {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
    Oxygen-Sans, Ubuntu, Cantarell, 'Helvetica Neue', sans-serif;
}
</style>
