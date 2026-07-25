<template>
  <div class="container py-1 w-100 mt-2 benchmark-verification">
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
                <li><span class="keys"><kbd>R</kbd></span><span class="desc">Toggle the reference panel</span></li>
                <li><span class="keys"><kbd>Ctrl</kbd><span class="plus">+</span><kbd>Enter</kbd></span><span class="desc">Submit &amp; go to the next task</span></li>
                <li><span class="keys"><kbd>Ctrl</kbd><span class="plus">+</span><kbd>S</kbd></span><span class="desc">Save your progress</span></li>
              </ul>
              <p class="text-muted fs-9 mb-0">On macOS, use <kbd>⌘ Cmd</kbd> in place of <kbd>Ctrl</kbd>.</p>
            </div>
            <div class="col-md-6">
              <h6 class="usage-heading"><i class="bi bi-mouse2 me-2"></i>Using the interface</h6>
              <ul class="usage-list">
                <li>Read the <strong>Reference</strong> panel first — the <strong>domain</strong> and the <strong>phenomenon tags</strong> tell you what this sentence is meant to test.</li>
                <li>Verify the <strong>Raw Text</strong> and the <strong>Spoken Form</strong>. Click either field to edit it directly.</li>
                <li>Choose <strong>Accept</strong> if both are correct, or <strong>Reject</strong> if something is wrong.</li>
                <li>Add a <strong>comment</strong> explaining a rejection (required when you reject).</li>
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

        <!-- ============ REFERENCE PANEL ============ -->
        <section class="ref-card rounded-4 mb-4 shadow-sm">
          <header class="ref-head" @click="showReference = !showReference">
            <div class="d-flex align-items-center gap-2 flex-wrap">
              <span class="ref-title"><i class="bi bi-info-circle-fill me-2"></i>Reference</span>
              <span class="ref-id" :title="String(currentTest.id)">{{ currentTest.id }}</span>
              <span v-if="languageLabel" class="chip chip-lang"><i class="bi bi-translate"></i>{{ languageLabel }}</span>
              <span v-if="currentTest.domain" class="chip chip-domain"><i class="bi bi-diagram-3-fill"></i>{{ formatTag(currentTest.domain) }}</span>
              <span v-if="phenomenonTags.length" class="chip chip-count" :title="phenomenonTags.join(', ')">
                <i class="bi bi-tags-fill"></i>{{ phenomenonTags.length }} tag<span v-if="phenomenonTags.length > 1">s</span>
              </span>
            </div>
            <button type="button" class="btn btn-sm btn-link ref-toggle text-decoration-none" :aria-expanded="showReference">
              {{ showReference ? 'Hide' : 'Show' }}
              <i class="bi ms-1" :class="showReference ? 'bi-chevron-up' : 'bi-chevron-down'"></i>
            </button>
          </header>

          <div v-show="showReference" class="ref-body">
            <!-- Phenomenon tags: the thing the annotator most needs to check -->
            <div class="ref-row">
              <div class="ref-label"><i class="bi bi-tags-fill me-1"></i>Phenomenon tags</div>
              <div class="ref-value">
                <template v-if="phenomenonTags.length">
                  <span v-for="t in phenomenonTags" :key="t" class="chip chip-phen">{{ formatTag(t) }}</span>
                </template>
                <span v-else class="text-muted fst-italic">none — plain sentence</span>
              </div>
            </div>

            <!-- English source sentence (parallel benchmark round) -->
            <div v-if="sourceRawText" class="ref-row">
              <div class="ref-label"><i class="bi bi-translate me-1"></i>English source</div>
              <div class="ref-value">
                <div class="source-box">
                  <p class="source-text mb-0">{{ sourceRawText }}</p>
                  <p v-if="sourceSpokenForm && sourceSpokenForm !== sourceRawText" class="source-text source-spoken mb-0">
                    <span class="source-tag">spoken</span>{{ sourceSpokenForm }}
                  </p>
                </div>
                <p class="ref-hint mb-0">
                  <i class="bi bi-lightbulb me-1"></i>The sentence below should carry this meaning, phrased naturally in {{ languageLabel || 'the target language' }}.
                </p>
              </div>
            </div>

            <!-- The rest of the metadata -->
            <div class="ref-row ref-row-grid">
              <div v-for="m in metaFields" :key="m.label" class="meta-cell">
                <span class="meta-label">{{ m.label }}</span>
                <span class="meta-value" :title="m.value">{{ m.value }}</span>
              </div>
            </div>
          </div>
        </section>

        <!-- ============ TEXT TO VERIFY ============ -->
        <div class="card border-0 shadow-sm rounded-4 bg-white p-3 p-md-4 mb-4">
          <!-- Raw Text (editable) -->
          <div class="edit-block rounded-4 p-3 border mb-4" :class="{ 'is-edited': rawEdited }">
            <div class="d-flex justify-content-between align-items-center mb-2">
              <label class="form-label mb-0 small text-uppercase fw-bold tracking-wide text-primary">
                <i class="bi bi-file-text me-1"></i> Raw Text
                <span class="field-hint">as written</span>
              </label>
              <div class="d-flex align-items-center gap-2">
                <button
                  type="button"
                  class="btn btn-sm btn-outline-secondary"
                  v-if="!readonly && rawEdited"
                  title="Show the original value"
                  @click="showRawDiff = !showRawDiff"
                >
                  <i class="bi bi-arrow-left-right me-1"></i>{{ showRawDiff ? 'Hide' : 'Compare' }}
                </button>
                <button
                  type="button"
                  class="btn btn-sm btn-outline-secondary"
                  v-if="!readonly"
                  title="Reset to original raw text"
                  :disabled="!rawEdited"
                  @click="rawText = origRawText"
                >
                  <i class="bi bi-arrow-counterclockwise me-1"></i> Reset
                </button>
              </div>
            </div>
            <div v-if="showRawDiff && rawEdited" class="diff-box mb-2">
              <span class="diff-tag">original</span>
              <span class="diff-text" :dir="isRtl ? 'rtl' : 'ltr'" :class="{ 'rtl-text': isRtl }">{{ origRawText }}</span>
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
              <span v-if="rawEdited" class="text-warning-emphasis"><i class="bi bi-pencil-fill me-1"></i> Edited</span>
              <span v-else class="text-success-emphasis"><i class="bi bi-check-circle-fill me-1"></i> Original</span>
              <span class="text-muted">{{ rawText?.length || 0 }} chars</span>
            </div>
          </div>

          <!-- Spoken Form (editable) -->
          <div class="edit-block rounded-4 p-3 border" :class="{ 'is-edited': spokenEdited }">
            <div class="d-flex justify-content-between align-items-center mb-2">
              <label class="form-label mb-0 small text-uppercase fw-bold tracking-wide text-primary">
                <i class="bi bi-soundwave me-1"></i> Spoken Form
                <span class="field-hint">as read aloud</span>
              </label>
              <div class="d-flex align-items-center gap-2">
                <button
                  type="button"
                  class="btn btn-sm btn-outline-secondary"
                  v-if="!readonly && spokenEdited"
                  title="Show the original value"
                  @click="showSpokenDiff = !showSpokenDiff"
                >
                  <i class="bi bi-arrow-left-right me-1"></i>{{ showSpokenDiff ? 'Hide' : 'Compare' }}
                </button>
                <button
                  type="button"
                  class="btn btn-sm btn-outline-secondary"
                  v-if="!readonly"
                  title="Reset to original spoken form"
                  :disabled="!spokenEdited"
                  @click="spokenForm = origSpokenForm"
                >
                  <i class="bi bi-arrow-counterclockwise me-1"></i> Reset
                </button>
              </div>
            </div>
            <div v-if="showSpokenDiff && spokenEdited" class="diff-box mb-2">
              <span class="diff-tag">original</span>
              <span class="diff-text" :dir="isRtl ? 'rtl' : 'ltr'" :class="{ 'rtl-text': isRtl }">{{ origSpokenForm }}</span>
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
              <span v-if="spokenEdited" class="text-warning-emphasis"><i class="bi bi-pencil-fill me-1"></i> Edited</span>
              <span v-else class="text-success-emphasis"><i class="bi bi-check-circle-fill me-1"></i> Original</span>
              <span class="text-muted">{{ spokenForm?.length || 0 }} chars</span>
            </div>
          </div>
        </div>

        <!-- ============ VERDICT ============ -->
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
                <kbd class="verdict-kbd">1</kbd>
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
                <kbd class="verdict-kbd">2</kbd>
              </button>
            </div>
          </div>

          <!-- Comment -->
          <div class="mt-3">
            <label class="form-label small text-uppercase fw-bold tracking-wide text-secondary mb-1">
              Comment
              <span v-if="decision === 'reject'" class="text-danger fw-normal text-lowercase">(required for a rejection)</span>
              <span v-else class="text-muted fw-normal text-lowercase">(optional)</span>
            </label>
            <!-- Quick reasons: one click drops a standard reason into the comment -->
            <div v-if="!readonly && decision === 'reject'" class="d-flex flex-wrap gap-2 mb-2">
              <button
                v-for="r in quickReasons"
                :key="r"
                type="button"
                class="btn btn-sm reason-chip"
                :class="commentHas(r) ? 'btn-danger' : 'btn-outline-danger'"
                @click="toggleReason(r)"
              >{{ r }}</button>
            </div>
            <textarea
              v-model="comments"
              v-auto-grow
              class="form-control shadow-inner border-2"
              :class="{ 'is-invalid': decision === 'reject' && !readonly && !comments.trim() }"
              :readonly="readonly"
              rows="2"
              placeholder="Add a note explaining the rejection…"
            ></textarea>
          </div>
        </div>

        <!-- ============ SUBMIT ============ -->
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
              <button class="btn btn-warning px-4 py-2 rounded-pill text-dark fw-medium d-flex align-items-center gap-2" :disabled="isBusy" @click="handleSave">
                <span v-if="isSaving" class="spinner-border spinner-border-sm"></span>
                <i v-else class="bi bi-bookmark-fill"></i> Save Draft
              </button>
              <button class="btn btn-outline-warning px-4 py-2 rounded-pill d-flex align-items-center gap-2" :disabled="isBusy" @click="handleSkip">
                <i class="bi bi-skip-forward-circle-fill"></i> Skip
              </button>
              <button class="btn btn-success px-5 py-2 rounded-pill d-flex align-items-center gap-2 shadow-sm" :disabled="isBusy || !isValid" @click="handleSubmit">
                <span v-if="isSubmitting" class="spinner-border spinner-border-sm"></span>
                <i v-else class="bi bi-cloud-arrow-up-fill"></i>
                {{ isSubmitting ? 'Saving...' : isLastTest ? 'Submit & Finish' : 'Submit & Next' }}
              </button>
            </div>
          </div>
          <div v-if="!isValid" class="text-danger text-center small mt-3">
            <i class="bi bi-exclamation-triangle-fill me-1"></i>
            <span>{{ validationMessage }}</span>
          </div>
          <div class="text-center text-muted mt-3" style="font-size: 0.78rem;">
            Shortcuts: <kbd>1</kbd> accept · <kbd>2</kbd> reject · <kbd>R</kbd> reference ·
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
const isBusy = computed(() => isSubmitting.value || isSaving.value)
const startTime = ref(Date.now())

const rawText = ref('')
const origRawText = ref('')
const spokenForm = ref('')
const origSpokenForm = ref('')
const decision = ref('')      // 'accept' | 'reject' | ''
const comments = ref('')

// The reference panel keeps whatever state the annotator left it in, across items.
const showReference = ref(true)
const showRawDiff = ref(false)
const showSpokenDiff = ref(false)

const quickReasons = [
  'Wrong translation', 'Unnatural phrasing', 'Spelling / typo', 'Number or unit wrong',
  'Spoken form mismatch', 'Grammar', 'Wrong domain / tag'
]

function setup() {
  startTime.value = Date.now()
  const t = props.currentTest || {}
  rawText.value = t.raw_text ?? ''
  spokenForm.value = t.spoken_form ?? ''
  // The backend merges an annotator's saved edits back into raw_text / spoken_form,
  // so the pristine values it sends alongside are what "Reset" and the Edited badge
  // must compare against — otherwise a resumed draft looks unedited and Reset
  // restores the edit instead of the original.
  origRawText.value = t.original_raw_text ?? t.raw_text ?? ''
  origSpokenForm.value = t.original_spoken_form ?? t.spoken_form ?? ''
  decision.value = t.decision ?? ''
  comments.value = t.comments ?? ''
  showRawDiff.value = false
  showSpokenDiff.value = false
  window.scrollTo({ top: 0, behavior: 'auto' })
}
watch(() => props.currentTest, setup, { immediate: true })

const rawEdited = computed(() => rawText.value !== origRawText.value)
const spokenEdited = computed(() => spokenForm.value !== origSpokenForm.value)

function setDecision(d) { if (props.readonly) return; decision.value = d }

function commentHas(reason) {
  return comments.value.split(/[;\n]/).map(s => s.trim()).includes(reason)
}
function toggleReason(reason) {
  if (props.readonly) return
  const parts = comments.value.split(/[;\n]/).map(s => s.trim()).filter(Boolean)
  const i = parts.indexOf(reason)
  if (i === -1) parts.push(reason)
  else parts.splice(i, 1)
  comments.value = parts.join('; ')
}

// Keyboard: 1 = accept, 2 = reject, R = reference, Ctrl/Cmd+Enter = submit, Ctrl/Cmd+S = save.
function onKeydown(e) {
  if (props.readonly) return
  const key = e.key || ''
  const tag = (e.target && e.target.tagName) || ''
  const typing = tag === 'TEXTAREA' || tag === 'INPUT' || (e.target && e.target.isContentEditable)
  if (e.ctrlKey || e.metaKey) {
    if (key === 'Enter') { e.preventDefault(); handleSubmit() }
    else if (key.toLowerCase() === 's') { e.preventDefault(); handleSave() }
    return
  }
  if (typing || e.altKey) return
  if (key === '1') { e.preventDefault(); setDecision('accept') }
  else if (key === '2') { e.preventDefault(); setDecision('reject') }
  else if (key.toLowerCase() === 'r') { e.preventDefault(); showReference.value = !showReference.value }
}
onMounted(() => window.addEventListener('keydown', onKeydown))
onUnmounted(() => window.removeEventListener('keydown', onKeydown))

const LANG_NAMES = {
  bn: 'Bengali', gu: 'Gujarati', hi: 'Hindi', kn: 'Kannada', ml: 'Malayalam',
  mr: 'Marathi', or: 'Odia', ta: 'Tamil', te: 'Telugu', ur: 'Urdu', en: 'English'
}
const languageLabel = computed(() => {
  const l = props.currentTest?.lang || props.currentTest?.language || ''
  return LANG_NAMES[l] || (l ? l.charAt(0).toUpperCase() + l.slice(1) : '')
})
const rtlLanguages = ['ur', 'urdu', 'ar', 'arabic', 'he', 'hebrew', 'fa', 'farsi', 'persian', 'sd', 'sindhi']
const isRtl = computed(() =>
  rtlLanguages.includes((props.currentTest?.lang || props.currentTest?.language || '').toLowerCase()))

const phenomenonTags = computed(() => {
  const tags = props.currentTest?.phenomenon_tags
  if (!Array.isArray(tags)) return []
  return tags.filter(t => t && String(t).toLowerCase() !== 'none')
})

// English source sentence, attached by the parallel-benchmark loader.
const sourceRawText = computed(() => props.currentTest?._ref_source_raw_text || '')
const sourceSpokenForm = computed(() => props.currentTest?._ref_source_spoken_form || '')

const metaFields = computed(() => {
  const t = props.currentTest || {}
  const axes = Array.isArray(t.probes_axes) ? t.probes_axes : []
  return [
    { label: 'Domain', value: formatTag(t.domain) },
    { label: 'Suite', value: formatTag(t.suite) },
    { label: 'Length', value: formatTag(t.length_bucket) },
    { label: 'Quota class', value: formatTag(t.quota_class) },
    { label: 'Target emotion', value: t.target_emotion ? formatTag(t.target_emotion) : '—' },
    { label: 'Probes axes', value: axes.length ? axes.map(formatTag).join(', ') : '—' },
    { label: 'Source ID', value: t.source_id || '—' },
  ].filter(m => m.value !== '')
})

const isValid = computed(() => {
  if (!decision.value) return false
  if (!(rawText.value || '').trim() || !(spokenForm.value || '').trim()) return false
  // A rejection with no reason is useless downstream — the comment is the only
  // record of *what* was wrong with the sentence.
  if (decision.value === 'reject' && !(comments.value || '').trim()) return false
  return true
})
const validationMessage = computed(() => {
  if (!decision.value) return 'Please choose Accept or Reject before submitting.'
  if (!(rawText.value || '').trim() || !(spokenForm.value || '').trim())
    return 'Raw Text and Spoken Form cannot be empty.'
  return 'Please add a comment explaining the rejection.'
})

function formatTag(s) {
  if (s === null || s === undefined || s === '') return ''
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

function toast(message, icon = 'bi-check-circle-fill text-warning') {
  const el = document.createElement('div')
  el.className = 'position-fixed bottom-0 start-50 translate-middle-x mb-4 bg-dark text-white py-2 px-4 rounded-pill shadow-lg z-3'
  el.style.transition = 'opacity .3s ease'
  el.innerHTML = `<i class="bi ${icon} me-2"></i> ${message}`
  document.body.appendChild(el)
  setTimeout(() => { el.style.opacity = '0'; setTimeout(() => el.remove(), 300) }, 2200)
}

async function handleSubmit() {
  if (props.readonly) return
  if (isBusy.value || !isValid.value) return
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
  if (isBusy.value) return
  isSaving.value = true
  try {
    const r = await post('saved')
    if (!r.ok) throw new Error('save failed')
    emit('submit-status', { index: props.currentIndex, status: 'saved', results: buildResults() })
    toast('Progress saved!')
  } catch (e) { console.error(e); alert('Failed to save progress.') }
  finally { isSaving.value = false }
}

async function handleSkip() {
  if (props.readonly) return
  if (isBusy.value) return
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

/* ---------- reference panel ---------- */
.ref-card { background: #fff; border: 1px solid rgba(0,0,0,0.07); overflow: hidden; }
.ref-head {
  display: flex; align-items: center; justify-content: space-between; gap: .75rem;
  padding: .7rem 1rem; cursor: pointer; user-select: none;
  background: linear-gradient(180deg, #fbfcfe 0%, #f5f7fb 100%);
  border-bottom: 1px solid rgba(0,0,0,0.06);
}
.ref-head:hover { background: linear-gradient(180deg, #f7f9fd 0%, #eef2f9 100%); }
.ref-title { font-size: .74rem; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; color: #465a75; }
.ref-id {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .74rem; color: #5b6b80;
  background: #eef1f6; border: 1px solid #e0e5ee; border-radius: 6px; padding: .1rem .45rem;
  max-width: 15rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.ref-toggle { font-size: .78rem; font-weight: 600; color: #6b7b90; flex-shrink: 0; }
.ref-body { padding: .35rem 1rem .9rem; }
.ref-row { display: flex; gap: 1rem; padding: .6rem 0; border-top: 1px dashed rgba(0,0,0,0.07); }
.ref-row:first-child { border-top: 0; }
.ref-label {
  flex: 0 0 9.5rem; font-size: .7rem; font-weight: 700; letter-spacing: .05em;
  text-transform: uppercase; color: #7b8798; padding-top: .18rem;
}
.ref-value { flex: 1 1 auto; min-width: 0; display: flex; flex-wrap: wrap; gap: .35rem; align-items: flex-start; }
.ref-row-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(11rem, 1fr)); gap: .5rem 1rem; }
.meta-cell { display: flex; flex-direction: column; min-width: 0; }
.meta-label { font-size: .64rem; font-weight: 700; letter-spacing: .05em; text-transform: uppercase; color: #98a3b3; }
.meta-value { font-size: .84rem; color: #34404f; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.chip {
  display: inline-flex; align-items: center; gap: .3rem; font-size: .74rem; font-weight: 600;
  padding: .18rem .6rem; border-radius: 999px; border: 1px solid transparent; white-space: nowrap;
}
.chip-lang { background: #fff4e5; color: #a35b12; border-color: #f6dcbb; }
.chip-domain { background: #e8f0fe; color: #1a4d9c; border-color: #cfe0fb; }
.chip-count { background: #f0ecfb; color: #5b3fa8; border-color: #ddd4f5; }
.chip-phen { background: #e9f7ef; color: #1c6b46; border-color: #c9ecda; }

.source-box {
  width: 100%; background: #fffdf6; border: 1px solid #f2e4c4; border-left: 4px solid #e2a33c;
  border-radius: 10px; padding: .65rem .85rem;
}
.source-text { font-size: 1rem; line-height: 1.55; color: #4a3a1c; }
.source-spoken { margin-top: .35rem; font-size: .9rem; color: #7a6a48; }
.source-tag {
  font-size: .6rem; font-weight: 700; text-transform: uppercase; letter-spacing: .06em;
  background: #f0e2c0; color: #8a6a26; border-radius: 4px; padding: .05rem .3rem; margin-right: .4rem;
}
.ref-hint { width: 100%; font-size: .74rem; color: #8a94a3; margin-top: .35rem; }

/* ---------- edit blocks ---------- */
.edit-block { background-color: #fcfdfe; border-color: rgba(0,0,0,0.06) !important; transition: border-color .2s ease, background-color .2s ease; }
.edit-block.is-edited { background-color: #fffdf5; border-color: #f0dcae !important; }
.field-hint { font-size: .64rem; font-weight: 600; color: #a4aebd; text-transform: none; letter-spacing: 0; margin-left: .4rem; }
.correction-textarea { font-size: 1.1rem; line-height: 1.6; border-radius: 12px; padding: 14px 16px; resize: none; overflow-y: hidden; background-color: #fff; transition: border-color .2s ease, box-shadow .2s ease; min-height: 60px; }
.correction-textarea:focus { border-color: #d8661b; box-shadow: 0 0 0 3px rgba(216,102,27,0.15) !important; }
.shadow-inner { box-shadow: inset 0 2px 4px rgba(0,0,0,0.06); }
.diff-box { background: #f6f7f9; border: 1px dashed #d6dbe3; border-radius: 10px; padding: .5rem .75rem; display: flex; gap: .5rem; align-items: flex-start; }
.diff-tag { font-size: .6rem; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; color: #8b95a4; background: #e8ebf0; border-radius: 4px; padding: .1rem .35rem; flex-shrink: 0; margin-top: .15rem; }
.diff-text { font-size: .95rem; color: #59626f; line-height: 1.5; word-break: break-word; }

/* ---------- verdict ---------- */
.verdict-btn { transition: all 0.15s ease; font-size: 1.05rem; position: relative; }
.verdict-btn:active { transform: scale(0.98); }
.verdict-kbd { position: absolute; right: .8rem; font-size: .65rem; opacity: .55; }
.reason-chip { font-size: .74rem; border-radius: 999px; padding: .15rem .7rem; }

@keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
.animate-fade-in { animation: fadeIn 0.4s ease-out; }

@media (max-width: 576px) {
  .ref-row { flex-direction: column; gap: .3rem; }
  .ref-label { flex-basis: auto; }
}
</style>
