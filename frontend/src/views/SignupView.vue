<template>
  <div class="signup-container">
    <h2 class="text-center mb-4">Signup</h2>
    <form @submit.prevent="handleSubmit">
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
      <div class="mb-3">
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
      <div class="mb-3">
        <label for="gender" class="form-label">Gender</label>
        <select id="gender" v-model="gender" class="form-control" required>
          <option value="" disabled>Select Gender</option>
          <option value="Male">Male</option>
          <option value="Female">Female</option>
          <option value="Other">Other</option>
        </select>
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
      <div class="mb-3">
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
            class="btn btn-outline-secondary"
            @click="togglePasswordVisibility"
          >
            {{ showPassword ? 'Hide' : 'Show' }}
          </button>
        </div>
      </div>
      <div class="mb-3">
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
            class="btn btn-outline-secondary"
            @click="togglePasswordVisibility"
          >
            {{ showPassword ? 'Hide' : 'Show' }}
          </button>
        </div>
      </div>
      <div class="mb-3 form-check">
        <input type="checkbox" class="form-check-input" id="acceptTerms" v-model="acceptTerms">
        <label class="form-check-label" for="acceptTerms">
          I consent to all the tests
        </label>
      </div>
      <button type="submit" class="btn btn-primary w-100" :disabled="isSubmitting || !acceptTerms">
        <span v-if="isSubmitting" class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
        {{ isSubmitting ? 'Signing up...' : 'Signup' }}
      </button>
    </form>

    <div v-if="error" class="alert alert-danger mt-3" role="alert">
      {{ error }}
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { API_BASE_URL } from '@/config';

// Form fields
const name = ref('')
const age = ref('')
const gender = ref('')
const email = ref('')
const password = ref('')
const confirmPassword = ref('')
const showPassword = ref(false)
const acceptTerms = ref(false)

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
  if (!acceptTerms.value) {
    error.value = 'You must accept the terms and conditions.'
    return false
  }
  return true
}

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
      password: password.value
    })
  })

  try {
    if (!response.ok) {
      throw new Error('Signup failed')
    }

    const data = await response.json()

    localStorage.setItem('authToken', data.token) // Save token for authentication

    router.push('/') // Redirect to home page
  } catch (err) {
    const data = await response.json()

    console.error('Signup error:', err)
    error.value = data.message
  } finally {
    isSubmitting.value = false
  }
}
</script>

<style scoped>
.signup-container {
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
