<template>
  <div class="admin-auth">
    <div class="auth-shell">
      <aside class="auth-side">
        <div class="org-mark">
          <span class="org-glyph"><SaffronLogo :size="26" variant="white" /></span>
          <div>
            <div class="org-name">Saffron</div>
            <div class="org-tag">Annotation Studio</div>
          </div>
        </div>
        <h1>Team administration</h1>
        <p>Sign in with your team's admin credentials. Each team sees only its own
           tasks, annotators and statistics.</p>
        <ul v-if="teams.length" class="team-hints">
          <li v-for="t in teams" :key="t.key">
            <span class="tdot" :style="{ background: t.accent || '#94a3b8' }"></span>
            <strong>{{ t.name }}</strong>
            <em v-if="t.description">{{ t.description }}</em>
          </li>
        </ul>
        <div class="side-foot">An organisation admin can switch between all teams after signing in.</div>
      </aside>

      <section class="auth-main">
        <h2>Admin sign in</h2>
        <p class="lead">Use your admin username — not an annotator account.</p>

        <form @submit.prevent="submit">
          <label class="form-label">Admin username</label>
          <input v-model="username" class="form-control mb-3" autocomplete="username"
                 placeholder="Your admin username" required>

          <label class="form-label">Password</label>
          <div class="input-group mb-3">
            <input :type="show ? 'text' : 'password'" v-model="password" class="form-control"
                   autocomplete="current-password" required>
            <button class="btn btn-outline-secondary" type="button" @click="show = !show">
              <i :class="show ? 'bi bi-eye-slash' : 'bi bi-eye'"></i>
            </button>
          </div>

          <button class="btn btn-dark w-100 btn-signin" :disabled="busy">
            <span v-if="busy" class="spinner-border spinner-border-sm me-2"></span>
            {{ busy ? 'Signing in…' : 'Sign in to dashboard' }}
          </button>
        </form>

        <div v-if="error" class="alert alert-danger mt-3 mb-0 py-2">
          <i class="bi bi-exclamation-circle-fill me-2"></i>{{ error }}
        </div>

        <p class="switch">
          Are you an annotator? <router-link to="/login">Sign in here</router-link>
        </p>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import SaffronLogo from '@/components/SaffronLogo.vue'
import { useRouter } from 'vue-router'
import { API_BASE_URL } from '@/config'
import { loadIdentity, landingPath, setActiveTeam } from '@/session'

const router = useRouter()
const username = ref('')
const password = ref('')
const show = ref(false)
const busy = ref(false)
const error = ref('')
const teams = ref([])

onMounted(async () => {
  // The side panel lists whatever teams the platform actually has.
  try {
    const res = await fetch(`${API_BASE_URL}/teams`)
    if (res.ok) teams.value = (await res.json()).teams || []
  } catch { /* the hints are decorative; sign-in works without them */ }
})

async function submit() {
  busy.value = true
  error.value = ''
  try {
    const res = await fetch(`${API_BASE_URL}/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: username.value.trim(), password: password.value }),
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.message || 'Invalid credentials')
    if (data.role !== 'admin') {
      throw new Error('That is an annotator account. Please use the annotator sign-in page.')
    }
    localStorage.setItem('authToken', data.token)
    if (data.team) setActiveTeam(data.team.key)
    const identity = await loadIdentity(true)
    router.push(landingPath(identity))
  } catch (e) {
    error.value = e.message
    password.value = ''
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.admin-auth { min-height: 100vh; background: #0f172a; display: grid; place-items: center; padding: 1.5rem; }
.auth-shell { display: grid; grid-template-columns: 1.05fr 1fr; max-width: 940px; width: 100%; background: #fff; border-radius: 20px; overflow: hidden; box-shadow: 0 30px 70px rgba(0,0,0,.4); }
@media (max-width: 820px) { .auth-shell { grid-template-columns: 1fr; } .auth-side { display: none; } }

.auth-side { background: linear-gradient(160deg, #1e293b, #0f172a); color: #e2e8f0; padding: 2.5rem 2rem; display: flex; flex-direction: column; }
.org-mark { display: flex; align-items: center; gap: .7rem; margin-bottom: 2rem; }
.org-glyph { width: 40px; height: 40px; border-radius: 11px; background: linear-gradient(135deg, #f4a93c, #d8661b); display: grid; place-items: center; }
.org-name { font-weight: 800; font-size: 1.05rem; letter-spacing: -.02em; }
.org-name span { color: #f4a93c; }
.org-tag { font-size: .72rem; color: #94a3b8; letter-spacing: .06em; text-transform: uppercase; }
.auth-side h1 { font-size: 1.5rem; font-weight: 700; margin-bottom: .6rem; }
.auth-side p { color: #94a3b8; font-size: .9rem; line-height: 1.6; }
.team-hints { list-style: none; padding: 0; margin: 1.5rem 0 0; }
.team-hints li { display: flex; align-items: center; gap: .5rem; padding: .55rem 0; border-bottom: 1px solid rgba(255,255,255,.07); font-size: .85rem; }
.team-hints em { color: #64748b; font-style: normal; font-size: .78rem; margin-left: auto; }
.tdot { width: 9px; height: 9px; border-radius: 50%; }
.tdot.tts { background: #d8661b; } .tdot.asr { background: #0f766e; }
.side-foot { margin-top: auto; padding-top: 1.5rem; font-size: .76rem; color: #64748b; }

.auth-main { padding: 3rem 2.5rem; display: flex; flex-direction: column; justify-content: center; }
.auth-main h2 { font-size: 1.45rem; font-weight: 700; color: #0f172a; margin-bottom: .25rem; }
.lead { color: #94a3b8; font-size: .88rem; margin-bottom: 1.75rem; }
.form-label { font-size: .78rem; font-weight: 700; text-transform: uppercase; letter-spacing: .05em; color: #475569; }
.form-control { border-radius: 9px; padding: .6rem .8rem; }
.btn-signin { border-radius: 9px; padding: .7rem; font-weight: 600; background: #d8661b; border-color: #d8661b; }
.switch { margin: 1.5rem 0 0; font-size: .85rem; color: #94a3b8; text-align: center; }
</style>
