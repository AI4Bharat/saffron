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
    <div class="tabs-nav mb-4 bg-white p-2 rounded shadow-sm border d-flex gap-2 flex-wrap">
      <button
        v-for="t in tabs"
        :key="t.key"
        @click="activeTab = t.key"
        :title="t.hint"
        :class="['tab-btn btn flex-fill py-2 fw-semibold d-flex align-items-center justify-content-center gap-2', activeTab === t.key ? 'btn-dark text-white' : 'btn-light text-secondary']"
      >
        <i :class="['bi', t.icon]"></i>
        <span>{{ t.label }}</span>
      </button>
    </div>

    <!-- Tab Contents -->
    <div v-if="!isLoading || dashboardData.stats" class="tab-content">
      <!-- OVERVIEW TAB -->
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
        <!-- Language Breakdown section (compact table) -->
        <div class="bg-white rounded shadow-sm border mb-4">
          <div class="d-flex justify-content-between align-items-center px-3 pt-3 pb-2">
            <h3 class="fw-bold text-dark m-0 fs-5"><i class="bi bi-translate text-primary me-2"></i>Languages Statistics</h3>
            <span class="text-muted text-xs">{{ languages.length }} language{{ languages.length === 1 ? '' : 's' }}</span>
          </div>
          <div v-if="languages.length === 0" class="text-center text-muted py-4">
            No languages stats found.
          </div>
          <div v-else class="table-responsive">
            <table class="table table-sm align-middle mb-0 lang-compact-table">
              <thead class="table-light">
                <tr>
                  <th class="text-xs ps-3">Language</th>
                  <th class="text-xs text-end">Batches</th>
                  <th class="text-xs" style="min-width:150px">Completed Coverage</th>
                  <th class="text-xs text-end">Unique Tasks</th>
                  <th class="text-xs text-end pe-3">Submissions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="lang in languages" :key="lang.language">
                  <td class="fw-semibold text-dark text-xs ps-3">{{ lang.language }}</td>
                  <td class="text-end text-xs text-muted">{{ lang.test_count }}</td>
                  <td>
                    <div class="d-flex align-items-center gap-2">
                      <div class="progress bg-light-gradient flex-grow-1" style="height:6px; border-radius:3px;">
                        <div class="progress-bar progress-gradient" role="progressbar"
                             :style="{ width: getPercent(lang.unique_completed_tasks, lang.total_tasks) + '%' }"></div>
                      </div>
                      <span class="fw-bold text-dark text-xs" style="min-width:38px; text-align:right">
                        {{ getPercent(lang.unique_completed_tasks, lang.total_tasks) }}%
                      </span>
                    </div>
                  </td>
                  <td class="text-end text-xs text-dark">{{ lang.unique_completed_tasks }} / {{ lang.total_tasks }}</td>
                  <td class="text-end text-xs text-dark pe-3">{{ lang.total_submissions }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

      </div>

      <!-- TASKS TAB (sub-tabs: Overview | All Tasks) -->
      <div v-if="activeTab === 'tasks'">
        <!-- Sub-tab nav: centered segmented control -->
        <div class="d-flex justify-content-center mb-4">
          <div class="tasks-subnav d-inline-flex align-items-center">
            <button type="button" @click="tasksSubTab = 'overview'"
              :class="['subnav-btn', { active: tasksSubTab === 'overview' }]">
              <i class="bi bi-stack"></i><span>Overview</span>
            </button>
            <button type="button" @click="tasksSubTab = 'alltasks'"
              :class="['subnav-btn', { active: tasksSubTab === 'alltasks' }]">
              <i class="bi bi-list-check"></i><span>All Tasks</span>
              <span class="subnav-badge">{{ filteredTests.length }}</span>
            </button>
          </div>
        </div>

        <!-- Overview sub-pane -->
        <div v-show="tasksSubTab === 'overview'">
        <!-- Tasks Overview: every task type under its own sub-tab -->
        <h3 class="fw-bold text-dark mb-3"><i class="bi bi-stack text-primary me-2"></i>Tasks Overview</h3>
        <div v-if="taskTypeNames.length" class="bg-white rounded shadow-sm border mb-4">
          <!-- Sub-tab nav: one pill per task type -->
          <div class="d-flex flex-wrap gap-1 p-2 border-bottom type-tabs">
            <button
              v-for="tt in taskTypeNames"
              :key="tt"
              type="button"
              @click="activeTypeTab = tt"
              :class="['type-tab-btn btn btn-sm fw-semibold', activeTypeTab === tt ? 'btn-dark text-white' : 'btn-light text-secondary']"
            >
              {{ formatTestType(tt) }}
              <span class="badge rounded-pill ms-1" :class="activeTypeTab === tt ? 'bg-white text-dark' : 'bg-secondary-subtle text-secondary'">
                {{ taskTypes[tt].totals.batches }}
              </span>
            </button>
          </div>

          <div v-if="currentType" class="p-3">
            <!-- Totals strip: the numbers an admin needs at a glance -->
            <div class="d-flex flex-wrap gap-2 mb-3">
              <div class="ov-tile">
                <span class="lbl">Batches</span>
                <span class="val">{{ currentType.totals.batches }}</span>
                <span class="sub">
                  <span class="text-success fw-semibold">{{ currentType.totals.batches_complete }} done</span> ·
                  <span class="text-warning-emphasis fw-semibold">{{ currentType.totals.batches_stalled }} stalled</span> ·
                  <span class="text-danger fw-semibold">{{ currentType.totals.batches_unassigned }} unassigned</span>
                </span>
              </div>
              <div class="ov-tile">
                <span class="lbl">Tasks completed</span>
                <span class="val">{{ currentType.totals.unique_completed.toLocaleString() }} <small class="text-muted fw-normal">/ {{ currentType.totals.total_tasks.toLocaleString() }}</small></span>
                <div class="progress mt-1 mb-1" style="height: 5px;">
                  <div class="progress-bar bg-success" :style="{ width: getPercent(currentType.totals.unique_completed, currentType.totals.total_tasks) + '%' }"></div>
                </div>
                <span class="sub">{{ getPercent(currentType.totals.unique_completed, currentType.totals.total_tasks) }}% coverage</span>
              </div>
              <div class="ov-tile">
                <span class="lbl">Submissions</span>
                <span class="val">{{ currentType.totals.total_submissions.toLocaleString() }}</span>
                <span class="sub">{{ currentType.totals.skipped ? currentType.totals.skipped + ' skipped' : 'includes re-submissions' }}</span>
              </div>
              <div v-if="typeHasEval" class="ov-tile">
                <span class="lbl">Accept / Reject</span>
                <span class="val">
                  <span class="text-success">{{ currentType.totals.accepted.toLocaleString() }}</span>
                  <span class="text-muted mx-1 fw-normal">/</span>
                  <span class="text-danger">{{ currentType.totals.rejected.toLocaleString() }}</span>
                </span>
                <span class="sub">{{ getPercent(currentType.totals.accepted, currentType.totals.accepted + currentType.totals.rejected) }}% accepted</span>
              </div>
              <div v-if="currentType.totals.in_progress" class="ov-tile">
                <span class="lbl">Drafts saved</span>
                <span class="val">{{ currentType.totals.in_progress }}</span>
                <span class="sub">in-progress work</span>
              </div>
              <div class="ov-tile">
                <span class="lbl">Annotators</span>
                <span class="val">{{ currentType.totals.annotators }}</span>
                <span class="sub">have submitted</span>
              </div>
              <div class="ov-tile">
                <span class="lbl">Last activity</span>
                <span class="val fs-6">{{ timeAgo(currentType.totals.last_activity) }}</span>
                <span class="sub">{{ formatDate(currentType.totals.last_activity) || 'no submissions yet' }}</span>
              </div>
            </div>

            <!-- Audio segmentation keeps its per-batch hours tracker -->
            <template v-if="activeTypeTab === 'audio-segmentation'">
          <div class="d-flex flex-wrap justify-content-end align-items-center mb-3 gap-2">
            <span class="badge bg-light text-dark border py-2 px-3">
              <i class="bi bi-soundwave text-primary me-1"></i>
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
            </template>

            <!-- Every other task type: dense per-batch table with per-annotator drill-down -->
            <template v-else>
              <div class="row g-2 align-items-end mb-3">
                <div class="col-6 col-md-2">
                  <label class="form-label text-xs fw-bold text-secondary mb-1">Language</label>
                  <select v-model="typeLangFilter" class="form-select form-select-sm">
                    <option value="">All Languages</option>
                    <option v-for="l in typeLanguages" :key="l" :value="l">{{ l }}</option>
                  </select>
                </div>
                <div class="col-6 col-md-2">
                  <label class="form-label text-xs fw-bold text-secondary mb-1">Status</label>
                  <select v-model="typeStatusFilter" class="form-select form-select-sm">
                    <option value="">All Statuses</option>
                    <option value="notstarted">Not started</option>
                    <option value="inprogress">In progress</option>
                    <option value="complete">Complete</option>
                    <option value="unassigned">Unassigned</option>
                  </select>
                </div>
                <div class="col-12 col-md-4">
                  <label class="form-label text-xs fw-bold text-secondary mb-1">Search</label>
                  <input v-model="typeSearch" type="text" class="form-control form-control-sm" placeholder="ID, description or annotator…" />
                </div>
                <div class="col-12 col-md-4 text-md-end text-muted text-xs pb-1">
                  Showing {{ typeRangeStart }}–{{ typeRangeEnd }} of {{ filteredTypeBatches.length }} batches · click a row for the annotator breakdown
                </div>
              </div>

              <div class="table-responsive border rounded">
                <table class="table table-sm table-hover align-middle mb-0">
                  <thead class="table-light">
                    <tr>
                      <th style="width: 28px;"></th>
                      <th class="sortable-th" style="width: 70px;" @click="sortType('id')">ID <i :class="['bi', sortIcon(typeSort, 'id')]"></i></th>
                      <th>Description</th>
                      <th style="width: 95px;">Language</th>
                      <th style="width: 145px;">Assigned to</th>
                      <th style="width: 105px;">Status</th>
                      <th class="sortable-th" style="width: 185px;" @click="sortType('completion')">Progress <i :class="['bi', sortIcon(typeSort, 'completion')]"></i></th>
                      <th class="sortable-th text-end" style="width: 65px;" @click="sortType('submissions')" title="Total submissions">Subs <i :class="['bi', sortIcon(typeSort, 'submissions')]"></i></th>
                      <th v-if="typeHasEval" class="text-center" style="width: 85px;" title="Accepted / Rejected">
                        <i class="bi bi-check-circle text-success"></i> / <i class="bi bi-x-circle text-danger"></i>
                      </th>
                      <th class="text-end" style="width: 85px;" title="Average time per task">Avg time</th>
                      <th class="sortable-th text-end pe-3" style="width: 105px;" @click="sortType('lastactivity')">Activity <i :class="['bi', sortIcon(typeSort, 'lastactivity')]"></i></th>
                    </tr>
                  </thead>
                  <tbody>
                    <template v-for="b in pagedTypeBatches" :key="b.test_id">
                      <tr class="type-row" @click="toggleTypeRow(b.test_id)">
                        <td class="text-center text-muted"><i :class="['bi text-xs', expandedTypeRows.includes(b.test_id) ? 'bi-chevron-down' : 'bi-chevron-right']"></i></td>
                        <td><a href="#" class="fw-semibold text-decoration-none" title="Open this batch" @click.stop.prevent="openTask(b.test_id)">#{{ b.test_id }}</a></td>
                        <td class="text-truncate" style="max-width: 320px;" :title="b.description">
                          <span class="text-dark text-xs">{{ b.description }}</span>
                        </td>
                        <td><span class="badge rounded-pill bg-secondary-subtle text-secondary border">{{ b.language || '—' }}</span></td>
                        <td>
                          <span v-if="b.assigned_to.length" class="text-xs text-dark" :title="b.assigned_to.join(', ')">
                            {{ b.assigned_to.slice(0, 2).join(', ') }}<span v-if="b.assigned_to.length > 2" class="text-muted"> +{{ b.assigned_to.length - 2 }}</span>
                          </span>
                          <span v-else class="badge bg-danger-subtle text-danger rounded-pill">Unassigned</span>
                        </td>
                        <td>
                          <span :class="['badge rounded-pill', batchStatus(b) === 'Complete' ? 'bg-success-subtle text-success' : batchStatus(b) === 'In progress' ? 'bg-warning-subtle text-warning-emphasis' : 'bg-light text-muted border']">
                            {{ batchStatus(b) }}
                          </span>
                        </td>
                        <td>
                          <div class="d-flex align-items-center gap-2">
                            <span class="text-xs text-nowrap fw-semibold">{{ b.unique_completed }} / {{ b.total_tasks }}</span>
                            <div class="progress flex-grow-1" style="height: 5px; min-width: 36px;">
                              <div class="progress-bar" :class="batchStatus(b) === 'Complete' ? 'bg-success' : 'bg-warning'" :style="{ width: getPercent(b.unique_completed, b.total_tasks) + '%' }"></div>
                            </div>
                            <span class="text-xs text-muted" style="min-width: 32px;">{{ getPercent(b.unique_completed, b.total_tasks) }}%</span>
                          </div>
                        </td>
                        <td class="text-end text-xs">{{ b.total_submissions }}</td>
                        <td v-if="typeHasEval" class="text-center text-xs">
                          <span class="text-success fw-bold">{{ b.accepted }}</span><span class="text-muted mx-1">/</span><span class="text-danger fw-bold">{{ b.rejected }}</span>
                        </td>
                        <td class="text-end text-xs">{{ b.avg_secs ? formatDuration(b.avg_secs) : '—' }}</td>
                        <td class="text-end text-xs pe-3" :title="formatDate(b.last_activity)">{{ timeAgo(b.last_activity) }}</td>
                      </tr>
                      <tr v-if="expandedTypeRows.includes(b.test_id)">
                        <td :colspan="typeHasEval ? 11 : 10" class="p-0 border-bottom">
                          <div class="p-3 bg-light-subtle">
                            <table v-if="b.annotators.length" class="table table-sm mb-0 bg-white border rounded">
                              <thead class="table-light">
                                <tr>
                                  <th class="text-xs">Annotator</th>
                                  <th class="text-xs text-end" style="width: 110px;">Completed</th>
                                  <th v-if="typeHasEval" class="text-xs text-center" style="width: 110px;">Accept / Reject</th>
                                  <th class="text-xs text-end" style="width: 80px;">Skipped</th>
                                  <th class="text-xs text-end" style="width: 80px;">Drafts</th>
                                  <th class="text-xs text-end" style="width: 110px;">Avg time / task</th>
                                  <th class="text-xs text-end" style="width: 120px;">Last activity</th>
                                </tr>
                              </thead>
                              <tbody>
                                <tr v-for="a in b.annotators" :key="a.rater_id">
                                  <td class="text-xs"><span class="fw-semibold text-dark">{{ a.name }}</span> <span class="text-muted">· {{ a.email }}</span></td>
                                  <td class="text-xs text-end fw-semibold">{{ a.completed }} / {{ b.total_tasks }}</td>
                                  <td v-if="typeHasEval" class="text-xs text-center"><span class="text-success fw-bold">{{ a.accepted }}</span><span class="text-muted mx-1">/</span><span class="text-danger fw-bold">{{ a.rejected }}</span></td>
                                  <td class="text-xs text-end">{{ a.skipped || 0 }}</td>
                                  <td class="text-xs text-end">{{ a.in_progress || 0 }}</td>
                                  <td class="text-xs text-end">{{ a.avg_secs ? formatDuration(a.avg_secs) : '—' }}</td>
                                  <td class="text-xs text-end" :title="formatDate(a.last_activity)">{{ timeAgo(a.last_activity) }}</td>
                                </tr>
                              </tbody>
                            </table>
                            <div v-else class="text-muted text-xs">No submissions on this batch yet.</div>
                          </div>
                        </td>
                      </tr>
                    </template>
                    <tr v-if="filteredTypeBatches.length === 0">
                      <td :colspan="typeHasEval ? 11 : 10" class="text-center text-muted py-4">No batches match the selected filters.</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <!-- Pager -->
              <div v-if="typePageCount > 1" class="d-flex justify-content-between align-items-center pt-3">
                <span class="text-muted text-xs">Page {{ typePage }} of {{ typePageCount }}</span>
                <div class="btn-group">
                  <button class="btn btn-sm btn-light border" :disabled="typePage <= 1" @click="typePage--"><i class="bi bi-chevron-left"></i></button>
                  <button class="btn btn-sm btn-light border" :disabled="typePage >= typePageCount" @click="typePage++"><i class="bi bi-chevron-right"></i></button>
                </div>
              </div>
            </template>
          </div>
        </div>
        </div><!-- /Overview sub-pane -->

        <!-- All Tasks sub-pane: the full batch list -->
        <div v-show="tasksSubTab === 'alltasks'">
        <div id="batch-list-section" class="card shadow-sm border mb-4">
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
        </div><!-- /All Tasks sub-pane -->
      </div>

      <!-- ANNOTATORS TAB -->
      <div v-if="activeTab === 'annotators'">
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
                  <button class="btn btn-outline-primary btn-sm d-inline-flex align-items-center gap-1" @click="openRatingsModal(null)" title="Export raw task rating submissions">
                    <i class="bi bi-file-earmark-code"></i> Ratings Export
                  </button>
                  <button class="btn btn-success btn-sm d-inline-flex align-items-center gap-1" @click="openAnnotatorDataModal(null)" title="Export annotators data with timeline selector (Default: Entire Life)">
                    <i class="bi bi-calendar-range"></i> Annotators Data
                  </button>
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
          
          <!-- Period filter: work done between two dates (default = all time) -->
          <div class="px-3 py-2 border-bottom bg-light-subtle">
            <div class="d-flex flex-wrap align-items-end gap-2">
              <div>
                <label class="form-label text-xs fw-bold text-secondary mb-1">From</label>
                <input type="date" v-model="activityFrom" class="form-control form-control-sm" style="max-width:170px">
              </div>
              <div>
                <label class="form-label text-xs fw-bold text-secondary mb-1">To</label>
                <input type="date" v-model="activityTo" class="form-control form-control-sm" style="max-width:170px">
              </div>
              <button class="btn btn-primary btn-sm" @click="fetchRaterActivity" :disabled="activityLoading">
                <i class="bi bi-calendar-check me-1"></i>{{ activityLoading ? 'Loading...' : 'Apply' }}
              </button>
              <div class="btn-group btn-group-sm" role="group">
                <button class="btn btn-outline-secondary" @click="setActivityPreset(0)">Today</button>
                <button class="btn btn-outline-secondary" @click="setActivityPreset(7)">7 days</button>
                <button class="btn btn-outline-secondary" @click="setActivityPreset(30)">30 days</button>
                <button class="btn btn-outline-secondary" @click="clearActivity">All time</button>
              </div>
              <div v-if="raterActivity" class="ms-auto d-flex flex-wrap gap-2 align-items-center">
                <span class="badge bg-primary-subtle text-primary border py-2 px-2">{{ raterActivity.totals.completed_tasks }} tasks</span>
                <span class="badge bg-info-subtle text-info-emphasis border py-2 px-2">{{ raterActivity.totals.hours }} h</span>
                <span class="badge bg-light text-secondary border py-2 px-2">{{ raterActivity.totals.active_raters }} active</span>
              </div>
            </div>
          </div>

          <div class="table-responsive">
            <table class="table table-hover align-middle mb-0">
              <thead class="table-light">
                <tr>
                  <th class="ps-3 sortable-th" @click="sortRaters('name')">Annotator <i :class="['bi', sortIcon(raterSort, 'name')]"></i></th>
                  <th style="width: 85px;">Demog.</th>
                  <th class="sortable-th" style="width: 190px;" @click="sortRaters('assigned')">Assigned <i :class="['bi', sortIcon(raterSort, 'assigned')]"></i></th>
                  <th class="sortable-th" style="width: 125px;" @click="sortRaters('lastactive')">Last Active <i :class="['bi', sortIcon(raterSort, 'lastactive')]"></i></th>
                  <th style="width: 120px;">Status</th>
                  <th class="sortable-th text-end text-nowrap" style="width: 120px;" @click="sortRaters('completed')">
                    <span v-if="raterActivity">In period / All</span><span v-else>Tasks done</span>
                    <i :class="['bi', sortIcon(raterSort, 'completed')]"></i>
                  </th>
                  <th class="text-end pe-3" style="width: 210px;">Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="rater in filteredRaters" :key="rater.id" :class="{ 'stale-row': isStale(rater) }">
                  <td class="ps-3">
                    <div class="d-flex align-items-center gap-2" style="min-width: 0;">
                      <div class="avatar-circle flex-shrink-0">{{ rater.name.charAt(0).toUpperCase() }}</div>
                      <div style="min-width: 0;">
                        <div class="fw-semibold text-dark text-truncate" style="max-width: 200px;" :title="rater.name">{{ rater.name }}</div>
                        <div class="text-muted text-xs text-truncate" style="max-width: 200px;" :title="rater.email">{{ rater.email }}</div>
                      </div>
                    </div>
                  </td>
                  <td>
                    <div class="text-xs">
                      <span class="text-dark">{{ rater.gender }}</span>, <span class="text-muted">{{ rater.age }}y</span>
                    </div>
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
                  <td class="text-end tasks-cell">
                    <template v-if="raterActivity">
                      <span class="badge bg-primary-subtle text-primary border px-2"
                            :title="'Tasks completed in the selected period'">{{ periodFor(rater.id) ? periodFor(rater.id).completed_tasks : 0 }}</span>
                      <span class="text-muted mx-1">/</span>
                      <span class="text-secondary" :title="'All-time tasks completed'">{{ rater.completed_tasks_count }}</span>
                    </template>
                    <span v-else class="badge bg-light text-dark border px-2">{{ rater.completed_tasks_count }}</span>
                  </td>
                  <td class="text-end pe-3">
                    <div class="d-inline-flex gap-2 justify-content-end align-items-center rater-actions">
                      <!-- 1. Assign Tasks (Primary) -->
                      <button
                        class="rater-action-btn"
                        :class="assignedIdList(rater).length ? 'btn btn-sm btn-primary' : 'btn btn-sm btn-outline-primary'"
                        @click="openAssignModal(rater)"
                        :title="assignedIdList(rater).length ? 'Edit assigned tasks for ' + rater.name : 'Assign tasks to ' + rater.name"
                      >
                        <i :class="['bi', assignedIdList(rater).length ? 'bi-pencil-square' : 'bi-plus-lg']"></i>
                      </button>

                      <!-- 2. Ratings Export -->
                      <button
                        class="rater-action-btn btn btn-sm btn-outline-primary"
                        @click="openRatingsModal(rater)"
                        :title="'Export raw task rating submissions for ' + rater.name"
                      >
                        <i class="bi bi-file-earmark-code"></i>
                      </button>

                      <!-- 3. Annotator Data Export (Timeline picker, default Entire Life) -->
                      <button
                        class="rater-action-btn btn btn-sm btn-success text-white border-0"
                        @click="openAnnotatorDataModal(rater)"
                        :title="'Export annotator metrics, tasks done & working task ID for ' + rater.name + ' (Timeline: Entire Life default)'"
                      >
                        <i class="bi bi-calendar-range"></i>
                      </button>

                      <!-- 4. Message Annotator -->
                      <button
                        class="rater-action-btn btn btn-sm btn-outline-secondary position-relative"
                        @click="openMessageModal(rater)"
                        :title="'Send a direct message to ' + rater.name"
                      >
                        <i class="bi bi-chat-dots"></i>
                        <span v-if="rater.messages_sent" class="rater-msg-badge">{{ rater.messages_sent }}</span>
                      </button>

                      <!-- 5. Nudge (only for stale annotators) -->
                      <button
                        v-if="isStale(rater)"
                        class="rater-action-btn btn btn-sm btn-outline-warning"
                        @click="nudgeRater(rater)"
                        :title="'Send task reminder nudge to ' + rater.name"
                      >
                        <i class="bi bi-bell"></i>
                      </button>

                      <!-- 6. Deactivate / Reactivate -->
                      <button
                        v-if="rater.account_active === false"
                        class="rater-action-btn btn btn-sm btn-success"
                        @click="reactivateRater(rater)"
                        :title="'Reactivate ' + rater.name + ' (restores previous task locks)'"
                      >
                        <i class="bi bi-arrow-counterclockwise"></i>
                      </button>
                      <button
                        v-else
                        class="rater-action-btn btn btn-sm btn-outline-danger"
                        @click="openRemoveModal(rater)"
                        :title="'Deactivate ' + rater.name + ' (unlocks assigned tasks)'"
                      >
                        <i class="bi bi-person-dash"></i>
                      </button>
                    </div>
                  </td>
                </tr>
                <tr v-if="filteredRaters.length === 0">
                  <td colspan="7" class="text-center text-muted py-5 bg-white">
                    No matching raters found.
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- QUALITY TAB -->
      <div v-if="activeTab === 'quality'">
        <!-- Voice-artist QC: rejection rate per artist + reason breakdown (vendor-shareable) -->
        <div class="bg-white p-4 rounded shadow-sm border mb-4">
          <div class="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-3">
            <div>
              <h3 class="fw-bold text-dark m-0 fs-5"><i class="bi bi-mic text-primary me-2"></i>Voice Artist QC</h3>
              <div class="text-muted text-xs">Audio-segmentation rejection rate per artist, what is still pending review, and why clips were rejected.</div>
            </div>
            <div class="d-flex flex-wrap gap-2 align-items-center">
              <!-- Language filter: narrows every number and every export below. -->
              <div class="d-flex align-items-center gap-1">
                <i class="bi bi-translate text-muted"></i>
                <select v-model="qualityLanguage" class="form-select form-select-sm w-auto">
                  <option value="">All languages</option>
                  <option v-for="l in qualityLanguageOptions" :key="l" :value="l">{{ l }}</option>
                </select>
              </div>
              <button class="btn btn-outline-success btn-sm" @click="downloadArtistReport">
                <i class="bi bi-file-earmark-spreadsheet me-1"></i>Export for vendor (CSV)
              </button>
              <button class="btn btn-outline-secondary btn-sm" @click="downloadAudioClips(true)">
                <i class="bi bi-play-circle me-1"></i>Rejected clips + links
              </button>
              <button class="btn btn-outline-primary btn-sm" @click="downloadAudioClips(false)">
                <i class="bi bi-list-ul me-1"></i>All clips + links
              </button>
            </div>
          </div>

          <!-- Review progress for the current language selection -->
          <div v-if="artistStats.artists.length" class="row g-2 mb-3">
            <div class="col-6 col-md-3">
              <div class="border rounded-3 p-2 h-100 bg-light">
                <div class="text-muted text-xs text-uppercase fw-bold">Total clips</div>
                <div class="fs-5 fw-bold text-dark">{{ artistStats.overall.clips || 0 }}</div>
              </div>
            </div>
            <div class="col-6 col-md-3">
              <div class="border rounded-3 p-2 h-100 bg-light">
                <div class="text-muted text-xs text-uppercase fw-bold">Reviewed</div>
                <div class="fs-5 fw-bold text-dark">{{ artistStats.overall.total || 0 }}</div>
              </div>
            </div>
            <div class="col-6 col-md-3">
              <div class="border rounded-3 p-2 h-100 bg-warning-subtle">
                <div class="text-muted text-xs text-uppercase fw-bold">Pending review</div>
                <div class="fs-5 fw-bold text-warning-emphasis">{{ artistStats.overall.pending || 0 }}</div>
              </div>
            </div>
            <div class="col-6 col-md-3">
              <div class="border rounded-3 p-2 h-100 bg-light">
                <div class="text-muted text-xs text-uppercase fw-bold">Review progress</div>
                <div class="fs-5 fw-bold text-dark">{{ artistStats.overall.reviewed_rate || 0 }}%</div>
                <div class="progress mt-1" style="height:5px">
                  <div class="progress-bar bg-success" :style="{ width: (artistStats.overall.reviewed_rate || 0) + '%' }"></div>
                </div>
              </div>
            </div>
          </div>

          <div v-if="!artistStats.artists || !artistStats.artists.length" class="text-muted text-center py-3">
            {{ qualityLanguage ? 'No audio-segmentation batches for ' + qualityLanguage + '.' : 'No audio-segmentation submissions yet.' }}
          </div>

          <div v-else class="row g-4">
            <!-- per artist -->
            <div class="col-12 col-lg-6">
              <h6 class="fw-bold text-secondary text-xs text-uppercase mb-2">Rejection rate per artist</h6>
              <div class="table-responsive">
                <table class="table table-sm align-middle mb-0">
                  <thead class="table-light">
                    <tr>
                      <th class="text-xs">Artist</th>
                      <th class="text-xs text-end">Clips</th>
                      <th class="text-xs text-end">Reviewed</th>
                      <th class="text-xs text-end">Accepted</th>
                      <th class="text-xs text-end">Rejected</th>
                      <th class="text-xs text-end">Pending</th>
                      <th class="text-xs text-end">Rejection %</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="a in artistStats.artists" :key="a.artist"
                        :class="{ 'table-warning': a.rejection_rate >= 10 }">
                      <td class="fw-semibold text-dark text-xs">
                        {{ a.artist }}
                        <span class="text-muted">({{ a.batch_count }} batch{{ a.batch_count === 1 ? '' : 'es' }})</span>
                      </td>
                      <td class="text-end text-xs text-muted">{{ a.clips }}</td>
                      <td class="text-end text-xs">{{ a.total }}</td>
                      <td class="text-end text-xs text-success">{{ a.accepted }}</td>
                      <td class="text-end text-xs text-danger">{{ a.rejected }}</td>
                      <td class="text-end text-xs" :class="a.pending ? 'text-warning-emphasis fw-semibold' : 'text-muted'"
                          :title="a.pending + ' of ' + a.clips + ' clips still awaiting review'">
                        {{ a.pending }}
                      </td>
                      <td class="text-end fw-bold text-xs">{{ a.rejection_rate }}%</td>
                    </tr>
                    <tr class="border-top">
                      <td class="fw-bold text-xs">OVERALL</td>
                      <td class="text-end fw-bold text-xs text-muted">{{ artistStats.overall.clips }}</td>
                      <td class="text-end fw-bold text-xs">{{ artistStats.overall.total }}</td>
                      <td class="text-end fw-bold text-xs text-success">{{ artistStats.overall.accepted }}</td>
                      <td class="text-end fw-bold text-xs text-danger">{{ artistStats.overall.rejected }}</td>
                      <td class="text-end fw-bold text-xs text-warning-emphasis">{{ artistStats.overall.pending }}</td>
                      <td class="text-end fw-bold text-xs">{{ artistStats.overall.rejection_rate }}%</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <!-- reason breakdown -->
            <div class="col-12 col-lg-6">
              <div class="d-flex align-items-center gap-2 mb-2">
                <h6 class="fw-bold text-secondary text-xs text-uppercase mb-0">Rejection reasons</h6>
                <select v-model="artistReasonFilter" class="form-select form-select-sm w-auto ms-auto">
                  <option value="">All artists</option>
                  <option v-for="a in artistStats.artists" :key="a.artist" :value="a.artist">{{ a.artist }}</option>
                </select>
              </div>
              <div v-if="!activeReasons.length" class="text-muted text-xs py-2">No rejections recorded.</div>
              <div v-for="r in activeReasons" :key="r.reason" class="mb-2">
                <div class="d-flex justify-content-between text-xs">
                  <span class="text-dark">{{ r.label }}</span>
                  <span class="text-muted">{{ r.count }} &middot; <strong>{{ r.pct_of_rejections }}%</strong></span>
                </div>
                <div class="progress" style="height:6px">
                  <div class="progress-bar bg-danger" :style="{ width: r.pct_of_rejections + '%' }"></div>
                </div>
              </div>
              <div class="text-muted text-xs mt-2">% = share of that selection's rejected clips citing the reason (a clip can cite several).</div>
            </div>
          </div>

          <!-- Where the remaining review work sits, per language -->
          <div v-if="!qualityLanguage && languageStats.length > 1" class="mt-4 pt-3 border-top">
            <h6 class="fw-bold text-secondary text-xs text-uppercase mb-2">Pending review by language</h6>
            <div class="table-responsive">
              <table class="table table-sm align-middle mb-0">
                <thead class="table-light">
                  <tr>
                    <th class="text-xs">Language</th>
                    <th class="text-xs text-end">Clips</th>
                    <th class="text-xs text-end">Reviewed</th>
                    <th class="text-xs text-end">Pending</th>
                    <th class="text-xs" style="width:28%">Progress</th>
                    <th class="text-xs text-end">Rejection %</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="l in languageStats" :key="l.language">
                    <td class="fw-semibold text-dark text-xs">
                      <a href="#" class="text-decoration-none" @click.prevent="qualityLanguage = l.language">{{ l.language }}</a>
                    </td>
                    <td class="text-end text-xs text-muted">{{ l.clips }}</td>
                    <td class="text-end text-xs">{{ l.total }}</td>
                    <td class="text-end text-xs" :class="l.pending ? 'text-warning-emphasis fw-semibold' : 'text-muted'">{{ l.pending }}</td>
                    <td>
                      <div class="progress" style="height:6px">
                        <div class="progress-bar bg-success" :style="{ width: l.reviewed_rate + '%' }"></div>
                      </div>
                      <span class="text-muted text-xs">{{ l.reviewed_rate }}% reviewed</span>
                    </td>
                    <td class="text-end fw-bold text-xs">{{ l.rejection_rate }}%</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <!-- =====================================================================
             Clips still carrying a rejection reason the UI no longer offers.
             The reason cannot be un-picked from a report, only re-annotated, so
             each row links straight to that clip.
             ===================================================================== -->
        <div v-if="retiredClips.total" class="bg-white p-4 rounded shadow-sm border border-warning-subtle mb-4">
          <div class="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-3">
            <div>
              <h3 class="fw-bold text-dark m-0 fs-5">
                <i class="bi bi-exclamation-triangle-fill text-warning me-2"></i>Retired rejection reasons
                <span class="badge rounded-pill bg-warning text-dark ms-1">{{ retiredClips.total }}</span>
              </h3>
              <div class="text-muted text-xs">
                These clips were rejected with a reason that is no longer offered
                ({{ retiredClips.by_reason.map(r => r.label + ' × ' + r.count).join(', ') }}).
                Open each one, uncheck the retired reason and pick a current one — the
                row disappears once it is re-submitted.
              </div>
            </div>
            <button class="btn btn-outline-secondary btn-sm" @click="copyRetiredList">
              <i class="bi bi-clipboard me-1"></i>{{ retiredCopied ? 'Copied!' : 'Copy list for annotator' }}
            </button>
          </div>

          <div class="table-responsive">
            <table class="table table-sm align-middle mb-0">
              <thead class="table-light">
                <tr>
                  <th class="text-xs">Annotator</th>
                  <th class="text-xs">Batch</th>
                  <th class="text-xs">Clip</th>
                  <th class="text-xs">Retired reason</th>
                  <th class="text-xs">What they wrote</th>
                  <th class="text-xs text-end">Submitted</th>
                  <th class="text-xs text-end"></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="c in retiredClips.clips" :key="c.rating_id">
                  <td class="fw-semibold text-dark text-xs">{{ c.rater_name }}</td>
                  <td class="text-xs">
                    <span class="text-dark">#{{ c.test_id }}</span>
                    <div class="text-muted" style="font-size:0.72rem">{{ c.persona }}</div>
                  </td>
                  <td class="text-xs font-monospace text-secondary">{{ c.clip_id }}</td>
                  <td class="text-xs">
                    <span v-for="s in c.retired_reasons" :key="s"
                          class="badge bg-warning-subtle text-warning-emphasis border border-warning-subtle me-1">
                      {{ s }}
                    </span>
                  </td>
                  <td class="text-xs text-secondary" style="max-width:340px">
                    <div class="text-truncate" :title="c.custom_reason || c.comments">
                      {{ c.custom_reason || c.comments || '—' }}
                    </div>
                  </td>
                  <td class="text-end text-xs text-muted">{{ formatDate(c.submitted) }}</td>
                  <td class="text-end">
                    <a :href="c.link" target="_blank" rel="noopener"
                       class="btn btn-sm btn-outline-primary py-0 px-2 text-xs">
                      Open <i class="bi bi-box-arrow-up-right"></i>
                    </a>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- =====================================================================
             Annotation hours — audio segmentation only. How much AUDIO each
             annotator has reviewed: cumulative to date and per IST day.
             ===================================================================== -->
        <div class="bg-white p-4 rounded shadow-sm border mb-4">
          <div class="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-3">
            <div>
              <h3 class="fw-bold text-dark m-0 fs-5"><i class="bi bi-hourglass-split text-primary me-2"></i>Annotation Hours</h3>
              <div class="text-muted text-xs">
                Audio reviewed per annotator on audio-segmentation batches — cumulative to date and day by day.
                Days are counted in {{ audioHours.timezone }}; skipped clips are excluded.
              </div>
            </div>
            <div class="d-flex flex-wrap gap-2 align-items-center">
              <div class="btn-group btn-group-sm" role="group" aria-label="Hours range">
                <button
                  v-for="r in hoursRanges"
                  :key="r.days"
                  type="button"
                  class="btn"
                  :class="hoursRange === r.days ? 'btn-primary' : 'btn-outline-primary'"
                  @click="hoursRange = r.days"
                >{{ r.label }}</button>
              </div>
              <button class="btn btn-outline-success btn-sm" @click="downloadAudioHours">
                <i class="bi bi-file-earmark-spreadsheet me-1"></i>Export hours (CSV)
              </button>
            </div>
          </div>

          <div v-if="!audioHours.annotators.length && !audioHours.by_artist.length"
               class="text-muted text-center py-3">
            No audio-segmentation work recorded yet.
          </div>

          <template v-else>
            <!-- Headline numbers -->
            <div class="row g-2 mb-3">
              <div class="col-6 col-md-3">
                <div class="border rounded-3 p-2 h-100 bg-primary-subtle">
                  <div class="text-muted text-xs text-uppercase fw-bold">Total audio reviewed</div>
                  <div class="fs-5 fw-bold text-primary-emphasis">{{ audioHours.totals.label }}</div>
                  <div class="text-muted text-xs">{{ audioHours.totals.clips }} clips</div>
                </div>
              </div>
              <div class="col-6 col-md-3">
                <div class="border rounded-3 p-2 h-100 bg-light">
                  <div class="text-muted text-xs text-uppercase fw-bold">Today</div>
                  <div class="fs-5 fw-bold text-dark">{{ audioHours.today.label }}</div>
                  <div class="text-muted text-xs">{{ audioHours.today.clips }} clips</div>
                </div>
              </div>
              <div class="col-6 col-md-3">
                <div class="border rounded-3 p-2 h-100 bg-light">
                  <div class="text-muted text-xs text-uppercase fw-bold">Last 7 days</div>
                  <div class="fs-5 fw-bold text-dark">{{ audioHours.last_7_days.label }}</div>
                  <div class="text-muted text-xs">{{ audioHours.last_7_days.clips }} clips</div>
                </div>
              </div>
              <div class="col-6 col-md-3">
                <div class="border rounded-3 p-2 h-100 bg-light">
                  <div class="text-muted text-xs text-uppercase fw-bold">Working today</div>
                  <div class="fs-5 fw-bold text-dark">{{ audioHours.active_today }} / {{ audioHours.annotators.length }}</div>
                  <div class="text-muted text-xs">annotators active</div>
                </div>
              </div>
            </div>

            <!-- Team trend -->
            <div class="border rounded-3 p-3 mb-3">
              <div class="d-flex justify-content-between align-items-baseline mb-2">
                <h6 class="fw-bold text-secondary text-xs text-uppercase mb-0">Team output · last {{ hoursRange }} days</h6>
                <span class="text-muted text-xs">Peak {{ teamPeakLabel }}</span>
              </div>
              <div class="ah-chart">
                <div
                  v-for="d in teamSeries"
                  :key="d.date"
                  class="ah-chart-col"
                  :title="`${d.date} · ${d.label} · ${d.clips} clips`"
                >
                  <div class="ah-chart-track">
                    <div
                      class="ah-chart-bar"
                      :class="{ 'is-today': d.date === audioHours.today_date, 'is-empty': !d.seconds }"
                      :style="{ height: teamBarHeight(d) }"
                    ></div>
                  </div>
                  <span v-if="teamSeries.length <= 14" class="ah-chart-day">{{ shortDay(d.date) }}</span>
                </div>
              </div>
            </div>

            <!-- Hours by voice artist / persona: how much of the audio each ARTIST
                 recorded has been QC'd (vs. who did the reviewing, below). -->
            <div class="row g-4 mb-4">
              <div class="col-12 col-xl-7">
                <h6 class="fw-bold text-secondary text-xs text-uppercase mb-2">
                  Hours completed per voice artist
                </h6>
                <div class="table-responsive">
                  <table class="table table-sm align-middle mb-0">
                    <thead class="table-light">
                      <tr>
                        <th class="text-xs">Voice artist</th>
                        <th class="text-xs">Persona</th>
                        <th class="text-xs text-end">Total audio</th>
                        <th class="text-xs text-end">Hours completed</th>
                        <th class="text-xs text-end">Pending</th>
                        <th class="text-xs text-end">Today</th>
                        <th class="text-xs" style="width:18%">Progress</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="a in audioHours.by_artist" :key="a.artist">
                        <td class="fw-semibold text-dark text-xs">
                          {{ a.artist }}
                          <div class="text-muted fw-normal" style="font-size:0.72rem">
                            {{ a.batches }} batch{{ a.batches === 1 ? '' : 'es' }} · {{ a.total_clips }} clips
                          </div>
                        </td>
                        <td class="text-xs text-secondary">{{ a.personas.join(', ') || '—' }}</td>
                        <td class="text-end text-xs text-muted">{{ a.total_label }}</td>
                        <td class="text-end text-xs fw-bold text-dark">{{ a.label }}</td>
                        <td class="text-end text-xs" :class="a.pending_seconds ? 'text-warning-emphasis fw-semibold' : 'text-muted'">
                          {{ a.pending_seconds ? a.pending_label : '—' }}
                        </td>
                        <td class="text-end text-xs" :class="a.today_seconds ? 'text-success fw-semibold' : 'text-muted'">
                          {{ a.today_seconds ? a.today_label : '—' }}
                        </td>
                        <td>
                          <div class="progress" style="height:6px">
                            <div class="progress-bar bg-success" :style="{ width: a.progress + '%' }"></div>
                          </div>
                          <span class="text-muted text-xs">{{ a.progress }}%</span>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>

              <div class="col-12 col-xl-5">
                <h6 class="fw-bold text-secondary text-xs text-uppercase mb-2">
                  Hours completed per persona
                </h6>
                <div class="table-responsive">
                  <table class="table table-sm align-middle mb-0">
                    <thead class="table-light">
                      <tr>
                        <th class="text-xs">Persona</th>
                        <th class="text-xs text-end">Total</th>
                        <th class="text-xs text-end">Completed</th>
                        <th class="text-xs" style="width:26%">Progress</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="p in audioHours.by_persona" :key="p.persona">
                        <td class="fw-semibold text-dark text-xs">
                          {{ p.persona }}
                          <div class="text-muted fw-normal" style="font-size:0.72rem">
                            {{ p.artists.join(', ') || '—' }}
                          </div>
                        </td>
                        <td class="text-end text-xs text-muted">{{ p.total_label }}</td>
                        <td class="text-end text-xs fw-bold text-dark">{{ p.label }}</td>
                        <td>
                          <div class="progress" style="height:6px">
                            <div class="progress-bar bg-success" :style="{ width: p.progress + '%' }"></div>
                          </div>
                          <span class="text-muted text-xs">{{ p.progress }}%</span>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <div class="text-muted text-xs mt-2">
                  "Hours completed" = audio that has been QC'd at least once, counted
                  per recorded clip (never double-counted when two annotators review
                  the same clip).
                </div>
              </div>
            </div>

            <!-- Per annotator -->
            <h6 class="fw-bold text-secondary text-xs text-uppercase mb-2">Hours per annotator <span class="text-muted fw-normal text-lowercase">— who did the reviewing</span></h6>
            <div class="table-responsive">
              <table class="table table-sm align-middle mb-0">
                <thead class="table-light">
                  <tr>
                    <th class="text-xs">Annotator</th>
                    <th class="text-xs text-end">Clips</th>
                    <th class="text-xs text-end">Total audio</th>
                    <th class="text-xs text-end">Today</th>
                    <th class="text-xs text-end">Last 7 days</th>
                    <th class="text-xs text-end">Avg / active day</th>
                    <th class="text-xs" style="width: 18%">Share of total</th>
                    <th class="text-xs text-end">Last activity</th>
                    <th class="text-xs text-end"></th>
                  </tr>
                </thead>
                <tbody>
                  <template v-for="a in audioHours.annotators" :key="a.rater_id">
                    <tr :class="{ 'table-light': !a.is_active }">
                      <td class="fw-semibold text-dark text-xs">
                        {{ a.name }}
                        <span v-if="!a.is_active" class="badge bg-secondary-subtle text-secondary-emphasis ms-1">inactive</span>
                        <div class="text-muted fw-normal" style="font-size:0.72rem">
                          {{ a.email }} · {{ a.batches }} batch{{ a.batches === 1 ? '' : 'es' }}
                        </div>
                      </td>
                      <td class="text-end text-xs text-muted">{{ a.clips }}</td>
                      <td class="text-end text-xs fw-bold text-dark">{{ a.label }}</td>
                      <td class="text-end text-xs" :class="a.today.seconds ? 'text-success fw-semibold' : 'text-muted'">
                        {{ a.today.seconds ? a.today.label : '—' }}
                      </td>
                      <td class="text-end text-xs">{{ a.last_7_days.seconds ? a.last_7_days.label : '—' }}</td>
                      <td class="text-end text-xs text-muted">{{ a.avg_per_active_day.label }}</td>
                      <td>
                        <div class="progress" style="height:6px">
                          <div class="progress-bar bg-primary" :style="{ width: hoursShare(a) + '%' }"></div>
                        </div>
                        <span class="text-muted text-xs">{{ hoursShare(a) }}%</span>
                      </td>
                      <td class="text-end text-xs text-muted" :title="formatDate(a.last_activity)">{{ timeAgo(a.last_activity) }}</td>
                      <td class="text-end">
                        <button
                          class="btn btn-sm btn-link p-0 text-decoration-none text-xs"
                          @click="toggleHoursRow(a.rater_id)"
                        >
                          {{ expandedHours === a.rater_id ? 'Hide' : 'Daily' }}
                          <i class="bi" :class="expandedHours === a.rater_id ? 'bi-chevron-up' : 'bi-chevron-down'"></i>
                        </button>
                      </td>
                    </tr>

                    <!-- Per-day detail for one annotator -->
                    <tr v-if="expandedHours === a.rater_id">
                      <td colspan="9" class="bg-light-subtle">
                        <div class="p-2">
                          <div class="fw-bold text-secondary text-xs text-uppercase mb-2">
                            {{ a.name }} · daily audio ({{ hoursRange }} days)
                          </div>
                          <div v-if="!workedDays(a).length" class="text-muted text-xs">
                            No clips reviewed in this window.
                          </div>
                          <div v-else class="table-responsive ah-scroll">
                            <table class="table table-sm mb-0">
                              <thead>
                                <tr>
                                  <th class="text-xs">Date</th>
                                  <th class="text-xs text-end">Clips</th>
                                  <th class="text-xs text-end">Audio</th>
                                  <th class="text-xs" style="width:45%"></th>
                                </tr>
                              </thead>
                              <tbody>
                                <tr v-for="d in workedDays(a)" :key="d.date">
                                  <td class="text-xs fw-semibold text-dark">
                                    {{ longDay(d.date) }}
                                    <span v-if="d.date === audioHours.today_date" class="badge bg-success-subtle text-success-emphasis ms-1">Today</span>
                                  </td>
                                  <td class="text-end text-xs text-muted">{{ d.clips }}</td>
                                  <td class="text-end text-xs fw-bold text-dark">{{ d.label }}</td>
                                  <td>
                                    <div class="progress" style="height:6px">
                                      <div class="progress-bar bg-primary"
                                           :style="{ width: dayShareOf(d, a) + '%' }"></div>
                                    </div>
                                  </td>
                                </tr>
                              </tbody>
                            </table>
                          </div>
                        </div>
                      </td>
                    </tr>
                  </template>

                  <tr class="border-top">
                    <td class="fw-bold text-xs">OVERALL</td>
                    <td class="text-end fw-bold text-xs text-muted">{{ audioHours.totals.clips }}</td>
                    <td class="text-end fw-bold text-xs">{{ audioHours.totals.label }}</td>
                    <td class="text-end fw-bold text-xs">{{ audioHours.today.label }}</td>
                    <td class="text-end fw-bold text-xs">{{ audioHours.last_7_days.label }}</td>
                    <td colspan="4"></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </template>
        </div>

      </div>

      <!-- ADMIN TAB -->
      <div v-if="activeTab === 'admin'">
        <!-- Daily signup PIN: share this with people who should be able to sign up -->
        <div class="bg-white p-3 rounded shadow-sm border mb-4 d-flex flex-wrap align-items-center gap-3">
          <div>
            <h5 class="fw-bold text-dark m-0"><i class="bi bi-shield-lock text-primary me-2"></i>Today's Signup PIN</h5>
            <div class="text-muted text-xs">New annotators must enter this 8-digit PIN to sign up. It changes daily{{ signupPinDate ? ' (' + signupPinDate + ')' : '' }}.</div>
          </div>
          <div class="ms-auto d-flex align-items-center gap-2">
            <code class="fs-4 fw-bold text-dark bg-light border rounded px-3 py-1" style="letter-spacing:.25em">{{ signupPin || '--------' }}</code>
            <button class="btn btn-outline-secondary btn-sm" @click="copySignupPin" :disabled="!signupPin">
              <i class="bi bi-clipboard me-1"></i>{{ signupPinCopied ? 'Copied' : 'Copy' }}
            </button>
            <button class="btn btn-outline-primary btn-sm" @click="fetchSignupPin"><i class="bi bi-arrow-clockwise"></i></button>
          </div>
        </div>

        <!-- Export task list (filter by version) -->
        <div class="bg-white p-4 rounded shadow-sm border mb-4">
          <div class="d-flex flex-wrap justify-content-between align-items-end gap-3">
            <div>
              <h3 class="fw-bold text-dark m-0 fs-5"><i class="bi bi-table text-primary me-2"></i>Export Task List</h3>
              <div class="text-muted text-xs">Sr. No., Language, Task ID, Detail and No. of Tasks &mdash; as a CSV you can open in Excel.</div>
            </div>
            <div class="d-flex flex-wrap gap-2 align-items-end">
              <div>
                <label class="form-label text-xs fw-bold text-secondary mb-1">Task type</label>
                <select v-model="exportTestType" class="form-select form-select-sm">
                  <option value="conversation-editable">Conversation Editable</option>
                  <option value="audio-segmentation">Audio Segmentation</option>
                  <option value="">All types</option>
                </select>
              </div>
              <div>
                <label class="form-label text-xs fw-bold text-secondary mb-1">Version</label>
                <select v-model="exportVersion" class="form-select form-select-sm">
                  <option value="">All versions</option>
                  <option v-for="v in exportVersionOptions" :key="v" :value="v">{{ v === 'new' ? 'New Version' : (v === 'base' ? 'Base' : 'Version ' + v) }}</option>
                </select>
              </div>
              <button class="btn btn-primary btn-sm" @click="downloadTasksExport">
                <i class="bi bi-download me-1"></i>Export CSV
              </button>
            </div>
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

    <!-- ===================== ANNOTATOR DATA MODAL ===================== -->
    <transition name="modal-fade">
      <div v-if="showAnnotatorDataModal" class="assign-modal-backdrop" @click.self="closeAnnotatorDataModal">
        <div class="assign-modal-card shadow-lg border-0 rounded-4" style="max-width: 580px; width: 100%;">
          <!-- Header -->
          <div class="assign-modal-header d-flex justify-content-between align-items-center bg-success-subtle py-3 px-4 rounded-top-4 border-bottom border-success-subtle">
            <div class="d-flex align-items-center gap-2.5" v-if="selectedRater">
              <div class="avatar-circle flex-shrink-0 bg-success text-white fw-bold" style="width: 38px; height: 38px; font-size: 1rem;">
                {{ (selectedRater.name || '?').charAt(0).toUpperCase() }}
              </div>
              <div style="min-width: 0;">
                <h6 class="fw-bold mb-0 text-dark text-truncate" style="max-width: 420px;">{{ selectedRater.name }}</h6>
                <div class="text-xs text-muted text-truncate" style="max-width: 420px;">Rater ID #{{ selectedRater.id }} &bull; {{ selectedRater.email }}</div>
              </div>
            </div>
            <div class="d-flex align-items-center gap-2.5" v-else>
              <div class="avatar-circle bg-success text-white flex-shrink-0" style="width: 38px; height: 38px; font-size: 1.1rem;">
                <i class="bi bi-people-fill"></i>
              </div>
              <div>
                <h6 class="fw-bold mb-0 text-dark">Export Annotators Data</h6>
                <div class="text-xs text-muted">All registered annotators performance & metrics report</div>
              </div>
            </div>
            <button class="btn-close" @click="closeAnnotatorDataModal"></button>
          </div>

          <!-- Body -->
          <div class="assign-modal-body p-4">
            <!-- Timeline Selector Card -->
            <div class="card p-3.5 mb-3.5 border-0 bg-light rounded-3">
              <div class="d-flex justify-content-between align-items-center mb-3">
                <label class="form-label text-xs fw-bold text-uppercase text-secondary mb-0 d-flex align-items-center gap-1.5">
                  <i class="bi bi-clock-history text-success"></i> Timeline Duration
                </label>
                <span class="badge bg-success-subtle text-success border border-success-subtle px-2.5 py-1 text-xs rounded-pill">
                  {{ activePreset === 'all' ? 'Entire Life (Default)' : activePreset === 'today' ? 'Today' : activePreset === '7days' ? 'Last 7 Days' : 'Last 30 Days' }}
                </span>
              </div>

              <!-- Quick Presets -->
              <div class="btn-group btn-group-sm w-100 mb-3" role="group">
                <button 
                  class="btn py-1.5 px-3 text-xs" 
                  :class="activePreset === 'all' ? 'btn-success text-white fw-semibold' : 'btn-outline-secondary'"
                  @click="setTimelinePreset('all')"
                >
                  <i class="bi bi-infinity me-1"></i> Entire Life
                </button>
                <button 
                  class="btn py-1.5 px-3 text-xs" 
                  :class="activePreset === 'today' ? 'btn-success text-white fw-semibold' : 'btn-outline-secondary'"
                  @click="setTimelinePreset('today')"
                >
                  Today
                </button>
                <button 
                  class="btn py-1.5 px-3 text-xs" 
                  :class="activePreset === '7days' ? 'btn-success text-white fw-semibold' : 'btn-outline-secondary'"
                  @click="setTimelinePreset('7days')"
                >
                  Last 7 Days
                </button>
                <button 
                  class="btn py-1.5 px-3 text-xs" 
                  :class="activePreset === '30days' ? 'btn-success text-white fw-semibold' : 'btn-outline-secondary'"
                  @click="setTimelinePreset('30days')"
                >
                  Last 30 Days
                </button>
              </div>

              <!-- Custom Date Inputs -->
              <div class="row g-3">
                <div class="col-6">
                  <label class="form-label text-xs text-muted mb-1">From Date</label>
                  <input type="date" v-model="timelineFrom" @change="activePreset = 'custom'" class="form-control form-control-sm bg-white" />
                </div>
                <div class="col-6">
                  <label class="form-label text-xs text-muted mb-1">To Date</label>
                  <input type="date" v-model="timelineTo" @change="activePreset = 'custom'" class="form-control form-control-sm bg-white" />
                </div>
              </div>
            </div>

            <!-- Export Information Note -->
            <div class="text-xs text-muted mb-4 px-1">
              <i class="bi bi-info-circle text-primary me-1"></i> Includes tasks done, current pending task ID, working task ID, assigned batches & time spent.
            </div>

            <!-- Export Button -->
            <button 
              class="btn btn-success w-100 py-2.5 shadow-2xs d-flex align-items-center justify-content-center gap-2 fw-semibold text-sm rounded-3 border-0"
              @click="exportAnnotatorDataCSV"
            >
              <i class="bi bi-file-earmark-spreadsheet-fill fs-5"></i>
              <span>Export Annotator Data (CSV)</span>
            </button>
          </div>

          <!-- Footer -->
          <div class="assign-modal-footer d-flex justify-content-end py-3 px-4 border-top bg-light-subtle rounded-bottom-4">
            <button class="btn btn-outline-secondary btn-sm px-4 text-xs" @click="closeAnnotatorDataModal">Close</button>
          </div>
        </div>
      </div>
    </transition>

    <!-- ===================== RATINGS EXPORT MODAL ===================== -->
    <transition name="modal-fade">
      <div v-if="showRatingsModal" class="assign-modal-backdrop" @click.self="closeRatingsModal">
        <div class="assign-modal-card shadow-lg border-0 rounded-4" style="max-width: 580px; width: 100%;">
          <!-- Header -->
          <div class="assign-modal-header d-flex justify-content-between align-items-center bg-primary-subtle py-3 px-4 rounded-top-4 border-bottom border-primary-subtle">
            <div class="d-flex align-items-center gap-2.5" v-if="selectedRater">
              <div class="avatar-circle flex-shrink-0 bg-primary text-white fw-bold" style="width: 38px; height: 38px; font-size: 1rem;">
                {{ (selectedRater.name || '?').charAt(0).toUpperCase() }}
              </div>
              <div style="min-width: 0;">
                <h6 class="fw-bold mb-0 text-dark text-truncate" style="max-width: 420px;">{{ selectedRater.name }}</h6>
                <div class="text-xs text-muted text-truncate" style="max-width: 420px;">Rater ID #{{ selectedRater.id }} &bull; {{ selectedRater.email }}</div>
              </div>
            </div>
            <div class="d-flex align-items-center gap-2.5" v-else>
              <div class="avatar-circle bg-primary text-white flex-shrink-0" style="width: 38px; height: 38px; font-size: 1.1rem;">
                <i class="bi bi-file-earmark-code"></i>
              </div>
              <div>
                <h6 class="fw-bold mb-0 text-dark">Export Task Ratings</h6>
                <div class="text-xs text-muted">Raw submission ratings report</div>
              </div>
            </div>
            <button class="btn-close" @click="closeRatingsModal"></button>
          </div>

          <!-- Body -->
          <div class="assign-modal-body p-4">
            <p class="text-xs text-muted mb-4">
              Export raw line-by-line task rating submissions {{ selectedRater ? 'done by ' + selectedRater.name : 'across all annotators' }}.
            </p>
            <div class="form-group mb-4" v-if="selectedRater">
              <label class="form-label text-xs fw-bold text-secondary mb-1.5">Select Assigned Task Batch (Optional)</label>
              <select v-model="selectedExportTaskId" class="form-select form-select-sm bg-white">
                <option value="">-- All Assigned Batches --</option>
                <option v-for="tid in exportableTaskIds" :key="tid" :value="tid">
                  Task #{{ tid }} - {{ getTaskDescription(tid) }}
                </option>
              </select>
            </div>
            
            <button 
              class="btn btn-primary w-100 py-2.5 shadow-2xs d-flex align-items-center justify-content-center gap-2 fw-semibold text-sm rounded-3 border-0"
              @click="exportRatingsCSV"
            >
              <i class="bi bi-download fs-5"></i>
              <span>Export Raw Ratings (CSV)</span>
            </button>
          </div>

          <!-- Footer -->
          <div class="assign-modal-footer d-flex justify-content-end py-3 px-4 border-top bg-light-subtle rounded-bottom-4">
            <button class="btn btn-outline-secondary btn-sm px-4 text-xs" @click="closeRatingsModal">Close</button>
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
            <!-- Full history with this annotator, stacked like a chat -->
            <div v-if="threadLoading" class="text-center text-muted py-3">
              <span class="spinner-border spinner-border-sm me-2"></span>Loading history…
            </div>
            <div v-else-if="threadItems.length" ref="threadBox" class="msg-thread mb-3">
              <div
                v-for="item in threadItems"
                :key="item.kind === 'broadcast' ? 'b-' + item.broadcast_id : 'm-' + item.id"
                class="msg-bubble"
                :class="{ broadcast: item.kind === 'broadcast' }"
              >
                <div class="d-flex justify-content-between align-items-center gap-2 mb-1">
                  <span class="d-inline-flex align-items-center gap-2 flex-wrap">
                    <span v-if="item.kind === 'broadcast'" class="badge rounded-pill bg-primary-subtle text-primary"><i class="bi bi-broadcast me-1"></i>Broadcast</span>
                    <span v-else-if="item.category === 'nudge'" class="badge rounded-pill bg-warning-subtle text-warning-emphasis"><i class="bi bi-bell me-1"></i>Nudge</span>
                    <span v-else class="badge rounded-pill bg-secondary-subtle text-secondary"><i class="bi bi-chat-dots me-1"></i>Message</span>
                    <span v-if="item.kind === 'broadcast'" class="fs-9 text-muted">{{ item.recipients_read }}/{{ item.recipients_total }} read</span>
                    <span v-else class="fs-9" :class="item.is_read ? 'text-success' : 'text-muted'">
                      <i :class="['bi', item.is_read ? 'bi-check2-all' : 'bi-check2']"></i> {{ item.is_read ? 'Read' : 'Unread' }}
                    </span>
                  </span>
                  <button class="btn btn-link btn-sm p-0 text-secondary" title="Edit this message" @click="openEditMsg(item)"><i class="bi bi-pencil"></i></button>
                </div>
                <div class="small text-dark" style="white-space: pre-wrap; word-break: break-word;">{{ item.body }}</div>
                <div class="text-muted fs-9 mt-1">{{ formatDate(item.created_at) }}<span v-if="item.edited_at"> · edited {{ formatDate(item.edited_at) }}</span></div>
              </div>
            </div>
            <div v-else class="text-center text-muted small py-2 mb-2">
              <i class="bi bi-chat-square-text d-block fs-4 mb-1 opacity-50"></i>
              No previous messages with this annotator.
            </div>

            <label class="form-label fw-semibold text-dark small mb-1">New message</label>
            <textarea v-model="messageBody" class="form-control" rows="3" maxlength="2000" placeholder="Write your message… (they see it in their in-app inbox)"></textarea>
            <div class="text-end text-muted fs-9 mt-1">{{ messageBody.length }}/2000</div>
            <div v-if="messageError" class="text-danger small mt-1"><i class="bi bi-exclamation-triangle-fill me-1"></i>{{ messageError }}</div>
          </div>
          <div class="assign-modal-footer d-flex justify-content-end gap-2">
            <button class="btn btn-light border btn-sm" @click="closeMessageModal" :disabled="isSendingMsg">Close</button>
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
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { API_BASE_URL } from '@/config'
import router from '@/router'

// State
const activeTab = ref('overview')
// Sub-tab within the Tasks tab: 'overview' (progress by type) | 'alltasks' (batch list)
const tasksSubTab = ref('overview')
// Tab bar: labels reflect the content that actually lives under each pane.
const tabs = [
  { key: 'overview',   label: 'Overview',   icon: 'bi-grid-1x2-fill',      hint: 'Key numbers, batch health & language stats' },
  { key: 'tasks',      label: 'Tasks',      icon: 'bi-list-check',         hint: 'Progress by task type + the full batch list' },
  { key: 'annotators', label: 'Annotators', icon: 'bi-people-fill',        hint: 'Assign tasks, message & manage annotators' },
  { key: 'quality',    label: 'Quality',    icon: 'bi-patch-check-fill',   hint: 'Voice-artist QC & rejection analytics' },
  { key: 'admin',      label: 'Admin',      icon: 'bi-gear-fill',          hint: 'Signup PIN and task-list export' },
]
const dashboardData = ref({})
// --- Annotator work in a date period (backed by /api/admin/rater_activity) ---
const activityFrom = ref('')
const activityTo = ref('')
const raterActivity = ref(null)
const activityLoading = ref(false)

function periodFor(raterId) {
  if (!raterActivity.value) return null
  return raterActivity.value.raters.find(r => r.rater_id === raterId) || null
}

function setActivityPreset(daysBack) {
  const today = new Date()
  const start = new Date()
  start.setDate(today.getDate() - daysBack)
  const fmt = d => d.toISOString().slice(0, 10)
  activityFrom.value = fmt(start)
  activityTo.value = fmt(today)
  fetchRaterActivity()
}

function clearActivity() {
  activityFrom.value = ''
  activityTo.value = ''
  raterActivity.value = null
}

async function fetchRaterActivity() {
  activityLoading.value = true
  try {
    const token = localStorage.getItem('authToken')
    const params = new URLSearchParams()
    if (activityFrom.value) params.set('from', activityFrom.value)
    if (activityTo.value) params.set('to', activityTo.value)
    const qs = params.toString()
    const resp = await fetch(`${API_BASE_URL}/admin/rater_activity${qs ? '?' + qs : ''}`, {
      headers: { 'Authorization': `Bearer ${token}` }
    })
    if (!resp.ok) { alert('Could not load activity (' + resp.status + ')'); return }
    raterActivity.value = await resp.json()
  } catch (e) {
    console.error('rater activity failed', e)
  } finally {
    activityLoading.value = false
  }
}
const artistReasonFilter = ref('')
// Quality tab language filter — drives the tables, the stats and the CSV exports.
const qualityLanguage = ref('')
const exportTestType = ref('conversation-editable')
const exportVersion = ref('')
const exportVersionOptions = ['2', '3', '4', '5', '6', 'new', 'base']

// Raw payload from /admin/dashboard: artists carry a by_language breakdown so the
// language filter below is applied client-side, with no extra round trip.
const rawArtistStats = computed(() => {
  const d = dashboardData.value.audio_seg_artists || {}
  return {
    artists: d.artists || [],
    overall: d.overall || {},
    languages: d.languages || [],
    all_languages: d.all_languages || [],
  }
})

const qualityLanguageOptions = computed(() => {
  const d = rawArtistStats.value
  if (d.all_languages.length) return d.all_languages
  return d.languages.map(l => l.language)
})

const languageStats = computed(() =>
  [...rawArtistStats.value.languages].sort((a, b) => b.pending - a.pending || b.clips - a.clips)
)

const EMPTY_BUCKET = {
  clips: 0, total: 0, accepted: 0, rejected: 0, pending: 0, batch_count: 0,
  rejection_rate: 0, pending_rate: 0, reviewed_rate: 0, reasons: [],
}

function rollUp(buckets) {
  const out = { ...EMPTY_BUCKET, reasons: [] }
  const reasons = {}
  for (const b of buckets) {
    out.clips += b.clips || 0
    out.total += b.total || 0
    out.accepted += b.accepted || 0
    out.rejected += b.rejected || 0
    out.pending += b.pending || 0
    out.batch_count += b.batch_count || 0
    for (const r of b.reasons || []) {
      const e = reasons[r.reason] || (reasons[r.reason] = { reason: r.reason, label: r.label, count: 0 })
      e.count += r.count
    }
  }
  const pct = (n, d) => (d ? Math.round((1000 * n) / d) / 10 : 0)
  out.rejection_rate = pct(out.rejected, out.total)
  out.pending_rate = pct(out.pending, out.clips)
  out.reviewed_rate = pct(out.clips - out.pending, out.clips)
  out.reasons = Object.values(reasons)
    .map(r => ({ ...r, pct_of_rejections: pct(r.count, out.rejected) }))
    .sort((a, b) => b.count - a.count)
  return out
}

// Artist rollups narrowed to the selected language (all languages when unset).
const artistStats = computed(() => {
  const d = rawArtistStats.value
  if (!qualityLanguage.value) return { artists: d.artists, overall: d.overall }
  const artists = []
  for (const a of d.artists) {
    const b = (a.by_language || {})[qualityLanguage.value]
    if (!b) continue
    artists.push({ ...rollUp([b]), artist: a.artist })
  }
  artists.sort((x, y) => y.rejection_rate - x.rejection_rate)
  const lang = d.languages.find(l => l.language === qualityLanguage.value)
  return { artists, overall: lang || rollUp(artists) }
})

// ---------------------------------------------------------------------------
// Annotation hours (audio segmentation only) — Quality tab
// ---------------------------------------------------------------------------
const EMPTY_HOURS_BUCKET = { clips: 0, skipped: 0, seconds: 0, hours: 0, label: '0s' }
const EMPTY_AUDIO_HOURS = {
  timezone: 'IST (UTC+5:30)', today_date: '', annotators: [], daily_series: [],
  totals: EMPTY_HOURS_BUCKET, today: EMPTY_HOURS_BUCKET,
  last_7_days: EMPTY_HOURS_BUCKET, active_today: 0,
  by_artist: [], by_persona: [],
}

const hoursRanges = [{ days: 7, label: '7d' }, { days: 14, label: '14d' }, { days: 30, label: '30d' }]
const hoursRange = ref(14)
const expandedHours = ref(null)

// Clips still stored with a rejection reason the UI has retired.
const retiredCopied = ref(false)
const retiredClips = computed(() => {
  const d = dashboardData.value?.retired_reason_clips
  if (!d || !Array.isArray(d.clips)) return { clips: [], total: 0, by_reason: [] }
  return d
})

// Plain-text list the admin can paste into a message to the annotator.
async function copyRetiredList() {
  const lines = retiredClips.value.clips.map(
    c => `${c.rater_name} · batch ${c.test_id} · clip ${c.clip_id} · reason "${c.retired_reasons.join(', ')}" · ${c.link}`
  )
  const text = `Please re-do these ${lines.length} clip(s) — the rejection reason used is no longer available, `
    + `so open each one, uncheck it and pick a current reason:\n\n` + lines.join('\n')
  try {
    await navigator.clipboard.writeText(text)
  } catch (e) {
    // Clipboard API needs a secure context / permission; fall back to a prompt.
    window.prompt('Copy the list below:', text)
  }
  retiredCopied.value = true
  setTimeout(() => { retiredCopied.value = false }, 2000)
}

const audioHours = computed(() => {
  const d = dashboardData.value?.audio_hours
  if (!d || !Array.isArray(d.annotators)) return EMPTY_AUDIO_HOURS
  return { ...EMPTY_AUDIO_HOURS, ...d }
})

// The backend sends 30 dense days newest-first; slice to the picked range and flip
// so the chart reads left (oldest) to right (today).
const teamSeries = computed(() =>
  [...(audioHours.value.daily_series || [])].slice(0, hoursRange.value).reverse()
)

const teamPeak = computed(() =>
  teamSeries.value.reduce((m, d) => Math.max(m, d.seconds || 0), 0)
)

const teamPeakLabel = computed(() => {
  const p = teamSeries.value.find(d => d.seconds === teamPeak.value)
  return teamPeak.value ? p.label : '—'
})

function teamBarHeight(d) {
  if (!teamPeak.value || !d.seconds) return '3px'
  return Math.max(6, Math.round((d.seconds / teamPeak.value) * 100)) + '%'
}

function hoursShare(a) {
  const total = audioHours.value.totals.seconds || 0
  if (!total || !a.seconds) return 0
  return Math.round((a.seconds / total) * 100)
}

// Only the days this annotator actually worked, inside the picked range.
function workedDays(a) {
  return (a.daily_series || []).slice(0, hoursRange.value).filter(d => d.clips)
}

function dayShareOf(d, a) {
  const peak = workedDays(a).reduce((m, x) => Math.max(m, x.seconds || 0), 0)
  if (!peak || !d.seconds) return 0
  return Math.max(4, Math.round((d.seconds / peak) * 100))
}

function toggleHoursRow(raterId) {
  expandedHours.value = expandedHours.value === raterId ? null : raterId
}

// 'YYYY-MM-DD' is already an IST calendar date — parse it as a local date so no
// browser timezone can shift the label back a day.
function parseDay(iso) {
  const [y, m, d] = (iso || '').split('-').map(Number)
  return new Date(y, (m || 1) - 1, d || 1)
}

function shortDay(iso) {
  return parseDay(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
}

function longDay(iso) {
  return parseDay(iso).toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' })
}

function downloadAudioHours() {
  downloadCsv('/admin/export_audio_hours_csv?days=' + hoursRange.value,
              'audio_hours_last_' + hoursRange.value + 'd.csv')
}

// Reasons for the selected artist, or the overall breakdown when none is picked.
const activeReasons = computed(() => {
  if (!artistReasonFilter.value) return artistStats.value.overall.reasons || []
  const a = artistStats.value.artists.find(x => x.artist === artistReasonFilter.value)
  return a ? a.reasons : []
})

// A filtered-out artist must not leave a stale reason breakdown on screen.
watch(qualityLanguage, () => {
  if (artistReasonFilter.value &&
      !artistStats.value.artists.some(a => a.artist === artistReasonFilter.value)) {
    artistReasonFilter.value = ''
  }
})

async function downloadCsv(path, filename) {
  try {
    const token = localStorage.getItem('authToken')
    const resp = await fetch(`${API_BASE_URL}${path}`, {
      headers: { 'Authorization': `Bearer ${token}` }
    })
    if (!resp.ok) { alert('Export failed (' + resp.status + ')'); return }
    const blob = await resp.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  } catch (e) {
    console.error('export failed', e)
    alert('Export failed - see console.')
  }
}

function downloadTasksExport() {
  const params = new URLSearchParams()
  if (exportVersion.value) params.set('version', exportVersion.value)
  if (exportTestType.value) params.set('test_type', exportTestType.value)
  const qs = params.toString()
  const name = 'tasks_export' + (exportVersion.value ? '_v' + exportVersion.value : '') + '.csv'
  downloadCsv('/admin/export_tasks_csv' + (qs ? '?' + qs : ''), name)
}

// Suffix the downloaded filename with the language so the vendor can tell the
// per-language exports apart.
function qualitySuffix() {
  return qualityLanguage.value ? '_' + qualityLanguage.value.replace(/[^A-Za-z0-9_-]/g, '') : ''
}

function downloadAudioClips(onlyRejected) {
  const params = new URLSearchParams()
  if (onlyRejected) params.set('rejected_only', '1')
  if (qualityLanguage.value) params.set('language', qualityLanguage.value)
  const qs = params.toString()
  // "All clips" also carries the not-yet-reviewed clips (evaluation = pending).
  const name = (onlyRejected ? 'audio_clips_rejected' : 'audio_clips_all') + qualitySuffix() + '.csv'
  downloadCsv('/admin/export_audio_clips_csv' + (qs ? '?' + qs : ''), name)
}

function downloadArtistReport() {
  const qs = qualityLanguage.value ? '?language=' + encodeURIComponent(qualityLanguage.value) : ''
  downloadCsv('/admin/export_artist_report_csv' + qs, 'artist_rejection_report' + qualitySuffix() + '.csv')
}

function downloadAnnotatorsReport() {
  const params = new URLSearchParams()
  if (activityFrom.value) params.set('from', activityFrom.value)
  if (activityTo.value) params.set('to', activityTo.value)
  const qs = params.toString()
  const name = 'annotators_report' + (qs ? '_' + qs : '') + '.csv'
  downloadCsv('/admin/export_annotators_csv' + (qs ? '?' + qs : ''), name)
}

const exportFromDate = ref('')
const exportToDate = ref('')

function setExportPreset(days) {
  if (days === 0) {
    const today = new Date().toISOString().split('T')[0]
    exportFromDate.value = today
    exportToDate.value = today
  } else if (days > 0) {
    const to = new Date()
    const from = new Date()
    from.setDate(from.getDate() - days + 1)
    exportFromDate.value = from.toISOString().split('T')[0]
    exportToDate.value = to.toISOString().split('T')[0]
  } else {
    exportFromDate.value = ''
    exportToDate.value = ''
  }
}

function downloadAnnotatorSummaryReport(rater = null) {
  const params = new URLSearchParams()
  if (rater) params.set('rater_id', rater.id)
  if (exportFromDate.value) params.set('from', exportFromDate.value)
  if (exportToDate.value) params.set('to', exportToDate.value)
  const qs = params.toString()
  const rName = rater ? (rater.name || 'rater').replace(/\s+/g, '_') : 'all'
  const name = rater ? `annotator_${rater.id}_${rName}_summary.csv` : `annotators_summary_report${qs ? '_' + qs : ''}.csv`
  downloadCsv('/admin/export_annotators_csv?' + qs, name)
}

function downloadAllDetailedRatings() {
  const params = new URLSearchParams()
  if (exportFromDate.value) params.set('from', exportFromDate.value)
  if (exportToDate.value) params.set('to', exportToDate.value)
  const qs = params.toString()
  const name = 'all_annotations_report' + (qs ? '_' + qs : '') + '.csv'
  downloadCsv('/admin/export_all_ratings_csv' + (qs ? '?' + qs : ''), name)
}

const openGlobalExportModal = () => {
  currentRaterForExport.value = null
  selectedExportTaskId.value = ''
  exportFromDate.value = activityFrom.value || ''
  exportToDate.value = activityTo.value || ''
  showExportModal.value = true
  clearTimers()
}

function downloadRaterDetailedRatings(rater) {
  if (!rater) return
  const params = new URLSearchParams()
  if (exportFromDate.value) params.set('from', exportFromDate.value)
  if (exportToDate.value) params.set('to', exportToDate.value)
  const qs = params.toString()
  const rName = (rater.name || 'rater').replace(/\s+/g, '_')
  const name = `annotations_rater_${rater.id}_${rName}.csv`
  downloadCsv(`/admin/export_rater_ratings_csv/${rater.id}` + (qs ? '?' + qs : ''), name)
}


const signupPin = ref('')
const signupPinDate = ref('')
const signupPinCopied = ref(false)

async function fetchSignupPin() {
  try {
    const token = localStorage.getItem('authToken')
    const resp = await fetch(`${API_BASE_URL}/admin/signup-key`, {
      headers: { 'Authorization': `Bearer ${token}` }
    })
    if (!resp.ok) return
    const d = await resp.json()
    signupPin.value = d.pin || ''
    signupPinDate.value = d.date || ''
  } catch (e) {
    console.error('Could not load signup PIN', e)
  }
}

async function copySignupPin() {
  try {
    await navigator.clipboard.writeText(signupPin.value)
    signupPinCopied.value = true
    setTimeout(() => { signupPinCopied.value = false }, 1500)
  } catch (e) {
    console.error('copy failed', e)
  }
}
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
const showAnnotatorDataModal = ref(false)
const showRatingsModal = ref(false)
const selectedRater = ref(null)
const selectedExportTaskId = ref('')

const timelineFrom = ref('')
const timelineTo = ref('')
const activePreset = ref('all')

const setTimelinePreset = (preset) => {
  activePreset.value = preset
  if (preset === 'today') {
    const today = new Date().toISOString().split('T')[0]
    timelineFrom.value = today
    timelineTo.value = today
  } else if (preset === '7days') {
    const to = new Date()
    const from = new Date()
    from.setDate(from.getDate() - 6)
    timelineFrom.value = from.toISOString().split('T')[0]
    timelineTo.value = to.toISOString().split('T')[0]
  } else if (preset === '30days') {
    const to = new Date()
    const from = new Date()
    from.setDate(from.getDate() - 29)
    timelineFrom.value = from.toISOString().split('T')[0]
    timelineTo.value = to.toISOString().split('T')[0]
  } else {
    // 'all' / Entire Life Duration by default
    timelineFrom.value = ''
    timelineTo.value = ''
  }
}

const openAnnotatorDataModal = (rater = null) => {
  selectedRater.value = rater
  setTimelinePreset('all') // Entire Life Duration default!
  showAnnotatorDataModal.value = true
  clearTimers()
}

const closeAnnotatorDataModal = () => {
  showAnnotatorDataModal.value = false
  selectedRater.value = null
  if (isAutoRefreshActive.value) startTimers()
}

const openRatingsModal = (rater = null) => {
  selectedRater.value = rater
  selectedExportTaskId.value = ''
  showRatingsModal.value = true
  clearTimers()
}

const closeRatingsModal = () => {
  showRatingsModal.value = false
  selectedRater.value = null
  selectedExportTaskId.value = ''
  if (isAutoRefreshActive.value) startTimers()
}

const exportAnnotatorDataCSV = () => {
  const rater = selectedRater.value
  const params = new URLSearchParams()
  if (rater) params.set('rater_id', rater.id)
  if (timelineFrom.value) params.set('from', timelineFrom.value)
  if (timelineTo.value) params.set('to', timelineTo.value)
  const qs = params.toString()
  const rName = rater ? (rater.name || 'rater').replace(/\s+/g, '_') : 'all'
  const name = rater ? `annotator_${rater.id}_${rName}_summary.csv` : `annotators_summary_report${qs ? '_' + qs : ''}.csv`
  downloadCsv('/admin/export_annotators_csv?' + qs, name)
  closeAnnotatorDataModal()
}

const exportRatingsCSV = () => {
  const rater = selectedRater.value
  if (selectedExportTaskId.value) {
    exportCSV(selectedExportTaskId.value, rater ? rater.id : null, rater ? rater.name : '')
  } else if (rater) {
    const params = new URLSearchParams()
    if (timelineFrom.value) params.set('from', timelineFrom.value)
    if (timelineTo.value) params.set('to', timelineTo.value)
    const qs = params.toString()
    const rName = (rater.name || 'rater').replace(/\s+/g, '_')
    const name = `annotations_rater_${rater.id}_${rName}.csv`
    downloadCsv(`/admin/export_rater_ratings_csv/${rater.id}` + (qs ? '?' + qs : ''), name)
  } else {
    const params = new URLSearchParams()
    if (timelineFrom.value) params.set('from', timelineFrom.value)
    if (timelineTo.value) params.set('to', timelineTo.value)
    const qs = params.toString()
    const name = 'all_annotations_report' + (qs ? '_' + qs : '') + '.csv'
    downloadCsv('/admin/export_all_ratings_csv' + (qs ? '?' + qs : ''), name)
  }
  closeRatingsModal()
}

const exportableTaskIds = computed(() => {
  return assignedIdList(selectedRater.value)
})

const getTaskDescription = (tid) => {
  const t = tests.value.find(x => x.id === tid)
  return t ? t.description : 'No description'
}

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

// Backend timestamps are UTC but serialized without a timezone marker; append
// 'Z' so they render in the viewer's local time instead of shifted by the offset.
const toUtcDate = (iso) => {
  if (!iso) return new Date(NaN)
  return new Date(/[Zz]|[+-]\d\d:\d\d$/.test(iso) ? iso : iso + 'Z')
}

const formatDate = (isoString) => {
  if (!isoString) return ''
  const date = toUtcDate(isoString)
  if (isNaN(date.getTime())) return ''
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
  const t = toUtcDate(iso).getTime()
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
  activeTab.value = 'tasks'
  tasksSubTab.value = 'alltasks'
  // Bring the batch list into view once the "All Tasks" sub-tab has rendered.
  nextTick(() => {
    document.getElementById('batch-list-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  })
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

// ---- Per-task-type overview (Overview tab sub-tabs) ----
const taskTypes = computed(() => dashboardData.value.task_types || {})
const taskTypeNames = computed(() => Object.keys(taskTypes.value).sort())
const activeTypeTab = ref('')
watch(taskTypeNames, (names) => {
  if (names.length && !names.includes(activeTypeTab.value)) activeTypeTab.value = names[0]
}, { immediate: true })
const currentType = computed(() => taskTypes.value[activeTypeTab.value] || null)
// Accept/reject columns only make sense for evaluation-style task types.
const typeHasEval = computed(() =>
  !!currentType.value && (currentType.value.totals.accepted + currentType.value.totals.rejected) > 0
)

const typeSearch = ref('')
const typeLangFilter = ref('')
const typeStatusFilter = ref('')
const typeSort = ref({ key: 'id', dir: 'asc' })
const typePage = ref(1)
const typePageSize = 25
const expandedTypeRows = ref([])

// Each tab is its own view — reset filters when switching so nothing looks empty.
watch(activeTypeTab, () => {
  typeSearch.value = ''
  typeLangFilter.value = ''
  typeStatusFilter.value = ''
  typeSort.value = { key: 'id', dir: 'asc' }
  typePage.value = 1
  expandedTypeRows.value = []
})

const toggleTypeRow = (id) => {
  const i = expandedTypeRows.value.indexOf(id)
  if (i === -1) expandedTypeRows.value.push(id)
  else expandedTypeRows.value.splice(i, 1)
}

const batchStatus = (b) => {
  if (b.total_tasks && b.unique_completed >= b.total_tasks) return 'Complete'
  if (b.total_submissions > 0 || b.in_progress > 0) return 'In progress'
  return 'Not started'
}

const typeLanguages = computed(() => {
  if (!currentType.value) return []
  return [...new Set(currentType.value.batches.map(b => b.language).filter(Boolean))].sort()
})

const sortType = (key) => {
  if (typeSort.value.key === key) typeSort.value = { key, dir: typeSort.value.dir === 'asc' ? 'desc' : 'asc' }
  else typeSort.value = { key, dir: key === 'id' ? 'asc' : 'desc' }
}

const filteredTypeBatches = computed(() => {
  if (!currentType.value) return []
  let list = currentType.value.batches
  if (typeLangFilter.value) list = list.filter(b => b.language === typeLangFilter.value)
  if (typeStatusFilter.value === 'notstarted') list = list.filter(b => batchStatus(b) === 'Not started')
  else if (typeStatusFilter.value === 'inprogress') list = list.filter(b => batchStatus(b) === 'In progress')
  else if (typeStatusFilter.value === 'complete') list = list.filter(b => batchStatus(b) === 'Complete')
  else if (typeStatusFilter.value === 'unassigned') list = list.filter(b => !b.assigned_to.length)
  if (typeSearch.value) {
    const q = typeSearch.value.toLowerCase()
    list = list.filter(b =>
      String(b.test_id).includes(q) ||
      (b.description || '').toLowerCase().includes(q) ||
      b.assigned_to.some(n => n.toLowerCase().includes(q)) ||
      b.annotators.some(a => (a.name || '').toLowerCase().includes(q))
    )
  }
  const { key, dir } = typeSort.value
  const mul = dir === 'asc' ? 1 : -1
  return [...list].sort((a, b) => {
    switch (key) {
      case 'completion':
        return mul * (getPercent(a.unique_completed, a.total_tasks) - getPercent(b.unique_completed, b.total_tasks))
      case 'submissions':
        return mul * (a.total_submissions - b.total_submissions)
      case 'lastactivity':
        return mul * (toUtcDate(a.last_activity).getTime() - toUtcDate(b.last_activity).getTime())
      default:
        return mul * (a.test_id - b.test_id)
    }
  })
})

const typePageCount = computed(() => Math.max(1, Math.ceil(filteredTypeBatches.value.length / typePageSize)))
const pagedTypeBatches = computed(() =>
  filteredTypeBatches.value.slice((typePage.value - 1) * typePageSize, typePage.value * typePageSize)
)
const typeRangeStart = computed(() => filteredTypeBatches.value.length ? (typePage.value - 1) * typePageSize + 1 : 0)
const typeRangeEnd = computed(() => Math.min(typePage.value * typePageSize, filteredTypeBatches.value.length))
watch(() => filteredTypeBatches.value.length, () => { typePage.value = 1 })

// "2h ago" relative time for dense tables; hover shows the full date.
const timeAgo = (iso) => {
  if (!iso) return '—'
  const t = toUtcDate(iso).getTime()
  if (isNaN(t)) return '—'
  const s = Math.floor((Date.now() - t) / 1000)
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  return `${Math.floor(s / 86400)}d ago`
}

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
// Clicking a task opens the admin review view (submitted annotations grouped by
// annotator), not the blank annotation page.
const openTask = (id) => { router.push(`/admin/task/${id}`) }

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

// ---- Message a single annotator (with full stacked history) ----
const threadItems = ref([])
const threadLoading = ref(false)
const threadBox = ref(null)

// Everything ever sent to this annotator (individual messages, nudges and
// broadcasts they received), oldest first so it reads like a chat.
const loadThread = async (raterId) => {
  threadLoading.value = true
  try {
    const token = localStorage.getItem('authToken')
    if (!token) { router.push('/login'); return }
    const resp = await fetch(`${API_BASE_URL}/admin/messages`, {
      headers: { 'Authorization': `Bearer ${token}` }
    })
    const data = await resp.json().catch(() => ({}))
    if (!resp.ok) throw new Error(data.message || 'Failed to load history.')
    threadItems.value = (data.items || [])
      .filter(it => it.kind === 'broadcast' || it.rater_id === raterId)
      .reverse()
    await nextTick()
    if (threadBox.value) threadBox.value.scrollTop = threadBox.value.scrollHeight
  } catch (_) {
    threadItems.value = []
  } finally {
    threadLoading.value = false
  }
}

const openMessageModal = (rater) => {
  messageTarget.value = rater
  messageBody.value = ''
  messageError.value = null
  showMessageModal.value = true
  clearTimers()
  loadThread(rater.id)
}
const closeMessageModal = () => {
  showMessageModal.value = false
  messageTarget.value = null
  threadItems.value = []
  if (isAutoRefreshActive.value) startTimers()
}
const sendMessage = async () => {
  if (!messageTarget.value || !messageBody.value.trim()) return
  isSendingMsg.value = true
  messageError.value = null
  try {
    const name = messageTarget.value.name
    await adminPost(`/admin/rater/${messageTarget.value.id}/message`, { body: messageBody.value.trim() })
    messageBody.value = ''
    showToast(`Message sent to ${name}`)
    // Keep the modal open so the sent message appears at the bottom of the stack.
    loadThread(messageTarget.value.id)
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
    if (showOutboxModal.value) await fetchOutbox()
    // If the edit was launched from a message thread, refresh that stack too.
    if (showMessageModal.value && messageTarget.value) loadThread(messageTarget.value.id)
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

// --- Modal UX: Esc-to-close + background scroll lock (applies to every popup) ---
// Ordered by stacking: whichever is open gets closed first on Escape.
const modalControllers = [
  { open: showEditMsgModal,       close: closeEditMsg },
  { open: showOutboxModal,        close: closeOutbox },
  { open: showRemoveModal,        close: closeRemoveModal },
  { open: showAssignModal,        close: closeAssignModal },
  { open: showMessageModal,       close: closeMessageModal },
  { open: showBroadcastModal,     close: closeBroadcastModal },
  { open: showRatingsModal,       close: closeRatingsModal },
  { open: showAnnotatorDataModal, close: closeAnnotatorDataModal },
]
const anyModalOpen = computed(() => modalControllers.some(m => m.open.value))
watch(anyModalOpen, (open) => {
  document.body.classList.toggle('modal-open-lock', open)
})
const onGlobalKeydown = (e) => {
  if (e.key === 'Escape') {
    const top = modalControllers.find(m => m.open.value)
    if (top) { e.preventDefault(); top.close() }
  }
}

// Lifecycle
onMounted(() => {
  window.addEventListener('keydown', onGlobalKeydown)
  fetchSignupPin()
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
  window.removeEventListener('keydown', onGlobalKeydown)
  document.body.classList.remove('modal-open-lock')
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
  /* Keep the tab bar reachable while scrolling the long tables underneath. */
  position: sticky;
  top: 8px;
  z-index: 1020;
}
.tab-btn {
  border-radius: 6px;
  transition: all 0.2s ease;
  font-size: 0.95rem;
  min-width: 120px;
}
.tab-btn:hover {
  transform: translateY(-1px);
}
.tab-btn i {
  font-size: 1rem;
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

/* ---------- Annotation hours (Quality tab) ---------- */
.ah-chart {
  display: flex;
  align-items: flex-end;
  gap: 5px;
  height: 120px;
}

.ah-chart-col {
  flex: 1 1 0;
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  height: 100%;
}

.ah-chart-track {
  flex: 1 1 auto;
  width: 100%;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}

.ah-chart-bar {
  width: 100%;
  max-width: 24px;
  border-radius: 5px 5px 2px 2px;
  background: linear-gradient(180deg, #7ba7f5, #2563eb);
  transition: height 0.25s ease, filter 0.15s ease;
}

.ah-chart-bar.is-today { background: linear-gradient(180deg, #34d399, #059669); }
.ah-chart-bar.is-empty { background: #e9eef5; }
.ah-chart-col:hover .ah-chart-bar { filter: brightness(1.08); }

.ah-chart-day {
  margin-top: 6px;
  font-size: 0.62rem;
  color: #98a2b3;
  white-space: nowrap;
}

.ah-scroll { max-height: 300px; overflow-y: auto; }

/* Helper Text styles */
.text-xs {
  font-size: 0.825rem;
}

/* Utility shims: these Tailwind-style class names are used throughout the
   template (esp. the popups) but don't exist in Bootstrap, so without these
   rules the intended spacing/typography silently does nothing. */
.text-sm { font-size: 0.875rem; }
.fs-9 { font-size: 0.75rem; }
.fs-10 { font-size: 0.7rem; }
.shadow-2xs { box-shadow: 0 1px 2px rgba(15, 23, 42, 0.06) !important; }
.p-3\.5 { padding: 1.25rem !important; }
.px-3\.5 { padding-left: 1.25rem !important; padding-right: 1.25rem !important; }
.py-2\.5 { padding-top: 0.75rem !important; padding-bottom: 0.75rem !important; }
.px-2\.5 { padding-left: 0.75rem !important; padding-right: 0.75rem !important; }
.py-1\.5 { padding-top: 0.375rem !important; padding-bottom: 0.375rem !important; }
.mb-3\.5 { margin-bottom: 1.25rem !important; }
.mb-1\.5 { margin-bottom: 0.375rem !important; }
.gap-2\.5 { gap: 0.75rem !important; }
.gap-1\.5 { gap: 0.375rem !important; }
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
  flex-shrink: 0;            /* header stays put; only the body scrolls */
}

.assign-modal-body {
  padding: 1.25rem 1.5rem;
  overflow-y: auto;
}

.assign-modal-footer {
  padding: 1rem 1.5rem;
  border-top: 1px solid #eef2f7;
  background: #f8fafc;
  flex-shrink: 0;           /* action buttons stay visible on tall modals */
}

/* Lock background scrolling while any popup is open (body is outside scoped CSS). */
:global(body.modal-open-lock) {
  overflow: hidden;
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
.rater-actions {
  flex-wrap: nowrap;
  gap: 8px !important;
}
.rater-action-btn {
  width: 32px;
  height: 32px;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  flex-shrink: 0;
  transition: all 0.15s ease;
}
.rater-action-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.12), 0 2px 4px -2px rgba(0, 0, 0, 0.08);
}
.rater-action-btn .bi {
  font-size: 0.95rem;
}
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

/* Centered segmented control for the Tasks sub-tabs */
.tasks-subnav {
  background: #eef1f4;
  border: 1px solid #e4e8ec;
  border-radius: 999px;
  padding: 4px;
  gap: 2px;
}
.subnav-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  border: none;
  background: transparent;
  color: #6b7280;
  font-weight: 600;
  font-size: 0.9rem;
  line-height: 1;
  padding: 0.5rem 1.25rem;
  border-radius: 999px;
  cursor: pointer;
  transition: color 0.18s ease, background-color 0.18s ease, box-shadow 0.18s ease;
  white-space: nowrap;
}
.subnav-btn:hover:not(.active) {
  color: #1f2937;
  background: rgba(15, 23, 42, 0.05);
}
.subnav-btn.active {
  background: #1f2937;
  color: #fff;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.18);
}
.subnav-btn .bi {
  font-size: 1rem;
}
.subnav-badge {
  font-size: 0.72rem;
  font-weight: 700;
  padding: 0.08rem 0.5rem;
  border-radius: 999px;
  background: #d7dce1;
  color: #4b5563;
}
.subnav-btn.active .subnav-badge {
  background: rgba(255, 255, 255, 0.24);
  color: #fff;
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

/* ---- UX polish: keep table headers visible while scrolling long lists ---- */
.table-responsive {
  max-height: calc(100vh - 260px);
  overflow-y: auto;
}
.table-responsive > table > thead th {
  position: sticky;
  top: 0;
  z-index: 3;
  background: #f8f9fa;
  box-shadow: inset 0 -1px 0 #dee2e6;
}
/* numbers line up column-wise instead of jittering */
.tasks-cell, .tasks-cell .badge {
  font-variant-numeric: tabular-nums;
}
.tasks-cell .badge { min-width: 2.5rem; }

/* ---- Tasks Overview: per-task-type sub-tabs ---- */
.type-tabs {
  background-color: #f8f9fa;
  border-top-left-radius: inherit;
  border-top-right-radius: inherit;
}
.type-tab-btn {
  border-radius: 6px;
  font-size: 0.85rem;
  transition: all 0.15s ease;
}
.ov-tile {
  display: flex;
  flex-direction: column;
  justify-content: center;
  flex: 1 1 150px;
  min-width: 150px;
  max-width: 260px;
  padding: 10px 14px;
  border: 1px solid #e9ecef;
  border-radius: 8px;
  background: #fcfcfd;
}
.ov-tile .lbl {
  font-size: 0.66rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #6c757d;
  white-space: nowrap;
}
.ov-tile .val {
  font-size: 1.15rem;
  font-weight: 700;
  color: #212529;
  line-height: 1.3;
}
.ov-tile .sub {
  font-size: 0.7rem;
  color: #6c757d;
  white-space: nowrap;
}
.type-row {
  cursor: pointer;
}

/* ---- Admin message thread (stacked history in the message modal) ---- */
.msg-thread {
  max-height: 300px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-right: 4px;
}
.msg-bubble {
  background: #f8fafc;
  border: 1px solid #eef2f7;
  border-radius: 10px;
  padding: 10px 12px;
}
.msg-bubble.broadcast {
  background: #fffaf3;
  border-color: #fbe3c4;
}
</style>