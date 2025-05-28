<template>
  <div class="container py-4">
    <ConsentForm
      v-if="!consentGiven"
      @consent-given="handleConsent"
    />
    <template v-else>
      <div>
        <!-- Progress Bar -->
        <div class="progress mb-4 vh-10">
          <div
            class="progress-bar"
            role="progressbar"
            :style="{ width: `${progress}%` }"
            :aria-valuenow="progress"
            aria-valuemin="0"
            aria-valuemax="100"
            style="color: linear-gradient(45deg, #1976D2, #2196F3);"
          >
            {{ progress }}%
          </div>
        </div>

        <!-- Error Message -->
        <div v-if="error" class="alert alert-danger" role="alert">
          {{ error }}
        </div>

        <component
          v-if="currentTest"
          :is="currentTestComponent"
          :current-test="currentTest"
          :can-proceed="true"
          :is-last-test="isLast"
          :test_id="test_id"
          :session_id="props.session_id"
          :currentIndex="currentIndex"
          @next="handleNext"
        />

        <!-- Page Number -->
        <div class="page-number mt-4 text-center">
          Page {{ currentIndex + 1 }}
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import HFR from '@/components/HFR.vue'
import Mushra from '@/components/Mushra.vue'
import MushraGranular from '@/components/MushraGranular.vue'
import HFRGranular from '@/components/HFRGranular.vue'
import { API_BASE_URL } from '@/config';
import CMOS from '@/components/CMOS.vue'

// Receive props from the router
const props = defineProps({
  prolific_pid: String,
  study_id: String,
});

// State
const data = ref(null)
const testData = ref([])
const currentIndex = ref(0)
const test_id = ref(null)
const error = ref(null)
const consentGiven = ref(false)
const completionurl = ref(null)
let token = ref(null)
const rejectionUrl = ref(null)

// Computed
const progress = computed(() => {
  return testData.value.length
    ? Math.round((currentIndex.value / testData.value.length) * 100)
    : 0
})

const handleConsent = async () => {
  try {
    const response = await fetch(`${API_BASE_URL}/prolific/consent/${test_id.value}`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token.value}`,
        'Content-Type': 'application/json'
      }
    });

    if (!response.ok) {
      throw new Error('Failed to submit consent');
    }

    // const responseData = await response.json();
    consentGiven.value = true

  } catch (error) {
    console.error('Error submitting consent:', error);
    // alert('Error submitting consent. Please try again.');
  }
}

const currentTest = computed(() => {
  return testData.value[currentIndex.value]
})

const isLast = computed(() => {
  return currentIndex.value === testData.value.length - 1
})

const currentTestComponent = computed(() => {
  if (!data.value?.test_type) return null

  const testComponents = {
    'hfr': HFR,
    'mushra-granular': MushraGranular,
    'hfr-granular': HFRGranular,
    'cmos': CMOS,
    'mushra': Mushra,
  }

  return testComponents[data.value.test_type]
})

// Methods
const handleNext = async () => {
  if (isLast.value) {
    try {
      const token = localStorage.getItem('authToken')
      const response = await fetch(`${API_BASE_URL}/verify_test/${test_id.value}`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.status === 200) {
        // Test is complete - redirect to completion URL
        window.location.href = completionurl.value;
      } else {
        // Test is not complete - refresh the page
        window.location.reload();
      }
    } catch (err) {
      console.error('Error verifying test completion:', err);
      error.value = 'Error verifying test completion';
    }
  } else {
    currentIndex.value++;
  }
}

// Lifecycle hooks
onMounted(async () => {
  try {
    const { prolific_pid, study_id, session_id } = props;
    if (!prolific_pid || !study_id || !session_id) {
      throw new Error('Missing required parameters')
    }

    const endpoint = `${API_BASE_URL}/prolific/study`;
    const params = new URLSearchParams({
      PROLIFIC_PID: prolific_pid,
      STUDY_ID: study_id,
      SESSION_ID: session_id
    });

    const finalUrl = `${endpoint}?${params.toString()}`;

    const response = await fetch(finalUrl, {
      method: 'GET',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Cache-Control': 'no-cache',
        'Upgrade-Insecure-Requests': '1',
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains'
      }
    });

    if (!response.ok) {
      console.error(response)
      throw new Error('Failed to fetch test data.')
    }
    const responseData = await response.json()
    token.value = responseData.token
    if (localStorage.getItem('authToken')) {
      localStorage.removeItem('authToken');
    }
    localStorage.setItem('authToken', token)
    data.value = responseData
    completionurl.value = responseData.completion_url
    currentIndex.value = Number(responseData.page_no) || 0
    testData.value = responseData.json_entry || []
    test_id.value = responseData.test_id
    consentGiven.value = responseData.consent
    rejectionUrl.value = responseData.rejection_url

    if (currentIndex.value >= testData.value.length) {
      window.location.href = completionurl.value;
    }
  } catch (err) {
    console.error('Error fetching test data:', err)
    error.value = 'Unable to load test data. Please try again later.'
  }
})
</script>

<style scoped>
.progress {
  height: 25px;
}

.alert {
  margin-bottom: 20px;
}

.page-number {
  font-size: 1rem;
  color: #555;
}
</style>
