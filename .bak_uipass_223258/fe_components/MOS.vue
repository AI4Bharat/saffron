<template>
  <div class="container py-1 w-100 mt-2">
    <!-- Instructions Section -->
    <div class="alert alert-info shadow-sm" role="alert">
      <div class="d-flex justify-content-center">
        <button
          class="btn btn-primary instruction-btn shadow-sm"
          type="button"
          data-bs-toggle="collapse"
          data-bs-target="#audioGuidelines"
          aria-expanded="false"
          aria-controls="audioGuidelines"
        >
          <i class="bi bi-info-circle me-2"></i>
          Mean Opinion Score (MOS) Instructions (Click to Expand)
        </button>
      </div>
      <div class="collapse mt-3" id="audioGuidelines">
        <div class="card card-body border-0 shadow-inner">
          <h4 class="mb-3">Study Description & Instructions</h4>
          <p>
            In this study, you will listen to a series of audio recordings and rate their overall quality and naturalness on a scale from 1 to 5. Your ratings will help evaluate and improve speech synthesis technology.
          </p>

          <h5 class="mt-3">Scoring Scale</h5>
          <div class="table-responsive">
            <table class="table table-bordered table-hover align-middle">
              <thead class="table-light">
                <tr>
                  <th scope="col" style="width: 100px;">Score</th>
                  <th scope="col" style="width: 150px;">Rating</th>
                  <th scope="col">Description</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><span class="badge bg-success-subtle text-success border border-success px-2 py-1 fs-6">5</span></td>
                  <td><strong>Excellent</strong></td>
                  <td>Completely natural voice, perfect clarity, no digital distortions or synthetic glitches.</td>
                </tr>
                <tr>
                  <td><span class="badge bg-info-subtle text-info border border-info px-2 py-1 fs-6">4</span></td>
                  <td><strong>Good</strong></td>
                  <td>Very natural voice with minor, barely noticeable speech or quality issues.</td>
                </tr>
                <tr>
                  <td><span class="badge bg-warning-subtle text-warning border border-warning px-2 py-1 fs-6">3</span></td>
                  <td><strong>Fair</strong></td>
                  <td>Fairly natural, but has clear signs of synthetic generation or audio degradation.</td>
                </tr>
                <tr>
                  <td><span class="badge bg-orange-subtle text-orange border border-orange px-2 py-1 fs-6">2</span></td>
                  <td><strong>Poor</strong></td>
                  <td>Highly unnatural/robotic voice, noticeable speed/pitch issues, or distracting artifacts.</td>
                </tr>
                <tr>
                  <td><span class="badge bg-danger-subtle text-danger border border-danger px-2 py-1 fs-6">1</span></td>
                  <td><strong>Bad</strong></td>
                  <td>Extremely synthetic/unusable audio with severe distortion, skips, or static noise.</td>
                </tr>
              </tbody>
            </table>
          </div>

          <h5 class="mt-3">Procedure</h5>
          <ul>
            <li>Click **Play** to listen to the entire audio sample without skipping.</li>
            <li>After the audio plays completely, rate the quality by selecting a score from **1** to **5**.</li>
            <li>Click **Next** (or **Submit** for the last page) to proceed.</li>
          </ul>
        </div>
      </div>
    </div>

    <!-- Evaluation Section -->
    <div class="row g-4 justify-content-center mt-2">
      <!-- Waveform and Player -->
      <div class="col-12 col-lg-10">
        <div class="card border-0 shadow-sm glass-card">
          <div class="card-body p-4">
            <h5 class="card-title text-muted mb-3 d-flex align-items-center">
              <i class="bi bi-music-note-beamed me-2 text-primary"></i>
              Audio Sample
            </h5>
            <div id="waveform" class="waveform mb-3 shadow-inner rounded"></div>
            
            <div class="d-flex align-items-center justify-content-between">
              <span class="text-secondary small">
                {{ formatTime(currentTime) }} / {{ formatTime(duration) }}
              </span>
              <button
                class="btn btn-lg btn-play shadow"
                @click="playAudio"
                :disabled="isLoading"
              >
                <i :class="isPlaying ? 'bi bi-pause-fill' : 'bi bi-play-fill'"></i>
                {{ isPlaying ? 'Pause' : 'Play' }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Rating Scale -->
      <div class="col-12 col-lg-10 text-center">
        <div class="card border-0 shadow-sm glass-card p-4">
          <h5 class="mb-4 font-semibold text-dark">
            How do you rate the overall quality and naturalness of this audio?
          </h5>
          
          <div class="mos-rating-group d-flex justify-content-center flex-wrap gap-2 my-2">
            <button
              v-for="score in [1, 2, 3, 4, 5]"
              :key="score"
              type="button"
              class="btn mos-btn d-flex flex-column align-items-center"
              :class="getMosBtnClass(score)"
              @click="setRating(score)"
              :disabled="!canClassify"
            >
              <span class="mos-score-num">{{ score }}</span>
              <span class="mos-score-label small">{{ getScoreLabel(score) }}</span>
            </button>
          </div>

          <div v-if="!canClassify" class="text-muted small mt-2">
            <i class="bi bi-info-circle me-1"></i> Please listen to the audio completely before rating.
          </div>
        </div>
      </div>

      <!-- Submit / Next Button -->
      <div class="col-12 text-center mt-3">
        <button
          class="btn btn-success btn-next shadow px-5 py-3 fs-5"
          :disabled="!canProceed || isSubmitting"
          @click="handleNext"
        >
          <span v-if="isSubmitting" class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
          {{ isSubmitting ? 'Submitting...' : isLastTest ? 'Submit Ratings' : 'Next Sample' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, nextTick } from 'vue'
import WaveSurfer from 'https://cdn.jsdelivr.net/npm/wavesurfer.js@7/dist/wavesurfer.esm.js'
import { API_BASE_URL } from '@/config';

const props = defineProps({
  currentTest: Object,
  isLastTest: Boolean,
  test_id: Object,
  session_id: Object,
  currentIndex: Object,
})

const emit = defineEmits(['next'])
const isSubmitting = ref(false)

// State
const startTime = ref(Date.now())
const rating = ref(null)
const waveSurfer = ref(null)
const isPlaying = ref(false)
const isLoading = ref(true)
const hasPlayed = ref(false)
const currentTime = ref(0)
const duration = ref(0)

// Computed
const canClassify = computed(() => {
  return hasPlayed.value
})

const canProceed = computed(() => {
  return rating.value !== null && canClassify.value
})

// Methods
const formatTime = (time) => {
  const mins = Math.floor(time / 60)
  const secs = Math.floor(time % 60)
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

const getScoreLabel = (score) => {
  const labels = {
    1: 'Bad',
    2: 'Poor',
    3: 'Fair',
    4: 'Good',
    5: 'Excellent'
  }
  return labels[score]
}

const getMosBtnClass = (score) => {
  if (rating.value === score) {
    const activeClasses = {
      1: 'mos-active-1',
      2: 'mos-active-2',
      3: 'mos-active-3',
      4: 'mos-active-4',
      5: 'mos-active-5'
    }
    return activeClasses[score]
  }
  return 'btn-outline-secondary'
}

const initializeWaveSurfer = (url) => {
  const ws = WaveSurfer.create({
    container: '#waveform',
    waveColor: '#d1e6ff',
    progressColor: '#0055ff',
    height: 70,
    cursorWidth: 1,
    cursorColor: '#0055ff',
    barWidth: 3,
    barGap: 1.5,
    responsive: true,
    interact: false,
    hideScrollbar: true
  })

  ws.load(url)
  return ws
}

const playAudio = () => {
  if (waveSurfer.value) {
    waveSurfer.value.playPause()
    isPlaying.value = !isPlaying.value
  }
}

const setRating = (score) => {
  rating.value = score
}

const handleNext = async () => {
  const endTime = Date.now()
  if (isSubmitting.value) return

  try {
    isSubmitting.value = true
    const token = localStorage.getItem('authToken')
    
    const results_json = {
      text: props.currentTest.Sentence || "",
      language: props.currentTest.attributes?.language_id || "",
      audios: [
        {
          url: props.currentTest.audio_path,
          system: props.currentTest.label || "",
          score: rating.value,
          label: getScoreLabel(rating.value),
          attributes: props.currentTest.attributes || {}
        }
      ],
      rating: rating.value
    }

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
        time_taken_to_submit: endTime - startTime.value,
        pageNo_progress: props.currentTest.id
      })
    })

    if (!response.ok) {
      throw new Error('Failed to save rating.')
    } else {
      await response.json()

      emit('next')

      // Reset state for next sample
      rating.value = null
      hasPlayed.value = false
      currentTime.value = 0
      startTime.value = Date.now()
      isPlaying.value = false
      isLoading.value = true

      // Clean up old waveform
      if (waveSurfer.value) waveSurfer.value.destroy()

      // Initialize new waveform
      await nextTick()
      setupWaveform()
    }
  } catch (error) {
    console.error('Error saving rating:', error)
  } finally {
    isSubmitting.value = false
  }
}

const setupWaveform = async () => {
  try {
    waveSurfer.value = initializeWaveSurfer(`${props.currentTest.audio_path}`)

    waveSurfer.value.on('ready', () => {
      isLoading.value = false
      duration.value = waveSurfer.value.getDuration()
    })

    waveSurfer.value.on('audioprocess', () => {
      currentTime.value = waveSurfer.value.getCurrentTime()
    })

    waveSurfer.value.on('finish', () => {
      isPlaying.value = false
      hasPlayed.value = true
    })
  } catch (error) {
    console.error('Error setting up waveform:', error)
  }
}

// Lifecycle hooks
onMounted(async () => {
  await nextTick()
  await setupWaveform()
})

onUnmounted(() => {
  if (waveSurfer.value) waveSurfer.value.destroy()
})
</script>

<style scoped>
.glass-card {
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.4);
  border-radius: 12px;
  transition: all 0.3s ease;
}

.glass-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 16px rgba(0, 0, 0, 0.08) !important;
}

.waveform {
  background: #f1f5f9;
  border-radius: 8px;
  padding: 14px 10px;
  min-height: 80px;
}

.btn-play {
  background: linear-gradient(45deg, #0055ff, #0088ff);
  color: white;
  border: none;
  font-weight: 500;
  padding: 0.5rem 1.75rem;
  border-radius: 30px;
  transition: all 0.2s ease;
}

.btn-play:hover {
  transform: scale(1.03);
  box-shadow: 0 4px 12px rgba(0, 85, 255, 0.25);
  opacity: 0.95;
}

.btn-play:active {
  transform: scale(0.98);
}

/* MOS buttons styling */
.mos-btn {
  flex: 1;
  min-width: 90px;
  max-width: 140px;
  height: 90px;
  border-radius: 10px;
  padding: 10px;
  font-weight: 500;
  border-width: 2px;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 2px 4px rgba(0,0,0,0.03);
}

.mos-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.mos-score-num {
  font-size: 1.6rem;
  font-weight: bold;
}

.mos-score-label {
  font-weight: 500;
}

/* Color codes for active buttons */
.mos-active-1 {
  background-color: #f8d7da;
  border-color: #dc3545;
  color: #842029;
  box-shadow: 0 4px 12px rgba(220, 53, 69, 0.2);
}

.mos-active-2 {
  background-color: #ffe8d6;
  border-color: #fd7e14;
  color: #a04e0b;
  box-shadow: 0 4px 12px rgba(253, 126, 20, 0.2);
}

.mos-active-3 {
  background-color: #fff3cd;
  border-color: #ffc107;
  color: #664d03;
  box-shadow: 0 4px 12px rgba(255, 193, 7, 0.2);
}

.mos-active-4 {
  background-color: #cff4fc;
  border-color: #0dcaf0;
  color: #087990;
  box-shadow: 0 4px 12px rgba(13, 202, 240, 0.2);
}

.mos-active-5 {
  background-color: #d1e7dd;
  border-color: #198754;
  color: #0f5132;
  box-shadow: 0 4px 12px rgba(25, 135, 84, 0.2);
}

.btn-outline-secondary:hover:not(:disabled) {
  background-color: #f8fafc;
  border-color: #94a3b8;
  transform: translateY(-2px);
}

/* Custom Orange Badge for table */
.bg-orange-subtle {
  background-color: rgba(253, 126, 20, 0.15);
}
.border-orange {
  border-color: rgba(253, 126, 20, 0.3) !important;
}
.text-orange {
  color: #fd7e14 !important;
}

.btn-next {
  min-height: 48px;
  border-radius: 30px;
  background: linear-gradient(45deg, #198754, #2bb16f);
  border: none;
  font-weight: 500;
  transition: all 0.2s ease;
}

.btn-next:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 4px 15px rgba(25, 135, 84, 0.3);
}

.btn-next:disabled {
  opacity: 0.65;
}

.shadow-inner {
  box-shadow: inset 0 2px 4px rgba(0,0,0,0.06);
}
</style>
