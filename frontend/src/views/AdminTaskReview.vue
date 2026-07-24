<template>
  <div class="container-fluid py-4 review-bg">
    <!-- Header -->
    <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
      <div class="d-flex align-items-center gap-3">
        <button class="btn btn-outline-secondary rounded-pill px-3" @click="goBack">
          <i class="bi bi-arrow-left me-1"></i> Back
        </button>
        <div>
          <h4 class="fw-bold text-dark mb-0">
            <i class="bi bi-clipboard-check text-primary me-2"></i>
            {{ data ? data.description : 'Loading…' }}
          </h4>
          <div v-if="data" class="d-flex flex-wrap gap-2 mt-1">
            <span class="badge bg-dark-subtle text-dark border rounded-pill">#{{ data.test_id }}</span>
            <span class="badge bg-primary-subtle text-primary border rounded-pill">{{ formatType(data.test_type) }}</span>
            <span class="badge bg-secondary-subtle text-secondary border rounded-pill">{{ data.total_items }} items</span>
            <span class="badge bg-info-subtle text-info-emphasis border rounded-pill">{{ (data.annotators || []).length }} annotator(s)</span>
          </div>
        </div>
      </div>
      <!-- Open a fresh, editable blank task in a new tab -->
      <a v-if="data" :href="`/${data.test_id}`" target="_blank" rel="noopener"
         class="btn btn-outline-primary rounded-pill px-3" title="Open a fresh empty annotation page in a new tab">
        <i class="bi bi-box-arrow-up-right me-1"></i> Open fresh empty page
      </a>
    </div>

    <!-- Loading / error -->
    <div v-if="loading" class="text-center text-muted py-5">
      <div class="spinner-border text-primary mb-2"></div>
      <div>Loading annotations…</div>
    </div>
    <div v-else-if="error" class="alert alert-danger rounded-4">
      <i class="bi bi-exclamation-triangle-fill me-2"></i>{{ error }}
    </div>

    <template v-else-if="data">
      <!-- Tab bar: one tab per annotator, plus a "Blank task" tab -->
      <div class="d-flex flex-wrap gap-1 p-2 mb-3 bg-white rounded-4 border shadow-sm annotator-tabs">
        <button
          v-for="(a, i) in data.annotators"
          :key="a.rater_id"
          type="button"
          @click="selectTab(i)"
          :class="['tab-btn btn btn-sm fw-semibold d-flex align-items-center gap-2', activeTab === i ? 'btn-dark text-white' : 'btn-light text-secondary']"
        >
          <i class="bi bi-person-circle"></i>
          <span>{{ a.name }}</span>
          <span class="badge rounded-pill" :class="activeTab === i ? 'bg-white text-dark' : 'bg-secondary-subtle text-secondary'">
            {{ a.counts.completed + a.counts.skipped }}
          </span>
        </button>
        <button
          type="button"
          @click="selectTab(-1)"
          :class="['tab-btn btn btn-sm fw-semibold d-flex align-items-center gap-2', activeTab === -1 ? 'btn-dark text-white' : 'btn-light text-secondary']"
          title="Preview the empty task"
        >
          <i class="bi bi-file-earmark"></i> Blank task
        </button>
      </div>

      <!-- Annotator summary strip -->
      <div v-if="currentAnnotator" class="d-flex flex-wrap align-items-center gap-2 mb-3">
        <span class="text-muted small me-2"><i class="bi bi-envelope me-1"></i>{{ currentAnnotator.email || '—' }}</span>
        <span class="stat-pill"><span class="lbl">Completed</span><span class="val text-success">{{ currentAnnotator.counts.completed }}</span></span>
        <span v-if="currentAnnotator.counts.skipped" class="stat-pill"><span class="lbl">Skipped</span><span class="val text-purple">{{ currentAnnotator.counts.skipped }}</span></span>
        <span v-if="hasVerdict" class="stat-pill"><span class="lbl">Accepted</span><span class="val text-success">{{ currentAnnotator.counts.accepted }}</span></span>
        <span v-if="hasVerdict" class="stat-pill"><span class="lbl">Rejected</span><span class="val text-danger">{{ currentAnnotator.counts.rejected }}</span></span>
      </div>

      <!-- Task workspace: sidebar (item list) + the real task UI in read-only mode -->
      <div class="row">
        <div class="col-lg-4 col-md-5 mb-3">
          <div class="card border-0 shadow-sm sidebar-card">
            <div class="card-header bg-dark text-white py-2 border-0 rounded-top-4 d-flex align-items-center justify-content-between">
              <span class="fw-semibold"><i class="bi bi-grid-fill me-2 text-warning"></i>Items</span>
              <span class="badge bg-warning text-dark rounded-pill">{{ doneCount }}/{{ testData.length }}</span>
            </div>
            <div class="card-body p-2">
              <input v-model="search" type="text" class="form-control form-control-sm bg-light border-0 mb-2" placeholder="Search item id…" />
              <div class="task-list-wrapper">
                <div
                  v-for="task in filteredTasks"
                  :key="task.id"
                  class="task-item p-2 mb-1 rounded-3 cursor-pointer d-flex align-items-center justify-content-between"
                  :class="{ 'active-task': currentIndex === task.originalIndex, 'done-task': isDone(task) }"
                  @click="currentIndex = task.originalIndex"
                >
                  <div class="text-truncate pe-2">
                    <div class="fw-semibold text-truncate small">{{ task.originalIndex + 1 }}. {{ task.id }}</div>
                  </div>
                  <span v-if="task.completion_status === 'completed'" class="badge bg-success-subtle text-success border rounded-pill">Done</span>
                  <span v-else-if="task.completion_status === 'skipped'" class="badge bg-purple-subtle text-purple border rounded-pill">Skip</span>
                  <span v-else class="badge bg-light text-muted border rounded-pill">—</span>
                </div>
                <div v-if="!filteredTasks.length" class="text-center text-muted small py-4">No items.</div>
              </div>
            </div>
          </div>
        </div>

        <div class="col-lg-8 col-md-7">
          <component
            v-if="currentTest"
            :is="currentComponent"
            :key="`${activeTab}-${currentIndex}`"
            :current-test="currentTest"
            :is-last-test="currentIndex === testData.length - 1"
            :test_id="data.test_id"
            :test-type="data.test_type"
            :session_id="null"
            :currentIndex="currentIndex"
            :readonly="true"
            @next="goNext"
            @prev="goPrev"
          />
          <div v-else class="text-center text-muted py-5 bg-white rounded-4 border">
            No items to show.
          </div>
          <div class="text-center text-muted small mt-3">
            Viewing item {{ currentIndex + 1 }} of {{ testData.length }} (ID: {{ currentTest?.id }})
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { API_BASE_URL } from '@/config'
import TranslationCorrection from '@/components/TranslationCorrection.vue'
import SentenceCorrection from '@/components/SentenceCorrection.vue'
import ConversationEvaluation from '@/components/ConversationEvaluation.vue'
import AudioSegmentation from '@/components/AudioSegmentation.vue'
import BenchmarkVerification from '@/components/BenchmarkVerification.vue'

const route = useRoute()
const router = useRouter()

const data = ref(null)
const loading = ref(true)
const error = ref(null)
const activeTab = ref(-1)   // -1 = blank task; 0..n-1 = annotator index
const currentIndex = ref(0)
const search = ref('')

const COMPONENTS = {
  'translation-correction': TranslationCorrection,
  'sentence-correction': SentenceCorrection,
  'conversation-evaluation': ConversationEvaluation,
  'conversation-editable': ConversationEvaluation,
  'audio-segmentation': AudioSegmentation,
  'benchmark-verification': BenchmarkVerification,
}

const currentComponent = computed(() => COMPONENTS[data.value?.test_type] || null)
const currentAnnotator = computed(() =>
  activeTab.value >= 0 ? (data.value?.annotators?.[activeTab.value] || null) : null)
const hasVerdict = computed(() =>
  currentAnnotator.value && (currentAnnotator.value.counts.accepted || currentAnnotator.value.counts.rejected))

// Build the item list for the active tab. Blank tab = pristine items; an annotator
// tab = each item overlaid with that annotator's submitted results + status.
const testData = computed(() => {
  const items = data.value?.items || []
  const ann = currentAnnotator.value
  return items.map((item) => {
    if (!ann) return { ...item, completion_status: 'uncompleted' }
    const rec = ann.ratings[String(item.id)]
    if (!rec) return { ...item, completion_status: 'uncompleted' }
    return { ...item, ...(rec.results || {}), completion_status: rec.status || 'completed' }
  })
})

const currentTest = computed(() => testData.value[currentIndex.value] || null)
const doneCount = computed(() => testData.value.filter(t => t.completion_status === 'completed').length)

const filteredTasks = computed(() => {
  const term = search.value.trim().toLowerCase()
  return testData.value
    .map((task, originalIndex) => ({ ...task, originalIndex }))
    .filter(task => !term || String(task.id || '').toLowerCase().includes(term))
})

function isDone(task) { return task.completion_status === 'completed' || task.completion_status === 'skipped' }

function selectTab(i) {
  activeTab.value = i
  // Jump to the first item this annotator actually worked on.
  const firstDone = testData.value.findIndex(t => t.completion_status === 'completed' || t.completion_status === 'skipped')
  currentIndex.value = firstDone !== -1 ? firstDone : 0
}
function goNext() { if (currentIndex.value < testData.value.length - 1) currentIndex.value++ }
function goPrev() { if (currentIndex.value > 0) currentIndex.value-- }

function formatType(t) {
  return String(t || '').split(/[-_]/).map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
}
function goBack() {
  if (window.history.length > 1) router.back()
  else router.push('/tracking')
}

watch(currentIndex, () => window.scrollTo({ top: 0, behavior: 'smooth' }))

onMounted(async () => {
  try {
    const token = localStorage.getItem('authToken')
    const res = await fetch(`${API_BASE_URL}/admin/task/${route.params.id}/annotations`, {
      headers: { 'Authorization': `Bearer ${token}` },
    })
    if (res.status === 401) { router.push('/login'); return }
    if (!res.ok) throw new Error('Failed to load annotations for this task.')
    data.value = await res.json()
    // Default to the first annotator if any submitted; otherwise show the blank task.
    if (data.value.annotators && data.value.annotators.length) selectTab(0)
    else activeTab.value = -1
  } catch (e) {
    console.error(e)
    error.value = e.message || 'Failed to load annotations.'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.review-bg { min-height: calc(100vh - 56px); background-color: #f8fafc; }
.annotator-tabs { position: sticky; top: 8px; z-index: 5; }
.tab-btn { border-radius: 10px; }
.sidebar-card { border-radius: 16px; position: sticky; top: 64px; }
.task-list-wrapper { max-height: calc(100vh - 220px); overflow-y: auto; padding-right: 2px; }
.task-list-wrapper::-webkit-scrollbar { width: 6px; }
.task-list-wrapper::-webkit-scrollbar-thumb { background-color: #cbd5e1; border-radius: 10px; }
.task-item { background: #f8fafc; border: 1px solid #f1f5f9; transition: all 0.15s ease; }
.task-item:hover { background: #f1f5f9; }
.active-task { border-color: #d8661b !important; background: #fceee3 !important; }
.done-task { border-left: 4px solid #10b981; }
.stat-pill { display: inline-flex; flex-direction: column; align-items: center; background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 3px 12px; min-width: 78px; }
.stat-pill .lbl { font-size: 0.6rem; text-transform: uppercase; letter-spacing: 0.05em; color: #64748b; font-weight: 700; }
.stat-pill .val { font-size: 1.05rem; font-weight: 800; }
.text-purple { color: #7e22ce !important; }
.bg-purple-subtle { background-color: #faf5ff !important; }
.cursor-pointer { cursor: pointer; }
</style>
