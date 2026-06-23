<template>
  <div class="page-container py-5">
    <div class="container">
      
      <!-- Greeting Banner -->
      <div class="welcome-banner p-4 p-md-5 rounded-4 shadow-lg mb-5 text-white position-relative overflow-hidden">
        <div class="banner-gradient"></div>
        <div class="row align-items-center position-relative z-index-1">
          <div class="col-md-8">
            <h1 class="display-5 fw-bold mb-2">Welcome back, {{ displayUsername }}!</h1>
            <p class="lead opacity-85 mb-0">
              {{ isAdmin ? 'Admin mode: Monitor system and inspect tasks.' : 'Here is the list of translation and correction tasks assigned to you.' }}
            </p>
          </div>
          <div class="col-md-4 text-md-end mt-4 mt-md-0">
            <div class="banner-badge px-4 py-2 rounded-pill d-inline-block">
              <i class="bi bi-shield-check me-2" v-if="isAdmin"></i>
              <i class="bi bi-person-badge me-2" v-else></i>
              <span class="fw-semibold text-uppercase tracking-wider small">
                {{ isAdmin ? 'Administrator' : 'Annotator / Rater' }}
              </span>
            </div>
          </div>
        </div>

        <!-- Quick actions: overall progress + resume next task -->
        <div v-if="!isAdmin && tasks.length" class="banner-progress mt-4 pt-4 position-relative z-index-1">
          <div class="d-flex flex-column flex-md-row align-items-md-center gap-3">
            <router-link
              v-if="nextTask"
              :to="`/${nextTask.id}`"
              class="btn btn-continue fw-semibold px-4 py-2 rounded-pill shadow-sm d-inline-flex align-items-center gap-2 flex-shrink-0"
            >
              <i class="bi bi-play-circle-fill"></i>
              {{ nextTask.status === 'In Progress' ? 'Resume' : 'Start' }} Task #{{ nextTask.id }}
            </router-link>
            <span v-else class="all-done-pill fw-semibold px-4 py-2 rounded-pill d-inline-flex align-items-center gap-2 flex-shrink-0">
              <i class="bi bi-check2-circle"></i> All tasks completed
            </span>

            <div class="flex-grow-1 w-100">
              <div class="d-flex justify-content-between small fw-semibold mb-1">
                <span><i class="bi bi-graph-up-arrow me-1"></i>Overall progress</span>
                <span>{{ overallDone }} / {{ overallTotal }} items · {{ overallProgress }}%</span>
              </div>
              <div class="progress banner-progress-bar rounded-pill" style="height: 9px;">
                <div
                  class="progress-bar bg-white rounded-pill"
                  role="progressbar"
                  :style="{ width: overallProgress + '%' }"
                  :aria-valuenow="overallProgress"
                  aria-valuemin="0"
                  aria-valuemax="100"
                ></div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Admin Control Panel inside Home (for manual Test ID bypass & quick link) -->
      <div v-if="isAdmin" class="card border-0 shadow-sm rounded-4 mb-5 overflow-hidden">
        <div class="card-header bg-dark text-white py-3 border-0">
          <h5 class="mb-0 d-flex align-items-center gap-2">
            <i class="bi bi-sliders text-warning"></i>
            <span>Admin Quick Controls</span>
          </h5>
        </div>
        <div class="card-body p-4 bg-light-subtle">
          <div class="row g-4">
            <div class="col-lg-6 border-end-lg">
              <h6 class="fw-bold text-dark mb-2">Quick Navigation</h6>
              <p class="text-muted small">Go to the main tracking dashboard to manage annotator task assignments, batch coverage, and system-wide statistics.</p>
              <router-link to="/tracking" class="btn btn-primary d-inline-flex align-items-center gap-2 px-4 shadow-sm">
                <i class="bi bi-grid-1x2-fill"></i>
                <span>Open Admin Dashboard</span>
              </router-link>
            </div>
            <div class="col-lg-6">
              <h6 class="fw-bold text-dark mb-2">Direct Task Preview</h6>
              <p class="text-muted small">Enter any Test ID directly to inspect and preview the annotation flow as a rater.</p>
              <form @submit.prevent="handleManualSubmit" class="row g-2">
                <div class="col-md-8">
                  <div class="input-group">
                    <span class="input-group-text bg-white border-secondary-subtle text-muted">ID</span>
                    <input
                      type="text"
                      v-model="manualTestId"
                      class="form-control border-secondary-subtle shadow-none"
                      placeholder="e.g. 101"
                      required
                    />
                  </div>
                </div>
                <div class="col-md-4">
                  <button type="submit" class="btn btn-outline-dark w-100">
                    Inspect Task
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      </div>

      <!-- Main Annotator Dashboard Section -->
      <div v-if="!isAdmin">
        
        <!-- Stats Summary Grid -->
        <div class="row g-4 mb-5">
          <div class="col-6 col-md-3" v-for="stat in statsCards" :key="stat.title">
            <div class="stat-card p-4 rounded-4 shadow-sm bg-white border border-light-subtle hover-lift">
              <div class="d-flex justify-content-between align-items-center mb-2">
                <span class="text-muted fw-medium small text-uppercase">{{ stat.title }}</span>
                <div :class="['stat-icon px-2 py-1 rounded-3', stat.bgClass, stat.textClass]">
                  <i :class="stat.icon"></i>
                </div>
              </div>
              <h3 class="fw-bold mb-0 text-dark">{{ stat.value }}</h3>
            </div>
          </div>
        </div>

        <!-- Filter and Search Row -->
        <div class="row g-3 align-items-center justify-content-between mb-4">
          <div class="col-12 col-lg-5">
            <!-- Search field -->
            <div class="input-group search-bar border shadow-sm rounded-pill overflow-hidden bg-white">
              <span class="input-group-text border-0 bg-white text-muted px-3"><i class="bi bi-search"></i></span>
              <input
                type="text"
                v-model="searchQuery"
                class="form-control border-0 shadow-none py-2.5 fs-7 bg-white"
                placeholder="Search assigned tasks by description..."
              />
              <button v-if="searchQuery" @click="searchQuery = ''" class="btn border-0 bg-white text-muted pe-3">
                <i class="bi bi-x-lg"></i>
              </button>
            </div>
          </div>

          <div class="col-12 col-lg-7 d-flex flex-wrap gap-2 justify-content-lg-end">
            <!-- Language filter dropdown -->
            <select v-model="selectedLanguage" class="form-select filter-select shadow-sm border rounded-pill py-2 px-3 bg-white" style="width: auto; min-width: 150px;">
              <option value="">All Languages</option>
              <option v-for="lang in uniqueLanguages" :key="lang" :value="lang">{{ lang }}</option>
            </select>

            <!-- Status Tabs -->
            <div class="bg-white p-1 rounded-pill shadow-sm border d-flex gap-1">
              <button
                v-for="status in ['all', 'Not Started', 'In Progress', 'Completed']"
                :key="status"
                @click="selectedStatus = status"
                :class="['btn btn-sm rounded-pill px-3 py-1.5 fw-semibold text-capitalize', selectedStatus === status ? 'btn-dark text-white' : 'btn-light text-secondary border-0 bg-transparent']"
              >
                {{ status === 'all' ? 'All Tasks' : status }}
              </button>
            </div>

            <!-- Refresh button -->
            <button @click="loadTasks" class="btn btn-light shadow-sm rounded-pill px-3" :disabled="isLoading" title="Refresh task list">
              <i :class="['bi bi-arrow-clockwise', isLoading ? 'animate-spin' : '']"></i>
            </button>
          </div>
        </div>

        <!-- Task List Loading State -->
        <div v-if="isLoading" class="text-center py-5">
          <div class="spinner-border text-primary" role="status" style="width: 3rem; height: 3rem;">
            <span class="visually-hidden">Loading...</span>
          </div>
          <p class="text-muted mt-3 fw-medium">Loading your assigned tasks, please wait...</p>
        </div>

        <!-- Error Alert -->
        <div v-else-if="error" class="alert alert-danger p-4 rounded-4 shadow-sm border-0 d-flex align-items-start gap-3" role="alert">
          <i class="bi bi-exclamation-triangle-fill fs-3 text-danger"></i>
          <div class="flex-grow-1">
            <h5 class="fw-bold mb-1">Failed to load tasks</h5>
            <p class="mb-0 text-secondary">{{ error }}</p>
            <button @click="loadTasks" class="btn btn-outline-danger btn-sm mt-3 px-4 rounded-pill">Try Again</button>
          </div>
        </div>

        <!-- Empty State -->
        <div v-else-if="filteredTasks.length === 0" class="empty-state-card text-center p-5 rounded-4 shadow-sm bg-white border border-light-subtle">
          <div class="empty-illustration mb-4">
            <svg viewBox="0 0 120 120" width="100" height="100" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="60" cy="60" r="50" fill="#f8fafc" />
              <path d="M40 55 L55 70 L80 40" stroke="#cbd5e1" stroke-width="6" stroke-linecap="round" stroke-linejoin="round" />
              <circle cx="85" cy="85" r="15" fill="#f1f5f9" />
              <path d="M80 85 L90 85" stroke="#94a3b8" stroke-width="2" stroke-linecap="round" />
              <path d="M85 80 L85 90" stroke="#94a3b8" stroke-width="2" stroke-linecap="round" />
            </svg>
          </div>
          <h4 class="fw-bold text-dark mb-2">No Assigned Tasks Found</h4>
          <p class="text-muted max-w-sm mx-auto mb-4">
            {{ tasks.length === 0 ? 'You currently do not have any annotation or correction tasks assigned to your account.' : 'No tasks match your selected search query or filters.' }}
          </p>
          <div v-if="tasks.length === 0" class="alert alert-warning d-inline-block rounded-pill py-2 px-4 fs-7 mb-0">
            <i class="bi bi-info-circle-fill me-2"></i> Please contact your project administrator to assign tasks.
          </div>
          <button v-else @click="resetFilters" class="btn btn-dark rounded-pill px-4">Clear All Filters</button>
        </div>

        <!-- Task Cards Grid -->
        <div v-else class="row g-4">
          <div v-for="task in filteredTasks" :key="task.id" class="col-md-6 col-xl-4">
            <div class="task-card card h-100 border-0 shadow-sm rounded-4 overflow-hidden position-relative">
              <!-- Top color bar indicating status -->
              <div :class="['status-bar', getStatusClass(task.status)]"></div>

              <div class="card-body p-4 d-flex flex-column h-100">
                <!-- Header: Language & ID -->
                <div class="d-flex justify-content-between align-items-center mb-3">
                  <span :class="['badge rounded-pill px-3 py-1.5 fs-8 text-white shadow-sm', getLanguageBadgeClass(task.language)]">
                    {{ task.language }}
                  </span>
                  <span class="task-id fw-bold text-secondary text-uppercase fs-8">Task #{{ task.id }}</span>
                </div>

                <!-- Title & Description -->
                <h5 class="fw-bold text-dark mb-2 text-truncate-2" :title="task.description">
                  {{ task.description }}
                </h5>
                <p class="text-secondary small mb-4 flex-grow-1 text-truncate-3">
                  Type: <span class="fw-semibold text-dark text-capitalize">{{ formatTestType(task.test_type) }}</span>
                </p>

                <!-- Progress Section -->
                <div class="mb-4">
                  <div class="d-flex justify-content-between text-xs mb-1.5">
                    <span class="text-muted fw-medium">Completion Progress</span>
                    <span class="fw-bold text-dark">{{ task.completed_count }} / {{ task.total_count }} ({{ getProgressPercent(task) }}%)</span>
                  </div>
                  <div class="progress rounded-pill bg-light" style="height: 8px; overflow: hidden;">
                    <div
                      :class="['progress-bar rounded-pill progress-bar-striped progress-bar-animated', getProgressBarClass(task.status)]"
                      role="progressbar"
                      :style="{ width: getProgressPercent(task) + '%' }"
                      :aria-valuenow="getProgressPercent(task)"
                      aria-valuemin="0"
                      aria-valuemax="100"
                    ></div>
                  </div>
                </div>

                <!-- Footer / Action Button -->
                <div class="d-flex align-items-center justify-content-between pt-3 border-top mt-auto">
                  <span :class="['badge px-2.5 py-1.5 rounded-pill fs-9 fw-bold d-inline-flex align-items-center gap-1', getStatusBadgeStyle(task.status)]">
                    <i :class="['bi', getStatusIcon(task.status)]"></i>
                    {{ task.status }}
                  </span>
                  
                  <router-link :to="`/${task.id}`" :class="['btn btn-sm rounded-pill px-4 py-2 fw-semibold d-flex align-items-center gap-1.5 shadow-sm', getButtonClass(task.status)]">
                    <span>{{ getButtonText(task.status) }}</span>
                    <i class="bi bi-arrow-right-short fs-5 lh-1"></i>
                  </router-link>
                </div>
              </div>
            </div>
          </div>
        </div>

      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { API_BASE_URL } from '@/config'

const router = useRouter()

// Authentication & State
const displayUsername = ref('Annotator')
const isAdmin = ref(false)
const manualTestId = ref('')

const tasks = ref([])
const isLoading = ref(true)
const error = ref(null)

// Filtering & Search
const searchQuery = ref('')
const selectedLanguage = ref('')
const selectedStatus = ref('all')

// Decode token on mount
const loadUserFromToken = () => {
  const token = localStorage.getItem('authToken')
  if (token) {
    try {
      const payload = JSON.parse(atob(token.split('.')[1]))
      displayUsername.value = payload.username || 'Annotator'
      isAdmin.value = (payload.username === 'admin')
    } catch (e) {
      console.error('Error decoding token:', e)
    }
  }
}

// Fetch assigned tasks from the backend
const loadTasks = async () => {
  if (isAdmin.value) {
    isLoading.value = false
    return
  }

  isLoading.value = true
  error.value = null

  try {
    const token = localStorage.getItem('authToken')
    if (!token) {
      router.push('/login')
      return
    }

    const response = await fetch(`${API_BASE_URL}/rater/tasks`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    })

    if (response.status === 401) {
      localStorage.removeItem('authToken')
      router.push('/login')
      return
    }

    if (!response.ok) {
      throw new Error('Failed to load assigned tasks.')
    }

    const data = await response.json()
    tasks.value = data.tasks || []
  } catch (err) {
    console.error('Error fetching rater tasks:', err)
    error.value = 'We encountered an error loading your assigned tasks. Please verify your internet connection or login and try again.'
  } finally {
    isLoading.value = false
  }
}

// Actions
const handleManualSubmit = () => {
  if (manualTestId.value.trim()) {
    router.push(`/${manualTestId.value.trim()}`)
  }
}

const resetFilters = () => {
  searchQuery.value = ''
  selectedLanguage.value = ''
  selectedStatus.value = 'all'
}

// Helper computations
const uniqueLanguages = computed(() => {
  const list = tasks.value.map(t => t.language).filter(Boolean)
  return [...new Set(list)].sort()
})

const filteredTasks = computed(() => {
  return tasks.value.filter(task => {
    // 1. Search Query
    if (searchQuery.value) {
      const q = searchQuery.value.toLowerCase()
      const descMatch = (task.description || '').toLowerCase().includes(q)
      const typeMatch = (task.test_type || '').toLowerCase().includes(q)
      const idMatch = String(task.id).includes(q)
      if (!descMatch && !typeMatch && !idMatch) return false
    }

    // 2. Language Filter
    if (selectedLanguage.value && task.language !== selectedLanguage.value) {
      return false
    }

    // 3. Status Filter
    if (selectedStatus.value !== 'all' && task.status !== selectedStatus.value) {
      return false
    }

    return true
  })
})

const statsCards = computed(() => {
  const total = tasks.value.length
  const completed = tasks.value.filter(t => t.status === 'Completed').length
  const inProgress = tasks.value.filter(t => t.status === 'In Progress').length
  const notStarted = tasks.value.filter(t => t.status === 'Not Started').length

  return [
    { title: 'Total Assigned', value: total, icon: 'bi-collection-fill', bgClass: 'bg-primary-subtle', textClass: 'text-primary' },
    { title: 'Not Started', value: notStarted, icon: 'bi-circle', bgClass: 'bg-secondary-subtle', textClass: 'text-secondary' },
    { title: 'In Progress', value: inProgress, icon: 'bi-hourglass-split', bgClass: 'bg-warning-subtle', textClass: 'text-warning' },
    { title: 'Completed', value: completed, icon: 'bi-check-circle-fill', bgClass: 'bg-success-subtle', textClass: 'text-success' }
  ]
})

// Overall progress + resume-next-task (dashboard quick actions)
const overallTotal = computed(() => tasks.value.reduce((s, t) => s + (t.total_count || 0), 0))
const overallDone = computed(() => tasks.value.reduce((s, t) => s + (t.completed_count || 0), 0))
const overallProgress = computed(() =>
  overallTotal.value ? Math.round((overallDone.value / overallTotal.value) * 100) : 0
)
const nextTask = computed(() =>
  tasks.value.find(t => t.status === 'In Progress') ||
  tasks.value.find(t => t.status === 'Not Started') ||
  null
)

// Visual formatting helpers
const getProgressPercent = (task) => {
  if (!task.total_count) return 0
  return Math.round((task.completed_count / task.total_count) * 100)
}

const formatTestType = (type) => {
  if (!type) return ''
  return type.replace(/-/g, ' ')
}

const getLanguageBadgeClass = (lang) => {
  const l = (lang || '').toLowerCase()
  if (l === 'hindi') return 'bg-orange'
  if (l === 'english') return 'bg-navy'
  if (l === 'bengali') return 'bg-indigo'
  if (l === 'gujarati') return 'bg-teal'
  if (l === 'kannada') return 'bg-cyan'
  if (l === 'malayalam') return 'bg-emerald'
  if (l === 'marathi') return 'bg-pink'
  if (l === 'tamil') return 'bg-crimson'
  if (l === 'telugu') return 'bg-violet'
  if (l === 'urdu') return 'bg-purple'
  return 'bg-secondary'
}

const getStatusClass = (status) => {
  if (status === 'Completed') return 'status-completed'
  if (status === 'In Progress') return 'status-in-progress'
  return 'status-not-started'
}

const getStatusBadgeStyle = (status) => {
  if (status === 'Completed') return 'bg-success-subtle text-success border border-success-subtle'
  if (status === 'In Progress') return 'bg-warning-subtle text-warning-emphasis border border-warning-subtle'
  return 'bg-light text-muted border'
}

const getStatusIcon = (status) => {
  if (status === 'Completed') return 'bi-check-circle-fill'
  if (status === 'In Progress') return 'bi-hourglass-split'
  return 'bi-circle'
}

const getProgressBarClass = (status) => {
  if (status === 'Completed') return 'bg-success'
  if (status === 'In Progress') return 'bg-warning'
  return 'bg-secondary'
}

const getButtonClass = (status) => {
  if (status === 'Completed') return 'btn-outline-success'
  if (status === 'In Progress') return 'btn-warning text-dark'
  return 'btn-primary text-white'
}

const getButtonText = (status) => {
  if (status === 'Completed') return 'Review'
  if (status === 'In Progress') return 'Resume'
  return 'Start'
}

// Lifecycle
onMounted(() => {
  loadUserFromToken()
  loadTasks()
})
</script>

<style scoped>
.page-container {
  min-height: calc(100vh - 40px);
  background-color: #f8fafc;
}

/* Greeting Banner */
.welcome-banner {
  border-radius: 20px;
  background-color: #1e293b;
  position: relative;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.banner-gradient {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: linear-gradient(135deg, #d8661b 0%, #f4a93c 100%);
  opacity: 0.95;
  z-index: 0;
}

.z-index-1 {
  z-index: 1;
}

.opacity-85 {
  opacity: 0.85;
}

.banner-badge {
  background-color: rgba(255, 255, 255, 0.18);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.2);
  color: white;
}

.banner-progress {
  border-top: 1px solid rgba(255, 255, 255, 0.25);
}

.banner-progress-bar {
  background-color: rgba(255, 255, 255, 0.25) !important;
}

.btn-continue {
  background-color: #fff;
  color: #b4530f;
  border: none;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.btn-continue:hover {
  color: #8a3f0d;
  transform: translateY(-1px);
  box-shadow: 0 8px 18px rgba(0, 0, 0, 0.18);
}

.all-done-pill {
  background-color: rgba(255, 255, 255, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.35);
  color: #fff;
}

.tracking-wider {
  letter-spacing: 0.08em;
}

/* Stat Cards */
.stat-card {
  border-radius: 16px;
  transition: all 0.25s ease;
}

.hover-lift:hover {
  transform: translateY(-4px);
  box-shadow: 0 10px 20px rgba(0, 0, 0, 0.05) !important;
}

.stat-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
}

/* Custom HSL-like and vibrant background colors for language badges */
.bg-orange { background-color: #e27c3e !important; }
.bg-navy { background-color: #1e3a8a !important; }
.bg-indigo { background-color: #4f46e5 !important; }
.bg-teal { background-color: #0d9488 !important; }
.bg-cyan { background-color: #0891b2 !important; }
.bg-emerald { background-color: #059669 !important; }
.bg-pink { background-color: #db2777 !important; }
.bg-crimson { background-color: #be123c !important; }
.bg-violet { background-color: #7c3aed !important; }
.bg-purple { background-color: #9333ea !important; }

/* Filter Controls */
.filter-select {
  border-color: #e2e8f0;
  color: #475569;
  font-weight: 500;
  outline: none;
}

.search-bar {
  border-color: #e2e8f0;
}

.search-bar input::placeholder {
  color: #94a3b8;
}

/* Task Cards */
.task-card {
  background-color: white;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  border: 1px solid rgba(0, 0, 0, 0.03) !important;
}

.task-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 12px 25px rgba(0, 0, 0, 0.08) !important;
}

.status-bar {
  height: 6px;
  width: 100%;
}

.status-completed {
  background: linear-gradient(90deg, #10b981, #34d399);
}

.status-in-progress {
  background: linear-gradient(90deg, #f59e0b, #fbbf24);
}

.status-not-started {
  background: linear-gradient(90deg, #94a3b8, #cbd5e1);
}

.task-id {
  letter-spacing: 0.05em;
  color: #94a3b8;
}

.text-truncate-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
  min-height: 48px;
}

.text-truncate-3 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
}

.text-xs {
  font-size: 0.8rem;
}

.fs-7 {
  font-size: 0.9rem;
}

.fs-8 {
  font-size: 0.8rem;
}

.fs-9 {
  font-size: 0.72rem;
}

.text-warning-emphasis {
  color: #854d0e !important;
}

/* Empty State Card */
.empty-state-card {
  border: 2px dashed #e2e8f0 !important;
  background-color: white;
  max-width: 600px;
  margin: 0 auto;
}

.max-w-sm {
  max-width: 420px;
}

.animate-spin {
  animation: spin 1.2s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@media (min-width: 992px) {
  .border-end-lg {
    border-end: 0;
    border-right: 1px solid #e2e8f0;
  }
}
</style>
