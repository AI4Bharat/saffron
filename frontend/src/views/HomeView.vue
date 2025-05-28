<template>
  <div class="container py-4 d-flex justify-content-center align-items-center">
    <div class="card form-card shadow-lg">
      <div class="card-body">
        <h1 class="card-title text-center mb-4">Enter Test ID</h1>
        <form @submit.prevent="handleSubmit">
          <!-- Input field -->
          <div class="mb-4">
            <input
              type="text"
              id="testId"
              class="form-control form-control-lg input-box"
              v-model="testId"
              placeholder="Enter your Test ID here"
              required
            />
          </div>
          <!-- Submit button -->
          <button type="submit" class="btn btn-primary btn-lg w-100">
            Submit
          </button>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const testId = ref('')

const handleSubmit = () => {
  if (testId.value.trim()) {
    router.push(`/${testId.value.trim()}`)
  } else {
    alert('Please enter a valid test ID.')
  }
}
</script>

<style scoped>
/* Center the card in the viewport */
.container {
  min-height: 10vh;
  background-color: #f8f9fa;
}

.form-card {
  width: 100%;
  max-width: 500px;
  padding: 30px;
  border-radius: 10px;
  background: #ffffff;
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.1);
}

/* Input box styling */
.input-box {
  border-radius: 5px;
  border: 1px solid #ced4da;
  padding: 10px 15px;
  font-size: 18px;
  background: #f8f9fa;
  transition: box-shadow 0.3s ease;
}

.input-box:focus {
  outline: none;
  border-color: #1976d2;
  box-shadow: 0 0 10px rgba(25, 118, 210, 0.3);
}

/* Button styling */
.btn-primary {
  background-color: #1976d2;
  border: none;
  border-radius: 5px;
  font-size: 18px;
}

.btn-primary:hover {
  background-color: #125ca4;
}
</style>
