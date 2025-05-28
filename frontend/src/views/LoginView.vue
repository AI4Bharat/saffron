<template>
  <div class="login-container">
    <h2 class="text-center mb-4">Login</h2>
    <form @submit.prevent="handleSubmit">
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
            class="btn btn-outline-secondary"
            @click="togglePasswordVisibility"
          >
            {{ showPassword ? 'Hide' : 'Show' }}
          </button>
        </div>
      </div>
      <div class="mb-3 form-check">
        <input type="checkbox" class="form-check-input" id="rememberMe" v-model="rememberMe">
        <label class="form-check-label" for="rememberMe">Remember me</label>
      </div>
      <button type="submit" class="btn btn-primary w-100" :disabled="isSubmitting">
        <span v-if="isSubmitting" class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
        {{ isSubmitting ? 'Logging in...' : 'Login' }}
      </button>
    </form>

    <div v-if="error" class="alert alert-danger mt-3" role="alert">
      {{ error }}
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { API_BASE_URL } from '@/config';

const router = useRouter()

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

    router.push('/')  // Redirect to home page
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
    router.push('/')  // Redirect to home if already logged in
  }
})
</script>

<style scoped>
.login-container {
  max-width: 400px;
  margin: 2rem auto;
  padding: 2rem;
  border: 1px solid #ddd;
  border-radius: 8px;
  background-color: #f8f9fa;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.btn-primary {
  background-color: #007bff;
  border-color: #007bff;
}

.btn-primary:hover {
  background-color: #0056b3;
  border-color: #0056b3;
}

.input-group .btn {
  z-index: 0;
}
</style>
