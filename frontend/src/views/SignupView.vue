<template>
  <div class="auth-page">
    <div class="auth-card">
      <!-- Brand / hero side -->
      <aside class="auth-brand">
        <SaffronLogo :size="34" variant="white" class="auth-brand-logo" />
        <h1>Join Saffron Annotation Studio</h1>
        <p class="auth-brand-sub">Create your annotator profile to start contributing to audio and translation evaluation tasks.</p>
        <div class="auth-feature"><i class="bi bi-list-check"></i><span>Get tasks assigned to your account</span></div>
        <div class="auth-feature"><i class="bi bi-bar-chart-line"></i><span>Track completion as you go</span></div>
        <div class="auth-feature"><i class="bi bi-shield-lock"></i><span>Your work is saved securely</span></div>
      </aside>

      <!-- Form side -->
      <section class="auth-form-panel">
        <div class="auth-form-mark">
          <SaffronLogo :size="20" /><span>Saffron</span>
        </div>
        <h2 class="auth-title">Create account</h2>
        <p class="auth-subtitle">Set up your annotator profile to get started.</p>

        <form class="auth-form" @submit.prevent="handleSubmit">
          <div class="mb-3">
            <label for="name" class="form-label">Username</label>
            <input
              ref="nameInput"
              type="text"
              id="name"
              v-model="name"
              class="form-control"
              required
              autocomplete="username"
              autofocus
            >
            <div class="form-text">You'll sign in with this name.</div>
          </div>

          <div class="row g-3 mb-3">
            <div class="col-6">
              <label for="age" class="form-label">Age</label>
              <input
                type="number"
                id="age"
                v-model="age"
                class="form-control"
                required
                min="10"
                max="100"
              >
            </div>
            <div class="col-6">
              <label for="gender" class="form-label">Gender</label>
              <select id="gender" v-model="gender" class="form-select" required>
                <option value="" disabled>Select</option>
                <option value="Male">Male</option>
                <option value="Female">Female</option>
                <option value="Other">Other</option>
              </select>
            </div>
          </div>

          <div class="mb-3">
            <label for="email" class="form-label">Email</label>
            <input
              type="email"
              id="email"
              v-model="email"
              class="form-control"
              required
              autocomplete="email"
            >
          </div>

          <div class="row g-3 mb-3">
            <div class="col-md-6">
              <label for="password" class="form-label">Password</label>
              <div class="input-group">
                <input
                  :type="showPassword ? 'text' : 'password'"
                  id="password"
                  v-model="password"
                  class="form-control"
                  :class="{ 'is-invalid': password && password.length < MIN_PASSWORD }"
                  required
                  minlength="6"
                  autocomplete="new-password"
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
              <div class="form-text" :class="{ 'text-danger': password && password.length < MIN_PASSWORD }">
                At least {{ MIN_PASSWORD }} characters.
              </div>
            </div>
            <div class="col-md-6">
              <label for="confirmPassword" class="form-label">Confirm Password</label>
              <div class="input-group">
                <input
                  :type="showPassword ? 'text' : 'password'"
                  id="confirmPassword"
                  v-model="confirmPassword"
                  class="form-control"
                  :class="{ 'is-invalid': passwordMismatch, 'is-valid': passwordsMatch }"
                  required
                  autocomplete="new-password"
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
              <div v-if="passwordMismatch" class="form-text text-danger">Passwords don't match yet.</div>
              <div v-else-if="passwordsMatch" class="form-text text-success">Passwords match.</div>
            </div>
          </div>

          <div class="mb-3">
            <label for="team" class="form-label">Team you are joining</label>
            <select id="team" v-model="team" class="form-select" required>
              <option v-for="t in teams" :key="t.key" :value="t.key">{{ t.name }}</option>
            </select>
            <div class="form-text">{{ teamDescription }}</div>
          </div>

          <div class="mb-3">
            <label for="signupPin" class="form-label">Signup PIN</label>
            <input
              type="text"
              inputmode="numeric"
              pattern="[0-9]*"
              maxlength="8"
              id="signupPin"
              v-model="signupPin"
              class="form-control"
              placeholder="8-digit PIN from the admin"
              required
              autocomplete="off"
            >
            <div class="form-text">Ask the admin for the PIN.</div>
          </div>

          <button type="submit" class="btn btn-saffron w-100 mt-2" :disabled="isSubmitting">
            <span v-if="isSubmitting" class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
            {{ isSubmitting ? 'Signing up...' : 'Create account' }}
          </button>
        </form>

        <div v-if="error" class="alert alert-danger mt-3 mb-0 d-flex align-items-center gap-2" role="alert">
          <i class="bi bi-exclamation-circle-fill"></i>
          <span>{{ error }}</span>
        </div>

        <p class="auth-switch">
          Already have an account?
          <router-link to="/login">Sign in</router-link>
        </p>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import SaffronLogo from '@/components/SaffronLogo.vue'
import { API_BASE_URL } from '@/config';

const MIN_PASSWORD = 6

// Form fields
const name = ref('')
const age = ref('')
const gender = ref('')
const team = ref('tts')
const teams = ref([{ key: 'tts', name: 'TTS Team' }, { key: 'asr', name: 'ASR Team' }])
const email = ref('')
const password = ref('')
const confirmPassword = ref('')
const signupPin = ref('')
const showPassword = ref(false)
const nameInput = ref(null)

// Form submission state
const isSubmitting = ref(false)
const error = ref('')

const passwordMismatch = computed(() =>
  confirmPassword.value.length > 0 && password.value !== confirmPassword.value)
const passwordsMatch = computed(() =>
  confirmPassword.value.length > 0 && password.value === confirmPassword.value)

const togglePasswordVisibility = () => {
  showPassword.value = !showPassword.value
}

const validateForm = () => {
  if (!name.value.trim() || !age.value || !gender.value || !email.value.trim()
      || !password.value || !confirmPassword.value) {
    error.value = 'Please fill in all fields.'
    return false
  }
  if (password.value.length < MIN_PASSWORD) {
    error.value = `The password needs at least ${MIN_PASSWORD} characters.`
    return false
  }
  if (password.value !== confirmPassword.value) {
    error.value = 'Passwords do not match.'
    return false
  }
  if (!/^\d{8}$/.test(signupPin.value.trim())) {
    error.value = 'The signup PIN is the 8-digit number the admin shares each day.'
    return false
  }
  return true
}

const teamDescription = computed(() =>
  teams.value.find(t => t.key === team.value)?.description || '')

onMounted(async () => {
  nameInput.value?.focus()
  try {
    const res = await fetch(`${API_BASE_URL}/teams`)
    if (res.ok) {
      const data = await res.json()
      if (data.teams?.length) {
        teams.value = data.teams
        if (!data.teams.some(t => t.key === team.value)) team.value = data.teams[0].key
      }
    }
  } catch { /* fall back to the built-in list */ }
})

const handleSubmit = async () => {
  if (!validateForm()) return

  isSubmitting.value = true
  error.value = ''

  try {
    const response = await fetch(`${API_BASE_URL}/signup`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        name: name.value.trim(),
        age: age.value,
        gender: gender.value,
        email: email.value.trim(),
        password: password.value,
        team: team.value,
        signup_key: signupPin.value.trim()
      })
    })

    const data = await response.json().catch(() => ({}))
    if (!response.ok) {
      throw new Error(data.message || 'Signup failed. Please check your details and try again.')
    }

    localStorage.setItem('authToken', data.token) // Save token for authentication
    window.location.href = '/' // Redirect to home page with full refresh
  } catch (err) {
    console.error('Signup error:', err)
    error.value = err instanceof TypeError
      ? 'Cannot reach the server. Please check your connection and try again.'
      : (err.message || 'Signup failed. Please try again.')
  } finally {
    isSubmitting.value = false
  }
}
</script>
