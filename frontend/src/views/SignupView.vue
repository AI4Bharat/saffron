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
        <h1>Join Saffron Annotation Studio</h1>
        <p class="auth-brand-sub">Create your annotator profile to start contributing to audio and translation evaluation tasks.</p>
        <div class="auth-feature"><i class="bi bi-list-check"></i><span>Get tasks assigned to your account</span></div>
        <div class="auth-feature"><i class="bi bi-bar-chart-line"></i><span>Track completion as you go</span></div>
        <div class="auth-feature"><i class="bi bi-shield-lock"></i><span>Your work is saved securely</span></div>
      </aside>

      <!-- Form side -->
      <section class="auth-form-panel">
        <div class="auth-form-mark">
          <i class="bi bi-flower1"></i><span>Saffron</span>
        </div>
        <h2 class="auth-title">Create account</h2>
        <p class="auth-subtitle">Set up your annotator profile to get started.</p>

        <form class="auth-form" @submit.prevent="handleSubmit">
          <div class="mb-3">
            <label for="name" class="form-label">Username</label>
            <input
              type="text"
              id="name"
              v-model="name"
              class="form-control"
              required
            >
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
                min="1"
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
            </div>
            <div class="col-md-6">
              <label for="confirmPassword" class="form-label">Confirm Password</label>
              <div class="input-group">
                <input
                  :type="showPassword ? 'text' : 'password'"
                  id="confirmPassword"
                  v-model="confirmPassword"
                  class="form-control"
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
import { useRouter } from 'vue-router'
import { API_BASE_URL } from '@/config';

const router = useRouter()

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

// Form submission state
const isSubmitting = ref(false)
const error = ref('')

const togglePasswordVisibility = () => {
  showPassword.value = !showPassword.value
}

const validateForm = () => {
  if (!name.value || !age.value || !gender.value || !email.value || !password.value || !confirmPassword.value) {
    error.value = 'Please fill in all fields.'
    return false
  }
  if (password.value !== confirmPassword.value) {
    error.value = 'Passwords do not match.'
    return false
  }
  return true
}

const teamDescription = computed(() =>
  teams.value.find(t => t.key === team.value)?.description || '')

onMounted(async () => {
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

  const response = await fetch(`${API_BASE_URL}/signup`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      name: name.value,
      age: age.value,
      gender: gender.value,
      email: email.value,
      password: password.value,
      team: team.value,
      signup_key: signupPin.value
    })
  })

  try {
    if (!response.ok) {
      throw new Error('Signup failed')
    }

    const data = await response.json()

    localStorage.setItem('authToken', data.token) // Save token for authentication

    window.location.href = '/' // Redirect to home page with full refresh
  } catch (err) {
    const data = await response.json()

    console.error('Signup error:', err)
    error.value = data.message
  } finally {
    isSubmitting.value = false
  }
}
</script>
