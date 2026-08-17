<template>
  <div class="audio-seg-container animate-fade-in" v-if="currentTest">
    
    <!-- Guidelines & Keyboard Shortcuts Alert -->
    <div class="usage-alert shadow-sm mb-4">
      <div class="d-flex justify-content-center gap-3 flex-wrap">
        <button
          class="btn btn-primary instruction-btn shadow-sm"
          type="button"
          data-bs-toggle="collapse"
          data-bs-target="#audioGuidelines"
          aria-expanded="false"
          aria-controls="audioGuidelines"
        >
          <i class="bi bi-keyboard me-2"></i>
          How to Use &amp; Shortcuts (Click to Expand)
        </button>
        <button
          class="btn btn-success qc-guidelines-btn shadow-sm"
          type="button"
          @click="showQCGuidelinesModal = true"
        >
          <i class="bi bi-file-earmark-music-fill me-2"></i>
          Audio QC Guidelines
        </button>
      </div>
      <div class="collapse mt-3" id="audioGuidelines">
        <div class="card card-body border-0 shadow-inner usage-panel">
          <div class="row g-4">
            <div class="col-md-6">
              <h6 class="usage-heading"><i class="bi bi-keyboard me-2"></i>Keyboard Shortcuts</h6>
              <ul class="shortcut-list mb-2">
                <li><span class="keys"><kbd>1</kbd></span><span class="desc">Select Accept</span></li>
                <li><span class="keys"><kbd>2</kbd></span><span class="desc">Select Reject (opens reasons popup)</span></li>
                <li><span class="keys"><kbd>Space</kbd></span><span class="desc">Play / Pause Audio (when not typing)</span></li>
                <li><span class="keys"><kbd>Ctrl</kbd><span class="plus">+</span><kbd>Enter</kbd></span><span class="desc">Submit &amp; next task</span></li>
              </ul>
              <p class="text-muted fs-9 mb-0">On macOS, use <kbd>⌘ Cmd</kbd> in place of <kbd>Ctrl</kbd>.</p>
            </div>
            <div class="col-md-6">
              <h6 class="usage-heading"><i class="bi bi-mouse2 me-2"></i>Task Guidelines</h6>
              <ul class="usage-list">
                <li>Listen to the audio segment using the custom player controls.</li>
                <li>Verify if the transcript matches the audio. You can edit the text directly in the transcript box.</li>
                <li>If the audio quality, pronunciation, or text has issues, click <strong>Reject</strong> and choose the corresponding reason(s).</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Metadata Details Header -->
    <div class="card border-0 shadow-sm rounded-4 mb-4 bg-white p-4">
      <div class="row g-3">
        <div class="col-6 col-md-3">
          <div class="meta-pill-card p-3 rounded-3 text-center border">
            <span class="text-muted fs-8 text-uppercase d-block mb-1">Speaker</span>
            <span class="fw-bold text-dark fs-6">{{ currentTest.speaker || 'N/A' }}</span>
          </div>
        </div>
        <div class="col-6 col-md-3">
          <div class="meta-pill-card p-3 rounded-3 text-center border">
            <span class="text-muted fs-8 text-uppercase d-block mb-1">Role</span>
            <span class="fw-bold text-dark fs-6">{{ currentTest.role || 'N/A' }}</span>
          </div>
        </div>
        <div class="col-6 col-md-3">
          <div class="meta-pill-card p-3 rounded-3 text-center border">
            <span class="text-muted fs-8 text-uppercase d-block mb-1">Language</span>
            <span class="fw-bold text-dark fs-6">{{ currentTest.language || 'N/A' }}</span>
          </div>
        </div>
        <div class="col-6 col-md-3">
          <div class="meta-pill-card p-3 rounded-3 text-center border">
            <span class="text-muted fs-8 text-uppercase d-block mb-1">Persona</span>
            <span class="fw-bold text-dark fs-6">{{ currentTest.persona || 'N/A' }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Custom Streamable Audio Player Card -->
    <div class="card border-0 shadow-sm rounded-4 mb-4 bg-white p-4">
      <h5 class="fw-bold text-dark mb-3 d-flex align-items-center gap-2">
        <i class="bi bi-music-note-beamed text-primary"></i>
        Audio Player
      </h5>
      
      <!-- Hidden Audio Element -->
      <audio
        ref="audioRef"
        :src="audioUrl"
        preload="auto"
        @timeupdate="onTimeUpdate"
        @loadedmetadata="onLoadedMetadata"
        @ended="onEnded"
      ></audio>

      <!-- Custom Player Interface -->
      <div class="custom-player p-3 rounded-4 shadow-inner border bg-light">
        <div class="d-flex flex-column gap-3">
          <!-- Playback and Timeline Progress -->
          <div class="d-flex align-items-center gap-3">
            <button
              type="button"
              class="btn btn-primary play-btn shadow-sm rounded-circle d-flex align-items-center justify-content-center"
              @click="togglePlay"
              title="Play/Pause (Space)"
            >
              <i class="bi fs-4" :class="isPlaying ? 'bi-pause-fill' : 'bi-play-fill'"></i>
            </button>

            <!-- Progress bar slider -->
            <div class="flex-grow-1 position-relative">
              <input
                type="range"
                class="form-range progress-slider"
                min="0"
                :max="duration || 100"
                v-model="currentTime"
                @input="seekAudio"
              />
              <!-- Progress filled visual track -->
              <div 
                class="slider-filled-track" 
                :style="{ width: `${(currentTime / (duration || 100)) * 100}%` }"
              ></div>
            </div>

            <!-- Time tracker display -->
            <span class="time-display font-monospace fs-8 text-secondary">
              {{ formatTime(currentTime) }} / {{ formatTime(duration) }}
            </span>
          </div>

          <!-- Bottom Control Bar: Speed & Volume -->
          <div class="d-flex flex-wrap align-items-center justify-content-between gap-3 border-top pt-2">
            <!-- Speed controls -->
            <div class="d-flex align-items-center gap-2">
              <span class="fs-8 text-secondary fw-semibold">Speed:</span>
              <div class="btn-group btn-group-sm rounded-pill overflow-hidden border">
                <button
                  v-for="rate in [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]"
                  :key="rate"
                  type="button"
                  class="btn speed-btn py-1 px-2.5 fs-9 fw-bold"
                  :class="playbackRate === rate ? 'btn-dark' : 'btn-light'"
                  @click="changePlaybackRate(rate)"
                >
                  {{ rate }}x
                </button>
              </div>
            </div>

            <!-- Volume control -->
            <div class="d-flex align-items-center gap-2" style="width: 150px;">
              <button 
                type="button" 
                class="btn btn-link text-secondary p-0 border-0" 
                @click="toggleMute"
              >
                <i class="bi fs-5" :class="volumeIcon"></i>
              </button>
              <input
                type="range"
                class="form-range volume-slider"
                min="0"
                max="1"
                step="0.1"
                v-model="volume"
                @input="changeVolume"
              />
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Transcript Editing Card -->
    <div class="card border-0 shadow-sm rounded-4 mb-4 bg-white p-4">
      <div class="d-flex justify-content-between align-items-center mb-3">
        <h5 class="fw-bold text-dark mb-0 d-flex align-items-center gap-2">
          <i class="bi bi-file-earmark-text-fill text-success"></i>
          Audio Transcript Editor
        </h5>
        <button
          type="button"
          class="btn btn-sm btn-outline-secondary py-1 px-2.5 rounded-pill fs-8"
          title="Reset to original transcript"
          :disabled="!isTranscriptModified"
          @click="resetTranscript"
        >
          <i class="bi bi-arrow-counterclockwise me-1"></i> Reset
        </button>
      </div>

      <div class="textarea-wrapper position-relative">
        <textarea
          v-model="transcript"
          v-auto-grow
          class="form-control correction-textarea p-3 w-100 fs-6 shadow-inner"
          rows="3"
          placeholder="Edit audio transcript here..."
        ></textarea>
      </div>

      <div class="d-flex justify-content-between align-items-center mt-2 fs-8 text-secondary">
        <span v-if="isTranscriptModified" class="text-warning fw-semibold">
          <i class="bi bi-pencil-fill me-1"></i> Transcript edited
        </span>
        <span v-else class="text-success-emphasis fw-semibold">
          <i class="bi bi-check-circle-fill me-1"></i> Original transcript
        </span>
        <span class="font-monospace">{{ transcript?.length || 0 }} characters</span>
      </div>
    </div>

    <!-- Evaluation Choice Card -->
    <div class="card border-0 shadow-sm rounded-4 mb-4 bg-white p-4">
      <h5 class="fw-bold text-dark mb-3 d-flex align-items-center gap-2">
        <i class="bi bi-clipboard-check-fill text-warning"></i>
        Audio Segmentation Evaluation
      </h5>
      <p class="text-secondary fs-8 mb-4">Please rate the audio segment as Accept or Reject based on quality and matching criteria.</p>

      <div class="row g-3 justify-content-center">
        <!-- Accept Choice Button -->
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

        <!-- Reject Choice Button -->
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

      <!-- Display selected Rejection reasons if rejected -->
      <div v-if="evaluation === 'reject'" class="mt-4 p-3 bg-danger-subtle rounded-3 border-start border-danger border-3">
        <div class="d-flex justify-content-between align-items-center mb-2">
          <span class="fw-bold text-danger fs-8 text-uppercase tracking-wider">Rejection Reasons Added:</span>
          <button 
            type="button" 
            class="btn btn-sm btn-outline-danger py-0.5 px-2 rounded-pill fs-9 fw-bold"
            @click="showRejectModal = true"
          >
            <i class="bi bi-pencil-fill me-1"></i> Edit Reasons
          </button>
        </div>
        <div class="d-flex flex-wrap gap-1.5 mt-1">
          <span 
            v-for="reason in rejectionReasons" 
            :key="reason"
            class="badge bg-danger text-white rounded-pill fs-9 py-1 px-2.5 shadow-xs"
          >
            {{ formatReasonLabel(reason) }}
          </span>
          <span 
            v-if="rejectionReasons.includes('others') && customRejectionReason" 
            class="badge bg-dark text-white rounded-pill fs-9 py-1 px-2.5 shadow-xs"
          >
            Custom: {{ customRejectionReason }}
          </span>
          <span v-if="rejectionReasons.length === 0" class="text-muted fs-8 italic">
            No reasons selected yet. Click Edit Reasons to add.
          </span>
        </div>
      </div>

      <!-- General Comments / Rationale textarea -->
      <div class="mt-4">
        <label for="evalComments" class="form-label fw-bold text-dark-emphasis mb-2 d-flex justify-content-between">
          <span>General Evaluation Comments</span>
          <span class="text-muted fs-9">{{ comments?.length || 0 }} chars</span>
        </label>
        <textarea
          id="evalComments"
          v-model="comments"
          v-auto-grow
          rows="2"
          class="form-control annotation-textarea p-3 rounded-3 shadow-inner fs-7"
          placeholder="Enter any additional observations or notes here..."
        ></textarea>
      </div>
    </div>

    <!-- Submit / Saving Bottom Controls -->
    <div v-if="!readonly" class="card border-0 shadow-sm rounded-4 bg-white p-4 mb-5">
      <div class="d-flex flex-column flex-sm-row justify-content-between align-items-center gap-3">
        <!-- Previous Task -->
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
          <!-- Skip Task -->
          <button
            class="btn btn-outline-warning px-4 py-2.5 rounded-pill d-flex align-items-center gap-2 transition-all hover-translate"
            :disabled="isSubmitting || isSaving"
            @click="handleSkip"
          >
            <i class="bi bi-skip-forward-circle-fill"></i>
            Skip Task
          </button>
          
          <!-- Submit Task -->
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
      
      <!-- Validation warning alerts -->
      <div v-if="!isValid" class="text-danger text-center small mt-3">
        <i class="bi bi-exclamation-triangle-fill me-1"></i>
        <span v-if="!evaluation">Please evaluate this item (Accept or Reject) before submitting.</span>
        <span v-else-if="evaluation === 'reject' && rejectionReasons.length === 0">Please check at least one rejection reason.</span>
        <span v-else-if="evaluation === 'reject' && (!comments || !comments.trim())">Please enter an evaluation comment explaining why you rejected (compulsory).</span>
      </div>
    </div>

    <!-- Rejection Reasons Glassmorphic Modal Dialog Popup -->
    <div v-if="showRejectModal" class="reject-modal-overlay animate-fade-in" @click.self="closeRejectModal">
      <div class="reject-modal-card card border-0 shadow-lg rounded-4 animate-scale-up">
        <div class="card-header bg-danger text-white py-3 border-0 rounded-top-4 d-flex align-items-center justify-content-between">
          <h5 class="mb-0 fw-bold d-flex align-items-center gap-2">
            <i class="bi bi-exclamation-octagon-fill"></i>
            Select Rejection Reason(s)
          </h5>
          <button type="button" class="btn-close btn-close-white" aria-label="Close" @click="closeRejectModal"></button>
        </div>
        
        <div class="card-body p-4 reject-modal-body">
          <p class="text-muted small mb-3">Please check all details that apply for rejecting this audio segment:</p>
          
          <!-- Checklist grid of reasons (retired ones appended so they stay removable) -->
          <div class="row g-2 reasons-grid">
            <div
              v-for="reason in modalReasons"
              :key="reason"
              class="col-12 col-sm-6"
            >
              <div
                class="reason-checkbox-card p-2.5 rounded-3 border d-flex align-items-center cursor-pointer transition-all"
                :class="{ 'reason-checked': tempReasons.includes(reason), 'reason-retired': legacyReasons.includes(reason) }"
                @click="toggleReason(reason)"
              >
                <div class="form-check m-0 d-flex align-items-center">
                  <input
                    type="checkbox"
                    class="form-check-input me-2 cursor-pointer shadow-none"
                    :id="`reason_${reason}`"
                    :checked="tempReasons.includes(reason)"
                    @click.stop="toggleReason(reason)"
                  />
                  <label
                    class="form-check-label cursor-pointer fw-semibold text-dark-emphasis fs-8-5"
                    :for="`reason_${reason}`"
                    @click.stop
                  >
                    {{ formatReasonLabel(reason) }}
                    <span v-if="legacyReasons.includes(reason)" class="retired-tag ms-1">retired &mdash; uncheck to remove</span>
                  </label>
                </div>
              </div>
            </div>
          </div>

          <!-- Custom Reason Field -->
          <div v-if="tempReasons.includes('others')" class="mt-4 animate-slide-down">
            <label for="customReason" class="form-label fw-bold text-dark fs-8 mb-1.5">Custom Rejection Reason</label>
            <input
              type="text"
              id="customReason"
              v-model="tempCustomReason"
              class="form-control border-2 shadow-inner p-2.5 rounded-3 fs-7"
              placeholder="Describe the specific custom issue here..."
              required
            />
          </div>
        </div>

        <div class="card-footer bg-light p-3 border-top rounded-bottom-4 d-flex justify-content-end gap-2">
          <button 
            type="button" 
            class="btn btn-outline-secondary px-4 py-2 rounded-pill fw-semibold fs-8" 
            @click="closeRejectModal"
          >
            Cancel
          </button>
          <button 
            type="button" 
            class="btn btn-danger px-4 py-2 rounded-pill fw-bold fs-8 shadow-sm"
            :disabled="tempReasons.length === 0 || (tempReasons.includes('others') && !tempCustomReason.trim())"
            @click="confirmRejection"
          >
            Confirm Rejection
          </button>
        </div>
      </div>
    </div>

    <!-- Audio Quality Control (QC) Guidelines Modal Popup -->
    <div v-if="showQCGuidelinesModal" class="qc-modal-overlay animate-fade-in" @click.self="showQCGuidelinesModal = false">
      <div class="qc-modal-card card border-0 shadow-lg rounded-4 animate-scale-up">
        <div class="card-header bg-dark text-white py-3 border-0 rounded-top-4 d-flex align-items-center justify-content-between">
          <h5 class="mb-0 fw-bold d-flex align-items-center gap-2">
            <i class="bi bi-shield-check text-warning"></i>
            Audio Quality Control (QC) Guidelines
          </h5>
          <button type="button" class="btn-close btn-close-white" aria-label="Close" @click="showQCGuidelinesModal = false"></button>
        </div>
        
        <div class="card-body p-4 qc-modal-body">
          <p class="text-secondary mb-4">
            Please review all audio files against the following checklist to ensure high-quality output. Your goal is to verify that the audio is clean, matches the script, and fits the required persona.
          </p>
          
          <!-- ACCEPT Criteria Card -->
          <div class="qc-section-card accept-card p-3 rounded-4 mb-3">
            <h6 class="fw-bold text-success mb-2 d-flex align-items-center gap-2">
              <i class="bi bi-check-circle-fill"></i>
              ACCEPT Criteria
            </h6>
            <p class="small text-muted mb-2">Approve the audio if it meets all of the following conditions:</p>
            <ul class="qc-list accept-list mb-0">
              <li><strong>Persona Match:</strong> The voice artist's tone, energy, and style perfectly match the assigned persona.</li>
              <li><strong>Performance Quality:</strong> The speaker maintains consistent voice pitch, natural modulation, and appropriate variation throughout the recording.</li>
              <li><strong>Audio Clarity:</strong> The background is completely clean and clear.</li>
              <li><strong>Script Accuracy:</strong> The audio matches the provided script (subject to the correction rules below).</li>
            </ul>
          </div>

          <!-- REJECT Criteria Card -->
          <div class="qc-section-card reject-card p-3 rounded-4 mb-3">
            <h6 class="fw-bold text-danger mb-2 d-flex align-items-center gap-2">
              <i class="bi bi-x-circle-fill"></i>
              REJECT Criteria
            </h6>
            <p class="small text-muted mb-2">Reject the audio and send it back for a re-record if you notice any of the following:</p>
            
            <div class="row g-3">
              <div class="col-md-6">
                <div class="fw-bold text-danger-emphasis small mb-2"><i class="bi bi-volume-up-fill me-1"></i>Noise Issues:</div>
                <ul class="qc-list reject-list mb-0">
                  <li><strong>Background Noise:</strong> Any hum, hiss, static, or environmental sound.</li>
                  <li><strong>Breathing Sounds:</strong> Heavy, distracting, or loud breathing noises.</li>
                  <li><strong>Extraneous Sounds:</strong> Any sound other than the voice artist reading the script (e.g., lip smacks, mic bumps, background talking).</li>
                </ul>
              </div>
              <div class="col-md-6">
                <div class="fw-bold text-danger-emphasis small mb-2"><i class="bi bi-blockquote-left me-1"></i>Script &amp; Reading Errors:</div>
                <ul class="qc-list reject-list mb-0">
                  <li><strong>Major Mismatches:</strong> The audio meaning drastically differs from the text.</li>
                  <li><strong>Word Skips:</strong> The artist skips more than 2 words in the script.</li>
                  <li><strong>Sentence Skips:</strong> An entire sentence from the script is missed.</li>
                </ul>
              </div>
            </div>
          </div>

          <!-- Script Correction Rules Card -->
          <div class="qc-section-card correction-card p-3 rounded-4 border-2">
            <h6 class="fw-bold text-warning-emphasis mb-2 d-flex align-items-center gap-2">
              <i class="bi bi-pencil-square"></i>
              Script Correction Rules (Do Not Reject)
            </h6>
            <p class="small text-muted mb-2">Sometimes the audio is great, but the text needs a quick update. Accept the audio and manually update the text script in these scenarios:</p>
            <ul class="qc-list correction-list mb-0">
              <li><strong>Script Typos:</strong> If there is a grammatical error or typo in the original script, but the artist says it correctly and naturally, update the text to match the audio.</li>
              <li><strong>Natural Phrase Additions:</strong> If the artist adds extra words or full phrases to make the delivery sound more natural (e.g., "Can you understand?", "Are you able to follow what I'm saying?"), amend the script to match the audio, provided the additions do not alter the original meaning.</li>
              <li><strong>Human Filler Sounds:</strong> If the voice artist adds natural human expressions (e.g., "hmm", "ok", "oh"), do not reject the audio. Simply type those exact sounds into the script where they occur.</li>
            </ul>
          </div>

        </div>

        <div class="card-footer bg-light p-3 border-top rounded-bottom-4 d-flex justify-content-end">
          <button 
            type="button" 
            class="btn btn-dark px-4 py-2 rounded-pill fw-bold fs-8 shadow-sm"
            @click="showQCGuidelinesModal = false"
          >
            Got It
          </button>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { API_BASE_URL } from '@/config';

// Directive for auto growing textareas
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
  },
  // Read-only preview (admin review): hide actions, disable all submit paths.
  readonly: {
    type: Boolean,
    default: false
  },
  testType: {
    type: String,
    default: 'audio-segmentation'
  }
})

const emit = defineEmits(['next', 'prev', 'submit-status'])

// Audio state variables
const audioRef = ref(null)
const isPlaying = ref(false)
const currentTime = ref(0)
const duration = ref(0)
const playbackRate = ref(1.0)
const volume = ref(1.0)
const prevVolume = ref(1.0)

// Evaluation state variables
const evaluation = ref(null)
const comments = ref('')
const transcript = ref('')
const originalTranscript = ref('')
const rejectionReasons = ref([])
const customRejectionReason = ref('')

// Modal state variables
const showRejectModal = ref(false)
const showQCGuidelinesModal = ref(false)
const tempReasons = ref([])
const tempCustomReason = ref('')

const isSubmitting = ref(false)
const isSaving = ref(false)
const startTime = ref(Date.now())

// Available rejection reasons from the images
const availableReasons = [
  'abnormal', 'artist_issue', 'chatter', 'dramatic',
  'duplicate', 'echo', 'fan', 'flag',
  'incorrect_style', 'incorrect_text', 'low_volume', 'manual',
  'mispronounce', 'mismatch', 'noise', 'noise_beginning',
  'noise_end', 'not_normalized', 'objectionable_content', 'page_flip',
  'repeating_content', 'silence', 'skipping_words', 'too_fast',
  'too_slow', 'truncated_audio', 'unclear', 'unnatural',
  'weak_emotion', 'wrong_language', 'wrong_speaker'
]

// Reasons that were retired from the list above (e.g. the old free-text "others")
const legacyReasons = computed(() => {
  const stored = Array.isArray(props.currentTest?.rejection_reasons)
    ? props.currentTest.rejection_reasons
    : []
  const seen = new Set([...stored, ...rejectionReasons.value, ...tempReasons.value])
  return [...seen].filter(r => r && !availableReasons.includes(r))
})

// What the modal actually lists: the current reasons + any retired one still on
const modalReasons = computed(() => [...availableReasons, ...legacyReasons.value])

// Computed
const audioUrl = computed(() => {
  if (!props.currentTest?.audio_filename) return ''
  return `${API_BASE_URL}/audio/${props.currentTest.audio_filename}`
})

const isTranscriptModified = computed(() => {
  return transcript.value !== originalTranscript.value
})

const isValid = computed(() => {
  const hasSelectedEval = evaluation.value === 'accept' || evaluation.value === 'reject'
  if (!hasSelectedEval) return false
  if (evaluation.value === 'reject') {
    if (rejectionReasons.value.length === 0) return false
    if (!comments.value || !comments.value.trim()) return false
  }
  return true
})

const volumeIcon = computed(() => {
  if (volume.value === 0) return 'bi-volume-mute-fill'
  if (volume.value < 0.5) return 'bi-volume-down-fill'
  return 'bi-volume-up-fill'
})

// Watchers
watch(() => props.currentTest, () => {
  setupState()
}, { immediate: true })

// Reset audio when test changes
watch(audioUrl, () => {
  isPlaying.value = false
  currentTime.value = 0
  duration.value = 0
  if (audioRef.value) {
    audioRef.value.load()
  }
})

// Methods
function setupState() {
  startTime.value = Date.now()
  if (!props.currentTest) return

  // Load existing answers (restoring draft / completed rating states)
  evaluation.value = props.currentTest.evaluation || null
  comments.value = props.currentTest.comments || ''
  transcript.value = props.currentTest.transcript || ''
  originalTranscript.value = props.currentTest._originalTranscript || props.currentTest.transcript || ''
  // Copy, never alias: rejectionReasons is mutated locally and must not write
  rejectionReasons.value = Array.isArray(props.currentTest.rejection_reasons)
    ? [...props.currentTest.rejection_reasons]
    : []
  customRejectionReason.value = props.currentTest.custom_rejection_reason || ''
  tempReasons.value = [...rejectionReasons.value]
  tempCustomReason.value = customRejectionReason.value

  // Cache original transcript locally for reset protection if not cached already
  if (!props.currentTest._originalTranscript) {
    props.currentTest._originalTranscript = props.currentTest.transcript || ''
  }

  // Close modals
  showRejectModal.value = false
  showQCGuidelinesModal.value = false

  window.scrollTo({ top: 0, behavior: 'auto' })
}

// Audio logic handlers
function togglePlay() {
  if (!audioRef.value) return
  if (isPlaying.value) {
    audioRef.value.pause()
    isPlaying.value = false
  } else {
    audioRef.value.play().then(() => {
      isPlaying.value = true
    }).catch(err => {
      console.error("Playback error:", err)
    })
  }
}

function onTimeUpdate() {
  if (audioRef.value) {
    currentTime.value = audioRef.value.currentTime
  }
}

function onLoadedMetadata() {
  if (audioRef.value) {
    duration.value = audioRef.value.duration
  }
}

function onEnded() {
  isPlaying.value = false
  currentTime.value = 0
}

function seekAudio(event) {
  if (audioRef.value) {
    audioRef.value.currentTime = Number(event.target.value)
    currentTime.value = audioRef.value.currentTime
  }
}

function changePlaybackRate(rate) {
  playbackRate.value = rate
  if (audioRef.value) {
    audioRef.value.playbackRate = rate
  }
}

function changeVolume() {
  if (audioRef.value) {
    audioRef.value.volume = Number(volume.value)
  }
}

function toggleMute() {
  if (volume.value > 0) {
    prevVolume.value = volume.value
    volume.value = 0
  } else {
    volume.value = prevVolume.value
  }
  changeVolume()
}

function formatTime(seconds) {
  if (isNaN(seconds) || seconds === null) return '0:00'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60).toString().padStart(2, '0')
  return `${m}:${s}`
}

// Evaluation choices and reasoning modal handlers
function selectEvaluation(val) {
  if (props.readonly) return
  if (val === 'accept') {
    evaluation.value = 'accept'
    rejectionReasons.value = []
    customRejectionReason.value = ''
  } else if (val === 'reject') {
    // Open the reject modal popup
    tempReasons.value = [...rejectionReasons.value]
    tempCustomReason.value = customRejectionReason.value
    showRejectModal.value = true
  }
}

function closeRejectModal() {
  showRejectModal.value = false
  // If rejection was selected but has no confirmed reasons, cancel selection
  if (evaluation.value === 'reject' && rejectionReasons.value.length === 0) {
    evaluation.value = null
  }
}

function toggleReason(reason) {
  const index = tempReasons.value.indexOf(reason)
  if (index > -1) {
    tempReasons.value.splice(index, 1)
  } else {
    tempReasons.value.push(reason)
  }
}

function confirmRejection() {
  rejectionReasons.value = [...tempReasons.value]
  customRejectionReason.value = tempReasons.value.includes('others') ? tempCustomReason.value : ''
  evaluation.value = 'reject'
  showRejectModal.value = false
}

function resetTranscript() {
  transcript.value = originalTranscript.value
}

function formatReasonLabel(reason) {
  if (!reason) return ''
  return reason.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ')
}

// Submission builders
function buildResultsJson() {
  return {
    id: props.currentTest.id,
    evaluation: evaluation.value,
    comments: comments.value,
    transcript: transcript.value,
    rejection_reasons: rejectionReasons.value,
    custom_rejection_reason: customRejectionReason.value
  }
}

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
    
    // Display save notification
    const toast = document.createElement('div')
    toast.className = 'position-fixed bottom-0 start-50 translate-middle-x mb-4 bg-dark text-white py-2.5 px-4 rounded-pill shadow-lg z-3 border border-secondary animate-fade-in'
    toast.style.transition = 'opacity 0.3s ease'
    toast.innerHTML = '<i class="bi bi-check-circle-fill text-warning me-2"></i> Draft progress saved!'
    document.body.appendChild(toast)
    setTimeout(() => {
      toast.style.opacity = '0'
      setTimeout(() => toast.remove(), 300)
    }, 2000)
    
  } catch (error) {
    console.error('Error saving draft:', error)
    alert('Failed to save draft. Please check connection.')
  } finally {
    isSaving.value = false
  }
}

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
      throw new Error('Failed to skip')
    }

    emit('submit-status', { index: props.currentIndex, status: 'skipped', results: results_json })
    emit('next')
  } catch (error) {
    console.error('Error skipping rating:', error)
    alert('Failed to skip rating.')
  } finally {
    isSubmitting.value = false
  }
}

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
      throw new Error('Failed to submit evaluation')
    }

    emit('submit-status', { index: props.currentIndex, status: 'completed', results: results_json })
    emit('next')
  } catch (error) {
    console.error('Error submitting evaluation:', error)
    alert('Failed to submit. Please try again.')
  } finally {
    isSubmitting.value = false
  }
}

// Global Shortcuts
function onKeydown(e) {
  if (props.readonly) return
  // Ignore shortcuts when editing text inputs
  if (document.activeElement.tagName === 'TEXTAREA' || document.activeElement.tagName === 'INPUT') {
    // Standard submit combinations: Ctrl/Cmd + Enter
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault()
      if (isValid.value) handleSubmit()
    }
    return
  }

  // Key combinations
  if (e.key === '1') {
    e.preventDefault()
    selectEvaluation('accept')
  } else if (e.key === '2') {
    e.preventDefault()
    selectEvaluation('reject')
  } else if (e.key === ' ') {
    e.preventDefault()
    togglePlay()
  }

  // Standard Ctrl key handlers
  if (e.ctrlKey || e.metaKey) {
    if (e.key === 'Enter') {
      e.preventDefault()
      if (isValid.value) handleSubmit()
    }
  }
}

// Lifecycle
onMounted(() => {
  setupState()
  window.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
})
</script>

<style scoped>
.audio-seg-container {
  max-width: 800px;
  margin: 0 auto;
}

.instruction-btn {
  border-radius: 20px;
  background-color: #d8661b;
  border-color: #d8661b;
  padding: 8px 20px;
  font-weight: 600;
  transition: all 0.25s ease;
}

.instruction-btn:hover {
  background-color: #b4530f;
  border-color: #b4530f;
}

.usage-panel {
  background-color: #fff9f6;
  border: 1px solid #fde68a;
  border-radius: 12px;
}

.usage-heading {
  color: #b4530f;
  font-weight: 700;
  border-bottom: 2px solid #fde68a;
  padding-bottom: 6px;
}

.shortcut-list, .usage-list {
  padding-left: 0;
  list-style: none;
  font-size: 0.85rem;
}

.shortcut-list li {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
}

.shortcut-list .keys {
  width: 100px;
  display: flex;
  align-items: center;
  gap: 2px;
}

.shortcut-list .plus {
  color: #94a3b8;
  font-weight: bold;
}

.shortcut-list kbd {
  background-color: #f1f5f9;
  color: #334155;
  border: 1px solid #cbd5e1;
  border-radius: 4px;
  padding: 2px 6px;
  font-size: 0.75rem;
  font-family: inherit;
  box-shadow: 0 1px 1px rgba(0,0,0,0.1);
}

.usage-list li {
  margin-bottom: 8px;
  position: relative;
  padding-left: 18px;
  line-height: 1.4;
}

.usage-list li::before {
  content: "•";
  color: #d8661b;
  font-weight: bold;
  font-size: 1.2rem;
  position: absolute;
  left: 0;
  top: -2px;
}

.meta-pill-card {
  background-color: #fafafa;
  border-color: #eaeaea !important;
  transition: all 0.2s ease;
  border-radius: 12px;
}

.meta-pill-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.03);
}

/** Custom Audio Player UI Styling */
.custom-player {
  background-color: #f8fafc;
  border-color: #e2e8f0 !important;
}

.play-btn {
  width: 52px;
  height: 52px;
  background-color: #d8661b;
  border-color: #d8661b;
  transition: transform 0.2s ease, background-color 0.2s ease;
}

.play-btn:hover {
  transform: scale(1.05);
  background-color: #b4530f;
  border-color: #b4530f;
}

.progress-slider {
  -webkit-appearance: none;
  height: 6px;
  background-color: #cbd5e1;
  border-radius: 5px;
  outline: none;
  width: 100%;
}

.progress-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background-color: #d8661b;
  cursor: pointer;
  box-shadow: 0 1px 3px rgba(0,0,0,0.3);
  transition: transform 0.15s ease;
  position: relative;
  z-index: 5;
}

.progress-slider::-webkit-slider-thumb:hover {
  transform: scale(1.25);
}

.slider-filled-track {
  position: absolute;
  top: 10px;
  left: 0;
  height: 6px;
  background-color: #d8661b;
  border-radius: 5px 0 0 5px;
  pointer-events: none;
}

.speed-btn {
  color: #64748b;
  background-color: #ffffff;
  border-color: #f1f5f9;
  transition: all 0.15s ease;
}

.speed-btn:hover {
  color: #1e293b;
  background-color: #f1f5f9;
}

.volume-slider {
  height: 4px;
}

.volume-slider::-webkit-slider-thumb {
  background-color: #64748b;
  width: 10px;
  height: 10px;
}

/** Transcript and comments */
.correction-textarea {
  background-color: #ffffff;
  border-color: #cbd5e1;
  color: #1e293b;
  border-radius: 12px;
  font-family: inherit;
  font-size: 1rem;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.correction-textarea:focus {
  border-color: #d8661b;
  box-shadow: 0 0 0 4px rgba(216, 102, 27, 0.15);
}

/** Evaluation buttons */
.evaluation-choice-btn {
  background-color: white;
  min-height: 68px;
}

.btn-outline-success {
  border-color: #10b981;
  color: #10b981;
}

.btn-outline-success:hover {
  background-color: #f0fdf4;
  color: #10b981;
}

.btn-success-selected {
  background-color: #10b981 !important;
  color: white !important;
  border-color: #10b981 !important;
  box-shadow: 0 4px 12px rgba(16, 185, 129, 0.2);
}

.btn-outline-danger {
  border-color: #ef4444;
  color: #ef4444;
}

.btn-outline-danger:hover {
  background-color: #fef2f2;
  color: #ef4444;
}

.btn-danger-selected {
  background-color: #ef4444 !important;
  color: white !important;
  border-color: #ef4444 !important;
  box-shadow: 0 4px 12px rgba(239, 68, 68, 0.2);
}

.annotation-textarea {
  background-color: #ffffff;
  border-color: #cbd5e1;
}

.annotation-textarea:focus {
  border-color: #d8661b;
  box-shadow: 0 0 0 4px rgba(216, 102, 27, 0.15);
}

/** Modal Popup Rejection reasons */
.reject-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background-color: rgba(15, 23, 42, 0.5);
  backdrop-filter: blur(4px);
  z-index: 1050;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}

.reject-modal-card {
  width: 100%;
  max-width: 680px;
  background-color: #ffffff;
  border: 1px solid rgba(255, 255, 255, 0.2);
  display: flex;
  flex-direction: column;
  max-height: 85vh;
  box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1), 0 10px 10px -5px rgba(0,0,0,0.04);
}

.reject-modal-body {
  overflow-y: auto;
  padding-right: 8px;
}

/** Reasons grid checkboxes styling */
.reasons-grid {
  max-height: 45vh;
  overflow-y: auto;
  padding-right: 6px;
}

.reasons-grid::-webkit-scrollbar {
  width: 5px;
}

.reasons-grid::-webkit-scrollbar-track {
  background: transparent;
}

.reasons-grid::-webkit-scrollbar-thumb {
  background-color: #cbd5e1;
  border-radius: 10px;
}

.reason-checkbox-card {
  background-color: #f8fafc;
  border: 1px solid #e2e8f0;
  user-select: none;
}

.reason-checkbox-card:hover {
  background-color: #f1f5f9;
  border-color: #cbd5e1;
}

.reason-checked {
  background-color: #fef2f2;
  border-color: #fca5a5;
}

/** A reason that has been retired from the list but is still stored on this clip. Shown so it can b. */
.reason-retired {
  background-color: #fffbeb;
  border-style: dashed;
  border-color: #fcd34d;
}

.retired-tag {
  font-size: 0.65rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: #b45309;
  white-space: nowrap;
}

.form-check-input:checked {
  background-color: #ef4444;
  border-color: #ef4444;
}

/** Transitions and Helper utilities */
.animate-fade-in {
  animation: fadeIn 0.25s ease-out;
}

.animate-scale-up {
  animation: scaleUp 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.animate-slide-down {
  animation: slideDown 0.2s ease-out;
}

.fs-8-5 {
  font-size: 0.85rem;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes scaleUp {
  from { transform: scale(0.95); opacity: 0; }
  to { transform: scale(1); opacity: 1; }
}

@keyframes slideDown {
  from { transform: translateY(-10px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}

.hover-translate {
  transition: transform 0.2s ease;
}

.hover-translate:hover {
  transform: translateY(-1px);
}

/** QC Guidelines button & modal styling */
.qc-guidelines-btn {
  border-radius: 20px;
  background-color: #0d9488;
  border-color: #0d9488;
  color: white;
  padding: 8px 20px;
  font-weight: 600;
  transition: all 0.25s ease;
}

.qc-guidelines-btn:hover {
  background-color: #0f766e;
  border-color: #0f766e;
  color: white;
}

.qc-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background-color: rgba(15, 23, 42, 0.4);
  backdrop-filter: blur(8px);
  z-index: 1050;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}

.qc-modal-card {
  width: 100%;
  max-width: 800px;
  background-color: #ffffff;
  border: 1px solid rgba(255, 255, 255, 0.2);
  display: flex;
  flex-direction: column;
  max-height: 90vh;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
}

.qc-modal-body {
  overflow-y: auto;
  padding-right: 12px;
}

.qc-section-card {
  border: 1px solid;
  transition: transform 0.2s ease;
}

.qc-section-card:hover {
  transform: translateY(-2px);
}

.accept-card {
  background-color: #f0fdf4;
  border-color: #bbf7d0 !important;
}

.reject-card {
  background-color: #fef2f2;
  border-color: #fca5a5 !important;
}

.correction-card {
  background-color: #fffbeb;
  border-color: #fde68a !important;
}

.text-danger-emphasis {
  color: #991b1b !important;
}

.text-warning-emphasis {
  color: #854d0e !important;
}

.qc-list {
  padding-left: 0;
  list-style: none;
}

.qc-list li {
  margin-bottom: 8px;
  position: relative;
  padding-left: 20px;
  line-height: 1.45;
  font-size: 0.85rem;
}

.qc-list li:last-child {
  margin-bottom: 0;
}

.accept-list li::before {
  font-family: "bootstrap-icons";
  content: "\\F26E";           /* bi-check-lg */
  color: #10b981;
  font-weight: bold;
  position: absolute;
  left: 0;
  top: 0;
}

.reject-list li::before {
  font-family: "bootstrap-icons";
  content: "\\F62A";           /* bi-x-lg */
  color: #ef4444;
  font-weight: bold;
  position: absolute;
  left: 0;
  top: 0;
}

.correction-list li::before {
  font-family: "bootstrap-icons";
  content: "\\F4CB";           /* bi-pencil */
  color: #d97706;
  font-weight: bold;
  position: absolute;
  left: 0;
  top: 0;
}
</style>
