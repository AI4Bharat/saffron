<template>
  <div class="grounding-page p-4 bg-light rounded">
    <h1 class="text-center mb-4">Grounding Page</h1>
    <p class="text-center mb-4">Please listen to the following audio samples to understand what human speech sounds like.</p>
    <div class="audio-samples">
      <div v-for="(audio, index) in audioSamples" :key="index" class="audio-sample mb-4">
        <div class="waveform-container">
          <div :id="`waveform-${index}`" class="waveform"></div>
          <div class="controls">
            <button
              class="btn btn-primary play-btn"
              @click="togglePlay(index)"
              :disabled="loading[index]"
            >
              <div v-if="loading[index]" class="spinner-border spinner-border-sm" role="status">
                <span class="visually-hidden">Loading...</span>
              </div>
              <i v-else :class="isPlaying[index] ? 'bi bi-pause-fill' : 'bi bi-play-fill'"></i>
            </button>
            <span class="time">{{ formatTime(currentTime[index]) }} / {{ formatTime(duration[index]) }}</span>
          </div>
        </div>
      </div>
    </div>
    <div class="alert alert-info mt-4" role="alert">
      <strong>Disclaimer:</strong> When you click "Start Screening Test," an 8-minute timer will start. You’ll listen to 10 audio samples and decide if each one is human or machine-generated. To pass, you need to correctly identify most of the human samples.
      <br><br>
      <strong>Important:</strong> If you refresh the page during the screening test, the test will restart from the beginning, but the timer will keep running in the background. You won’t get extra time, so please avoid refreshing the page.
      <!-- <br><br> -->
      <!-- <strong>Note:</strong> This behavior applies only to the screening test. The main study does not have a timer and will not be affected if you refresh the page. -->
    </div>
    <div class="text-center mt-4">
      <button class="btn btn-primary btn-lg" @click="proceedToTest">Starting Screening Test</button>
    </div>

  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import WaveSurfer from 'https://cdn.jsdelivr.net/npm/wavesurfer.js@7/dist/wavesurfer.esm.js'

const audioSamples = ref([
  'https://d6ehh39do7g33.cloudfront.net/tts-evaluation/ground_truth/conv-disgusted.wav',
  'https://d6ehh39do7g33.cloudfront.net/tts-evaluation/ground_truth/conv-fearful.wav',
  'https://d6ehh39do7g33.cloudfront.net/tts-evaluation/ground_truth/read-confused.wav',
  'https://d6ehh39do7g33.cloudfront.net/tts-evaluation/ground_truth/read-default.wav',
  'https://d6ehh39do7g33.cloudfront.net/tts-evaluation/ground_truth/read-happy.wav'
])

const emit = defineEmits(['grounding-completed'])
const wavesurfers = ref([])
const isPlaying = ref(Array(audioSamples.value.length).fill(false))
const loading = ref(Array(audioSamples.value.length).fill(true))
const currentTime = ref(Array(audioSamples.value.length).fill(0))
const duration = ref(Array(audioSamples.value.length).fill(0))

onMounted(() => {
  audioSamples.value.forEach((audio, index) => {
    const wavesurfer = WaveSurfer.create({
      container: `#waveform-${index}`,
      backgroundColor: '#ffffff',
      waveColor: '#2196F3',
      progressColor: '#1565C0',
      cursorColor: '#2c5282',
      height: 80,
      barWidth: 3,
      barGap: 1,
      responsive: true,
      normalize: true
    })

    wavesurfer.load(audio)
    wavesurfers.value[index] = wavesurfer

    wavesurfer.on('ready', () => {
      loading.value[index] = false
      duration.value[index] = wavesurfer.getDuration()
    })

    wavesurfer.on('audioprocess', () => {
      currentTime.value[index] = wavesurfer.getCurrentTime()
    })

    wavesurfer.on('finish', () => {
      isPlaying.value[index] = false
    })
  })
})

onBeforeUnmount(() => {
  wavesurfers.value.forEach(ws => ws?.destroy())
})

const togglePlay = (index) => {
  wavesurfers.value[index].playPause()
  isPlaying.value[index] = !isPlaying.value[index]
}

const formatTime = (time) => {
  if (!time) return '0:00'
  const minutes = Math.floor(time / 60)
  const seconds = Math.floor(time % 60)
  return `${minutes}:${seconds.toString().padStart(2, '0')}`
}

const proceedToTest = () => {
  emit('grounding-completed')
}
</script>

<style scoped>
.grounding-page {
  max-width: 800px;
  margin: 0 auto;
  box-shadow: 0px 4px 10px rgba(0, 0, 0, 0.1);
}

.waveform-container {
  background: white;
  padding: 1rem;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}

.waveform {
  margin-bottom: 1rem;
}

.controls {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.time {
  font-family: monospace;
  font-size: 0.9rem;
  color: #666;
}

.play-btn {
  width: 40px;
  height: 40px;
  padding: 0;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.play-btn:hover:not(:disabled) {
  transform: scale(1.05);
  background-color: #0056b3;
}

.play-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.controls {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.time {
  font-family: monospace;
  color: #666;
}
</style>
