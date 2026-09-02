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
          <div class="text-center mt-3">
            <button type="button" class="btn btn-link btn-sm p-0 auth-forgot"
                    @click="openForgot">Forgot password?</button>
          </div>
        </form>

        <!-- Forgot password: files a request for an admin to answer. -->
        <div v-if="forgotOpen" class="forgot-panel mt-3">
          <template v-if="!forgotSent">
            <p class="text-muted small mb-2">
              Enter your username. Your admin will send you a link to set a new password.
            </p>
            <form class="d-flex gap-2" @submit.prevent="submitForgot">
              <input v-model="forgotUsername" class="form-control form-control-sm"
                     placeholder="Your username" autocomplete="username" :disabled="forgotBusy">
              <button class="btn btn-sm btn-saffron px-3" type="submit"
                      :disabled="forgotBusy || !forgotUsername.trim()">
                <span v-if="forgotBusy" class="spinner-border spinner-border-sm"></span>
                <span v-else>Send</span>
              </button>
            </form>
            <button type="button" class="btn btn-link btn-sm p-0 mt-2 text-muted"
                    @click="forgotOpen = false">Cancel</button>
          </template>
          <div v-else class="d-flex align-items-start gap-2">
            <i class="bi bi-check-circle-fill text-success mt-1"></i>
            <div>
              <p class="mb-1 small">{{ forgotMessage }}</p>
              <button type="button" class="btn btn-link btn-sm p-0 text-muted"
                      @click="forgotOpen = false">Close</button>
            </div>
          </div>
        </div>

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
const forgotOpen = ref(false)
const forgotUsername = ref('')
const forgotBusy = ref(false)
const forgotSent = ref(false)
const forgotMessage = ref('')
const passwordInput = ref(null)

function openForgot() {
  forgotOpen.value = true
  forgotSent.value = false
  // Save retyping when they already started signing in.
  if (!forgotUsername.value) forgotUsername.value = username.value
}

async function submitForgot() {
  if (forgotBusy.value) return
  forgotBusy.value = true
  try {
    const r = await fetch(`${API_BASE_URL}/password_reset/request`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: forgotUsername.value.trim() }),
    })
    const d = await r.json().catch(() => ({}))
    // The server answers the same way whichever the outcome, on purpose.
    forgotMessage.value = d.message
      || 'If that account exists, your admin has been notified.'
  } catch (e) {
    forgotMessage.value = 'Could not reach the server. Please try again.'
  } finally {
    forgotBusy.value = false
    forgotSent.value = true
  }
}

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
