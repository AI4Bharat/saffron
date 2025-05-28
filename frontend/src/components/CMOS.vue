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
          <span style="font-size: 1.2em;">Study Description and Instructions <strong>(CLICK TO EXPAND)</strong></span>
        </button>
        </div>
        <div class="collapse mt-3" id="audioGuidelines">
          <div class="card card-body">
            <h4 class="mb-4">Study Description and Instructions</h4>
            <p>
                In this study, you will evaluate the quality and naturalness of various audio recordings. Your assessments will contribute to advancements in speech synthesis technology.
            </p>

            <h5 class="mt-4">Equipment Requirements</h5>
            <ul>
                <li><strong>Device:</strong> Use a laptop or desktop computer.</li>
                <li><strong>Audio:</strong> Utilize high-quality headphones for accurate audio perception.</li>
                <li><strong>Environment:</strong> Ensure a quiet, distraction-free setting.</li>
            </ul>

            <h5 class="mt-4">Task Overview</h5>
            <p>
                You will be presented with multiple audio recordings, including a reference recording and one or more samples to evaluate. For each pair of recordings, you will:
            </p>
            <ul>
                <li><strong>Listen:</strong> Play the entire audio sample and the reference audio without interruption.</li>
                <li><strong>Evaluate:</strong> Assess the sample recording in comparison to the reference recording based on specific criteria outlined below.</li>
                <li><strong>Rate:</strong> Assign a CMOS score based on how much better or worse the sample is compared to the reference, using the scale provided below.</li>
                <li><strong>Navigate and Compare:</strong> Move through the audio pairs on the page. There are around 5-7 pairs per page. Listen to all pairs, rate them, and ensure your scoring is consistent and logical across all comparisons.</li>
            </ul>

            <h5 class="mt-4">Evaluation Criteria</h5>
            <p>When comparing the sample recording to the reference, consider the following aspects:</p>
            <ul>
                <li><strong>Liveliness:</strong> Does the sample sound more engaging, expressive, and human-like compared to the reference?</li>
                <li><strong>Voice Quality/Clarity:</strong> Is the voice in the sample clearer, more natural, or less digital compared to the reference?</li>
                <li><strong>Rhythm:</strong> Does the sample flow more naturally, or is it too fast or too slow compared to the reference?</li>
                <li><strong>Pronunciation:</strong> Are there more or fewer mild or severe pronunciation errors in the sample than in the reference?</li>
                <li><strong>Artifacts:</strong> Does the sample have more or fewer clicks, pops, or unnatural digital sounds than the reference?</li>
                <li><strong>Pauses and Timing:</strong> Are pauses, timing, or speed issues better handled in the sample compared to the reference?</li>
                <li><strong>Word Skips/Repetitions:</strong> Are there more or fewer skipped or repeated words in the sample than in the reference?</li>
            </ul>

            <h5 class="mt-4">Scoring Procedure</h5>
            <p>Provide a CMOS score for each pair of recordings, reflecting how much better or worse the sample is compared to the reference:</p>
            <ul>
                <li><strong>+3:</strong> The sample is much better than the reference.</li>
                <li><strong>+2:</strong> The sample is better than the reference.</li>
                <li><strong>+1:</strong> The sample is slightly better than the reference.</li>
                <li><strong>0:</strong> The sample is as good as the reference.</li>
                <li><strong>-1:</strong> The sample is slightly worse than the reference.</li>
                <li><strong>-2:</strong> The sample is worse than the reference.</li>
                <li><strong>-3:</strong> The sample is much worse than the reference.</li>
            </ul>
            <p>Use the scale to assign scores logically, ensuring consistency across all evaluations on the page.</p>


            <h5 class="mt-4">Quality Assurance</h5>
            <p><strong>Attentiveness:</strong> Hidden reference samples are included to ensure focus. Consistent inattentiveness may result in exclusion from the study.</p>

            <h5 class="mt-4">Confidentiality</h5>
            <p>Your responses will be anonymized and used solely for research purposes. <strong>Please do not share details of this study to maintain data integrity.</strong></p>

            <h5 class="mt-4">Completion</h5>
            <ul>
                <li>Ensure all recordings have been evaluated before submitting your responses.</li>
                <li>If you encounter any issues, please contact the researcher through the provided platform.</li>
            </ul>

            <p class="mt-4"><strong>Thank you for your valuable contribution to this study!</strong></p>
          </div>
        </div>
      </div>
    </div>
    <div class="bg-light p-3 p-sm-6 d-flex align-items-center justify-content-center">
      <div class="bg-white rounded shadow p-3 p-sm-4 w-100" style="max-width: 1200px;">
        <!-- Single waveform container -->
        <div class="mb-3">
          <div id="waveform" class="bg-secondary bg-opacity-10 rounded"></div>
        </div>

        <!-- Tab navigation -->
        <div class="tab-scroll-container">
          <ul class="nav nav-tabs mb-3">
            <!-- Reference Tab -->
            <li class="nav-item">
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
                <span class="ms-2 badge bg-secondary">{{ sampleScores.reference.overall || 0 }}</span>
            </button>
            </li>
            <!-- Test Audio Tabs -->
            <li class="nav-item" v-for="(audio, index) in props.currentTest.test_audios" :key="index">
          <div class="d-flex align-items-center">
            <button
              class="nav-link d-flex align-items-center"
              :class="{ active: activeTab === `sample-${index}` }"
              @click="setActiveTab(`sample-${index}`)"
            >
              S{{ index + 1 }}
              <button
            class="btn btn-sm ms-2"
            @click.stop="playAudioAndSetTab(`sample-${index}`)"
              >
            <i :class="isPlaying[`sample-${index}`] ? 'bi bi-pause-fill' : 'bi bi-play-fill'"></i>
              </button>
              <span class="ms-2 badge bg-secondary">{{ sampleScores.samples[index]?.overall || 0 }}</span>
            </button>
          </div>
            </li>
          </ul>
        </div>
        <br>
        <div v-if="currentSampleIndex >= 0">
    <div class="mb-2">
        <label class="form-label" style="font-size: 1rem; font-weight: 500;">
            How does this sample compare to the reference in terms of quality and naturalness?
        </label>
        </div>
  <div class="mb-3 d-flex justify-content-between align-items-center gap-3">
    <label class="form-label mb-0">Score:</label>
    <input
      type="range"
      class="my-range flex-grow-1"
      min="-3"
      max="3"
      step="0.5"
      v-model.number="getCurrentScore().overall"
      :style="{
        'background': `linear-gradient(to right, #1976D2 0%, #1976D2 ${(getCurrentScore().overall + 3) / 6 * 100}%, #e0e0e0 ${(getCurrentScore().overall + 3) / 6 * 100}%, #ddd 100%)`,
        'opacity': '0.9'
      }"
    />
    <input
      type="number"
      class="form-control form-control-sm"
      style="width: 70px"
      v-model.number="getCurrentScore().overall"
    />
  </div>
  <!-- Add labels below the range -->
  <div class="d-flex justify-content-between mt-2">
    <span style="font-size: 0.8rem; color: #424242; font-weight: 400;">Much worse</span>
    <span style="font-size: 0.8rem; color: #424242; font-weight: 400;">worse</span>
    <span style="font-size: 0.8rem; color: #424242; font-weight: 400;">slightly worse</span>
    <span style="font-size: 0.8rem; color: #424242; font-weight: 400;">Both are equal</span>
    <span style="font-size: 0.8rem; color: #424242; font-weight: 400;">Slightly better</span>
    <span style="font-size: 0.8rem; color: #424242; font-weight: 400;">Better</span>
    <span style="font-size: 0.8rem; color: #424242; font-weight: 500;">Much better</span>
  </div>
</div>

        <small v-if="!canSubmit" class="text-muted d-block mt-2">
          Please listen to all audios completely for enabling the Submit button.
        </small>
        <!-- :disabled="!canSubmit" -->
        <button
          class="btn btn-primary w-100"
          :disabled="!canSubmit || isSubmitting"
          @click="handleNext"
        >
          <span v-if="isSubmitting" class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
          {{ isSubmitting ? 'Submitting...' : 'Submit Ratings' }}
        </button>
      </div>
    </div>
  </template>

  <script setup>
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
  const isSubmitting = ref(false)

  // State
  const isPlaying = ref({
    reference: true,
    hidden_reference: false,
    ...Object.fromEntries(props.currentTest.test_audios.map((_, index) => [`sample-${index}`, false]))
  })
  const audioProgress = ref({
    reference: 0,
    ...Object.fromEntries(props.currentTest.test_audios.map((_, index) => [`sample-${index}`, 0]))
  })
  const startTime = ref(Date.now())
  const activeTab = ref('reference')
  const currentWavesurfer = ref(null)
  const sampleScores = ref({
    reference: {
      overall: 0,
    },
    samples: Array(props.currentTest.test_audios.length).fill().map(() => ({
      overall: 0,
    }))
  })

  const currentSampleIndex = computed(() => {
    if (activeTab.value === 'reference') return -1;
    return parseInt(activeTab.value.split('-')[1]);
  })

  // Computed
  const canSubmit = computed(() => {
    // Check if all samples have been fully listened to
    const allSamplesPlayed = Object.entries(audioProgress.value)
      .filter(([key]) => key !== 'reference')
      .every(([progress]) => progress >= 0.99);

    // Check if all ratings are set
    const referenceRated = sampleScores.value.reference.overall !== undefined;
    const allSamplesRated = sampleScores.value.samples.every(sample =>
      sample.overall !== undefined
    );

    return allSamplesPlayed && referenceRated && allSamplesRated;
  })

  const calculateOverallScore = (scores) => {
    return scores.overall; // Keep the overall score as-is, directly editable by the user.
    };

  const updateOverallScore = (scores) => {
    scores.overall = calculateOverallScore(scores);
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

  const getCurrentScore = () => {
    return activeTab.value === 'reference'
      ? sampleScores.value.reference
      : sampleScores.value.samples[currentSampleIndex.value]
  }

  const handleNext = async () => {
    if (isSubmitting.value) return
    const endTime = Date.now()
    const timeTaken = (endTime - startTime.value) / 1000

    try {
      isSubmitting.value = true
      const token = localStorage.getItem('authToken')
      const results_json = {
        text: "",
        language: "",
        reference: {
          url: props.currentTest.reference_audio,
          score: sampleScores.value.reference.overall,
          label: sampleScores.value.reference.overall >= 50 ? 'Preferred' : 'Not Preferred',
          attributes: { ...sampleScores.value.reference }
        },
        audios: props.currentTest.test_audios.map((audio, index) => ({
          url: audio.audio_path,
          system: audio.class,
          score: sampleScores.value.samples[index].overall,
          label: sampleScores.value.samples[index].overall >= 50 ? 'Preferred' : 'Not Preferred',
          attributes: { ...sampleScores.value.samples[index] }
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
        reference: {
            overall: 0
        },
        samples: Array(props.currentTest.test_audios.length).fill().map(() => ({
            overall: 0
        }))
    };


      startTime.value = Date.now()
      await setActiveTab('reference')

      // Reset audio progress
      audioProgress.value = {
        reference: 0,
        ...Object.fromEntries(props.currentTest.test_audios.map((_, index) => [`sample-${index}`, 0]))
      }

    } catch (error) {
      console.error('Error submitting ratings:', error)
      alert('Error submitting ratings. Please try again.')
    } finally {
      isSubmitting.value = false
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
    overflow-x: scroll;
    scrollbar-width: none;
    -ms-overflow-style: none;
    -webkit-overflow-scrolling: touch;
  }

  .nav-tabs .nav-link {
    padding: 50px;
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
  .tab-scroll-container {
    overflow-x: scroll;
    scrollbar-width: thin;
    scrollbar-color: #1976D2 #f0f0f0;

    /* For WebKit browsers */
      &::-webkit-scrollbar {
      height: 8px;
    }
    &::-webkit-scrollbar-track {
      background: #f0f0f0;
    }
    &::-webkit-scrollbar-thumb {
      background: #a0a0a0;
      border-radius: 4px;
    }
  }

      .tab-scroll-container::-webkit-scrollbar {
        height: 8px;
        display: block;
        height: 12px;
      }

      .tab-scroll-container::-webkit-scrollbar-track {
        background: #f0f0f0;
        border-radius: 4px;
      }

      .tab-scroll-container::-webkit-scrollbar-thumb {
        background: #1976D2;
        border-radius: 4px;
      }

      .tab-scroll-container::-webkit-scrollbar-thumb:hover {
        background: #1565C0;
      }

      .nav-tabs {
        flex-wrap: nowrap;
        min-width: min-content;
      }

  .score {
    margin-top: 4px;
    font-weight: bold;
  }
  .play-button {
    margin-top: 8px;
  }

  </style>
