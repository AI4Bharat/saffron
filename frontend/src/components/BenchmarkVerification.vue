<template>
  <div class="container py-1 w-100 mt-2">
    <!-- How to use this page & keyboard shortcuts -->
    <div class="usage-alert shadow-sm animate-fade-in">
      <div class="d-flex justify-content-center">
        <button
          class="btn btn-primary instruction-btn shadow-sm"
          type="button"
          data-bs-toggle="collapse"
          data-bs-target="#benchmarkGuidelines"
          aria-expanded="false"
          aria-controls="benchmarkGuidelines"
        >
          <i class="bi bi-keyboard me-2"></i>
          How to Use &amp; Shortcuts (Click to Expand)
        </button>
      </div>
      <div class="collapse mt-3" id="benchmarkGuidelines">
        <div class="card card-body border-0 shadow-inner usage-panel">
          <div class="row g-4">
            <div class="col-md-6">
              <h6 class="usage-heading"><i class="bi bi-keyboard me-2"></i>Keyboard shortcuts</h6>
              <ul class="shortcut-list mb-2">
                <li><span class="keys"><kbd>1</kbd></span><span class="desc">Mark as Accept</span></li>
                <li><span class="keys"><kbd>2</kbd></span><span class="desc">Mark as Reject</span></li>
                <li><span class="keys"><kbd>Ctrl</kbd><span class="plus">+</span><kbd>Enter</kbd></span><span class="desc">Submit &amp; go to the next task</span></li>
                <li><span class="keys"><kbd>Ctrl</kbd><span class="plus">+</span><kbd>S</kbd></span><span class="desc">Save your progress</span></li>
              </ul>
              <p class="text-muted fs-9 mb-0">On macOS, use <kbd>⌘ Cmd</kbd> in place of <kbd>Ctrl</kbd>.</p>
            </div>
            <div class="col-md-6">
              <h6 class="usage-heading"><i class="bi bi-mouse2 me-2"></i>Using the interface</h6>
              <ul class="usage-list">
                <li>Verify the <strong>Raw Text</strong> and the <strong>Spoken Form</strong>. Click either field to edit it directly.</li>
                <li>Choose <strong>Accept</strong> if both are correct, or <strong>Reject</strong> if something is wrong.</li>
                <li>Add a <strong>comment</strong> to explain a rejection (optional but recommended).</li>
                <li>Use <i class="bi bi-arrow-counterclockwise"></i> <strong>Reset</strong> on a field to restore its original value.</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="row justify-content-center g-4">
      <div class="col-12 col-lg-10">
        <!-- Read-only preview banner (admin review) -->
        <div v-if="readonly" class="alert alert-info d-flex align-items-center rounded-4 mb-3">
          <i class="bi bi-eye-fill me-2"></i>
          <span>Read-only preview of a submitted annotation.</span>
        </div>

        <!-- Metadata chips -->
        <div class="d-flex flex-wrap gap-2 mb-3 align-items-center">
          <span class="badge bg-dark-subtle text-dark border rounded-pill px-3 py-2"><i class="bi bi-hash"></i> {{ currentTest.id }}</span>
          <span v-if="languageLabel" class="badge bg-warning-subtle text-warning-emphasis border border-warning-subtle rounded-pill px-3 py-2"><i class="bi bi-translate me-1"></i>{{ languageLabel }}</span>
          <span v-if="currentTest.domain" class="badge bg-primary-subtle text-primary border border-primary-subtle rounded-pill px-3 py-2"><i class="bi bi-diagram-3 me-1"></i>{{ formatTag(currentTest.domain) }}</span>
          <span v-if="currentTest.suite" class="badge bg-info-subtle text-info-emphasis border rounded-pill px-3 py-2"><i class="bi bi-collection me-1"></i>{{ formatTag(currentTest.suite) }}</span>
          <span v-if="currentTest.length_bucket" class="badge bg-secondary-subtle text-secondary border rounded-pill px-3 py-2"><i class="bi bi-rulers me-1"></i>{{ formatTag(currentTest.length_bucket) }}</span>
          <span v-if="currentTest.target_emotion" class="badge bg-success-subtle text-success border border-success-subtle rounded-pill px-3 py-2"><i class="bi bi-emoji-smile me-1"></i>{{ formatTag(currentTest.target_emotion) }}</span>
        </div>

        <div class="card border-0 shadow-sm rounded-4 bg-white p-3 p-md-4 mb-4">
          <!-- Raw Text (editable) -->
          <div class="edit-block rounded-4 p-3 border mb-4">
            <div class="d-flex justify-content-between align-items-center mb-2">
              <label class="form-label mb-0 small text-uppercase fw-bold tracking-wide text-primary">
                <i class="bi bi-file-text me-1"></i> Raw Text
              </label>
              <button
                type="button"
                class="btn btn-sm btn-outline-secondary"
                v-if="!readonly"
                title="Reset to original raw text"
                :disabled="rawText === origRawText"
                @click="rawText = origRawText"
              >
                <i class="bi bi-arrow-counterclockwise me-1"></i> Reset
              </button>
            </div>
            <textarea
              v-model="rawText"
              v-auto-grow
              class="form-control correction-textarea shadow-inner border-2"
              :class="{ 'rtl-text': isRtl }"
              :dir="isRtl ? 'rtl' : 'ltr'"
              :readonly="readonly"
              rows="2"
              placeholder="Raw text…"
            ></textarea>
            <div class="d-flex justify-content-between align-items-center mt-2 fs-7">
              <span v-if="rawText !== origRawText" class="text-warning"><i class="bi bi-pencil-fill me-1"></i> Edited</span>
              <span v-else class="text-success-emphasis"><i class="bi bi-check-circle-fill me-1"></i> Original</span>
              <span class="text-muted">{{ rawText?.length || 0 }} chars</span>
            </div>
          </div>

          <!-- Spoken Form (editable) -->
          <div class="edit-block rounded-4 p-3 border">
            <div class="d-flex justify-content-between align-items-center mb-2">
              <label class="form-label mb-0 small text-uppercase fw-bold tracking-wide text-primary">
                <i class="bi bi-soundwave me-1"></i> Spoken Form
              </label>
              <button
                type="button"
                class="btn btn-sm btn-outline-secondary"
                v-if="!readonly"
                title="Reset to original spoken form"
                :disabled="spokenForm === origSpokenForm"
                @click="spokenForm = origSpokenForm"
              >
                <i class="bi bi-arrow-counterclockwise me-1"></i> Reset
              </button>
            </div>
            <textarea
              v-model="spokenForm"
              v-auto-grow
              class="form-control correction-textarea shadow-inner border-2"
              :class="{ 'rtl-text': isRtl }"
              :dir="isRtl ? 'rtl' : 'ltr'"
              :readonly="readonly"
              rows="2"
              placeholder="Spoken form…"
            ></textarea>
            <div class="d-flex justify-content-between align-items-center mt-2 fs-7">
              <span v-if="spokenForm !== origSpokenForm" class="text-warning"><i class="bi bi-pencil-fill me-1"></i> Edited</span>
              <span v-else class="text-success-emphasis"><i class="bi bi-check-circle-fill me-1"></i> Original</span>
              <span class="text-muted">{{ spokenForm?.length || 0 }} chars</span>
            </div>
          </div>
        </div>

        <!-- Verdict: Accept / Reject -->
        <div class="card border-0 shadow-sm rounded-4 bg-white p-3 p-md-4 mb-4">
          <p class="text-secondary fs-8 mb-3 text-uppercase fw-bold tracking-wide">Verification decision</p>
          <div class="row g-3">
            <div class="col-6">
              <button
                type="button"
                class="btn w-100 py-3 rounded-4 fw-bold d-flex align-items-center justify-content-center gap-2 verdict-btn"
                :class="decision === 'accept' ? 'btn-success' : 'btn-outline-success'"
                :disabled="readonly"
                @click="setDecision('accept')"
              >
                <i class="bi" :class="decision === 'accept' ? 'bi-check-circle-fill' : 'bi-check-circle'"></i>
                Accept
              </button>
            </div>
            <div class="col-6">
              <button
                type="button"
                class="btn w-100 py-3 rounded-4 fw-bold d-flex align-items-center justify-content-center gap-2 verdict-btn"
                :class="decision === 'reject' ? 'btn-danger' : 'btn-outline-danger'"
                :disabled="readonly"
                @click="setDecision('reject')"
              >
                <i class="bi" :class="decision === 'reject' ? 'bi-x-circle-fill' : 'bi-x-circle'"></i>
                Reject
              </button>
            </div>
          </div>

          <!-- Optional comment -->
          <div class="mt-3">
            <label class="form-label small text-uppercase fw-bold tracking-wide text-secondary mb-1">
              Comment <span class="text-muted fw-normal text-lowercase">(for rejection)</span>
            </label>
            <textarea
              v-model="comments"
              v-auto-grow
              class="form-control shadow-inner border-2"
              :readonly="readonly"
              rows="2"
              placeholder="Add a note explaining the rejection…"
            ></textarea>
          </div>
        </div>

        <!-- Submit / Navigation -->
        <div v-if="!readonly" class="card border-0 shadow-sm rounded-4 bg-white p-4 mb-5">
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
            <i class="bi bi-exclamation-triangle-fill me-1"></i>
            <span v-if="!decision">Please choose Accept or Reject before submitting.</span>
            <span v-else>Raw Text and Spoken Form cannot be empty.</span>
          </div>
          <div class="text-center text-muted mt-3" style="font-size: 0.78rem;">
            Shortcuts: <kbd>1</kbd> accept · <kbd>2</kbd> reject ·
            <kbd>Ctrl</kbd>/<kbd>⌘</kbd> + <kbd>Enter</kbd> submit &amp; next ·
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
  currentIndex: { type: Number, required: true },
  // Read-only preview (admin review): hide actions, disable all submit paths.
  readonly: { type: Boolean, default: false }
})
const emit = defineEmits(['next', 'prev', 'submit-status'])

const isSubmitting = ref(false)
const isSaving = ref(false)
const startTime = ref(Date.now())

const rawText = ref('')
const origRawText = ref('')
const spokenForm = ref('')
const origSpokenForm = ref('')
const decision = ref('')      // 'accept' | 'reject' | ''
const comments = ref('')

function setup() {
  startTime.value = Date.now()
  rawText.value = props.currentTest?.raw_text ?? ''
  origRawText.value = props.currentTest?.raw_text ?? ''
  spokenForm.value = props.currentTest?.spoken_form ?? ''
  origSpokenForm.value = props.currentTest?.spoken_form ?? ''
  decision.value = props.currentTest?.decision ?? ''
  comments.value = props.currentTest?.comments ?? ''
  window.scrollTo({ top: 0, behavior: 'auto' })
}
watch(() => props.currentTest, setup, { immediate: true })

function setDecision(d) { if (props.readonly) return; decision.value = d }

// Keyboard: 1 = accept, 2 = reject, Ctrl/Cmd+Enter = submit, Ctrl/Cmd+S = save.
function onKeydown(e) {
  if (props.readonly) return
  const tag = (e.target && e.target.tagName) || ''
  const typing = tag === 'TEXTAREA' || tag === 'INPUT'
  if (e.ctrlKey || e.metaKey) {
    if (e.key === 'Enter') { e.preventDefault(); handleSubmit() }
    else if (e.key.toLowerCase() === 's') { e.preventDefault(); handleSave() }
    return
  }
  if (typing) return
  if (e.key === '1') { e.preventDefault(); setDecision('accept') }
  else if (e.key === '2') { e.preventDefault(); setDecision('reject') }
}
onMounted(() => { setup(); window.addEventListener('keydown', onKeydown) })
onUnmounted(() => window.removeEventListener('keydown', onKeydown))

const languageLabel = computed(() => {
  const map = { bn: 'Bengali', gu: 'Gujarati', hi: 'Hindi', kn: 'Kannada', ml: 'Malayalam', mr: 'Marathi', or: 'Odia', ta: 'Tamil', te: 'Telugu', ur: 'Urdu', en: 'English' }
  const l = props.currentTest?.lang || props.currentTest?.language || ''
  return map[l] || (l ? l.charAt(0).toUpperCase() + l.slice(1) : '')
})
const rtlLanguages = ['ur', 'urdu', 'ar', 'arabic', 'he', 'hebrew', 'fa', 'farsi', 'persian', 'sd', 'sindhi']
const isRtl = computed(() =>
  rtlLanguages.includes((props.currentTest?.lang || props.currentTest?.language || '').toLowerCase()))

const isValid = computed(() =>
  !!decision.value && (rawText.value || '').trim().length > 0 && (spokenForm.value || '').trim().length > 0)

function formatTag(s) {
  if (!s) return ''
  return String(s).split(/[_\s]+/).map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
}

function buildResults() {
  return {
    id: props.currentTest.id,
    raw_text: rawText.value,
    spoken_form: spokenForm.value,
    decision: decision.value,
    comments: comments.value
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
  if (props.readonly) return
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
  if (props.readonly) return
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
  if (props.readonly) return
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
.fs-7 { font-size: 0.85rem; } .fs-8 { font-size: 0.72rem; } .fs-9 { font-size: 0.68rem; }
.tracking-wide { letter-spacing: 0.06em; }
.edit-block { background-color: #fcfdfe; border-color: rgba(0,0,0,0.06) !important; }
.correction-textarea { font-size: 1.1rem; line-height: 1.6; border-radius: 12px; padding: 14px 16px; resize: none; overflow-y: hidden; background-color: #fff; transition: border-color .2s ease, box-shadow .2s ease; min-height: 60px; }
.correction-textarea:focus { border-color: #d8661b; box-shadow: 0 0 0 3px rgba(216,102,27,0.15) !important; }
.shadow-inner { box-shadow: inset 0 2px 4px rgba(0,0,0,0.06); }
.verdict-btn { transition: all 0.15s ease; font-size: 1.05rem; }
.verdict-btn:active { transform: scale(0.98); }
@keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
.animate-fade-in { animation: fadeIn 0.4s ease-out; }
</style>
