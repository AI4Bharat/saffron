<template>
  <div class="dashboard-container py-4">
    <!-- Header with Auto Refresh control -->
    <div class="d-flex flex-wrap justify-content-between align-items-center mb-4 pb-3 border-bottom border-secondary-subtle">
      <div>
        <h1 class="h2 fw-bold text-dark mb-1">Admin Dashboard</h1>
        <p class="text-muted mb-0">Monitor translations, languages, and rater registrations in real-time.</p>
      </div>
      <div class="d-flex align-items-center gap-3 mt-3 mt-md-0">
        <!-- Auto refresh indicator -->
        <div class="d-flex align-items-center gap-2 bg-light px-3 py-2 rounded border shadow-sm">
          <div :class="['status-dot', isAutoRefreshActive ? 'active animate-pulse' : '']"></div>
          <span class="text-xs fw-medium text-secondary">
            {{ isAutoRefreshActive ? `Auto-refreshing in ${countdown}s` : 'Auto-refresh paused' }}
          </span>
          <button @click="toggleAutoRefresh" class="btn btn-sm btn-outline-secondary ms-2" title="Toggle Auto-Refresh">
            <i :class="['bi', isAutoRefreshActive ? 'bi-pause-fill' : 'bi-play-fill']"></i>
          </button>
        </div>
        <button @click="fetchDashboardData(true)" class="btn btn-primary d-flex align-items-center gap-2 shadow-sm" :disabled="isLoading">
          <i :class="['bi', isLoading ? 'bi-arrow-clockwise animate-spin' : 'bi-arrow-clockwise']"></i>
          <span>Refresh</span>
        </button>
      </div>
    </div>

    <!-- Error Alert -->
    <div v-if="error" class="alert alert-danger alert-dismissible fade show shadow-sm" role="alert">
      <i class="bi bi-exclamation-triangle-fill me-2"></i>
      {{ error }}
      <button type="button" class="btn-close" @click="error = null"></button>
    </div>

    <!-- Navigation Tabs -->
    <div class="tabs-nav mb-4 bg-white p-2 rounded shadow-sm border d-flex gap-2">
      <button 
        v-for="tab in ['overview', 'batches', 'raters']" 
        :key="tab"
        @click="activeTab = tab"
        :class="['tab-btn btn flex-fill py-2 fw-semibold text-capitalize', activeTab === tab ? 'btn-dark text-white' : 'btn-light text-secondary']"
      >
        <i :class="['bi me-2', tab === 'overview' ? 'bi-grid-1x2-fill' : tab === 'batches' ? 'bi-folder-fill' : 'bi-people-fill']"></i>
        {{ tab }}
      </button>
    </div>

    <!-- Tab Contents -->
    <div v-if="!isLoading || dashboardData.stats" class="tab-content">
      <!-- 1. OVERVIEW TAB -->
      <div v-if="activeTab === 'overview'" class="tab-pane-active">
        <!-- KPI Cards Grid -->
        <div class="row g-4 mb-4">
          <div class="col-12 col-sm-6 col-xl-3">
            <div class="kpi-card bg-white p-4 rounded shadow-sm border border-start border-4 border-primary">
              <div class="d-flex justify-content-between align-items-center mb-2">
                <span class="text-muted fw-medium text-uppercase text-xs">Total Registered Raters</span>
                <div class="kpi-icon-wrapper bg-primary-subtle text-primary">
                  <i class="bi bi-people-fill fs-5"></i>
                </div>
              </div>
              <h2 class="fw-bold text-dark mb-1">{{ stats.total_registered_users || 0 }}</h2>
              <div class="text-xs text-muted d-flex align-items-center gap-1">
                <span class="text-success fw-bold">{{ stats.active_users || 0 }} Active</span>
                <span>•</span>
                <span class="text-warning fw-bold">{{ stats.pending_registrations || 0 }} 0 Tasks Completed</span>
              </div>
            </div>
          </div>
          
          <div class="col-12 col-sm-6 col-xl-3">
            <div class="kpi-card bg-white p-4 rounded shadow-sm border border-start border-4 border-warning">
              <div class="d-flex justify-content-between align-items-center mb-2">
                <span class="text-muted fw-medium text-uppercase text-xs">0 Tasks Completed</span>
                <div class="kpi-icon-wrapper bg-warning-subtle text-warning">
                  <i class="bi bi-person-fill-exclamation fs-5 animate-pulse-slow"></i>
                </div>
              </div>
              <h2 class="fw-bold text-dark mb-1">{{ stats.pending_registrations || 0 }}</h2>
              <p class="text-xs text-muted mb-0">Registered but completed 0 tasks.</p>
            </div>
          </div>

          <div class="col-12 col-sm-6 col-xl-3">
            <div class="kpi-card bg-white p-4 rounded shadow-sm border border-start border-4 border-success">
              <div class="d-flex justify-content-between align-items-center mb-2">
                <span class="text-muted fw-medium text-uppercase text-xs">Task Completions</span>
                <div class="kpi-icon-wrapper bg-success-subtle text-success">
                  <i class="bi bi-check-circle-fill fs-5"></i>
                </div>
              </div>
              <h2 class="fw-bold text-dark mb-1">{{ stats.unique_tasks_completed || 0 }} <span class="text-muted fs-6">/ {{ stats.total_tasks || 0 }}</span></h2>
              <div class="progress mt-2" style="height: 6px;">
                <div class="progress-bar bg-success" role="progressbar" :style="{ width: globalProgressPercent + '%' }" :aria-valuenow="globalProgressPercent" aria-valuemin="0" aria-valuemax="100"></div>
              </div>
              <p class="text-xs text-muted mt-2 mb-0">Coverage: {{ globalProgressPercent }}% of unique tasks</p>
            </div>
          </div>

          <div class="col-12 col-sm-6 col-xl-3">
            <div class="kpi-card bg-white p-4 rounded shadow-sm border border-start border-4 border-info">
              <div class="d-flex justify-content-between align-items-center mb-2">
                <span class="text-muted fw-medium text-uppercase text-xs">Total Submissions</span>
                <div class="kpi-icon-wrapper bg-info-subtle text-info">
                  <i class="bi bi-collection-fill fs-5"></i>
                </div>
              </div>
              <h2 class="fw-bold text-dark mb-1">{{ stats.total_submissions || 0 }}</h2>
              <p class="text-xs text-muted mb-0">Total ratings submitted by all users.</p>
            </div>
          </div>
        </div>

        <!-- Language Breakdown section -->
        <h3 class="fw-bold text-dark mb-3">Languages Statistics</h3>
        <div class="row g-4 mb-4">
          <div v-for="lang in languages" :key="lang.language" class="col-12 col-md-6 col-lg-4">
            <div class="lang-card bg-white p-4 rounded shadow-sm border hover-lift">
              <div class="d-flex justify-content-between align-items-center mb-3">
                <h4 class="fw-bold text-dark m-0">{{ lang.language }}</h4>
                <span class="badge bg-light text-dark border">{{ lang.test_count }} {{ lang.test_count === 1 ? 'Batch' : 'Batches' }}</span>
              </div>
              
              <!-- Completion rate -->
              <div class="mb-3">
                <div class="d-flex justify-content-between text-xs mb-1">
                  <span class="text-muted">Completed Coverage</span>
                  <span class="fw-bold text-dark">{{ getPercent(lang.unique_completed_tasks, lang.total_tasks) }}%</span>
                </div>
                <div class="progress bg-light-gradient" style="height: 10px; border-radius: 5px;">
                  <div 
                    class="progress-bar progress-gradient" 
                    role="progressbar" 
                    :style="{ width: getPercent(lang.unique_completed_tasks, lang.total_tasks) + '%' }"
                  ></div>
                </div>
              </div>
              
              <!-- Metrics list -->
              <div class="d-flex justify-content-between text-xs text-muted pt-2 border-top">
                <div>
                  <span class="d-block fw-bold text-dark">{{ lang.unique_completed_tasks }} / {{ lang.total_tasks }}</span>
                  <span>Unique Tasks</span>
                </div>
                <div class="text-end">
                  <span class="d-block fw-bold text-dark">{{ lang.total_submissions }}</span>
                  <span>Total Submissions</span>
                </div>
              </div>
            </div>
          </div>
          <div v-if="languages.length === 0" class="col-12 text-center text-muted py-5 bg-white rounded border">
            No languages stats found.
          </div>
        </div>

        <!-- Audio Segmentation Hours -->
        <div v-if="audioSegStats.length">
          <div class="d-flex flex-wrap justify-content-between align-items-center mb-3 gap-2">
            <h3 class="fw-bold text-dark m-0"><i class="bi bi-soundwave text-primary me-2"></i>Audio Segmentation Hours</h3>
            <span class="badge bg-light text-dark border py-2 px-3">
              Completed {{ formatDuration(audioSegFilteredTotals.completedSecs) }} of {{ formatDuration(audioSegFilteredTotals.totalSecs) }} total audio
            </span>
          </div>

          <!-- Filters + accept/reject totals for the audio tracker -->
          <div class="bg-white p-3 rounded shadow-sm border mb-4">
            <div class="row g-3 align-items-end">
              <div class="col-6 col-md-3">
                <label class="form-label text-xs fw-bold text-secondary mb-1">Language</label>
                <select v-model="audioLangFilter" class="form-select">
                  <option value="">All Languages</option>
                  <option v-for="l in audioLanguages" :key="l" :value="l">{{ l }}</option>
                </select>
              </div>
              <div class="col-6 col-md-3">
                <label class="form-label text-xs fw-bold text-secondary mb-1">Persona</label>
                <select v-model="audioPersonaFilter" class="form-select">
                  <option value="">All Personas</option>
                  <option v-for="p in audioPersonas" :key="p" :value="p">{{ p }}</option>
                </select>
              </div>
              <div class="col-12 col-md-6">
                <div class="d-flex flex-wrap gap-2 justify-content-md-end">
                  <div class="seg-stat-pill total">
                    <span class="lbl">Total Submissions</span>
                    <span class="val">{{ audioSegFilteredTotals.total }}</span>
                  </div>
                  <div class="seg-stat-pill accept">
                    <span class="lbl"><i class="bi bi-check-circle-fill me-1"></i>Accepted</span>
                    <span class="val">{{ audioSegFilteredTotals.accepted }}</span>
                  </div>
                  <div class="seg-stat-pill reject">
                    <span class="lbl"><i class="bi bi-x-circle-fill me-1"></i>Rejected</span>
                    <span class="val">{{ audioSegFilteredTotals.rejected }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="row g-4 mb-4">
            <div v-for="seg in filteredAudioSeg" :key="seg.test_id" class="col-12 col-lg-6">
              <div class="bg-white p-4 rounded shadow-sm border hover-lift h-100">
                <div class="d-flex justify-content-between align-items-start mb-2 gap-2">
                  <div>
                    <h4 class="fw-bold text-dark m-0 fs-6">#{{ seg.test_id }} — {{ seg.description }}</h4>
                    <div class="d-flex flex-wrap gap-1 mt-1">
                      <span class="badge rounded-pill bg-secondary-subtle text-secondary border">{{ seg.language || 'Unknown' }}</span>
                      <span class="badge rounded-pill bg-info-subtle text-info-emphasis border">{{ seg.persona || 'Unknown' }}</span>
                    </div>
                  </div>
                  <span class="badge bg-light text-dark border text-nowrap">{{ seg.total_tasks }} clips</span>
                </div>

                <!-- Accept / reject summary for this batch -->
                <div class="d-flex flex-wrap gap-2 mb-3">
                  <span class="badge bg-success-subtle text-success border py-2 px-2">
                    <i class="bi bi-check-circle-fill me-1"></i>{{ seg.accepted || 0 }} accepted
                  </span>
                  <span class="badge bg-danger-subtle text-danger border py-2 px-2">
                    <i class="bi bi-x-circle-fill me-1"></i>{{ seg.rejected || 0 }} rejected
                  </span>
                  <span class="badge bg-light text-secondary border py-2 px-2">
                    {{ seg.total_submissions || 0 }} submissions
                  </span>
                </div>

                <div class="d-flex justify-content-between text-xs mb-1">
                  <span class="text-muted">Audio completed</span>
                  <span class="fw-bold text-dark">
                    {{ formatDuration(seg.completed_audio_seconds) }} / {{ formatDuration(seg.total_audio_seconds) }}
                    ({{ getPercent(seg.completed_audio_seconds, seg.total_audio_seconds) }}%)
                  </span>
                </div>
                <div class="progress bg-light-gradient mb-3" style="height: 10px; border-radius: 5px;">
                  <div
                    class="progress-bar progress-gradient"
                    role="progressbar"
                    :style="{ width: getPercent(seg.completed_audio_seconds, seg.total_audio_seconds) + '%' }"
                  ></div>
                </div>
                <div class="table-responsive">
                  <table class="table table-sm table-hover align-middle mb-0">
                    <thead class="table-light">
                      <tr>
                        <th class="text-xs">Annotator</th>
                        <th class="text-xs text-end" style="width: 100px;">Tasks Done</th>
                        <th class="text-xs text-center" style="width: 120px;">Accept / Reject</th>
                        <th class="text-xs text-end" style="width: 130px;">Hours Completed</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="a in seg.annotators" :key="a.rater_id">
                        <td>
                          <div class="fw-semibold text-dark text-xs">{{ a.name }}</div>
                          <div class="text-muted" style="font-size: 0.7rem;">{{ a.email }}</div>
                        </td>
                        <td class="text-end text-xs">{{ a.completed_tasks }} / {{ seg.total_tasks }}</td>
                        <td class="text-center text-xs">
                          <span class="text-success fw-bold">{{ a.accepted || 0 }}</span>
                          <span class="text-muted mx-1">/</span>
                          <span class="text-danger fw-bold">{{ a.rejected || 0 }}</span>
                        </td>
                        <td class="text-end fw-bold text-xs">{{ formatDuration(a.completed_audio_seconds) }}</td>
                      </tr>
                      <tr v-if="seg.annotators.length === 0">
                        <td colspan="4" class="text-center text-muted text-xs py-2">No submissions yet.</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
            <div v-if="filteredAudioSeg.length === 0" class="col-12 text-center text-muted py-4 bg-white rounded border">
              No audio batches match the selected filters.
            </div>
          </div>
        </div>

        <!-- Needs Attention: actionable batch health (click a card to jump) -->
        <h3 class="fw-bold text-dark mb-3"><i class="bi bi-clipboard2-pulse-fill text-primary me-2"></i>Needs Attention</h3>
        <div class="row g-4 mb-4">
          <div class="col-12 col-md-4">
            <button type="button" class="attention-card w-100 text-start bg-white p-4 rounded shadow-sm border border-start border-4 border-danger" @click="focusBatches('unassigned')">
              <div class="d-flex justify-content-between align-items-center mb-2">
                <span class="text-muted fw-medium text-uppercase text-xs">Unassigned Batches</span>
                <div class="kpi-icon-wrapper bg-danger-subtle text-danger"><i class="bi bi-folder-x fs-5"></i></div>
              </div>
              <h2 class="fw-bold text-dark mb-1">{{ unassignedBatches.length }}</h2>
              <p class="text-xs text-muted mb-0"><i class="bi bi-arrow-right-short"></i> Not locked to any annotator — assign them.</p>
            </button>
          </div>
          <div class="col-12 col-md-4">
            <button type="button" class="attention-card w-100 text-start bg-white p-4 rounded shadow-sm border border-start border-4 border-warning" @click="focusBatches('stalled')">
              <div class="d-flex justify-content-between align-items-center mb-2">
                <span class="text-muted fw-medium text-uppercase text-xs">Stalled Batches</span>
                <div class="kpi-icon-wrapper bg-warning-subtle text-warning"><i class="bi bi-hourglass-bottom fs-5"></i></div>
              </div>
              <h2 class="fw-bold text-dark mb-1">{{ stalledBatches.length }}</h2>
              <p class="text-xs text-muted mb-0"><i class="bi bi-arrow-right-short"></i> No submissions yet (0% complete).</p>
            </button>
          </div>
          <div class="col-12 col-md-4">
            <button type="button" class="attention-card w-100 text-start bg-white p-4 rounded shadow-sm border border-start border-4 border-success" @click="focusBatches('almostdone')">
              <div class="d-flex justify-content-between align-items-center mb-2">
                <span class="text-muted fw-medium text-uppercase text-xs">Almost Done</span>
                <div class="kpi-icon-wrapper bg-success-subtle text-success"><i class="bi bi-flag-fill fs-5"></i></div>
              </div>
              <h2 class="fw-bold text-dark mb-1">{{ almostDoneBatches.length }}</h2>
              <p class="text-xs text-muted mb-0"><i class="bi bi-arrow-right-short"></i> &ge;80% done — a final push finishes them.</p>
            </button>
          </div>
        </div>
      </div>

      <!-- 2. TEST BATCHES TAB -->
      <div v-if="activeTab === 'batches'">
        <div class="card shadow-sm border mb-4">
          <div class="card-header bg-white py-3 border-bottom-0">
            <div class="d-flex flex-wrap justify-content-between align-items-center gap-3 mb-3 border-bottom pb-2">
              <h3 class="fw-bold text-dark m-0 d-inline-flex align-items-center flex-wrap gap-2">
                Test Batches Progress
                <span v-if="batchAttentionFilter" class="badge attention-chip rounded-pill">
                  {{ batchAttentionFilter === 'unassigned' ? 'Unassigned' : batchAttentionFilter === 'stalled' ? 'Stalled · 0%' : 'Almost done · ≥80%' }}
                  <i class="bi bi-x-lg ms-1" role="button" title="Clear filter" @click="batchAttentionFilter = ''"></i>
                </span>
              </h3>
            </div>
            <div class="row g-3 align-items-center">
              <div class="col-12 col-sm-6 col-md-2">
                <select v-model="batchLanguageFilter" class="form-select">
                  <option value="">All Languages</option>
                  <option v-for="lang in uniqueLanguages" :key="lang" :value="lang">{{ lang }}</option>
                </select>
              </div>
              <div class="col-12 col-sm-6 col-md-2">
                <select v-model="batchVersionFilter" class="form-select">
                  <option value="">All Versions</option>
                  <option v-for="version in uniqueVersions" :key="version" :value="version">{{ version }}</option>
                </select>
              </div>
              <div class="col-12 col-sm-6 col-md-2">
                <select v-model="batchTestTypeFilter" class="form-select">
                  <option value="">All Test Types</option>
                  <option v-for="type in uniqueTestTypes" :key="type" :value="type">{{ formatTestType(type) }}</option>
                </select>
              </div>
              <div class="col-12 col-sm-6 col-md-3">
                <input 
                  v-model="batchSearchQuery" 
                  type="text" 
                  class="form-control" 
                  placeholder="Search batches..." 
                />
              </div>
              <div class="col-12 col-sm-6 col-md-3">
                <div class="input-group">
                  <input 
                    type="number" 
                    class="form-control" 
                    placeholder="Export ID..." 
                    v-model.number="exportTaskId"
                    @keyup.enter="exportCSV(exportTaskId)"
                  />
                  <button class="btn btn-success" @click="exportCSV(exportTaskId)" :disabled="!exportTaskId">
                    <i class="bi bi-download"></i> Export
                  </button>
                </div>
              </div>
            </div>
          </div>
          
          <div class="table-responsive">
            <table class="table table-hover align-middle mb-0">
              <thead class="table-light">
                <tr>
                  <th class="ps-4 sortable-th" style="width: 80px;" @click="sortBatches('id')">ID <i :class="['bi', sortIcon(batchSort, 'id')]"></i></th>
                  <th class="sortable-th" @click="sortBatches('description')">Description <i :class="['bi', sortIcon(batchSort, 'description')]"></i></th>
                  <th class="sortable-th" style="width: 150px;" @click="sortBatches('language')">Language <i :class="['bi', sortIcon(batchSort, 'language')]"></i></th>
                  <th style="width: 150px;">Test Type</th>
                  <th class="sortable-th" style="width: 250px;" @click="sortBatches('completion')">Unique Completed / Total <i :class="['bi', sortIcon(batchSort, 'completion')]"></i></th>
                  <th class="sortable-th" style="width: 140px;" @click="sortBatches('submissions')">Total Submissions <i :class="['bi', sortIcon(batchSort, 'submissions')]"></i></th>
                  <th style="width: 120px;">Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="test in pagedTests" :key="test.id" class="batch-row" @click="openTask(test.id)" title="Click to open this task">
                  <td class="ps-4 fw-bold text-secondary">#{{ test.id }}</td>
                  <td>
                    <div class="fw-semibold text-dark">{{ test.description }}</div>
                    <div class="mt-1">
                      <span class="badge bg-secondary-subtle text-secondary-emphasis text-xs border rounded-pill">
                        {{ test.version || getVersionFromDescription(test.description) }}
                      </span>
                    </div>
                  </td>
                  <td>
                    <span class="badge rounded-pill bg-light text-dark border">{{ test.language }}</span>
                  </td>
                  <td>
                    <span class="text-secondary text-xs text-capitalize">{{ formatTestType(test.test_type) }}</span>
                  </td>
                  <td>
                    <div class="d-flex align-items-center gap-2">
                      <div class="progress flex-grow-1" style="height: 8px;">
                        <div 
                          class="progress-bar bg-success" 
                          role="progressbar" 
                          :style="{ width: getPercent(test.unique_completed_tasks, test.total_tasks) + '%' }"
                        ></div>
                      </div>
                      <span class="text-xs fw-bold text-secondary" style="width: 80px; text-align: right;">
                        {{ test.unique_completed_tasks }}/{{ test.total_tasks }} ({{ getPercent(test.unique_completed_tasks, test.total_tasks) }}%)
                      </span>
                    </div>
                  </td>
                  <td>
                    <span class="fw-semibold text-dark">{{ test.total_submissions }}</span>
                  </td>
                  <td @click.stop>
                    <div class="btn-group btn-group-sm" role="group">
                      <button type="button" class="btn btn-outline-secondary"
                              title="Copy task link" @click="copyTaskLink(test.id)">
                        <i class="bi bi-clipboard"></i>
                      </button>
                      <button type="button" class="btn btn-outline-success"
                              title="Export annotations to CSV" @click="exportCSV(test.id)">
                        <i class="bi bi-download"></i>
                      </button>
                    </div>
                  </td>
                </tr>
                <tr v-if="filteredTests.length === 0">
                  <td colspan="7" class="text-center text-muted py-5 bg-white">
                    No matching test batches found.
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Pager: keeps the batch list scannable instead of one endless table -->
          <div v-if="filteredTests.length" class="d-flex flex-wrap align-items-center justify-content-between gap-2 px-3 py-3 border-top bg-white">
            <small class="text-muted">
              Showing <strong>{{ batchRangeStart }}–{{ batchRangeEnd }}</strong> of <strong>{{ filteredTests.length }}</strong> batches
            </small>
            <div class="d-flex align-items-center gap-2">
              <select v-model.number="batchPageSize" class="form-select form-select-sm" style="width: auto;" title="Rows per page">
                <option :value="12">12 / page</option>
                <option :value="25">25 / page</option>
                <option :value="50">50 / page</option>
                <option :value="9999">Show all</option>
              </select>
              <div class="btn-group btn-group-sm">
                <button class="btn btn-outline-secondary" :disabled="batchPage <= 1" @click="batchPage--"><i class="bi bi-chevron-left"></i></button>
                <span class="btn btn-outline-secondary disabled fw-semibold">{{ batchPage }} / {{ batchPageCount }}</span>
                <button class="btn btn-outline-secondary" :disabled="batchPage >= batchPageCount" @click="batchPage++"><i class="bi bi-chevron-right"></i></button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 3. RATERS DIRECTORY TAB -->
      <div v-if="activeTab === 'raters'">
        <!-- Stale-annotator alert -->
        <div v-if="staleRaters.length" class="alert stale-alert d-flex align-items-center gap-2 shadow-sm mb-3" role="alert">
          <i class="bi bi-exclamation-triangle-fill fs-5"></i>
          <div class="flex-grow-1">
            <strong>{{ staleRaters.length }}</strong>
            annotator{{ staleRaters.length > 1 ? 's have' : ' has' }} tasks assigned but no activity in {{ STALE_DAYS }}+ days.
          </div>
          <button class="btn btn-sm btn-warning flex-shrink-0 fw-semibold" @click="remindAllStale" :disabled="isBulkNudging" title="Send a reminder message to every stale annotator">
            <span v-if="isBulkNudging" class="spinner-border spinner-border-sm me-1"></span>
            <i v-else class="bi bi-bell-fill me-1"></i>
            Remind all
          </button>
          <button class="btn btn-sm btn-outline-dark flex-shrink-0" @click="showStaleOnly = !showStaleOnly">
            <i :class="['bi me-1', showStaleOnly ? 'bi-list-ul' : 'bi-funnel-fill']"></i>
            {{ showStaleOnly ? 'Show all' : 'Show only these' }}
          </button>
        </div>
        <div class="card shadow-sm border">
          <div class="card-header bg-white py-3 border-bottom-0">
            <div class="row g-3 align-items-center">
              <div class="col-12 col-md-6">
                <h3 class="fw-bold text-dark m-0">Annotators &amp; Task Assignment</h3>
                <small class="text-muted">Assign task batches to an annotator — assigned tasks get <strong>locked</strong> to them only.</small>
              </div>
              <div class="col-12 col-md-6">
                <div class="d-flex flex-wrap gap-2 justify-content-md-end align-items-center">
                  <button class="btn btn-outline-primary btn-sm d-inline-flex align-items-center gap-1" @click="openBroadcastModal" title="Send a message to every annotator">
                    <i class="bi bi-broadcast"></i> Broadcast
                  </button>
                  <button class="btn btn-outline-secondary btn-sm d-inline-flex align-items-center gap-1" @click="openOutbox" title="View and edit messages you've sent">
                    <i class="bi bi-clock-history"></i> Sent
                  </button>
                  <div class="form-check form-switch mb-0 me-1">
                    <input class="form-check-input" type="checkbox" role="switch" id="showAllRaters" v-model="showAllRaters" />
                    <label class="form-check-label text-xs text-secondary user-select-none" for="showAllRaters">Show all</label>
                  </div>
                  <input
                    v-model="raterSearchQuery"
                    type="text"
                    class="form-control"
                    style="max-width: 280px;"
                    placeholder="Search by name or email..."
                  />
                </div>
              </div>
            </div>
          </div>
          
          <div class="table-responsive">
            <table class="table table-hover align-middle mb-0">
              <thead class="table-light">
                <tr>
                  <th class="ps-4 sortable-th" @click="sortRaters('name')">Name <i :class="['bi', sortIcon(raterSort, 'name')]"></i></th>
                  <th class="sortable-th" @click="sortRaters('email')">Email <i :class="['bi', sortIcon(raterSort, 'email')]"></i></th>
                  <th style="width: 100px;">Demographics</th>
                  <th class="sortable-th" style="width: 110px;" @click="sortRaters('completed')">Completed <i :class="['bi', sortIcon(raterSort, 'completed')]"></i></th>
                  <th class="sortable-th" style="width: 230px;" @click="sortRaters('assigned')">Assigned Tasks <i :class="['bi', sortIcon(raterSort, 'assigned')]"></i></th>
                  <th class="sortable-th" style="width: 160px;" @click="sortRaters('lastactive')">Last Active <i :class="['bi', sortIcon(raterSort, 'lastactive')]"></i></th>
                  <th style="width: 140px;">Status</th>
                  <th class="text-end pe-4" style="width: 180px;">Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="rater in filteredRaters" :key="rater.id" :class="{ 'stale-row': isStale(rater) }">
                  <td class="ps-4">
                    <div class="d-flex align-items-center gap-2">
                      <div class="avatar-circle">{{ rater.name.charAt(0).toUpperCase() }}</div>
                      <div class="fw-semibold text-dark">{{ rater.name }}</div>
                    </div>
                  </td>
                  <td>
                    <span class="text-secondary">{{ rater.email }}</span>
                  </td>
                  <td>
                    <div class="text-xs">
                      <span class="text-dark">{{ rater.gender }}</span>, <span class="text-muted">{{ rater.age }} yrs</span>
                    </div>
                  </td>
                  <td>
                    <span class="badge bg-light text-dark border fs-6 px-3">{{ rater.completed_tasks_count }}</span>
                  </td>
                  <td>
                    <div v-if="assignedIdList(rater).length" class="d-flex flex-wrap gap-1 assigned-chip-wrap">
                      <span v-for="tid in assignedIdList(rater).slice(0, 6)" :key="tid"
                            class="badge rounded-pill bg-primary-subtle text-primary border border-primary-subtle">#{{ tid }}</span>
                      <span v-if="assignedIdList(rater).length > 6"
                            class="badge rounded-pill bg-secondary-subtle text-secondary border">+{{ assignedIdList(rater).length - 6 }}</span>
                    </div>
                    <span v-else class="text-muted text-xs fst-italic">Unassigned</span>
                  </td>
                  <td>
                    <span v-if="rater.last_active" class="text-secondary text-xs">{{ formatDate(rater.last_active) }}</span>
                    <span v-else class="text-muted text-xs">—</span>
                    <span v-if="isStale(rater)" class="badge stale-badge rounded-pill ms-1" title="Assigned tasks but inactive">
                      <i class="bi bi-exclamation-triangle-fill me-1"></i>Stale
                    </span>
                  </td>
                  <td>
                    <span
                      v-if="rater.account_active === false"
                      class="badge px-3 py-2 text-xs rounded-pill d-inline-flex align-items-center gap-1 bg-danger-subtle text-danger"
                      title="This annotator is deactivated and cannot log in"
                    >
                      <i class="bi bi-slash-circle-fill"></i> Deactivated
                    </span>
                    <span
                      v-else
                      :class="['badge px-3 py-2 text-xs rounded-pill d-inline-flex align-items-center gap-1',
                        rater.completed_tasks_count >= 1 ? 'bg-success-subtle text-success' : 'bg-warning-subtle text-warning animate-pulse-border']"
                    >
                      <i :class="['bi', rater.completed_tasks_count >= 1 ? 'bi-check-circle-fill' : 'bi-exclamation-triangle-fill']"></i>
                      {{ rater.status }}
                    </span>
                  </td>
                  <td class="text-end pe-4">
                    <div class="d-inline-flex gap-1 justify-content-end rater-actions">
                      <!-- Assign / Edit (primary action) -->
                      <button
                        class="rater-action-btn"
                        :class="assignedIdList(rater).length ? 'btn btn-sm btn-primary' : 'btn btn-sm btn-outline-primary'"
                        @click="openAssignModal(rater)"
                        :title="assignedIdList(rater).length ? 'Edit assigned tasks' : 'Assign tasks'"
                      >
                        <i :class="['bi', assignedIdList(rater).length ? 'bi-pencil-square' : 'bi-plus-lg']"></i>
                      </button>
                      <!-- Message -->
                      <button
                        class="rater-action-btn btn btn-sm btn-outline-secondary position-relative"
                        @click="openMessageModal(rater)"
                        title="Send a message to this annotator"
                      >
                        <i class="bi bi-chat-dots"></i>
                        <span v-if="rater.messages_sent" class="rater-msg-badge">{{ rater.messages_sent }}</span>
                      </button>
                      <!-- Nudge (only for stale annotators) -->
                      <button
                        v-if="isStale(rater)"
                        class="rater-action-btn btn btn-sm btn-outline-warning"
                        @click="nudgeRater(rater)"
                        title="Send a task reminder to this stale annotator"
                      >
                        <i class="bi bi-bell"></i>
                      </button>
                      <!-- Export -->
                      <button
                        class="rater-action-btn btn btn-sm btn-outline-success"
                        @click="openExportModal(rater)"
                        title="Export annotator annotations to CSV"
                        :disabled="!assignedIdList(rater).length"
                      >
                        <i class="bi bi-download"></i>
                      </button>
                      <!-- Remove (deactivate) or Reactivate -->
                      <button
                        v-if="rater.account_active === false"
                        class="rater-action-btn btn btn-sm btn-success"
                        @click="reactivateRater(rater)"
                        title="Reactivate this annotator (restores their previous task locks)"
                      >
                        <i class="bi bi-arrow-counterclockwise"></i>
                      </button>
                      <button
                        v-else
                        class="rater-action-btn btn btn-sm btn-outline-danger"
                        @click="openRemoveModal(rater)"
                        title="Remove (deactivate) this annotator"
                      >
                        <i class="bi bi-person-dash"></i>
                      </button>
                    </div>
                  </td>
                </tr>
                <tr v-if="filteredRaters.length === 0">
                  <td colspan="8" class="text-center text-muted py-5 bg-white">
                    No matching raters found.
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
    
    <!-- Skeleton loader -->
    <div v-else class="text-center py-5">
      <div class="spinner-border text-primary" role="status" style="width: 3rem; height: 3rem;">
        <span class="visually-hidden">Loading...</span>
      </div>
      <p class="text-muted mt-3">Fetching initial statistics, please wait...</p>
    </div>

    <!-- ===================== ASSIGN TASKS MODAL ===================== -->
    <transition name="modal-fade">
      <div v-if="showAssignModal" class="assign-modal-backdrop" @click.self="closeAssignModal">
        <div class="assign-modal-card shadow-lg">
          <!-- Header -->
          <div class="assign-modal-header d-flex justify-content-between align-items-center">
            <div class="d-flex align-items-center gap-3">
              <div class="avatar-circle-lg">{{ (currentRater && currentRater.name ? currentRater.name : '?').charAt(0).toUpperCase() }}</div>
              <div>
                <h5 class="fw-bold mb-0 text-dark">Assign Tasks</h5>
                <small class="text-muted">{{ currentRater && currentRater.name }} · {{ currentRater && currentRater.email }}</small>
              </div>
            </div>
            <button class="btn-close" @click="closeAssignModal"></button>
          </div>

          <!-- Body -->
          <div class="assign-modal-body">
            <!-- Lock notice -->
            <div class="d-flex align-items-start gap-2 py-2 px-3 rounded-3 bg-info-subtle mb-3">
              <i class="bi bi-lock-fill text-info mt-1"></i>
              <small class="text-info-emphasis">Selected tasks are <strong>locked to this annotator</strong>. No one else will be able to open them. Removing a task unlocks it again.</small>
            </div>

            <!-- Selected summary -->
            <div class="d-flex justify-content-between align-items-center mb-2">
              <span class="fw-semibold text-dark">
                Selected <span class="badge bg-primary rounded-pill ms-1">{{ assignSelected.length }}</span>
              </span>
              <button v-if="assignSelected.length" class="btn btn-sm btn-link text-danger p-0 text-decoration-none" @click="assignSelected = []">
                <i class="bi bi-x-circle me-1"></i>Clear all
              </button>
            </div>
            <div class="selected-chips mb-3" v-if="assignSelected.length">
              <span v-for="tid in assignSelected" :key="tid" class="chip">
                #{{ tid }}
                <i class="bi bi-x-lg" role="button" title="Remove" @click="toggleTask(tid)"></i>
              </span>
            </div>

            <!-- Search batches -->
            <div class="input-group mb-2">
              <span class="input-group-text bg-white border-end-0"><i class="bi bi-search text-muted"></i></span>
              <input v-model="assignSearch" type="text" class="form-control border-start-0 ps-0" placeholder="Search batches by ID, description, language or test type..." />
            </div>

            <!-- Batch list -->
            <div class="batch-picker border rounded-3">
              <label
                v-for="t in assignableTests"
                :key="t.id"
                :class="['batch-row d-flex align-items-center gap-3 px-3 py-2', assignSelected.includes(t.id) ? 'selected' : '']"
              >
                <input type="checkbox" class="form-check-input mt-0 flex-shrink-0" :checked="assignSelected.includes(t.id)" @change="toggleTask(t.id)" />
                <span class="badge bg-light text-dark border flex-shrink-0 text-center" style="min-width: 52px;">#{{ t.id }}</span>
                <span class="flex-grow-1 text-truncate text-dark small">{{ t.description }}</span>
                <span v-if="taskOwnerMap[t.id]"
                      class="badge rounded-pill bg-warning-subtle text-warning-emphasis flex-shrink-0 d-inline-flex align-items-center gap-1"
                      :title="`Already locked to ${taskOwnerMap[t.id]}`">
                  <i class="bi bi-lock-fill"></i>{{ taskOwnerMap[t.id] }}
                </span>
                <span class="badge rounded-pill bg-secondary-subtle text-secondary flex-shrink-0">{{ t.language }}</span>
              </label>
              <div v-if="assignableTests.length === 0" class="text-center text-muted py-4 small">
                <i class="bi bi-inbox d-block fs-4 mb-1 opacity-50"></i>
                No batches match your search.
              </div>
            </div>
          </div>

          <!-- Footer -->
          <div class="assign-modal-footer d-flex justify-content-between align-items-center gap-3">
            <small v-if="assignError" class="text-danger"><i class="bi bi-exclamation-circle me-1"></i>{{ assignError }}</small>
            <small v-else class="text-muted">
              {{ assignSelected.length }} task(s) will be locked to <strong>{{ currentRater && currentRater.name }}</strong>
            </small>
            <div class="d-flex gap-2 flex-shrink-0">
              <button class="btn btn-light border" @click="closeAssignModal" :disabled="isSaving">Cancel</button>
              <button class="btn btn-primary d-inline-flex align-items-center gap-2" @click="saveAssignments" :disabled="isSaving">
                <span v-if="isSaving" class="spinner-border spinner-border-sm"></span>
                <i v-else class="bi bi-check2-circle"></i>
                <span>{{ isSaving ? 'Saving…' : 'Save Assignment' }}</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </transition>

    <!-- ===================== EXPORT TASK MODAL ===================== -->
    <transition name="modal-fade">
      <div v-if="showExportModal" class="assign-modal-backdrop" @click.self="closeExportModal">
        <div class="assign-modal-card shadow-lg" style="max-width: 480px;">
          <!-- Header -->
          <div class="assign-modal-header d-flex justify-content-between align-items-center">
            <div class="d-flex align-items-center gap-2">
              <i class="bi bi-download text-success fs-4"></i>
              <h5 class="fw-bold mb-0 text-dark">Export Annotations</h5>
            </div>
            <button class="btn-close" @click="closeExportModal"></button>
          </div>

          <!-- Body -->
          <div class="assign-modal-body">
            <p class="text-xs text-muted mb-3">
              Export annotations done by <strong>{{ currentRaterForExport?.name }}</strong> as a CSV spreadsheet.
            </p>
            <div class="form-group mb-2">
              <label class="form-label text-xs fw-bold text-secondary">Choose Assigned Task ID</label>
              <select v-model="selectedExportTaskId" class="form-select">
                <option value="" disabled>-- Select a Task ID --</option>
                <option v-for="tid in exportableTaskIds" :key="tid" :value="tid">
                  Task #{{ tid }} - {{ getTaskDescription(tid) }}
                </option>
              </select>
            </div>
            <div v-if="exportableTaskIds.length === 0" class="text-danger small mt-2">
              <i class="bi bi-exclamation-circle-fill me-1"></i> This annotator has no assigned tasks.
            </div>
          </div>

          <!-- Footer -->
          <div class="assign-modal-footer d-flex justify-content-end gap-2">
            <button class="btn btn-light border btn-sm" @click="closeExportModal">Cancel</button>
            <button class="btn btn-success btn-sm d-inline-flex align-items-center gap-1.5" 
                    :disabled="!selectedExportTaskId" 
                    @click="confirmExport">
              <i class="bi bi-download"></i>
              <span>Export CSV</span>
            </button>
          </div>
        </div>
      </div>
    </transition>

    <!-- ===================== MESSAGE MODAL ===================== -->
    <transition name="modal-fade">
      <div v-if="showMessageModal" class="assign-modal-backdrop" @click.self="closeMessageModal">
        <div class="assign-modal-card shadow-lg" style="max-width: 520px;">
          <div class="assign-modal-header d-flex justify-content-between align-items-center">
            <div class="d-flex align-items-center gap-3">
              <div class="avatar-circle-lg">{{ (messageTarget && messageTarget.name ? messageTarget.name : '?').charAt(0).toUpperCase() }}</div>
              <div>
                <h5 class="fw-bold mb-0 text-dark">Message annotator</h5>
                <small class="text-muted">{{ messageTarget && messageTarget.name }} · {{ messageTarget && messageTarget.email }}</small>
              </div>
            </div>
            <button class="btn-close" @click="closeMessageModal"></button>
          </div>
          <div class="assign-modal-body">
            <div class="d-flex align-items-start gap-2 py-2 px-3 rounded-3 bg-info-subtle mb-3">
              <i class="bi bi-info-circle-fill text-info mt-1"></i>
              <small class="text-info-emphasis">The annotator sees this in their in-app inbox the next time they open the studio.</small>
            </div>
            <label class="form-label fw-semibold text-dark small">Message</label>
            <textarea v-model="messageBody" class="form-control" rows="4" maxlength="2000" placeholder="Write your message…"></textarea>
            <div class="text-end text-muted fs-9 mt-1">{{ messageBody.length }}/2000</div>
            <div v-if="messageError" class="text-danger small mt-1"><i class="bi bi-exclamation-triangle-fill me-1"></i>{{ messageError }}</div>
          </div>
          <div class="assign-modal-footer d-flex justify-content-end gap-2">
            <button class="btn btn-light border btn-sm" @click="closeMessageModal" :disabled="isSendingMsg">Cancel</button>
            <button class="btn btn-primary btn-sm d-inline-flex align-items-center gap-1.5" :disabled="isSendingMsg || !messageBody.trim()" @click="sendMessage">
              <span v-if="isSendingMsg" class="spinner-border spinner-border-sm"></span>
              <i v-else class="bi bi-send-fill"></i>
              <span>Send message</span>
            </button>
          </div>
        </div>
      </div>
    </transition>

    <!-- ===================== BROADCAST MODAL ===================== -->
    <transition name="modal-fade">
      <div v-if="showBroadcastModal" class="assign-modal-backdrop" @click.self="closeBroadcastModal">
        <div class="assign-modal-card shadow-lg" style="max-width: 520px;">
          <div class="assign-modal-header d-flex justify-content-between align-items-center">
            <div class="d-flex align-items-center gap-3">
              <div class="avatar-circle-lg bg-primary-subtle text-primary"><i class="bi bi-broadcast"></i></div>
              <div>
                <h5 class="fw-bold mb-0 text-dark">Broadcast to all annotators</h5>
                <small class="text-muted">Sends the same message to every registered annotator.</small>
              </div>
            </div>
            <button class="btn-close" @click="closeBroadcastModal"></button>
          </div>
          <div class="assign-modal-body">
            <label class="form-label fw-semibold text-dark small">Message</label>
            <textarea v-model="broadcastBody" class="form-control" rows="4" maxlength="2000" placeholder="Announcement for everyone…"></textarea>
            <div class="text-end text-muted fs-9 mt-1">{{ broadcastBody.length }}/2000</div>
            <div v-if="broadcastError" class="text-danger small mt-1"><i class="bi bi-exclamation-triangle-fill me-1"></i>{{ broadcastError }}</div>
          </div>
          <div class="assign-modal-footer d-flex justify-content-end gap-2">
            <button class="btn btn-light border btn-sm" @click="closeBroadcastModal" :disabled="isBroadcasting">Cancel</button>
            <button class="btn btn-primary btn-sm d-inline-flex align-items-center gap-1.5" :disabled="isBroadcasting || !broadcastBody.trim()" @click="sendBroadcast">
              <span v-if="isBroadcasting" class="spinner-border spinner-border-sm"></span>
              <i v-else class="bi bi-broadcast"></i>
              <span>Broadcast</span>
            </button>
          </div>
        </div>
      </div>
    </transition>

    <!-- ===================== SENT MESSAGES (OUTBOX) MODAL ===================== -->
    <transition name="modal-fade">
      <div v-if="showOutboxModal" class="assign-modal-backdrop" @click.self="closeOutbox">
        <div class="assign-modal-card shadow-lg" style="max-width: 680px;">
          <div class="assign-modal-header d-flex justify-content-between align-items-center">
            <div class="d-flex align-items-center gap-3">
              <div class="avatar-circle-lg bg-secondary-subtle text-secondary"><i class="bi bi-clock-history"></i></div>
              <div>
                <h5 class="fw-bold mb-0 text-dark">Sent messages</h5>
                <small class="text-muted">Messages and broadcasts you've shared with annotators.</small>
              </div>
            </div>
            <button class="btn-close" @click="closeOutbox"></button>
          </div>
          <div class="assign-modal-body" style="max-height: 60vh; overflow-y: auto;">
            <div v-if="outboxLoading" class="text-center text-muted py-4">
              <span class="spinner-border spinner-border-sm me-2"></span> Loading…
            </div>
            <div v-else-if="outboxError" class="text-danger small py-2">
              <i class="bi bi-exclamation-triangle-fill me-1"></i>{{ outboxError }}
            </div>
            <div v-else-if="!outboxItems.length" class="text-center text-muted py-4">
              <i class="bi bi-inbox fs-3 d-block mb-2"></i> You haven't sent any messages yet.
            </div>
            <div v-else class="d-flex flex-column gap-2">
              <div
                v-for="item in outboxItems"
                :key="item.kind === 'broadcast' ? 'b-' + item.broadcast_id : 'm-' + item.id"
                class="border rounded-3 p-3"
              >
                <div class="d-flex justify-content-between align-items-start gap-2">
                  <div class="d-flex align-items-center gap-2 flex-wrap">
                    <span v-if="item.kind === 'broadcast'" class="badge rounded-pill bg-primary-subtle text-primary">
                      <i class="bi bi-broadcast me-1"></i>Broadcast
                    </span>
                    <span v-else-if="item.category === 'nudge'" class="badge rounded-pill bg-warning-subtle text-warning-emphasis">
                      <i class="bi bi-bell me-1"></i>Nudge
                    </span>
                    <span v-else class="badge rounded-pill bg-secondary-subtle text-secondary">
                      <i class="bi bi-chat-dots me-1"></i>Message
                    </span>
                    <span class="fw-semibold text-dark small">
                      {{ item.kind === 'broadcast' ? 'All annotators' : item.rater_name }}
                    </span>
                    <span v-if="item.kind === 'broadcast'" class="text-muted fs-9">
                      · {{ item.recipients_read }}/{{ item.recipients_total }} read
                    </span>
                    <span v-else class="fs-9" :class="item.is_read ? 'text-success' : 'text-muted'">
                      · {{ item.is_read ? 'Read' : 'Unread' }}
                    </span>
                  </div>
                  <button class="btn btn-sm btn-outline-primary flex-shrink-0" @click="openEditMsg(item)" title="Edit this message">
                    <i class="bi bi-pencil"></i>
                  </button>
                </div>
                <div class="text-body small mt-2" style="white-space: pre-wrap; word-break: break-word;">{{ item.body }}</div>
                <div class="text-muted fs-9 mt-1">
                  {{ formatDate(item.created_at) }}
                  <span v-if="item.edited_at"> · edited {{ formatDate(item.edited_at) }}</span>
                </div>
              </div>
            </div>
          </div>
          <div class="assign-modal-footer d-flex justify-content-end gap-2">
            <button class="btn btn-light border btn-sm" @click="closeOutbox">Close</button>
          </div>
        </div>
      </div>
    </transition>

    <!-- ===================== EDIT SENT MESSAGE MODAL ===================== -->
    <transition name="modal-fade">
      <div v-if="showEditMsgModal" class="assign-modal-backdrop" @click.self="closeEditMsg">
        <div class="assign-modal-card shadow-lg" style="max-width: 520px;">
          <div class="assign-modal-header d-flex justify-content-between align-items-center">
            <div class="d-flex align-items-center gap-3">
              <div class="avatar-circle-lg bg-primary-subtle text-primary"><i class="bi bi-pencil-square"></i></div>
              <div>
                <h5 class="fw-bold mb-0 text-dark">Edit {{ editTarget && editTarget.kind === 'broadcast' ? 'broadcast' : 'message' }}</h5>
                <small class="text-muted">
                  {{ editTarget && editTarget.kind === 'broadcast'
                      ? 'Updates the copy every annotator sees.'
                      : (editTarget ? editTarget.rater_name : '') }}
                </small>
              </div>
            </div>
            <button class="btn-close" @click="closeEditMsg"></button>
          </div>
          <div class="assign-modal-body">
            <label class="form-label fw-semibold text-dark small">Message</label>
            <textarea v-model="editBody" class="form-control" rows="4" maxlength="2000" placeholder="Update your message…"></textarea>
            <div class="text-end text-muted fs-9 mt-1">{{ editBody.length }}/2000</div>
            <div v-if="editError" class="text-danger small mt-1"><i class="bi bi-exclamation-triangle-fill me-1"></i>{{ editError }}</div>
          </div>
          <div class="assign-modal-footer d-flex justify-content-end gap-2">
            <button class="btn btn-light border btn-sm" @click="closeEditMsg" :disabled="isSavingEdit">Cancel</button>
            <button class="btn btn-primary btn-sm d-inline-flex align-items-center gap-1.5" :disabled="isSavingEdit || !editBody.trim()" @click="saveEditMsg">
              <span v-if="isSavingEdit" class="spinner-border spinner-border-sm"></span>
              <i v-else class="bi bi-check-lg"></i>
              <span>Save changes</span>
            </button>
          </div>
        </div>
      </div>
    </transition>

    <!-- ===================== REMOVE (DEACTIVATE) MODAL ===================== -->
    <transition name="modal-fade">
      <div v-if="showRemoveModal" class="assign-modal-backdrop" @click.self="closeRemoveModal">
        <div class="assign-modal-card shadow-lg" style="max-width: 520px;">
          <div class="assign-modal-header d-flex justify-content-between align-items-center">
            <div class="d-flex align-items-center gap-3">
              <div class="avatar-circle-lg bg-danger-subtle text-danger"><i class="bi bi-person-dash-fill"></i></div>
              <div>
                <h5 class="fw-bold mb-0 text-dark">Remove annotator</h5>
                <small class="text-muted">{{ removeTarget && removeTarget.name }} · {{ removeTarget && removeTarget.email }}</small>
              </div>
            </div>
            <button class="btn-close" @click="closeRemoveModal"></button>
          </div>
          <div class="assign-modal-body">
            <div class="d-flex align-items-start gap-2 py-2 px-3 rounded-3 bg-warning-subtle mb-3">
              <i class="bi bi-shield-check text-warning-emphasis mt-1"></i>
              <small class="text-dark">
                This <strong>deactivates</strong> the account (they can no longer log in) and
                <strong>unlocks their {{ removeTarget ? assignedIdList(removeTarget).length : 0 }} assigned task(s)</strong> so others can pick them up.
                Their submitted annotations are <strong>kept</strong>, and this is <strong>reversible</strong> — you can Reactivate them later.
              </small>
            </div>
            <label class="form-label fw-semibold text-dark small">
              Type <code class="text-danger">delete {{ removeTarget && removeTarget.name }}</code> to confirm
            </label>
            <input
              v-model="removeConfirmText"
              type="text"
              class="form-control"
              :class="{ 'is-invalid': removeConfirmText && !removeConfirmMatches }"
              :placeholder="`delete ${removeTarget ? removeTarget.name : ''}`"
              @keyup.enter="removeConfirmMatches && confirmRemove()"
              autocomplete="off"
            />
            <div v-if="removeError" class="text-danger small mt-2"><i class="bi bi-exclamation-triangle-fill me-1"></i>{{ removeError }}</div>
          </div>
          <div class="assign-modal-footer d-flex justify-content-end gap-2">
            <button class="btn btn-light border btn-sm" @click="closeRemoveModal" :disabled="isRemoving">Cancel</button>
            <button class="btn btn-danger btn-sm d-inline-flex align-items-center gap-1.5" :disabled="isRemoving || !removeConfirmMatches" @click="confirmRemove">
              <span v-if="isRemoving" class="spinner-border spinner-border-sm"></span>
              <i v-else class="bi bi-person-dash-fill"></i>
              <span>Deactivate annotator</span>
            </button>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { API_BASE_URL } from '@/config'
import router from '@/router'

// State
const activeTab = ref('overview')
const dashboardData = ref({})
const isLoading = ref(true)
const error = ref(null)

// Filters & Search
const batchSearchQuery = ref('')
const batchLanguageFilter = ref('')
const batchVersionFilter = ref('')
const batchTestTypeFilter = ref('')
const raterSearchQuery = ref('')
const raterStatusFilter = ref('')
const showAllRaters = ref(true)

// Sorting + Needs-Attention + stale-annotator state
const batchSort = ref({ key: 'id', dir: 'asc' })
const raterSort = ref({ key: 'default', dir: 'asc' })
const batchAttentionFilter = ref('')   // '' | 'unassigned' | 'stalled' | 'almostdone'
const showStaleOnly = ref(false)
const STALE_DAYS = 7

// Task assignment modal state
const showAssignModal = ref(false)
const currentRater = ref(null)
const assignSelected = ref([])   // numeric test ids selected for the current rater
const assignSearch = ref('')
const isSaving = ref(false)
const assignError = ref(null)
const exportTaskId = ref('')
const showExportModal = ref(false)
const currentRaterForExport = ref(null)
const selectedExportTaskId = ref('')

// ---- Messaging / nudge / remove(deactivate) modal state ----
const showMessageModal = ref(false)
const messageTarget = ref(null)
const messageBody = ref('')
const isSendingMsg = ref(false)
const messageError = ref(null)

const showBroadcastModal = ref(false)
const broadcastBody = ref('')
const isBroadcasting = ref(false)
const broadcastError = ref(null)

// ---- Sent messages (admin outbox) + edit ----
const showOutboxModal = ref(false)
const outboxItems = ref([])
const outboxLoading = ref(false)
const outboxError = ref(null)

const showEditMsgModal = ref(false)
const editTarget = ref(null)   // the outbox item currently being edited
const editBody = ref('')
const editError = ref(null)
const isSavingEdit = ref(false)

const showRemoveModal = ref(false)
const removeTarget = ref(null)
const removeConfirmText = ref('')
const isRemoving = ref(false)
const removeError = ref(null)
const isBulkNudging = ref(false)

const removeConfirmMatches = computed(() =>
  !!removeTarget.value &&
  removeConfirmText.value.trim().toLowerCase() === `delete ${removeTarget.value.name}`.toLowerCase()
)

// Copy a batch's rater-facing task URL to the clipboard.
const copyTaskLink = async (id) => {
  const url = `${window.location.origin}/${id}`
  try {
    await navigator.clipboard.writeText(url)
  } catch (_) {
    const ta = document.createElement('textarea')
    ta.value = url; document.body.appendChild(ta); ta.select()
    try { document.execCommand('copy') } catch (e) { /* ignore */ }
    ta.remove()
  }
  const toast = document.createElement('div')
  toast.className = 'position-fixed bottom-0 start-50 translate-middle-x mb-4 bg-dark text-white py-2.5 px-4 rounded-pill shadow-lg'
  toast.style.zIndex = '1080'
  toast.innerHTML = `<i class="bi bi-clipboard-check text-warning me-2"></i> Link copied: ${url}`
  document.body.appendChild(toast)
  setTimeout(() => { toast.style.opacity = '0'; setTimeout(() => toast.remove(), 300) }, 2200)
}

const exportCSV = async (id, raterId = null, raterName = '') => {
  if (!id) return
  try {
    const token = localStorage.getItem('authToken')
    if (!token) {
      router.push('/login')
      return
    }
    
    let url = `${API_BASE_URL}/admin/export_csv/${id}`
    if (raterId) {
      url += `?rater_id=${raterId}`
    }
    
    const response = await fetch(url, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    })
    
    if (response.status === 401) {
      localStorage.removeItem('authToken')
      router.push('/login')
      return
    }
    
    if (response.status === 404) {
      showToast('Task ID not found in database', 'bi-exclamation-triangle-fill text-danger')
      return
    }
    
    if (!response.ok) {
      throw new Error('Failed to export annotations.')
    }
    
    const blob = await response.blob()
    const downloadUrl = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = downloadUrl
    
    let filename = `annotations_task_${id}`
    if (raterName) {
      filename += `_rater_${raterName.replace(/\s+/g, '_')}`
    }
    filename += '.csv'
    
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    window.URL.revokeObjectURL(downloadUrl)
    
    showToast('Annotations exported successfully!', 'bi-check-circle-fill text-success')
  } catch (err) {
    console.error(err)
    showToast('Failed to export CSV. Please try again.', 'bi-exclamation-triangle-fill text-danger')
  }
}

const exportableTaskIds = computed(() => {
  return assignedIdList(currentRaterForExport.value)
})

const getTaskDescription = (tid) => {
  const t = tests.value.find(x => x.id === tid)
  return t ? t.description : 'No description'
}

const openExportModal = (rater) => {
  currentRaterForExport.value = rater
  selectedExportTaskId.value = ''
  showExportModal.value = true
  clearTimers()
}

const closeExportModal = () => {
  showExportModal.value = false
  currentRaterForExport.value = null
  if (isAutoRefreshActive.value) startTimers()
}

const confirmExport = () => {
  if (!currentRaterForExport.value || !selectedExportTaskId.value) return
  exportCSV(selectedExportTaskId.value, currentRaterForExport.value.id, currentRaterForExport.value.name)
  closeExportModal()
}

// Auto-Refresh
const isAutoRefreshActive = ref(true)
const countdown = ref(10)
const refreshInterval = 10 // seconds
let countdownTimer = null
let autoRefreshTimer = null

// Fetch data
const fetchDashboardData = async (manual = false) => {
  if (manual) isLoading.value = true
  try {
    const token = localStorage.getItem('authToken')
    if (!token) {
      router.push('/login')
      return
    }
    
    const response = await fetch(`${API_BASE_URL}/admin/dashboard`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    })
    
    if (response.status === 401) {
      localStorage.removeItem('authToken')
      router.push('/login')
      return
    }
    
    if (!response.ok) {
      throw new Error('Failed to fetch dashboard statistics.')
    }
    
    dashboardData.value = await response.json()
    error.value = null
  } catch (err) {
    console.error(err)
    error.value = 'Failed to load dashboard data. Please verify your connection or login status.'
  } finally {
    isLoading.value = false
    if (manual) {
      // Reset countdown on manual refresh
      countdown.value = refreshInterval
    }
  }
}

// Helpers
const getPercent = (completed, total) => {
  if (!total) return 0
  return Math.round((completed / total) * 100)
}

const formatDate = (isoString) => {
  if (!isoString) return ''
  const date = new Date(isoString)
  return date.toLocaleString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// ---- Admin tools: Needs Attention, stale annotators, table sorting ----
const daysSince = (iso) => {
  if (!iso) return Infinity
  const t = new Date(iso).getTime()
  if (isNaN(t)) return Infinity
  return Math.floor((Date.now() - t) / 86400000)
}

// A rater with assigned work, not yet finished, and no activity for STALE_DAYS+.
const isStale = (rater) => {
  const assigned = assignedIdList(rater).length
  if (!assigned) return false
  if ((rater.completed_tasks_count || 0) >= assigned) return false
  return daysSince(rater.last_active) >= STALE_DAYS
}

const focusBatches = (filter) => {
  batchAttentionFilter.value = batchAttentionFilter.value === filter ? '' : filter
  activeTab.value = 'batches'
}

const sortBatches = (key) => {
  if (batchSort.value.key === key) {
    batchSort.value = { key, dir: batchSort.value.dir === 'asc' ? 'desc' : 'asc' }
  } else {
    batchSort.value = { key, dir: key === 'id' ? 'asc' : 'desc' }
  }
}

const sortRaters = (key) => {
  if (raterSort.value.key === key) {
    raterSort.value = { key, dir: raterSort.value.dir === 'asc' ? 'desc' : 'asc' }
  } else {
    raterSort.value = { key, dir: (key === 'name' || key === 'email') ? 'asc' : 'desc' }
  }
}

const sortIcon = (state, key) => {
  if (state.key !== key) return 'bi-chevron-expand'
  return state.dir === 'asc' ? 'bi-caret-up-fill' : 'bi-caret-down-fill'
}

// Auto Refresh control
const toggleAutoRefresh = () => {
  isAutoRefreshActive.value = !isAutoRefreshActive.value
  if (isAutoRefreshActive.value) {
    startTimers()
  } else {
    clearTimers()
  }
}

const startTimers = () => {
  clearTimers()
  countdown.value = refreshInterval
  
  countdownTimer = setInterval(() => {
    if (countdown.value > 1) {
      countdown.value--
    } else {
      countdown.value = refreshInterval
    }
  }, 1000)
  
  autoRefreshTimer = setInterval(() => {
    fetchDashboardData(false)
  }, refreshInterval * 1000)
}

const clearTimers = () => {
  if (countdownTimer) clearInterval(countdownTimer)
  if (autoRefreshTimer) clearInterval(autoRefreshTimer)
}

// Reset page filters on search
watch(batchSearchQuery, () => {})
watch(raterSearchQuery, () => {})

// Computed stats properties
const stats = computed(() => dashboardData.value.stats || {})
const languages = computed(() => dashboardData.value.languages || [])
const tests = computed(() => dashboardData.value.tests || [])
const raters = computed(() => dashboardData.value.raters || [])

const globalProgressPercent = computed(() => {
  return getPercent(stats.value.unique_tasks_completed, stats.value.total_tasks)
})

// Audio segmentation: total audio duration + hours completed per annotator
const audioSegStats = computed(() => dashboardData.value.audio_segmentation || [])

// Audio tracker filters (Overview tab)
const audioLangFilter = ref('')
const audioPersonaFilter = ref('')

// Distinct languages across audio-segmentation batches
const audioLanguages = computed(() =>
  [...new Set(audioSegStats.value.map(s => s.language).filter(Boolean))].sort()
)

// Personas — narrowed to the selected language so the two filters stay in sync
const audioPersonas = computed(() => {
  let list = audioSegStats.value
  if (audioLangFilter.value) list = list.filter(s => s.language === audioLangFilter.value)
  return [...new Set(list.map(s => s.persona).filter(Boolean))].sort()
})

// Reset the persona filter whenever language changes so we never show an empty set
watch(audioLangFilter, () => { audioPersonaFilter.value = '' })

const filteredAudioSeg = computed(() =>
  audioSegStats.value.filter(s =>
    (!audioLangFilter.value || s.language === audioLangFilter.value) &&
    (!audioPersonaFilter.value || s.persona === audioPersonaFilter.value)
  )
)

// One set of totals for the current language + persona filter
const audioSegFilteredTotals = computed(() => {
  let accepted = 0, rejected = 0, totalSecs = 0, completedSecs = 0
  for (const seg of filteredAudioSeg.value) {
    accepted += seg.accepted || 0
    rejected += seg.rejected || 0
    totalSecs += seg.total_audio_seconds || 0
    completedSecs += seg.completed_audio_seconds || 0
  }
  return { accepted, rejected, total: accepted + rejected, totalSecs, completedSecs }
})

// 5025s -> "1h 23m 45s", 754s -> "12m 34s", 9s -> "9s"
const formatDuration = (seconds) => {
  const s = Math.round(seconds || 0)
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  if (h > 0) return `${h}h ${m}m ${sec}s`
  if (m > 0) return `${m}m ${sec}s`
  return `${sec}s`
}

const getVersionFromDescription = (description) => {
  if (!description) return 'V1 / Default'
  const match = description.match(/Version\s*([\w\d]+)/i)
  if (match) {
    return `Version ${match[1]}`
  }
  if (/new\s*version/i.test(description)) {
    return 'New Version'
  }
  return 'V1 / Default'
}

// Languages filter list
const uniqueLanguages = computed(() => {
  const langs = tests.value.map(t => t.language)
  return [...new Set(langs)].sort()
})

// Versions filter list
const uniqueVersions = computed(() => {
  const versions = tests.value.map(t => t.version || getVersionFromDescription(t.description))
  return [...new Set(versions)].sort((a, b) => {
    if (a.includes('Default') || a.includes('V1')) return -1
    if (b.includes('Default') || b.includes('V1')) return 1
    return a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' })
  })
})

// Test Types filter list
const uniqueTestTypes = computed(() => {
  const types = tests.value.map(t => t.test_type).filter(Boolean)
  return [...new Set(types)].sort()
})

const formatTestType = (type) => {
  if (!type) return ''
  return type.split('-').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ')
}

// Needs-Attention groupings (Overview)
const unassignedBatches = computed(() => tests.value.filter(t => !taskOwnerMap.value[t.id]))
const stalledBatches = computed(() => tests.value.filter(t => (t.unique_completed_tasks || 0) === 0))
const almostDoneBatches = computed(() => tests.value.filter(t => {
  const p = getPercent(t.unique_completed_tasks, t.total_tasks)
  return p >= 80 && p < 100
}))

// Filtered lists
const filteredTests = computed(() => {
  let list = tests.value

  if (batchLanguageFilter.value) {
    list = list.filter(t => t.language === batchLanguageFilter.value)
  }

  if (batchVersionFilter.value) {
    list = list.filter(t => (t.version || getVersionFromDescription(t.description)) === batchVersionFilter.value)
  }

  if (batchTestTypeFilter.value) {
    list = list.filter(t => t.test_type === batchTestTypeFilter.value)
  }

  if (batchSearchQuery.value) {
    const q = batchSearchQuery.value.toLowerCase()
    list = list.filter(t => t.description.toLowerCase().includes(q) || String(t.id).includes(q))
  }

  // Needs-Attention quick filter (set by the Overview cards)
  if (batchAttentionFilter.value === 'unassigned') {
    list = list.filter(t => !taskOwnerMap.value[t.id])
  } else if (batchAttentionFilter.value === 'stalled') {
    list = list.filter(t => (t.unique_completed_tasks || 0) === 0)
  } else if (batchAttentionFilter.value === 'almostdone') {
    list = list.filter(t => {
      const p = getPercent(t.unique_completed_tasks, t.total_tasks)
      return p >= 80 && p < 100
    })
  }

  // Column sorting
  const { key, dir } = batchSort.value
  const mul = dir === 'asc' ? 1 : -1
  return [...list].sort((a, b) => {
    switch (key) {
      case 'description':
        return mul * (a.description || '').localeCompare(b.description || '')
      case 'language':
        return mul * (a.language || '').localeCompare(b.language || '')
      case 'completion':
        return mul * (getPercent(a.unique_completed_tasks, a.total_tasks) - getPercent(b.unique_completed_tasks, b.total_tasks))
      case 'submissions':
        return mul * ((a.total_submissions || 0) - (b.total_submissions || 0))
      default:
        return mul * ((a.id || 0) - (b.id || 0))
    }
  })
})

// ---- Batch pagination (keeps the long task list scannable) ----
const batchPage = ref(1)
const batchPageSize = ref(12)
const batchPageCount = computed(() => Math.max(1, Math.ceil(filteredTests.value.length / batchPageSize.value)))
const pagedTests = computed(() => {
  const start = (batchPage.value - 1) * batchPageSize.value
  return filteredTests.value.slice(start, start + batchPageSize.value)
})
const batchRangeStart = computed(() => filteredTests.value.length ? (batchPage.value - 1) * batchPageSize.value + 1 : 0)
const batchRangeEnd = computed(() => Math.min(batchPage.value * batchPageSize.value, filteredTests.value.length))
// Snap back to page 1 whenever the filtered set or page size changes.
watch([() => filteredTests.value.length, batchPageSize], () => { batchPage.value = 1 })
watch(batchPage, (p) => {
  if (p < 1) batchPage.value = 1
  else if (p > batchPageCount.value) batchPage.value = batchPageCount.value
})

// Open a task in the SAME tab (in-app navigation) — used by the clickable batch row.
const openTask = (id) => { router.push(`/${id}`) }

// Parse a rater's assigned_tasks string ("1,2,3") into a numeric id array
const assignedIdList = (rater) => {
  if (!rater || !rater.assigned_tasks) return []
  return rater.assigned_tasks
    .split(',')
    .map(s => s.trim())
    .filter(s => /^\d+$/.test(s))
    .map(Number)
}

const staleRaters = computed(() => raters.value.filter(isStale))

const filteredRaters = computed(() => {
  // "Show all" off hides the long tail of auto-created / never-started accounts.
  // It defaults on so admins can assign tasks to brand-new annotators too.
  let list = raters.value
  if (!showAllRaters.value) {
    list = list.filter(r => r.completed_tasks_count >= 1)
  }

  if (showStaleOnly.value) {
    list = list.filter(isStale)
  }

  if (raterSearchQuery.value) {
    const q = raterSearchQuery.value.toLowerCase()
    list = list.filter(r => r.name.toLowerCase().includes(q) || r.email.toLowerCase().includes(q))
  }

  const { key, dir } = raterSort.value

  // Default view: annotators with assigned tasks float to the top, then by name.
  if (key === 'default') {
    return [...list].sort((a, b) => {
      const aHas = assignedIdList(a).length > 0 ? 0 : 1
      const bHas = assignedIdList(b).length > 0 ? 0 : 1
      if (aHas !== bHas) return aHas - bHas
      return (a.name || '').localeCompare(b.name || '')
    })
  }

  // Column sorting
  const mul = dir === 'asc' ? 1 : -1
  return [...list].sort((a, b) => {
    switch (key) {
      case 'name':
        return mul * (a.name || '').localeCompare(b.name || '')
      case 'email':
        return mul * (a.email || '').localeCompare(b.email || '')
      case 'completed':
        return mul * ((a.completed_tasks_count || 0) - (b.completed_tasks_count || 0))
      case 'assigned':
        return mul * (assignedIdList(a).length - assignedIdList(b).length)
      case 'lastactive':
        return mul * ((new Date(a.last_active || 0).getTime()) - (new Date(b.last_active || 0).getTime()))
      default:
        return 0
    }
  })
})

// ---- Task assignment helpers ----
const assignableTests = computed(() => {
  let list = tests.value
  if (assignSearch.value) {
    const q = assignSearch.value.toLowerCase()
    list = list.filter(t =>
      String(t.id).includes(q) ||
      (t.description || '').toLowerCase().includes(q) ||
      (t.language || '').toLowerCase().includes(q) ||
      (t.test_type || '').toLowerCase().includes(q)
    )
  }
  // Selected batches first, then by id ascending.
  return [...list].sort((a, b) => {
    const sa = assignSelected.value.includes(a.id) ? 0 : 1
    const sb = assignSelected.value.includes(b.id) ? 0 : 1
    if (sa !== sb) return sa - sb
    return a.id - b.id
  })
})

// Map of test id -> name of another annotator it is already locked to (excludes the rater
// currently being edited). Lets the admin spot conflicts before double-assigning a task.
const taskOwnerMap = computed(() => {
  const map = {}
  for (const r of raters.value) {
    if (currentRater.value && r.id === currentRater.value.id) continue
    for (const id of assignedIdList(r)) {
      if (!map[id]) map[id] = r.name
    }
  }
  return map
})

const toggleTask = (id) => {
  const i = assignSelected.value.indexOf(id)
  if (i === -1) assignSelected.value.push(id)
  else assignSelected.value.splice(i, 1)
}

const openAssignModal = (rater) => {
  currentRater.value = rater
  assignSelected.value = assignedIdList(rater)
  assignSearch.value = ''
  assignError.value = null
  showAssignModal.value = true
  clearTimers()   // pause auto-refresh so the table doesn't shift under the admin
}

const closeAssignModal = () => {
  showAssignModal.value = false
  currentRater.value = null
  if (isAutoRefreshActive.value) startTimers()
}

const showToast = (msg, icon = 'bi-check-circle-fill text-success') => {
  const toast = document.createElement('div')
  toast.className = 'position-fixed bottom-0 start-50 translate-middle-x mb-4 bg-dark text-white py-2 px-4 rounded-pill shadow-lg'
  toast.style.zIndex = '1080'
  toast.style.transition = 'opacity 0.3s ease'
  toast.innerHTML = `<i class="bi ${icon} me-2"></i> ${msg}`
  document.body.appendChild(toast)
  setTimeout(() => { toast.style.opacity = '0'; setTimeout(() => toast.remove(), 300) }, 2400)
}

// Small helper: authenticated POST that returns parsed JSON or throws with the
// server-provided message. Mirrors the pattern used by saveAssignments.
const adminPost = async (path, body) => {
  const token = localStorage.getItem('authToken')
  if (!token) { router.push('/login'); throw new Error('Not authenticated') }
  const resp = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {})
  })
  const data = await resp.json().catch(() => ({}))
  if (!resp.ok) throw new Error(data.message || `Request failed (HTTP ${resp.status}).`)
  return data
}

// Authenticated PUT — same contract as adminPost, used for editing sent messages.
const adminPut = async (path, body) => {
  const token = localStorage.getItem('authToken')
  if (!token) { router.push('/login'); throw new Error('Not authenticated') }
  const resp = await fetch(`${API_BASE_URL}${path}`, {
    method: 'PUT',
    headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {})
  })
  const data = await resp.json().catch(() => ({}))
  if (!resp.ok) throw new Error(data.message || `Request failed (HTTP ${resp.status}).`)
  return data
}

// ---- Message a single annotator ----
const openMessageModal = (rater) => {
  messageTarget.value = rater
  messageBody.value = ''
  messageError.value = null
  showMessageModal.value = true
  clearTimers()
}
const closeMessageModal = () => {
  showMessageModal.value = false
  messageTarget.value = null
  if (isAutoRefreshActive.value) startTimers()
}
const sendMessage = async () => {
  if (!messageTarget.value || !messageBody.value.trim()) return
  isSendingMsg.value = true
  messageError.value = null
  try {
    const name = messageTarget.value.name
    await adminPost(`/admin/rater/${messageTarget.value.id}/message`, { body: messageBody.value.trim() })
    closeMessageModal()
    showToast(`Message sent to ${name}`)
    fetchDashboardData(false)
  } catch (err) {
    messageError.value = err.message || 'Failed to send message.'
  } finally {
    isSendingMsg.value = false
  }
}

// ---- Nudge (canned reminder) ----
const nudgeRater = async (rater) => {
  try {
    await adminPost(`/admin/rater/${rater.id}/nudge`, {})
    showToast(`Reminder sent to ${rater.name}`, 'bi-bell-fill text-warning')
    fetchDashboardData(false)
  } catch (err) {
    showToast(err.message || 'Failed to send nudge.', 'bi-exclamation-triangle-fill text-danger')
  }
}
const remindAllStale = async () => {
  if (isBulkNudging.value || !staleRaters.value.length) return
  isBulkNudging.value = true
  try {
    let ok = 0
    for (const r of staleRaters.value) {
      try { await adminPost(`/admin/rater/${r.id}/nudge`, {}); ok++ } catch (_) { /* skip */ }
    }
    showToast(`Reminder sent to ${ok} stale annotator(s)`, 'bi-bell-fill text-warning')
    fetchDashboardData(false)
  } finally {
    isBulkNudging.value = false
  }
}

// ---- Broadcast to all ----
const openBroadcastModal = () => {
  broadcastBody.value = ''
  broadcastError.value = null
  showBroadcastModal.value = true
  clearTimers()
}
const closeBroadcastModal = () => {
  showBroadcastModal.value = false
  if (isAutoRefreshActive.value) startTimers()
}
const sendBroadcast = async () => {
  if (!broadcastBody.value.trim()) return
  isBroadcasting.value = true
  broadcastError.value = null
  try {
    const data = await adminPost('/admin/message/broadcast', { body: broadcastBody.value.trim() })
    closeBroadcastModal()
    showToast(data.message || 'Broadcast sent', 'bi-broadcast text-primary')
    fetchDashboardData(false)
  } catch (err) {
    broadcastError.value = err.message || 'Failed to broadcast.'
  } finally {
    isBroadcasting.value = false
  }
}

// ---- Sent messages (outbox): view + edit ----
const openOutbox = async () => {
  showOutboxModal.value = true
  clearTimers()
  await fetchOutbox()
}
const closeOutbox = () => {
  showOutboxModal.value = false
  if (isAutoRefreshActive.value) startTimers()
}
const fetchOutbox = async () => {
  outboxLoading.value = true
  outboxError.value = null
  try {
    const token = localStorage.getItem('authToken')
    if (!token) { router.push('/login'); return }
    const resp = await fetch(`${API_BASE_URL}/admin/messages`, {
      headers: { 'Authorization': `Bearer ${token}` }
    })
    const data = await resp.json().catch(() => ({}))
    if (!resp.ok) throw new Error(data.message || `Request failed (HTTP ${resp.status}).`)
    outboxItems.value = data.items || []
  } catch (err) {
    outboxError.value = err.message || 'Failed to load sent messages.'
  } finally {
    outboxLoading.value = false
  }
}
const openEditMsg = (item) => {
  editTarget.value = item
  editBody.value = item.body || ''
  editError.value = null
  showEditMsgModal.value = true
}
const closeEditMsg = () => {
  showEditMsgModal.value = false
  editTarget.value = null
}
const saveEditMsg = async () => {
  if (!editTarget.value || !editBody.value.trim()) return
  isSavingEdit.value = true
  editError.value = null
  try {
    const item = editTarget.value
    const path = item.kind === 'broadcast'
      ? `/admin/broadcast/${item.broadcast_id}`
      : `/admin/message/${item.id}`
    const data = await adminPut(path, { body: editBody.value.trim() })
    closeEditMsg()
    showToast(data.message || 'Message updated', 'bi-check-circle-fill text-success')
    await fetchOutbox()
    fetchDashboardData(false)
  } catch (err) {
    editError.value = err.message || 'Failed to update message.'
  } finally {
    isSavingEdit.value = false
  }
}

// ---- Remove (deactivate) / reactivate ----
const openRemoveModal = (rater) => {
  removeTarget.value = rater
  removeConfirmText.value = ''
  removeError.value = null
  showRemoveModal.value = true
  clearTimers()
}
const closeRemoveModal = () => {
  showRemoveModal.value = false
  removeTarget.value = null
  if (isAutoRefreshActive.value) startTimers()
}
const confirmRemove = async () => {
  if (!removeTarget.value || !removeConfirmMatches.value) return
  isRemoving.value = true
  removeError.value = null
  try {
    const name = removeTarget.value.name
    const data = await adminPost(`/admin/rater/${removeTarget.value.id}/deactivate`, { confirm: removeConfirmText.value.trim() })
    closeRemoveModal()
    showToast(data.message || `${name} deactivated`, 'bi-person-dash-fill text-danger')
    fetchDashboardData(false)
  } catch (err) {
    removeError.value = err.message || 'Failed to deactivate annotator.'
  } finally {
    isRemoving.value = false
  }
}
const reactivateRater = async (rater) => {
  try {
    const data = await adminPost(`/admin/rater/${rater.id}/reactivate`, {})
    showToast(data.message || `${rater.name} reactivated`, 'bi-arrow-counterclockwise text-success')
    fetchDashboardData(false)
  } catch (err) {
    showToast(err.message || 'Failed to reactivate.', 'bi-exclamation-triangle-fill text-danger')
  }
}

const saveAssignments = async () => {
  if (!currentRater.value) return
  isSaving.value = true
  assignError.value = null
  try {
    const token = localStorage.getItem('authToken')
    if (!token) {
      router.push('/login')
      return
    }
    const resp = await fetch(`${API_BASE_URL}/admin/rater/${currentRater.value.id}/assign_tasks`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ assigned_tasks: assignSelected.value.join(',') })
    })

    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}))
      throw new Error(data.message || `Failed to save (HTTP ${resp.status}).`)
    }

    const data = await resp.json()
    const raterName = currentRater.value.name
    // Reflect the change immediately in the open table.
    currentRater.value.assigned_tasks = data.assigned_tasks
    const count = data.assigned_tasks ? data.assigned_tasks.split(',').filter(Boolean).length : 0

    showAssignModal.value = false
    currentRater.value = null
    if (isAutoRefreshActive.value) startTimers()
    showToast(`${count} task(s) locked to ${raterName}`)
    fetchDashboardData(false)
  } catch (err) {
    console.error(err)
    assignError.value = err.message || 'Failed to save assignment.'
  } finally {
    isSaving.value = false
  }
}

// Lifecycle
onMounted(() => {
  const token = localStorage.getItem('authToken')
  if (!token) {
    router.push('/login')
    return
  }
  
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    if (payload.username !== 'admin') {
      router.push('/')
      return
    }
  } catch (e) {
    router.push('/login')
    return
  }
  
  fetchDashboardData(true)
  if (isAutoRefreshActive.value) {
    startTimers()
  }
})

onUnmounted(() => {
  clearTimers()
})
</script>

<style scoped>
.dashboard-container {
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 20px;
}

/* Tab button customizations */
.tabs-nav {
  background-color: #f8f9fa;
}
.tab-btn {
  border-radius: 6px;
  transition: all 0.2s ease;
  font-size: 0.95rem;
}
.tab-btn:hover {
  transform: translateY(-1px);
}

/* KPI cards styling */
.kpi-card {
  height: 100%;
  border-radius: 12px;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.kpi-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 8px 20px rgba(0,0,0,0.08) !important;
}
.kpi-icon-wrapper {
  width: 42px;
  height: 42px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* Language card styling */
.lang-card {
  border-radius: 12px;
  border: 1px solid rgba(0,0,0,0.08);
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}
.lang-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 10px 25px rgba(0,0,0,0.08) !important;
  border-color: rgba(0,0,0,0.15);
}

/* Audio tracker accept/reject totals pills */
.seg-stat-pill {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 96px;
  padding: 0.45rem 0.9rem;
  border-radius: 12px;
  border: 1px solid rgba(0,0,0,0.08);
  background: #f8f9fa;
}
.seg-stat-pill .lbl {
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: #64748b;
}
.seg-stat-pill .val {
  font-size: 1.35rem;
  font-weight: 700;
  line-height: 1.1;
  color: #1e293b;
}
.seg-stat-pill.accept {
  background: #ecfdf3;
  border-color: #abefc6;
}
.seg-stat-pill.accept .lbl,
.seg-stat-pill.accept .val { color: #087443; }
.seg-stat-pill.reject {
  background: #fef3f2;
  border-color: #fecdca;
}
.seg-stat-pill.reject .lbl,
.seg-stat-pill.reject .val { color: #b42318; }
.seg-stat-pill.total {
  background: #eff8ff;
  border-color: #b2ddff;
}
.seg-stat-pill.total .lbl,
.seg-stat-pill.total .val { color: #175cd3; }

/* Helper Text styles */
.text-xs {
  font-size: 0.825rem;
}
.text-uppercase {
  letter-spacing: 0.05em;
}

/* Modern Gradient Progress Bars */
.bg-light-gradient {
  background-color: #e9ecef;
}
.progress-gradient {
  background: linear-gradient(90deg, #d8661b, #fdba74);
  border-radius: 5px;
}

/* Animation utilities */
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
.animate-spin {
  animation: spin 1.2s linear infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
.animate-pulse {
  animation: pulse 1.5s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

@keyframes pulse-slow {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.08); }
}
.animate-pulse-slow {
  animation: pulse-slow 2s infinite ease-in-out;
}

@keyframes pulse-border {
  0%, 100% { box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.4); }
  50% { box-shadow: 0 0 0 4px rgba(245, 158, 11, 0); }
}
.animate-pulse-border {
  animation: pulse-border 2s infinite ease-in-out;
}

/* Avatar layout for raters list */
.avatar-circle {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background-color: #d8661b;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 0.9rem;
}

/* Status dots */
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #cbd5e1;
}
.status-dot.active {
  background-color: #22c55e;
}

/* Assigned task chips inside the table */
.assigned-chip-wrap {
  max-width: 220px;
}

/* ===================== Assign Tasks Modal ===================== */
.assign-modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.55);
  backdrop-filter: blur(3px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1070;
  padding: 1rem;
}

.assign-modal-card {
  background: #fff;
  width: 100%;
  max-width: 620px;
  max-height: 90vh;
  border-radius: 18px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.assign-modal-header {
  padding: 1.1rem 1.5rem;
  border-bottom: 1px solid #eef2f7;
}

.assign-modal-body {
  padding: 1.25rem 1.5rem;
  overflow-y: auto;
}

.assign-modal-footer {
  padding: 1rem 1.5rem;
  border-top: 1px solid #eef2f7;
  background: #f8fafc;
}

.avatar-circle-lg {
  width: 46px;
  height: 46px;
  border-radius: 50%;
  background: linear-gradient(135deg, #d8661b, #f4a93c);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 1.2rem;
  flex-shrink: 0;
}

/* Selected chips row */
.selected-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  max-height: 110px;
  overflow-y: auto;
}
.selected-chips .chip {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  background: #fceee3;
  color: #b4530f;
  border: 1px solid #f3cdaa;
  font-weight: 600;
  font-size: 0.8rem;
  padding: 0.25rem 0.65rem;
  border-radius: 999px;
}
.selected-chips .chip i {
  cursor: pointer;
  font-size: 0.65rem;
  opacity: 0.7;
  transition: opacity 0.15s ease;
}
.selected-chips .chip i:hover {
  opacity: 1;
}

/* Scrollable batch picker */
.batch-picker {
  max-height: 300px;
  overflow-y: auto;
}
.batch-row {
  cursor: pointer;
  border-bottom: 1px solid #f1f5f9;
  margin: 0;
  transition: background 0.12s ease;
}
.batch-row:last-child {
  border-bottom: none;
}
.batch-row:hover {
  background: #f8fafc;
}
.batch-row.selected {
  background: #fceee3;
}

/* Modal fade + scale transition */
.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.2s ease;
}
.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}
.modal-fade-enter-active .assign-modal-card,
.modal-fade-leave-active .assign-modal-card {
  transition: transform 0.22s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.modal-fade-enter-from .assign-modal-card,
.modal-fade-leave-to .assign-modal-card {
  transform: translateY(18px) scale(0.97);
}

/* Sortable table headers */
/* Clickable batch rows: the whole row opens the task in the same tab */
.batch-row { cursor: pointer; transition: background-color .12s ease, box-shadow .12s ease; }
.batch-row:hover { background-color: #fff7ee !important; box-shadow: inset 3px 0 0 #d8661b; }

/* Rater actions: uniform square icon buttons in a single tidy row */
.rater-actions { flex-wrap: nowrap; }
.rater-action-btn {
  width: 32px; height: 32px; padding: 0;
  display: inline-flex; align-items: center; justify-content: center;
  border-radius: 8px; flex-shrink: 0;
}
.rater-action-btn .bi { font-size: 0.9rem; }
.rater-msg-badge {
  position: absolute; top: -5px; right: -5px;
  min-width: 15px; height: 15px; line-height: 15px; padding: 0 3px;
  background: #64748b; color: #fff; font-size: 0.58rem; font-weight: 700;
  border-radius: 999px; box-shadow: 0 0 0 1.5px #fff;
}

.sortable-th {
  cursor: pointer;
  user-select: none;
  white-space: nowrap;
  transition: color 0.15s ease;
}
.sortable-th:hover {
  color: var(--brand, #d8661b);
}
.sortable-th .bi {
  font-size: 0.75rem;
  opacity: 0.6;
}

/* Needs Attention cards */
.attention-card {
  cursor: pointer;
  transition: transform 0.18s ease, box-shadow 0.18s ease;
}
.attention-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 10px 22px rgba(15, 23, 42, 0.08) !important;
}
.attention-chip {
  background: #fceee3;
  color: #b4530f;
  border: 1px solid #f3cdaa;
  font-size: 0.72rem;
  font-weight: 600;
  vertical-align: middle;
}

/* Stale-annotator alert + rows */
.stale-alert {
  background: #fff7ed;
  border: 1px solid #fed7aa;
  color: #9a3412;
  border-radius: 12px;
}
.stale-badge {
  background: #fef3c7;
  color: #92400e;
  border: 1px solid #fde68a;
  font-size: 0.68rem;
  font-weight: 600;
}
.stale-row {
  background: #fffbeb !important;
}
.stale-row:hover {
  background: #fef3c7 !important;
}
</style>