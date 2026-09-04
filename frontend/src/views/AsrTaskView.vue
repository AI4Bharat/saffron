<template>
  <div class="container-fluid py-4 page-bg">
    <div class="row">
      <!-- ── Task Explorer (same shell as the TTS task page) ── -->
      <div class="col-lg-4 col-md-5 mb-4">
        <div class="card border-0 shadow-sm sidebar-card">
          <div class="card-header bg-dark text-white py-3 border-0 rounded-top-4">
            <h5 class="mb-0 d-flex align-items-center justify-content-between">
              <span class="d-flex align-items-center">
                <i class="bi bi-grid-fill me-2 text-warning"></i>Task Explorer
              </span>
              <span class="badge bg-warning text-dark fs-8 px-2 py-1 rounded-pill">
                {{ doneCount }}/{{ batchTotal }} Done
              </span>
            </h5>
          </div>

          <div class="card-body p-3">
            <div class="input-group mb-3 search-box">
              <span class="input-group-text bg-light border-0 text-muted"><i class="bi bi-search"></i></span>
              <input v-model="searchQuery" type="text" class="form-control bg-light border-0 shadow-none fs-7"
                     placeholder="Search tasks..." />
              <button v-if="searchQuery" class="btn btn-light border-0 text-muted" @click="searchQuery = ''">
                <i class="bi bi-x-lg"></i>
              </button>
            </div>

            <div class="task-list-wrapper">
              <div v-for="task in filteredTasks" :key="task.id"
                   class="task-item-card p-3 mb-2 rounded-3 cursor-pointer border d-flex align-items-center justify-content-between"
                   :class="{ 'active-task': currentIndex === task.originalIndex,
                             'completed-task': task.done, 'pending-task': !task.done }"
                   @click="jumpTo(task.originalIndex)">
                <div class="d-flex align-items-center text-truncate pe-2">
                  <div class="status-dot-container me-2">
                    <span v-if="task.done" class="status-indicator bg-success shadow-sm"><i class="bi bi-check text-white"></i></span>
                    <span v-else class="status-indicator bg-secondary-subtle border text-muted">{{ task.originalIndex + 1 }}</span>
                  </div>
                  <div class="text-truncate flex-grow-1">
                    <div class="task-title fw-semibold text-truncate text-dark">Task #{{ task.originalIndex + 1 }}</div>
                    <div class="task-id-line text-truncate"><i class="bi bi-hash"></i>ID: {{ task.id }}</div>
                    <span class="task-desc text-muted d-block text-truncate" :dir="rtl(task.language) ? 'rtl' : 'ltr'">
                      {{ trim(task.text, 40) }}
                    </span>
                  </div>
                </div>
                <i class="bi bi-chevron-right text-muted fs-7"></i>
              </div>
              <p v-if="!filteredTasks.length" class="text-muted text-center small py-3 mb-0">
                Nothing matches that search.
              </p>
            </div>
          </div>

          <div class="card-footer bg-white border-0 p-3">
            <router-link :to="workspaceLink" class="btn btn-outline-secondary w-100 rounded-pill">
              <i class="bi bi-arrow-left me-1"></i>Back to my workspace
            </router-link>
          </div>
        </div>
      </div>

      <!-- ── Annotation pane ── -->
      <div class="col-lg-8 col-md-7">
        <!-- progress -->
        <div class="card border-0 shadow-sm rounded-4 mb-3">
          <div class="card-body py-3 px-4">
            <div class="d-flex justify-content-between align-items-center mb-2">
              <span class="fw-semibold text-dark">
                Task {{ currentIndex + 1 }} of {{ items.length }}
                <span class="text-muted fw-normal">· {{ doneCount }} finished this batch</span>
              </span>
              <span class="badge bg-primary-subtle text-primary rounded-pill px-3">{{ progressPct }}%</span>
            </div>
            <div class="progress" style="height: 7px;">
              <div class="progress-bar bg-success" :style="{ width: progressPct + '%' }"></div>
            </div>
          </div>
        </div>

        <div v-if="loading" class="text-center py-5"><span class="spinner-border text-secondary"></span></div>

        <div v-else-if="!items.length" class="card border-0 shadow-sm rounded-4">
          <div class="card-body text-center py-5">
            <i class="bi bi-inbox d-block fs-1 text-muted mb-3"></i>
            <h5 class="fw-bold text-dark">Your queue is empty</h5>
            <p class="text-muted">Pull a new batch of items from your workspace to keep going.</p>
            <router-link :to="workspaceLink" class="btn btn-success rounded-pill px-4">
              <i class="bi bi-download me-1"></i>Get more work
            </router-link>
          </div>
        </div>

        <template v-else-if="current">
          <!-- how to use + shortcuts, same pattern as the TTS pages -->
          <div class="usage-alert shadow-sm mb-3">
            <div class="d-flex justify-content-center">
              <button class="btn btn-primary instruction-btn shadow-sm" type="button"
                      data-bs-toggle="collapse" data-bs-target="#asrGuidelines">
                <i class="bi bi-keyboard me-2"></i>How to Use &amp; Shortcuts (Click to Expand)
              </button>
            </div>
            <div class="collapse mt-3" id="asrGuidelines">
              <div class="card card-body border-0 shadow-inner usage-panel">
                <div class="row g-4">
                  <div class="col-md-6">
                    <h6 class="usage-heading"><i class="bi bi-keyboard me-2"></i>Keyboard shortcuts</h6>
                    <ul class="shortcut-list mb-2">
                      <li><span class="keys"><kbd>Ctrl</kbd><span class="plus">+</span><kbd>Enter</kbd></span><span class="desc">Submit &amp; go to the next prompt</span></li>
                      <li v-if="needDifficulty"><span class="keys"><kbd>1</kbd> <kbd>2</kbd> <kbd>3</kbd></span><span class="desc">Set Easy / Medium / Hard</span></li>
                      <li><span class="keys"><kbd>&uarr;</kbd> <kbd>&darr;</kbd></span><span class="desc">Move between prompts</span></li>
                    </ul>
                    <p class="text-muted fs-9 mb-0">On macOS, use <kbd>⌘ Cmd</kbd> in place of <kbd>Ctrl</kbd>.</p>
                  </div>
                  <div class="col-md-6">
                    <h6 class="usage-heading"><i class="bi bi-mouse2 me-2"></i>Using the interface</h6>
                    <ul class="usage-list">
                      <li>Switch prompts from the <strong>Task Explorer</strong> on the left.</li>
                      <li>Only change the text if it is actually wrong — press <i class="bi bi-arrow-counterclockwise"></i> <strong>Reset</strong> to restore the original.</li>
                      <li>If a prompt cannot be used at all, <strong>Flag</strong> it with a reason instead of labelling it.</li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- metadata chips -->
          <div class="d-flex flex-wrap gap-2 mb-3 align-items-center">
            <span class="badge bg-dark-subtle text-dark border rounded-pill px-3 py-2"><i class="bi bi-hash"></i> {{ current.id }}</span>
            <span class="badge bg-primary-subtle text-primary border border-primary-subtle rounded-pill px-3 py-2">
              <i class="bi bi-list-task me-1"></i>Task #{{ current.task_id }}</span>
            <span class="badge bg-warning-subtle text-warning-emphasis border border-warning-subtle rounded-pill px-3 py-2">
              <i class="bi bi-translate me-1"></i>{{ current.language }}</span>
            <span v-if="current.class" class="badge bg-primary-subtle text-primary border border-primary-subtle rounded-pill px-3 py-2">
              <i class="bi bi-mortarboard me-1"></i>Class {{ current.class }}</span>
            <span v-if="current.category" class="badge bg-success-subtle text-success border border-success-subtle rounded-pill px-3 py-2">
              <i class="bi bi-journal-bookmark me-1"></i>{{ current.category }}</span>
            <span v-if="current.n_words" class="badge bg-secondary-subtle text-secondary border rounded-pill px-3 py-2">
              <i class="bi bi-123 me-1"></i>{{ current.n_words }} words</span>
            <span v-if="current.source" class="badge bg-light text-muted border rounded-pill px-3 py-2">
              source: {{ current.source }}</span>
            <span v-if="current.source_difficulty" class="badge bg-light text-muted border rounded-pill px-3 py-2">
              suggested: {{ current.source_difficulty }}</span>
            <span v-if="!isTextReview" class="badge bg-info-subtle text-info-emphasis border border-info-subtle rounded-pill px-3 py-2">
              <i class="bi bi-tools me-1"></i>{{ current.task_type_label || current.task_type }}</span>
          </div>

          <!-- MDFS audio fluency rating -->
          <div v-if="isMdfs" class="card border-0 shadow-sm rounded-4 bg-white p-3 p-md-4 mb-4">
            <MdfsEvaluation :item="current" v-model="mdfsScores" />
            <!-- flag -->
            <div class="mt-3 d-flex flex-wrap align-items-center gap-2">
              <button class="btn btn-sm btn-outline-warning rounded-pill" @click="flagOpen = !flagOpen">
                <i class="bi bi-flag me-1"></i>This clip can't be rated
              </button>
              <template v-if="flagOpen">
                <select v-model="flagReason" class="form-select form-select-sm w-auto">
                  <option value="">Pick a reason…</option>
                  <option v-for="r in flagReasons" :key="r" :value="r">{{ r }}</option>
                </select>
                <button class="btn btn-sm btn-warning rounded-pill" :disabled="!flagReason || saving" @click="submit(true)">
                  Flag &amp; next
                </button>
              </template>
            </div>
          </div>

          <!-- an item whose kind of work this page does not know how to render yet -->
          <div v-else-if="!isTextReview && !isTranslation" class="card border-0 shadow-sm rounded-4 bg-white p-4 mb-4 text-center">
            <i class="bi bi-puzzle d-block fs-1 text-muted mb-3"></i>
            <h5 class="fw-bold text-dark">This item needs a different tool</h5>
            <p class="text-muted mb-1">
              It is a <strong>{{ current.task_type_label || current.task_type }}</strong> item, and this page
              only handles text review. Skip it for now — your other items are unaffected.
            </p>
            <div class="d-flex justify-content-center gap-2 mt-3">
              <button class="btn btn-outline-secondary rounded-pill px-4" :disabled="items.length < 2" @click="skip">
                <i class="bi bi-skip-forward me-1"></i>Skip this item
              </button>
              <router-link :to="workspaceLink" class="btn btn-outline-primary rounded-pill px-4">
                Back to workspace
              </router-link>
            </div>
          </div>

          <!-- text card -->
          <div v-else class="card border-0 shadow-sm rounded-4 bg-white p-3 p-md-4 mb-4">
            <!-- Translation correction: the English is what the annotator judges
                 against, so it sits above the text and is never editable. -->
            <div v-if="isTranslation && sourceEnglish" class="mb-4">
              <span class="badge bg-primary-subtle text-primary mb-2 fs-8 text-uppercase tracking-wide">
                <i class="bi bi-translate me-1"></i>English source (reference)
              </span>
              <div class="p-3 rounded-3 border-start border-3 border-primary source-en">
                <p class="mb-0 text-dark fs-5 leading-relaxed" dir="ltr">{{ sourceEnglish }}</p>
              </div>
            </div>

            <div class="mb-4">
              <span class="badge bg-secondary-subtle text-secondary mb-2 fs-8 text-uppercase tracking-wide">{{ originalLabel }}</span>
              <div class="p-3 bg-light rounded-3 border-start border-3 border-secondary">
                <p class="mb-0 text-dark fs-5 leading-relaxed" :dir="isRtl ? 'rtl' : 'ltr'">{{ current.original_text }}</p>
              </div>
            </div>

            <div class="translation-edit-wrapper rounded-4 p-3 border">
              <div class="d-flex justify-content-between align-items-center mb-2">
                <label class="form-label mb-0 small text-uppercase font-bold tracking-wide text-primary">
                  {{ editorLabel }}
                </label>
                <button type="button" class="btn btn-sm btn-outline-secondary" title="Reset to the original text"
                        :disabled="!isModified" @click="draftText = current.original_text">
                  <i class="bi bi-arrow-counterclockwise me-1"></i> Reset
                </button>
              </div>
              <textarea ref="textBox" v-model="draftText" v-auto-grow rows="3"
                        class="form-control correction-textarea shadow-inner border-2"
                        :class="{ 'rtl-text': isRtl }" :dir="isRtl ? 'rtl' : 'ltr'"
                        spellcheck="false" @keydown="onTextKeydown"></textarea>
              <div class="d-flex justify-content-between align-items-center mt-2 fs-7">
                <span v-if="isModified" class="text-warning"><i class="bi bi-pencil-fill me-1"></i> Modified</span>
                <span v-else class="text-success-emphasis"><i class="bi bi-check-circle-fill me-1"></i> Original</span>
                <span class="text-muted">{{ draftText.length }} chars</span>
              </div>
            </div>

            <!-- difficulty (shown only when the admin has difficulty labelling switched on) -->
            <div v-if="needDifficulty" class="mt-4">
              <label class="form-label small text-uppercase font-bold tracking-wide text-primary mb-2">
                How hard is this to read aloud?
              </label>
              <div class="d-flex flex-wrap gap-2">
                <button v-for="(d, i) in difficulties" :key="d" type="button"
                        class="btn rounded-pill px-4 py-2 d-flex align-items-center gap-2 difficulty-btn"
                        :class="draftDifficulty === d ? activeDiffClass(d) : 'btn-outline-secondary'"
                        @click="draftDifficulty = d">
                  <kbd class="diff-key">{{ i + 1 }}</kbd>{{ d }}
                </button>
              </div>
            </div>

            <!-- flag -->
            <div class="mt-3 d-flex flex-wrap align-items-center gap-2">
              <button class="btn btn-sm btn-outline-warning rounded-pill" @click="flagOpen = !flagOpen">
                <i class="bi bi-flag me-1"></i>This prompt can't be labelled
              </button>
              <template v-if="flagOpen">
                <select v-model="flagReason" class="form-select form-select-sm w-auto">
                  <option value="">Pick a reason…</option>
                  <option v-for="r in flagReasons" :key="r" :value="r">{{ r }}</option>
                </select>
                <button class="btn btn-sm btn-warning rounded-pill" :disabled="!flagReason || saving" @click="submit(true)">
                  Flag &amp; next
                </button>
              </template>
            </div>
          </div>

          <!-- submit bar (mirrors the TTS one) -->
          <div v-if="isTextReview || isMdfs || isTranslation" class="card border-0 shadow-sm rounded-4 bg-white p-4 mb-5">
            <div class="d-flex flex-column flex-sm-row justify-content-between align-items-center gap-3">
              <button class="btn btn-outline-secondary px-4 py-2 rounded-pill d-flex align-items-center gap-2"
                      :disabled="currentIndex === 0" @click="go(-1)">
                <i class="bi bi-arrow-left-circle-fill"></i> Previous
              </button>
              <div class="d-flex gap-3 w-100 w-sm-auto justify-content-center flex-wrap">
                <button class="btn btn-outline-warning px-4 py-2 rounded-pill d-flex align-items-center gap-2"
                        :disabled="saving || items.length < 2" @click="skip">
                  <i class="bi bi-skip-forward-circle-fill"></i> Later
                </button>
                <button class="btn btn-success px-5 py-2 rounded-pill d-flex align-items-center gap-2 shadow-sm"
                        :disabled="saving || !canSubmit" @click="submit(false)">
                  <span v-if="saving" class="spinner-border spinner-border-sm"></span>
                  <i v-else class="bi bi-cloud-arrow-up-fill"></i>
                  {{ saving ? 'Saving…'
                     : current?.done ? 'Already submitted'
                     : (allDone ? 'Submit & Finish' : 'Submit & Next') }}
                </button>
              </div>
            </div>
            <div v-if="isMdfs && !mdfsComplete" class="text-danger text-center small mt-3">
              <i class="bi bi-exclamation-triangle-fill me-1"></i> Rate all four dimensions before submitting.
            </div>
            <div v-else-if="needDifficulty && !draftDifficulty" class="text-danger text-center small mt-3">
              <i class="bi bi-exclamation-triangle-fill me-1"></i> Pick a difficulty before submitting.
            </div>
            <div class="text-center text-muted mt-3" style="font-size: 0.78rem;">
              Shortcuts: <kbd>Ctrl</kbd>/<kbd>⌘</kbd> + <kbd>Enter</kbd> submit &amp; next<template v-if="needDifficulty"> ·
              <kbd>1</kbd><kbd>2</kbd><kbd>3</kbd> difficulty</template>
            </div>
            <div v-if="toast" class="text-center text-success fw-semibold small mt-2">{{ toast }}</div>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '@/session'
import MdfsEvaluation from '@/components/MdfsEvaluation.vue'

const vAutoGrow = {
  mounted(el) {
    el.style.resize = 'none'; el.style.overflowY = 'hidden'
    const resize = () => { el.style.height = 'auto'; el.style.height = `${el.scrollHeight}px` }
    el.addEventListener('input', resize); setTimeout(resize, 0); el._r = resize
  },
  updated(el) { if (el._r) setTimeout(el._r, 0) },
  unmounted(el) { if (el._r) el.removeEventListener('input', el._r) }
}

const route = useRoute()
// Which pool team this page is working for (from /pool/<teamKey>/task).
const teamKey = computed(() => String(route.params.teamKey || 'asr').toLowerCase())
const workspaceLink = computed(() => `/pool/${teamKey.value}`)
const loading = ref(true)
const items = ref([])
const currentIndex = ref(0)
const draftText = ref('')
const draftDifficulty = ref('')
const flagOpen = ref(false)
const flagReason = ref('')
const saving = ref(false)
const toast = ref('')
const searchQuery = ref('')
const textBox = ref(null)
const difficulties = ref(['Easy', 'Medium', 'Hard'])
const flagReasons = ref([])
// Whether the admin requires a difficulty label: each item carries its own flag (the admin controls it per language / class / category); the team default is the fallback.
const teamNeedDifficulty = ref(true)
const batchTotal = ref(0)
const doneCount = ref(0)
let shownAt = Date.now()

const current = computed(() => items.value[currentIndex.value] || null)
// This page renders the text-review and MDFS tools; an item of any other kind of work gets a graceful notice instead of the wrong editor.
const isTextReview = computed(() =>
  !current.value || (current.value.task_type || 'text-review') === 'text-review')
const isMdfs = computed(() => current.value?.task_type === 'audio-mdfs')
// Translation correction reuses the text editor: the same edit-and-submit path,
// with the English source shown above it as read-only reference.
const isTranslation = computed(() => current.value?.task_type === 'translation-correction')
const sourceEnglish = computed(() => current.value?.extra_json?.source_en || '')
const originalLabel = computed(() =>
  isTranslation.value ? 'Translation as received' : 'Original prompt')
const editorLabel = computed(() => isTranslation.value
  ? 'Corrected ' + (current.value?.language || '') + ' translation — fix anything that misreads the English'
  : 'Prompt text (' + (current.value?.language || '') + ') — edit only if it is wrong')
// One score (1..4) per MDFS dimension, plus an optional comment.
const blankScores = () => ({ expression: null, phrasing: null, smoothness: null,
                             pacing: null, comments: '' })
const mdfsScores = ref(blankScores())
const mdfsComplete = computed(() =>
  ['expression', 'phrasing', 'smoothness', 'pacing'].every(k => mdfsScores.value[k] >= 1))
const isRtl = computed(() => rtl(current.value?.language))
const isModified = computed(() =>
  !!current.value && draftText.value.trim() !== (current.value.original_text || '').trim())
// Difficulty is a text-review question. Numeracy and MDFS never ask it, so they
// are excluded by task type rather than relying on the per-item flag alone -- a
// missing or stale flag must not be able to put these buttons back.
const needDifficulty = computed(() => {
  const it = current.value
  if (!it) return false
  if (it.task_type && it.task_type !== 'text-review') return false
  return it.need_difficulty !== undefined
    ? it.need_difficulty !== false
    : teamNeedDifficulty.value
})
const canSubmit = computed(() => {
  // A task already submitted in this batch is not offered again; the server
  // would refuse a second answer anyway.
  if (current.value?.done) return false
  return isMdfs.value
    ? mdfsComplete.value
    : !!draftText.value.trim() && (!needDifficulty.value || !!draftDifficulty.value)
})
const progressPct = computed(() =>
  batchTotal.value ? Math.round(100 * doneCount.value / batchTotal.value) : 0)

const filteredTasks = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  return items.value
    // `done` is set when the task is submitted, so the list ticks off as you go
    .map((it, i) => ({ ...it, originalIndex: i, done: !!it.done }))
    .filter(t => !q || String(t.id).includes(q) || (t.text || '').toLowerCase().includes(q))
})

/** The next task still to do, starting after the current one and wrapping. */
function nextUnfinished(from) {
  const n = items.value.length
  for (let step = 1; step <= n; step++) {
    const i = (from + step) % n
    if (!items.value[i]?.done) return i
  }
  return -1
}

const allDone = computed(() =>
  items.value.length > 0 && items.value.every(it => it.done))

const RTL_LANGUAGES = ['urdu', 'arabic', 'sindhi', 'kashmiri']
function rtl(lang) { return RTL_LANGUAGES.includes(String(lang || '').toLowerCase()) }
function trim(t, n = 90) {
  const s = (t || '').replace(/\s+/g, ' ').trim()
  return s.length > n ? s.slice(0, n) + '…' : s
}
function activeDiffClass(d) {
  return { Easy: 'btn-success', Medium: 'btn-warning', Hard: 'btn-danger' }[d] || 'btn-primary'
}

function loadDraft() {
  const it = current.value
  draftText.value = it ? (it.text || '') : ''
  draftDifficulty.value = it?.final_difficulty || ''
  // Prefill from an earlier submission when re-opening a done item; blank otherwise.
  mdfsScores.value = { ...blankScores(), ...((it?.extra_json || {}).results || {}) }
  flagOpen.value = false
  flagReason.value = ''
  shownAt = Date.now()
  if (!it || (it.task_type || 'text-review') === 'text-review') {
    nextTick(() => textBox.value?.focus())
  }
}
watch(currentIndex, loadDraft)

function jumpTo(i) { currentIndex.value = i }
function go(delta) {
  const next = currentIndex.value + delta
  if (next >= 0 && next < items.value.length) currentIndex.value = next
}
function skip() {
  if (items.value.length < 2) return
  const [item] = items.value.splice(currentIndex.value, 1)
  items.value.push(item)
  if (currentIndex.value >= items.value.length) currentIndex.value = 0
  loadDraft()
}

async function load() {
  loading.value = true
  try {
    // ?pull=<id> opens exactly the slice the annotator chose in their workspace;
    const pull = route.query.pull ? `&pull_id=${encodeURIComponent(route.query.pull)}` : ''
    const task = route.query.task ? `&task_id=${encodeURIComponent(route.query.task)}` : ''
    const [d, s] = await Promise.all([
      api(`/pool/items?team=${teamKey.value}&scope=open${pull}${task}`),
      api(`/pool/summary?team=${teamKey.value}`),
    ])
    items.value = d.items || []
    difficulties.value = s.difficulties || difficulties.value
    flagReasons.value = s.flag_reasons || []
    teamNeedDifficulty.value = s.difficulty_annotation !== false
    batchTotal.value = items.value.length + (s.completed_today || 0)
    doneCount.value = s.completed_today || 0
    const idx = parseInt(route.query.index, 10)
    currentIndex.value = Number.isInteger(idx) && idx >= 0 && idx < items.value.length ? idx : 0
    loadDraft()
  } finally {
    loading.value = false
  }
}

async function submit(flagged) {
  if (!current.value || saving.value) return
  saving.value = true
  try {
    const body = { item_id: current.value.id, time_taken_ms: Date.now() - shownAt }
    if (flagged) {
      body.is_flagged = true
      body.flag_reason = flagReason.value
    } else if (isMdfs.value) {
      const { expression, phrasing, smoothness, pacing, comments } = mdfsScores.value
      body.results = { expression, phrasing, smoothness, pacing,
                       ...(comments && comments.trim() ? { comments: comments.trim() } : {}) }
    } else {
      body.text = draftText.value
      if (draftDifficulty.value) body.difficulty = draftDifficulty.value
    }
    const resp = await api('/pool/submit', { method: 'POST', body: JSON.stringify(body) })
    // Belt and braces during rollout: the server must echo the stored scores back.
    if (!flagged && isMdfs.value && !(resp?.item?.extra_json?.results)) {
      alert('The server did not store the scores (it may still be running the old version). '
            + 'Please tell the admin before rating more clips.')
      return
    }
    // Keep the task in the list and mark it finished, so the sidebar ticks it
    // off rather than the row disappearing and renumbering everything below.
    const finished = { ...items.value[currentIndex.value], done: true }
    items.value.splice(currentIndex.value, 1, finished)
    doneCount.value += 1

    const nxt = nextUnfinished(currentIndex.value)
    if (nxt >= 0) {
      currentIndex.value = nxt
      shownAt = Date.now()
    }
    loadDraft()
    toast.value = allDone.value
      ? 'That is the whole batch finished'
      : (flagged ? 'Flagged — next task' : 'Saved — next task')
    setTimeout(() => (toast.value = ''), 1800)
  } catch (e) {
    alert(e.message)
  } finally {
    saving.value = false
  }
}

function onTextKeydown(e) {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    e.preventDefault()
    if (canSubmit.value) submit(false)
  }
}
function onGlobalKey(e) {
  const typing = ['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && canSubmit.value) {
    e.preventDefault(); submit(false); return
  }
  if (typing) return
  if (needDifficulty.value && ['1', '2', '3'].includes(e.key)) {
    draftDifficulty.value = difficulties.value[Number(e.key) - 1]
  }
  else if (e.key === 'ArrowDown') go(1)
  else if (e.key === 'ArrowUp') go(-1)
}

onMounted(async () => {
  await load()
  window.addEventListener('keydown', onGlobalKey)
})
onBeforeUnmount(() => window.removeEventListener('keydown', onGlobalKey))
</script>

<style scoped>
.page-bg { background: #f7f8fb; min-height: calc(100vh - 48px); }
.fs-7 { font-size: .85rem; } .fs-8 { font-size: .75rem; } .fs-9 { font-size: .7rem; }
.tracking-wide { letter-spacing: .05em; }
.leading-relaxed { line-height: 1.75; }
.cursor-pointer { cursor: pointer; }

.sidebar-card { position: sticky; top: 1rem; border-radius: 1rem; overflow: hidden; }
.task-list-wrapper { max-height: 60vh; overflow-y: auto; }
.task-item-card { background: #fff; transition: all .15s ease; }
.task-item-card:hover { background: #f8f9fa; transform: translateX(2px); }
.task-item-card.active-task { background: #e7f1ff; border-color: #0d6efd !important; }
.task-item-card.completed-task { opacity: .7; }
.status-indicator { width: 26px; height: 26px; border-radius: 50%; display: grid; place-items: center; font-size: .72rem; font-weight: 700; }
.task-title { font-size: .85rem; }
.task-id-line { font-size: .68rem; color: #adb5bd; }
.task-desc { font-size: .72rem; }

.usage-alert { background: #fff; border-radius: 1rem; padding: 1rem; }
.instruction-btn { border-radius: 2rem; font-size: .85rem; }
.usage-panel { background: #f8f9fa; border-radius: .75rem; }
.usage-heading { font-size: .8rem; font-weight: 700; text-transform: uppercase; letter-spacing: .05em; color: #495057; }
.shortcut-list, .usage-list { list-style: none; padding-left: 0; font-size: .82rem; }
.shortcut-list li { display: flex; gap: .6rem; align-items: center; margin-bottom: .35rem; }
.usage-list li { margin-bottom: .35rem; color: #495057; }
.keys kbd { margin: 0 1px; }
.plus { margin: 0 2px; color: #adb5bd; }

.source-en { background: rgba(13, 110, 253, .04); }
.translation-edit-wrapper { background: #fcfcfd; border-color: #e9ecef !important; }
.correction-textarea { font-size: 1.15rem; line-height: 1.9; border-radius: .75rem; }
.correction-textarea:focus { border-color: #0d6efd; box-shadow: 0 0 0 .2rem rgba(13,110,253,.15); }
.rtl-text { text-align: right; }
.difficulty-btn { font-weight: 600; }
.diff-key { background: rgba(0,0,0,.08); border-radius: .25rem; padding: 0 .3rem; font-size: .72rem; }
</style>
