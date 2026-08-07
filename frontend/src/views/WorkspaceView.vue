<template>
  <div class="ws-picker">
    <header class="picker-head">
      <div class="org-mark">
        <span class="org-glyph"><SaffronLogo :size="26" variant="white" /></span>
        <div>
          <div class="org-name">Saffron</div>
          <div class="org-tag">Annotation Studio</div>
        </div>
      </div>
      <h1>Welcome{{ session.name ? ', ' + session.name : '' }}</h1>
      <p v-if="session.teams.length > 1">
        You work with {{ session.teams.length }} teams. Choose the workspace you want to open —
        you can switch at any time from the top bar.
      </p>
      <p v-else-if="session.teams.length === 1">Opening your workspace…</p>
      <p v-else>You are not part of any team yet.</p>
    </header>

    <div v-if="session.teams.length" class="team-grid">
      <button v-for="t in session.teams" :key="t.key" class="team-card"
              :style="{ '--accent': t.accent || '#d8661b' }" @click="enter(t)">
        <span class="team-badge">{{ t.key.toUpperCase() }}</span>
        <h2>{{ t.name }}</h2>
        <p>{{ t.description }}</p>
        <div class="team-meta">
          <span class="tag">{{ t.workflow === 'pool' ? 'Pull-based pool' : 'Assigned batches' }}</span>
          <span v-if="t.languages?.length" class="tag">{{ t.languages.length }} language(s)</span>
        </div>
        <span class="enter">Open workspace <i class="bi bi-arrow-right"></i></span>
      </button>
    </div>

    <div v-else class="no-team">
      <i class="bi bi-people"></i>
      <p>No workspace has been assigned to your account yet. Please ask your team admin
         to add you to a team.</p>
      <button class="btn btn-outline-secondary btn-sm" @click="signOut">Sign out</button>
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import SaffronLogo from '@/components/SaffronLogo.vue'
import { useRouter } from 'vue-router'
import { session, loadIdentity, setActiveTeam, workspacePath, clearSession } from '@/session'

const router = useRouter()

function enter(team) {
  setActiveTeam(team.key)
  router.push(workspacePath(team))
}
function signOut() {
  clearSession()
  router.push('/login')
}

onMounted(async () => {
  await loadIdentity()
  if (session.role === 'admin') { router.replace('/tracking'); return }
  if (session.teams.length === 1) enter(session.teams[0])
})
</script>

<style scoped>
.ws-picker { max-width: 940px; margin: 0 auto; padding: 3rem 1rem; }
.picker-head { text-align: center; margin-bottom: 2.5rem; }
.org-mark { display: inline-flex; align-items: center; gap: .7rem; margin-bottom: 1.5rem; }
.org-glyph { width: 40px; height: 40px; border-radius: 11px; background: linear-gradient(135deg, #f4a93c, #d8661b); display: grid; place-items: center; }
.org-name { font-weight: 800; font-size: 1.05rem; color: #0f172a; text-align: left; }
.org-name span { color: #0d9488; }
.org-tag { font-size: .7rem; color: #94a3b8; letter-spacing: .06em; text-transform: uppercase; text-align: left; }
.picker-head h1 { font-size: 1.8rem; font-weight: 700; color: #0f172a; }
.picker-head p { color: #64748b; max-width: 560px; margin: .5rem auto 0; }

.team-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1.25rem; }
.team-card { position: relative; text-align: left; background: #fff; border: 1px solid #e2e8f0; border-radius: 18px; padding: 1.5rem; transition: transform .15s, box-shadow .15s, border-color .15s; }
.team-card:hover { transform: translateY(-3px); border-color: var(--accent); box-shadow: 0 14px 34px rgba(15,23,42,.1); }
.team-card::before { content: ''; position: absolute; inset: 0 0 auto 0; height: 4px; background: var(--accent); border-radius: 18px 18px 0 0; }
.team-badge { display: inline-block; font-size: .7rem; font-weight: 800; letter-spacing: .08em; color: var(--accent); background: color-mix(in srgb, var(--accent) 12%, white); border-radius: 6px; padding: .2rem .5rem; margin-bottom: .6rem; }
.team-card h2 { font-size: 1.15rem; font-weight: 700; color: #0f172a; margin-bottom: .4rem; }
.team-card p { color: #64748b; font-size: .87rem; line-height: 1.55; margin-bottom: .9rem; }
.team-meta { display: flex; gap: .4rem; flex-wrap: wrap; margin-bottom: 1rem; }
.tag { font-size: .72rem; background: #f1f5f9; color: #475569; border-radius: 999px; padding: .18rem .6rem; }
.enter { font-size: .85rem; font-weight: 600; color: var(--accent); }

.no-team { text-align: center; background: #fff; border: 1px solid #e2e8f0; border-radius: 16px; padding: 3rem; color: #64748b; }
.no-team i { font-size: 2.2rem; color: #cbd5e1; display: block; margin-bottom: .75rem; }
.no-team p { max-width: 420px; margin: 0 auto 1rem; }
</style>
