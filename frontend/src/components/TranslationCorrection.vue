<template>
  <div class="container py-1 w-100 mt-2">
    <!-- Instructions Section -->
    <div class="alert alert-info shadow-sm animate-fade-in" role="alert">
      <div class="d-flex justify-content-center">
        <button
          class="btn btn-primary instruction-btn shadow-sm"
          type="button"
          data-bs-toggle="collapse"
          data-bs-target="#translationGuidelines"
          aria-expanded="false"
          aria-controls="translationGuidelines"
        >
          <i class="bi bi-info-circle me-2"></i>
          Translation Correction Instructions (Click to Expand)
        </button>
      </div>
      <div class="collapse mt-3" id="translationGuidelines">
        <div class="card card-body border-0 shadow-inner">
          <h4 class="mb-3 text-primary">Task Description & Instructions</h4>
          <p class="lead text-secondary fs-6">
            You are performing a translation correction task. Your goal is to review and correct the translations of the conversation between the teacher (<strong>{{ teacherName }}</strong>) and the student (<strong>{{ studentName }}</strong>).
          </p>
          
          <h5 class="mt-3 text-dark"><i class="bi bi-shield-check me-2 text-success"></i>Key Guidelines:</h5>
          <ul class="lh-base">
            <li>
              <strong>Code-Mixed Sentences:</strong> The translations are supposed to be <strong>code-mixed</strong> (i.e., mixing the target language with English terms where natural/common in normal conversation). Ensure the code-mixing is natural and readable.
            </li>
            <li>
              <strong>Grammar Verification:</strong> Check and correct the grammar, spelling, sentence structure, and flow in the target language to make sure it sounds natural and accurate.
            </li>
            <li>
              <strong>Formulas & Equations:</strong> Check any mathematical formulas, variables, symbols, or equations. Make sure the <strong>exact same formula or equation</strong> is preserved identically in the translated output.
            </li>
            <li>
              <strong>Reset & Helper Tools:</strong> Use the <i class="bi bi-arrow-counterclockwise text-secondary"></i> reset button to restore the original translation, or the <i class="bi bi-copy text-secondary"></i> copy button to copy the English text directly into the edit box.
            </li>
          </ul>
        </div>
      </div>
    </div>

    <!-- Pre-Scene Context Card (Editable if pre_scene_en exists) -->
    <div v-if="preSceneEn || preSceneText" class="row justify-content-center mb-4">
      <div class="col-12 col-lg-10">
        <div class="card border-0 shadow-sm scene-card overflow-hidden">
          <div class="card-body p-4">
            <div class="d-flex align-items-center mb-3">
              <div class="scene-icon-container me-3 bg-primary-subtle text-primary rounded-3 p-2">
                <i class="bi bi-film fs-4"></i>
              </div>
              <h5 class="card-title text-uppercase tracking-wider text-secondary small mb-0">Pre-Scene Context</h5>
            </div>

            <!-- English pre-scene -->
            <div v-if="preSceneEn" class="mb-3 p-3 bg-light rounded-3 border-start border-3 border-secondary">
              <span class="badge bg-secondary-subtle text-secondary mb-2 fs-8 uppercase tracking-wide">English Context</span>
              <p class="mb-0 text-dark font-medium italic-text">"{{ preSceneEn }}"</p>
            </div>

            <!-- Translated/Editable pre-scene -->
            <div v-if="preSceneEn" class="mt-3">
              <div class="d-flex justify-content-between align-items-center mb-2">
                <label class="form-label mb-0 small text-uppercase font-bold tracking-wide text-primary">
                  Correct Pre-Scene Translation ({{ languageLabel }})
                </label>
                <div>
                  <button type="button" class="btn btn-sm btn-outline-secondary" :disabled="!isSceneModified('pre_scene')" @click="resetText('pre_scene')">
                    <i class="bi bi-arrow-counterclockwise me-1"></i> Reset
                  </button>
                </div>
              </div>
              <textarea
                v-model="sceneState.pre_scene"
                v-auto-grow
                class="form-control correction-textarea shadow-inner border-2"
                :class="{ 'rtl-text': isRtl }"
                :dir="isRtl ? 'rtl' : 'ltr'"
                rows="2"
                placeholder="Correct pre-scene translation..."
              ></textarea>
              
              <div class="d-flex justify-content-between align-items-center mt-2 fs-7">
                <span v-if="isSceneModified('pre_scene')" class="text-warning">
                  <i class="bi bi-pencil-fill me-1"></i> Modified
                </span>
                <span v-else class="text-success-emphasis">
                  <i class="bi bi-check-circle-fill me-1"></i> Original
                </span>
                <span class="text-muted">{{ sceneState.pre_scene?.length || 0 }} chars</span>
              </div>
            </div>
            <!-- Read-only translation if no English context is provided -->
            <p
              v-else
              class="card-text fs-5 text-dark mb-0 italic-text"
              :class="{ 'rtl-text': isRtl }"
              :dir="isRtl ? 'rtl' : 'ltr'"
            >
              "{{ preSceneText }}"
            </p>
          </div>
        </div>
      </div>
    </div>

    <!-- Chat / Dialogue Stream -->
    <div class="row justify-content-center g-4">
      <div class="col-12 col-lg-10">
        <div class="chat-container p-3 p-md-4 rounded-4 shadow-sm bg-white mb-4">
          <div class="d-flex align-items-center justify-content-between border-bottom pb-3 mb-4">
            <h5 class="text-muted mb-0 d-flex align-items-center">
              <i class="bi bi-chat-left-dots-fill me-2 text-primary"></i>
              Dialogue Flow
            </h5>
            <span class="badge bg-secondary-subtle text-secondary px-3 py-2 rounded-pill fs-7">
              {{ languageLabel }} Mode
            </span>
          </div>

          <!-- Conversation Turns -->
          <div class="dialogue-list">
            <div
              v-for="(turn, idx) in conversationState"
              :key="idx"
              class="dialogue-turn mb-4 pb-4 border-bottom-dashed"
              :class="{ 'focused-turn': activeTurnIndex === idx }"
            >
              <div class="d-flex align-items-start">
                <!-- Speaker Avatar -->
                <div class="speaker-avatar-container text-center me-3" style="width: 65px;">
                  <div 
                    class="avatar shadow-sm mx-auto mb-1 rounded-circle d-flex align-items-center justify-content-center text-white font-bold"
                    :class="getSpeakerAvatarClass(turn.role || turn.speaker)"
                  >
                    <i :class="getSpeakerIcon(turn.role || turn.speaker)"></i>
                  </div>
                </div>

                <!-- Content Area -->
                <div class="flex-grow-1">
                  <!-- Speaker Details Header -->
                  <div class="d-flex align-items-center mb-2 flex-wrap gap-2">
                    <span class="fw-bold text-dark fs-6">{{ getSpeakerInfo(turn).name }}</span>
                    <span 
                      class="badge rounded-pill px-2.5 py-1 fs-9 border-0 d-inline-flex align-items-center"
                      :class="getSpeakerInfo(turn).designation === 'Teacher' ? 'badge-teacher' : 'badge-student'"
                    >
                      <i :class="getSpeakerInfo(turn).designation === 'Teacher' ? 'bi bi-mortarboard-fill me-1' : 'bi bi-person-fill me-1'"></i>
                      {{ getSpeakerInfo(turn).designation }}
                    </span>
                    <span class="badge bg-secondary-subtle text-secondary-emphasis border border-secondary-subtle rounded-pill px-2.5 py-1 fs-9">
                      {{ getTurnPairLabel(idx) }}
                    </span>
                  </div>

                  <!-- English / Original Bubble -->
                  <div class="bubble bubble-en p-3 rounded-4 mb-3 position-relative">
                    <span class="badge bg-light text-dark border position-absolute top-0 end-0 translate-middle-y me-3 px-2 py-1 fs-8 text-uppercase tracking-wide">
                      English
                    </span>
                    <p class="mb-0 text-dark font-medium leading-relaxed">{{ getEnglishText(turn) }}</p>
                  </div>

                  <!-- Translation Correction Box (Only if translation key exists) -->
                  <div v-if="turn._translationKey" class="translation-edit-wrapper mt-3 bg-light-subtle rounded-4 p-3 border">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                      <label class="form-label mb-0 small text-uppercase font-bold tracking-wide text-primary">
                        Correct Translation ({{ languageLabel }})
                      </label>
                      
                      <!-- Turn Utilities -->
                      <div>
                        <button 
                          type="button" 
                          class="btn btn-sm btn-outline-secondary" 
                          title="Reset to Original Translation"
                          :disabled="!isModified(idx)"
                          @click="resetTranslation(idx)"
                        >
                          <i class="bi bi-arrow-counterclockwise me-1"></i> Reset
                        </button>
                      </div>
                    </div>

                    <!-- Text area for edit -->
                    <textarea
                      v-model="turn[turn._translationKey]"
                      v-auto-grow
                      class="form-control correction-textarea shadow-inner border-2"
                      :class="{ 'rtl-text': isRtl }"
                      :dir="isRtl ? 'rtl' : 'ltr'"
                      rows="3"
                      placeholder="Enter the corrected translation here..."
                      @focus="activeTurnIndex = idx"
                      @blur="activeTurnIndex = null"
                    ></textarea>

                    <div class="d-flex justify-content-between align-items-center mt-2 fs-7">
                      <!-- Status Indicator -->
                      <span>
                        <span v-if="isModified(idx)" class="text-warning">
                          <i class="bi bi-pencil-fill me-1"></i> Modified
                        </span>
                        <span v-else class="text-success-emphasis">
                          <i class="bi bi-check-circle-fill me-1"></i> Original
                        </span>
                      </span>
                      <!-- Character count -->
                      <span class="text-muted">
                        {{ turn[turn._translationKey]?.length || 0 }} chars
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Post-Scene Context Card (Editable if post_scene_en exists) -->
    <div v-if="postSceneEn || postSceneText" class="row justify-content-center mb-4">
      <div class="col-12 col-lg-10">
        <div class="card border-0 shadow-sm scene-card overflow-hidden">
          <div class="card-body p-4">
            <div class="d-flex align-items-center mb-3">
              <div class="scene-icon-container me-3 bg-success-subtle text-success rounded-3 p-2">
                <i class="bi bi-film fs-4"></i>
              </div>
              <h5 class="card-title text-uppercase tracking-wider text-secondary small mb-0">Post-Scene Context</h5>
            </div>

            <!-- English post-scene -->
            <div v-if="postSceneEn" class="mb-3 p-3 bg-light rounded-3 border-start border-3 border-secondary">
              <span class="badge bg-secondary-subtle text-secondary mb-2 fs-8 uppercase tracking-wide">English Context</span>
              <p class="mb-0 text-dark font-medium italic-text">"{{ postSceneEn }}"</p>
            </div>

            <!-- Translated/Editable post-scene -->
            <div v-if="postSceneEn" class="mt-3">
              <div class="d-flex justify-content-between align-items-center mb-2">
                <label class="form-label mb-0 small text-uppercase font-bold tracking-wide text-primary">
                  Correct Post-Scene Translation ({{ languageLabel }})
                </label>
                <div>
                  <button type="button" class="btn btn-sm btn-outline-secondary" :disabled="!isSceneModified('post_scene')" @click="resetText('post_scene')">
                    <i class="bi bi-arrow-counterclockwise me-1"></i> Reset
                  </button>
                </div>
              </div>
              <textarea
                v-model="sceneState.post_scene"
                v-auto-grow
                class="form-control correction-textarea shadow-inner border-2"
                :class="{ 'rtl-text': isRtl }"
                :dir="isRtl ? 'rtl' : 'ltr'"
                rows="2"
                placeholder="Correct post-scene translation..."
              ></textarea>
              
              <div class="d-flex justify-content-between align-items-center mt-2 fs-7">
                <span v-if="isSceneModified('post_scene')" class="text-warning">
                  <i class="bi bi-pencil-fill me-1"></i> Modified
                </span>
                <span v-else class="text-success-emphasis">
                  <i class="bi bi-check-circle-fill me-1"></i> Original
                </span>
                <span class="text-muted">{{ sceneState.post_scene?.length || 0 }} chars</span>
              </div>
            </div>
            <!-- Read-only translation if no English context is provided -->
            <p
              v-else
              class="card-text fs-5 text-dark mb-0 italic-text"
              :class="{ 'rtl-text': isRtl }"
              :dir="isRtl ? 'rtl' : 'ltr'"
            >
              "{{ postSceneText }}"
            </p>
          </div>
        </div>
      </div>
    </div>

    <!-- Submit / Navigation Bar -->
    <div class="row justify-content-center mt-4 mb-5 animate-fade-in">
      <div class="col-12 col-lg-10">
        <div class="card border-0 shadow-sm rounded-4 bg-white p-4">
          <div class="d-flex flex-column flex-sm-row justify-content-between align-items-center gap-3">
            
            <!-- Previous Button -->
            <button
              class="btn btn-outline-secondary px-4 py-2.5 rounded-pill d-flex align-items-center gap-2 transition-all hover-translate"
              :disabled="currentIndex === 0"
              @click="$emit('prev')"
            >
              <i class="bi bi-arrow-left-circle-fill"></i>
              Previous Task
            </button>
            
            <!-- Center Actions (Skip / Submit) -->
            <div class="d-flex gap-3 w-100 w-sm-auto justify-content-center flex-wrap">
              <!-- Save Draft Button -->
              <button
                class="btn btn-warning px-4 py-2.5 rounded-pill d-flex align-items-center gap-2 transition-all hover-translate text-dark fw-medium"
                :disabled="isSubmitting || isSaving"
                @click="handleSave"
              >
                <span v-if="isSaving" class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
                <i v-else class="bi bi-bookmark-fill"></i>
                Save Draft
              </button>

              <!-- Skip Button -->
              <button
                class="btn btn-outline-warning px-4 py-2.5 rounded-pill d-flex align-items-center gap-2 transition-all hover-translate"
                :disabled="isSubmitting || isSaving"
                @click="handleSkip"
              >
                <i class="bi bi-skip-forward-circle-fill"></i>
                Skip Task
              </button>
              
              <!-- Submit & Next Button -->
              <button
                class="btn btn-success btn-submit-correction px-5 py-2.5 rounded-pill d-flex align-items-center gap-2 shadow-sm transition-all hover-translate"
                :disabled="isSubmitting || isSaving || !isValid"
                @click="handleSubmit"
              >
                <span v-if="isSubmitting" class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
                <i v-else class="bi bi-cloud-arrow-up-fill"></i>
                {{ isSubmitting ? 'Saving...' : isLastTest ? 'Submit & Finish' : 'Submit & Next' }}
              </button>
            </div>
            
          </div>
          
          <!-- Validation Warning -->
          <div v-if="!isValid" class="text-danger text-center small mt-3">
            <i class="bi bi-exclamation-triangle-fill me-1"></i>
            Please check that all translation fields are completed.
          </div>
          <div class="text-center text-muted mt-3" style="font-size: 0.78rem;">
            Shortcuts: <kbd>Ctrl</kbd>/<kbd>⌘</kbd> + <kbd>Enter</kbd> submit &amp; next ·
            <kbd>Ctrl</kbd>/<kbd>⌘</kbd> + <kbd>S</kbd> save draft
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- Floating Save Draft Button -->
  <div class="position-fixed bottom-0 end-0 m-4 z-3 d-none d-md-block animate-fade-in">
    <button
      class="btn btn-warning shadow rounded-circle d-flex align-items-center justify-content-center floating-save-btn"
      style="width: 56px; height: 56px;"
      title="Save Progress (Draft)"
      :disabled="isSaving || isSubmitting"
      @click="handleSave"
    >
      <span v-if="isSaving" class="spinner-border spinner-border-sm text-dark" role="status" aria-hidden="true"></span>
      <i v-else class="bi bi-bookmark-fill text-dark fs-4"></i>
    </button>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { API_BASE_URL } from '@/config';

// Custom directive to automatically grow textareas and hide scrollbars
const vAutoGrow = {
  mounted(el) {
    el.style.resize = 'none';
    el.style.overflowY = 'hidden';
    const resize = () => {
      el.style.height = 'auto';
      el.style.height = `${el.scrollHeight}px`;
    };
    el.addEventListener('input', resize);
    setTimeout(resize, 0);
    el._autoGrowResize = resize;
  },
  updated(el) {
    if (el._autoGrowResize) {
      setTimeout(el._autoGrowResize, 0);
    }
  },
  unmounted(el) {
    if (el._autoGrowResize) {
      el.removeEventListener('input', el._autoGrowResize);
    }
  }
}

const props = defineProps({
  currentTest: {
    type: Object,
    required: true
  },
  isLastTest: {
    type: Boolean,
    default: false
  },
  test_id: {
    type: [Number, String],
    required: true
  },
  session_id: {
    type: String,
    default: null
  },
  currentIndex: {
    type: Number,
    required: true
  }
})

const emit = defineEmits(['next', 'prev', 'submit-status'])

// Reactive State
const isSubmitting = ref(false)
const isSaving = ref(false)
const startTime = ref(Date.now())
const conversationState = ref([])
const activeTurnIndex = ref(null)

// Scene texts state for correction
const sceneState = ref({
  pre_scene: '',
  _orig_pre_scene: '',
  post_scene: '',
  _orig_post_scene: ''
})

// Watch currentTest to re-initialize state on progress changes
watch(() => props.currentTest, () => {
  setupState()
}, { immediate: true })

// Helper: Setup State
function setupState() {
  startTime.value = Date.now()
  activeTurnIndex.value = null
  
  if (!props.currentTest) return

  // 1. Setup pre_scene and post_scene states
  sceneState.value = {
    pre_scene: props.currentTest.pre_scene || props.currentTest.pre_Scene || '',
    _orig_pre_scene: props.currentTest.pre_scene || props.currentTest.pre_Scene || '',
    post_scene: props.currentTest.post_scene || props.currentTest.post_Scene || '',
    _orig_post_scene: props.currentTest.post_scene || props.currentTest.post_Scene || ''
  }

  // Scroll viewport smoothly to top
  window.scrollTo({ top: 0, behavior: 'smooth' })

  // 2. Setup turns
  const originalTurns = props.currentTest.conversation || props.currentTest.dialogue || props.currentTest.turns
  
  if (Array.isArray(originalTurns)) {
    conversationState.value = originalTurns.map(turn => {
      // Find the translation key inside the turn
      let translationKey = null
      const keys = Object.keys(turn)
      // Check for common translation keys
      const foundKey = keys.find(k => 
        ['translated', 'translation', 'translated_text', 'translated_sentence', 'text_translated', 'target', 'target_text'].includes(k.toLowerCase()) || 
        k.toLowerCase().includes('trans') || 
        k.toLowerCase().includes('target')
      )
      if (foundKey) {
        translationKey = foundKey
      } else if (keys.includes('text')) {
        // If 'text' is present, default to it as the translation key
        translationKey = 'text'
      }

      return {
        ...turn,
        _translationKey: translationKey,
        _originalTranslation: translationKey ? (turn[translationKey] || '') : ''
      }
    })
  } else {
    // Fallback: If it's a single flat translation item instead of dialogue
    let translationKey = null
    const keys = Object.keys(props.currentTest)
    const foundKey = keys.find(k => 
      ['translated', 'translation', 'translated_text', 'translated_sentence', 'text_translated', 'target', 'target_text'].includes(k.toLowerCase()) || 
      k.toLowerCase().includes('trans') || 
      k.toLowerCase().includes('target')
    )
    if (foundKey) {
      translationKey = foundKey
    }

    const englishText = props.currentTest.english || props.currentTest.original || props.currentTest.text_en || props.currentTest.Sentence || props.currentTest.sentence || ''

    conversationState.value = [{
      role: 'speaker',
      english: englishText,
      [translationKey]: translationKey ? (props.currentTest[translationKey] || '') : '',
      _translationKey: translationKey,
      _originalTranslation: translationKey ? (props.currentTest[translationKey] || '') : ''
    }]
  }
}

// Helper: Get English sentence
function getEnglishText(turn) {
  return turn.english || turn.english_text || turn.original || turn.original_text || turn.en || turn.text_en || ''
}

// Speaker Info Extractor
function getSpeakerInfo(turn) {
  const name = turn.speaker || turn.role || 'Speaker'
  let designation = ''
  
  const lowerName = name.toLowerCase()
  if (lowerName.includes('teacher') || lowerName.includes('instructor') || lowerName.includes('professor') || lowerName.includes('tutor') || lowerName.includes('designation: teacher')) {
    designation = 'Teacher'
  } else if (lowerName.includes('student') || lowerName.includes('learner') || lowerName.includes('pupil') || lowerName.includes('child') || lowerName.includes('designation: student')) {
    designation = 'Student'
  } else {
    const role = (turn.role || '').toLowerCase()
    if (role.includes('teacher') || role.includes('instructor')) {
      designation = 'Teacher'
    } else {
      designation = 'Student'
    }
  }
  return { name, designation }
}

function getTurnPairLabel(idx) {
  if (!conversationState.value || conversationState.value.length === 0) return '';
  const firstTurn = conversationState.value[0];
  const firstDesignation = getSpeakerInfo(firstTurn).designation; // 'Teacher' or 'Student'
  const secondDesignation = firstDesignation === 'Teacher' ? 'Student' : 'Teacher';
  
  const pairName = `${firstDesignation}-${secondDesignation}`;
  const pairNum = Math.floor(idx / 2) + 1;
  return `${pairName} Pair ${pairNum} (Turn ${idx + 1})`;
}

const teacherName = computed(() => {
  const originalTurns = props.currentTest?.conversation || props.currentTest?.dialogue || props.currentTest?.turns || []
  if (Array.isArray(originalTurns)) {
    const turn = originalTurns.find(t => {
      const info = getSpeakerInfo(t)
      return info.designation === 'Teacher'
    })
    if (turn) return getSpeakerInfo(turn).name
  }
  return 'Teacher'
})

const studentName = computed(() => {
  const originalTurns = props.currentTest?.conversation || props.currentTest?.dialogue || props.currentTest?.turns || []
  if (Array.isArray(originalTurns)) {
    const turn = originalTurns.find(t => {
      const info = getSpeakerInfo(t)
      return info.designation === 'Student'
    })
    if (turn) return getSpeakerInfo(turn).name
  }
  return 'Student'
})

// Speaker avatar class
function getSpeakerAvatarClass(role) {
  const r = (role || '').toLowerCase()
  if (r.includes('teacher') || r.includes('instructor')) return 'bg-indigo-avatar'
  if (r.includes('student') || r.includes('learner') || r.includes('pupil')) return 'bg-teal-avatar'
  return 'bg-secondary'
}

// Speaker icons
function getSpeakerIcon(role) {
  const r = (role || '').toLowerCase()
  if (r.includes('teacher') || r.includes('instructor')) return 'bi bi-mortarboard-fill'
  if (r.includes('student') || r.includes('learner') || r.includes('pupil')) return 'bi bi-person-fill'
  return 'bi bi-chat-right-text-fill'
}

// Utilities for turns
function copyEnglish(index) {
  const turn = conversationState.value[index]
  if (turn._translationKey) {
    turn[turn._translationKey] = getEnglishText(turn)
  }
}

function resetTranslation(index) {
  const turn = conversationState.value[index]
  if (turn._translationKey) {
    turn[turn._translationKey] = turn._originalTranslation
  }
}

function isModified(index) {
  const turn = conversationState.value[index]
  if (!turn._translationKey) return false
  return turn[turn._translationKey] !== turn._originalTranslation
}

// Utilities for scene pre/post contexts
function copyText(field) {
  if (field === 'pre_scene') {
    sceneState.value.pre_scene = preSceneEn.value
  } else if (field === 'post_scene') {
    sceneState.value.post_scene = postSceneEn.value
  }
}

function resetText(field) {
  if (field === 'pre_scene') {
    sceneState.value.pre_scene = sceneState.value._orig_pre_scene
  } else if (field === 'post_scene') {
    sceneState.value.post_scene = sceneState.value._orig_post_scene
  }
}

function isSceneModified(field) {
  if (field === 'pre_scene') {
    return sceneState.value.pre_scene !== sceneState.value._orig_pre_scene
  } else if (field === 'post_scene') {
    return sceneState.value.post_scene !== sceneState.value._orig_post_scene
  }
  return false
}

// Computeds
const preSceneEn = computed(() => {
  return props.currentTest?.pre_scene_en || ''
})

const preSceneText = computed(() => {
  return props.currentTest?.pre_scene || props.currentTest?.pre_Scene || props.currentTest?.scene || props.currentTest?.context || ''
})

const postSceneEn = computed(() => {
  return props.currentTest?.post_scene_en || ''
})

const postSceneText = computed(() => {
  return props.currentTest?.post_scene || props.currentTest?.post_Scene || ''
})

const languageLabel = computed(() => {
  const rawLang = props.currentTest?.target_language || props.currentTest?.metadata?.language || props.currentTest?.language || props.currentTest?.lang || ''
  if (!rawLang) return 'Target Language'
  return rawLang.charAt(0).toUpperCase() + rawLang.slice(1)
})

const rtlLanguages = ['urdu', 'arabic', 'hebrew', 'farsi', 'persian', 'sindhi']
const isRtl = computed(() => {
  const rawLang = (props.currentTest?.target_language || props.currentTest?.metadata?.language || props.currentTest?.language || props.currentTest?.lang || '').toLowerCase()
  return rtlLanguages.includes(rawLang)
})

const isValid = computed(() => {
  // Validate pre_scene and post_scene are not empty if they are editable
  if (preSceneEn.value && !sceneState.value.pre_scene.trim()) return false
  if (postSceneEn.value && !sceneState.value.post_scene.trim()) return false

  // Make sure every turn that has a translation field is not left completely blank
  return conversationState.value.every(turn => {
    if (!turn._translationKey) return true
    return (turn[turn._translationKey] || '').trim().length > 0
  })
})

// Skip Action
async function handleSkip() {
  if (isSubmitting.value) return
  isSubmitting.value = true

  const durationMs = Date.now() - startTime.value

  const updatedTurns = conversationState.value.map(turn => {
    const cleanTurn = { ...turn }
    delete cleanTurn._translationKey
    delete cleanTurn._originalTranslation
    return cleanTurn
  })

  let dialogueKey = 'conversation'
  if ('dialogue' in props.currentTest) {
    dialogueKey = 'dialogue'
  } else if ('turns' in props.currentTest) {
    dialogueKey = 'turns'
  }

  const results_json = {
    id: props.currentTest.id,
    pre_scene: sceneState.value.pre_scene || preSceneText.value,
    post_scene: sceneState.value.post_scene || postSceneText.value,
    [dialogueKey]: updatedTurns
  }

  try {
    const token = localStorage.getItem('authToken')
    const response = await fetch(`${API_BASE_URL}/ratings`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        test_id: props.test_id,
        session_id: props.session_id,
        results_json: results_json,
        time_taken_to_submit: durationMs,
        pageNo_progress: String(props.currentTest.id),
        completion_status: 'skipped'
      })
    })

    if (!response.ok) {
      throw new Error('Failed to skip rating')
    }

    emit('submit-status', { index: props.currentIndex, status: 'skipped' })
    emit('next')
  } catch (error) {
    console.error('Error skipping rating:', error)
    alert('Failed to skip. Please check your connection and try again.')
  } finally {
    isSubmitting.value = false
  }
}

// Draft Save
async function handleSave() {
  if (isSaving.value || isSubmitting.value) return
  isSaving.value = true

  const durationMs = Date.now() - startTime.value

  const updatedTurns = conversationState.value.map(turn => {
    const cleanTurn = { ...turn }
    delete cleanTurn._translationKey
    delete cleanTurn._originalTranslation
    return cleanTurn
  })

  let dialogueKey = 'conversation'
  if ('dialogue' in props.currentTest) {
    dialogueKey = 'dialogue'
  } else if ('turns' in props.currentTest) {
    dialogueKey = 'turns'
  }

  const results_json = {
    id: props.currentTest.id,
    pre_scene: sceneState.value.pre_scene || preSceneText.value,
    post_scene: sceneState.value.post_scene || postSceneText.value,
    [dialogueKey]: updatedTurns
  }

  try {
    const token = localStorage.getItem('authToken')
    const response = await fetch(`${API_BASE_URL}/ratings`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        test_id: props.test_id,
        session_id: props.session_id,
        results_json: results_json,
        time_taken_to_submit: durationMs,
        pageNo_progress: String(props.currentTest.id),
        completion_status: 'saved'
      })
    })

    if (!response.ok) {
      throw new Error('Failed to save draft')
    }

    emit('submit-status', { index: props.currentIndex, status: 'saved', results: results_json })
    
    // Display a gentle toast/notification rather than an annoying alert
    const toast = document.createElement('div')
    toast.className = 'position-fixed bottom-0 start-50 translate-middle-x mb-4 bg-dark text-white py-2.5 px-4 rounded-pill shadow-lg z-3 border border-secondary'
    toast.style.transition = 'opacity 0.3s ease'
    toast.innerHTML = '<i class="bi bi-check-circle-fill text-warning me-2"></i> Progress saved successfully!'
    document.body.appendChild(toast)
    setTimeout(() => {
      toast.style.opacity = '0'
      setTimeout(() => toast.remove(), 300)
    }, 2500)
    
  } catch (error) {
    console.error('Error saving draft:', error)
    alert('Failed to save progress. Please check your connection and try again.')
  } finally {
    isSaving.value = false
  }
}

// Submission
async function handleSubmit() {
  if (isSubmitting.value || !isValid.value) return
  isSubmitting.value = true

  const endTime = Date.now()
  const durationMs = endTime - startTime.value

  const updatedTurns = conversationState.value.map(turn => {
    const cleanTurn = { ...turn }
    delete cleanTurn._translationKey
    delete cleanTurn._originalTranslation
    return cleanTurn
  })

  let dialogueKey = 'conversation'
  if ('dialogue' in props.currentTest) {
    dialogueKey = 'dialogue'
  } else if ('turns' in props.currentTest) {
    dialogueKey = 'turns'
  }

  const results_json = {
    id: props.currentTest.id,
    pre_scene: sceneState.value.pre_scene || preSceneText.value,
    post_scene: sceneState.value.post_scene || postSceneText.value,
    [dialogueKey]: updatedTurns
  }

  try {
    const token = localStorage.getItem('authToken')
    const response = await fetch(`${API_BASE_URL}/ratings`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        test_id: props.test_id,
        session_id: props.session_id,
        results_json: results_json,
        time_taken_to_submit: durationMs,
        pageNo_progress: String(props.currentTest.id),
        completion_status: 'completed'
      })
    })

    if (!response.ok) {
      throw new Error('Failed to submit translation ratings')
    }

    emit('submit-status', { index: props.currentIndex, status: 'completed', results: results_json })
    emit('next')
  } catch (error) {
    console.error('Error submitting ratings:', error)
    alert('Failed to submit annotations. Please check your connection and try again.')
  } finally {
    isSubmitting.value = false
  }
}

// Keyboard shortcuts: Ctrl/Cmd+Enter = Submit & Next, Ctrl/Cmd+S = Save Draft.
function onKeydown(e) {
  if (!(e.ctrlKey || e.metaKey)) return
  if (e.key === 'Enter') { e.preventDefault(); if (isValid.value) handleSubmit() }
  else if (e.key.toLowerCase() === 's') { e.preventDefault(); handleSave() }
}
onMounted(() => {
  setupState()
  window.addEventListener('keydown', onKeydown)
})
onUnmounted(() => window.removeEventListener('keydown', onKeydown))
</script>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Arabic:wght@400;500;600;700&family=Noto+Nastaliq+Urdu:wght@400;700&display=swap');

.rtl-text {
  direction: rtl;
  text-align: right;
  font-family: 'Noto Nastaliq Urdu', 'Noto Sans Arabic', 'Inter', sans-serif;
  line-height: 1.8;
}

/* Modern color variables */
.bg-indigo-avatar {
  background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%) !important;
}
.bg-teal-avatar {
  background: linear-gradient(135deg, #14b8a6 0%, #0d9488 100%) !important;
}

/* Speaker Badges */
.badge-teacher {
  background-color: #e0e7ff;
  color: #4338ca;
}
.badge-student {
  background-color: #d1fae5;
  color: #065f46;
}

/* Base chat layout */
.chat-container {
  border: 1px solid rgba(0, 0, 0, 0.08);
  background-color: #fff;
  border-radius: 16px !important;
}

.border-bottom-dashed {
  border-bottom: 1px dashed rgba(0, 0, 0, 0.12);
}
.dialogue-turn:last-child {
  border-bottom: none !important;
  margin-bottom: 0 !important;
  padding-bottom: 0 !important;
}

.avatar {
  width: 44px;
  height: 44px;
  font-size: 1.15rem;
  transition: all 0.3s ease;
}

.dialogue-turn {
  transition: all 0.3s ease;
  border-left: 3px solid transparent;
  padding-left: 10px;
}

.focused-turn {
  border-left-color: #4f46e5;
  background-color: rgba(99, 102, 241, 0.02);
  border-radius: 8px;
}

.focused-turn .avatar {
  transform: scale(1.08);
}

.bubble {
  position: relative;
  background-color: #f8fafc;
  border: 1px solid rgba(0, 0, 0, 0.04);
}

.bubble-en {
  border-top-left-radius: 2px !important;
}

.fs-7 {
  font-size: 0.85rem;
}
.fs-8 {
  font-size: 0.72rem;
}
.fs-9 {
  font-size: 0.75rem;
}

.translation-edit-wrapper {
  background-color: #fcfdfe;
  border-color: rgba(0, 0, 0, 0.06) !important;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.01);
}

.correction-textarea {
  font-size: 1.1rem;
  line-height: 1.6;
  border-radius: 12px;
  padding: 14px 16px;
  resize: none;
  overflow-y: hidden;
  background-color: #fff;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
  min-height: 100px;
}

.correction-textarea:focus {
  border-color: #4f46e5;
  box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.15) !important;
}

.scene-card {
  background: linear-gradient(135deg, rgba(255,255,255,0.9) 0%, rgba(248,250,252,0.9) 100%);
  border-left: 5px solid #3b82f6 !important;
  border-radius: 12px !important;
}

.scene-icon-container {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.italic-text {
  font-style: italic;
  color: #475569;
}

.tracking-wider {
  letter-spacing: 0.08em;
}

.btn-submit-correction {
  border-radius: 30px;
  font-weight: 500;
}

.hover-translate {
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.hover-translate:hover:not(:disabled) {
  transform: translateY(-2px);
}

.shadow-inner {
  box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.06);
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(5px); }
  to { opacity: 1; transform: translateY(0); }
}

.animate-fade-in {
  animation: fadeIn 0.4s ease-out;
}
.floating-save-btn {
  background-color: #ffc107 !important; /* Bootstrap warning yellow */
  border-color: #ffc107 !important;
  transition: all 0.2s ease;
  box-shadow: 0 4px 14px rgba(255, 193, 7, 0.4) !important;
}
.floating-save-btn:hover {
  background-color: #e0a800 !important;
  transform: scale(1.1);
}
</style>
