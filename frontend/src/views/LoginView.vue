<template>
  <div class="auth-page">
    <div class="auth-card">
      <!-- Brand / hero side -->
      <aside class="auth-brand">
        <SaffronLogo :size="34" variant="white" class="auth-brand-logo" />
                <h1>Welcome back to Saffron</h1>
        <p class="auth-brand-sub">One sign-in for the whole studio: annotators reach their tasks, admins reach their dashboard.</p>
        <div class="auth-feature"><i class="bi bi-soundwave"></i><span>Audio &amp; translation evaluation</span></div>
        <div class="auth-feature"><i class="bi bi-bar-chart-line"></i><span>Track your progress in real time</span></div>
        <div class="auth-feature"><i class="bi bi-shield-lock"></i><span>Secure, token-based access</span></div>
      </aside>

      <!-- Form side -->
      <section class="auth-form-panel">
        <div class="auth-form-mark">
          <SaffronLogo :size="20" /><span>Saffron</span>
        </div>
        <h2 class="auth-title">Sign in</h2>
        <p class="auth-subtitle">Annotators and admins sign in here — you land on the right screen automatically.</p>

        <form class="auth-form" @submit.prevent="handleSubmit">
          <div class="mb-3">
            <label for="username" class="form-label">Username</label>
            <input
              ref="usernameInput"
              type="text"
              id="username"
              v-model="username"
              class="form-control"
              required
              autocomplete="username"
              autofocus
            >
          </div>
          <div class="mb-3">
            <label for="password" class="form-label">Password</label>
            <div class="input-group">
              <input
                ref="passwordInput"
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
          <button type="submit" class="btn btn-saffron w-100 mt-2" :disabled="isSubmitting">
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
import { ref, nextTick, onMounted } from 'vue'
import SaffronLogo from '@/components/SaffronLogo.vue'
import { useRouter, useRoute } from 'vue-router'
import { API_BASE_URL } from '@/config';
import { loadIdentity, landingPath, setActiveTeam } from '@/session';

const router = useRouter()
const route = useRoute()

const username = ref('')
const password = ref('')
const showPassword = ref(false)
const isSubmitting = ref(false)
const error = ref('')
const usernameInput = ref(null)
const passwordInput = ref(null)

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
        username: username.value.trim(),
        password: password.value
      })
    })

    const data = await response.json().catch(() => ({}))
    if (!response.ok) {
      throw new Error(data.message || 'Invalid username or password')
    }

    localStorage.setItem('authToken', data.token)

    if (data.team) setActiveTeam(data.team.key)
    else if (data.teams?.length === 1) setActiveTeam(data.teams[0].key)
    const landing = landingPath({ role: data.role, scope: data.scope,
                                  teams: data.teams || [], team: data.team })
    window.location.href = destinationFor(data.role, landing)  // full refresh
  } catch (err) {
    console.error('Login error:', err)
    // A network failure reads differently from a wrong password.
    error.value = err instanceof TypeError
      ? 'Cannot reach the server. Please check your connection and try again.'
      : (err.message || 'Invalid username or password')
    // Keep the username so a typo in the password doesn't mean retyping everything.
    password.value = ''
    await nextTick()
    passwordInput.value?.focus()
  } finally {
    isSubmitting.value = false
  }
}

/** Where to send someone after a successful sign-in. A real deep link (?redirect=/42?task=7) wins,. */
function destinationFor(role, landing) {
  let dest = route.query.redirect || ''
  if (Array.isArray(dest)) dest = dest[0]
  if (typeof dest !== 'string' || !dest.startsWith('/')) return landing
  if (['/', '/login', '/signup', '/workspaces'].includes(dest)) return landing
  if (role === 'admin' && !/^\/(org|admin\/|[a-z0-9_-]+\/admin)/.test(dest)) return landing
  return dest
}

onMounted(async () => {
  usernameInput.value?.focus()
  // Already signed in? Send them straight where they belong.
  const token = localStorage.getItem('authToken') || sessionStorage.getItem('authToken')
  if (!token) return
  const identity = await loadIdentity()
  router.push(destinationFor(identity.role, landingPath(identity)))
})
</script>
