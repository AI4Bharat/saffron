<template>
  <div>
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark py-1">
      <div class="container">
        <button
          class="navbar-toggler"
          type="button"
          data-bs-toggle="collapse"
          data-bs-target="#navbar"
          aria-controls="navbar"
          aria-expanded="false"
          aria-label="Toggle navigation"
        >
          <span class="navbar-toggler-icon"></span>
        </button>
        <div class="collapse navbar-collapse" id="navbar">
          <ul class="navbar-nav ms-auto align-items-center">
            <li v-if="isLoggedIn && isAdmin && route.name !== 'DynamicTest'" class="nav-item me-3">
              <router-link to="/tracking" class="nav-link">
                <p class="mb-0">Admin Dashboard</p>
              </router-link>
            </li>
            <li v-if="isLoggedIn && route.name !== 'DynamicTest'" class="nav-item">
              <a href="#" class="nav-link" @click.prevent="logout">
                <p class="mb-0">Logout</p>
              </a>
            </li>
            <li v-else-if="route.name !== 'DynamicTest'" class="nav-item">
              <router-link
                :to="isLoginPage ? '/signup' : '/login'"
                class="nav-link"
              >
                <p class="mb-0">{{ isLoginPage ? 'Signup' : 'Log-in' }}</p>
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
  height: 20px;
}

.brand-text {
  color: var(--primary-color);
  font-weight: bold;
  font-size: 1.2rem;
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
