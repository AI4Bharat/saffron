<template>
  <div class="auth-page">
    <div class="auth-card">
      <!-- Brand / hero side -->
      <aside class="auth-brand">
        <span class="auth-brand-logo" aria-hidden="true">
          <svg viewBox="0 0 32 32" width="30" height="30" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M16 16 C16 16 11 9 9 4 C13 6 15 11 16 16Z" fill="#fff" opacity="0.95"/>
            <path d="M16 16 C16 16 21 9 23 4 C19 6 17 11 16 16Z" fill="#fff" opacity="0.95"/>
            <path d="M16 16 C16 16 16 7 16 2 C17.6 6 17 11 16 16Z" fill="#fff" opacity="0.95"/>
            <path d="M16 15 C10 16 6 20 5 27 C12 27 15 22 16 16 C17 22 20 27 27 27 C26 20 22 16 16 15Z" fill="#fff"/>
          </svg>
        </span>
        <h1>Welcome back to Saffron</h1>
        <p class="auth-brand-sub">Sign in to pick up your annotation and translation tasks where you left off.</p>
        <div class="auth-feature"><i class="bi bi-soundwave"></i><span>Audio &amp; translation evaluation</span></div>
        <div class="auth-feature"><i class="bi bi-bar-chart-line"></i><span>Track your progress in real time</span></div>
        <div class="auth-feature"><i class="bi bi-shield-lock"></i><span>Secure, token-based access</span></div>
      </aside>

      <!-- Form side -->
      <section class="auth-form-panel">
        <div class="auth-form-mark">
          <i class="bi bi-flower1"></i><span>Saffron</span>
        </div>
        <h2 class="auth-title">Sign in</h2>
        <p class="auth-subtitle">Enter your credentials to access your tasks.</p>

        <form class="auth-form" @submit.prevent="handleSubmit">
          <div class="mb-3">
            <label for="username" class="form-label">Username</label>
            <input
              type="text"
              id="username"
              v-model="username"
              class="form-control"
              required
              autocomplete="username"
            >
          </div>
          <div class="mb-3">
            <label for="password" class="form-label">Password</label>
            <div class="input-group">
              <input
                :type="showPassword ? 'text' : 'password'"
                id="password"
                v-model="password"
                class="form-control"
                required
                autocomplete="current-password"
              >
              <button
                type="button"
                class="btn btn-reveal"
                :aria-label="showPassword ? 'Hide password' : 'Show password'"
                @click="togglePasswordVisibility"
              >
                <i :class="showPassword ? 'bi bi-eye-slash' : 'bi bi-eye'"></i>
              </button>
            </div>
          </div>
          <div class="mb-4 form-check">
            <input type="checkbox" class="form-check-input" id="rememberMe" v-model="rememberMe">
            <label class="form-check-label" for="rememberMe">Remember me</label>
          </div>
          <button type="submit" class="btn btn-saffron w-100" :disabled="isSubmitting">
            <span v-if="isSubmitting" class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
            {{ isSubmitting ? 'Logging in...' : 'Login' }}
          </button>
        </form>

        <div v-if="error" class="alert alert-danger mt-3 mb-0 d-flex align-items-center gap-2" role="alert">
          <i class="bi bi-exclamation-circle-fill"></i>
          <span>{{ error }}</span>
        </div>

        <p class="auth-switch">
          Don't have an account?
          <router-link to="/signup">Create one</router-link>
        </p>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { API_BASE_URL } from '@/config';

const router = useRouter()
const route = useRoute()

const username = ref('')
const password = ref('')
const showPassword = ref(false)
const rememberMe = ref(true)  // Set to true by default
const isSubmitting = ref(false)
const error = ref('')

const togglePasswordVisibility = () => {
  showPassword.value = !showPassword.value
}

const validateForm = () => {
  if (!username.value || !password.value) {
    error.value = 'Please fill in all fields.'
    return false
  }
  return true
}

const handleSubmit = async () => {
  if (!validateForm()) return

  isSubmitting.value = true
  error.value = ''

  try {
    const response = await fetch(`${API_BASE_URL}/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        username: username.value,
        password: password.value
      })
    })

    if (!response.ok) {
      throw new Error('Invalid credentials')
    }

    const data = await response.json()

    if (rememberMe.value) {
      localStorage.setItem('authToken', data.token)
    } else {
      sessionStorage.setItem('authToken', data.token)
    }

    // Return the user to whatever they originally clicked (deep links carry
    // ?redirect=/<test_id>?task=<id>); fall back to home.
    let redirectPath = route.query.redirect || '/'
    if (Array.isArray(redirectPath)) redirectPath = redirectPath[0]
    // only allow internal paths -- never bounce to an external site
    if (typeof redirectPath !== 'string' || !redirectPath.startsWith('/')) redirectPath = '/'
    window.location.href = redirectPath  // Redirect with full refresh
  } catch (err) {
    console.error('Login error:', err)
    error.value = 'Invalid username or password'
    username.value = ''
    password.value = ''
  } finally {
    isSubmitting.value = false
  }
}

onMounted(() => {
  // Check if there's a stored token
  const token = localStorage.getItem('authToken') || sessionStorage.getItem('authToken')
  if (token) {
    let dest = route.query.redirect || '/'
    if (Array.isArray(dest)) dest = dest[0]
    if (typeof dest !== 'string' || !dest.startsWith('/')) dest = '/'
    router.push(dest)  // already logged in: honour the deep link
  }
})
</script>
