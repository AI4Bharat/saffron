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
        Study Description and Instructions (Click to Expand)
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
              You will be presented with multiple audio recordings. After listening to each recording in its entirety, indicate whether you believe the audio sample  is <strong>human spoken</strong> or the audio is <strong>machine-generated</strong>.
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
              <li>If a sample is mark as machine-generated, you must also use the boxes to indicate the issue -
                  <ul>
                      <li><strong>Voice Quality is Digital:</strong> Sounds robotic, compressed, or lacks depth.</li>
                      <li><strong>Unnatural Pitch or Modulation:</strong> Odd pitch changes or overly smooth tones.</li>
                      <li><strong>Flat or Monotonic:</strong> Speech feels emotionless and dull.</li>
                      <li><strong>Inappropriate Emotion/Intonation:</strong> Wrong tone or mood for the content.</li>
                      <li><strong>Mispronunciations:</strong> Words sound wrong, especially uncommon ones.</li>
                      <li><strong>Skipped or Repeated Words:</strong> Feels like words are missing or doubled.</li>
                      <li><strong>Unnatural Pauses, Timing, or Speed:</strong> Awkward breaks, rushed delivery, or overly fast/slow speech.</li>
                      <li><strong>Digital Artifacts:</strong> Clicks, noisy breaths, or fake background sounds.</li>
                      <li><strong>No Human Quirks:</strong> No natural human quirks like breaths, hesitations, or stutters.</li>
                  </ul>
              </li>
          </ul>

          <h5 class="mt-4">Judgment Criteria</h5>
          <p>
              Focus on nuances in the audio, such as <strong>tone, clarity, and naturalness</strong>, to make an informed decision.
              If you are uncertain, use your best judgment. Participants are expected to guess "Human" correctly at least <strong>K%</strong> (the value of K will not be revealed) of the time.
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
              It is acceptable to mistakenly classify machine-generated audio as human, but you are expected to correctly identify human audio at least <strong>K%</strong> (the value of K will not be revealed) of the time.
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
    <div class="col-12">
      <div class="card">
        <div class="card-body">
          <div v-if="props.currentTest.Sentence" class="mb-3">
            <h5 class="sentence-title mb-2">
              <i class="bi bi-text-paragraph me-2"></i>
              Sentence
            </h5>
            <div class="form-control enhanced-text-box" readonly>
              {{ props.currentTest.Sentence }}
            </div>
          </div>
          <div class="row">
            <div class="col-12">
              <div class="card-body">
                <h5 class="card-title">Sample</h5>
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
          <div class="mb-3"></div>
          <div class="mb-3">
            <h6>Do you think the sample is human-spoken or machine-generated?</h6>
            <div class="btn-group" role="group">
              <button
                @click="setRating('human')"
                class="btn btn-outline-primary"
                :class="{ active: rating === 'human'}"
                :disabled="!hasPlayedAudio"
              >Human</button>
              <button
                @click="setRating('machine')"
                class="btn btn-outline-primary"
                :class="{ active: rating === 'machine'}"
                :disabled="!hasPlayedAudio"
              >Machine</button>
            </div>
            <small v-if="!hasPlayedAudio" class="text-muted d-block mt-2">
              Please listen to the complete audio before rating
            </small>
          </div>
          <div v-if="rating === 'machine'" class="rejection-reasons">
            <div v-for="category in rejectionCategories" :key="category.name" class="mb-3">
              <h6 class="mb-2">Why do you think the sample is machine-generated?</h6>
              <div class="row g-2">
                <div v-for="reason in category.reasons" :key="reason.value" class="col-md-3">
                  <div class="form-check">
                    <input
                      class="form-check-input"
                      type="checkbox"
                      v-model="selectedReasons[reason.value]"
                      :id="reason.value"
                    >
                    <label class="form-check-label" :for="reason.value">{{ reason.label }}</label>
                  </div>
                </div>
              </div>
            </div>
            <div class="col-12 mt-3">
              <label for="comments" class="form-label">
                Comments <span v-if="requiresComment" class="text-danger">*</span>
              </label>
              <textarea
                v-model="comments"
                id="comments"
                class="form-control"
                rows="2"
              ></textarea>
            </div>
          </div>
        </div>
      </div>
      <div class="col-12 text-center mt-4">
        <button
          class="btn btn-success"
          :disabled="!canProceed || isSubmitting"
          @click="handleNext"
        >
          <span v-if="isSubmitting" class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
          {{ isSubmitting ? 'Submitting...' : isLastTest ? 'Submit' : 'Next' }}
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
  currentIndex: Object,
})

const isLoading = ref(true)
const emit = defineEmits(['next'])

const startTime = ref(Date.now())
const rating = ref(null)
const selectedReasons = ref({})
const comments = ref('')
const hasPlayed = ref(false)
const endTime = ref(null)

const waveSurfer = ref(null)
const isPlaying = ref(false)
const isLoadingAudio = ref(true)
const hasPlayedAudio = ref(false)
const isSubmitting = ref(false)

const rejectionCategories = [
  {
    name: '',
    reasons: [
    {value: 'voice_quality', label: 'Voice Quality is Digital'},
      {value: 'unnatural_pitch', label: 'Unnatural Pitch or Modulation'},
      {value: 'flat', label: 'Flat or Monotonic'},
      {value: 'inappropriate_emotion', label: 'Inappropriate Emotion/Intonation'},
      {value: 'mispronunciations', label: 'Mispronunciations'},
      {value: 'skipped_repeated_words', label: 'Skipped or Repeated Words'},
      {value: 'unnatural_pauses', label: 'Unnatural Pauses, Timing, or Speed'},
      {value: 'digital_artifacts', label: 'Digital Artifacts'},
      {value: 'too_perfect', label: 'No Human Quirks'},
    ]
  }
];

const requiresComment = computed(() => {
  return ['mispronounce', 'incorrect_text', 'others'].some(
    reason => selectedReasons.value[reason]
  )
})

const canProceed = computed(() => {
  if (!rating.value) return false
  return true
})

const playAudio = () => {
  waveSurfer.value.playPause()
  isPlaying.value = !isPlaying.value
}

const setRating = (value) => {
  rating.value = value
  endTime.value = Date.now()
}

const handleNext = async () => {
  if (isSubmitting.value) return

  try {
    isSubmitting.value = true
    const token = localStorage.getItem('authToken')
    const reasons = Object.fromEntries(
      rejectionCategories[0].reasons.map(reason => [
        reason.value,
        !!selectedReasons.value[reason.value]
      ])
    )

    const results_json = {
      text: props.currentTest.Sentence || "",
      language: "",
      audios: [
        {
          url: props.currentTest.audio_path,
          system: props.currentTest.label,
          score: rating.value === 'human' ? '1' : '0',
          label: rating.value,
          attributes: reasons
        }
      ],
      rating: rating.value,
      // reasons: reasons,
      comments: comments.value,
      time_taken: (endTime.value - startTime.value) / 1000
    }

    await fetch(`${API_BASE_URL}/ratings`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        test_id: props.test_id,
        results_json: results_json,
        time_taken_to_submit: endTime.value - startTime.value,
        pageNo_progress: props.currentTest.id,
      }),
    })

    emit('next')
    resetState()

    await new Promise(resolve => setTimeout(resolve, 100))
    await setupWaveform()

  } catch (error) {
    console.error('Error saving rating:', error)
  } finally {
    isSubmitting.value = false
  }
}

const setupWaveform = async () => {
  try {
    if (waveSurfer.value) {
      waveSurfer.value.destroy()
      waveSurfer.value = null
    }

    await nextTick()

    waveSurfer.value = WaveSurfer.create({
      backgroundColor: '#ffffff',
      container: '#waveform',
      waveColor: '#2196F3',
      progressColor: '#1565C0',
      height: 80,
      cursorWidth: 1,
      cursorColor: '#1976D2',
      barWidth: 3,
      barGap: 1,
      responsive: true,
      interact: false,
      hideScrollbar: true,
    })

    waveSurfer.value.on('ready', () => {
      isLoadingAudio.value = false
      isLoading.value = false
    })

    waveSurfer.value.on('finish', () => {
      isPlaying.value = false
      hasPlayedAudio.value = true
    })

    waveSurfer.value.load(props.currentTest.audio_path)

  } catch (error) {
    console.error('Error setting up waveform:', error)
  }
}

const resetState = async () => {
  rating.value = null
  selectedReasons.value = {}
  comments.value = ''
  hasPlayed.value = false
  startTime.value = Date.now()
  isPlaying.value = false
  isLoadingAudio.value = true
  hasPlayedAudio.value = false

  if (waveSurfer.value) {
    waveSurfer.value.destroy()
    waveSurfer.value = null
  }

  await setupWaveform()
}

onMounted(async () => {
  await setupWaveform()
})

onUnmounted(() => {
  if (waveSurfer.value) {
    waveSurfer.value.destroy()
  }
})
</script>

<style scoped>
.btn-primary {
  background: linear-gradient(45deg, #1976D2, #2196F3);
  border: none;
  padding: 0.75rem 1.5rem;
  transition: all 0.3s ease;
}

.btn {
  transition: all 0.2s ease-in-out;
}

.btn:hover {
  transform: translateY(-1px);
}

.btn-outline-primary {
  border-width: 2px;
  font-weight: 500;
}

.btn-outline-primary.active {
  background: linear-gradient(45deg, #1976D2, #2196F3);
  border: none;
}

.card {
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.card:hover {
  box-shadow: 0 10px 15px rgba(0, 0, 0, 0.1);
  transform: translateY(-1px);
}

.badge {
  font-size: 0.75rem;
  font-weight: 600;
}

.text-truncate {
  max-width: 150px;
}

.bg-light {
  background-color: #f8f9fa;
}

.display-6 {
  font-size: 1.5rem;
}

.metadata-item {
  display: flex;
  align-items: center;
  background-color: #f8f9fa;
  border-radius: 0.25rem;
  padding: 0.25rem 0.5rem;
}

.metadata-label {
  font-weight: bold;
  color: #6c757d;
  margin-right: 0.5rem;
}

.metadata-value {
  color: #212529;
}

@media (min-width: 576px) {
  .metadata-container {
    flex-direction: column;
  }

  .metadata-item {
    width: 100%;
  }
  .text-truncate {
    max-width: 250px;
  }
  .display-6 {
    font-size: 2.5rem;
  }
}

.btn-group {
  width: 100%;
}

.btn-group .btn {
  flex: 1;
}

.rejection-reasons {
  background-color: linear-gradient(to bottom, #ffffff, #f8f9fa);;
  padding: 15px;
  border: 1px solid #e0e0e0;
  border-radius: 5px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
  margin: 1.5rem 0;
  margin-top: 15px;
}

@media (max-width: 768px) {
  .col-md-3 {
    flex: 0 0 100%;
    max-width: 100%;
  }
}

.rejection-reasons h6 {
  margin-top: 1rem;
  margin-bottom: 0.5rem;
  font-weight: bold;
}

.rejection-reasons .row {
  margin-left: -0.5rem;
  margin-right: -0.5rem;
}

.rejection-reasons .col-md-3 {
  padding-left: 0.5rem;
  padding-right: 0.5rem;
}

@media (max-width: 768px) {
  .rejection-reasons .col-md-3 {
    flex: 0 0 100%;
    max-width: 100%;
  }
}

.waveform-container {
  width: 100%;
}

.play-button {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0.5rem 1rem;
  font-size: 1rem;
}

.play-button i {
  font-size: 1.2rem;
}

@media (max-width: 576px) {
  .play-button {
    width: 100%;
    margin-bottom: 1rem;
  }
}

@media (min-width: 577px) {
  .waveform-container {
    max-width: 90%;
  }
  .play-button {
    max-width: 25%;
  }
}

.text-box {
  background-color: #f8f9fa;
  border: 1px solid #dee2e6;
  padding: 0.75rem;
  font-size: 1rem;
  line-height: 1.5;
  color: #212529;
  border-radius: 0.25rem;
  min-height: 60px;
}

.sentence-title {
  color: #2c3e50;
  font-size: 1.1rem;
  font-weight: 600;
}

.enhanced-text-box {
  background: linear-gradient(to bottom, #ffffff, #f8f9fa);
  border: 1px solid #e0e0e0;
  padding: 1rem 1.25rem;
  font-size: 1.1rem;
  line-height: 1.6;
  color: #2c3e50;
  border-radius: 0.5rem;
  min-height: 60px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
  transition: all 0.2s ease;
}

.enhanced-text-box:hover {
  box-shadow: 0 4px 6px rgba(0,0,0,0.08);
  border-color: #d0d0d0;
}
</style>
