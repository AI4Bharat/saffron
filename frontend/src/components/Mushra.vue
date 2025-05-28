<template>
  <div class="bg-light p-3 p-sm-6 d-flex align-items-center justify-content-center">
    <div class="bg-white rounded shadow p-3 p-sm-4 w-100" style="max-width: 1000px;">
      <!-- Single waveform container -->
      <div class="mb-3">
        <div id="waveform" class="bg-secondary bg-opacity-10 rounded"></div>
      </div>

      <!-- Tab navigation -->
      <ul class="nav nav-tabs mb-3">
        <li class="nav-item">
          <div class="d-flex align-items-center">
            <button
              class="nav-link d-flex align-items-center"
              :class="{ active: activeTab === 'reference' }"
              @click="setActiveTab('reference')"
            >
              Reference
              <button
                class="btn btn-sm ms-2"
                @click.stop="playAudioAndSetTab('reference')"
              >
                <i :class="isPlaying['reference'] ? 'bi bi-pause-fill' : 'bi bi-play-fill'"></i>
              </button>
              <span class="ms-2 badge bg-secondary">{{ sampleScores.reference.overall || 0 }}/100</span>
            </button>
          </div>
        </li>
        <li class="nav-item" v-for="(audio, index) in props.currentTest.test_audios" :key="index">
          <div class="d-flex align-items-center">
            <button
              class="nav-link d-flex align-items-center"
              :class="{ active: activeTab === `sample-${index}` }"
              @click="setActiveTab(`sample-${index}`)"
            >
              Sample {{ index + 1 }}
              <button
                class="btn btn-sm ms-2"
                @click.stop="playAudioAndSetTab(`sample-${index}`)"
              >
                <i :class="isPlaying[`sample-${index}`] ? 'bi bi-pause-fill' : 'bi bi-play-fill'"></i>
              </button>
              <span class="ms-2 badge bg-secondary">{{ sampleScores.samples[index]?.overall || 0 }}/100</span>
            </button>
          </div>
        </li>
      </ul>

      <div v-if="activeTab === 'reference' || currentSampleIndex >= 0">
        <div class="mb-3 d-flex justify-content-between align-items-center gap-3">
          <label class="form-label mb-0" style="min-width: 100px">Overall Score:</label>
          <input
            type="range"
            class="my-range flex-grow-1"
            min="0"
            max="100"
            v-model.number="getCurrentScore().overall"
            :style="{'background': `linear-gradient(to right, #1976D2 0%, #1976D2 ${getCurrentScore().overall}%, #ddd ${getCurrentScore().overall}%, #ddd 100%)`}"
          />
          <input
            type="number"
            class="form-control form-control-sm"
            style="width: 70px"
            min="0"
            max="100"
            v-model.number="getCurrentScore().overall"
          />
        </div>
      </div>

      <small v-if="!canSubmit" class="text-muted d-block mt-2">
        Please listen to the complete audio before rating
      </small>
      <button class="btn btn-primary w-100" :disabled="!canSubmit" @click="handleNext">Submit Ratings</button>
    </div>
  </div>
</template>

<script setup>
// Keep the imports
import { ref, onMounted, onUnmounted, nextTick, computed, watch } from 'vue'
import WaveSurfer from 'https://cdn.jsdelivr.net/npm/wavesurfer.js@7/dist/wavesurfer.esm.js'
import { API_BASE_URL } from '@/config';

const props = defineProps({
  currentTest: Object,
  canProceed: Boolean,
  isLastTest: Boolean,
  test_id: Object,
  currentIndex: Object,
})

const emit = defineEmits(['next'])

// Simplified state
const sampleScores = ref({
  reference: {
    overall: 50
  },
  samples: Array(props.currentTest.test_audios.length).fill().map(() => ({
    overall: 50
  }))
})

// Keep all the audio-related state variables
const isPlaying = ref({
  reference: false,
  ...Object.fromEntries(props.currentTest.test_audios.map((_, index) => [`sample-${index}`, false]))
})
const audioProgress = ref({
  reference: 0,
  ...Object.fromEntries(props.currentTest.test_audios.map((_, index) => [`sample-${index}`, 0]))
})
const startTime = ref(Date.now())
const activeTab = ref('reference')
const currentWavesurfer = ref(null)

const currentSampleIndex = computed(() => {
  if (activeTab.value === 'reference') return -1;
  return parseInt(activeTab.value.split('-')[1]);
})

const canSubmit = computed(() => {
  const referencePlayed = audioProgress.value.reference >= 0.99;
  const allSamplesPlayed = Object.entries(audioProgress.value)
    .filter(([key]) => key !== 'reference')
    .every(([progress]) => progress >= 0.99);

  return referencePlayed && allSamplesPlayed;
})

const getCurrentScore = () => {
  return activeTab.value === 'reference'
    ? sampleScores.value.reference
    : sampleScores.value.samples[currentSampleIndex.value]
}

// Simplified handleNext
const handleNext = async () => {
  const endTime = Date.now()
  const timeTaken = (endTime - startTime.value) / 1000

  try {
    const token = localStorage.getItem('authToken')
    const results_json = {
      text: "",
      language: "",
      reference: {
        url: props.currentTest.reference_audio,
        score: sampleScores.value.reference.overall,
        label: sampleScores.value.reference.overall >= 50 ? 'Preferred' : 'Not Preferred'
      },
      audios: props.currentTest.test_audios.map((audio, index) => ({
        url: audio.audio_path,
        system: audio.class,
        score: sampleScores.value.samples[index].overall,
        label: sampleScores.value.samples[index].overall >= 50 ? 'Preferred' : 'Not Preferred'
      }))
    }

    await fetch(`${API_BASE_URL}/ratings`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        test_id: props.test_id,
        results_json: results_json,
        time_taken_to_submit: timeTaken,
        pageNo_progress: props.currentTest.id
      })
    })

    emit('next')

    // Reset state
    sampleScores.value = {
      reference: { overall: 50 },
      samples: Array(props.currentTest.test_audios.length).fill().map(() => ({
        overall: 50
      }))
    }

    startTime.value = Date.now()
    await setActiveTab('reference')

  } catch (error) {
    console.error('Error submitting ratings:', error)
    alert('Error submitting ratings. Please try again.')
  }
}

const playAudioAndSetTab = async (tabName) => {
  // If current tab is playing and matches clicked tab, just pause
  if (isPlaying.value[tabName] && activeTab.value === tabName) {
    playAudio()
    return
  }

  // Otherwise switch tab and play
  await setActiveTab(tabName)
  playAudio()
}

const initializeWaveSurfer = async (audioPath) => {
  if (currentWavesurfer.value) {
    currentWavesurfer.value.destroy()
  }

  await nextTick()

  currentWavesurfer.value = WaveSurfer.create({
    container: '#waveform',
    waveColor: '#4a9eff',
    progressColor: '#1976D2',
    height: 100,
    cursorWidth: 1,
    cursorColor: '#1976D2',
    barWidth: 3,
    barGap: 1,
    responsive: true,
    interact: false, // Disable user interaction
    hideScrollbar: true,
  })

  currentWavesurfer.value.on('ready', () => {
    isPlaying.value[activeTab.value] = false
  })

  currentWavesurfer.value.on('finish', () => {
    isPlaying.value[activeTab.value] = false
    audioProgress.value[activeTab.value] = 1
  })

  currentWavesurfer.value.on('audioprocess', () => {
    const currentProgress = currentWavesurfer.value.getCurrentTime() / currentWavesurfer.value.getDuration()
    audioProgress.value[activeTab.value] = Math.max(currentProgress, audioProgress.value[activeTab.value])
  })

  await currentWavesurfer.value.load(audioPath)
}

const playAudio = () => {
  if (currentWavesurfer.value) {
    currentWavesurfer.value.playPause()
    isPlaying.value[activeTab.value] = !isPlaying.value[activeTab.value]
  }
}

onMounted(async () => {
  await setActiveTab('reference')
})

onUnmounted(() => {
  if (currentWavesurfer.value) {
    currentWavesurfer.value.destroy()
  }
})

const setActiveTab = async (tabName) => {
  activeTab.value = tabName
  Object.keys(isPlaying.value).forEach(key => {
    isPlaying.value[key] = false
  })

  const audioPath = tabName === 'reference'
    ? props.currentTest.reference_audio
    : props.currentTest.test_audios[parseInt(tabName.split('-')[1])].audio_path

  await initializeWaveSurfer(audioPath)
}

const updateOverallScore = (scores) => {
  scores.overall = calculateOverallScore(scores);
}

const calculateOverallScore = (scores) => {
  const totalScore = Object.values(scores).reduce((sum, score) => sum + score.overall, 0);
  return Math.round(totalScore / Object.keys(scores).length);
}

watch(() => sampleScores.value.reference, (newScores) => {
  updateOverallScore(newScores);
}, { deep: true });

sampleScores.value.samples.forEach((_, index) => {
  watch(() => sampleScores.value.samples[index], (newScores) => {
    updateOverallScore(newScores);
  }, { deep: true });
});
</script>

<style scoped>
.my-range {
  -webkit-appearance: none;
  height: 10px;
  border-radius: 4px;
  outline: none;
  cursor: pointer;
  margin: 0;
  padding: 0;
  background-size: 100% 100%;
  background-repeat: no-repeat;
  transition: all 0.2s ease;
}

.my-range:hover {
  height: 10px;
}

.my-range::-webkit-slider-thumb {
  -webkit-appearance: none;
  height: 0px;
  width: 0px;
  border-radius: 50%;
  background-color: #1976D2;
  border: 0px solid #fff;
  box-shadow: 0 1px 3px rgba(0,0,0,0.2);
  cursor: pointer;
  margin-top: -5px;
  transition: all 0.2s ease;
}

.my-range::-moz-range-thumb {
  height: 0px;
  width: 0px;
  border-radius: 50%;
  background-color: #1976D2;
  border: 2px solid #fff;
  box-shadow: 0 1px 3px rgba(0,0,0,0.2);
  cursor: pointer;
  transition: all 0.2s ease;
}

.my-range::-webkit-slider-thumb:hover {
  transform: scale(1.1);
  box-shadow: 0 2px 4px rgba(0,0,0,0.3);
}

.my-range::-moz-range-thumb:hover {
  transform: scale(1.1);
  box-shadow: 0 2px 4px rgba(0,0,0,0.3);
}

/* Style number inputs */
.form-control {
  border: 2px solid #e0e0e0;
  border-radius: 6px;
  padding: 4px;
  font-size: 16px; /* Better for mobile */
  min-height: 30px;
  transition: all 0.2s ease;
  text-align: center;
  box-shadow: inset 0 1px 2px rgba(0,0,0,0.05);
}

.form-control:hover {
  border-color: #bbdefb;
}

.form-control:focus {
  border-color: #1976D2;
  box-shadow: 0 0 0 3px rgba(25, 118, 210, 0.1);
  outline: none;
}

/* Improve labels */
.form-label {
  font-weight: 500;
  color: #424242;
  font-size: 14px;
}

/* Container spacing */
.gap-3 {
  gap: 1rem !important;
}

.mb-3 {
  margin-bottom: 1.25rem !important;
}

.nav-tabs {
  flex-wrap: nowrap;
  overflow-x: auto;
  scrollbar-width: none;
  -ms-overflow-style: none;
  -webkit-overflow-scrolling: touch;
}

.nav-tabs .nav-link {
  border: 3px solid transparent;
  border-top-left-radius: 6px;
  border-top-right-radius: 6px;
  margin-bottom: -4px;
  white-space: nowrap;
  padding: 12px;
  font-size: 14px;
  color: #6c757d;
  transition: all 0.2s ease;
}

@media (max-width: 768px) {
  .gap-3 {
    gap: 0.75rem !important;
  }

  .mb-3 {
    margin-bottom: 1rem !important;
  }

  .form-label {
    font-size: 13px;
    min-width: 80px !important;
  }

  .row {
    margin: 0 -8px;
  }

  .col-md-6 {
    padding: 0 8px;
  }

  /* Stack labels and inputs vertically on very small screens */
  @media (max-width: 480px) {
    .d-flex.justify-content-between.align-items-center {
      flex-direction: column;
      align-items: stretch !important;
      gap: 0.5rem;
    }

    .form-control {
      width: 100% !important;
    }

    .form-label {
      text-align: left;
      width: 100%;
    }
  }
}

.nav-tabs::-webkit-scrollbar {
  display: none;
}

.nav-tabs .nav-link:hover {
  border-color: #e9ecef #e9ecef #dee2e6;
  background-color: #f8f9fa;
}

.nav-tabs .nav-link.active {
  color: #1976D2;
  background-color: #fff;
  border-color: #dee2e6 #dee2e6 #fff;
  border-width: 2px;
  font-weight: 500;
}

.btn {
  min-height: 44px;
  font-size: 16px;
}

.btn-sm {
  min-height: 36px;
}

/* Better spacing for mobile */
.p-4 {
  padding: 1rem !important;
}

@media (min-width: 576px) {
  .p-4 {
    padding: 1.5rem !important;
  }
}
</style>
