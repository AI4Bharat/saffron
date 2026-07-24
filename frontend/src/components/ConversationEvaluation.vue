<template>
  <div class="conversation-eval-container animate-fade-in" v-if="currentTest">

    <!-- How to use this page & keyboard shortcuts -->
    <div class="usage-alert shadow-sm">
      <div class="d-flex justify-content-center">
        <button
          class="btn btn-primary instruction-btn shadow-sm"
          type="button"
          data-bs-toggle="collapse"
          data-bs-target="#conversationGuidelines"
          aria-expanded="false"
          aria-controls="conversationGuidelines"
        >
          <i class="bi bi-keyboard me-2"></i>
          How to Use &amp; Shortcuts (Click to Expand)
        </button>
      </div>
      <div class="collapse mt-3" id="conversationGuidelines">
        <div class="card card-body border-0 shadow-inner usage-panel">
          <div class="row g-4">
            <div class="col-md-6">
              <h6 class="usage-heading"><i class="bi bi-keyboard me-2"></i>Keyboard shortcuts</h6>
              <ul class="shortcut-list mb-2">
                <li><span class="keys"><kbd>1</kbd></span><span class="desc">Accept the current turn</span></li>
                <li><span class="keys"><kbd>2</kbd></span><span class="desc">Reject the current turn</span></li>
                <li><span class="keys"><kbd>Ctrl</kbd><span class="plus">+</span><kbd>Enter</kbd></span><span class="desc">Submit &amp; go to the next task</span></li>
                <li><span class="keys"><kbd>Ctrl</kbd><span class="plus">+</span><kbd>S</kbd></span><span class="desc">Save your progress</span></li>
              </ul>
              <p class="text-muted fs-9 mb-0">On macOS, use <kbd>⌘ Cmd</kbd> in place of <kbd>Ctrl</kbd>.</p>
            </div>
            <div class="col-md-6">
              <h6 class="usage-heading"><i class="bi bi-mouse2 me-2"></i>Using the interface</h6>
              <ul class="usage-list">
                <li>Switch between tasks from the <strong>Task Explorer</strong> on the left — each row shows its <strong>number</strong> and <strong>ID</strong>.</li>
                <li>Rate every dialogue turn as <strong>Accept</strong> or <strong>Reject</strong> before submitting.</li>
                <li>The progress bar at the top tracks how many tasks you have completed.</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Meta Information Header -->
    <div class="card border-0 shadow-sm rounded-4 mb-4 bg-white p-4">
      <div class="d-flex flex-column gap-3">
        
        <!-- Pre-Scene Narrative -->
        <div class="pre-scene-box p-3 rounded-3 mb-2">
          <div class="d-flex align-items-start gap-2">
            <i class="bi bi-info-circle-fill text-primary fs-5 mt-0.5"></i>
            <div class="w-100">
              <div class="d-flex justify-content-between align-items-center mb-2">
                <span class="text-uppercase fw-bold text-secondary tracking-wider fs-9">Pre-Scene Narrative</span>
                <button
                  v-if="isEditable"
                  type="button"
                  class="btn btn-sm btn-outline-secondary py-0.5 px-2 fs-9"
                  title="Reset to original pre-scene narrative"
                  :disabled="!isSceneModified('pre_scene')"
                  @click="resetText('pre_scene')"
                >
                  <i class="bi bi-arrow-counterclockwise me-1"></i> Reset
                </button>
              </div>
              <div v-if="isEditable">
                <textarea
                  v-if="editingKey === 'pre_scene'"
                  v-model="sceneState.pre_scene"
                  v-auto-grow
                  v-focus
                  @blur="stopEdit"
                  class="form-control correction-textarea shadow-inner border-2 w-100"
                  rows="2"
                  placeholder="Edit pre-scene narrative..."
                ></textarea>
                <div
                  v-else
                  class="editable-rendered"
                  role="textbox"
                  tabindex="0"
                  title="Click to edit"
                  @click="startEdit('pre_scene')"
                  @focus="startEdit('pre_scene')"
                >
                  <span v-if="(sceneState.pre_scene || '').trim()" v-html="renderMath(sceneState.pre_scene)"></span>
                  <span v-else class="editable-placeholder">Click to edit pre-scene narrative…</span>
                </div>
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
              <p v-else class="mb-0 fs-6 text-dark fw-medium leading-relaxed" v-html="renderMath(currentTest.pre_scene)"></p>
            </div>
          </div>
        </div>

        <!-- Meta Details Grid -->
        <div class="row g-3">
          <div class="col-12 col-md-4">
            <div class="meta-pill-card p-3 rounded-3 text-center border">
              <span class="text-muted fs-8 text-uppercase d-block mb-1">Subject</span>
              <span class="fw-bold text-dark fs-6">{{ cellData.subject || 'N/A' }}</span>
            </div>
          </div>
          <div class="col-12 col-md-4">
            <div class="meta-pill-card p-3 rounded-3 text-center border">
              <span class="text-muted fs-8 text-uppercase d-block mb-1">Grade</span>
              <span class="fw-bold text-dark fs-6">{{ formatGrade(cellData.grade_bucket) || 'N/A' }}</span>
            </div>
          </div>
          <div class="col-12 col-md-4">
            <div class="meta-pill-card p-3 rounded-3 text-center border">
              <span class="text-muted fs-8 text-uppercase d-block mb-1">Persona</span>
              <span class="fw-bold text-dark fs-6">{{ formatPersona(currentTest.teacher_persona) || 'N/A' }}</span>
            </div>
          </div>
        </div>

        <!-- Persona Guidelines -->
        <div v-if="personaGuidelines" class="persona-guidelines-box p-3 rounded-3 border-start-warning">
          <div class="d-flex align-items-start gap-2">
            <i class="bi bi-person-lines-fill text-warning fs-5 mt-0.5"></i>
            <div>
              <span class="text-uppercase fw-bold text-warning-emphasis tracking-wider fs-9 d-block mb-1">Persona Guidelines</span>
              <p class="mb-0 fs-7 text-dark-emphasis">{{ personaGuidelines }}</p>
            </div>
          </div>
        </div>

      </div>
    </div>

    <!-- Dialogue Flow Section -->
    <div class="card border-0 shadow-sm rounded-4 mb-4 bg-white p-4">
      <h3 class="fw-bold text-dark mb-4 d-flex align-items-center gap-2">
        <i class="bi bi-chat-left-dots-fill text-primary"></i>
        Dialogue Evaluation
      </h3>
      
      <div class="dialogue-turns-list">
        <div 
          v-for="(turn, idx) in dialogueTurns" 
          :key="turn.turn_index"
          class="dialogue-row row g-3 align-items-stretch mb-4"
        >
          <!-- Dialogue Speech Bubble -->
          <div :class="turn.speaker === 'teacher' ? 'col-12 col-md-8' : 'col-12'">
            <div 
              class="speech-bubble p-3 rounded-4 shadow-xs transition-all h-100"
              :class="turn.speaker === 'teacher' ? 'teacher-bubble' : 'student-bubble'"
            >
              <div class="d-flex justify-content-between align-items-center mb-2">
                <span class="fw-bold fs-7" :class="turn.speaker === 'teacher' ? 'text-primary' : 'text-success'">
                  {{ getSpeakerName(turn) }} &mdash; {{ turn.speaker === 'teacher' ? 'Teacher' : 'Student' }}
                </span>
                <div class="d-flex align-items-center gap-2">
                  <button
                    v-if="isEditable"
                    type="button"
                    class="btn btn-sm btn-outline-secondary py-0.5 px-2 fs-9"
                    title="Reset to original text"
                    :disabled="!isTurnModified(idx)"
                    @click="resetTurn(idx)"
                  >
                    <i class="bi bi-arrow-counterclockwise me-1"></i> Reset
                  </button>
                  <span class="badge bg-light text-muted border fs-9">Turn {{ turn.turn_index }}</span>
                </div>
              </div>
              <div v-if="isEditable">
                <textarea
                  v-if="editingKey === 'turn:' + idx"
                  v-model="turn.text"
                  v-auto-grow
                  v-focus
                  @blur="stopEdit"
                  class="form-control correction-textarea shadow-inner border-2 w-100"
                  rows="2"
                  placeholder="Edit dialogue text..."
                ></textarea>
                <div
                  v-else
                  class="editable-rendered"
                  role="textbox"
                  tabindex="0"
                  title="Click to edit"
                  @click="startEdit('turn:' + idx)"
                  @focus="startEdit('turn:' + idx)"
                >
                  <span v-if="(turn.text || '').trim()" v-html="renderMath(turn.text)"></span>
                  <span v-else class="editable-placeholder">Click to edit dialogue text…</span>
                </div>
                <div class="d-flex justify-content-between align-items-center mt-2 fs-7">
                  <span v-if="isTurnModified(idx)" class="text-warning">
                    <i class="bi bi-pencil-fill me-1"></i> Modified
                  </span>
                  <span v-else class="text-success-emphasis">
                    <i class="bi bi-check-circle-fill me-1"></i> Original
                  </span>
                  <span class="text-muted">{{ turn.text?.length || 0 }} chars</span>
                </div>
              </div>
              <p v-else class="mb-0 fs-6 text-dark leading-relaxed" v-html="renderMath(turn.text)"></p>
            </div>
          </div>

          <!-- Voice Direction Box for Teacher turns -->
          <div v-if="turn.speaker === 'teacher'" class="col-12 col-md-4">
            <div class="voice-direction-card p-3 rounded-4 border-dashed h-100 d-flex flex-column justify-content-center">
              <div class="d-flex align-items-center gap-2 mb-2">
                <div class="voice-icon-pulse">
                  <i class="bi bi-mic-fill text-primary"></i>
                </div>
                <span class="text-uppercase fw-bold text-primary tracking-wider fs-9">
                  Voice Direction {{ getTeacherTurnNumber(turn.turn_index) }}
                </span>
              </div>
              <p class="mb-0 fs-7 italic-text text-secondary leading-relaxed">
                {{ getVoiceDirection(turn.turn_index) }}
              </p>
            </div>
          </div>

        </div>
      </div>
    </div>

    <!-- Post-Scene Narrative Box -->
    <div v-if="currentTest.post_scene || isEditable" class="card border-0 shadow-sm rounded-4 mb-4 bg-white p-4">
      <div class="post-scene-box p-3 rounded-3 border-start-secondary">
        <div class="d-flex align-items-start gap-2">
          <i class="bi bi-flag-fill text-secondary fs-5 mt-0.5"></i>
          <div class="w-100">
            <div class="d-flex justify-content-between align-items-center mb-2">
              <span class="text-uppercase fw-bold text-secondary tracking-wider fs-9">Post-Scene Narrative</span>
              <button
                v-if="isEditable"
                type="button"
                class="btn btn-sm btn-outline-secondary py-0.5 px-2 fs-9"
                title="Reset to original post-scene narrative"
                :disabled="!isSceneModified('post_scene')"
                @click="resetText('post_scene')"
              >
                <i class="bi bi-arrow-counterclockwise me-1"></i> Reset
              </button>
            </div>
            <div v-if="isEditable">
              <textarea
                v-if="editingKey === 'post_scene'"
                v-model="sceneState.post_scene"
                v-auto-grow
                v-focus
                @blur="stopEdit"
                class="form-control correction-textarea shadow-inner border-2 w-100"
                rows="2"
                placeholder="Edit post-scene narrative..."
              ></textarea>
              <div
                v-else
                class="editable-rendered"
                role="textbox"
                tabindex="0"
                title="Click to edit"
                @click="startEdit('post_scene')"
                @focus="startEdit('post_scene')"
              >
                <span v-if="(sceneState.post_scene || '').trim()" v-html="renderMath(sceneState.post_scene)"></span>
                <span v-else class="editable-placeholder">Click to edit post-scene narrative…</span>
              </div>
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
            <p v-else class="mb-0 fs-6 text-dark fw-medium leading-relaxed" v-html="renderMath(currentTest.post_scene)"></p>
          </div>
        </div>
      </div>
    </div>

    <!-- Conversation Evaluation Block -->
    <div class="card border-0 shadow-sm rounded-4 mb-4 bg-white p-4">
      <h3 class="fw-bold text-dark mb-3 d-flex align-items-center gap-2">
        <i class="bi bi-clipboard-check-fill text-success"></i>
        Conversation Evaluation
      </h3>
      <p class="text-secondary fs-7 mb-4">Please label the entire dialogue below as a single Accept/Reject choice.</p>

      <div class="row g-3 mb-4 justify-content-center">
        <!-- Accept Button -->
        <div class="col-12 col-sm-6 col-md-5">
          <button 
            type="button" 
            class="btn evaluation-choice-btn w-100 py-3 rounded-4 border-2 transition-all d-flex align-items-center justify-content-center gap-2"
            :class="evaluation === 'accept' ? 'btn-success-selected' : 'btn-outline-success'"
            @click="selectEvaluation('accept')"
          >
            <i class="bi" :class="evaluation === 'accept' ? 'bi-check-circle-fill' : 'bi-check-circle'"></i>
            <span class="fw-bold">Accept</span>
            <span class="badge bg-success text-white rounded-pill fs-9 ms-1 font-monospace">1</span>
          </button>
        </div>

        <!-- Reject Button -->
        <div class="col-12 col-sm-6 col-md-5">
          <button 
            type="button" 
            class="btn evaluation-choice-btn w-100 py-3 rounded-4 border-2 transition-all d-flex align-items-center justify-content-center gap-2"
            :class="evaluation === 'reject' ? 'btn-danger-selected' : 'btn-outline-danger'"
            @click="selectEvaluation('reject')"
          >
            <i class="bi" :class="evaluation === 'reject' ? 'bi-x-circle-fill' : 'bi-x-circle'"></i>
            <span class="fw-bold">Reject</span>
            <span class="badge bg-danger text-white rounded-pill fs-9 ms-1 font-monospace">2</span>
          </button>
        </div>
      </div>

      <!-- Annotation Reason / Comments -->
      <div class="mb-3">
        <label for="annotationReason" class="form-label fw-bold text-dark-emphasis mb-2 d-flex justify-content-between">
          <span>Annotation Reason</span>
          <span class="text-muted fs-8 font-normal">{{ comments?.length || 0 }} chars</span>
        </label>
        <textarea
          id="annotationReason"
          v-model="comments"
          v-auto-grow
          rows="3"
          class="form-control annotation-textarea p-3 rounded-3 shadow-inner"
          placeholder="Explain why you accepted or rejected this conversation (brief)..."
        ></textarea>
      </div>
    </div>

    <!-- Read-only preview banner (admin review) -->
    <div v-if="readonly" class="alert alert-info d-flex align-items-center rounded-4 mb-4">
      <i class="bi bi-eye-fill me-2"></i>
      <span>Read-only preview of a submitted annotation.</span>
    </div>

    <!-- Submit / Navigation Bar -->
    <div v-if="!readonly" class="card border-0 shadow-sm rounded-4 bg-white p-4 mb-5">
      <div class="d-flex flex-column flex-sm-row justify-content-between align-items-center gap-3">
        
        <!-- Previous Button -->
        <button
          class="btn btn-outline-secondary px-4 py-2.5 rounded-pill d-flex align-items-center gap-2 transition-all hover-translate"
          :disabled="currentIndex === 0 || isSubmitting || isSaving"
          @click="$emit('prev')"
        >
          <i class="bi bi-arrow-left-circle-fill"></i>
          Previous Task
        </button>
        
        <!-- Center Actions -->
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
            class="btn btn-success btn-submit-eval px-5 py-2.5 rounded-pill d-flex align-items-center gap-2 shadow-sm transition-all hover-translate"
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
        Please select Accept or Reject before submitting.
      </div>
      
      <!-- Keyboard Shortcuts Info -->
      <div class="text-center text-muted mt-3" style="font-size: 0.78rem;">
        Shortcuts: <kbd>1</kbd> Accept · <kbd>2</kbd> Reject · 
        <kbd>Ctrl</kbd>/<kbd>⌘</kbd> + <kbd>Enter</kbd> submit &amp; next ·
        <kbd>Ctrl</kbd>/<kbd>⌘</kbd> + <kbd>S</kbd> save draft
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { API_BASE_URL } from '@/config';

// Auto-grow textarea directive
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

// Focus (and place the caret at the end of) a textarea the moment it mounts,
// used by the click-to-edit fields so editing starts on the first click.
const vFocus = {
  mounted(el) {
    el.focus();
    try {
      const len = el.value.length;
      el.setSelectionRange(len, len);
    } catch (_) { /* non-text inputs */ }
  }
}

// Click-to-edit state: a field shows its rendered math/text until clicked, then
// becomes a raw textarea; on blur it renders again. Only one field edits at a
// time, keyed by 'pre_scene' | 'post_scene' | 'turn:<idx>'.
const editingKey = ref(null)
function startEdit(key) { editingKey.value = key }
function stopEdit() { editingKey.value = null }

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
  },
  // When true the component is a read-only preview (admin review): action buttons
  // are hidden and all submit paths are inert.
  readonly: {
    type: Boolean,
    default: false
  },
  testType: {
    type: String,
    default: 'conversation-evaluation'
  }
})

const emit = defineEmits(['next', 'prev', 'submit-status'])

// Reactive State
const evaluation = ref(null)
const comments = ref('')
const isSubmitting = ref(false)
const isSaving = ref(false)
const startTime = ref(Date.now())
const conversationState = ref([])
const sceneState = ref({
  pre_scene: '',
  post_scene: ''
})

const isEditable = computed(() => {
  return props.testType === 'conversation-editable'
})

// Watch currentTest changes to setupState
watch(() => props.currentTest, () => {
  setupState()
}, { immediate: true })

function setupState() {
  startTime.value = Date.now()
  if (!props.currentTest) return

  // Load existing values from response if they exist (drafts or loaded ratings)
  evaluation.value = props.currentTest.evaluation || null
  comments.value = props.currentTest.comments || ''

  // Initialize editable pre_scene and post_scene states
  sceneState.value = {
    pre_scene: props.currentTest.pre_scene || '',
    _orig_pre_scene: props.currentTest.pre_scene || '',
    post_scene: props.currentTest.post_scene || '',
    _orig_post_scene: props.currentTest.post_scene || ''
  }

  const originalTurns = props.currentTest.dialogue || props.currentTest.conversation || props.currentTest.turns || []
  conversationState.value = originalTurns.map(turn => ({
    ...turn,
    _originalText: turn.text || ''
  }))

  window.scrollTo({ top: 0, behavior: 'auto' })
}

// Helpers
const cellData = computed(() => {
  return props.currentTest.cell || {}
})

const dialogueTurns = computed(() => {
  return conversationState.value
})

const personaGuidelines = computed(() => {
  // Guidelines based on persona
  const guidelinesMap = {
    'calm_explainer': 'Maintains a calm, composed tone, explaining the misconceptions step-by-step with logical clarity and steady pacing.',
    'energetic_enthusiast': 'Very enthusiastic, encouraging, and uses dynamic language. Speaks with high energy and passion to engage the student.',
    'reflective_mentor': 'Encourages the student to reflect on their own logic. Acts as a supportive guide rather than lecturing, prompting self-realization.',
    'relatable_peer': 'Friendly and uses relatable language. Breaks down barriers to sound like a peer explaining things to a classmate.',
    'socratic_challenger': 'Asks continuous probing questions to make the student realize their logical contradictions. Relies on the Socratic method.',
    'storyteller': 'Weaves explanations into narrative, anecdotes, and stories to create context and memorable analogies.',
    'strict_disciplinarian': 'Extremely direct, formal, and authoritative. Expects focus and checks for precise rules and definitions.',
    'warm_encourager': 'Genuinely kind and supportive. Builds the student up before addressing the misconception. Uses phrases that affirm effort. Approaches errors as expected steps in learning, not failures.'
  };
  
  const personaKey = (props.currentTest.teacher_persona || '').toLowerCase().trim();
  return guidelinesMap[personaKey] || props.currentTest.persona_guidelines || '';
})

function formatGrade(grade) {
  if (!grade) return '';
  return grade.replace('_', ' ').split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
}

function formatPersona(persona) {
  if (!persona) return '';
  return persona.replace('_', ' ').split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
}

function getSpeakerName(turn) {
  if (turn.speaker === 'teacher') {
    return props.currentTest.teacher_name || 'Teacher';
  } else {
    return props.currentTest.student_name || 'Student';
  }
}

function getTeacherTurnNumber(turnIndex) {
  // Find which teacher turn this is (e.g. 1st, 2nd, etc.)
  const teacherTurns = conversationState.value
    .filter(t => t.speaker === 'teacher')
    .map(t => t.turn_index);
  const position = teacherTurns.indexOf(turnIndex);
  return position !== -1 ? position + 1 : 1;
}

function getVoiceDirection(turnIndex) {
  const turnNum = getTeacherTurnNumber(turnIndex);
  const key = `teacher_turn_${turnNum}_voice_direction`;
  return props.currentTest[key] || 'No specific voice direction.';
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

function resetTurn(index) {
  const turn = conversationState.value[index]
  if (turn) {
    turn.text = turn._originalText
  }
}

function isTurnModified(index) {
  const turn = conversationState.value[index]
  if (!turn) return false
  return turn.text !== turn._originalText
}

function selectEvaluation(val) {
  evaluation.value = val;
}

const isValid = computed(() => {
  const isEvalValid = evaluation.value === 'accept' || evaluation.value === 'reject';
  if (!isEvalValid) return false;
  
  if (isEditable.value) {
    if (!sceneState.value.pre_scene.trim()) return false;
    if (props.currentTest.post_scene && !sceneState.value.post_scene.trim()) return false;
    return conversationState.value.every(turn => (turn.text || '').trim().length > 0);
  }
  
  return true;
})

// Skip Action
async function handleSkip() {
  if (props.readonly) return
  if (isSubmitting.value) return
  isSubmitting.value = true

  const durationMs = Date.now() - startTime.value
  const results_json = buildResultsJson()

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

    emit('submit-status', { index: props.currentIndex, status: 'skipped', results: results_json })
    emit('next')
  } catch (error) {
    console.error('Error skipping rating:', error)
    alert('Failed to skip. Please check your connection and try again.')
  } finally {
    isSubmitting.value = false
  }
}

function buildResultsJson() {
  const cleanTurns = conversationState.value.map(turn => {
    const cleanTurn = { ...turn }
    delete cleanTurn._originalText
    return cleanTurn
  })
  
  let dialogueKey = 'conversation'
  if ('dialogue' in props.currentTest) {
    dialogueKey = 'dialogue'
  } else if ('turns' in props.currentTest) {
    dialogueKey = 'turns'
  }

  return {
    id: props.currentTest.id,
    evaluation: evaluation.value,
    comments: comments.value,
    ...(isEditable.value ? {
      pre_scene: sceneState.value.pre_scene,
      post_scene: sceneState.value.post_scene,
      [dialogueKey]: cleanTurns
    } : {})
  }
}

// Draft Save
async function handleSave() {
  if (props.readonly) return
  if (isSaving.value || isSubmitting.value) return
  isSaving.value = true

  const durationMs = Date.now() - startTime.value
  const results_json = buildResultsJson()

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
    
    // Display toast notification
    const toast = document.createElement('div')
    toast.className = 'position-fixed bottom-0 start-50 translate-middle-x mb-4 bg-dark text-white py-2.5 px-4 rounded-pill shadow-lg z-3 border border-secondary animate-fade-in'
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
  if (props.readonly) return
  if (isSubmitting.value || !isValid.value) return
  isSubmitting.value = true

  const durationMs = Date.now() - startTime.value
  const results_json = buildResultsJson()

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
      throw new Error('Failed to submit evaluation ratings')
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

// Shortcuts listener
function onKeydown(e) {
  if (props.readonly) return
  // Don't trigger if user is typing in a textarea or input field
  if (document.activeElement.tagName === 'TEXTAREA' || document.activeElement.tagName === 'INPUT') {
    // Only intercept Ctrl+Enter or Ctrl+S
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault()
      if (isValid.value) handleSubmit()
    } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
      e.preventDefault()
      handleSave()
    }
    return
  }

  // Handle number shortcut selection
  if (e.key === '1') {
    e.preventDefault()
    selectEvaluation('accept')
  } else if (e.key === '2') {
    e.preventDefault()
    selectEvaluation('reject')
  }

  // Standard Ctrl combinations
  if (e.ctrlKey || e.metaKey) {
    if (e.key === 'Enter') {
      e.preventDefault()
      if (isValid.value) handleSubmit()
    } else if (e.key.toLowerCase() === 's') {
      e.preventDefault()
      handleSave()
    }
  }
}

onMounted(() => {
  setupState()
  window.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
})

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

// True when the string contains any LaTeX math delimiter, so we only show the
// equation preview for turns/scenes that actually contain math.
function hasMath(s) {
  if (!s) return false
  return /\$[^$]+\$|\\\(|\\\[|\$\$/.test(String(s))
}
</script>

<style scoped>
/* Click-to-edit field: shows rendered math/text, becomes a textarea on click,
   renders again on blur. Styled to look editable (hover + focus affordance). */
.editable-rendered {
  min-height: 2.6rem;
  padding: 0.5rem 0.75rem;
  border: 1px solid #e2e8f0;
  border-radius: 0.5rem;
  background-color: #fff;
  cursor: text;
  font-size: 1rem;
  line-height: 1.7;
  color: #0f172a;
  transition: border-color .15s, background-color .15s, box-shadow .15s;
  overflow-x: auto;
}
.editable-rendered:hover {
  border-color: #0ea5e9;
  background-color: #f0f9ff;
}
.editable-rendered:focus {
  outline: none;
  border-color: #0ea5e9;
  background-color: #f0f9ff;
  box-shadow: 0 0 0 0.15rem rgba(14, 165, 233, 0.2);
}
.editable-placeholder {
  color: #94a3b8;
  font-style: italic;
}
/* keep KaTeX from overflowing narrow columns */
.editable-rendered :deep(.katex) {
  white-space: normal;
}

/* Gradient and visual card styles */
.pre-scene-box {
  background-color: #f0f7ff;
  border-left: 4px solid #3b82f6;
}

.meta-pill-card {
  background-color: #fafafa;
  border-color: #eaeaea !important;
  transition: all 0.2s ease;
}

.meta-pill-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 10px rgba(0,0,0,0.03);
}

.border-start-warning {
  border-left: 4px solid #f59e0b;
}
.persona-guidelines-box {
  background-color: #fffbeb;
}

/* Dialogue speech bubbles */
.speech-bubble {
  position: relative;
  background-color: #fff;
  transition: all 0.25s ease;
}

.teacher-bubble {
  border-left: 4px solid #2563eb !important;
  background-color: #f8fafc;
}

.student-bubble {
  border-left: 4px solid #10b981 !important;
  background-color: #f9fbf9;
}

.dialogue-row:hover .speech-bubble {
  box-shadow: 0 4px 12px rgba(0,0,0,0.04);
}

/* Voice Direction Box styling - elegant dashboard card */
.voice-direction-card {
  background-color: #fdfdfd;
  border: 1px dashed #cbd5e1;
  transition: all 0.25s ease;
}

.dialogue-row:hover .voice-direction-card {
  border-color: #3b82f6;
  background-color: #f8fafc;
}

.voice-icon-pulse {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  background-color: #eff6ff;
  border-radius: 50%;
}

.italic-text {
  font-style: italic;
  font-family: Georgia, serif;
}

.border-start-secondary {
  border-left: 4px solid #6b7280;
}
.post-scene-box {
  background-color: #f9fafb;
}

/* Interactive Accept/Reject buttons */
.evaluation-choice-btn {
  font-size: 1.1rem;
  transition: all 0.2s ease;
}

.btn-outline-success {
  color: #198754;
  border-color: #198754;
}
.btn-outline-success:hover {
  background-color: #f4fbf7;
  color: #198754;
}

.btn-success-selected {
  background-color: #198754 !important;
  color: #ffffff !important;
  border-color: #198754 !important;
  box-shadow: 0 4px 15px rgba(25, 135, 84, 0.3) !important;
}

.btn-outline-danger {
  color: #dc3545;
  border-color: #dc3545;
}
.btn-outline-danger:hover {
  background-color: #fdf5f6;
  color: #dc3545;
}

.btn-danger-selected {
  background-color: #dc3545 !important;
  color: #ffffff !important;
  border-color: #dc3545 !important;
  box-shadow: 0 4px 15px rgba(220, 53, 69, 0.3) !important;
}

.annotation-textarea {
  font-size: 1.05rem;
  line-height: 1.5;
  border-radius: 12px;
  border: 1px solid #ced4da;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
  background-color: #fdfdfd;
}

.annotation-textarea:focus {
  border-color: #198754;
  box-shadow: 0 0 0 3px rgba(25, 135, 84, 0.15) !important;
  background-color: #ffffff;
  outline: none;
}

.btn-submit-eval {
  font-weight: 500;
}

.hover-translate {
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.hover-translate:hover:not(:disabled) {
  transform: translateY(-2px);
}

.shadow-inner {
  box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.05);
}

/* Animations */
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(5px); }
  to { opacity: 1; transform: translateY(0); }
}

.animate-fade-in {
  animation: fadeIn 0.4s ease-out;
}

.leading-relaxed {
  line-height: 1.625;
}
</style>
