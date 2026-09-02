<template>
  <div class="org-page">
    <header class="org-head">
      <div>
        <div class="eyebrow">Organisation overview</div>
        <h1>Teams</h1>
        <p>Every team on the platform. Open a team to work inside its dashboard.</p>
      </div>
      <div class="org-totals" v-if="data.totals">
        <div><strong>{{ data.totals.teams }}</strong><span>teams</span></div>
        <div><strong>{{ data.totals.annotators }}</strong><span>annotators</span></div>
        <div><strong>{{ data.totals.multi_team_annotators }}</strong><span>in 2+ teams</span></div>
        <div><strong>{{ data.totals.admins }}</strong><span>admins</span></div>
      </div>
    </header>

    <div v-if="loading" class="text-center py-5"><span class="spinner-border text-secondary"></span></div>

    <div v-else class="team-grid">
      <div v-for="t in data.teams" :key="t.key" class="team-card" :style="{ '--accent': t.accent }">
        <div class="tc-head">
          <span class="tc-badge">{{ t.key.toUpperCase() }}</span>
          <h2>{{ t.name }}</h2>
        </div>
        <p class="tc-desc">{{ t.description }}</p>

        <div class="tc-stats">
          <div><span>Annotators</span><strong>{{ t.annotators }}</strong></div>
          <div v-if="t.workflow === 'classic'"><span>Batches</span><strong>{{ t.batches }}</strong></div>
          <div v-if="t.pool"><span>Pool items</span><strong>{{ t.pool.total.toLocaleString() }}</strong></div>
          <div v-if="t.pool"><span>Done</span><strong>{{ t.pool.done.toLocaleString() }}</strong></div>
        </div>

        <div v-if="t.pool" class="tc-progress">
          <div class="progress"><div class="progress-bar" :style="{ width: t.pool.progress + '%' }"></div></div>
          <small>{{ t.pool.progress }}% complete</small>
        </div>

        <div class="tc-actions">
          <router-link class="btn btn-sm btn-primary" :to="dashFor(t)">
            <i class="bi bi-speedometer2 me-1"></i>Open dashboard
          </router-link>
          <span class="tc-flow">{{ t.workflow === 'pool' ? 'pull-based pool' : 'assigned batches' }}</span>
        </div>
      </div>
    </div>

    <section class="admins-panel" v-if="!loading">
      <div class="ap-head">
        <h2>Admin accounts</h2>
        <button class="btn btn-sm btn-outline-primary" @click="openNew">
          <i class="bi bi-person-badge me-1"></i>New admin
        </button>
      </div>
      <table class="table table-sm align-middle">
        <thead><tr><th>Username</th><th>Name</th><th>Scope</th><th>Team</th><th>Last sign-in</th><th></th></tr></thead>
        <tbody>
          <tr v-for="a in admins" :key="a.id">
            <td class="fw-semibold">{{ a.username }}</td>
            <td>{{ a.display_name }}</td>
            <td><span class="pill" :class="a.scope">{{ a.scope === 'org' ? 'organisation' : 'team' }}</span></td>
            <td>{{ a.team?.name || '— all teams —' }}</td>
            <td class="muted">{{ a.last_login ? new Date(a.last_login).toLocaleString('en-IN') : 'never' }}</td>
            <td><button class="btn btn-sm btn-outline-secondary" @click="openReset(a)">Reset password</button></td>
          </tr>
        </tbody>
      </table>
    </section>

    <!-- Annotators who used "Forgot password?" on the sign-in page. -->
    <section class="admins-panel" v-if="!loading">
      <PasswordResetPanel />
    </section>

    <!-- new / reset admin -->
    <div v-if="modal" class="modal-backdrop-x" @click.self="modal = null">
      <div class="modal-card">
        <div class="modal-head">
          <h3>{{ modal.mode === 'new' ? 'Create an admin' : `Reset ${modal.username}'s password` }}</h3>
          <button class="btn-close" @click="modal = null"></button>
        </div>
        <div class="modal-body-x">
          <template v-if="modal.mode === 'new'">
            <label class="form-label">Username</label>
            <input v-model="modal.username" class="form-control mb-3" placeholder="e.g. asr_lead">
            <label class="form-label">Display name</label>
            <input v-model="modal.display_name" class="form-control mb-3">
            <label class="form-label">Team</label>
            <select v-model="modal.team" class="form-select mb-3">
              <option value="">Organisation admin (all teams)</option>
              <option v-for="t in data.teams" :key="t.key" :value="t.key">{{ t.name }}</option>
            </select>
          </template>
          <label class="form-label">Password</label>
          <input v-model="modal.password" type="text" class="form-control" placeholder="at least 6 characters">
          <p v-if="modalError" class="text-danger small mt-2 mb-0">{{ modalError }}</p>
        </div>
        <div class="modal-foot">
          <button class="btn btn-outline-secondary" @click="modal = null">Cancel</button>
          <button class="btn btn-primary" :disabled="saving" @click="saveModal">
            <span v-if="saving" class="spinner-border spinner-border-sm me-1"></span>Save
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api, dashboardPath, setActiveTeam } from '@/session'
import PasswordResetPanel from '@/components/PasswordResetPanel.vue'

const loading = ref(true)
const data = ref({ teams: [], totals: null })
const admins = ref([])
const modal = ref(null)
const modalError = ref('')
const saving = ref(false)

function dashFor(team) {
  setActiveTeam(team.key)
  return dashboardPath(team)
}

async function load() {
  loading.value = true
  try {
    data.value = await api('/admin/org/overview')
    const a = await api('/admin/admins')
    admins.value = a.admins || []
  } finally {
    loading.value = false
  }
}

function openNew() {
  modalError.value = ''
  modal.value = { mode: 'new', username: '', display_name: '', team: '', password: '' }
}
function openReset(a) {
  modalError.value = ''
  modal.value = { mode: 'reset', id: a.id, username: a.username, password: '' }
}

async function saveModal() {
  saving.value = true
  modalError.value = ''
  try {
    if (modal.value.mode === 'new') {
      await api('/admin/admins', { method: 'POST', body: JSON.stringify(modal.value) })
    } else {
      await api(`/admin/admins/${modal.value.id}`, {
        method: 'PUT', body: JSON.stringify({ password: modal.value.password }),
      })
    }
    modal.value = null
    await load()
  } catch (e) {
    modalError.value = e.message
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.org-page { max-width: 1200px; margin: 0 auto; padding: 1.5rem 1rem 3rem; }
.org-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 1.5rem; flex-wrap: wrap; margin-bottom: 1.75rem; }
.eyebrow { font-size: .74rem; letter-spacing: .09em; text-transform: uppercase; color: #94a3b8; font-weight: 700; }
.org-head h1 { font-size: 1.7rem; font-weight: 800; color: #0f172a; margin: .2rem 0; }
.org-head p { color: #64748b; margin: 0; }
.org-totals { display: flex; gap: 1.75rem; }
.org-totals div { text-align: center; }
.org-totals strong { display: block; font-size: 1.4rem; color: #0f172a; }
.org-totals span { font-size: .72rem; color: #94a3b8; text-transform: uppercase; letter-spacing: .05em; }

.team-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1.25rem; }
.team-card { background: #fff; border: 1px solid #e2e8f0; border-radius: 18px; padding: 1.4rem; border-top: 4px solid var(--accent, #d8661b); }
.tc-head { display: flex; align-items: center; gap: .6rem; }
.tc-badge { font-size: .68rem; font-weight: 800; letter-spacing: .08em; color: var(--accent); background: color-mix(in srgb, var(--accent) 12%, white); border-radius: 6px; padding: .2rem .5rem; }
.tc-head h2 { font-size: 1.1rem; font-weight: 700; color: #0f172a; margin: 0; }
.tc-desc { color: #64748b; font-size: .86rem; margin: .6rem 0 1rem; }
.tc-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(90px, 1fr)); gap: .5rem; margin-bottom: .9rem; }
.tc-stats div { background: #f8fafc; border-radius: 10px; padding: .5rem .65rem; }
.tc-stats span { display: block; font-size: .68rem; color: #94a3b8; text-transform: uppercase; letter-spacing: .04em; font-weight: 700; }
.tc-stats strong { font-size: 1.05rem; color: #0f172a; }
.tc-progress { margin-bottom: 1rem; }
.tc-progress .progress { height: 7px; }
.tc-progress .progress-bar { background: var(--accent); }
.tc-progress small { color: #94a3b8; font-size: .75rem; }
.tc-actions { display: flex; align-items: center; justify-content: space-between; }
.tc-flow { font-size: .72rem; color: #94a3b8; }

.admins-panel { background: #fff; border: 1px solid #e2e8f0; border-radius: 16px; padding: 1.25rem; margin-top: 1.5rem; }
.ap-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: .75rem; }
.ap-head h2 { font-size: 1rem; font-weight: 700; color: #0f172a; margin: 0; }
.pill { font-size: .7rem; font-weight: 700; border-radius: 999px; padding: .12rem .55rem; }
.pill.org { background: #ede9fe; color: #6d28d9; }
.pill.team { background: #f1f5f9; color: #475569; }
.muted { color: #94a3b8; font-size: .82rem; }

.modal-backdrop-x { position: fixed; inset: 0; background: rgba(15,23,42,.45); display: grid; place-items: center; z-index: 1080; padding: 1rem; }
.modal-card { background: #fff; border-radius: 16px; width: 100%; max-width: 460px; box-shadow: 0 20px 50px rgba(0,0,0,.25); }
.modal-head { display: flex; justify-content: space-between; align-items: center; padding: 1rem 1.25rem; border-bottom: 1px solid #e2e8f0; }
.modal-head h3 { margin: 0; font-size: 1.02rem; font-weight: 700; }
.modal-body-x { padding: 1.25rem; }
.modal-foot { display: flex; gap: .5rem; justify-content: flex-end; padding: 1rem 1.25rem; border-top: 1px solid #e2e8f0; }
.form-label { font-size: .78rem; font-weight: 700; text-transform: uppercase; letter-spacing: .05em; color: #475569; }
</style>
