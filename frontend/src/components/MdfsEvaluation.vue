<template>
  <div>
    <!-- ── the audio being judged ── -->
    <div class="mdfs-player rounded-4 border p-3 mb-3">
      <div class="d-flex flex-wrap align-items-center gap-2 mb-2">
        <span class="badge bg-dark text-white rounded-pill px-3 py-2">
          <i class="bi bi-headphones me-1"></i>Listen, then rate the reading
        </span>
        <div class="ms-auto d-flex align-items-center gap-1">
          <span class="text-muted fs-8 me-1">Speed</span>
          <button v-for="r in rates" :key="r" type="button"
                  class="btn btn-sm rounded-pill speed-btn"
                  :class="rate === r ? 'btn-dark text-white' : 'btn-outline-secondary'"
                  @click="setRate(r)">{{ r }}×</button>
        </div>
      </div>
      <audio ref="player" :src="audioUrl" controls preload="metadata" class="w-100"></audio>
      <div class="mt-3">
        <span class="badge bg-secondary-subtle text-secondary fs-8 text-uppercase tracking-wide mb-1">
          Sentence being read
        </span>
        <p class="mb-0 text-dark fs-5 gold-text" :dir="rtl ? 'rtl' : 'ltr'">{{ item.text }}</p>
      </div>
    </div>

    <!-- ── the four MDFS dimensions, each level with its full description ── -->
    <div v-for="dim in DIMENSIONS" :key="dim.key" class="mdfs-dim rounded-4 border p-3 mb-3">
      <div class="d-flex flex-wrap align-items-baseline gap-2 mb-2">
        <h6 class="fw-bold text-dark mb-0">{{ dim.label }}</h6>
        <span class="text-muted fs-8">{{ dim.hint }}</span>
        <span v-if="modelValue[dim.key]" class="badge rounded-pill ms-auto px-3"
              :class="levelBadge(modelValue[dim.key])">
          {{ modelValue[dim.key] }} — {{ levelName(modelValue[dim.key]) }}
        </span>
        <span v-else class="badge bg-light text-muted border rounded-pill ms-auto px-3">not rated yet</span>
      </div>
      <div class="row g-2">
        <div v-for="lvl in 4" :key="lvl" class="col-12 col-md-6 col-xl-3">
          <button type="button" class="level-card w-100 text-start rounded-3 p-2"
                  :class="{ selected: modelValue[dim.key] === lvl, ['lvl-' + lvl]: true }"
                  @click="pick(dim.key, lvl)">
            <span class="level-num d-inline-grid mb-1">{{ lvl }}</span>
            <span class="level-desc d-block">{{ dim.levels[lvl - 1] }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- optional note -->
    <div class="rounded-4 border p-3">
      <label class="form-label small text-uppercase font-bold tracking-wide text-primary mb-1">
        Comments <span class="text-muted text-lowercase fw-normal">(optional)</span>
      </label>
      <textarea :value="modelValue.comments || ''" rows="2" class="form-control"
                placeholder="Anything unusual about this clip…"
                @input="$emit('update:modelValue', { ...modelValue, comments: $event.target.value })"></textarea>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { API_BASE_URL } from '@/config'

const props = defineProps({
  item: { type: Object, required: true },
  modelValue: { type: Object, required: true },   // { expression, phrasing, smoothness, pacing, comments }
})
const emit = defineEmits(['update:modelValue'])

// The Multidimensional Fluency Scale rubric: every level shown with its full description, so the choice is made against the rubric rather than from memory.
const DIMENSIONS = [
  {
    key: 'expression', label: 'Expression & Volume',
    hint: 'Does it sound like natural language, at a natural volume?',
    levels: [
      'Little expression or enthusiasm. Words are read as if simply to get them out, with little sense of making the text sound like natural language. Quiet voice.',
      'Some expression. Begins to sound like natural language in some areas, but not others. Focus remains largely on saying the words. Still a quiet voice.',
      'Sounds like natural language through most of the passage, with occasional slips into expressionless reading. Voice volume is appropriate throughout.',
      'Good enthusiasm throughout. Sounds like natural language; expression and volume vary to match the reader’s interpretation of the passage.',
    ],
  },
  {
    key: 'phrasing', label: 'Phrasing',
    hint: 'Are words grouped into meaningful phrases and sentences?',
    levels: [
      'Monotone with little sense of phrase boundaries; frequent word-by-word reading.',
      'Frequent two- and three-word phrases giving choppy reading; improper stress and intonation that fail to mark the ends of sentences and clauses.',
      'A mixture of run-ons, mid-sentence pauses for breath, and possibly some choppiness; reasonable stress and intonation.',
      'Generally well phrased, mostly in clause and sentence units, with adequate attention to expression.',
    ],
  },
  {
    key: 'smoothness', label: 'Smoothness',
    hint: 'Hesitations, false starts, repetitions and self-corrections.',
    levels: [
      'Frequent extended pauses, hesitations, false starts, sound-outs, repetitions and/or multiple attempts.',
      'Several “rough” spots where extended pauses, hesitations, etc. are frequent and disruptive.',
      'Occasional breaks in smoothness caused by difficulty with specific words and/or structures.',
      'Generally smooth reading with some breaks; word and structure difficulties are resolved quickly, usually through self-correction.',
    ],
  },
  {
    key: 'pacing', label: 'Pacing',
    hint: 'The overall speed and consistency of the reading.',
    levels: [
      'Slow and laborious.',
      'Moderately slow.',
      'An uneven mixture of fast and slow reading.',
      'Consistently conversational.',
    ],
  },
]
const LEVEL_NAMES = ['Poor', 'Fair', 'Good', 'Excellent']

const rates = [0.75, 1, 1.25, 1.5]
const rate = ref(1)
const player = ref(null)

const audioUrl = computed(() => {
  const path = props.item?.extra_json?.audio
  return path ? `${API_BASE_URL}/audio/${path}` : ''
})
const rtl = computed(() =>
  ['urdu', 'arabic', 'sindhi', 'kashmiri'].includes(String(props.item?.language || '').toLowerCase()))

function setRate(r) {
  rate.value = r
  if (player.value) player.value.playbackRate = r
}
// A new clip keeps the chosen speed but starts from the top.
watch(() => props.item?.id, () => {
  if (player.value) {
    player.value.pause()
    player.value.currentTime = 0
    setTimeout(() => { if (player.value) player.value.playbackRate = rate.value }, 0)
  }
})

function pick(key, lvl) {
  emit('update:modelValue', { ...props.modelValue, [key]: props.modelValue[key] === lvl ? null : lvl })
}
function levelName(lvl) { return LEVEL_NAMES[lvl - 1] || '' }
function levelBadge(lvl) {
  return ['bg-danger-subtle text-danger border border-danger-subtle',
          'bg-warning-subtle text-warning-emphasis border border-warning-subtle',
          'bg-info-subtle text-info-emphasis border border-info-subtle',
          'bg-success-subtle text-success border border-success-subtle'][lvl - 1] || ''
}
</script>

<style scoped>
.fs-8 { font-size: .75rem; }
.tracking-wide { letter-spacing: .05em; }
.mdfs-player { background: #f8f9fb; }
.gold-text { line-height: 1.8; }
.speed-btn { font-size: .72rem; padding: .1rem .55rem; }

.mdfs-dim { background: #fff; }
.level-card {
  border: 2px solid #e9ecef; background: #fcfcfd; cursor: pointer;
  min-height: 100%; transition: border-color .12s ease, background .12s ease, transform .12s ease;
}
.level-card:hover { border-color: #adb5bd; transform: translateY(-1px); }
.level-num {
  width: 22px; height: 22px; place-items: center; border-radius: 50%;
  background: #e9ecef; color: #495057; font-size: .78rem; font-weight: 700;
}
.level-desc { font-size: .78rem; line-height: 1.45; color: #495057; }
.level-card.selected { background: #fff; }
.level-card.selected .level-desc { color: #212529; }
.level-card.selected.lvl-1 { border-color: #dc3545; }
.level-card.selected.lvl-2 { border-color: #fd7e14; }
.level-card.selected.lvl-3 { border-color: #0dcaf0; }
.level-card.selected.lvl-4 { border-color: #198754; }
.level-card.selected.lvl-1 .level-num { background: #dc3545; color: #fff; }
.level-card.selected.lvl-2 .level-num { background: #fd7e14; color: #fff; }
.level-card.selected.lvl-3 .level-num { background: #0dcaf0; color: #fff; }
.level-card.selected.lvl-4 .level-num { background: #198754; color: #fff; }
</style>
