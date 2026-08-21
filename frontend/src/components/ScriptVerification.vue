<template>
  <div class="sv-wrap">
    <!-- ── metadata: what this recording is, before anything is judged ── -->
    <div class="sv-meta mb-3">
      <div class="d-flex flex-wrap align-items-start gap-2 mb-2">
        <h5 class="fw-bold mb-0 flex-grow-1 sv-title">{{ meta.title || 'Untitled recording' }}</h5>
        <span v-if="props.readonly" class="badge bg-secondary-subtle text-secondary border">
          <i class="bi bi-eye me-1"></i>read-only preview
        </span>
      </div>
      <div class="d-flex flex-wrap gap-1">
        <span v-if="meta.channel" class="badge bg-light text-secondary border rounded-pill px-3 py-2">
          <i class="bi bi-broadcast me-1"></i>{{ meta.channel }}
        </span>
        <span v-if="meta.category" class="badge bg-light text-secondary border rounded-pill px-3 py-2">
          <i class="bi bi-tag me-1"></i>{{ meta.category }}
        </span>
        <span v-if="meta.language" class="badge bg-light text-secondary border rounded-pill px-3 py-2">
          <i class="bi bi-translate me-1"></i>{{ meta.language }}
        </span>
        <span v-if="meta.duration" class="badge bg-light text-secondary border rounded-pill px-3 py-2">
          <i class="bi bi-clock me-1"></i>{{ meta.duration }}
        </span>
        <span v-if="meta.videoId" class="badge bg-light text-secondary border rounded-pill px-3 py-2">
          <i class="bi bi-hash"></i>{{ meta.videoId }}
        </span>
      </div>
    </div>

    <!-- ── audio ── -->
    <div class="sv-player mb-3">
      <audio ref="audioEl" :src="audioSrc" controls preload="none" class="w-100"
             @loadedmetadata="onLoaded" @error="audioFailed = true"></audio>
      <div v-if="audioFailed" class="text-danger small mt-2">
        <i class="bi bi-exclamation-triangle-fill me-1"></i>
        This audio could not be loaded. Please tell the team rather than judging the script without it.
      </div>
      <div class="d-flex flex-wrap align-items-center gap-2 mt-2">
        <span class="text-muted small me-1">Speed</span>
        <button v-for="r in rates" :key="r" type="button"
                class="btn btn-sm rounded-pill px-3"
                :class="rate === r ? 'btn-dark' : 'btn-outline-secondary'"
                @click="setRate(r)">{{ r }}×</button>
      </div>
    </div>

    <!-- ── the script: reference only, never editable ── -->
    <div class="d-flex align-items-center gap-2 mb-2">
      <span class="badge bg-primary-subtle text-primary fs-8 text-uppercase tracking-wide">
        <i class="bi bi-file-text me-1"></i>Script (read-only)
      </span>
      <span class="text-muted fs-9">Does this script match what is spoken?</span>
    </div>
    <div class="sv-script mb-4" dir="ltr" lang="ur">{{ script }}</div>

    <!-- ── comment: required, so the decision always carries a reason ── -->
    <div class="mb-4">
      <label class="form-label small text-uppercase fw-bold text-primary mb-2" for="sv-comment">
        Comments <span class="text-danger">*</span>
      </label>
      <textarea id="sv-comment" v-model="comment" rows="3" class="form-control"
                :class="{ 'is-invalid': showCommentError }"
                :disabled="props.readonly"
                :placeholder="props.readonly ? '' : 'Say what you found — required for both Accept and Reject.'"
                spellcheck="false" @input="showCommentError = false"></textarea>
      <div v-if="showCommentError" class="invalid-feedback d-block">
        Please add a comment before you accept or reject this script.
      </div>
      <div v-else class="form-text">Required. Recorded with your decision.</div>
    </div>

    <!-- ── choose a verdict, then submit it ── -->
    <div v-if="!props.readonly">
      <label class="form-label small text-uppercase fw-bold text-primary mb-2">
        Your verdict <span class="text-danger">*</span>
      </label>
      <div class="sv-actions mb-4">
        <button type="button" class="btn btn-lg rounded-pill px-5 d-flex align-items-center gap-2"
                :class="decision === 'accept' ? 'btn-success' : 'btn-outline-success'"
                :disabled="isSubmitting" @click="choose('accept')">
          <i class="bi bi-check-circle-fill"></i> Accept
        </button>
        <button type="button" class="btn btn-lg rounded-pill px-5 d-flex align-items-center gap-2"
                :class="decision === 'reject' ? 'btn-danger' : 'btn-outline-danger'"
                :disabled="isSubmitting" @click="choose('reject')">
          <i class="bi bi-x-circle-fill"></i> Reject
        </button>
      </div>

      <button type="button" class="btn btn-primary btn-lg rounded-pill px-5 d-flex align-items-center gap-2"
              :disabled="!canSubmit" @click="submit">
        <span v-if="isSubmitting" class="spinner-border spinner-border-sm"></span>
        <i v-else class="bi bi-send-fill"></i>
        Submit
      </button>
      <p v-if="!canSubmit && !isSubmitting" class="text-muted fs-9 mt-2 mb-0">
        <i class="bi bi-info-circle me-1"></i>{{ blockedReason }}
      </p>
    </div>
    <div v-else>
      <div v-if="decision" class="mb-2">
        <span class="badge rounded-pill px-3 py-2"
              :class="decision === 'accept' ? 'bg-success' : 'bg-danger'">
          <i :class="decision === 'accept' ? 'bi bi-check-circle-fill' : 'bi bi-x-circle-fill'"
             class="me-1"></i>{{ decision === 'accept' ? 'Accepted' : 'Rejected' }}
        </span>
      </div>
      <div class="alert alert-secondary py-2 mb-0">
        <i class="bi bi-eye me-1"></i>Read-only preview of a submitted annotation.
      </div>
    </div>

    <p v-if="submitError" class="text-danger small mt-3 mb-0">
      <i class="bi bi-exclamation-circle me-1"></i>{{ submitError }}
    </p>
    <p class="text-muted fs-9 mt-3 mb-0">
      Shortcuts: <kbd>A</kbd> accept · <kbd>R</kbd> reject ·
      <kbd>Ctrl</kbd>/<kbd>⌘</kbd>+<kbd>Enter</kbd> submit
    </p>
  </div>
</template>

<script setup>
import { handledAuthFailure } from '@/session'
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { API_BASE_URL } from '@/config'

const props = defineProps({
  currentTest: { type: Object, required: true },
  isLastTest: { type: Boolean, default: false },
  test_id: { type: [Number, String], required: true },
  session_id: { type: String, default: null },
  currentIndex: { type: Number, required: true },
  readonly: { type: Boolean, default: false },
})
const emit = defineEmits(['next', 'prev', 'submit-status'])

const audioEl = ref(null)
const audioFailed = ref(false)
const rates = [0.75, 1, 1.25, 1.5]
const rate = ref(1)
const durationSec = ref(0)
const decision = ref('')
const comment = ref('')
const showCommentError = ref(false)
const isSubmitting = ref(false)
const pending = ref('')
const submitError = ref('')
const startTime = ref(Date.now())

const script = computed(() => props.currentTest?.script || '')
const hasComment = computed(() => comment.value.trim().length > 0)
const canSubmit = computed(() =>
  !props.readonly && !!decision.value && hasComment.value && !isSubmitting.value)
const blockedReason = computed(() => {
  if (!decision.value && !hasComment.value) return 'Choose Accept or Reject, and add a comment.'
  if (!decision.value) return 'Choose Accept or Reject.'
  return 'Add a comment.'
})

/** The clip is served from backend/tasks/..., which /api/audio already allows. */
const audioSrc = computed(() => {
  const rel = props.currentTest?.audio_filename || ''
  return rel ? `${API_BASE_URL}/audio/${rel}` : ''
})

const meta = computed(() => {
  const t = props.currentTest || {}
  const secs = Number(t.duration_s || durationSec.value || 0)
  const mm = Math.floor(secs / 60)
  const ss = String(Math.round(secs % 60)).padStart(2, '0')
  return {
    title: t.title || '',
    channel: t.channel || '',
    category: t.category || '',
    language: (t.language || '').toUpperCase(),
    videoId: t.video_id || '',
    duration: secs ? `${mm}:${ss}` : '',
  }
})

function onLoaded() {
  durationSec.value = audioEl.value?.duration || 0
  if (audioEl.value) audioEl.value.playbackRate = rate.value
}

function setRate(r) {
  rate.value = r
  if (audioEl.value) audioEl.value.playbackRate = r
}

// A new clip is a fresh judgement: stop the old audio and restart the timer.
watch(() => props.currentTest, () => {
  audioFailed.value = false
  submitError.value = ''
  // A verdict and comment belong to one clip and must never carry over. On an
  // already-answered item -- the admin preview, or revisiting your own work --
  // the saved values come back on the item itself, so show those instead.
  const t = props.currentTest || {}
  decision.value = t.decision || ''
  comment.value = t.comment || ''
  showCommentError.value = false
  durationSec.value = 0
  startTime.value = Date.now()
  if (audioEl.value) {
    audioEl.value.pause()
    audioEl.value.currentTime = 0
  }
})

/** Pick a verdict. Nothing is recorded until Submit. */
function choose(verdict) {
  if (props.readonly || isSubmitting.value) return
  decision.value = verdict
}

async function submit() {
  if (!canSubmit.value) {
    if (!hasComment.value) {
      showCommentError.value = true
      document.getElementById('sv-comment')?.focus()
    }
    return
  }
  const verdict = decision.value
  isSubmitting.value = true
  pending.value = verdict
  submitError.value = ''

  const results = {
    decision: verdict,                       // 'accept' | 'reject'
    video_id: props.currentTest?.video_id || '',
    audio_filename: props.currentTest?.audio_filename || '',
    title: props.currentTest?.title || '',
    channel: props.currentTest?.channel || '',
    category: props.currentTest?.category || '',
    language: props.currentTest?.language || '',
    duration_s: props.currentTest?.duration_s || null,
    script: script.value,
    comment: comment.value.trim(),
  }

  try {
    const token = localStorage.getItem('authToken')
    const response = await fetch(`${API_BASE_URL}/ratings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify({
        test_id: props.test_id,
        session_id: props.session_id,
        results_json: results,
        time_taken_to_submit: Date.now() - startTime.value,
        pageNo_progress: String(props.currentTest.id),
        completion_status: 'completed',
      }),
    })
    if (handledAuthFailure(response)) return
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    emit('submit-status', { index: props.currentIndex, status: 'completed', results })
    emit('next')
  } catch (e) {
    console.error('script-verification submit failed:', e)
    submitError.value = 'Could not save that decision. Please try again.'
  } finally {
    isSubmitting.value = false
    pending.value = ''
  }
}

function onKeydown(e) {
  if (props.readonly || isSubmitting.value) return
  const tag = document.activeElement?.tagName
  const typing = tag === 'INPUT' || tag === 'TEXTAREA'
  // Ctrl/Cmd+Enter still submits from inside the comment box; bare A / R must
  // not, or they would be swallowed as text.
  if (typing && !((e.ctrlKey || e.metaKey) && e.key === 'Enter')) return
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); submit(); return }
  if (e.key === 'a' || e.key === 'A') { e.preventDefault(); choose('accept') }
  if (e.key === 'r' || e.key === 'R') { e.preventDefault(); choose('reject') }
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onUnmounted(() => window.removeEventListener('keydown', onKeydown))
</script>

<style scoped>
.sv-wrap { max-width: 900px; margin: 0 auto; }
.sv-title { line-height: 1.35; }
.sv-meta {
  background: #f8f9fa;
  border: 1px solid #e9ecef;
  border-radius: .75rem;
  padding: 1rem 1.15rem;
}
.sv-player {
  background: #fff;
  border: 1px solid #e9ecef;
  border-radius: .75rem;
  padding: 1rem 1.15rem;
}
.sv-script {
  background: #fff;
  border: 1px solid #e9ecef;
  border-left: 4px solid var(--bs-primary, #0d6efd);
  border-radius: .75rem;
  padding: 1.15rem 1.25rem;
  font-size: 1.2rem;
  line-height: 2.1;
  max-height: 46vh;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
  /* reference material, so it cannot be selected into and edited by accident */
  user-select: text;
}
.sv-actions { display: flex; flex-wrap: wrap; gap: .75rem; }
.fs-8 { font-size: .75rem; }
.fs-9 { font-size: .7rem; }
.tracking-wide { letter-spacing: .04em; }
</style>
