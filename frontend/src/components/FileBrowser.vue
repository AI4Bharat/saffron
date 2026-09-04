<template>
  <div>
    <!-- header: where you are, and what the bucket holds -->
    <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
      <div>
        <h3 class="fw-bold text-dark m-0 fs-5">
          <i class="bi bi-hdd-network me-2 text-primary"></i>Files
        </h3>
        <p class="text-muted text-xs mb-0">
          <span class="font-monospace">{{ bucket || '—' }}</span>
          <span v-if="usage"> · {{ usage.objects.toLocaleString() }} file(s) ·
            {{ human(usage.bytes) }}</span>
        </p>
      </div>
      <div class="d-flex gap-2">
        <button class="btn btn-sm btn-outline-secondary" :disabled="loading" @click="load()">
          <span v-if="loading" class="spinner-border spinner-border-sm"></span>
          <i v-else class="bi bi-arrow-clockwise"></i>
        </button>
        <button class="btn btn-sm btn-outline-primary" @click="newFolder">
          <i class="bi bi-folder-plus me-1"></i>New folder
        </button>
        <button v-if="files.length" class="btn btn-sm btn-outline-primary"
                :disabled="bulk.busy" @click="downloadHere">
          <span v-if="bulk.busy" class="spinner-border spinner-border-sm me-1"></span>
          <i v-else class="bi bi-download me-1"></i>Download all ({{ files.length }})
        </button>
        <button class="btn btn-sm btn-primary" :disabled="uploading" @click="pickFiles">
          <span v-if="uploading" class="spinner-border spinner-border-sm me-1"></span>
          <i v-else class="bi bi-upload me-1"></i>Upload
        </button>
        <input ref="fileInput" type="file" multiple class="d-none" @change="onPicked">
      </div>
    </div>

    <!-- breadcrumbs -->
    <nav class="mb-2">
      <ol class="breadcrumb mb-0 small">
        <li class="breadcrumb-item">
          <a href="#" @click.prevent="go('')"><i class="bi bi-house-door"></i></a>
        </li>
        <li v-for="(c, i) in breadcrumbs" :key="c.prefix"
            class="breadcrumb-item" :class="{ active: i === breadcrumbs.length - 1 }">
          <a v-if="i < breadcrumbs.length - 1" href="#" @click.prevent="go(c.prefix)">{{ c.name }}</a>
          <span v-else>{{ c.name }}</span>
        </li>
      </ol>
    </nav>

    <div v-if="bulk.busy || bulk.done" class="alert alert-info py-2 px-3 small d-flex align-items-center gap-2">
      <span v-if="bulk.busy" class="spinner-border spinner-border-sm"></span>
      <i v-else class="bi bi-check-circle-fill"></i>
      <span>
        <template v-if="bulk.busy">Downloading {{ bulk.at }} of {{ bulk.total }}…</template>
        <template v-else>Started {{ bulk.total }} download(s). Your browser may ask
          permission to save several files.</template>
      </span>
      <button v-if="!bulk.busy" class="btn btn-link btn-sm p-0 ms-auto"
              @click="bulk.done = false">Dismiss</button>
    </div>

    <div v-if="error" class="alert alert-danger py-2 px-3 small">{{ error }}</div>
    <div v-if="notice" class="alert alert-success py-2 px-3 small">{{ notice }}</div>

    <!-- drop zone + listing -->
    <div class="border rounded" :class="{ 'drop-hot': dragging }"
         @dragover.prevent="dragging = true"
         @dragleave.prevent="dragging = false"
         @drop.prevent="onDrop">
      <table class="table table-hover align-middle mb-0">
        <thead class="table-light">
          <tr>
            <th style="width:52%">Name</th>
            <th style="width:14%" class="text-end">Size</th>
            <th style="width:20%">Modified</th>
            <th style="width:14%"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="prefix">
            <td colspan="4">
              <a href="#" class="text-decoration-none" @click.prevent="goUp">
                <i class="bi bi-arrow-90deg-up me-2"></i>..
              </a>
            </td>
          </tr>

          <tr v-for="f in folders" :key="f.prefix">
            <td>
              <a href="#" class="text-decoration-none fw-semibold" @click.prevent="go(f.prefix)">
                <i class="bi bi-folder-fill text-warning me-2"></i>{{ f.name }}
              </a>
            </td>
            <td class="text-end text-muted">—</td>
            <td class="text-muted">—</td>
            <td class="text-end text-nowrap">
              <button class="btn btn-sm btn-link p-0 me-2" title="Download everything in this folder"
                      :disabled="bulk.busy" @click="downloadFolder(f)">
                <i class="bi bi-download"></i>
              </button>
              <button class="btn btn-sm btn-link text-danger p-0"
                      title="Delete this folder and everything in it"
                      @click="askDelete(f.prefix, f.name, true)">
                <i class="bi bi-trash"></i>
              </button>
            </td>
          </tr>

          <tr v-for="f in files" :key="f.key">
            <td>
              <i :class="icon(f.name)" class="me-2 text-secondary"></i>{{ f.name }}
            </td>
            <td class="text-end text-muted">{{ human(f.size) }}</td>
            <td class="text-muted text-xs">{{ when(f.modified) }}</td>
            <td class="text-end text-nowrap">
              <button v-if="isAudio(f.name)" class="btn btn-sm btn-link p-0 me-2"
                      title="Play" @click="play(f)">
                <i class="bi" :class="playingKey === f.key ? 'bi-pause-circle' : 'bi-play-circle'"></i>
              </button>
              <button class="btn btn-sm btn-link p-0 me-2" title="Download"
                      @click="download(f)">
                <i class="bi bi-download"></i>
              </button>
              <button class="btn btn-sm btn-link text-danger p-0" title="Delete"
                      @click="askDelete(f.key, f.name, false)">
                <i class="bi bi-trash"></i>
              </button>
            </td>
          </tr>

          <tr v-if="!loading && !folders.length && !files.length">
            <td colspan="4" class="text-center text-muted py-4">
              <i class="bi bi-cloud-arrow-up fs-3 d-block mb-2 opacity-50"></i>
              This folder is empty — drop files here, or use Upload.
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <p v-if="truncated" class="text-muted text-xs mt-2 mb-0">
      Showing the first 1,000 entries in this folder.
    </p>

    <!-- Deleting is not undoable, so it takes a deliberate act: the exact name
         has to be typed before the button turns on. -->
    <div v-if="del.open" class="fb-backdrop" @click.self="cancelDelete">
      <div class="fb-dialog">
        <h5 class="fw-bold text-danger mb-2">
          <i class="bi bi-exclamation-triangle-fill me-2"></i>
          Delete {{ del.isFolder ? 'folder' : 'file' }}?
        </h5>
        <p class="small mb-2">
          You are about to permanently delete
          <strong class="font-monospace">{{ del.name }}</strong>.
        </p>
        <div v-if="del.isFolder" class="alert alert-warning py-2 px-3 small">
          <div v-if="del.counting"><span class="spinner-border spinner-border-sm me-1"></span>
            Checking what is inside…</div>
          <div v-else>
            This removes <strong>{{ del.count }}</strong> file(s),
            <strong>{{ human(del.bytes) }}</strong> in total, including everything
            in sub-folders.
          </div>
        </div>
        <p class="small text-muted mb-2">
          This cannot be undone. Type <strong class="font-monospace">{{ del.name }}</strong>
          to confirm.
        </p>
        <input v-model="del.typed" class="form-control form-control-sm mb-3"
               :placeholder="del.name" autocomplete="off" spellcheck="false"
               @keyup.enter="del.typed === del.name && doDelete()">
        <div class="d-flex justify-content-end gap-2">
          <button class="btn btn-sm btn-outline-secondary" @click="cancelDelete">Cancel</button>
          <button class="btn btn-sm btn-danger" :disabled="del.typed !== del.name || del.busy"
                  @click="doDelete">
            <span v-if="del.busy" class="spinner-border spinner-border-sm me-1"></span>
            Delete permanently
          </button>
        </div>
      </div>
    </div>

    <!-- inline player, so audio can be checked without downloading -->
    <div v-if="playing" class="border rounded p-2 mt-3 d-flex align-items-center gap-2">
      <span class="text-truncate small fw-semibold">{{ playing.name }}</span>
      <audio :src="playing.url" controls autoplay class="flex-grow-1" style="height:34px"
             @ended="playing = null"></audio>
      <button class="btn btn-sm btn-link text-muted" @click="playing = null">
        <i class="bi bi-x-lg"></i>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { API_BASE_URL } from '@/config'
import { authHeaders, authToken } from '@/session'

const bucket = ref('')
const prefix = ref('')
const breadcrumbs = ref([])
const folders = ref([])
const files = ref([])
const truncated = ref(false)
const usage = ref(null)
const loading = ref(false)
const uploading = ref(false)
const dragging = ref(false)
const error = ref('')
const notice = ref('')
const fileInput = ref(null)
const playing = ref(null)
const playingKey = ref('')
const bulk = ref({ busy: false, at: 0, total: 0, done: false })
const del = ref({ open: false, key: '', name: '', isFolder: false, typed: '',
                  busy: false, counting: false, count: 0, bytes: 0 })

async function call(path, opts = {}) {
  const r = await fetch(`${API_BASE_URL}${path}`, { headers: authHeaders(), ...opts })
  const d = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(d.message || `Request failed (${r.status})`)
  return d
}

async function load(p = null) {
  if (p !== null) prefix.value = p
  loading.value = true
  error.value = ''
  try {
    const d = await call(`/storage/list?prefix=${encodeURIComponent(prefix.value)}`)
    bucket.value = d.bucket
    breadcrumbs.value = d.breadcrumbs || []
    folders.value = d.folders || []
    files.value = d.files || []
    truncated.value = !!d.truncated
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function loadUsage() {
  try {
    usage.value = await call('/storage/usage')
  } catch (e) {
    // A slow or failing usage scan must not stop the browser working.
    usage.value = null
  }
}

function go(p) { load(p) }

function goUp() {
  const parts = prefix.value.split('/').filter(Boolean)
  parts.pop()
  load(parts.length ? parts.join('/') + '/' : '')
}

function pickFiles() { fileInput.value?.click() }

function onPicked(e) {
  const list = Array.from(e.target.files || [])
  if (list.length) upload(list)
  e.target.value = ''
}

function onDrop(e) {
  dragging.value = false
  const list = Array.from(e.dataTransfer?.files || [])
  if (list.length) upload(list)
}

async function upload(list) {
  uploading.value = true
  error.value = ''
  notice.value = ''
  try {
    const fd = new FormData()
    fd.append('prefix', prefix.value)
    for (const f of list) fd.append('files', f)
    // FormData sets its own content type, so only the token goes in the headers.
    const r = await fetch(`${API_BASE_URL}/storage/upload`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${authToken()}` },
      body: fd,
    })
    const d = await r.json().catch(() => ({}))
    if (!r.ok) throw new Error(d.message || 'Upload failed')
    notice.value = d.message
    if ((d.failed || []).length) {
      error.value = d.failed.map(f => `${f.name}: ${f.error}`).join('; ')
    }
    await load()
    loadUsage()
  } catch (e) {
    error.value = e.message
  } finally {
    uploading.value = false
  }
}

async function newFolder() {
  const name = window.prompt('Name for the new folder')
  if (!name) return
  error.value = ''
  try {
    await call('/storage/folder', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ prefix: prefix.value, name: name.trim() }),
    })
    await load()
  } catch (e) {
    error.value = e.message
  }
}

async function download(f) {
  error.value = ''
  try {
    const d = await call(`/storage/download?key=${encodeURIComponent(f.key)}`)
    // The presigned URL points straight at the store, so the file never goes
    // through the app server.
    const a = document.createElement('a')
    a.href = d.url
    a.download = f.name
    document.body.appendChild(a)
    a.click()
    a.remove()
  } catch (e) {
    error.value = e.message
  }
}

async function play(f) {
  if (playingKey.value === f.key) { playing.value = null; playingKey.value = ''; return }
  try {
    const d = await call(`/storage/preview?key=${encodeURIComponent(f.key)}`)
    playing.value = { name: f.name, url: d.url }
    playingKey.value = f.key
  } catch (e) {
    error.value = e.message
  }
}

function askDelete(key, name, isFolder) {
  del.value = { open: true, key, name, isFolder, typed: '', busy: false,
                counting: isFolder, count: 0, bytes: 0 }
  if (isFolder) countFolder(key)
}

function cancelDelete() {
  del.value.open = false
}

/** What is actually inside, so the dialog can say what will be lost. */
async function countFolder(prefix) {
  let count = 0
  let bytes = 0
  let cursor = ''
  try {
    for (let page = 0; page < 50; page++) {
      const qs = `prefix=${encodeURIComponent(prefix)}` + (cursor ? `&cursor=${encodeURIComponent(cursor)}` : '')
      const d = await call(`/storage/list?${qs}`)
      for (const f of d.files || []) { count += 1; bytes += f.size || 0 }
      // Sub-folders count too: a delete takes the whole prefix.
      for (const sub of d.folders || []) {
        const inner = await call(`/storage/list?prefix=${encodeURIComponent(sub.prefix)}`)
        for (const f of inner.files || []) { count += 1; bytes += f.size || 0 }
      }
      if (!d.truncated || !d.cursor) break
      cursor = d.cursor
    }
  } catch (e) {
    // A count we cannot take must not block the dialog; the warning still stands.
  }
  del.value.count = count
  del.value.bytes = bytes
  del.value.counting = false
}

async function doDelete() {
  if (del.value.typed !== del.value.name) return
  del.value.busy = true
  error.value = ''
  try {
    const d = await call(`/storage/object?key=${encodeURIComponent(del.value.key)}`,
                         { method: 'DELETE' })
    notice.value = d.message
    del.value.open = false
    await load()
    loadUsage()
  } catch (e) {
    error.value = e.message
  } finally {
    del.value.busy = false
  }
}

/** Download every file in a folder, one at a time so the browser keeps up. */
async function downloadMany(list) {
  bulk.value = { busy: true, at: 0, total: list.length, done: false }
  error.value = ''
  try {
    for (let i = 0; i < list.length; i++) {
      bulk.value.at = i + 1
      try {
        const d = await call(`/storage/download?key=${encodeURIComponent(list[i].key)}`)
        const a = document.createElement('a')
        a.href = d.url
        a.download = list[i].name
        document.body.appendChild(a)
        a.click()
        a.remove()
      } catch (e) {
        error.value = `${list[i].name}: ${e.message}`
      }
      await new Promise(r => setTimeout(r, 350))
    }
  } finally {
    bulk.value.busy = false
    bulk.value.done = true
  }
}

function downloadHere() {
  downloadMany(files.value)
}

async function downloadFolder(f) {
  error.value = ''
  try {
    const d = await call(`/storage/list?prefix=${encodeURIComponent(f.prefix)}`)
    const list = d.files || []
    if (!list.length) {
      error.value = `"${f.name}" has no files directly inside it.`
      return
    }
    downloadMany(list)
  } catch (e) {
    error.value = e.message
  }
}

function human(n) {
  if (n === 0) return '0 B'
  if (!n) return '—'
  const u = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.min(u.length - 1, Math.floor(Math.log(n) / Math.log(1024)))
  return `${(n / Math.pow(1024, i)).toFixed(i ? 1 : 0)} ${u[i]}`
}

function when(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return isNaN(d) ? '—' : d.toLocaleString('en-IN',
    { day: '2-digit', month: 'short', year: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function isAudio(name) {
  return /\.(wav|mp3|m4a|ogg|flac|aac|opus)$/i.test(name || '')
}

function icon(name) {
  if (isAudio(name)) return 'bi bi-file-earmark-music'
  if (/\.(png|jpe?g|gif|webp|svg)$/i.test(name)) return 'bi bi-file-earmark-image'
  if (/\.(csv|xlsx?|tsv)$/i.test(name)) return 'bi bi-file-earmark-spreadsheet'
  if (/\.(docx?|pdf|txt|md)$/i.test(name)) return 'bi bi-file-earmark-text'
  if (/\.(zip|tar|gz|7z)$/i.test(name)) return 'bi bi-file-earmark-zip'
  return 'bi bi-file-earmark'
}

onMounted(() => { load(''); loadUsage() })
</script>

<style scoped>
.fb-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,.45);
               display: flex; align-items: center; justify-content: center; z-index: 1080; }
.fb-dialog { background: #fff; border-radius: .75rem; padding: 1.25rem;
             width: 100%; max-width: 30rem; box-shadow: 0 1rem 3rem rgba(0,0,0,.3); }
.drop-hot { outline: 2px dashed #0d6efd; outline-offset: -4px; background: #f8fbff; }
.breadcrumb-item + .breadcrumb-item::before { content: "/"; }
</style>
