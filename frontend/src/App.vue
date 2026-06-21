<template>
  <div>
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark py-0" style="min-height: 40px; line-height: 40px;">
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
            class="btn btn-sm btn-outline-light d-flex align-items-center gap-1 py-0.5 px-2.5 rounded-pill"
            style="font-size: 0.8rem; font-weight: 500; border-color: rgba(255, 255, 255, 0.25); color: #e2e8f0; height: 26px; line-height: 1;"
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
          <ul class="navbar-nav ms-auto align-items-center py-0">
            <li v-if="isLoggedIn && isAdmin && route.name !== 'DynamicTest'" class="nav-item me-3">
              <router-link to="/tracking" class="nav-link py-0 d-flex align-items-center" style="height: 40px;">
                <span>Admin Dashboard</span>
              </router-link>
            </li>
            <li v-if="isLoggedIn && route.name !== 'DynamicTest'" class="nav-item">
              <a href="#" class="nav-link py-0 d-flex align-items-center" style="height: 40px;" @click.prevent="logout">
                <span>Logout</span>
              </a>
            </li>
            <li v-else-if="route.name !== 'DynamicTest'" class="nav-item">
              <router-link
                :to="isLoginPage ? '/signup' : '/login'"
                class="nav-link py-0 d-flex align-items-center"
                style="height: 40px;"
              >
                <span>{{ isLoginPage ? 'Signup' : 'Log-in' }}</span>
              </router-link>
            </li>
          </ul>
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

:global(body) {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
    Oxygen-Sans, Ubuntu, Cantarell, 'Helvetica Neue', sans-serif;
}
</style>
