<template>
  <div class="container py-1 w-100 mt-2">
    <div class="alert alert-info" role="alert">
      <div class="d-flex justify-content-center">
        <button
          class="btn btn-primary instruction-btn"
          type="button"
          data-bs-toggle="collapse"
          data-bs-target="#audioGuidelines"
          aria-expanded="false"
          aria-controls="audioGuidelines"
        >
        <i class="bi bi-info-circle me-2"></i>
        Audio Study Instructions (Click to Expand)
      </button>
      </div>
      <div class="collapse mt-3" id="audioGuidelines">
        <div class="card card-body">
          <h4 class="mb-4">Study Description and Instructions</h4>
          <p>
              In this study, you will listen to a series of audio recordings and determine whether each one is <strong>human-spoken</strong> or <strong>machine-generated</strong>. Your participation will contribute to advancements in speech synthesis technology.
          </p>

          <h5 class="mt-4">Equipment Requirements</h5>
          <ul>
              <li><strong>Device:</strong> You must use a laptop for this study.</li>
              <li><strong>Audio:</strong> Use headphones for optimal audio quality.</li>
              <li><strong>Environment:</strong> Ensure you are in a quiet setting to avoid distractions.</li>
          </ul>

          <h5 class="mt-4">Task Overview</h5>
          <p>
              You will be presented with multiple audio recordings. After listening to each recording in its entirety, indicate whether you believe the speaker is <strong>human</strong> or the audio is <strong>machine-generated</strong>.
          </p>

          <h5 class="mt-4">Procedure</h5>
          <h6 class="mt-3">1. Grounding Phase</h6>
          <ul>
              <li>At the start of the test, you will be presented with audio recordings of <strong>human speakers</strong>.</li>
              <li>Listen carefully to these grounding examples as they will not be shown again.</li>
              <li>Spend a few minutes analyzing these examples to familiarize yourself with <strong>human speech characteristics</strong>.</li>
          </ul>

          <h6 class="mt-3">2. Evaluation Phase</h6>
          <ul>
              <li>Click the <strong>"Play"</strong> button to listen to an audio recording.</li>
              <li>Listen to the entire recording without interruption.</li>
              <li>Select one of the following options:
                  <ul>
                      <li><strong>Human:</strong> If you believe the recording is of a human speaker.</li>
                      <li><strong>Machine-generated:</strong> If you believe the recording is synthesized by a text-to-speech system.</li>
                  </ul>
              </li>
          </ul>

          <h5 class="mt-4">Judgment Criteria</h5>
          <p>
              Focus on nuances in the audio, such as <strong>tone, clarity, and naturalness</strong>, to make an informed decision. If you are uncertain, use your best judgment. Participants are expected to guess "Human" correctly at least <strong>K%</strong> of the time.
          </p>

          <h5 class="mt-4">Sample Duration</h5>
          <p>Each audio sample is between <strong>2 seconds</strong> and <strong>30 seconds</strong> long.</p>

          <h5 class="mt-4">Quality Assurance</h5>
          <ul>
              <li><strong>Hidden controls</strong> are embedded in the test to ensure attentiveness. Obvious examples may appear to test your focus.</li>
              <li>Consistently inattentive responses or random guessing will result in <strong>exclusion from payment eligibility</strong>.</li>
          </ul>

          <h5 class="mt-4">What If You Are Unable to Make a Judgment?</h5>
          <p>
              Participants are given grounding at the start of the test with examples of human audio. This grounding should help you make a judgment.
          </p>
          <p>
              It is acceptable to mistakenly classify machine-generated audio as human, but you are expected to correctly identify human audio at least <strong>K%</strong> of the time.
          </p>

          <h5 class="mt-4">Confidentiality</h5>
          <p>
              Your responses will be anonymized and used solely for research purposes. <strong class="text-danger">Do not share details of this study to maintain data integrity.</strong>
          </p>

          <h5 class="mt-4">Completion</h5>
          <ul>
              <li>Ensure all recordings have been evaluated before submitting your responses.</li>
              <li>If you encounter issues during the study, please contact the researcher through the <strong>Prolific platform</strong>.</li>
          </ul>

          <p class="mt-4"><strong>Thank you for contributing to this study!</strong></p>
        </div>
      </div>
    </div>
  </div>
  <div class="row g-4">
    <!-- Single Audio Player -->
    <div class="col-12">
      <div class="card">
        <div class="card-body">
          <h5 class="card-title">Audio Sample</h5>
          <div id="waveform" class="waveform mb-2"></div>
          <button
            class="btn btn-primary w-100"
            @click="playAudio"
            :disabled="isLoading"
          >
            {{ isPlaying ? 'Pause' : 'Play' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Classification Selection -->
    <div class="col-12 text-center">
      <h5 class="mb-3">Is this audio human or machine-generated?</h5>
      <div class="btn-group" role="group">
        <button
          class="btn btn-outline-primary"
          :class="{ active: classification === 'human' }"
          @click="setClassification('human')"
          :disabled="!canClassify"
        >
          Human
        </button>
        <button
          class="btn btn-outline-primary"
          :class="{ active: classification === 'machine' }"
          @click="setClassification('machine')"
          :disabled="!canClassify"
        >
          Machine-generated
        </button>
      </div>
    </div>

    <!-- Navigation -->
    <div class="col-12 text-center mt-4">
      <button
        class="btn btn-success"
        :disabled="!canProceed || isSubmitting"
        @click="handleNext"
      >
        <span v-if="isSubmitting" class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
        {{ isSubmitting ? 'Submitting...' : isLast ? 'Submit' : 'Next' }}
      </button>
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
const classification = ref(null)
const waveSurfer = ref(null)
const isPlaying = ref(false)
const isLoading = ref(true)
const hasPlayed = ref(false)

// Computed
const canClassify = computed(() => {
  return hasPlayed.value
})

const canProceed = computed(() => {
  return classification.value && canClassify.value
})

// Methods
const initializeWaveSurfer = (url) => {
  const ws = WaveSurfer.create({
    container: '#waveform',
    waveColor: '#4a9eff',
    progressColor: '#1976D2',
    height: 50,
    cursorWidth: 1,
    cursorColor: '#1976D2',
    barWidth: 2,
    barGap: 1,
    responsive: true,
    interact: false,
    hideScrollbar: true
  })

  ws.load(url)
  return ws
}

const playAudio = () => {
  waveSurfer.value.playPause()
  isPlaying.value = !isPlaying.value
}

const setClassification = (value) => {
  classification.value = value
}

const handleNext = async () => {
  const endTime = Date.now()
  if (isSubmitting.value) return

  try {
    isSubmitting.value = true
    const token = localStorage.getItem('authToken')
    // const results_json = {
    //   gt: props.currentTest.label,
    //   prediction: classification.value,
    //   audio: props.currentTest.audio_path
    // }
    const score = (props.currentTest.label === "Reference" && classification.value === "human") || (props.currentTest.label !== "Reference" && classification.value === "machine") ? 1 : 0
    const results_json = {
      text: "",
      language: "",
      audios: [
        {
          url: props.currentTest.audio_path,
          system: props.currentTest.label,
          score: score,
          label: classification.value,
          attributes: props.currentTest.attributes || {}
        }
      ]
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
      await response.json() // Wait for response to be processed

      emit('next')

      // Reset state for next sample
      classification.value = null
      hasPlayed.value = false
      startTime.value = Date.now()

      // Reset play state
      isPlaying.value = false
      isLoading.value = true

      // Clean up old waveform
      if (waveSurfer.value) waveSurfer.value.destroy()

      // Initialize new waveform after DOM update
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
  // console.log(`${API_BASE_URL}/${props.currentTest.audio_path}`)
  try {
    // Assuming the audio path is now directly in currentTest instead of in pairs
    waveSurfer.value = initializeWaveSurfer(`${props.currentTest.audio_path}`)

    waveSurfer.value.on('ready', () => {
      isLoading.value = false
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
  if (props.currentTest.audio_path == 'skip') {
    // Send a dummy rating for skipped items
    const token = localStorage.getItem('authToken')
    await fetch(`${API_BASE_URL}/ratings`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        test_id: props.test_id,
        session_id: props.session_id,
        results_json: {
          text: "",
          language: "",
          audios: [{
            url: "skip",
            system: "skip",
            score: 0,
            label: "skip",
            attributes: {}
          }]
        },
        time_taken_to_submit: 0,
        pageNo_progress: props.currentTest.id
      })
    })
    emit('next')
    return
  }
  await nextTick()
  await setupWaveform()
})

onUnmounted(() => {
  if (waveSurfer.value) waveSurfer.value.destroy()
})
</script>

<style scoped>
.waveform {
  background: #f8f9fa;
  border-radius: 4px;
  padding: 10px;
  min-height: 70px;
}

.btn-group {
  gap: 10px;
}

.card {
  height: 100%;
}
</style>
