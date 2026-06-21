<template>
  <div class="dashboard-container py-4">
    <!-- Header with Auto Refresh control -->
    <div class="d-flex flex-wrap justify-content-between align-items-center mb-4 pb-3 border-bottom border-secondary-subtle">
      <div>
        <h1 class="h2 fw-bold text-dark mb-1">Admin Dashboard</h1>
        <p class="text-muted mb-0">Monitor translations, languages, and rater registrations in real-time.</p>
      </div>
      <div class="d-flex align-items-center gap-3 mt-3 mt-md-0">
        <!-- Auto refresh indicator -->
        <div class="d-flex align-items-center gap-2 bg-light px-3 py-2 rounded border shadow-sm">
          <div :class="['status-dot', isAutoRefreshActive ? 'active animate-pulse' : '']"></div>
          <span class="text-xs fw-medium text-secondary">
            {{ isAutoRefreshActive ? `Auto-refreshing in ${countdown}s` : 'Auto-refresh paused' }}
          </span>
          <button @click="toggleAutoRefresh" class="btn btn-sm btn-outline-secondary ms-2" title="Toggle Auto-Refresh">
            <i :class="['bi', isAutoRefreshActive ? 'bi-pause-fill' : 'bi-play-fill']"></i>
          </button>
        </div>
        <button @click="fetchDashboardData(true)" class="btn btn-primary d-flex align-items-center gap-2 shadow-sm" :disabled="isLoading">
          <i :class="['bi', isLoading ? 'bi-arrow-clockwise animate-spin' : 'bi-arrow-clockwise']"></i>
          <span>Refresh</span>
        </button>
      </div>
    </div>

    <!-- Error Alert -->
    <div v-if="error" class="alert alert-danger alert-dismissible fade show shadow-sm" role="alert">
      <i class="bi bi-exclamation-triangle-fill me-2"></i>
      {{ error }}
      <button type="button" class="btn-close" @click="error = null"></button>
    </div>

    <!-- Navigation Tabs -->
    <div class="tabs-nav mb-4 bg-white p-2 rounded shadow-sm border d-flex gap-2">
      <button 
        v-for="tab in ['overview', 'batches', 'raters']" 
        :key="tab"
        @click="activeTab = tab"
        :class="['tab-btn btn flex-fill py-2 fw-semibold text-capitalize', activeTab === tab ? 'btn-dark text-white' : 'btn-light text-secondary']"
      >
        <i :class="['bi me-2', tab === 'overview' ? 'bi-grid-1x2-fill' : tab === 'batches' ? 'bi-folder-fill' : 'bi-people-fill']"></i>
        {{ tab }}
      </button>
    </div>

    <!-- Tab Contents -->
    <div v-if="!isLoading || dashboardData.stats" class="tab-content">
      <!-- 1. OVERVIEW TAB -->
      <div v-if="activeTab === 'overview'" class="tab-pane-active">
        <!-- KPI Cards Grid -->
        <div class="row g-4 mb-4">
          <div class="col-12 col-sm-6 col-xl-3">
            <div class="kpi-card bg-white p-4 rounded shadow-sm border border-start border-4 border-primary">
              <div class="d-flex justify-content-between align-items-center mb-2">
                <span class="text-muted fw-medium text-uppercase text-xs">Total Registered Raters</span>
                <div class="kpi-icon-wrapper bg-primary-subtle text-primary">
                  <i class="bi bi-people-fill fs-5"></i>
                </div>
              </div>
              <h2 class="fw-bold text-dark mb-1">{{ stats.total_registered_users || 0 }}</h2>
              <div class="text-xs text-muted d-flex align-items-center gap-1">
                <span class="text-success fw-bold">{{ stats.active_users || 0 }} Active</span>
                <span>•</span>
                <span class="text-warning fw-bold">{{ stats.pending_registrations || 0 }} 0 Tasks Completed</span>
              </div>
            </div>
          </div>
          
          <div class="col-12 col-sm-6 col-xl-3">
            <div class="kpi-card bg-white p-4 rounded shadow-sm border border-start border-4 border-warning">
              <div class="d-flex justify-content-between align-items-center mb-2">
                <span class="text-muted fw-medium text-uppercase text-xs">0 Tasks Completed</span>
                <div class="kpi-icon-wrapper bg-warning-subtle text-warning">
                  <i class="bi bi-person-fill-exclamation fs-5 animate-pulse-slow"></i>
                </div>
              </div>
              <h2 class="fw-bold text-dark mb-1">{{ stats.pending_registrations || 0 }}</h2>
              <p class="text-xs text-muted mb-0">Registered but completed 0 tasks.</p>
            </div>
          </div>

          <div class="col-12 col-sm-6 col-xl-3">
            <div class="kpi-card bg-white p-4 rounded shadow-sm border border-start border-4 border-success">
              <div class="d-flex justify-content-between align-items-center mb-2">
                <span class="text-muted fw-medium text-uppercase text-xs">Task Completions</span>
                <div class="kpi-icon-wrapper bg-success-subtle text-success">
                  <i class="bi bi-check-circle-fill fs-5"></i>
                </div>
              </div>
              <h2 class="fw-bold text-dark mb-1">{{ stats.unique_tasks_completed || 0 }} <span class="text-muted fs-6">/ {{ stats.total_tasks || 0 }}</span></h2>
              <div class="progress mt-2" style="height: 6px;">
                <div class="progress-bar bg-success" role="progressbar" :style="{ width: globalProgressPercent + '%' }" :aria-valuenow="globalProgressPercent" aria-valuemin="0" aria-valuemax="100"></div>
              </div>
              <p class="text-xs text-muted mt-2 mb-0">Coverage: {{ globalProgressPercent }}% of unique tasks</p>
            </div>
          </div>

          <div class="col-12 col-sm-6 col-xl-3">
            <div class="kpi-card bg-white p-4 rounded shadow-sm border border-start border-4 border-info">
              <div class="d-flex justify-content-between align-items-center mb-2">
                <span class="text-muted fw-medium text-uppercase text-xs">Total Submissions</span>
                <div class="kpi-icon-wrapper bg-info-subtle text-info">
                  <i class="bi bi-collection-fill fs-5"></i>
                </div>
              </div>
              <h2 class="fw-bold text-dark mb-1">{{ stats.total_submissions || 0 }}</h2>
              <p class="text-xs text-muted mb-0">Total ratings submitted by all users.</p>
            </div>
          </div>
        </div>

        <!-- Language Breakdown section -->
        <h3 class="fw-bold text-dark mb-3">Languages Statistics</h3>
        <div class="row g-4 mb-4">
          <div v-for="lang in languages" :key="lang.language" class="col-12 col-md-6 col-lg-4">
            <div class="lang-card bg-white p-4 rounded shadow-sm border hover-lift">
              <div class="d-flex justify-content-between align-items-center mb-3">
                <h4 class="fw-bold text-dark m-0">{{ lang.language }}</h4>
                <span class="badge bg-light text-dark border">{{ lang.test_count }} {{ lang.test_count === 1 ? 'Batch' : 'Batches' }}</span>
              </div>
              
              <!-- Completion rate -->
              <div class="mb-3">
                <div class="d-flex justify-content-between text-xs mb-1">
                  <span class="text-muted">Completed Coverage</span>
                  <span class="fw-bold text-dark">{{ getPercent(lang.unique_completed_tasks, lang.total_tasks) }}%</span>
                </div>
                <div class="progress bg-light-gradient" style="height: 10px; border-radius: 5px;">
                  <div 
                    class="progress-bar progress-gradient" 
                    role="progressbar" 
                    :style="{ width: getPercent(lang.unique_completed_tasks, lang.total_tasks) + '%' }"
                  ></div>
                </div>
              </div>
              
              <!-- Metrics list -->
              <div class="d-flex justify-content-between text-xs text-muted pt-2 border-top">
                <div>
                  <span class="d-block fw-bold text-dark">{{ lang.unique_completed_tasks }} / {{ lang.total_tasks }}</span>
                  <span>Unique Tasks</span>
                </div>
                <div class="text-end">
                  <span class="d-block fw-bold text-dark">{{ lang.total_submissions }}</span>
                  <span>Total Submissions</span>
                </div>
              </div>
            </div>
          </div>
          <div v-if="languages.length === 0" class="col-12 text-center text-muted py-5 bg-white rounded border">
            No languages stats found.
          </div>
        </div>
      </div>

      <!-- 2. TEST BATCHES TAB -->
      <div v-if="activeTab === 'batches'">
        <div class="card shadow-sm border mb-4">
          <div class="card-header bg-white py-3 border-bottom-0">
            <div class="row g-3 align-items-center">
              <div class="col-12 col-md-6">
                <h3 class="fw-bold text-dark m-0">Test Batches Progress</h3>
              </div>
              <div class="col-12 col-md-3">
                <select v-model="batchLanguageFilter" class="form-select">
                  <option value="">All Languages</option>
                  <option v-for="lang in uniqueLanguages" :key="lang" :value="lang">{{ lang }}</option>
                </select>
              </div>
              <div class="col-12 col-md-3">
                <input 
                  v-model="batchSearchQuery" 
                  type="text" 
                  class="form-control" 
                  placeholder="Search batches by desc..." 
                />
              </div>
            </div>
          </div>
          
          <div class="table-responsive">
            <table class="table table-hover align-middle mb-0">
              <thead class="table-light">
                <tr>
                  <th class="ps-4" style="width: 80px;">ID</th>
                  <th>Description</th>
                  <th style="width: 150px;">Language</th>
                  <th style="width: 150px;">Test Type</th>
                  <th style="width: 250px;">Unique Completed / Total</th>
                  <th style="width: 140px;">Total Submissions</th>
                  <th style="width: 140px;">Task Link</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="test in filteredTests" :key="test.id">
                  <td class="ps-4 fw-bold text-secondary">#{{ test.id }}</td>
                  <td>
                    <div class="fw-semibold text-dark">{{ test.description }}</div>
                  </td>
                  <td>
                    <span class="badge rounded-pill bg-light text-dark border">{{ test.language }}</span>
                  </td>
                  <td>
                    <span class="text-secondary text-xs">{{ test.test_type }}</span>
                  </td>
                  <td>
                    <div class="d-flex align-items-center gap-2">
                      <div class="progress flex-grow-1" style="height: 8px;">
                        <div 
                          class="progress-bar bg-success" 
                          role="progressbar" 
                          :style="{ width: getPercent(test.unique_completed_tasks, test.total_tasks) + '%' }"
                        ></div>
                      </div>
                      <span class="text-xs fw-bold text-secondary" style="width: 80px; text-align: right;">
                        {{ test.unique_completed_tasks }}/{{ test.total_tasks }} ({{ getPercent(test.unique_completed_tasks, test.total_tasks) }}%)
                      </span>
                    </div>
                  </td>
                  <td>
                    <span class="fw-semibold text-dark">{{ test.total_submissions }}</span>
                  </td>
                  <td>
                    <div class="btn-group btn-group-sm" role="group">
                      <a :href="`/${test.id}`" target="_blank" rel="noopener"
                         class="btn btn-outline-primary" title="Open task in a new tab">
                        <i class="bi bi-box-arrow-up-right"></i>
                      </a>
                      <button type="button" class="btn btn-outline-secondary"
                              title="Copy task link" @click="copyTaskLink(test.id)">
                        <i class="bi bi-clipboard"></i>
                      </button>
                    </div>
                  </td>
                </tr>
                <tr v-if="filteredTests.length === 0">
                  <td colspan="7" class="text-center text-muted py-5 bg-white">
                    No matching test batches found.
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- 3. RATERS DIRECTORY TAB -->
      <div v-if="activeTab === 'raters'">
        <div class="card shadow-sm border">
          <div class="card-header bg-white py-3 border-bottom-0">
            <div class="row g-3 align-items-center">
              <div class="col-12 col-md-8">
                <h3 class="fw-bold text-dark m-0">Active Annotators</h3>
                <small class="text-muted">Showing annotators with at least one completed task.</small>
              </div>
              <div class="col-12 col-md-4">
                <input
                  v-model="raterSearchQuery"
                  type="text"
                  class="form-control"
                  placeholder="Search by name or email..."
                />
              </div>
            </div>
          </div>
          
          <div class="table-responsive">
            <table class="table table-hover align-middle mb-0">
              <thead class="table-light">
                <tr>
                  <th class="ps-4">Name</th>
                  <th>Email</th>
                  <th style="width: 120px;">Demographics</th>
                  <th style="width: 180px;">Tasks Completed</th>
                  <th style="width: 200px;">Last Active</th>
                  <th style="width: 200px;">Status</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="rater in filteredRaters" :key="rater.id">
                  <td class="ps-4">
                    <div class="d-flex align-items-center gap-2">
                      <div class="avatar-circle">{{ rater.name.charAt(0).toUpperCase() }}</div>
                      <div class="fw-semibold text-dark">{{ rater.name }}</div>
                    </div>
                  </td>
                  <td>
                    <span class="text-secondary">{{ rater.email }}</span>
                  </td>
                  <td>
                    <div class="text-xs">
                      <span class="text-dark">{{ rater.gender }}</span>, <span class="text-muted">{{ rater.age }} yrs</span>
                    </div>
                  </td>
                  <td>
                    <span class="badge bg-light text-dark border fs-6 px-3">{{ rater.completed_tasks_count }}</span>
                  </td>
                  <td>
                    <span v-if="rater.last_active" class="text-secondary text-xs">{{ formatDate(rater.last_active) }}</span>
                    <span v-else class="text-muted text-xs">—</span>
                  </td>
                  <td>
                    <span 
                      :class="['badge px-3 py-2 text-xs rounded-pill d-inline-flex align-items-center gap-1', 
                        rater.completed_tasks_count >= 1 ? 'bg-success-subtle text-success' : 'bg-warning-subtle text-warning animate-pulse-border']"
                    >
                      <i :class="['bi', rater.completed_tasks_count >= 1 ? 'bi-check-circle-fill' : 'bi-exclamation-triangle-fill']"></i>
                      {{ rater.status }}
                    </span>
                  </td>
                </tr>
                <tr v-if="filteredRaters.length === 0">
                  <td colspan="6" class="text-center text-muted py-5 bg-white">
                    No matching raters found.
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
    
    <!-- Skeleton loader -->
    <div v-else class="text-center py-5">
      <div class="spinner-border text-primary" role="status" style="width: 3rem; height: 3rem;">
        <span class="visually-hidden">Loading...</span>
      </div>
      <p class="text-muted mt-3">Fetching initial statistics, please wait...</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { API_BASE_URL } from '@/config'
import router from '@/router'

// State
const activeTab = ref('overview')
const dashboardData = ref({})
const isLoading = ref(true)
const error = ref(null)

// Filters & Search
const batchSearchQuery = ref('')
const batchLanguageFilter = ref('')
const raterSearchQuery = ref('')
const raterStatusFilter = ref('')

// Copy a batch's rater-facing task URL to the clipboard.
const copyTaskLink = async (id) => {
  const url = `${window.location.origin}/${id}`
  try {
    await navigator.clipboard.writeText(url)
  } catch (_) {
    const ta = document.createElement('textarea')
    ta.value = url; document.body.appendChild(ta); ta.select()
    try { document.execCommand('copy') } catch (e) { /* ignore */ }
    ta.remove()
  }
  const toast = document.createElement('div')
  toast.className = 'position-fixed bottom-0 start-50 translate-middle-x mb-4 bg-dark text-white py-2 px-4 rounded-pill shadow-lg'
  toast.style.zIndex = '1080'
  toast.innerHTML = `<i class="bi bi-clipboard-check text-warning me-2"></i> Link copied: ${url}`
  document.body.appendChild(toast)
  setTimeout(() => { toast.style.opacity = '0'; setTimeout(() => toast.remove(), 300) }, 2200)
}

// Auto-Refresh
const isAutoRefreshActive = ref(true)
const countdown = ref(10)
const refreshInterval = 10 // seconds
let countdownTimer = null
let autoRefreshTimer = null

// Fetch data
const fetchDashboardData = async (manual = false) => {
  if (manual) isLoading.value = true
  try {
    const token = localStorage.getItem('authToken')
    if (!token) {
      router.push('/login')
      return
    }
    
    const response = await fetch(`${API_BASE_URL}/admin/dashboard`, {
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
      throw new Error('Failed to fetch dashboard statistics.')
    }
    
    dashboardData.value = await response.json()
    error.value = null
  } catch (err) {
    console.error(err)
    error.value = 'Failed to load dashboard data. Please verify your connection or login status.'
  } finally {
    isLoading.value = false
    if (manual) {
      // Reset countdown on manual refresh
      countdown.value = refreshInterval
    }
  }
}

// Helpers
const getPercent = (completed, total) => {
  if (!total) return 0
  return Math.round((completed / total) * 100)
}

const formatDate = (isoString) => {
  if (!isoString) return ''
  const date = new Date(isoString)
  return date.toLocaleString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// Auto Refresh control
const toggleAutoRefresh = () => {
  isAutoRefreshActive.value = !isAutoRefreshActive.value
  if (isAutoRefreshActive.value) {
    startTimers()
  } else {
    clearTimers()
  }
}

const startTimers = () => {
  clearTimers()
  countdown.value = refreshInterval
  
  countdownTimer = setInterval(() => {
    if (countdown.value > 1) {
      countdown.value--
    } else {
      countdown.value = refreshInterval
    }
  }, 1000)
  
  autoRefreshTimer = setInterval(() => {
    fetchDashboardData(false)
  }, refreshInterval * 1000)
}

const clearTimers = () => {
  if (countdownTimer) clearInterval(countdownTimer)
  if (autoRefreshTimer) clearInterval(autoRefreshTimer)
}

// Reset page filters on search
watch(batchSearchQuery, () => {})
watch(raterSearchQuery, () => {})

// Computed stats properties
const stats = computed(() => dashboardData.value.stats || {})
const languages = computed(() => dashboardData.value.languages || [])
const tests = computed(() => dashboardData.value.tests || [])
const raters = computed(() => dashboardData.value.raters || [])

const globalProgressPercent = computed(() => {
  return getPercent(stats.value.unique_tasks_completed, stats.value.total_tasks)
})

// Languages filter list
const uniqueLanguages = computed(() => {
  const langs = tests.value.map(t => t.language)
  return [...new Set(langs)].sort()
})

// Filtered lists
const filteredTests = computed(() => {
  let list = tests.value
  
  if (batchLanguageFilter.value) {
    list = list.filter(t => t.language === batchLanguageFilter.value)
  }
  
  if (batchSearchQuery.value) {
    const q = batchSearchQuery.value.toLowerCase()
    list = list.filter(t => t.description.toLowerCase().includes(q) || String(t.id).includes(q))
  }
  
  return list
})

const filteredRaters = computed(() => {
  // Only annotators who have actually completed at least one task — the long tail
  // of auto-created / never-started accounts ("0 Tasks Completed") is just noise.
  let list = raters.value.filter(r => r.completed_tasks_count >= 1)

  if (raterSearchQuery.value) {
    const q = raterSearchQuery.value.toLowerCase()
    list = list.filter(r => r.name.toLowerCase().includes(q) || r.email.toLowerCase().includes(q))
  }

  return list
})

// Lifecycle
onMounted(() => {
  const token = localStorage.getItem('authToken')
  if (!token) {
    router.push('/login')
    return
  }
  
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    if (payload.username !== 'admin') {
      router.push('/')
      return
    }
  } catch (e) {
    router.push('/login')
    return
  }
  
  fetchDashboardData(true)
  if (isAutoRefreshActive.value) {
    startTimers()
  }
})

onUnmounted(() => {
  clearTimers()
})
</script>

<style scoped>
.dashboard-container {
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 20px;
}

/* Tab button customizations */
.tabs-nav {
  background-color: #f8f9fa;
}
.tab-btn {
  border-radius: 6px;
  transition: all 0.2s ease;
  font-size: 0.95rem;
}
.tab-btn:hover {
  transform: translateY(-1px);
}

/* KPI cards styling */
.kpi-card {
  height: 100%;
  border-radius: 12px;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.kpi-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 8px 20px rgba(0,0,0,0.08) !important;
}
.kpi-icon-wrapper {
  width: 42px;
  height: 42px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* Language card styling */
.lang-card {
  border-radius: 12px;
  border: 1px solid rgba(0,0,0,0.08);
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}
.lang-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 10px 25px rgba(0,0,0,0.08) !important;
  border-color: rgba(0,0,0,0.15);
}

/* Helper Text styles */
.text-xs {
  font-size: 0.825rem;
}
.text-uppercase {
  letter-spacing: 0.05em;
}

/* Modern Gradient Progress Bars */
.bg-light-gradient {
  background-color: #e9ecef;
}
.progress-gradient {
  background: linear-gradient(90deg, #d8661b, #fdba74);
  border-radius: 5px;
}

/* Animation utilities */
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
.animate-spin {
  animation: spin 1.2s linear infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
.animate-pulse {
  animation: pulse 1.5s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

@keyframes pulse-slow {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.08); }
}
.animate-pulse-slow {
  animation: pulse-slow 2s infinite ease-in-out;
}

@keyframes pulse-border {
  0%, 100% { box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.4); }
  50% { box-shadow: 0 0 0 4px rgba(245, 158, 11, 0); }
}
.animate-pulse-border {
  animation: pulse-border 2s infinite ease-in-out;
}

/* Avatar layout for raters list */
.avatar-circle {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background-color: #d8661b;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 0.9rem;
}

/* Status dots */
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #cbd5e1;
}
.status-dot.active {
  background-color: #22c55e;
}
</style>