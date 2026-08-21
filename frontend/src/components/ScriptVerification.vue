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
    <div class="sv-script mb-4" dir="rtl" lang="ur">{{ script }}</div>

    <!-- ── the only decision: accept or reject ── -->
    <div v-if="!props.readonly" class="sv-actions">
      <button type="button" class="btn btn-success btn-lg rounded-pill px-5 d-flex align-items-center gap-2"
              :disabled="isSubmitting" @click="decide('accept')">
        <span v-if="isSubmitting && pending === 'accept'" class="spinner-border spinner-border-sm"></span>
        <i v-else class="bi bi-check-circle-fill"></i> Accept
      </button>
      <button type="button" class="btn btn-danger btn-lg rounded-pill px-5 d-flex align-items-center gap-2"
              :disabled="isSubmitting" @click="decide('reject')">
        <span v-if="isSubmitting && pending === 'reject'" class="spinner-border spinner-border-sm"></span>
        <i v-else class="bi bi-x-circle-fill"></i> Reject
      </button>
    </div>
    <div v-else class="alert alert-secondary py-2 mb-0">
      <i class="bi bi-eye me-1"></i>Read-only preview of a submitted annotation.
    </div>

    <p v-if="submitError" class="text-danger small mt-3 mb-0">
      <i class="bi bi-exclamation-circle me-1"></i>{{ submitError }}
    </p>
    <p class="text-muted fs-9 mt-3 mb-0">
      Shortcuts: <kbd>A</kbd> accept · <kbd>R</kbd> reject
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
const isSubmitting = ref(false)
const pending = ref('')
const submitError = ref('')
const startTime = ref(Date.now())

const script = computed(() => props.currentTest?.script || '')

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
  durationSec.value = 0
  startTime.value = Date.now()
  if (audioEl.value) {
    audioEl.value.pause()
    audioEl.value.currentTime = 0
  }
})

async function decide(verdict) {
  if (props.readonly || isSubmitting.value) return
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
  if (tag === 'INPUT' || tag === 'TEXTAREA') return
  if (e.key === 'a' || e.key === 'A') { e.preventDefault(); decide('accept') }
  if (e.key === 'r' || e.key === 'R') { e.preventDefault(); decide('reject') }
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
.sv-script[dir='rtl'] {
  border-left: 1px solid #e9ecef;
  border-right: 4px solid var(--bs-primary, #0d6efd);
}
.sv-actions { display: flex; flex-wrap: wrap; gap: .75rem; }
.fs-8 { font-size: .75rem; }
.fs-9 { font-size: .7rem; }
.tracking-wide { letter-spacing: .04em; }
</style>
