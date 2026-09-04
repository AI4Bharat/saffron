<template>
  <div>
    <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
      <div>
        <h3 class="fw-bold text-dark m-0 fs-5">
          <i class="bi bi-sliders me-2 text-primary"></i>MDFS scores
        </h3>
        <p class="text-muted text-xs mb-0">
          Every rating on record, one column per annotator. Each prompt is rated
          by {{ data.target || 3 }} people independently &mdash; they cannot see
          each other's scores.
        </p>
      </div>
      <div class="d-flex flex-wrap gap-2 align-items-center">
        <select v-model="language" class="form-select form-select-sm w-auto" @change="load(1)">
          <option value="">All languages</option>
          <option v-for="l in data.languages || []" :key="l.language" :value="l.language">
            {{ l.language }}
          </option>
        </select>
        <div class="form-check form-check-inline mb-0">
          <input id="mdfs-complete" v-model="onlyComplete" class="form-check-input"
                 type="checkbox" @change="load(1)">
          <label class="form-check-label text-xs" for="mdfs-complete">
            fully rated only
          </label>
        </div>
        <button class="btn btn-sm btn-outline-secondary" :disabled="loading" @click="load(page)">
          <span v-if="loading" class="spinner-border spinner-border-sm"></span>
          <i v-else class="bi bi-arrow-clockwise"></i>
        </button>
        <button class="btn btn-sm btn-success" @click="exportCsv">
          <i class="bi bi-file-earmark-spreadsheet me-1"></i>Export scores (CSV)
        </button>
      </div>
    </div>

    <div v-if="error" class="alert alert-danger py-2 px-3 small">{{ error }}</div>

    <!-- how far along the whole project is -->
    <div class="row g-2 mb-3">
      <div class="col-6 col-md-3">
        <div class="border rounded-3 p-2 bg-light h-100">
          <div class="text-muted text-xs text-uppercase fw-bold">Prompts</div>
          <div class="fs-5 fw-bold">{{ (data.totals?.items || 0).toLocaleString() }}</div>
        </div>
      </div>
      <div class="col-6 col-md-3">
        <div class="border rounded-3 p-2 bg-light h-100">
          <div class="text-muted text-xs text-uppercase fw-bold">Rated at least once</div>
          <div class="fs-5 fw-bold">{{ (data.totals?.rated || 0).toLocaleString() }}</div>
        </div>
      </div>
      <div class="col-6 col-md-3">
        <div class="border rounded-3 p-2 bg-success-subtle h-100">
          <div class="text-muted text-xs text-uppercase fw-bold">
            Fully rated ({{ data.target || 3 }}/{{ data.target || 3 }})
          </div>
          <div class="fs-5 fw-bold text-success-emphasis">
            {{ (data.totals?.complete || 0).toLocaleString() }}
          </div>
        </div>
      </div>
      <div class="col-6 col-md-3">
        <div class="border rounded-3 p-2 bg-light h-100">
          <div class="text-muted text-xs text-uppercase fw-bold">Ratings collected</div>
          <div class="fs-5 fw-bold">{{ (data.totals?.annotations || 0).toLocaleString() }}</div>
        </div>
      </div>
    </div>

    <!-- per language -->
    <div class="table-responsive border rounded mb-4">
      <table class="table table-sm align-middle mb-0">
        <thead class="table-light">
          <tr>
            <th>Language</th>
            <th class="text-end">Prompts</th>
            <th class="text-end">Fully rated</th>
            <th style="width:130px">Progress</th>
            <th v-for="d in data.dimensions || []" :key="d" class="text-end text-capitalize">
              {{ d }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="l in data.languages || []" :key="l.language">
            <td class="fw-semibold">{{ l.language }}</td>
            <td class="text-end">{{ l.items.toLocaleString() }}</td>
            <td class="text-end">{{ l.complete.toLocaleString() }}</td>
            <td>
              <div class="progress" style="height:6px">
                <div class="progress-bar bg-success" :style="{ width: l.progress + '%' }"></div>
              </div>
              <span class="text-muted fs-9">{{ l.progress }}%</span>
            </td>
            <td v-for="d in data.dimensions || []" :key="d" class="text-end">
              <span :class="scoreClass(l.average?.[d])">{{ fmt(l.average?.[d]) }}</span>
            </td>
          </tr>
          <tr v-if="!(data.languages || []).length">
            <td colspan="8" class="text-muted small">Nothing rated yet.</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- prompt by prompt, the annotators side by side -->
    <div class="d-flex align-items-center gap-2 mb-2">
      <h6 class="fw-bold text-uppercase text-muted text-xs mb-0">
        Prompt by prompt
      </h6>
      <span class="text-muted fs-9">
        most disagreement first &mdash;
        <strong>{{ (data.total || 0).toLocaleString() }}</strong> prompt(s)
        <template v-if="anyFilter">match these filters</template>
      </span>
      <button v-if="anyFilter" class="btn btn-link btn-sm p-0 ms-auto fs-9"
              @click="clearFilters">clear filters</button>
    </div>

    <div class="border rounded p-2 mb-2 bg-light">
      <div class="d-flex flex-wrap gap-2 align-items-center">
        <select v-model="f.status" class="form-select form-select-sm w-auto" @change="load(1)">
          <option value="">Any progress</option>
          <option value="unrated">Not rated yet</option>
          <option value="partial">Partly rated</option>
          <option value="complete">Fully rated ({{ data.target || 3 }}/{{ data.target || 3 }})</option>
        </select>

        <select v-model="f.category" class="form-select form-select-sm w-auto" @change="load(1)">
          <option value="">Any status</option>
          <option v-for="c in data.categories || []" :key="c" :value="c">{{ c }}</option>
        </select>

        <select v-model="f.annotator" class="form-select form-select-sm w-auto"
                :disabled="!(data.annotators || []).length" @change="load(1)">
          <option value="">Any annotator</option>
          <option v-for="a in data.annotators || []" :key="a.rater_id" :value="a.rater_id">
            {{ a.name }}
          </option>
        </select>

        <select v-model="f.min_spread" class="form-select form-select-sm w-auto" @change="load(1)">
          <option value="">Any agreement</option>
          <option value="0.5">Some disagreement (≥0.5)</option>
          <option value="1">Clear disagreement (≥1.0)</option>
          <option value="1.5">Wide disagreement (≥1.5)</option>
        </select>

        <select v-model="f.max_mean" class="form-select form-select-sm w-auto" @change="load(1)">
          <option value="">Any score</option>
          <option value="1.5">Weak — mean ≤ 1.5</option>
          <option value="2">Poor — mean ≤ 2.0</option>
          <option value="2.5">Below par — mean ≤ 2.5</option>
        </select>

        <div class="d-flex align-items-center gap-1 flex-grow-1" style="min-width:15rem">
          <i class="bi bi-search text-muted"></i>
          <input v-model="f.q" class="form-control form-control-sm"
                 placeholder="Search the paragraph or clip id"
                 @keyup.enter="load(1)">
          <button class="btn btn-sm btn-outline-secondary" @click="load(1)">Go</button>
        </div>
      </div>
    </div>

    <div v-if="!(data.rows || []).length && !loading"
         class="border rounded text-center text-muted small py-5">
      Nothing matches. Ratings appear here as annotators submit them.
    </div>

    <div v-for="r in data.rows || []" :key="r.item_id"
         class="border rounded mb-2 score-card" :class="{ 'border-danger-subtle': r.spread >= 1 }">
      <div class="row g-0">

        <!-- what was read -->
        <div class="col-12 col-lg-5 p-3 border-end">
          <div class="d-flex align-items-center gap-2 mb-2">
            <span class="badge bg-dark-subtle text-dark">{{ r.language }}</span>
            <span v-if="r.category" class="badge"
                  :class="r.category === 'tts_failed' ? 'bg-danger-subtle text-danger'
                                                      : 'bg-light text-muted'">
              {{ r.category }}
            </span>
            <span class="badge rounded-pill"
                  :class="r.answers >= r.target ? 'bg-success' : 'bg-secondary'">
              {{ r.answers }}/{{ r.target }} rated
            </span>
            <button v-if="r.audio" class="btn btn-sm btn-outline-primary rounded-pill py-0 px-2 ms-auto"
                    @click="play(r)">
              <i class="bi" :class="playingId === r.item_id ? 'bi-pause-fill' : 'bi-play-fill'"></i>
              {{ playingId === r.item_id ? 'stop' : 'listen' }}
            </button>
          </div>
          <div class="small prompt-text">{{ r.text }}</div>
          <div class="text-muted fs-9 mt-2">
            #{{ r.item_id }}<span v-if="r.clip_id"> · {{ r.clip_id }}</span>
          </div>
          <audio v-if="playingId === r.item_id" :src="playing?.url" controls autoplay
                 class="w-100 mt-2" style="height:34px" @ended="playing = null; playingId = null"></audio>
        </div>

        <!-- who gave what -->
        <div class="col-12 col-lg-7 p-3">
          <div v-if="!r.raters.length" class="text-muted small">
            Not rated yet.
          </div>
          <table v-else class="table table-sm mb-0 score-grid">
            <thead>
              <tr>
                <th class="fw-semibold">Annotator</th>
                <th v-for="d in data.dimensions" :key="d"
                    class="text-center text-capitalize fw-semibold">{{ d }}</th>
                <th class="text-center fw-semibold">Mean</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="a in r.raters" :key="a.rater_id">
                <td class="text-truncate" style="max-width:16ch" :title="a.annotator">
                  {{ a.annotator }}
                  <div class="text-muted fs-9">{{ a.submitted_ist }}</div>
                </td>
                <td v-for="d in data.dimensions" :key="d" class="text-center">
                  <span class="badge rounded score-badge" :class="scoreBadge(a.scores[d])">
                    {{ a.scores[d] ?? '–' }}
                  </span>
                </td>
                <td class="text-center fw-semibold">{{ raterMean(a) }}</td>
              </tr>
              <tr class="table-light">
                <td class="fw-semibold">Mean</td>
                <td v-for="d in data.dimensions" :key="d" class="text-center">
                  <span :class="scoreClass(r.mean?.[d])">{{ fmt(r.mean?.[d]) }}</span>
                </td>
                <td class="text-center">
                  <span :title="'How far apart the annotators were'"
                        :class="r.spread >= 1 ? 'text-danger fw-semibold' : 'text-muted'">
                    ±{{ r.spread }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>

          <!-- comments, in full: this is where a low score gets explained -->
          <div v-if="r.raters.some(a => a.comments)" class="mt-2">
            <div v-for="a in r.raters.filter(x => x.comments)" :key="'c' + a.rater_id"
                 class="d-flex gap-2 small mt-1">
              <i class="bi bi-chat-left-quote text-muted mt-1"></i>
              <div>
                <span class="fw-semibold">{{ a.annotator }}:</span>
                <span class="text-muted">{{ a.comments }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="(data.pages || 1) > 1" class="d-flex align-items-center gap-2 mt-2">
      <button class="btn btn-sm btn-outline-secondary" :disabled="page <= 1"
              @click="load(page - 1)">Previous</button>
      <span class="text-muted small">Page {{ page }} of {{ data.pages }}</span>
      <button class="btn btn-sm btn-outline-secondary" :disabled="page >= data.pages"
              @click="load(page + 1)">Next</button>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { API_BASE_URL } from '@/config'
import { api, authToken } from '@/session'

const props = defineProps({ teamKey: { type: String, default: 'asr' } })

const data = ref({})
const loading = ref(false)
const error = ref('')
const language = ref('')
const onlyComplete = ref(false)
const page = ref(1)
const f = ref({ status: '', category: '', annotator: '', min_spread: '', max_mean: '', q: '' })
const anyFilter = computed(() => Object.values(f.value).some(v => v !== '' && v !== null))

function clearFilters() {
  f.value = { status: '', category: '', annotator: '', min_spread: '', max_mean: '', q: '' }
  load(1)
}

/** Only the cuts that are actually set, so the URL stays readable. */
function filterParams() {
  const qs = new URLSearchParams()
  for (const [k, v] of Object.entries(f.value)) {
    if (v !== '' && v !== null && v !== undefined) qs.set(k, String(v))
  }
  return qs
}
const playing = ref(null)
const playingId = ref(null)

async function load(p = 1) {
  loading.value = true
  error.value = ''
  try {
    const qs = filterParams()
    qs.set('team', props.teamKey)
    qs.set('page', String(p))
    qs.set('limit', '200')
    if (language.value) qs.set('language', language.value)
    if (onlyComplete.value) qs.set('complete', '1')
    data.value = await api(`/pool/admin/mdfs/scores?${qs}`)
    page.value = data.value.page || p
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function exportCsv() {
  error.value = ''
  try {
    // the export takes the same cuts, so it matches the table
    const qs = filterParams()
    qs.set('team', props.teamKey)
    if (language.value) qs.set('language', language.value)
    if (onlyComplete.value) qs.set('complete', '1')
    // Fetched with the token in the header, like every other export here; the
    // route does not read a token from the query string.
    const res = await fetch(`${API_BASE_URL}/pool/admin/mdfs/export_csv?${qs}`,
                            { headers: { Authorization: `Bearer ${authToken()}` } })
    if (!res.ok) throw new Error('The server refused the export.')
    const url = URL.createObjectURL(await res.blob())
    const a = document.createElement('a')
    a.href = url
    a.download = `mdfs_scores${language.value ? '_' + language.value.toLowerCase() : ''}.csv`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  } catch (e) {
    error.value = e.message
  }
}

function play(r) {
  if (playingId.value === r.item_id) { playing.value = null; playingId.value = null; return }
  playing.value = { item_id: r.item_id, url: `${API_BASE_URL}/audio/${r.audio}` }
  playingId.value = r.item_id
}

/** One annotator's own average across the four dimensions. */
function raterMean(a) {
  const vals = Object.values(a.scores || {}).filter(v => typeof v === 'number')
  if (!vals.length) return '–'
  return (vals.reduce((x, y) => x + y, 0) / vals.length).toFixed(2)
}

function fmt(v) {
  return (v === null || v === undefined) ? '–' : Number(v).toFixed(2)
}

/** 1 is poor, 4 is fluent -- colour so the weak ones stand out. */
function scoreBadge(v) {
  if (v === null || v === undefined) return 'bg-light text-muted'
  if (v <= 1) return 'bg-danger'
  if (v === 2) return 'bg-warning text-dark'
  if (v === 3) return 'bg-info text-dark'
  return 'bg-success'
}

function scoreClass(v) {
  if (v === null || v === undefined) return 'text-muted'
  return v < 2.5 ? 'text-danger fw-semibold' : 'fw-semibold'
}

onMounted(() => load(1))
</script>

<style scoped>
/* The paragraph is what the rating is about, so it is shown whole. */
.prompt-text {
  line-height: 1.4;
  word-break: break-word;
  white-space: pre-wrap;
}

.score-card { background: #fff; }
.score-card:hover { box-shadow: 0 .2rem .6rem rgba(0,0,0,.06); }
.score-grid th { font-size: .72rem; text-transform: uppercase; color: #6c757d;
                 border-bottom: 1px solid #e9ecef; }
.score-grid td { font-size: .8rem; vertical-align: middle; }
.score-badge { min-width: 1.9rem; display: inline-block; }
</style>
