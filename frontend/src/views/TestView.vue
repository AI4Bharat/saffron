<template>
  <div class="container py-4">
    <!-- Progress Bar -->
    <div class="progress mb-4 vh-10">
      <div
        class="progress-bar"
        role="progressbar"
        :style="{ width: `${progress}%` }"
        :aria-valuenow="progress"
        aria-valuemin="0"
        aria-valuemax="100"
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
      :currentIndex="currentIndex"
      @next="handleNext"
    />

    <!-- Page Number -->
    <div class="page-number mt-4 text-center">
      Page {{ currentIndex + 1 }}
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import HFR from '@/components/HFR.vue'
import Mushra from '@/components/Mushra.vue'
import MushraGranular from '@/components/MushraGranular.vue'
import HFRGranular from '@/components/HFRGranular.vue'
import { API_BASE_URL } from '@/config';
import CMOS from '@/components/CMOS.vue'

const router = useRouter()
const route = useRoute()

// State
const data = ref(null)
const testData = ref([])
const currentIndex = ref(0)
const test_id = ref(null)
const error = ref(null)

// Computed
const progress = computed(() => {
  return testData.value.length
    ? Math.round((currentIndex.value / testData.value.length) * 100)
    : 0
})

const currentTest = computed(() => {
  // console.log('currentTest', testData.value[currentIndex.value])
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
        router.push('/completion');
      } else {
        // Test is not complete - refresh the page
        window.location.reload();
      }
    } catch (err) {
      console.error('Error verifying test completion:', err);
      window.location.reload();
    }
  } else {
    currentIndex.value++;
  }
}

// Lifecycle hooks
onMounted(async () => {
  try {
    const token = localStorage.getItem('authToken')
    const response = await fetch(`${API_BASE_URL}/test/${route.params.id}`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    })
    if (!response.ok) {
      throw new Error('Failed to fetch test data.')
    }
    const responseData = await response.json()
    data.value = responseData
    currentIndex.value = Number(responseData.page_no) || 0
    testData.value = responseData.json_entry || []
    test_id.value = responseData.test_id

    if (currentIndex.value >= testData.value.length) {
      router.push('/completion')
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
