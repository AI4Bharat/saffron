<template>
  <div class="container-fluid py-4 page-bg">
    <div class="row">
      <!-- Tasks Sidebar -->
      <div class="col-lg-4 col-md-5 mb-4">
        <div class="card border-0 shadow-sm sidebar-card">
          <div class="card-header bg-dark text-white py-3 border-0 rounded-top-4">
            <h5 class="mb-0 d-flex align-items-center justify-content-between">
              <span class="d-flex align-items-center">
                <i class="bi bi-grid-fill me-2 text-warning"></i>
                Task Explorer
              </span>
              <span class="badge bg-warning text-dark fs-8 px-2 py-1 rounded-pill">
                {{ completedCount }}/{{ testData.length }} Done
              </span>
            </h5>
          </div>
          
          <div class="card-body p-3">
            <!-- Search bar -->
            <div class="input-group mb-3 search-box">
              <span class="input-group-text bg-light border-0 text-muted"><i class="bi bi-search"></i></span>
              <input
                type="text"
                v-model="searchQuery"
                class="form-control bg-light border-0 shadow-none fs-7"
                placeholder="Search tasks..."
              />
              <button 
                v-if="searchQuery" 
                class="btn btn-light border-0 text-muted" 
                @click="searchQuery = ''"
              >
                <i class="bi bi-x-lg"></i>
              </button>
            </div>

            <!-- Task List -->
            <div class="task-list-wrapper">
              <div
                v-for="task in filteredTasks"
                :key="task.id"
                class="task-item-card p-3 mb-2 rounded-3 cursor-pointer transition-all border d-flex align-items-center justify-content-between"
                :class="{
                  'active-task': currentIndex === task.originalIndex,
                  'completed-task': task.completion_status === 'completed',
                  'skipped-task': task.completion_status === 'skipped',
                  'saved-task': task.completion_status === 'saved',
                  'pending-task': task.completion_status !== 'completed' && task.completion_status !== 'skipped' && task.completion_status !== 'saved'
                }"
                @click="jumpToTask(task.originalIndex)"
              >
                <div class="d-flex align-items-center text-truncate pe-2">
                  <!-- Custom Indicator Dot/Icon -->
                  <div class="status-dot-container me-2">
                    <span v-if="task.completion_status === 'completed'" class="status-indicator bg-success shadow-sm">
                      <i class="bi bi-check text-white"></i>
                    </span>
                    <span v-else-if="task.completion_status === 'skipped'" class="status-indicator bg-skipped-indicator shadow-sm text-white">
                      <i class="bi bi-arrow-right"></i>
                    </span>
                    <span v-else-if="task.completion_status === 'saved'" class="status-indicator bg-warning shadow-sm text-dark">
                      <i class="bi bi-bookmark-fill"></i>
                    </span>
                    <span v-else class="status-indicator bg-secondary-subtle border text-muted">
                      {{ task.originalIndex + 1 }}
                    </span>
                  </div>
                  
                  <div class="text-truncate flex-grow-1">
                    <div class="task-title fw-semibold text-truncate text-dark">
                      Task #{{ task.originalIndex + 1 }}
                    </div>
                    <div class="task-id-line text-truncate">
                      <i class="bi bi-hash"></i>ID: {{ task.id }}
                    </div>
                    <span class="task-desc text-muted d-block text-truncate">
                      {{ task.slug || task.pre_scene || task.description || 'No description' }}
                    </span>
                  </div>
                </div>
                
                <span 
                  v-if="task.completion_status === 'completed'" 
                  class="badge bg-success-subtle text-success border border-success-subtle rounded-pill fs-9 py-1 px-2"
                >
                  Done
                </span>
                <span 
                  v-else-if="task.completion_status === 'skipped'" 
                  class="badge bg-skipped-badge text-skipped border border-skipped-border rounded-pill fs-9 py-1 px-2"
                >
                  Skipped
                </span>
                <span 
                  v-else-if="task.completion_status === 'saved'" 
                  class="badge bg-warning-subtle text-warning-emphasis border border-warning-subtle rounded-pill fs-9 py-1 px-2 fw-bold"
                >
                  Saved
                </span>
                <span 
                  v-else 
                  class="badge bg-light text-muted border rounded-pill fs-9 py-1 px-2"
                >
                  Open
                </span>
              </div>
              
              <div v-if="filteredTasks.length === 0" class="text-center text-muted py-5">
                <i class="bi bi-inbox fs-3 d-block mb-2"></i>
                No matching tasks found
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Main Workspace -->
      <div class="col-lg-8 col-md-7">
        <!-- Progress Card -->
        <div class="card border-0 shadow-sm mb-4 rounded-4">
          <div class="card-body p-3">
            <div class="d-flex align-items-center justify-content-between mb-2">
              <span class="fw-semibold text-secondary small">Overall Annotation Progress</span>
              <span class="fw-bold text-primary small">{{ progress }}% Completed</span>
            </div>
            <div class="progress rounded-pill overflow-hidden" style="height: 10px;">
              <div
                class="progress-bar progress-bar-striped progress-bar-animated bg-primary"
                role="progressbar"
                :style="{ width: `${progress}%` }"
                :aria-valuenow="progress"
                aria-valuemin="0"
                aria-valuemax="100"
              ></div>
            </div>
          </div>
        </div>

        <!-- All Completed Info Banner -->
        <div v-if="progress === 100" class="alert alert-success shadow-sm mb-4 rounded-4 d-flex align-items-center justify-content-between p-3" role="alert">
          <div class="d-flex align-items-center">
            <i class="bi bi-check-circle-fill me-2 fs-4 text-success"></i>
            <div>
              <strong class="d-block text-success-emphasis">All tasks completed!</strong>
              <span class="fs-8 text-secondary">You can review and edit any task by selecting it from the explorer sidebar.</span>
            </div>
          </div>
          <button @click="router.push('/')" class="btn btn-sm btn-success rounded-pill px-3 py-1.5 fw-semibold flex-shrink-0">
            <i class="bi bi-house-door-fill me-1"></i> Go to Home
          </button>
        </div>

        <!-- Error Message -->
        <div v-if="error" class="alert alert-danger shadow-sm mb-4 rounded-3 d-flex align-items-center" role="alert">
          <i class="bi bi-exclamation-triangle-fill me-2 fs-5"></i>
          <div>{{ error }}</div>
        </div>

        <!-- Dynamic Test Component -->
        <div class="main-component-container">
          <component
            v-if="currentTest"
            :is="currentTestComponent"
            :current-test="currentTest"
            :can-proceed="true"
            :is-last-test="isLast"
            :test_id="test_id"
            :test-type="data?.test_type"
            :currentIndex="currentIndex"
            @next="handleNext"
            @prev="handlePrev"
            @submit-status="updateTaskStatus"
          />
        </div>

        <!-- Page Number / Navigation Assist Footer -->
        <div class="page-number-footer mt-4 text-center text-muted small">
          Viewing Task {{ currentIndex + 1 }} of {{ testData.length }} (ID: {{ currentTest?.id }})
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { API_BASE_URL } from '@/config';
import TranslationCorrection from '@/components/TranslationCorrection.vue'
import SentenceCorrection from '@/components/SentenceCorrection.vue'
import ConversationEvaluation from '@/components/ConversationEvaluation.vue'
import AudioSegmentation from '@/components/AudioSegmentation.vue'

const router = useRouter()
const route = useRoute()

// State
const data = ref(null)
const testData = ref([])
const currentIndex = ref(0)
const test_id = ref(null)
const error = ref(null)
const searchQuery = ref('')

// Computed
const progress = computed(() => {
  if (!testData.value.length) return 0
  const completed = testData.value.filter(t => t.completion_status === 'completed').length
  return Math.round((completed / testData.value.length) * 100)
})

const completedCount = computed(() => {
  return testData.value.filter(t => t.completion_status === 'completed').length
})

const currentTest = computed(() => {
  return testData.value[currentIndex.value]
})

const isLast = computed(() => {
  return currentIndex.value === testData.value.length - 1
})

const filteredTasks = computed(() => {
  return testData.value.map((task, originalIndex) => ({
    ...task,
    originalIndex
  })).filter(task => {
    const term = searchQuery.value.toLowerCase()
    const matchSlug = (task.slug || '').toLowerCase().includes(term)
    const matchId = String(task.id || '').toLowerCase().includes(term)
    const matchScene = (task.pre_scene || task.description || '').toLowerCase().includes(term)
    return matchSlug || matchId || matchScene
  })
})

const currentTestComponent = computed(() => {
  if (!data.value?.test_type) return null

  const testComponents = {
    'translation-correction': TranslationCorrection,
    'sentence-correction': SentenceCorrection,
    'conversation-evaluation': ConversationEvaluation,
    'conversation-editable': ConversationEvaluation,
    'audio-segmentation': AudioSegmentation,
  }

  return testComponents[data.value.test_type]
})

// Methods
const jumpToTask = (index) => {
  if (index >= 0 && index < testData.value.length) {
    currentIndex.value = index
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }
}

const handlePrev = () => {
  if (currentIndex.value > 0) {
    currentIndex.value--
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }
}

const updateTaskStatus = ({ index, status, results }) => {
  if (testData.value[index]) {
    testData.value[index].completion_status = status
    if (results) {
      if ('pre_scene' in results) {
        testData.value[index].pre_scene = results.pre_scene
      }
      if ('post_scene' in results) {
        testData.value[index].post_scene = results.post_scene
      }
      
      const dialogueKey = 'dialogue' in testData.value[index] ? 'dialogue' : ('turns' in testData.value[index] ? 'turns' : 'conversation')
      if (dialogueKey in results && Array.isArray(results[dialogueKey])) {
        const origTurns = testData.value[index][dialogueKey]
        const ratedTurns = results[dialogueKey]
        for (let i = 0; i < origTurns.length; i++) {
          if (i < ratedTurns.length) {
            Object.assign(origTurns[i], ratedTurns[i])
          }
        }
      }
    }
  }
}

const handleNext = async () => {
  if (isLast.value) {
    try {
      const token = localStorage.getItem('authToken')
      const response = await fetch(`${API_BASE_URL}/verify_test/${test_id.value}`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.status === 200) {
        showCompletionToast();
      } else {
        // Find next incomplete task and jump to it
        const nextIncompleteIdx = testData.value.findIndex((t, idx) => 
          t.completion_status !== 'completed' && t.completion_status !== 'skipped'
        )
        if (nextIncompleteIdx !== -1) {
          currentIndex.value = nextIncompleteIdx
        } else {
          showCompletionToast();
        }
      }
    } catch (err) {
      console.error('Error verifying test completion:', err);
      error.value = 'Failed to verify completion. Please submit again.'
    }
  } else {
    currentIndex.value++;
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }
}

const showCompletionToast = () => {
  const toast = document.createElement('div')
  toast.className = 'position-fixed bottom-0 start-50 translate-middle-x mb-4 bg-dark text-white py-2.5 px-4 rounded-pill shadow-lg z-3 border border-success'
  toast.style.transition = 'opacity 0.3s ease'
  toast.innerHTML = '<i class="bi bi-check-circle-fill text-success me-2"></i> All tasks completed successfully!'
  document.body.appendChild(toast)
  setTimeout(() => {
    toast.style.opacity = '0'
    setTimeout(() => toast.remove(), 300)
  }, 3500)
}

// Lifecycle hooks
onMounted(async () => {
  try {
    const token = localStorage.getItem('authToken')
    const response = await fetch(`${API_BASE_URL}/test/${route.params.id}`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    })
    if (!response.ok) {
      throw new Error('Failed to fetch test data.')
    }
    const responseData = await response.json()
    data.value = responseData
    currentIndex.value = Number(responseData.page_no) || 0
    testData.value = responseData.json_entry || []
    test_id.value = responseData.test_id

    // If initial index is out of bounds, check if completed and redirect
    if (currentIndex.value >= testData.value.length) {
      const nextIncompleteIdx = testData.value.findIndex((t, idx) => 
        t.completion_status !== 'completed' && t.completion_status !== 'skipped'
      )
      if (nextIncompleteIdx !== -1) {
        currentIndex.value = nextIncompleteIdx
      } else {
        currentIndex.value = testData.value.length - 1
      }
    }
  } catch (err) {
    console.error('Error fetching test data:', err)
    error.value = 'Unable to load test data. Please try again later.'
  }
})
</script>

<style scoped>
.page-bg {
  min-height: calc(100vh - 56px);
  background-color: #f8fafc;
}

.sidebar-card {
  border-radius: 16px;
  background-color: #ffffff;
  position: sticky;
  top: 12px;
}

.search-box {
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid #e2e8f0;
}

.search-box input {
  font-size: 0.9rem;
}

.task-list-wrapper {
  max-height: calc(100vh - 96px);
  overflow-y: auto;
  padding-right: 4px;
}

/* Custom scrollbars */
.task-list-wrapper::-webkit-scrollbar {
  width: 6px;
}
.task-list-wrapper::-webkit-scrollbar-track {
  background: transparent;
}
.task-list-wrapper::-webkit-scrollbar-thumb {
  background-color: #cbd5e1;
  border-radius: 10px;
}

/* Task Cards style */
.task-item-card {
  border-color: #f1f5f9;
  background-color: #f8fafc;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  user-select: none;
}

.task-item-card:hover {
  background-color: #f1f5f9;
  border-color: #cbd5e1;
  transform: translateX(4px);
}

.status-dot-container {
  display: flex;
  align-items: center;
  justify-content: center;
}

.status-indicator {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.95rem;
  font-weight: 700;
  flex-shrink: 0;
}

.status-indicator i {
  font-size: 1.15rem;
}

/* Task item text — bigger & always shows number + ID */
.task-title {
  font-size: 0.98rem;
  line-height: 1.3;
}

.task-id-line {
  font-size: 0.8rem;
  font-weight: 600;
  color: #d8661b;
  display: flex;
  align-items: center;
  gap: 1px;
  margin-top: 1px;
}

.task-id-line i {
  font-size: 0.9rem;
}

.task-desc {
  font-size: 0.8rem;
  margin-top: 2px;
}

/* Task Status Highlighting */
.completed-task {
  background-color: #f0fdf4 !important; /* Soft green */
  border-color: #bbf7d0 !important;
  border-left: 5px solid #10b981 !important;
}

.completed-task:hover {
  background-color: #dcfce7 !important;
}

.skipped-task {
  background-color: #fffbeb !important; /* Soft orange */
  border-color: #fde68a !important;
  border-left: 5px solid #f59e0b !important;
}

.skipped-task:hover {
  background-color: #fef3c7 !important;
}

.active-task {
  border-color: #d8661b !important;
  box-shadow: 0 4px 12px rgba(216, 102, 27, 0.15) !important;
  transform: scale(1.02) translateX(4px) !important;
}

.active-task.completed-task {
  background-color: #e6fcf5 !important;
}

.active-task.skipped-task {
  background-color: #fffbeb !important;
}

.active-task.pending-task {
  background-color: #fceee3 !important;
  color: #8a3f0d;
}

.saved-task {
  background-color: #fffbeb !important; /* Soft yellow/amber background */
  border-color: #fde68a !important;
  border-left: 5px solid #f59e0b !important;
}

.saved-task:hover {
  background-color: #fef3c7 !important;
}

.active-task.saved-task {
  background-color: #fef3c7 !important;
}

.skipped-task {
  background-color: #faf5ff !important; /* Soft purple background */
  border-color: #e9d5ff !important;
  border-left: 5px solid #a855f7 !important;
}

.skipped-task:hover {
  background-color: #f3e8ff !important;
}

.active-task.skipped-task {
  background-color: #f3e8ff !important;
}

.bg-skipped-indicator {
  background-color: #a855f7 !important;
}

.bg-skipped-badge {
  background-color: #faf5ff !important;
}

.text-skipped {
  color: #7e22ce !important;
}

.border-skipped-border {
  border-color: #e9d5ff !important;
}

.fs-8 {
  font-size: 0.8rem;
}

.fs-9 {
  font-size: 0.72rem;
}

.cursor-pointer {
  cursor: pointer;
}

.transition-all {
  transition: all 0.2s ease;
}
</style>
