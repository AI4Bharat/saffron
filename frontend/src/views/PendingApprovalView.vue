<template>
  <div class="pending-page d-flex align-items-center justify-content-center min-vh-100 bg-light">
    <div class="card border-0 shadow-sm rounded-4 p-4 text-center" style="max-width: 460px">
      <div class="mx-auto mb-3">
        <SaffronLogo />
      </div>
      <h4 class="fw-bold text-dark mb-2">Your account is ready — almost there</h4>
      <p class="text-muted mb-1">
        A team admin now needs to approve you into their team.
        Ask your coordinator to approve <b>{{ session.name || 'your account' }}</b> from the dashboard.
      </p>
      <p class="text-muted small mb-4">Once approved, your workspace appears here automatically.</p>

      <div class="d-flex justify-content-center gap-2">
        <button class="btn btn-saffron px-4" :disabled="checking" @click="checkAgain">
          <span v-if="checking" class="spinner-border spinner-border-sm me-2"></span>
          {{ checking ? 'Checking…' : 'Check again' }}
        </button>
        <button class="btn btn-outline-secondary" @click="logout">Log out</button>
      </div>
      <p v-if="stillWaiting" class="text-muted small mt-3 mb-0">
        Not approved yet — you're still in the queue.
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import SaffronLogo from '@/components/SaffronLogo.vue'
import { session, loadIdentity, landingPath, clearSession } from '@/session'

const router = useRouter()
const checking = ref(false)
const stillWaiting = ref(false)
let pollTimer = null

async function checkAgain(silent = false) {
  checking.value = !silent && true
  try {
    await loadIdentity(true)
    if (session.teams?.length) {
      router.push(landingPath())
      return
    }
    if (!silent) stillWaiting.value = true
  } catch { /* stay on the page; the button can retry */ } finally {
    checking.value = false
  }
}

function logout() {
  clearSession()
  router.push('/login')
}

onMounted(() => {
  checkAgain(true)
  // Quiet poll so approval kicks in without the annotator doing anything.
  pollTimer = setInterval(() => checkAgain(true), 20000)
})
onUnmounted(() => clearInterval(pollTimer))
</script>

<style scoped>
.btn-saffron {
  background: #f59e0b;
  color: #fff;
  font-weight: 600;
}
.btn-saffron:hover { background: #d97706; color: #fff; }
</style>
