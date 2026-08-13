<template>
  <div class="tc-wrap">
    <!-- Clip header -->
    <header class="tc-head">
      <div class="tc-head-main">
        <span class="tc-index">Clip {{ currentIndex + 1 }}</span>
        <h2 class="tc-title" :title="clip.title">{{ clip.title || clip.fileLabel }}</h2>
      </div>
      <div class="tc-meta">
        <span class="tc-chip"><i class="bi bi-collection"></i>{{ clip.domain }}</span>
        <span class="tc-chip"><i class="bi bi-person-video2"></i>{{ clip.speaker }}</span>
        <span class="tc-chip"><i class="bi bi-clock"></i>{{ fmt(clip.duration) }}</span>
        <span class="tc-chip"><i class="bi bi-list-ol"></i>{{ rows.length }} lines</span>
      </div>
    </header>

    <!-- Player: sticks to the top so it stays reachable through a 69-line transcript -->
    <section class="tc-player">
      <audio ref="audioEl" :src="audioUrl" preload="metadata"
             @timeupdate="onTime" @loadedmetadata="onMeta" @ended="playing = false"></audio>

      <div class="tc-player-row">
        <button type="button" class="tc-play" :disabled="!audioUrl" @click="toggle">
          <i class="bi" :class="playing ? 'bi-pause-fill' : 'bi-play-fill'"></i>
        </button>

        <button type="button" class="tc-skip" title="Back 5s" @click="nudge(-5)">
          <i class="bi bi-arrow-counterclockwise"></i><span>5</span>
        </button>
        <button type="button" class="tc-skip" title="Forward 5s" @click="nudge(5)">
          <i class="bi bi-arrow-clockwise"></i><span>5</span>
        </button>

        <span class="tc-time">{{ fmt(currentTime) }}</span>
        <input class="tc-seek" type="range" min="0" :max="durationSec || 0" step="0.01"
               :value="currentTime" @input="seek($event.target.value)" />
        <span class="tc-time tc-time-total">{{ fmt(durationSec) }}</span>

        <div class="tc-rates">
          <button v-for="r in RATES" :key="r" type="button" class="tc-rate"
                  :class="{ active: rate === r }" @click="setRate(r)">{{ r }}×</button>
        </div>
      </div>
    </section>

    <!-- Progress strip -->
    <div class="tc-progress">
      <span class="tc-progress-label">
        <b>{{ changedCount }}</b> of {{ rows.length }} lines edited
      </span>
      <div class="tc-progress-bar"><span :style="{ width: pct + '%' }"></span></div>
      <button v-if="changedCount" type="button" class="tc-reset" :disabled="readonly"
              @click="resetAll">
        <i class="bi bi-arrow-counterclockwise"></i> Reset all
      </button>
    </div>

    <!-- Transcript: one row per line, original above the editable field -->
    <section class="tc-lines">
      <div v-for="(row, i) in rows" :key="i" class="tc-line" :class="{ edited: row.text !== row.original }">
        <div class="tc-line-no">{{ i + 1 }}</div>
        <div class="tc-line-body">
          <p v-if="row.text !== row.original" class="tc-original" :title="row.original">
            <span class="tc-original-tag">was</span>{{ row.original || '—' }}
          </p>
          <textarea
            class="tc-input"
            :class="{ 'is-blank': !row.text.trim() }"
            :value="row.text"
            :readonly="readonly"
            rows="1"
            :aria-label="`Line ${i + 1}`"
            @input="onInput(i, $event)"
            @focus="focused = i"
            @blur="focused = null"
          ></textarea>
        </div>
        <button type="button" class="tc-revert" :disabled="readonly || row.text === row.original"
                title="Revert this line" @click="revert(i)">
          <i class="bi bi-arrow-counterclockwise"></i>
        </button>
      </div>
    </section>

    <!-- Actions -->
    <footer v-if="!readonly" class="tc-actions">
      <button type="button" class="btn btn-outline-secondary" :disabled="currentIndex === 0"
              @click="$emit('prev')">
        <i class="bi bi-chevron-left me-1"></i>Previous
      </button>
      <span class="tc-actions-spacer"></span>
      <button type="button" class="btn btn-outline-dark" :disabled="isSaving || isSubmitting"
              @click="handleSave">
        <span v-if="isSaving" class="spinner-border spinner-border-sm me-1"></span>
        Save draft
      </button>
      <button type="button" class="btn btn-dark" :disabled="isSubmitting || !isValid"
              @click="handleSubmit">
        <span v-if="isSubmitting" class="spinner-border spinner-border-sm me-1"></span>
        {{ isLastTest ? 'Submit & finish' : 'Submit & next' }}
      </button>
    </footer>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { API_BASE_URL } from '@/config'

const RATES = [0.75, 1, 1.25, 1.5]

const props = defineProps({
  currentTest: { type: Object, required: true },
  isLastTest: { type: Boolean, default: false },
  test_id: { type: [Number, String], required: true },
  session_id: { type: String, default: null },
  currentIndex: { type: Number, required: true },
  readonly: { type: Boolean, default: false }
})
const emit = defineEmits(['next', 'prev', 'submit-status'])

const rows = ref([])
const focused = ref(null)
const isSaving = ref(false)
const isSubmitting = ref(false)
const startTime = ref(Date.now())

const audioEl = ref(null)
const playing = ref(false)
const currentTime = ref(0)
const durationSec = ref(0)
const rate = ref(1)

const clip = computed(() => {
  const t = props.currentTest || {}
  const name = String(t.audio_filename || '').split('/').pop() || ''
  return {
    title: t.title || '',
    domain: t.domain || '',
    speaker: t.speaker || '',
    duration: t.duration || 0,
    fileLabel: name.replace(/\.wav$/i, '')
  }
})

const audioUrl = computed(() =>
  props.currentTest?.audio_filename
    ? `${API_BASE_URL}/audio/${props.currentTest.audio_filename.split('/').map(encodeURIComponent).join('/')}`
    : '')

/** Prefer the annotator's saved lines, else the loader's split, else split the raw text. */
function setup() {
  const t = props.currentTest || {}
  const original = Array.isArray(t.lines) && t.lines.length
    ? t.lines
    : String(t.text || '').split('\n')
  const saved = Array.isArray(t.corrected_lines) && t.corrected_lines.length === original.length
    ? t.corrected_lines
    : null
  rows.value = original.map((line, i) => ({
    original: line,
    text: saved ? saved[i] : line
  }))
  startTime.value = Date.now()
  currentTime.value = 0
  playing.value = false
  nextTick(sizeAll)
}
watch(() => props.currentTest, setup, { immediate: true })

const changedCount = computed(() => rows.value.filter(r => r.text !== r.original).length)
const pct = computed(() => rows.value.length ? (changedCount.value / rows.value.length) * 100 : 0)
// A transcript with every line blanked is never a real correction.
const isValid = computed(() => rows.value.some(r => r.text.trim().length > 0))

function onInput(i, e) {
  rows.value[i].text = e.target.value
  size(e.target)
}
function revert(i) {
  rows.value[i].text = rows.value[i].original
  nextTick(sizeAll)
}
function resetAll() {
  rows.value.forEach(r => { r.text = r.original })
  nextTick(sizeAll)
}

/** Textareas grow with their content so no line is ever clipped. */
function size(el) {
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${el.scrollHeight}px`
}
function sizeAll() {
  document.querySelectorAll('.tc-input').forEach(size)
}

function toggle() {
  const a = audioEl.value
  if (!a) return
  if (a.paused) { a.play(); playing.value = true } else { a.pause(); playing.value = false }
}
function nudge(sec) {
  const a = audioEl.value
  if (!a) return
  a.currentTime = Math.min(Math.max(0, a.currentTime + sec), durationSec.value || a.duration || 0)
}
function seek(v) {
  const a = audioEl.value
  if (!a) return
  a.currentTime = Number(v)
  currentTime.value = Number(v)
}
function setRate(r) {
  rate.value = r
  if (audioEl.value) audioEl.value.playbackRate = r
}
function onTime() { currentTime.value = audioEl.value?.currentTime || 0 }
function onMeta() {
  durationSec.value = audioEl.value?.duration || props.currentTest?.duration || 0
  if (audioEl.value) audioEl.value.playbackRate = rate.value
}

function fmt(s) {
  const v = Math.max(0, Math.floor(Number(s) || 0))
  return `${String(Math.floor(v / 60)).padStart(2, '0')}:${String(v % 60).padStart(2, '0')}`
}

function buildResults() {
  const lines = rows.value.map(r => r.text)
  return {
    id: props.currentTest.id,
    audio_filename: props.currentTest.audio_filename,
    original_text: rows.value.map(r => r.original).join('\n'),
    text: lines.join('\n'),
    corrected_lines: lines,
    lines_changed: changedCount.value,
    n_lines: lines.length,
    language: props.currentTest.language || 'hi'
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

async function handleSave() {
  if (props.readonly || isSaving.value) return
  isSaving.value = true
  try {
    const r = await post('draft')
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    emit('submit-status', { index: props.currentIndex, status: 'draft', results: buildResults() })
  } catch (e) {
    console.error(e)
    alert(`Could not save the draft (${e.message}). Your text is still on screen — try again.`)
  } finally { isSaving.value = false }
}

async function handleSubmit() {
  if (props.readonly || isSubmitting.value || !isValid.value) return
  isSubmitting.value = true
  try {
    const r = await post('completed')
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    emit('submit-status', { index: props.currentIndex, status: 'completed', results: buildResults() })
    emit('next')
  } catch (e) {
    console.error(e)
    alert(`Could not submit (${e.message}). Your text is still on screen — try again.`)
  } finally { isSubmitting.value = false }
}
</script>

<style scoped>
.tc-wrap {
  --tc-line: #e6e6ea;
  --tc-muted: #6b7280;
  --tc-accent: #4f46e5;
  max-width: 1080px;
  margin: 0 auto;
  padding: 0 0 2rem;
}

/* Header ------------------------------------------------------------ */
.tc-head { padding: .25rem 0 .75rem; border-bottom: 1px solid var(--tc-line); }
.tc-head-main { display: flex; align-items: baseline; gap: .65rem; flex-wrap: wrap; }
.tc-index {
  font-size: .7rem; font-weight: 700; letter-spacing: .06em; text-transform: uppercase;
  color: #fff; background: var(--tc-accent); border-radius: 999px; padding: .2rem .6rem;
  white-space: nowrap;
}
.tc-title {
  font-size: 1.05rem; font-weight: 600; margin: 0; line-height: 1.4; color: #111827;
  overflow-wrap: anywhere;
}
.tc-meta { display: flex; flex-wrap: wrap; gap: .4rem; margin-top: .55rem; }
.tc-chip {
  display: inline-flex; align-items: center; gap: .35rem;
  font-size: .74rem; color: var(--tc-muted);
  background: #f4f4f6; border-radius: 6px; padding: .2rem .5rem;
}

/* Player ------------------------------------------------------------ */
.tc-player {
  position: sticky; top: 0; z-index: 5;
  background: #fff; border-bottom: 1px solid var(--tc-line);
  padding: .7rem 0;
}
.tc-player-row { display: flex; align-items: center; gap: .55rem; }
.tc-play {
  flex: 0 0 auto; width: 42px; height: 42px; border-radius: 50%;
  border: none; background: #111827; color: #fff; font-size: 1.15rem; line-height: 1;
  display: inline-flex; align-items: center; justify-content: center;
}
.tc-play:disabled { opacity: .4; }
.tc-skip {
  flex: 0 0 auto; border: 1px solid var(--tc-line); background: #fff; color: #374151;
  border-radius: 7px; padding: .3rem .45rem; font-size: .72rem;
  display: inline-flex; align-items: center; gap: .15rem;
}
.tc-skip:hover { background: #f9fafb; }
.tc-time {
  flex: 0 0 auto; font-variant-numeric: tabular-nums; font-size: .78rem;
  color: var(--tc-muted); min-width: 42px; text-align: center;
}
.tc-seek { flex: 1 1 auto; min-width: 0; accent-color: var(--tc-accent); cursor: pointer; }
.tc-rates { flex: 0 0 auto; display: inline-flex; gap: .2rem; }
.tc-rate {
  border: 1px solid var(--tc-line); background: #fff; color: var(--tc-muted);
  border-radius: 6px; padding: .2rem .4rem; font-size: .7rem; font-variant-numeric: tabular-nums;
}
.tc-rate.active { background: #111827; border-color: #111827; color: #fff; }

/* Progress ---------------------------------------------------------- */
.tc-progress { display: flex; align-items: center; gap: .7rem; padding: .7rem 0 .5rem; }
.tc-progress-label { font-size: .76rem; color: var(--tc-muted); white-space: nowrap; }
.tc-progress-bar { flex: 1 1 auto; height: 5px; background: #ececed; border-radius: 999px; overflow: hidden; }
.tc-progress-bar span { display: block; height: 100%; background: var(--tc-accent); transition: width .18s ease; }
.tc-reset {
  border: none; background: none; color: var(--tc-muted); font-size: .74rem;
  display: inline-flex; align-items: center; gap: .25rem; white-space: nowrap;
}
.tc-reset:hover:not(:disabled) { color: #b91c1c; }

/* Lines ------------------------------------------------------------- */
.tc-lines { display: flex; flex-direction: column; }
.tc-line {
  display: grid;
  grid-template-columns: 2.1rem minmax(0, 1fr) 2rem;  /* number | body | revert */
  align-items: start;
  gap: .5rem;
  padding: .45rem .25rem;
  border-bottom: 1px solid #f1f1f3;
}
.tc-line:hover { background: #fcfcfd; }
.tc-line.edited { background: #fbfaff; }
.tc-line-no {
  font-size: .72rem; color: #9ca3af; font-variant-numeric: tabular-nums;
  text-align: right; padding-top: .5rem;
}
.tc-line.edited .tc-line-no { color: var(--tc-accent); font-weight: 700; }
.tc-line-body { min-width: 0; }
.tc-original {
  margin: 0 0 .25rem; font-size: .78rem; color: #9ca3af; line-height: 1.45;
  overflow-wrap: anywhere;
}
.tc-original-tag {
  display: inline-block; font-size: .62rem; font-weight: 700; text-transform: uppercase;
  letter-spacing: .05em; color: #b45309; background: #fef3c7;
  border-radius: 4px; padding: 0 .3rem; margin-right: .4rem;
}
.tc-input {
  display: block; width: 100%;
  border: 1px solid transparent; border-radius: 7px;
  background: transparent; padding: .35rem .5rem;
  font-size: .95rem; line-height: 1.6; color: #111827;
  resize: none; overflow: hidden;
}
.tc-input:hover:not([readonly]) { border-color: var(--tc-line); background: #fff; }
.tc-input:focus {
  outline: none; border-color: var(--tc-accent); background: #fff;
  box-shadow: 0 0 0 3px rgba(79, 70, 229, .12);
}
.tc-input.is-blank { background: #fef2f2; border-color: #fecaca; }
.tc-revert {
  border: none; background: none; color: #c7c7cc; font-size: .8rem;
  padding: .45rem .2rem; line-height: 1;
}
.tc-revert:hover:not(:disabled) { color: #b91c1c; }
.tc-revert:disabled { opacity: 0; pointer-events: none; }

/* Actions ----------------------------------------------------------- */
.tc-actions {
  position: sticky; bottom: 0;
  display: flex; align-items: center; gap: .5rem;
  padding: .8rem 0; margin-top: .5rem;
  background: linear-gradient(to top, #fff 72%, rgba(255, 255, 255, 0));
  border-top: 1px solid var(--tc-line);
}
.tc-actions-spacer { flex: 1 1 auto; }

@media (max-width: 640px) {
  .tc-player-row { flex-wrap: wrap; row-gap: .5rem; }
  .tc-seek { order: 10; flex-basis: 100%; }
  .tc-rates { margin-left: auto; }
  .tc-line { grid-template-columns: 1.6rem minmax(0, 1fr) 1.75rem; gap: .35rem; }
}
</style>
