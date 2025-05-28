<template>
    <div class="container py-4">
      <div class="card shadow-sm">
        <div class="card-header bg-primary text-white">
          <h3 class="mb-0">Test Progress Tracking</h3>
        </div>
        <div class="card-body">
          <div class="mb-3 d-flex justify-content-between">
            <div class="w-75 me-2">
              <input
                v-model="searchQuery"
                type="text"
                class="form-control"
                placeholder="Search by email, test id, type, or description..."
              />
            </div>
            <button @click="downloadCSV" class="btn btn-success">
              Download CSV
            </button>
          </div>
          <div v-if="error" class="alert alert-danger">
            {{ error }}
          </div>
          <div v-else class="table-responsive">
            <table class="table table-hover">
              <thead class="table-light">
                <tr>
                  <th>Email</th>
                  <th>Test ID</th>
                  <th>Test Type</th>
                  <th>Test Description</th>
                  <th>Pages Completed / Total Pages</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(item, index) in paginatedData" :key="index">
                  <td>{{ item.email }}</td>
                  <td>{{ item.test_id }}</td>
                  <td>{{ item.test_type }}</td>
                  <td>{{ item.test_desc }}</td>
                  <td>{{ item.completed_pages }} / {{ item.total_pages }}</td>
                </tr>
              </tbody>
            </table>
            <div v-if="filteredTrackingData.length === 0" class="text-center text-muted mt-3">
              No matching records found.
            </div>
            <div v-if="totalPages > 1" class="d-flex justify-content-between align-items-center mt-3">
              <button :disabled="currentPage === 1" @click="currentPage--" class="btn btn-secondary">
                Previous
              </button>
              <span>Page {{ currentPage }} of {{ totalPages }}</span>
              <button :disabled="currentPage === totalPages" @click="currentPage++" class="btn btn-secondary">
                Next
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </template>
  
  <script setup>
  import { ref, computed, onMounted, watch } from 'vue'
  import { API_BASE_URL } from '@/config'
  import router from '@/router'
  
  const trackingData = ref([])
  const error = ref(null)
  const searchQuery = ref('')
  const currentPage = ref(1)
  const itemsPerPage = 20
  
  const fetchTrackingData = async () => {
    try {
      const token = localStorage.getItem('authToken')
      const response = await fetch(`${API_BASE_URL}/tracking`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })
      if (!response.ok) {
        router.push('/')
        throw new Error('Failed to fetch tracking data.')
      }
      trackingData.value = await response.json()
    } catch (err) {
      console.error(err)
      error.value = 'Unable to load tracking data. Please try again later.'
    }
  }
  
  // Fuzzy search function
  const fuzzyMatch = (item, query) => {
    if (!query) return true;
    const q = query.toLowerCase();
    return (
      (item.email && item.email.toLowerCase().includes(q)) ||
      (String(item.test_id) && String(item.test_id).toLowerCase().includes(q)) ||
      (item.test_type && item.test_type.toLowerCase().includes(q)) ||
      (item.test_desc && item.test_desc.toLowerCase().includes(q))
    )
  }
  
  const filteredTrackingData = computed(() => {
    return trackingData.value.filter(item => fuzzyMatch(item, searchQuery.value))
  })
  
  const totalPages = computed(() => {
    return Math.ceil(filteredTrackingData.value.length / itemsPerPage) || 1
  })
  
  const paginatedData = computed(() => {
    const start = (currentPage.value - 1) * itemsPerPage
    return filteredTrackingData.value.slice(start, start + itemsPerPage)
  })
  
  watch(searchQuery, () => {
    currentPage.value = 1
  })
  
  const downloadCSV = () => {
    const headers = ['Email', 'Test ID', 'Test Type', 'Test Description', 'Pages Completed', 'Total Pages']
    const rows = paginatedData.value.map(item => [
      item.email,
      item.test_id,
      item.test_type,
      item.test_desc,
      item.completed_pages,
      item.total_pages
    ])
  
    let csvContent = headers.join(',') + '\n'
    rows.forEach(row => {
      csvContent += row.map(value => `"${value}"`).join(',') + '\n'
    })
  
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.setAttribute('href', url)
    link.setAttribute('download', 'tracking_data.csv')
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }
  
  onMounted(() => {
    if (!localStorage.getItem('authToken')) {
      router.push('/login')
    }
    fetchTrackingData()
  })
  </script>
  
  <style scoped>
  .card {
    margin-top: 20px;
    border-radius: 8px;
  }
  
  .card-header {
    border-bottom: none;
  }
  
  .table-responsive {
    margin-top: 15px;
  }
  
  .table-hover tbody tr:hover {
    background-color: #f8f9fa;
  }
  
  input::placeholder {
    color: #6c757d;
  }
  </style>