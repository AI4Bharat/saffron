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
          <ul class="navbar-nav ms-auto">
            <li v-if="isLoggedIn && route.name !== 'DynamicTest'" class="nav-item">
              <a href="#" class="nav-link" @click.prevent="logout">
              <p>Logout</p>
              </a>
            </li>
            <li v-else-if="route.name !== 'DynamicTest'" class="nav-item">
              <router-link
              :to="isLoginPage ? '/signup' : '/login'"
              class="nav-link"
              >
              <p>{{ isLoginPage ? 'Signup' : 'Log-in' }}</p>
              </router-link>
            </li>
          </ul>
        </div>
      </div>
    </nav>

    <div v-if="isBackendMaintenance" class="alert alert-warning" role="alert">
      The backend is currently under maintenance. Please try again later.
    </div>

    <router-view v-if="!isBackendMaintenance" />
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { API_BASE_URL } from '@/config';

console.log('API Base URL:', API_BASE_URL);
// Environment Variables
// const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:4020'

// Router and Route
const router = useRouter()
const route = useRoute()

// State
const isLoggedIn = ref(false)
const isLoginPage = computed(() => route.path === '/login')
const isBackendMaintenance = ref(false)

// Methods
const checkLoginStatus = () => {
  try {
    const token = localStorage.getItem('authToken')
    isLoggedIn.value = !!token
  } catch (error) {
    console.error('Error accessing localStorage:', error)
    isLoggedIn.value = false
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
    router.push('/login')
  } catch (error) {
    console.error('Error during logout:', error)
    // Optionally, display a user-friendly message
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

// Lifecycle Hooks
let tokenIntervalId
let backendIntervalId

onMounted(() => {
  if (route.path !== '/test') {
    checkLoginStatus()
    checkTokenExpiration()
    checkBackendStatus() // Initial check
    tokenIntervalId = setInterval(checkTokenExpiration, 300000) // Check every 2 minutes
    backendIntervalId = setInterval(checkBackendStatus, 300000) // Check every 5 minutes
  }
  else {
    checkBackendStatus()
    isLoggedIn.value = true
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
