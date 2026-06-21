<template>
  <div class="container py-1 w-100 mt-2">
    <!-- Instructions -->
    <div class="alert alert-info shadow-sm animate-fade-in" role="alert">
      <div class="d-flex justify-content-center">
        <button
          class="btn btn-primary instruction-btn shadow-sm"
          type="button"
          data-bs-toggle="collapse"
          data-bs-target="#sentenceGuidelines"
          aria-expanded="false"
          aria-controls="sentenceGuidelines"
        >
          <i class="bi bi-info-circle me-2"></i>
          Sentence Correction Instructions (Click to Expand)
        </button>
      </div>
      <div class="collapse mt-3" id="sentenceGuidelines">
        <div class="card card-body border-0 shadow-inner">
          <h4 class="mb-3 text-primary">Task Description &amp; Instructions</h4>
          <p class="lead text-secondary fs-6">
            Review and correct the <strong>{{ languageLabel }}</strong> translation of a single
            benchmark sentence so it reads naturally and preserves the meaning of the English source.
          </p>
          <h5 class="mt-2 text-dark"><i class="bi bi-shield-check me-2 text-success"></i>Key Guidelines:</h5>
          <ul class="lh-base">
            <li><strong>Code-Mixed:</strong> Keep technical/scientific terms and jargon in English; render the connective language naturally in {{ languageLabel }}.</li>
            <li><strong>Grammar &amp; Fluency:</strong> Fix grammar, spelling, structure and flow so it sounds like a real bilingual speaker.</li>
            <li><strong>Formulas &amp; Equations:</strong> Preserve every mathematical formula, variable and symbol <strong>exactly</strong> as in the source.</li>
            <li><strong>Reset:</strong> Use the <i class="bi bi-arrow-counterclockwise text-secondary"></i> reset button to restore the original translation.</li>
          </ul>
        </div>
      </div>
    </div>

    <div class="row justify-content-center g-4">
      <div class="col-12 col-lg-10">
        <!-- Metadata chips -->
        <div class="d-flex flex-wrap gap-2 mb-3 align-items-center">
          <span class="badge bg-dark-subtle text-dark border rounded-pill px-3 py-2"><i class="bi bi-hash"></i> {{ currentTest.id }}</span>
          <span v-if="level" class="badge bg-primary-subtle text-primary border border-primary-subtle rounded-pill px-3 py-2"><i class="bi bi-layers-half me-1"></i>{{ level }}</span>
          <span v-if="subject" class="badge bg-success-subtle text-success border border-success-subtle rounded-pill px-3 py-2"><i class="bi bi-journal-bookmark me-1"></i>{{ subject }}</span>
          <span v-if="grade" class="badge bg-secondary-subtle text-secondary border rounded-pill px-3 py-2"><i class="bi bi-mortarboard me-1"></i>{{ grade }}</span>
          <span class="badge bg-warning-subtle text-warning-emphasis border border-warning-subtle rounded-pill px-3 py-2"><i class="bi bi-translate me-1"></i>{{ languageLabel }}</span>
        </div>

        <div class="card border-0 shadow-sm rounded-4 bg-white p-3 p-md-4 mb-4">
          <!-- English source -->
          <div class="mb-4">
            <span class="badge bg-secondary-subtle text-secondary mb-2 fs-8 text-uppercase tracking-wide">English Source</span>
            <div class="p-3 bg-light rounded-3 border-start border-3 border-secondary">
              <p class="mb-0 text-dark fs-5 leading-relaxed" v-html="renderMath(englishText)"></p>
            </div>
          </div>

          <!-- Editable translation -->
          <div class="translation-edit-wrapper rounded-4 p-3 border">
            <div class="d-flex justify-content-between align-items-center mb-2">
              <label class="form-label mb-0 small text-uppercase font-bold tracking-wide text-primary">
                Correct Translation ({{ languageLabel }})
              </label>
              <button
                type="button"
                class="btn btn-sm btn-outline-secondary"
                title="Reset to original translation"
                :disabled="!isModified"
                @click="resetText"
              >
                <i class="bi bi-arrow-counterclockwise me-1"></i> Reset
              </button>
            </div>
            <textarea
              v-model="text"
              v-auto-grow
              class="form-control correction-textarea shadow-inner border-2"
              :class="{ 'rtl-text': isRtl }"
              :dir="isRtl ? 'rtl' : 'ltr'"
              rows="3"
              placeholder="Enter the corrected translation here..."
            ></textarea>
            <div class="d-flex justify-content-between align-items-center mt-2 fs-7">
              <span v-if="isModified" class="text-warning"><i class="bi bi-pencil-fill me-1"></i> Modified</span>
              <span v-else class="text-success-emphasis"><i class="bi bi-check-circle-fill me-1"></i> Original</span>
              <span class="text-muted">{{ text?.length || 0 }} chars</span>
            </div>
          </div>
        </div>

        <!-- Submit / Navigation -->
        <div class="card border-0 shadow-sm rounded-4 bg-white p-4 mb-5">
          <div class="d-flex flex-column flex-sm-row justify-content-between align-items-center gap-3">
            <button
              class="btn btn-outline-secondary px-4 py-2 rounded-pill d-flex align-items-center gap-2"
              :disabled="currentIndex === 0"
              @click="$emit('prev')"
            >
              <i class="bi bi-arrow-left-circle-fill"></i> Previous
            </button>
            <div class="d-flex gap-3 w-100 w-sm-auto justify-content-center flex-wrap">
              <button class="btn btn-warning px-4 py-2 rounded-pill text-dark fw-medium d-flex align-items-center gap-2" :disabled="isSubmitting || isSaving" @click="handleSave">
                <span v-if="isSaving" class="spinner-border spinner-border-sm"></span>
                <i v-else class="bi bi-bookmark-fill"></i> Save Draft
              </button>
              <button class="btn btn-outline-warning px-4 py-2 rounded-pill d-flex align-items-center gap-2" :disabled="isSubmitting || isSaving" @click="handleSkip">
                <i class="bi bi-skip-forward-circle-fill"></i> Skip
              </button>
              <button class="btn btn-success px-5 py-2 rounded-pill d-flex align-items-center gap-2 shadow-sm" :disabled="isSubmitting || isSaving || !isValid" @click="handleSubmit">
                <span v-if="isSubmitting" class="spinner-border spinner-border-sm"></span>
                <i v-else class="bi bi-cloud-arrow-up-fill"></i>
                {{ isSubmitting ? 'Saving...' : isLastTest ? 'Submit & Finish' : 'Submit & Next' }}
              </button>
            </div>
          </div>
          <div v-if="!isValid" class="text-danger text-center small mt-3">
            <i class="bi bi-exclamation-triangle-fill me-1"></i> The translation cannot be empty.
          </div>
          <div class="text-center text-muted mt-3" style="font-size: 0.78rem;">
            Shortcuts: <kbd>Ctrl</kbd>/<kbd>⌘</kbd> + <kbd>Enter</kbd> submit &amp; next ·
            <kbd>Ctrl</kbd>/<kbd>⌘</kbd> + <kbd>S</kbd> save draft
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { API_BASE_URL } from '@/config'

const vAutoGrow = {
  mounted(el) {
    el.style.resize = 'none'; el.style.overflowY = 'hidden'
    const resize = () => { el.style.height = 'auto'; el.style.height = `${el.scrollHeight}px` }
    el.addEventListener('input', resize); setTimeout(resize, 0); el._r = resize
  },
  updated(el) { if (el._r) setTimeout(el._r, 0) },
  unmounted(el) { if (el._r) el.removeEventListener('input', el._r) }
}

const props = defineProps({
  currentTest: { type: Object, required: true },
  isLastTest: { type: Boolean, default: false },
  test_id: { type: [Number, String], required: true },
  session_id: { type: String, default: null },
  currentIndex: { type: Number, required: true }
})
const emit = defineEmits(['next', 'prev', 'submit-status'])

const isSubmitting = ref(false)
const isSaving = ref(false)
const startTime = ref(Date.now())
const text = ref('')
const origText = ref('')

function setup() {
  startTime.value = Date.now()
  text.value = props.currentTest?.text ?? props.currentTest?.translated ?? ''
  origText.value = text.value
  window.scrollTo({ top: 0, behavior: 'smooth' })
}
watch(() => props.currentTest, setup, { immediate: true })

// Keyboard shortcuts: Ctrl/Cmd+Enter = Submit & Next, Ctrl/Cmd+S = Save Draft.
function onKeydown(e) {
  if (!(e.ctrlKey || e.metaKey)) return
  if (e.key === 'Enter') { e.preventDefault(); handleSubmit() }
  else if (e.key.toLowerCase() === 's') { e.preventDefault(); handleSave() }
}
onMounted(() => { setup(); window.addEventListener('keydown', onKeydown) })
onUnmounted(() => window.removeEventListener('keydown', onKeydown))

const englishText = computed(() =>
  props.currentTest?.text_en || props.currentTest?.english || props.currentTest?.original || props.currentTest?.en || '')
const subject = computed(() => props.currentTest?.subject || '')
const grade = computed(() => props.currentTest?.grade_bucket || props.currentTest?.grade || '')
const level = computed(() => props.currentTest?.level || '')
const languageLabel = computed(() => {
  const l = props.currentTest?.target_language || props.currentTest?.language || ''
  return l ? l.charAt(0).toUpperCase() + l.slice(1) : 'Target Language'
})
const rtlLanguages = ['urdu', 'arabic', 'hebrew', 'farsi', 'persian', 'sindhi']
const isRtl = computed(() =>
  rtlLanguages.includes((props.currentTest?.target_language || props.currentTest?.language || '').toLowerCase()))
const isModified = computed(() => text.value !== origText.value)
const isValid = computed(() => (text.value || '').trim().length > 0)

function resetText() { text.value = origText.value }

// Render $...$ / \(...\) math with KaTeX if present (loaded lazily, safe no-op otherwise).
function renderMath(s) {
  const esc = String(s == null ? '' : s).replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]))
  if (window.katex && window.renderMathInElement) {
    const div = document.createElement('div'); div.innerHTML = esc
    try {
      window.renderMathInElement(div, {
        delimiters: [
          { left: '$$', right: '$$', display: true }, { left: '\\[', right: '\\]', display: true },
          { left: '\\(', right: '\\)', display: false }, { left: '$', right: '$', display: false }
        ], throwOnError: false
      })
      return div.innerHTML
    } catch (_) { /* fall through */ }
  }
  return esc
}

function buildResults() {
  return {
    id: props.currentTest.id,
    text: text.value,
    text_en: englishText.value,
    subject: subject.value,
    level: level.value,
    target_language: props.currentTest.target_language || props.currentTest.language || ''
  }
}

async function post(status) {
  const token = localStorage.getItem('authToken')
  return fetch(`${API_BASE_URL}/ratings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
    body: JSON.stringify({
      test_id: props.test_id,
      session_id: props.session_id,
      results_json: buildResults(),
      time_taken_to_submit: Date.now() - startTime.value,
      pageNo_progress: String(props.currentTest.id),
      completion_status: status
    })
  })
}

async function handleSubmit() {
  if (isSubmitting.value || !isValid.value) return
  isSubmitting.value = true
  try {
    const r = await post('completed')
    if (!r.ok) throw new Error('submit failed')
    emit('submit-status', { index: props.currentIndex, status: 'completed', results: buildResults() })
    emit('next')
  } catch (e) { console.error(e); alert('Failed to submit. Please check your connection and try again.') }
  finally { isSubmitting.value = false }
}

async function handleSave() {
  if (isSaving.value || isSubmitting.value) return
  isSaving.value = true
  try {
    const r = await post('saved')
    if (!r.ok) throw new Error('save failed')
    emit('submit-status', { index: props.currentIndex, status: 'saved', results: buildResults() })
    const toast = document.createElement('div')
    toast.className = 'position-fixed bottom-0 start-50 translate-middle-x mb-4 bg-dark text-white py-2 px-4 rounded-pill shadow-lg z-3'
    toast.innerHTML = '<i class="bi bi-check-circle-fill text-warning me-2"></i> Progress saved!'
    document.body.appendChild(toast)
    setTimeout(() => { toast.style.opacity = '0'; setTimeout(() => toast.remove(), 300) }, 2200)
  } catch (e) { console.error(e); alert('Failed to save progress.') }
  finally { isSaving.value = false }
}

async function handleSkip() {
  if (isSubmitting.value) return
  isSubmitting.value = true
  try {
    const r = await post('skipped')
    if (!r.ok) throw new Error('skip failed')
    emit('submit-status', { index: props.currentIndex, status: 'skipped' })
    emit('next')
  } catch (e) { console.error(e); alert('Failed to skip.') }
  finally { isSubmitting.value = false }
}
</script>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Arabic:wght@400;500;600;700&family=Noto+Nastaliq+Urdu:wght@400;700&display=swap');
.rtl-text { direction: rtl; text-align: right; font-family: 'Noto Nastaliq Urdu', 'Noto Sans Arabic', 'Inter', sans-serif; line-height: 1.8; }
.fs-7 { font-size: 0.85rem; } .fs-8 { font-size: 0.72rem; }
.tracking-wide { letter-spacing: 0.06em; }
.translation-edit-wrapper { background-color: #fcfdfe; border-color: rgba(0,0,0,0.06) !important; }
.correction-textarea { font-size: 1.1rem; line-height: 1.6; border-radius: 12px; padding: 14px 16px; resize: none; overflow-y: hidden; background-color: #fff; transition: border-color .2s ease, box-shadow .2s ease; min-height: 90px; }
.correction-textarea:focus { border-color: #4f46e5; box-shadow: 0 0 0 3px rgba(79,70,229,0.15) !important; }
.shadow-inner { box-shadow: inset 0 2px 4px rgba(0,0,0,0.06); }
.leading-relaxed { line-height: 1.7; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
.animate-fade-in { animation: fadeIn 0.4s ease-out; }
</style>
