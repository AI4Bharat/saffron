<template>
  <div class="bg-white p-4 rounded shadow-sm border h-100">
    <div class="d-flex align-items-start justify-content-between gap-2 mb-2">
      <h5 class="fw-bold text-dark mb-0">
        <i class="bi bi-shield-lock-fill me-2 text-primary"></i>Password resets
      </h5>
      <button class="btn btn-sm btn-outline-secondary" :disabled="loading" @click="load">
        <span v-if="loading" class="spinner-border spinner-border-sm"></span>
        <i v-else class="bi bi-arrow-clockwise"></i>
      </button>
    </div>
    <p class="text-muted text-xs mb-3">
      When someone uses “Forgot password?” on the sign-in page their request lands here.
      Issue a link and send it to them — it works once and expires in
      {{ ttlHours }} hours.
    </p>

    <!-- the link, shown once -->
    <div v-if="issued" class="alert alert-success py-2 px-3 mb-3">
      <div class="fw-semibold small mb-1">
        Link for {{ issued.name }} — copy it now, it is not shown again
      </div>
      <div class="d-flex gap-2 align-items-center">
        <input ref="linkInput" :value="issued.link" readonly
               class="form-control form-control-sm font-monospace" style="font-size:.72rem">
        <button class="btn btn-sm btn-success px-3" @click="copy">
          {{ copied ? 'Copied' : 'Copy' }}
        </button>
      </div>
      <div class="text-xs text-muted mt-1">Expires {{ prettyTime(issued.expires_at) }}.</div>
    </div>

    <div v-if="error" class="alert alert-danger py-2 px-3 small mb-3">{{ error }}</div>

    <div v-if="!requests.length && !loading" class="text-muted small">
      No one is waiting for a reset.
    </div>

    <div v-for="r in requests" :key="r.id"
         class="d-flex align-items-center justify-content-between gap-2 border rounded p-2 mb-2">
      <div class="min-w-0">
        <div class="fw-semibold small text-truncate">{{ r.name }}</div>
        <div class="text-muted text-xs text-truncate">
          {{ r.email || 'no email on file' }} · asked {{ prettyTime(r.requested_at) }}
          <span v-if="r.status === 'issued'" class="badge bg-info-subtle text-info ms-1">
            link sent{{ r.expired ? ', expired' : '' }}
          </span>
        </div>
      </div>
      <div class="d-flex gap-1 flex-shrink-0">
        <button class="btn btn-sm btn-primary" :disabled="busyId === r.id" @click="issue(r)">
          <span v-if="busyId === r.id" class="spinner-border spinner-border-sm"></span>
          <span v-else>{{ r.status === 'issued' ? 'New link' : 'Issue link' }}</span>
        </button>
        <button class="btn btn-sm btn-outline-secondary" :disabled="busyId === r.id"
                title="Dismiss this request" @click="dismiss(r)">
          <i class="bi bi-x-lg"></i>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { API_BASE_URL } from '@/config'
import { authHeaders } from '@/session'

const ttlHours = 2
const requests = ref([])
const loading = ref(false)
const error = ref('')
const busyId = ref(null)
const issued = ref(null)
const copied = ref(false)
const linkInput = ref(null)

async function call(path, opts = {}) {
  const r = await fetch(`${API_BASE_URL}${path}`, { headers: authHeaders(), ...opts })
  const d = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(d.message || `Request failed (${r.status})`)
  return d
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const d = await call('/admin/password_resets')
    requests.value = d.requests || []
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function issue(r) {
  busyId.value = r.id
  error.value = ''
  try {
    issued.value = await call(`/admin/password_resets/${r.id}/issue`, { method: 'POST' })
    copied.value = false
    await load()
    await nextTick()
    linkInput.value?.select()
  } catch (e) {
    error.value = e.message
  } finally {
    busyId.value = null
  }
}

async function dismiss(r) {
  busyId.value = r.id
  try {
    await call(`/admin/password_resets/${r.id}/dismiss`, { method: 'POST' })
    await load()
  } catch (e) {
    error.value = e.message
  } finally {
    busyId.value = null
  }
}

async function copy() {
  try {
    await navigator.clipboard.writeText(issued.value.link)
    copied.value = true
  } catch (e) {
    // Clipboard access can be refused; selecting lets them copy by hand.
    linkInput.value?.select()
  }
}

function prettyTime(iso) {
  if (!iso) return ''
  const d = new Date(iso.endsWith('Z') ? iso : iso + 'Z')
  if (isNaN(d)) return iso
  return d.toLocaleString('en-IN', { day: '2-digit', month: 'short',
                                     hour: '2-digit', minute: '2-digit' })
}

onMounted(load)
</script>
