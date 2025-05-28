<template>
    <div class="container d-flex flex-column justify-content-center align-items-center vh-10">
      <!-- Success Message -->
      <div class="text-center">
        <h1 class="display-4 text-success mb-4">Good Job!</h1>
        <p class="lead text-muted">You have successfully completed the test. Thank you for your effort!</p>
      </div>

      <!-- Finish Button -->
      <button
        class="btn btn-lg btn-primary mt-4"
        @click="goToHome"
      >
        Finish
      </button>
    </div>
  </template>

  <script setup>
  import { useRouter } from 'vue-router'

  const router = useRouter()

  // Navigation Method
  const goToHome = () => {
    router.push('/')
  }
  </script>

  <style scoped>
  /* Full-screen container */
  .container {
    background: #f8f9fa;
    border-radius: 10px;
    padding: 2rem;
    text-align: center;
    box-shadow: 0px 4px 10px rgba(0, 0, 0, 0.1);
  }

  /* Success Message Styling */
  h1 {
    font-weight: bold;
  }

  p {
    font-size: 1.25rem;
  }
  </style>
