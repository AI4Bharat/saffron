<template>
  <div class="reset-wrap">
    <div class="reset-card">
      <div class="text-center mb-3">
        <SaffronLogo />
      </div>

      <!-- while we find out whether the link is still good -->
      <div v-if="checking" class="text-center text-muted py-4">
        <span class="spinner-border spinner-border-sm me-2"></span>Checking your link...
      </div>

      <!-- a link that is wrong, used, or past its time -->
      <div v-else-if="!valid" class="text-center py-2">
        <i class="bi bi-x-circle-fill text-danger fs-1"></i>
        <h5 class="fw-bold mt-3 mb-2">This link cannot be used</h5>
        <p class="text-muted small mb-3">{{ invalidMessage }}</p>
        <router-link to="/login" class="btn btn-saffron btn-sm px-4">Back to sign in</router-link>
      </div>

      <!-- done -->
      <div v-else-if="done" class="text-center py-2">
        <i class="bi bi-check-circle-fill text-success fs-1"></i>
        <h5 class="fw-bold mt-3 mb-2">Password changed</h5>
        <p class="text-muted small mb-3">You can sign in with your new password now.</p>
        <router-link to="/login" class="btn btn-saffron btn-sm px-4">Go to sign in</router-link>
      </div>

      <!-- the form -->
      <template v-else>
        <h5 class="fw-bold text-center mb-1">Set a new password</h5>
        <p class="text-muted small text-center mb-4">
          for <strong>{{ name }}</strong>
        </p>

        <form @submit.prevent="submit">
          <label class="form-label small fw-semibold" for="pw1">New password</label>
          <div class="input-group mb-3">
            <input :type="show ? 'text' : 'password'" id="pw1" v-model="password"
                   class="form-control" autocomplete="new-password" :disabled="busy">
            <button class="btn btn-outline-secondary" type="button" @click="show = !show"
                    :aria-label="show ? 'Hide password' : 'Show password'">
              <i :class="show ? 'bi bi-eye-slash' : 'bi bi-eye'"></i>
            </button>
          </div>

          <label class="form-label small fw-semibold" for="pw2">Confirm password</label>
          <input :type="show ? 'text' : 'password'" id="pw2" v-model="confirm"
                 class="form-control mb-3" autocomplete="new-password" :disabled="busy">

          <p v-if="hint" class="small text-danger mb-2">{{ hint }}</p>

          <button class="btn btn-saffron w-100" type="submit" :disabled="busy || !canSubmit">
            <span v-if="busy" class="spinner-border spinner-border-sm me-2"></span>
            {{ busy ? 'Saving...' : 'Set password' }}
          </button>
        </form>

        <p class="text-muted text-center small mt-3 mb-0">
          This link works once, and expires shortly after it was sent to you.
        </p>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import SaffronLogo from '@/components/SaffronLogo.vue'
import { API_BASE_URL } from '@/config'

const route = useRoute()
const token = String(route.query.token || '')

const checking = ref(true)
const valid = ref(false)
const invalidMessage = ref('')
const name = ref('')

const password = ref('')
const confirm = ref('')
const show = ref(false)
const busy = ref(false)
const done = ref(false)
const hint = ref('')

const MIN = 6
const canSubmit = computed(() =>
  password.value.length >= MIN && password.value === confirm.value)

onMounted(async () => {
  if (!token) {
    checking.value = false
    invalidMessage.value = 'The link is missing its code. Please use the full link your admin sent you.'
    return
  }
  try {
    const r = await fetch(`${API_BASE_URL}/password_reset/check?token=${encodeURIComponent(token)}`)
    const d = await r.json()
    valid.value = !!d.valid
    name.value = d.name || ''
    invalidMessage.value = d.message || 'Please ask your admin for a new link.'
  } catch (e) {
    invalidMessage.value = 'Could not reach the server. Please try again in a moment.'
  } finally {
    checking.value = false
  }
})

async function submit() {
  hint.value = ''
  if (password.value.length < MIN) {
    hint.value = `Please use at least ${MIN} characters.`
    return
  }
  if (password.value !== confirm.value) {
    hint.value = 'The two passwords do not match.'
    return
  }
  busy.value = true
  try {
    const r = await fetch(`${API_BASE_URL}/password_reset/complete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token, password: password.value }),
    })
    const d = await r.json().catch(() => ({}))
    if (!r.ok) {
      // A link can go stale between opening the page and submitting it.
      hint.value = d.message || 'Could not set the password.'
      if (r.status === 400 && /expired|used|invalid/i.test(d.message || '')) {
        valid.value = false
        invalidMessage.value = d.message
      }
      return
    }
    done.value = true
  } catch (e) {
    hint.value = 'Could not reach the server. Please try again.'
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.reset-wrap {
  min-height: 100vh; display: flex; align-items: center; justify-content: center;
  background: #f6f7f9; padding: 1.5rem;
}
.reset-card {
  background: #fff; border: 1px solid #e9ecef; border-radius: .9rem;
  box-shadow: 0 .5rem 1.5rem rgba(0,0,0,.06);
  padding: 2rem; width: 100%; max-width: 25rem;
}
</style>
