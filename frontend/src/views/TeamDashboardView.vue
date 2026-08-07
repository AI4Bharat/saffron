<template>
  <component :is="dashboardComponent" v-if="dashboardComponent" />
  <div v-else-if="session.loading || !session.loaded" class="dispatch-state">
    <span class="spinner-border text-secondary"></span>
    <p class="text-muted mt-3 mb-0">Loading your dashboard…</p>
  </div>
  <div v-else class="dispatch-state">
    <i class="bi bi-shield-lock fs-1 text-muted d-block mb-3"></i>
    <h5 class="fw-bold">No dashboard here</h5>
    <p class="text-muted">
      There is no team called “{{ route.params.team }}” that you can administer.
    </p>
    <router-link to="/login" class="btn btn-outline-secondary rounded-pill px-4">
      Back to sign in
    </router-link>
  </div>
</template>

<script setup>
// One URL shape for every team's dashboard: /<team>/admin. The component is
// chosen by the team's workflow, so adding a team needs no new route.
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { session, loadIdentity } from '@/session'
import TrackingPageView from '@/views/TrackingPageView.vue'
import AsrDashboard from '@/views/AsrDashboard.vue'

const route = useRoute()

const WORKFLOW_DASHBOARDS = {
  classic: TrackingPageView,
  pool: AsrDashboard,
}

const team = computed(() => {
  const key = String(route.params.team || '').toLowerCase()
  return (session.teams || []).find(t => t.key === key)
    || (session.team && session.team.key === key ? session.team : null)
})

const dashboardComponent = computed(() =>
  team.value ? (WORKFLOW_DASHBOARDS[team.value.workflow] || TrackingPageView) : null)

onMounted(() => loadIdentity())
</script>

<style scoped>
.dispatch-state { min-height: 60vh; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; padding: 2rem; }
</style>
