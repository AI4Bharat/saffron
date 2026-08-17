<template>
  <div class="dashboard-container py-4">
    <!-- Header -->
    <div class="d-flex flex-wrap justify-content-between align-items-center mb-4 pb-3 border-bottom border-secondary-subtle">
      <div>
        <h1 class="h2 fw-bold text-dark mb-1">Admin Dashboard</h1>
        <p class="text-muted mb-0">
          Monitor the prompt pool, languages, classes and annotator progress in real-time.
        </p>
      </div>
      <div class="d-flex align-items-center gap-3 mt-3 mt-md-0">
        <div class="d-flex align-items-center gap-2 bg-light px-3 py-2 rounded border shadow-sm">
          <div :class="['status-dot', isAutoRefreshActive ? 'active animate-pulse' : '']"></div>
          <span class="text-xs fw-medium text-secondary">
            {{ isAutoRefreshActive ? `Auto-refreshing in ${countdown}s` : 'Auto-refresh paused' }}
          </span>
          <button @click="toggleAutoRefresh" class="btn btn-sm btn-outline-secondary ms-2" title="Toggle Auto-Refresh">
            <i :class="['bi', isAutoRefreshActive ? 'bi-pause-fill' : 'bi-play-fill']"></i>
          </button>
        </div>
        <button class="btn btn-primary d-flex align-items-center gap-2 shadow-sm" :disabled="loading" @click="load">
          <i :class="['bi', 'bi-arrow-clockwise', { 'animate-spin': loading }]"></i>
          <span>Refresh</span>
        </button>
      </div>
    </div>

    <div v-if="error" class="alert alert-danger alert-dismissible fade show shadow-sm">
      <i class="bi bi-exclamation-triangle-fill me-2"></i>{{ error }}
      <button type="button" class="btn-close" @click="error = ''"></button>
    </div>

    <!-- Navigation Tabs -->
    <div class="tabs-nav mb-4 bg-white p-2 rounded shadow-sm border d-flex gap-2 flex-wrap">
      <button v-for="t in tabs" :key="t.key" :title="t.hint" @click="setTab(t.key)"
              :class="['tab-btn btn flex-fill py-2 fw-semibold d-flex align-items-center justify-content-center gap-2',
                       tab === t.key ? 'btn-dark text-white' : 'btn-light text-secondary']">
        <i :class="['bi', t.icon]"></i><span>{{ t.label }}</span>
      </button>
    </div>

    <div class="tab-content">
      <!-- ══════════════════ OVERVIEW ══════════════════ -->
      <div v-if="tab === 'overview'" class="tab-pane-active">
        <div class="row g-4 mb-4">
          <div class="col-12 col-sm-6 col-xl-3">
            <div class="kpi-card bg-white p-4 rounded shadow-sm border border-start border-4 border-primary">
              <div class="d-flex justify-content-between align-items-center mb-2">
                <span class="text-muted fw-medium text-uppercase text-xs">Prompts in the pool</span>
                <div class="kpi-icon-wrapper bg-primary-subtle text-primary"><i class="bi bi-collection-fill fs-5"></i></div>
              </div>
              <h2 class="fw-bold text-dark mb-1">{{ (stats.total || 0).toLocaleString() }}</h2>
              <div class="text-xs text-muted d-flex align-items-center gap-1">
                <span class="text-success fw-bold">{{ stats.languages || 0 }} languages</span>
                <span>•</span><span>{{ uploads.length }} upload(s)</span>
              </div>
            </div>
          </div>

          <div class="col-12 col-sm-6 col-xl-3">
            <div class="kpi-card bg-white p-4 rounded shadow-sm border border-start border-4 border-success">
              <div class="d-flex justify-content-between align-items-center mb-2">
                <span class="text-muted fw-medium text-uppercase text-xs">Annotated</span>
                <div class="kpi-icon-wrapper bg-success-subtle text-success"><i class="bi bi-check-circle-fill fs-5"></i></div>
              </div>
              <h2 class="fw-bold text-dark mb-1">
                {{ (stats.done || 0).toLocaleString() }}
                <span class="text-muted fs-6">/ {{ (stats.total || 0).toLocaleString() }}</span>
              </h2>
              <div class="progress mt-2" style="height: 6px;">
                <div class="progress-bar bg-success" :style="{ width: (stats.progress || 0) + '%' }"></div>
              </div>
              <p class="text-xs text-muted mt-2 mb-0">
                Coverage: {{ showPct(stats.progress, stats.done) }}% · {{ stats.completed_today || 0 }} today
              </p>
            </div>
          </div>

          <div class="col-12 col-sm-6 col-xl-3">
            <div class="kpi-card bg-white p-4 rounded shadow-sm border border-start border-4 border-warning">
              <div class="d-flex justify-content-between align-items-center mb-2">
                <span class="text-muted fw-medium text-uppercase text-xs">In progress</span>
                <div class="kpi-icon-wrapper bg-warning-subtle text-warning"><i class="bi bi-hourglass-split fs-5"></i></div>
              </div>
              <h2 class="fw-bold text-dark mb-1">{{ (stats.claimed || 0).toLocaleString() }}</h2>
              <p class="text-xs text-muted mb-0">
                Held by annotators · {{ (stats.available || 0).toLocaleString() }} still unclaimed
              </p>
            </div>
          </div>

          <div class="col-12 col-sm-6 col-xl-3">
            <div class="kpi-card bg-white p-4 rounded shadow-sm border border-start border-4 border-info">
              <div class="d-flex justify-content-between align-items-center mb-2">
                <span class="text-muted fw-medium text-uppercase text-xs">Annotators</span>
                <div class="kpi-icon-wrapper bg-info-subtle text-info"><i class="bi bi-people-fill fs-5"></i></div>
              </div>
              <h2 class="fw-bold text-dark mb-1">
                {{ stats.active_annotators || 0 }}<span class="text-muted fs-6">/ {{ stats.annotators || 0 }}</span>
              </h2>
              <div class="text-xs text-muted d-flex align-items-center gap-1">
                <span class="text-primary fw-bold">{{ (stats.edited || 0).toLocaleString() }} edits</span>
                <span>•</span>
                <span class="text-warning fw-bold">{{ (stats.flagged || 0).toLocaleString() }} flagged</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Needs attention: actionable task health (click a card to jump) -->
        <h3 class="fw-bold text-dark mb-3"><i class="bi bi-clipboard2-pulse-fill text-primary me-2"></i>Needs Attention</h3>
        <div class="row g-4 mb-4">
          <div class="col-12 col-md-4">
            <button type="button" class="attention-card w-100 text-start bg-white p-4 rounded shadow-sm border border-start border-4 border-danger"
                    @click="focusTasks('unassigned')">
              <div class="d-flex justify-content-between align-items-center mb-2">
                <span class="text-muted fw-medium text-uppercase text-xs">Unassigned Tasks</span>
                <div class="kpi-icon-wrapper bg-danger-subtle text-danger"><i class="bi bi-folder-x fs-5"></i></div>
              </div>
              <h2 class="fw-bold text-dark mb-1">{{ taskTotals.unassigned || 0 }}</h2>
              <p class="text-xs text-muted mb-0"><i class="bi bi-arrow-right-short"></i> Nobody can work these — assign them.</p>
            </button>
          </div>
          <div class="col-12 col-md-4">
            <button type="button" class="attention-card w-100 text-start bg-white p-4 rounded shadow-sm border border-start border-4 border-warning"
                    @click="focusTasks('not-started')">
              <div class="d-flex justify-content-between align-items-center mb-2">
                <span class="text-muted fw-medium text-uppercase text-xs">Assigned, Not Started</span>
                <div class="kpi-icon-wrapper bg-warning-subtle text-warning"><i class="bi bi-hourglass-bottom fs-5"></i></div>
              </div>
              <h2 class="fw-bold text-dark mb-1">{{ notStartedTasks }}</h2>
              <p class="text-xs text-muted mb-0"><i class="bi bi-arrow-right-short"></i> Handed out but nothing pulled yet.</p>
            </button>
          </div>
          <div class="col-12 col-md-4">
            <button type="button" class="attention-card w-100 text-start bg-white p-4 rounded shadow-sm border border-start border-4 border-success"
                    @click="focusTasks('in-progress')">
              <div class="d-flex justify-content-between align-items-center mb-2">
                <span class="text-muted fw-medium text-uppercase text-xs">Almost Done</span>
                <div class="kpi-icon-wrapper bg-success-subtle text-success"><i class="bi bi-flag-fill fs-5"></i></div>
              </div>
              <h2 class="fw-bold text-dark mb-1">{{ almostDoneTasks }}</h2>
              <p class="text-xs text-muted mb-0"><i class="bi bi-arrow-right-short"></i> &ge;80% done — a final push finishes them.</p>
            </button>
          </div>
        </div>

        <div v-if="stats.stale_claims" class="alert alert-warning d-flex align-items-center shadow-sm">
          <i class="bi bi-hourglass-split me-2"></i>
          <span><strong>{{ stats.stale_claims }}</strong> prompt(s) have been held for more than
            {{ staleHours }}h without being finished.</span>
          <button class="btn btn-sm btn-warning ms-auto" :disabled="reclaiming" @click="reclaim">
            Return them to the pool
          </button>
        </div>

        <div class="row g-4">
          <div class="col-12">
            <div class="bg-white p-4 rounded shadow-sm border h-100">
              <h5 class="fw-bold text-dark mb-3"><i class="bi bi-translate me-2 text-primary"></i>Progress by language</h5>
              <div v-for="L in languages" :key="L.language" class="mb-3 lang-line" @click="openLanguage(L)">
                <div class="d-flex justify-content-between align-items-center mb-1">
                  <span class="fw-semibold text-dark">{{ L.language }}</span>
                  <span class="text-xs text-muted">
                    {{ L.done.toLocaleString() }} / {{ L.total.toLocaleString() }}
                    <span class="fw-bold text-success ms-1">{{ showPct(L.progress, L.done) }}%</span>
                  </span>
                </div>
                <div class="progress" style="height: 7px;">
                  <div class="progress-bar bg-success" :style="{ width: pct(L.completed, L.total) }"></div>
                  <div class="progress-bar bg-warning" :style="{ width: pct(L.flagged, L.total) }"></div>
                  <div class="progress-bar bg-info" :style="{ width: pct(L.claimed, L.total) }"></div>
                </div>
              </div>
              <p v-if="!languages.length" class="text-muted small mb-0">No prompts loaded yet.</p>
            </div>
          </div>

        </div>
      </div>

      <!-- ══════════════════ TASKS ══════════════════ -->
      <div v-else-if="tab === 'tasks'" class="tab-pane-active">
        <!-- ── project heads: each kind of work is its own project; everything below is scoped to the selected one ── -->
        <div v-if="projectOptions.length > 1" class="d-flex justify-content-center mb-3">
          <div class="d-inline-flex flex-wrap justify-content-center gap-2">
            <button v-for="p in projectOptions" :key="p.key" type="button"
                    class="project-head-btn" :class="{ active: projectTab === p.key }"
                    @click="projectTab = p.key">
              <i :class="projectIcon(p.key)"></i>
              <span class="ph-label">{{ p.label }}</span>
              <span class="ph-count">{{ p.count }} task{{ p.count === 1 ? '' : 's' }} ·
                {{ p.items.toLocaleString() }} prompt{{ p.items === 1 ? '' : 's' }}</span>
            </button>
          </div>
        </div>

        <div class="d-flex justify-content-center align-items-center gap-3 flex-wrap mb-4">
          <div class="tasks-subnav d-inline-flex align-items-center">
            <button type="button" @click="tasksSubTab = 'overview'"
                    :class="['subnav-btn', { active: tasksSubTab === 'overview' }]">
              <i class="bi bi-stack"></i><span>Overview</span>
            </button>
            <button type="button" @click="tasksSubTab = 'all'"
                    :class="['subnav-btn', { active: tasksSubTab === 'all' }]">
              <i class="bi bi-list-task"></i><span>All Tasks</span>
              <span class="subnav-badge">{{ shownTasks.length }}</span>
            </button>
          </div>
          <div v-if="projectTab" class="d-inline-flex align-items-center gap-2 me-2 px-3 py-1 rounded-pill border bg-white">
            <label class="mb-0 small text-secondary text-nowrap" :for="'annper-' + projectTab">
              Annotators per task
            </label>
            <input :id="'annper-' + projectTab" type="number" min="1" max="9"
                   class="form-control form-control-sm text-center" style="width:64px"
                   :value="projectAnnotationsPer.effective"
                   title="How many annotators each prompt goes to. It is handed out at
                          most this many times and accepts exactly this many answers,
                          then closes to both. Any number of annotators may work the task."
                   @change="setProjectAnnotationsPer(projectTab, $event.target.value)" />
            <span class="text-muted text-xs text-nowrap">
              {{ projectAnnotationsPer.effective === 1
                   ? 'each prompt goes to one annotator'
                   : 'each prompt goes to ' + projectAnnotationsPer.effective
                     + ' annotators, then closes' }}
            </span>
            <button v-if="projectAnnotationsPer.override !== null"
                    class="btn btn-link btn-sm p-0 text-muted" title="Use the pool default again"
                    @click="setProjectAnnotationsPer(projectTab, null)">
              <i class="bi bi-x-circle-fill"></i>
            </button>
          </div>
          <button v-if="projectTab" type="button" class="btn btn-sm btn-outline-dark rounded-pill"
                  title="See this project's task exactly as an annotator sees it"
                  @click="openPreview(projectTab)">
            <i class="bi bi-eye me-1"></i>Preview annotator view
          </button>
        </div>

        <div v-if="tasksLoading" class="text-center py-5"><span class="spinner-border text-secondary"></span></div>

        <template v-else>
          <!-- ── Tasks overview ── -->
          <div v-show="tasksSubTab === 'overview'">
            <h3 class="fw-bold text-dark mb-3"><i class="bi bi-stack text-primary me-2"></i>Tasks Overview</h3>
            <div class="d-flex flex-wrap gap-2 mb-4">
              <div class="ov-tile">
                <span class="lbl">Tasks</span>
                <span class="val">{{ taskTotals.tasks || 0 }}</span>
                <span class="sub">one per language &amp; class</span>
              </div>
              <div class="ov-tile">
                <span class="lbl">Assigned</span>
                <span class="val">{{ taskTotals.assigned || 0 }}
                  <small class="text-muted fw-normal">/ {{ taskTotals.tasks || 0 }}</small></span>
                <span class="sub"><span class="text-danger fw-semibold">{{ taskTotals.unassigned || 0 }}</span> waiting for an annotator</span>
              </div>
              <div class="ov-tile">
                <span class="lbl">Task progress</span>
                <span class="val"><span class="text-success">{{ taskTotals.complete || 0 }}</span> done
                  <span class="text-muted mx-1 fw-normal">·</span>
                  <span class="text-warning-emphasis">{{ taskTotals.in_progress || 0 }}</span> running</span>
                <span class="sub">a task is done when every prompt in it is</span>
              </div>
              <div class="ov-tile">
                <span class="lbl">Prompts annotated</span>
                <span class="val">{{ (taskTotals.done || 0).toLocaleString() }}
                  <small class="text-muted fw-normal">/ {{ (taskTotals.total || 0).toLocaleString() }}</small></span>
                <div class="progress mt-1 mb-1" style="height: 5px;">
                  <div class="progress-bar bg-success" :style="{ width: (taskTotals.progress || 0) + '%' }"></div>
                </div>
                <span class="sub">{{ showPct(taskTotals.progress, taskTotals.done) }}% coverage</span>
              </div>
              <div class="ov-tile">
                <span class="lbl">Still unclaimed</span>
                <span class="val">{{ (taskTotals.available || 0).toLocaleString() }}</span>
                <span class="sub">{{ (taskTotals.claimed || 0).toLocaleString() }} being worked on now</span>
              </div>
            </div>

            <div class="bg-white p-4 rounded shadow-sm border">
              <div class="d-flex flex-wrap justify-content-between align-items-center mb-3">
                <div>
                  <h5 class="fw-bold text-dark mb-1">Tasks by language</h5>
                  <p class="text-muted text-xs mb-0">Click a language to see each class as its own task.</p>
                </div>
                <button class="btn btn-sm btn-outline-secondary"
                        @click="exportSimple('/pool/admin/export_tasks_csv', 'asr_task_list.csv', 'Task list')">
                  <i class="bi bi-filetype-csv me-1"></i>Export task list
                </button>
              </div>

              <div v-for="L in tasksByLanguage" :key="L.language" class="border rounded mb-2 overflow-hidden">
                <button class="lang-row btn w-100 d-flex align-items-center gap-3 py-3 px-3 text-start"
                        @click="toggle(L.language)">
                  <i class="bi text-secondary" :class="expanded[L.language] ? 'bi-chevron-down' : 'bi-chevron-right'"></i>
                  <span class="fw-bold text-dark" style="min-width:110px">{{ L.language }}</span>
                  <span class="text-xs text-muted" style="min-width:150px">
                    {{ L.tasks.length }} task(s) · {{ L.total.toLocaleString() }} prompts
                  </span>
                  <span class="badge rounded-pill" :class="L.assigned === L.tasks.length ? 'bg-success-subtle text-success' : 'bg-light text-secondary border'">
                    {{ L.assigned }}/{{ L.tasks.length }} assigned
                  </span>
                  <div class="progress flex-grow-1" style="height: 9px;">
                    <div class="progress-bar bg-success" :style="{ width: pct(L.completed, L.total) }" title="completed"></div>
                    <div class="progress-bar bg-warning" :style="{ width: pct(L.flagged, L.total) }" title="flagged"></div>
                    <div class="progress-bar bg-info" :style="{ width: pct(L.claimed, L.total) }" title="in progress"></div>
                  </div>
                  <span class="fw-bold text-success" style="min-width:56px;text-align:right">{{ showPct(L.progress, L.done) }}%</span>
                </button>

                <div v-if="expanded[L.language]" class="bg-light border-top p-3">
                  <div class="d-flex flex-wrap align-items-center gap-2 mb-2">
                    <button class="btn btn-sm btn-outline-primary"
                            @click="openAssign(L.tasks.map(t => t.task_id))">
                      <i class="bi bi-person-plus me-1"></i>
                      Assign all of {{ L.language }} ({{ L.tasks.length }} task(s))
                    </button>
                  </div>
                  <div class="table-responsive bg-white rounded border">
                    <table class="table table-sm table-hover align-middle mb-0">
                      <thead class="table-light">
                        <tr>
                          <th style="width:80px">Task ID</th><th>Class</th>
                          <th>Assigned to</th><th>State</th>
                          <th class="text-end">Prompts</th><th class="text-end">Completed</th>
                          <th class="text-end">In progress</th><th class="text-end">Available</th>
                          <th style="width:160px">Progress</th><th style="width:120px" title="Whether this kind of work requires its final label">Final label</th>
                          <th style="width:150px"></th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr v-for="t in L.tasks" :key="t.task_id" class="cursor-pointer" @click="openTask(t.task_id)">
                          <td><span class="task-id-badge">#{{ t.task_id }}</span></td>
                          <td class="fw-semibold">Class {{ t.class }}</td>
                          <td>
                            <span v-if="holdersOf(t).length" class="d-inline-flex flex-wrap gap-1 align-items-center">
                              <span v-for="a in holdersOf(t)" :key="a.rater_id + '-' + (a.category || '')"
                                    class="holder-chip" :title="holderTitle(a)">
                                <span class="holder-initial">{{ initialOf(a.name) }}</span>{{ a.name
                                }}<em v-if="a.category">{{ a.category }}</em>
                              </span>
                            </span>
                            <span v-else class="badge bg-danger-subtle text-danger rounded-pill">Unassigned</span>
                          </td>
                          <td><span class="badge rounded-pill" :class="stateBadge(t.state)">{{ t.state }}</span></td>
                          <td class="text-end">{{ t.total.toLocaleString() }}</td>
                          <td class="text-end text-success fw-semibold">{{ t.completed.toLocaleString() }}</td>
                          <td class="text-end">{{ t.claimed.toLocaleString() }}</td>
                          <td class="text-end text-muted">{{ t.available.toLocaleString() }}</td>
                          <td>
                            <div class="progress" style="height:6px"><div class="progress-bar bg-success" :style="{ width: t.progress + '%' }"></div></div>
                            <small class="text-muted">{{ showPct(t.progress, t.done) }}%</small>
                          </td>
                          <td @click.stop>
                            <DiffToggle v-if="t.supports_difficulty !== false"
                                        :on="t.difficulty_annotation !== false"
                                        :overridden="t.difficulty_override !== null && t.difficulty_override !== undefined"
                                        inherit="team default"
                                        @toggle="setDifficulty([t.task_id], '', $event)"
                                        @clear="setDifficulty([t.task_id], '', null)" />
                            <span v-else class="text-muted text-xs">—</span>
                          </td>
                          <td class="text-end text-nowrap" @click.stop>
                            <button class="btn btn-sm btn-outline-primary me-1" title="Assign annotators"
                                    @click="openAssign([t.task_id])">
                              <i class="bi bi-person-plus"></i>
                            </button>
                            <button v-if="holdersOf(t).length"
                                    class="btn btn-sm btn-outline-secondary"
                                    title="Take this task back from everyone" @click="unassignTask(t)">
                              <i class="bi bi-person-dash"></i>
                            </button>
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
              <p v-if="!tasksByLanguage.length" class="text-muted small mb-0">No tasks yet — load prompts into the pool first.</p>
            </div>
          </div>

          <!-- ── All tasks ── -->
          <div v-show="tasksSubTab === 'all'">
            <div class="bg-white p-4 rounded shadow-sm border">
              <div class="d-flex flex-wrap justify-content-between align-items-center mb-3 gap-2">
                <div>
                  <h5 class="fw-bold text-dark mb-1">All tasks</h5>
                  <p class="text-muted text-xs mb-0">
                    One task per language &amp; class. A task can be shared by several annotators —
                    every prompt is still done by exactly one person. Click a row to open it,
                    tick rows to assign them together.
                  </p>
                </div>
                <div class="d-flex gap-2">
                  <template v-if="selectedTasks.length">
                    <button class="btn btn-sm btn-outline-success"
                            title="Annotators must label difficulty on the ticked tasks"
                            @click="setDifficulty(selectedTasks, '', true)">
                      <i class="bi bi-toggle-on me-1"></i>Difficulty On
                    </button>
                    <button class="btn btn-sm btn-outline-secondary"
                            title="Hide the difficulty step on the ticked tasks"
                            @click="setDifficulty(selectedTasks, '', false)">
                      <i class="bi bi-toggle-off me-1"></i>Difficulty Off
                    </button>
                    <button class="btn btn-sm btn-outline-secondary"
                            title="Remove the ticked tasks' own switch — they follow their language again"
                            @click="setDifficulty(selectedTasks, '', null)">
                      <i class="bi bi-magic me-1"></i>Difficulty Auto
                    </button>
                  </template>
                  <button class="btn btn-sm btn-primary" :disabled="!selectedTasks.length"
                          @click="openAssign(selectedTasks)">
                    <i class="bi bi-person-plus me-1"></i>Assign
                    <span v-if="selectedTasks.length" class="badge bg-white text-primary ms-1">{{ selectedTasks.length }}</span>
                  </button>
                  <button class="btn btn-sm btn-outline-secondary" @click="loadTasks">
                    <i class="bi bi-arrow-clockwise"></i>
                  </button>
                </div>
              </div>

              <div class="d-flex flex-wrap gap-2 align-items-center mb-3">
                <select v-model="taskFilters.language" class="form-select form-select-sm w-auto">
                  <option value="">All languages</option>
                  <option v-for="l in taskLanguages" :key="l" :value="l">{{ l }}</option>
                </select>
                <select v-model="taskFilters.class" class="form-select form-select-sm w-auto">
                  <option value="">All classes</option>
                  <option v-for="c in taskClasses" :key="c" :value="c">Class {{ c }}</option>
                </select>
                <select v-model="taskFilters.state" class="form-select form-select-sm w-auto">
                  <option value="">Any state</option>
                  <option v-for="s in taskStates" :key="s" :value="s">{{ s }}</option>
                </select>
                <select v-model="taskFilters.annotator" class="form-select form-select-sm w-auto">
                  <option value="">Any annotator</option>
                  <option value="none">Unassigned</option>
                  <option v-for="a in annotators" :key="a.rater_id" :value="String(a.rater_id)">{{ a.name }}</option>
                </select>
                <input v-model="taskFilters.q" class="form-control form-control-sm" style="width:220px"
                       placeholder="Task ID, language, class, holder…">
                <button class="btn btn-sm btn-outline-secondary" @click="resetTaskFilters">Clear</button>
                <span class="ms-auto text-xs text-muted">{{ shownTasks.length }} of {{ taskTotals.tasks || 0 }} task(s)</span>
              </div>

              <div class="table-responsive">
                <table class="table table-hover align-middle">
                  <thead class="table-light">
                    <tr>
                      <th style="width:34px">
                        <input class="form-check-input" type="checkbox"
                               :checked="allShownSelected" @change="toggleSelectAll">
                      </th>
                      <th style="width:90px">Task ID</th><th>Language</th><th>Class</th>
                      <th>Assigned to</th><th>State</th>
                      <th class="text-end">Prompts</th><th class="text-end">Done</th>
                      <th class="text-end">In progress</th><th class="text-end">Available</th>
                      <th style="width:170px">Progress</th><th style="width:120px" title="Whether this kind of work requires its final label">Final label</th>
                      <th style="width:110px"></th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="t in shownTasks" :key="t.task_id" class="cursor-pointer" @click="openTask(t.task_id)">
                      <td @click.stop>
                        <input class="form-check-input" type="checkbox"
                               :checked="selectedTasks.includes(t.task_id)" @change="toggleTaskPick(t.task_id)">
                      </td>
                      <td><span class="task-id-badge">#{{ t.task_id }}</span></td>
                      <td class="fw-semibold text-dark">{{ t.language }}</td>
                      <td>Class {{ t.class }}</td>
                      <td>
                        <div v-if="holdersOf(t).length" class="d-flex flex-wrap gap-1 align-items-center">
                          <span v-for="a in holdersOf(t)" :key="a.rater_id + '-' + (a.category || '')"
                                class="holder-chip" :title="holderTitle(a)">
                            <span class="holder-initial">{{ initialOf(a.name) }}</span>{{ a.name
                            }}<em v-if="a.category">{{ a.category }}</em>
                          </span>
                        </div>
                        <span v-else class="badge bg-danger-subtle text-danger rounded-pill">Unassigned</span>
                      </td>
                      <td><span class="badge rounded-pill" :class="stateBadge(t.state)">{{ t.state }}</span></td>
                      <td class="text-end">{{ t.total.toLocaleString() }}</td>
                      <td class="text-end text-success fw-semibold">{{ t.done.toLocaleString() }}</td>
                      <td class="text-end">{{ t.claimed.toLocaleString() }}</td>
                      <td class="text-end text-muted">{{ t.available.toLocaleString() }}</td>
                      <td>
                        <div class="progress" style="height:6px"><div class="progress-bar bg-success" :style="{ width: t.progress + '%' }"></div></div>
                        <small class="text-muted">{{ showPct(t.progress, t.done) }}%</small>
                      </td>
                      <td @click.stop>
                        <DiffToggle v-if="t.supports_difficulty !== false" :on="t.difficulty_annotation !== false"
                                    :overridden="t.difficulty_override !== null && t.difficulty_override !== undefined"
                                    inherit="team default"
                                    @toggle="setDifficulty([t.task_id], '', $event)"
                                    @clear="setDifficulty([t.task_id], '', null)" />
                        <span v-else class="text-muted text-xs">—</span>
                      </td>
                      <td class="text-end text-nowrap" @click.stop>
                        <button class="btn btn-sm btn-outline-dark me-1" title="Preview the annotator view of this task"
                                @click="openPreview(t)"><i class="bi bi-eye"></i></button>
                        <button class="btn btn-sm btn-outline-primary me-1" title="Assign annotators"
                                @click="openAssign([t.task_id])"><i class="bi bi-person-plus"></i></button>
                        <button v-if="holdersOf(t).length"
                                class="btn btn-sm btn-outline-secondary" title="Take this task back from everyone"
                                @click="unassignTask(t)"><i class="bi bi-person-dash"></i></button>
                      </td>
                    </tr>
                    <tr v-if="!shownTasks.length"><td colspan="13" class="text-center text-muted py-4">Nothing matches those filters.</td></tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </template>
      </div>

      <!-- ══════════════════ ANNOTATORS ══════════════════ -->
      <div v-else-if="tab === 'annotators'" class="tab-pane-active">
        <!-- Sub-tabs: the team's members vs. the org-wide signup approval queue (same pill subnav as the Tasks tab) -->
        <div class="d-flex justify-content-center align-items-center gap-3 flex-wrap mb-4">
          <div class="tasks-subnav d-inline-flex align-items-center">
            <button type="button" @click="annotSubTab = 'members'"
                    :class="['subnav-btn', { active: annotSubTab === 'members' }]">
              <i class="bi bi-people-fill"></i><span>Team Members</span>
              <span class="subnav-badge">{{ shownAnnotators.length }}</span>
            </button>
            <button type="button" @click="annotSubTab = 'pending'; loadPending()"
                    :class="['subnav-btn', { active: annotSubTab === 'pending' }]">
              <i class="bi bi-person-plus-fill"></i><span>Pending Approval</span>
              <span v-if="pendingSignups.length" class="subnav-badge">{{ pendingSignups.length }}</span>
            </button>
          </div>
        </div>

        <!-- Approval queue: signups that belong to no team yet -->
        <div v-if="annotSubTab === 'pending'" class="card shadow-sm border">
          <div class="card-header bg-white py-3 d-flex flex-wrap align-items-center justify-content-between gap-2">
            <div>
              <h3 class="fw-bold text-dark m-0 fs-5">Waiting to join a team</h3>
              <small class="text-muted">Everyone who signed up and has not been let into any team yet.
                Approving adds them to <b>this</b> team; other teams' admins see the same queue.</small>
            </div>
            <button class="btn btn-outline-secondary btn-sm" :disabled="pendingLoading" @click="loadPending">
              <i class="bi bi-arrow-clockwise me-1"></i>Refresh
            </button>
          </div>
          <div class="table-responsive">
            <table class="table align-middle mb-0">
              <thead>
                <tr class="text-xs text-uppercase text-secondary">
                  <th class="ps-3">Name</th><th>Email</th><th>Age</th><th>Gender</th><th class="text-end pe-3">Action</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="p in pendingSignups" :key="p.rater_id">
                  <td class="ps-3 fw-semibold text-dark">{{ p.name }}</td>
                  <td class="text-muted">{{ p.email }}</td>
                  <td>{{ p.age }}</td>
                  <td class="text-capitalize">{{ p.gender }}</td>
                  <td class="text-end pe-3">
                    <button class="btn btn-sm btn-success" :disabled="approving === p.rater_id"
                            @click="approveSignup(p)">
                      <span v-if="approving === p.rater_id" class="spinner-border spinner-border-sm me-1"></span>
                      <i v-else class="bi bi-person-check me-1"></i>Approve into this team
                    </button>
                  </td>
                </tr>
                <tr v-if="!pendingSignups.length">
                  <td colspan="5" class="text-center text-muted py-5">
                    {{ pendingLoading ? 'Loading…' : 'Nobody is waiting right now — new signups appear here.' }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Stale-annotator alert -->
        <div v-if="annotSubTab === 'members' && staleRaters.length" class="alert stale-alert d-flex align-items-center gap-2 shadow-sm mb-3">
          <i class="bi bi-exclamation-triangle-fill fs-5"></i>
          <div class="flex-grow-1">
            <strong>{{ staleRaters.length }}</strong>
            annotator{{ staleRaters.length > 1 ? 's have' : ' has' }} tasks assigned but no activity in {{ STALE_DAYS }}+ days.
          </div>
          <button class="btn btn-sm btn-warning flex-shrink-0 fw-semibold" :disabled="bulkNudging" @click="remindAllStale">
            <span v-if="bulkNudging" class="spinner-border spinner-border-sm me-1"></span>
            <i v-else class="bi bi-bell-fill me-1"></i>Remind all
          </button>
          <button class="btn btn-sm btn-outline-dark flex-shrink-0" @click="showStaleOnly = !showStaleOnly">
            <i :class="['bi me-1', showStaleOnly ? 'bi-list-ul' : 'bi-funnel-fill']"></i>
            {{ showStaleOnly ? 'Show all' : 'Show only these' }}
          </button>
        </div>

        <div v-show="annotSubTab === 'members'" class="card shadow-sm border">
          <!-- Toolbar -->
          <div class="card-header bg-white py-3">
            <div class="d-flex flex-wrap align-items-center gap-3">
              <div class="me-auto">
                <h3 class="fw-bold text-dark m-0 fs-5">Annotators &amp; Task Assignment</h3>
                <small class="text-muted">Tasks can be shared — every prompt still goes to exactly one annotator.</small>
              </div>

              <div class="search-wrap position-relative">
                <i class="bi bi-search search-icon"></i>
                <input v-model="raterSearch" type="text" class="form-control form-control-sm ps-5"
                       placeholder="Search name or email…">
                <button v-if="raterSearch" class="btn btn-sm search-clear" @click="raterSearch = ''" title="Clear">
                  <i class="bi bi-x-lg"></i>
                </button>
              </div>

              <button class="btn btn-outline-secondary btn-sm d-inline-flex align-items-center gap-1"
                      @click="toggleMenu('exports', $event, 280)" title="Download reports">
                <i class="bi bi-download"></i> Exports <i class="bi bi-chevron-down text-xs"></i>
              </button>
              <button class="btn btn-outline-secondary btn-sm d-inline-flex align-items-center gap-1"
                      @click="toggleMenu('messages', $event, 240)" title="Message annotators">
                <i class="bi bi-chat-dots"></i> Messages <i class="bi bi-chevron-down text-xs"></i>
              </button>

              <div class="form-check form-switch mb-0">
                <input class="form-check-input" type="checkbox" role="switch" id="showAllRaters" v-model="showInactive">
                <label class="form-check-label text-xs text-secondary user-select-none" for="showAllRaters">Show inactive</label>
              </div>
            </div>
          </div>

          <!-- Date window + what it adds up to -->
          <div class="filter-bar border-top border-bottom">
            <div class="d-flex flex-wrap align-items-center gap-3">
              <div class="d-flex align-items-center gap-2">
                <i class="bi bi-calendar3 text-secondary"></i>
                <div class="btn-group btn-group-sm">
                  <button v-for="pr in activityPresets" :key="pr.label" class="btn"
                          :class="windowPreset === pr.label ? 'btn-primary' : 'btn-outline-secondary'"
                          @click="applyPreset(pr)">{{ pr.label }}</button>
                </div>
              </div>
              <div class="d-flex align-items-center gap-1">
                <input type="date" v-model="activityFrom" class="form-control form-control-sm date-input" title="From">
                <span class="text-muted text-xs">→</span>
                <input type="date" v-model="activityTo" class="form-control form-control-sm date-input" title="To">
                <button class="btn btn-sm btn-primary ms-1" :disabled="activityLoading" @click="loadActivityWindow">
                  <span v-if="activityLoading" class="spinner-border spinner-border-sm"></span>
                  <span v-else>Apply</span>
                </button>
              </div>

              <div v-if="activityWindow" class="ms-auto d-flex align-items-center gap-3 stat-strip">
                <div class="stat" title="Prompts completed in this window — what payment is based on">
                  <div class="stat-val text-success">{{ activityWindow.totals.completed.toLocaleString() }}</div>
                  <div class="stat-lbl">payable</div>
                </div>
                <div class="stat" title="Prompts handed back as unusable — not paid">
                  <div class="stat-val" :class="activityWindow.totals.flagged ? 'text-warning' : 'text-muted'">
                    {{ activityWindow.totals.flagged }}</div>
                  <div class="stat-lbl">flagged</div>
                </div>
                <div class="stat" title="Prompts whose text the annotator corrected">
                  <div class="stat-val text-primary">{{ activityWindow.totals.edited }}</div>
                  <div class="stat-lbl">edited</div>
                </div>
                <div class="stat" title="Claimed but not yet finished">
                  <div class="stat-val text-muted">{{ activityWindow.totals.holding }}</div>
                  <div class="stat-lbl">holding</div>
                </div>
                <div class="stat"><div class="stat-val">{{ activityWindow.totals.hours }}</div><div class="stat-lbl">hours</div></div>
                <div class="stat"><div class="stat-val">{{ activityWindow.totals.active_annotators }}</div><div class="stat-lbl">active</div></div>
              </div>
            </div>

            <div class="d-flex flex-wrap align-items-center gap-2 mt-2 pt-2 border-top">
              <span class="text-xs fw-bold text-secondary text-uppercase">
                By type<span v-if="!activityWindow" class="text-muted fw-normal text-lowercase"> · all time</span>
              </span>
              <span class="type-chip" title="ASR text review: edit the prompt and label its difficulty">
                ASR text review<b>{{ (stats.done || 0).toLocaleString() }}</b>
              </span>
              <button class="btn btn-sm btn-link text-decoration-none p-0 ms-auto text-xs"
                      @click="exportSimple('/pool/admin/export_rater_activity_csv', 'asr_annotator_days.csv', 'Per-day report')">
                <i class="bi bi-download me-1"></i>Task-wise CSV
              </button>
            </div>
          </div>

          <!-- The table -->
          <div class="table-responsive">
            <table class="table table-hover align-middle mb-0 rater-table">
              <thead>
                <tr>
                  <th class="ps-3 sortable-th" @click="sortRaters('name')">Annotator <i :class="['bi', sortIcon('name')]"></i></th>
                  <th class="sortable-th" style="width: 230px;" @click="sortRaters('assigned')">Assigned tasks <i :class="['bi', sortIcon('assigned')]"></i></th>
                  <th class="sortable-th" style="width: 185px;" @click="sortRaters('lastactive')">Status <i :class="['bi', sortIcon('lastactive')]"></i></th>
                  <th class="sortable-th text-end" style="width: 240px;" @click="sortRaters('completed')">
                    {{ activityWindow ? 'In period / All' : 'Prompts done' }} <i :class="['bi', sortIcon('completed')]"></i>
                  </th>
                  <th class="text-end pe-3" style="width: 130px;">Actions</th>
                </tr>
              </thead>
              <tbody>
                <template v-for="a in shownAnnotators" :key="a.rater_id">
                  <tr :class="{ 'stale-row': isStale(a), 'row-open': expandedRaters.includes(a.rater_id) }">
                    <td class="ps-3">
                      <div class="d-flex align-items-center gap-2" style="min-width: 0;">
                        <div class="avatar-circle flex-shrink-0" :class="{ 'avatar-off': a.account_active === false }">
                          {{ (a.name || '?').charAt(0).toUpperCase() }}
                        </div>
                        <div style="min-width: 0;">
                          <div class="fw-semibold text-dark text-truncate" style="max-width: 260px;" :title="a.name">{{ a.name }}</div>
                          <div class="text-muted text-xs text-truncate" style="max-width: 260px;" :title="a.email">
                            {{ a.email }}
                            <span v-if="a.gender || a.age" class="text-body-tertiary">· {{ a.gender }}{{ a.age ? ', ' + a.age : '' }}</span>
                          </div>
                        </div>
                      </div>
                    </td>

                    <td>
                      <div v-if="(a.assigned_task_ids || []).length" class="d-flex flex-wrap gap-1 assigned-chip-wrap">
                        <span v-for="tid in a.assigned_task_ids.slice(0, 4)" :key="tid"
                              class="badge rounded-pill bg-primary-subtle text-primary border border-primary-subtle cursor-pointer"
                              @click="openTask(tid)">#{{ tid }}</span>
                        <span v-if="a.assigned_task_ids.length > 4"
                              class="badge rounded-pill bg-secondary-subtle text-secondary border"
                              :title="a.assigned_task_ids.join(', ')">+{{ a.assigned_task_ids.length - 4 }}</span>
                      </div>
                      <span v-else class="text-muted text-xs fst-italic">Unassigned</span>
                    </td>

                    <td>
                      <div class="d-flex flex-column gap-1 align-items-start">
                        <span v-if="a.account_active === false" class="status-pill is-off" title="Deactivated — cannot log in">
                          <i class="bi bi-slash-circle-fill"></i> Deactivated
                        </span>
                        <span v-else class="status-pill" :class="raterStatusClass(a)">
                          <i :class="['bi', raterStatusIcon(a)]"></i> {{ raterStatus(a) }}
                        </span>
                        <span class="text-xs" :class="isStale(a) ? 'text-warning-emphasis fw-semibold' : 'text-muted'"
                              :title="fmtDate(a.last_active)">
                          <i v-if="isStale(a)" class="bi bi-exclamation-triangle-fill me-1"></i>
                          {{ a.last_active ? timeAgo(a.last_active) : 'never active' }}
                        </span>
                      </div>
                    </td>

                    <td class="text-end tasks-cell">
                      <div class="d-flex align-items-baseline justify-content-end gap-1">
                        <span class="tasks-num">{{ (activityWindow ? (a.completed || 0) : (a.completed || 0)).toLocaleString() }}</span>
                        <span v-if="activityWindow" class="text-muted text-xs">/ {{ (allTimeFor(a.rater_id)).toLocaleString() }}</span>
                      </div>
                      <div v-if="a.flagged || a.edited" class="d-flex gap-1 justify-content-end mt-1">
                        <span v-if="a.flagged" class="stat-pill warn" :title="a.flagged + ' flagged — not paid'">{{ a.flagged }} flagged</span>
                        <span v-if="a.edited" class="stat-pill info" :title="a.edited + ' prompts whose text was corrected'">{{ a.edited }} edited</span>
                      </div>
                      <button class="drill-btn mt-1" @click="toggleRaterTasks(a)">
                        <i class="bi" :class="expandedRaters.includes(a.rater_id) ? 'bi-chevron-up' : 'bi-chevron-down'"></i>
                        {{ expandedRaters.includes(a.rater_id) ? 'Hide tasks' : 'Task-wise' }}
                      </button>
                    </td>

                    <td class="text-end pe-3">
                      <div class="d-inline-flex gap-1 justify-content-end align-items-center flex-nowrap">
                        <button class="rater-action-btn btn btn-sm"
                                :class="(a.assigned_task_ids || []).length ? 'btn-primary' : 'btn-outline-primary'"
                                :title="(a.assigned_task_ids || []).length ? 'Edit the tasks assigned to ' + a.name : 'Assign tasks to ' + a.name"
                                @click="openAssign([], a.rater_id)">
                          <i :class="['bi', (a.assigned_task_ids || []).length ? 'bi-pencil-square' : 'bi-plus-lg']"></i>
                        </button>
                        <button class="rater-action-btn btn btn-sm btn-outline-secondary"
                                :title="'Message ' + a.name" @click="openMessage(a)">
                          <i class="bi bi-chat-dots"></i>
                        </button>
                        <button class="rater-action-btn btn btn-sm btn-outline-primary"
                                :title="'Open the full record for ' + a.name" @click="openAnnotator(a)">
                          <i class="bi bi-person-lines-fill"></i>
                        </button>
                        <button class="rater-action-btn btn btn-sm btn-outline-success"
                                :title="'Export the work of ' + a.name + ' (original and submission, prompt by prompt)'"
                                @click="exportSimple(`/pool/admin/export_submissions_csv&annotator=${a.rater_id}&state=submitted`,
                                                     `asr_${a.name}_submissions.csv`, a.name + ' submissions')">
                          <i class="bi bi-file-earmark-code"></i>
                        </button>
                        <button class="rater-action-btn btn btn-sm btn-outline-warning"
                                :title="'Send a reminder to ' + a.name" @click="nudgeRater(a)">
                          <i class="bi bi-bell"></i>
                        </button>
                        <button class="rater-action-btn btn btn-sm btn-outline-secondary"
                                :title="'Languages & pull size for ' + a.name" @click="openEdit(a)">
                          <i class="bi bi-gear"></i>
                        </button>
                        <button v-if="a.account_active === false" class="rater-action-btn btn btn-sm btn-outline-success"
                                :title="'Reactivate ' + a.name + ' (lets them sign in again)'"
                                @click="reactivateRater(a)">
                          <i class="bi bi-arrow-counterclockwise"></i>
                        </button>
                        <button v-else class="rater-action-btn btn btn-sm btn-outline-danger"
                                :title="'Deactivate ' + a.name + ' (frees their tasks and unfinished prompts)'"
                                @click="removeModal = { rater: a, confirm: '' }">
                          <i class="bi bi-person-dash"></i>
                        </button>
                      </div>
                    </td>
                  </tr>

                  <!-- Task-wise drill-down -->
                  <tr v-if="expandedRaters.includes(a.rater_id)" class="drill-row">
                    <td colspan="5" class="p-0">
                      <div class="drill-panel">
                        <div class="d-flex align-items-center mb-2 gap-2">
                          <span class="text-xs fw-bold text-secondary text-uppercase">{{ a.name }} · prompts per task</span>
                          <button class="btn btn-sm btn-link text-decoration-none p-0 ms-auto text-xs"
                                  @click="exportSimple(`/pool/admin/export_submissions_csv&annotator=${a.rater_id}&state=submitted`,
                                                       `asr_${a.name}_submissions.csv`, a.name + ' submissions')">
                            <i class="bi bi-download me-1"></i>CSV
                          </button>
                        </div>
                        <div v-if="raterTasksLoading === a.rater_id" class="text-center py-3">
                          <span class="spinner-border spinner-border-sm text-secondary"></span>
                        </div>
                        <table v-else class="table table-sm mb-0 bg-white border rounded drill-table">
                          <thead>
                            <tr>
                              <th style="width: 80px;">Task</th>
                              <th style="width: 110px;">Language</th>
                              <th style="width: 80px;">Class</th>
                              <th>Assigned</th>
                              <th class="text-end" style="width: 150px;">Completed</th>
                              <th class="text-end" style="width: 70px;">Flagged</th>
                              <th class="text-end" style="width: 70px;">Edited</th>
                              <th class="text-end" style="width: 80px;">Holding</th>
                              <th class="text-end" style="width: 70px;">Hours</th>
                              <th class="text-end" style="width: 140px;">Last activity</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr v-for="t in (raterTasks[a.rater_id] || [])" :key="t.task_id">
                              <td><a href="#" class="fw-semibold text-decoration-none" @click.prevent="openTask(t.task_id)">#{{ t.task_id }}</a></td>
                              <td><span class="badge rounded-pill bg-secondary-subtle text-secondary border">{{ t.language || '—' }}</span></td>
                              <td>Class {{ t.class }}</td>
                              <td>
                                <span v-if="t.is_assigned" class="badge bg-success-subtle text-success rounded-pill">holds it</span>
                                <span v-else class="text-muted text-xs">worked earlier</span>
                              </td>
                              <td class="text-end">
                                <div class="d-flex align-items-center gap-2 justify-content-end">
                                  <span class="fw-semibold text-nowrap">{{ t.completed }}<span v-if="t.task_total" class="text-muted"> / {{ t.task_total }}</span></span>
                                  <div v-if="t.task_total" class="progress" style="height: 5px; width: 52px;">
                                    <div class="progress-bar" :class="t.completed >= t.task_total ? 'bg-success' : 'bg-warning'"
                                         :style="{ width: (100 * t.completed / t.task_total) + '%' }"></div>
                                  </div>
                                </div>
                              </td>
                              <td class="text-end" :class="t.flagged ? 'text-warning fw-semibold' : 'text-muted'">{{ t.flagged }}</td>
                              <td class="text-end" :class="t.edited ? 'text-primary fw-semibold' : 'text-muted'">{{ t.edited }}</td>
                              <td class="text-end text-muted">{{ t.claimed }}</td>
                              <td class="text-end">{{ t.hours }}</td>
                              <td class="text-end text-muted text-xs">{{ t.last_active_ist || '—' }}</td>
                            </tr>
                            <tr v-if="!(raterTasks[a.rater_id] || []).length">
                              <td colspan="10" class="text-center text-muted py-3">No tasks touched yet.</td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                    </td>
                  </tr>
                </template>
                <tr v-if="!shownAnnotators.length">
                  <td colspan="5" class="text-center text-muted py-5 bg-white">No matching annotators found.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- ══════════════════ SUBMISSIONS ══════════════════ -->
      <div v-else-if="tab === 'submissions'" class="tab-pane-active">
        <div class="bg-white p-4 rounded shadow-sm border">
          <div class="d-flex flex-wrap justify-content-between align-items-center mb-3 gap-2">
            <div>
              <h5 class="fw-bold text-dark mb-1">Submissions</h5>
              <p class="text-muted text-xs mb-0">
                Every prompt and the submission made against it. Click a row to open the full record.
              </p>
            </div>
            <div class="d-flex gap-2">
              <button class="btn btn-sm btn-outline-secondary" @click="exportSubmissions">
                <i class="bi bi-filetype-csv me-1"></i>Export this view
              </button>
              <button class="btn btn-sm btn-primary" @click="exportOpen = true">
                <i class="bi bi-file-earmark-spreadsheet me-1"></i>Full export
              </button>
            </div>
          </div>

          <div class="filter-bar border-top border-bottom py-3 mb-3">
            <div class="d-flex flex-wrap gap-2 align-items-center">
              <select v-model="subFilters.task_id" class="form-select form-select-sm w-auto" @change="loadSubmissions(1)">
                <option value="">All tasks</option>
                <option v-for="t in subMeta.tasks" :key="t.task_id" :value="String(t.task_id)">
                  #{{ t.task_id }} — {{ t.label }}
                </option>
              </select>
              <select v-model="subFilters.language" class="form-select form-select-sm w-auto" @change="loadSubmissions(1)">
                <option value="">All languages</option>
                <option v-for="l in subMeta.languages" :key="l" :value="l">{{ l }}</option>
              </select>
              <select v-model="subFilters.class" class="form-select form-select-sm w-auto" @change="loadSubmissions(1)">
                <option value="">All classes</option>
                <option v-for="c in subMeta.classes" :key="c" :value="c">Class {{ c }}</option>
              </select>
              <select v-model="subFilters.category" class="form-select form-select-sm w-auto" @change="loadSubmissions(1)">
                <option value="">All categories</option>
                <option v-for="c in subMeta.categories" :key="c" :value="c">{{ c }}</option>
              </select>
              <select v-model="subFilters.annotator" class="form-select form-select-sm w-auto" @change="loadSubmissions(1)">
                <option value="">Any annotator</option>
                <option v-for="a in subMeta.annotators" :key="a.rater_id" :value="String(a.rater_id)">{{ a.name }}</option>
              </select>
              <select v-model="subFilters.state" class="form-select form-select-sm w-auto" @change="loadSubmissions(1)">
                <option value="submitted">Submitted only</option>
                <option value="completed">Completed</option>
                <option value="flagged">Flagged</option>
                <option value="pending">Not submitted yet</option>
                <option value="claimed">In progress</option>
                <option value="available">Untouched</option>
                <option value="">Everything</option>
              </select>
              <select v-model="subFilters.difficulty" class="form-select form-select-sm w-auto" @change="loadSubmissions(1)">
                <option value="">Any difficulty</option>
                <option v-for="d in difficulties" :key="d" :value="d">{{ d }}</option>
              </select>
            </div>

            <div class="d-flex flex-wrap gap-2 align-items-center mt-2">
              <div class="d-flex align-items-center gap-1">
                <i class="bi bi-calendar3 text-secondary"></i>
                <input type="date" v-model="subFilters.from" class="form-control form-control-sm date-input"
                       title="Submitted from" @change="loadSubmissions(1)">
                <span class="text-muted text-xs">-&gt;</span>
                <input type="date" v-model="subFilters.to" class="form-control form-control-sm date-input"
                       title="Submitted to" @change="loadSubmissions(1)">
              </div>
              <div class="form-check form-check-inline ms-1">
                <input class="form-check-input" type="checkbox" id="subEdited" v-model="subFilters.edited"
                       true-value="1" false-value="" @change="loadSubmissions(1)">
                <label class="form-check-label text-xs" for="subEdited">text edited</label>
              </div>
              <div class="form-check form-check-inline">
                <input class="form-check-input" type="checkbox" id="subFlagged" v-model="subFilters.flagged"
                       true-value="1" false-value="" @change="loadSubmissions(1)">
                <label class="form-check-label text-xs" for="subFlagged">flagged</label>
              </div>
              <div class="form-check form-check-inline">
                <input class="form-check-input" type="checkbox" id="subChanged" v-model="subFilters.changed"
                       true-value="1" false-value="" @change="loadSubmissions(1)">
                <label class="form-check-label text-xs" for="subChanged">difficulty changed</label>
              </div>
              <input v-model="subFilters.q" class="form-control form-control-sm" style="width:220px"
                     placeholder="Search text or prompt ID…" @keyup.enter="loadSubmissions(1)">
              <button class="btn btn-sm btn-outline-secondary" @click="loadSubmissions(1)"><i class="bi bi-search"></i></button>
              <button class="btn btn-sm btn-outline-secondary" @click="resetSubFilters">Clear</button>
              <span class="ms-auto text-xs text-muted">{{ subTotal.toLocaleString() }} row(s)</span>
            </div>
          </div>

          <div v-if="subLoading" class="text-center py-5"><span class="spinner-border text-secondary"></span></div>
          <template v-else>
            <div class="table-responsive">
              <table class="table table-sm table-hover align-middle">
                <thead class="table-light">
                  <tr>
                    <th style="width:70px">Task</th><th style="width:70px">Prompt</th>
                    <th>Language</th><th>Cl</th><th>Category</th>
                    <th>Submission</th><th>Difficulty</th><th>State</th>
                    <th>Annotator</th><th class="text-nowrap">When (IST)</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="it in submissions" :key="it.id" class="cursor-pointer" @click="openItem(it.id)">
                    <td><span class="task-id-badge">#{{ it.task_id }}</span></td>
                    <td class="text-muted">{{ it.id }}</td>
                    <td>{{ it.language }}</td>
                    <td>{{ it.class }}</td>
                    <td class="text-muted">{{ it.category }}</td>
                    <td class="cell-text" :dir="rtl(it.language) ? 'rtl' : 'ltr'">
                      <div>{{ trim(it.text) }}</div>
                      <div v-if="it.is_edited" class="text-xs text-muted-2">was: <s>{{ trim(it.original_text, 60) }}</s></div>
                      <div v-if="it.is_flagged" class="text-xs text-warning">flagged: {{ it.flag_reason }}</div>
                    </td>
                    <td>
                      <span v-if="it.final_difficulty" class="badge" :class="badgeFor(it.final_difficulty)">{{ it.final_difficulty }}</span>
                      <span v-else class="text-muted text-xs">{{ it.source_difficulty || '—' }}</span>
                      <i v-if="it.difficulty_changed" class="bi bi-arrow-left-right text-primary ms-1" title="changed by the annotator"></i>
                    </td>
                    <td>
                      <span class="badge" :class="statusBadge(it.status)">{{ it.status }}</span>
                      <span v-if="it.is_edited" class="badge bg-primary-subtle text-primary ms-1">edited</span>
                    </td>
                    <td class="text-xs text-muted">{{ it.annotator || '—' }}</td>
                    <td class="text-xs text-muted text-nowrap">{{ it.completed_at_ist || '—' }}</td>
                  </tr>
                  <tr v-if="!submissions.length"><td colspan="10" class="text-center text-muted py-4">Nothing matches those filters.</td></tr>
                </tbody>
              </table>
            </div>
            <div v-if="subPages > 1" class="d-flex justify-content-center align-items-center gap-3 mt-2">
              <button class="btn btn-sm btn-outline-secondary" :disabled="subPage <= 1" @click="loadSubmissions(subPage - 1)">Previous</button>
              <span class="text-xs text-muted">Page {{ subPage }} of {{ subPages }}</span>
              <button class="btn btn-sm btn-outline-secondary" :disabled="subPage >= subPages" @click="loadSubmissions(subPage + 1)">Next</button>
            </div>
          </template>
        </div>
      </div>

      <!-- ══════════════════ ACTIVITY LOG ══════════════════ -->
      <div v-else-if="tab === 'activity'" class="tab-pane-active">
        <div class="bg-white p-4 rounded shadow-sm border">
          <div class="d-flex flex-wrap justify-content-between align-items-center mb-3 gap-2">
            <div>
              <h5 class="fw-bold text-dark mb-1">Activity log</h5>
              <p class="text-muted text-xs mb-0">
                Every pull and every submission, newest first, in IST.
              </p>
            </div>
            <div class="d-flex gap-2 align-items-center">
              <select v-model.number="activityDays" class="form-select form-select-sm w-auto" @change="loadActivity(1)">
                <option :value="1">Last 24 hours</option>
                <option :value="7">Last 7 days</option>
                <option :value="30">Last 30 days</option>
                <option :value="365">Everything</option>
              </select>
              <button class="btn btn-sm btn-outline-secondary" title="Refresh" @click="loadActivity(actPage)">
                <i class="bi bi-arrow-clockwise"></i>
              </button>
              <button class="btn btn-sm btn-outline-secondary"
                      @click="exportSimple(`/pool/admin/export_activity_csv&days=${activityDays}`, 'asr_activity.csv', 'Activity log')">
                <i class="bi bi-filetype-csv me-1"></i>Export
              </button>
            </div>
          </div>

          <!-- What happened in this window — each chip is also a filter -->
          <div class="d-flex flex-wrap gap-2 align-items-center mb-3">
            <button type="button" class="act-chip"
                    :class="{ active: !actFilters.event }" @click="setActEvent('')">
              All <b>{{ actSummaryTotal.toLocaleString() }}</b>
            </button>
            <button v-for="ev in actEventTypes" :key="ev" type="button"
                    class="act-chip" :class="{ active: actFilters.event === ev }"
                    @click="setActEvent(ev)">
              <span class="badge" :class="eventBadge(ev)">{{ ev }}</span>
              <b>{{ (actSummary[ev] || 0).toLocaleString() }}</b>
            </button>
          </div>

          <div class="filter-bar border-top border-bottom py-2 mb-3">
            <div class="d-flex flex-wrap gap-2 align-items-center">
              <select v-model="actFilters.annotator" class="form-select form-select-sm w-auto" @change="loadActivity(1)">
                <option value="">Any annotator</option>
                <option v-for="a in annotators" :key="a.rater_id" :value="String(a.rater_id)">{{ a.name }}</option>
              </select>
              <select v-model="actFilters.language" class="form-select form-select-sm w-auto" @change="loadActivity(1)">
                <option value="">All languages</option>
                <option v-for="L in languages" :key="L.language" :value="L.language">{{ L.language }}</option>
              </select>
              <div class="position-relative">
                <input v-model="actFilters.q" class="form-control form-control-sm" style="width:230px"
                       placeholder="Prompt ID, task, annotator, detail…" @keyup.enter="loadActivity(1)">
              </div>
              <button class="btn btn-sm btn-outline-secondary" @click="loadActivity(1)"><i class="bi bi-search"></i></button>
              <button v-if="actFiltersDirty" class="btn btn-sm btn-outline-secondary" @click="resetActFilters">Clear</button>
              <span class="ms-auto text-xs text-muted">
                {{ actTotal.toLocaleString() }} event(s)<span v-if="actPages > 1"> · page {{ actPage }} of {{ actPages }}</span>
              </span>
            </div>
          </div>

          <div v-if="actLoading" class="text-center py-5"><span class="spinner-border text-secondary"></span></div>
          <div v-else-if="!activity.length" class="text-center text-muted py-5">
            <i class="bi bi-clock-history d-block fs-3 mb-2"></i>
            {{ actFiltersDirty ? 'Nothing matches those filters.' : 'Nothing has happened in this window yet.' }}
          </div>
          <template v-else>
            <div class="d-flex justify-content-end mb-2">
              <div class="btn-group btn-group-sm">
                <button :class="actView === 'grouped' ? 'btn btn-dark' : 'btn btn-outline-secondary'"
                        @click="actView = 'grouped'"><i class="bi bi-collection me-1"></i>Grouped</button>
                <button :class="actView === 'flat' ? 'btn btn-dark' : 'btn btn-outline-secondary'"
                        @click="actView = 'flat'"><i class="bi bi-list me-1"></i>Flat</button>
              </div>
            </div>

            <!-- Grouped: one section per day; bursts of the same kind collapse to a single row -->
            <div v-if="actView === 'grouped'">
              <div v-for="day in groupedActivity" :key="day.date" class="act-day">
                <div class="act-day-head">
                  <i class="bi bi-calendar3"></i>
                  <span class="fw-bold">{{ dayLabel(day.date) }}</span>
                  <span class="text-muted text-xs">{{ day.count }} event(s)</span>
                </div>
                <div class="act-day-body">
                  <template v-for="g in day.groups" :key="g.id">
                    <div v-if="g.items.length > 1" class="act-group">
                      <button type="button" class="act-group-row" @click="toggleActGroup(g.id)">
                        <i class="bi text-secondary" :class="expandedActGroups.includes(g.id) ? 'bi-chevron-down' : 'bi-chevron-right'"></i>
                        <span class="badge" :class="eventBadge(g.event)">{{ g.event }}</span>
                        <b class="act-count">× {{ g.items.length }}</b>
                        <span class="fw-semibold text-dark">{{ g.annotator || '—' }}</span>
                        <span class="text-muted text-xs">{{ g.language }} · Class {{ g.class }}</span>
                        <span v-if="groupSeconds(g)" class="text-muted text-xs">· {{ groupSeconds(g) }} spent</span>
                        <span class="ms-auto text-xs text-muted text-nowrap">{{ groupTimeRange(g) }}</span>
                      </button>
                      <div v-if="expandedActGroups.includes(g.id)" class="act-group-items">
                        <table class="table table-sm table-hover align-middle mb-0">
                          <tbody>
                            <tr v-for="(e, i) in g.items" :key="i" class="cursor-pointer" @click="openItem(e.item_id)">
                              <td style="width:70px" class="text-xs text-muted">{{ e.when_ist.slice(11, 16) }}</td>
                              <td style="width:90px" class="text-muted">#{{ e.item_id }}</td>
                              <td class="text-xs text-muted">{{ e.detail }}</td>
                              <td style="width:80px" class="text-end text-xs">{{ e.seconds != null ? e.seconds + 's' : '' }}</td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                    </div>
                    <div v-else class="act-single cursor-pointer" @click="openItem(g.items[0].item_id)">
                      <span class="text-xs text-muted act-time">{{ g.items[0].when_ist.slice(11, 16) }}</span>
                      <span class="badge" :class="eventBadge(g.event)">{{ g.event }}</span>
                      <span class="fw-semibold text-dark">{{ g.annotator || '—' }}</span>
                      <span class="text-muted">#{{ g.items[0].item_id }}</span>
                      <span class="text-muted text-xs">{{ g.language }} · Class {{ g.class }}</span>
                      <span v-if="g.items[0].detail" class="text-xs text-muted text-truncate" style="max-width: 260px;">{{ g.items[0].detail }}</span>
                      <span v-if="g.items[0].seconds != null" class="ms-auto text-xs text-muted">{{ g.items[0].seconds }}s</span>
                    </div>
                  </template>
                </div>
              </div>
            </div>

            <!-- Flat: the classic table -->
            <div v-else class="table-responsive">
              <table class="table table-sm table-hover align-middle">
                <thead class="table-light">
                  <tr><th>When (IST)</th><th>Event</th><th>Annotator</th><th>Prompt</th>
                      <th>Language</th><th>Class</th><th>Detail</th><th class="text-end">Seconds</th></tr>
                </thead>
                <tbody>
                  <tr v-for="(e, i) in activity" :key="i" class="cursor-pointer" @click="openItem(e.item_id)">
                    <td class="text-nowrap text-muted text-xs">{{ e.when_ist }}</td>
                    <td><span class="badge" :class="eventBadge(e.event)">{{ e.event }}</span></td>
                    <td>{{ e.annotator || '—' }}</td>
                    <td class="text-muted">#{{ e.item_id }}</td>
                    <td>{{ e.language }}</td>
                    <td>{{ e.class }}</td>
                    <td class="text-xs text-muted">{{ e.detail }}</td>
                    <td class="text-end text-xs">{{ e.seconds != null ? e.seconds : '' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-if="actPages > 1" class="d-flex justify-content-center align-items-center gap-2 mt-2 flex-wrap">
              <button class="btn btn-sm btn-outline-secondary" :disabled="actPage <= 1" @click="loadActivity(1)"
                      title="First page"><i class="bi bi-chevron-double-left"></i></button>
              <button class="btn btn-sm btn-outline-secondary" :disabled="actPage <= 1" @click="loadActivity(actPage - 1)">Previous</button>
              <span class="text-xs text-muted px-2">Page {{ actPage }} of {{ actPages }}</span>
              <button class="btn btn-sm btn-outline-secondary" :disabled="actPage >= actPages" @click="loadActivity(actPage + 1)">Next</button>
              <button class="btn btn-sm btn-outline-secondary" :disabled="actPage >= actPages" @click="loadActivity(actPages)"
                      title="Last page"><i class="bi bi-chevron-double-right"></i></button>
              <select :value="actPerPage" class="form-select form-select-sm w-auto ms-2"
                      @change="actPerPage = Number($event.target.value); loadActivity(1)">
                <option :value="50">50 / page</option>
                <option :value="100">100 / page</option>
                <option :value="200">200 / page</option>
              </select>
            </div>
          </template>
        </div>
      </div>

      <!-- ══════════════════ ADMIN ══════════════════ -->
      <div v-else-if="tab === 'admin'" class="tab-pane-active">
        <div class="row g-4">
          <div class="col-12 col-lg-6">
            <div class="bg-white p-4 rounded shadow-sm border h-100">
              <h5 class="fw-bold text-dark mb-2"><i class="bi bi-key-fill me-2 text-primary"></i>Today's signup PIN</h5>
              <p class="text-muted text-xs">New annotators need this PIN to create an account. It changes daily.</p>
              <div class="d-flex align-items-center gap-2">
                <code class="pin-box">{{ signupPin || '••••••••' }}</code>
                <button class="btn btn-sm btn-outline-secondary" @click="loadPin"><i class="bi bi-arrow-clockwise"></i></button>
                <button class="btn btn-sm btn-outline-secondary" :disabled="!signupPin" @click="copyPin">
                  <i class="bi bi-clipboard me-1"></i>{{ pinCopied ? 'Copied' : 'Copy' }}
                </button>
              </div>
              <p class="text-muted text-xs mb-0 mt-2">After signing up, new annotators wait in
                <b>Annotators → Pending approval</b> until you let them into the team.</p>
            </div>
          </div>

          <div class="col-12 col-lg-6">
            <div class="bg-white p-4 rounded shadow-sm border h-100">
              <h5 class="fw-bold text-dark mb-2"><i class="bi bi-download me-2 text-primary"></i>Reports</h5>
              <p class="text-muted text-xs">Every report covers the ASR team only.</p>
              <div class="d-grid gap-2">
                <button class="btn btn-sm btn-outline-primary" @click="exportOpen = true">
                  <i class="bi bi-file-earmark-spreadsheet me-1"></i>Full pool export (Excel / CSV)
                </button>
                <button class="btn btn-sm btn-outline-secondary"
                        @click="exportSimple('/pool/admin/export_tasks_csv', 'asr_task_list.csv', 'Task list')">
                  <i class="bi bi-list-task me-1"></i>Task list by language &amp; class
                </button>
                <button class="btn btn-sm btn-outline-secondary"
                        @click="exportSimple('/pool/admin/export_annotators_csv', 'asr_annotators.csv', 'Annotator report')">
                  <i class="bi bi-people me-1"></i>Annotator productivity
                </button>
                <button class="btn btn-sm btn-outline-secondary"
                        @click="exportSimple('/pool/admin/export_activity_csv&days=30', 'asr_activity.csv', 'Activity log')">
                  <i class="bi bi-clock-history me-1"></i>Activity log (30 days)
                </button>
              </div>
            </div>
          </div>

          <div class="col-12 col-lg-6">
            <div class="bg-white p-4 rounded shadow-sm border h-100">
              <h5 class="fw-bold text-dark mb-2"><i class="bi bi-sliders me-2 text-primary"></i>Annotation controls</h5>
              <p class="text-muted text-xs">The team-wide default. You can override it for any task
                (its row in the task tables), or any single category (open a task) — the most
                specific setting wins.</p>
              <div class="d-flex align-items-center justify-content-between gap-2 border rounded p-3">
                <div>
                  <div class="fw-semibold text-dark small">Difficulty labelling (team default)</div>
                  <div class="text-xs text-muted">
                    {{ teamSettings.difficulty_annotation !== false
                       ? 'ON — annotators must mark every prompt Easy / Medium / Hard.'
                       : 'OFF — annotators only review the text; the difficulty step is hidden.' }}
                  </div>
                </div>
                <span class="d-inline-flex align-items-center gap-2 flex-shrink-0">
                  <span v-if="savingSetting" class="spinner-border spinner-border-sm text-secondary"></span>
                  <DiffToggle :on="teamSettings.difficulty_annotation !== false" :overridden="true"
                              :disabled="savingSetting" @toggle="toggleDifficultySetting" />
                </span>
              </div>
              <div class="d-flex align-items-center justify-content-between gap-2 border rounded p-3 mt-3">
                <div>
                  <div class="fw-semibold text-dark small">Pull limit per annotator</div>
                  <div class="text-xs text-muted">
                    {{ pullCapDraft > 0
                       ? `An annotator may hold at most ${pullCapDraft} unfinished prompt(s); they must submit those before pulling more.`
                       : 'No limit — annotators may pull as many prompts as they like.' }}
                  </div>
                </div>
                <span class="d-inline-flex align-items-center gap-2 flex-shrink-0">
                  <input v-model.number="pullCapDraft" type="number" min="0" step="1"
                         class="form-control form-control-sm" style="width: 90px"
                         :disabled="savingSetting" />
                  <button class="btn btn-sm btn-primary"
                          :disabled="savingSetting || pullCapDraft === (teamSettings.max_open_items || 0)"
                          @click="savePullCap">Save</button>
                </span>
              </div>
            </div>
          </div>

          <div class="col-12 col-lg-6">
            <div class="bg-white p-4 rounded shadow-sm border h-100">
              <h5 class="fw-bold text-dark mb-2"><i class="bi bi-hourglass-split me-2 text-primary"></i>Abandoned work</h5>
              <p class="text-muted text-xs">Prompts claimed more than {{ staleHours }}h ago and never finished can go
                back to the pool. Finished annotations are never affected.</p>
              <div class="d-flex align-items-center gap-2">
                <span class="h4 fw-bold mb-0" :class="stats.stale_claims ? 'text-warning' : 'text-muted'">
                  {{ stats.stale_claims || 0 }}</span>
                <span class="text-xs text-muted">prompt(s) stale</span>
                <button class="btn btn-sm btn-warning ms-auto" :disabled="reclaiming || !stats.stale_claims"
                        @click="reclaim">Return to pool</button>
              </div>
            </div>
          </div>

          <div class="col-12 col-lg-6">
            <div class="bg-white p-4 rounded shadow-sm border h-100">
              <h5 class="fw-bold text-dark mb-2"><i class="bi bi-cloud-upload me-2 text-primary"></i>Uploads
                <span v-if="uploads.length" class="badge bg-light text-secondary border ms-1">{{ uploads.length }}</span>
              </h5>
              <div class="table-responsive" style="max-height: 280px; overflow-y: auto;">
                <table class="table table-sm mb-0">
                  <tbody>
                    <tr v-for="u in uploads" :key="u.id">
                      <td class="text-dark">{{ u.name }}</td>
                      <td class="text-end">{{ u.item_count.toLocaleString() }}</td>
                      <td class="text-xs text-muted text-nowrap">{{ fmtDate(u.created_at) }}</td>
                    </tr>
                    <tr v-if="!uploads.length"><td class="text-muted small">No uploads recorded.</td></tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ══ pop-menus (teleported so table overflow cannot clip them) ══ -->
    <Teleport to="body">
      <div v-if="openMenu !== null" class="menu-backdrop" @click="openMenu = null"></div>

      <div v-if="openMenu === 'exports'" class="pop-menu"
           :style="{ top: menuPos.top + 'px', left: menuPos.left + 'px', width: '280px' }">
        <div class="pop-menu-head">Exports</div>
        <button class="pop-item" @click="runMenu(() => { exportOpen = true })">
          <i class="bi bi-file-earmark-spreadsheet text-primary"></i>
          <span><b>All annotations</b><small>Every prompt: original, submission &amp; metadata</small></span>
        </button>
        <button class="pop-item" @click="runMenu(exportSubmissions)">
          <i class="bi bi-list-check text-primary"></i>
          <span><b>Submissions</b><small>Exactly what the Submissions tab is showing</small></span>
        </button>
        <button class="pop-item" @click="runMenu(() => exportSimple('/pool/admin/export_annotators_csv', 'asr_annotators.csv', 'Annotator data'))">
          <i class="bi bi-people text-success"></i>
          <span><b>Annotator data</b><small>Per-annotator totals, tasks held &amp; hours</small></span>
        </button>
        <button class="pop-item" @click="runMenu(() => exportSimple('/pool/admin/export_rater_activity_csv', 'asr_annotator_days.csv', 'Per-day report'))">
          <i class="bi bi-calendar-range text-success"></i>
          <span><b>Annotator day by day</b><small>One row per annotator per day</small></span>
        </button>
        <button class="pop-item" @click="runMenu(() => exportSimple('/pool/admin/export_tasks_csv', 'asr_task_list.csv', 'Task list'))">
          <i class="bi bi-diagram-3 text-success"></i>
          <span><b>Task list</b><small>Every task &amp; category with its progress</small></span>
        </button>
        <button class="pop-item" @click="runMenu(() => exportSimple('/pool/admin/export_activity_csv&days=30', 'asr_activity.csv', 'Activity log'))">
          <i class="bi bi-clock-history text-secondary"></i>
          <span><b>Activity log</b><small>Every pull and submission, last 30 days</small></span>
        </button>
      </div>

      <div v-if="openMenu === 'messages'" class="pop-menu"
           :style="{ top: menuPos.top + 'px', left: menuPos.left + 'px', width: '240px' }">
        <div class="pop-menu-head">Messages</div>
        <button class="pop-item" @click="runMenu(() => { broadcastModal = { body: '' } })">
          <i class="bi bi-broadcast text-primary"></i>
          <span><b>Announcement</b><small>Message every ASR annotator</small></span>
        </button>
        <button class="pop-item" @click="runMenu(openOutbox)">
          <i class="bi bi-clock-history text-secondary"></i>
          <span><b>Sent messages</b><small>Review and edit what you sent</small></span>
        </button>
      </div>

    </Teleport>

    <!-- ══ task detail ══ -->
    <div v-if="taskModal" class="asr-modal-backdrop" @click.self="taskModal = null">
      <div class="asr-modal wide">
        <div class="asr-modal-head">
          <div>
            <h5 class="fw-bold mb-0">
              <span class="task-id-badge me-2">#{{ taskModal.task.task_id }}</span>{{ taskModal.task.label }}
            </h5>
            <div class="text-xs text-muted">
              {{ taskModal.task.total.toLocaleString() }} prompts ·
              <span class="badge rounded-pill" :class="stateBadge(taskModal.task.state)">{{ taskModal.task.state }}</span>
              <span v-if="holdersOf(taskModal.task).length"> ·
                {{ holdersOf(taskModal.task).length === 1 ? 'held by' : `shared by ${holdersOf(taskModal.task).length} annotators:` }}
                <strong>{{ holdersOf(taskModal.task).map(a => a.name).join(', ') }}</strong>
              </span>
              <span v-else> · not assigned to anyone</span>
            </div>
          </div>
          <button class="btn-close" @click="taskModal = null"></button>
        </div>
        <div class="asr-modal-body">
          <div v-if="taskLoading" class="text-center py-5"><span class="spinner-border text-secondary"></span></div>
          <template v-else>
            <div class="row g-2 mb-3">
              <div class="col-6 col-md-2"><div class="mini-stat"><span>Prompts</span><strong>{{ taskModal.task.total.toLocaleString() }}</strong></div></div>
              <div class="col-6 col-md-2"><div class="mini-stat"><span>Completed</span><strong class="text-success">{{ taskModal.task.completed.toLocaleString() }}</strong></div></div>
              <div class="col-6 col-md-2"><div class="mini-stat"><span>Flagged</span><strong class="text-warning">{{ taskModal.task.flagged.toLocaleString() }}</strong></div></div>
              <div class="col-6 col-md-2"><div class="mini-stat"><span>In progress</span><strong>{{ taskModal.task.claimed.toLocaleString() }}</strong></div></div>
              <div class="col-6 col-md-2"><div class="mini-stat"><span>Available</span><strong class="text-muted">{{ taskModal.task.available.toLocaleString() }}</strong></div></div>
              <div class="col-6 col-md-2"><div class="mini-stat"><span>Progress</span><strong>{{ showPct(taskModal.task.progress, taskModal.task.done) }}%</strong></div></div>
            </div>

            <div class="border rounded p-3 mb-3">
              <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-2">
                <h6 class="fw-bold text-uppercase text-muted text-xs mb-0">
                  <i class="bi bi-people-fill me-1"></i>Assigned annotators
                  <span v-if="holdersOf(taskModal.task).length"
                        class="badge bg-light text-secondary border ms-1">{{ holdersOf(taskModal.task).length }}</span>
                </h6>
                <button class="btn btn-sm btn-outline-primary" @click="openAssign([taskModal.task.task_id])">
                  <i class="bi bi-person-plus me-1"></i>Add annotator
                </button>
              </div>
              <div v-if="holdersOf(taskModal.task).length" class="d-flex flex-wrap gap-2">
                <span v-for="a in holdersOf(taskModal.task)" :key="a.rater_id + '-' + (a.category || '')"
                      class="holder-pill">
                  <span class="holder-avatar">{{ initialOf(a.name) }}</span>
                  <span class="d-inline-flex flex-column lh-sm text-start">
                    <span class="fw-semibold text-dark small">{{ a.name }}</span>
                    <small class="text-muted" style="font-size:.68rem">
                      {{ a.category ? `only “${a.category}”` : 'whole task' }} · since {{ a.assigned_at_ist }}
                    </small>
                  </span>
                  <i class="bi bi-x-circle holder-remove" role="button"
                     :title="`Take this task back from ${a.name}`"
                     @click="unassignTask(taskModal.task, a)"></i>
                </span>
              </div>
              <p v-else class="text-muted small mb-0">
                Nobody yet. A task can be shared by several annotators — each prompt is still
                handed to exactly one of them, so their work never overlaps.
              </p>
            </div>

            <div class="d-flex flex-wrap align-items-center gap-2 mb-3 border rounded p-2 bg-light">
              <span class="text-xs fw-bold text-uppercase text-muted">
                <i class="bi bi-sliders me-1"></i>Difficulty labelling for this task
              </span>
              <DiffToggle :on="modalTaskDiff.on" :overridden="modalTaskDiff.overridden"
                          inherit="team default"
                          @toggle="setDifficulty([taskModal.task.task_id], '', $event)"
                          @clear="setDifficulty([taskModal.task.task_id], '', null)" />
              <span class="text-xs text-muted">On = annotators must label difficulty. Each category below
                has its own switch; “auto” means it follows the level above.</span>
            </div>

            <h6 class="fw-bold text-uppercase text-muted text-xs mb-2">Granularity inside this task</h6>
            <div class="table-responsive border rounded mb-3">
              <table class="table table-sm mb-0">
                <thead class="table-light"><tr><th>Category</th><th class="text-end">Prompts</th><th class="text-end">Completed</th>
                  <th class="text-end">Flagged</th><th class="text-end">In progress</th><th class="text-end">Available</th><th style="width:150px">Progress</th>
                  <th style="width:150px">Difficulty labels</th></tr></thead>
                <tbody>
                  <tr v-for="c in taskModal.task.categories" :key="c.category">
                    <td class="fw-semibold">{{ c.category }}</td>
                    <td class="text-end">{{ c.total.toLocaleString() }}</td>
                    <td class="text-end text-success">{{ c.completed.toLocaleString() }}</td>
                    <td class="text-end text-warning">{{ c.flagged }}</td>
                    <td class="text-end">{{ c.claimed }}</td>
                    <td class="text-end text-muted">{{ c.available.toLocaleString() }}</td>
                    <td><div class="progress" style="height:6px"><div class="progress-bar bg-success" :style="{ width: c.progress + '%' }"></div></div></td>
                    <td>
                      <DiffToggle :on="taskModal.task.difficulty_settings?.effective_by_category?.[c.category] !== false"
                                  :overridden="taskModal.task.difficulty_settings?.by_category?.[c.category] !== null
                                               && taskModal.task.difficulty_settings?.by_category?.[c.category] !== undefined"
                                  inherit="task setting"
                                  @toggle="setDifficulty([taskModal.task.task_id], c.category, $event)"
                                  @clear="setDifficulty([taskModal.task.task_id], c.category, null)" />
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div class="row g-4 mb-3">
              <div class="col-12 col-lg-6">
                <h6 class="fw-bold text-uppercase text-muted text-xs mb-2">Who has worked on it</h6>
                <div class="table-responsive border rounded">
                  <table class="table table-sm mb-0">
                    <thead class="table-light"><tr><th>Annotator</th><th class="text-end">Completed</th><th class="text-end">Flagged</th><th class="text-end">Holding</th></tr></thead>
                    <tbody>
                      <tr v-for="a in taskModal.annotators" :key="a.rater_id">
                        <td>{{ a.name }}</td>
                        <td class="text-end text-success">{{ a.completed }}</td>
                        <td class="text-end text-warning">{{ a.flagged }}</td>
                        <td class="text-end">{{ a.claimed }}</td>
                      </tr>
                      <tr v-if="!taskModal.annotators.length"><td colspan="4" class="text-muted small">Nothing submitted yet.</td></tr>
                    </tbody>
                  </table>
                </div>
              </div>
              <div class="col-12 col-lg-6">
                <h6 class="fw-bold text-uppercase text-muted text-xs mb-2">Assignment history</h6>
                <div class="table-responsive border rounded">
                  <table class="table table-sm mb-0">
                    <thead class="table-light"><tr><th>Annotator</th><th>Scope</th><th>From (IST)</th><th>Until</th><th>By</th></tr></thead>
                    <tbody>
                      <tr v-for="(h, i) in taskModal.assignment_history" :key="i">
                        <td>{{ h.name }}
                          <span v-if="h.is_active" class="badge bg-success-subtle text-success ms-1">current</span></td>
                        <td class="text-xs text-muted">{{ h.category || 'whole task' }}</td>
                        <td class="text-xs">{{ h.assigned_at_ist }}</td>
                        <td class="text-xs text-muted">{{ h.revoked_at_ist || '—' }}</td>
                        <td class="text-xs text-muted">{{ h.assigned_by || '—' }}</td>
                      </tr>
                      <tr v-if="!taskModal.assignment_history.length"><td colspan="5" class="text-muted small">Never assigned.</td></tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            <h6 class="fw-bold text-uppercase text-muted text-xs mb-2">Pulls made against this task</h6>
            <div class="table-responsive border rounded mb-3">
              <table class="table table-sm mb-0">
                <thead class="table-light"><tr><th>Pulled (IST)</th><th>Annotator</th><th>Slice</th>
                  <th class="text-end">Prompts</th><th class="text-end">Done</th><th class="text-end">Left</th><th>State</th></tr></thead>
                <tbody>
                  <tr v-for="p in taskModal.pulls" :key="p.pull_id">
                    <td class="text-xs text-nowrap">{{ p.created_at_ist }}</td>
                    <td>{{ p.annotator }}</td>
                    <td class="text-xs text-muted">{{ p.category || 'whole task' }}{{ p.source_difficulty ? ' · ' + p.source_difficulty : '' }}</td>
                    <td class="text-end">{{ p.item_count }}</td>
                    <td class="text-end text-success">{{ p.done }}</td>
                    <td class="text-end">{{ p.claimed }}</td>
                    <td><span class="badge" :class="pullBadge(p.status)">{{ p.status }}</span></td>
                  </tr>
                  <tr v-if="!taskModal.pulls.length"><td colspan="7" class="text-muted small">Nobody has pulled from this task yet.</td></tr>
                </tbody>
              </table>
            </div>

            <h6 class="fw-bold text-uppercase text-muted text-xs mb-2">Latest submissions</h6>
            <div class="table-responsive border rounded">
              <table class="table table-sm table-hover mb-0">
                <thead class="table-light"><tr><th>#</th><th>Category</th><th>Submission</th><th>Difficulty</th><th>Annotator</th><th>When (IST)</th></tr></thead>
                <tbody>
                  <tr v-for="it in taskModal.recent_submissions" :key="it.id" class="cursor-pointer" @click="openItem(it.id)">
                    <td class="text-muted">{{ it.id }}</td>
                    <td class="text-muted text-xs">{{ it.category }}</td>
                    <td class="cell-text" :dir="rtl(it.language) ? 'rtl' : 'ltr'">{{ trim(it.text, 60) }}</td>
                    <td><span v-if="it.final_difficulty" class="badge" :class="badgeFor(it.final_difficulty)">{{ it.final_difficulty }}</span></td>
                    <td class="text-xs">{{ it.annotator }}</td>
                    <td class="text-xs text-muted text-nowrap">{{ it.completed_at_ist }}</td>
                  </tr>
                  <tr v-if="!taskModal.recent_submissions.length"><td colspan="6" class="text-muted small">No submissions yet.</td></tr>
                </tbody>
              </table>
            </div>
          </template>
        </div>
        <div class="asr-modal-foot">
          <button v-if="holdersOf(taskModal.task).length"
                  class="btn btn-outline-danger me-auto" @click="unassignTask(taskModal.task)">
            <i class="bi bi-person-dash me-1"></i>Take back from everyone
          </button>
          <button class="btn btn-outline-secondary" @click="browseTask(taskModal.task.task_id)">
            <i class="bi bi-list-check me-1"></i>See its submissions
          </button>
          <button class="btn btn-primary" @click="openAssign([taskModal.task.task_id])">
            <i class="bi bi-person-plus me-1"></i>Assign
          </button>
        </div>
      </div>
    </div>

    <!-- ===================== ASSIGN TASKS MODAL ===================== -->
    <transition name="modal-fade">
      <div v-if="assignModal" class="assign-modal-backdrop" @click.self="assignModal = null">
        <div class="assign-modal-card shadow-lg">
          <!-- Header -->
          <div class="assign-modal-header d-flex justify-content-between align-items-center">
            <div class="d-flex align-items-center gap-3">
              <div v-if="assignRaters.length" class="avatar-stack">
                <div v-for="a in assignRaters.slice(0, 3)" :key="a.rater_id" class="avatar-circle-lg stacked"
                     :title="a.name">{{ initialOf(a.name) }}</div>
                <div v-if="assignRaters.length > 3" class="avatar-circle-lg stacked more">+{{ assignRaters.length - 3 }}</div>
              </div>
              <div v-else class="avatar-circle-lg">?</div>
              <div>
                <h5 class="fw-bold mb-0 text-dark">Assign Tasks</h5>
                <small class="text-muted">
                  <span v-if="assignRaters.length === 1">{{ assignRaters[0].name }} · {{ assignRaters[0].email }}</span>
                  <span v-else-if="assignRaters.length">{{ assignRaters.map(a => a.name).join(', ') }}</span>
                  <span v-else>Choose one or more annotators to hand these tasks to</span>
                </small>
              </div>
            </div>
            <button class="btn-close" @click="assignModal = null"></button>
          </div>

          <!-- Body -->
          <div class="assign-modal-body">
            <!-- Sharing notice -->
            <div class="d-flex align-items-start gap-2 py-2 px-3 rounded-3 bg-info-subtle mb-3">
              <i class="bi bi-people-fill text-info mt-1"></i>
              <small class="text-info-emphasis"><strong>Tasks can be shared.</strong> Everyone you pick
                can pull prompts from the selected tasks — but each prompt is only ever handed to
                <strong>one</strong> annotator, so nobody's work overlaps.</small>
            </div>

            <div class="d-flex justify-content-between align-items-center mb-1">
              <label class="form-label fw-semibold text-dark small mb-0">Annotators</label>
              <span class="text-xs" :class="assignModal.rater_ids.length ? 'text-muted' : 'text-danger'">
                {{ assignModal.rater_ids.length || 'none' }} selected
              </span>
            </div>
            <div class="batch-picker border rounded-3 mb-3" style="max-height: 190px;">
              <label v-for="a in assignCandidates" :key="a.rater_id"
                     :class="['batch-row d-flex align-items-center gap-3 px-3 py-2',
                              assignModal.rater_ids.includes(a.rater_id) ? 'selected' : '']">
                <input type="checkbox" class="form-check-input mt-0 flex-shrink-0"
                       :checked="assignModal.rater_ids.includes(a.rater_id)" @change="toggleAssignRater(a.rater_id)" />
                <span class="holder-initial lg flex-shrink-0">{{ initialOf(a.name) }}</span>
                <span class="flex-grow-1 text-truncate">
                  <span class="text-dark small fw-semibold">{{ a.name }}</span>
                  <span class="text-muted ms-1" style="font-size:.72rem">{{ a.email }}</span>
                </span>
                <span class="text-muted flex-shrink-0" style="font-size:.72rem">holds {{ a.tasks_held }} task(s)</span>
              </label>
              <div v-if="!assignCandidates.length" class="text-center text-muted py-3 small">
                No active annotators in this team yet — add members first.
              </div>
            </div>

            <label class="form-label fw-semibold text-dark small mb-1">Scope</label>
            <select v-model="assignModal.category" class="form-select mb-1">
              <option value="">Whole task — every category in it</option>
              <option v-for="c in assignCategoryOptions" :key="c" :value="c">Only the “{{ c }}” category</option>
            </select>
            <p class="text-muted mb-3" style="font-size:.72rem">
              A task can be handed over whole or narrowed to one category (word, sentence, …) —
              and either way it can go to several annotators at once.
              <span v-if="assignModal.category && assignModal.task_ids.length > 1">
                The category applies to every selected task.</span>
            </p>

            <!-- Selected summary -->
            <div class="d-flex justify-content-between align-items-center mb-2">
              <span class="fw-semibold text-dark">
                Selected <span class="badge bg-primary rounded-pill ms-1">{{ assignModal.task_ids.length }}</span>
              </span>
              <button v-if="assignModal.task_ids.length" class="btn btn-sm btn-link text-danger p-0 text-decoration-none"
                      @click="assignModal.task_ids = []">
                <i class="bi bi-x-circle me-1"></i>Clear all
              </button>
            </div>
            <div v-if="assignModal.task_ids.length" class="selected-chips mb-3">
              <span v-for="tid in assignModal.task_ids" :key="tid" class="chip">
                #{{ tid }}
                <i class="bi bi-x-lg" role="button" title="Remove" @click="toggleAssignPick(tid)"></i>
              </span>
            </div>

            <!-- Search tasks -->
            <div class="input-group mb-2">
              <span class="input-group-text bg-white border-end-0"><i class="bi bi-search text-muted"></i></span>
              <input v-model="assignSearch" type="text" class="form-control border-start-0 ps-0"
                     placeholder="Search tasks by ID, language, class or current holder..." />
            </div>

            <!-- Task list -->
            <div class="batch-picker border rounded-3">
              <label v-for="t in assignableShown" :key="t.task_id"
                     :class="['batch-row d-flex align-items-center gap-3 px-3 py-2',
                              assignModal.task_ids.includes(t.task_id) ? 'selected' : '']">
                <input type="checkbox" class="form-check-input mt-0 flex-shrink-0"
                       :checked="assignModal.task_ids.includes(t.task_id)" @change="toggleAssignPick(t.task_id)" />
                <span class="badge bg-light text-dark border flex-shrink-0 text-center" style="min-width: 52px;">#{{ t.task_id }}</span>
                <span class="flex-grow-1 text-truncate text-dark small">{{ t.label }}</span>
                <span class="text-muted flex-shrink-0" style="font-size: .72rem;">{{ t.available.toLocaleString() }} free</span>
                <span v-if="holdersOf(t).length"
                      class="badge rounded-pill bg-info-subtle text-info-emphasis flex-shrink-0 d-inline-flex align-items-center gap-1"
                      :title="'Already working on it: ' + holdersOf(t).map(a => `${a.name}${a.category ? ' · ' + a.category : ''}`).join(', ')">
                  <i class="bi bi-people-fill"></i>{{ holdersOf(t).length }}
                </span>
                <span class="badge rounded-pill bg-secondary-subtle text-secondary flex-shrink-0">{{ t.language }}</span>
              </label>
              <div v-if="!assignableShown.length" class="text-center text-muted py-4 small">
                <i class="bi bi-inbox d-block fs-4 mb-1 opacity-50"></i>
                No tasks match your search.
              </div>
            </div>

            <template v-if="assignOtherHolders.length">
              <label class="form-label fw-semibold text-dark small mb-1 mt-3">
                Some of the selection is already being worked on — what should happen?
              </label>
              <div class="d-flex flex-column flex-md-row gap-2 mb-1">
                <label :class="['mode-card flex-fill', assignModal.mode === 'add' ? 'active' : '']">
                  <input type="radio" class="form-check-input mt-0" value="add" v-model="assignModal.mode">
                  <span>
                    <span class="fw-semibold text-dark small d-block"><i class="bi bi-people me-1"></i>Share</span>
                    <small class="text-muted">Current annotators stay on; the new ones join them.</small>
                  </span>
                </label>
                <label :class="['mode-card flex-fill', assignModal.mode === 'replace' ? 'active' : '']">
                  <input type="radio" class="form-check-input mt-0" value="replace" v-model="assignModal.mode">
                  <span>
                    <span class="fw-semibold text-dark small d-block"><i class="bi bi-arrow-left-right me-1"></i>Replace</span>
                    <small class="text-muted">Take the task(s) back from everyone else first.
                      Submitted work is kept; unfinished prompts return to the pool.</small>
                  </span>
                </label>
              </div>
              <p class="mb-0" style="font-size:.72rem"
                 :class="assignModal.mode === 'replace' ? 'text-danger' : 'text-muted'">
                <template v-if="assignModal.mode === 'replace'">
                  Will be taken back: {{ assignOtherHolders.join(', ') }}.
                </template>
                <template v-else>
                  Already working on the selection: {{ assignOtherHolders.join(', ') }} — they keep their part.
                </template>
              </p>
            </template>
          </div>

          <!-- Footer -->
          <div class="assign-modal-footer d-flex justify-content-between align-items-center gap-3">
            <small v-if="assignError" class="text-danger"><i class="bi bi-exclamation-circle me-1"></i>{{ assignError }}</small>
            <small v-else class="text-muted">
              {{ assignModal.task_ids.length }} task(s) →
              <strong>{{ assignRaters.length ? assignRaters.map(a => a.name).join(', ') : 'the chosen annotator(s)' }}</strong>
            </small>
            <div class="d-flex gap-2 flex-shrink-0">
              <button class="btn btn-light border" @click="assignModal = null" :disabled="assigning">Cancel</button>
              <button class="btn btn-primary d-inline-flex align-items-center gap-2"
                      :disabled="assigning || !assignModal.rater_ids.length || !assignModal.task_ids.length"
                      @click="saveAssignment">
                <span v-if="assigning" class="spinner-border spinner-border-sm"></span>
                <i v-else class="bi bi-check2-circle"></i>
                <span>{{ assigning ? 'Saving…' : 'Save Assignment' }}</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </transition>

    <!-- ══ annotator drill-down ══ -->
    <div v-if="annotatorModal" class="asr-modal-backdrop" @click.self="annotatorModal = null">
      <div class="asr-modal wide">
        <div class="asr-modal-head">
          <div>
            <h5 class="fw-bold mb-0">{{ annotatorModal.annotator?.name }}</h5>
            <div class="text-xs text-muted">{{ annotatorModal.annotator?.email }}</div>
          </div>
          <button class="btn-close" @click="annotatorModal = null"></button>
        </div>
        <div class="asr-modal-body">
          <div v-if="annotatorLoading" class="text-center py-5"><span class="spinner-border text-secondary"></span></div>
          <template v-else>
            <div class="row g-2 mb-3">
              <div class="col-6 col-md-2"><div class="mini-stat"><span>Completed</span><strong class="text-success">{{ annotatorModal.totals.completed.toLocaleString() }}</strong></div></div>
              <div class="col-6 col-md-2"><div class="mini-stat"><span>Flagged</span><strong class="text-warning">{{ annotatorModal.totals.flagged }}</strong></div></div>
              <div class="col-6 col-md-2"><div class="mini-stat"><span>Text edited</span><strong>{{ annotatorModal.totals.edited }}</strong></div></div>
              <div class="col-6 col-md-2"><div class="mini-stat"><span>Diff. changed</span><strong>{{ annotatorModal.totals.difficulty_changed }}</strong></div></div>
              <div class="col-6 col-md-2"><div class="mini-stat"><span>Holding now</span><strong>{{ annotatorModal.totals.claimed }}</strong></div></div>
              <div class="col-6 col-md-2"><div class="mini-stat"><span>Avg / prompt</span><strong>{{ annotatorModal.totals.avg_seconds }}s</strong></div></div>
            </div>

            <template v-if="(annotatorModal.by_task_type || []).length">
              <h6 class="fw-bold text-uppercase text-muted text-xs mb-2">Payable work by task type</h6>
              <div class="table-responsive border rounded mb-3">
                <table class="table table-sm mb-0">
                  <thead class="table-light"><tr>
                    <th>Type of work</th><th class="text-end">Submitted</th>
                    <th class="text-end">Completed</th><th class="text-end">Flagged</th>
                    <th class="text-end">Edited</th><th class="text-end">Time (h)</th>
                  </tr></thead>
                  <tbody>
                    <tr v-for="tt in annotatorModal.by_task_type" :key="tt.task_type">
                      <td class="fw-semibold">{{ tt.task_type_label }}</td>
                      <td class="text-end fw-semibold">{{ tt.submitted.toLocaleString() }}</td>
                      <td class="text-end text-success">{{ tt.completed.toLocaleString() }}</td>
                      <td class="text-end text-warning">{{ tt.flagged }}</td>
                      <td class="text-end">{{ tt.edited }}</td>
                      <td class="text-end">{{ tt.hours }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </template>

            <h6 class="fw-bold text-uppercase text-muted text-xs mb-2">By language &amp; class</h6>
            <div class="table-responsive border rounded mb-3">
              <table class="table table-sm mb-0">
                <thead class="table-light"><tr><th>Language</th><th class="text-end">Completed</th><th class="text-end">Flagged</th><th class="text-end">Holding</th><th>Classes</th></tr></thead>
                <tbody>
                  <tr v-for="L in annotatorModal.by_language" :key="L.language">
                    <td class="fw-semibold">{{ L.language }}</td>
                    <td class="text-end text-success">{{ L.completed }}</td>
                    <td class="text-end text-warning">{{ L.flagged }}</td>
                    <td class="text-end">{{ L.claimed }}</td>
                    <td><span v-for="K in L.classes" :key="K.class" class="badge bg-light text-secondary border me-1">
                      C{{ K.class }} {{ K.completed + K.flagged }}</span></td>
                  </tr>
                  <tr v-if="!annotatorModal.by_language.length"><td colspan="5" class="text-muted small">Nothing yet.</td></tr>
                </tbody>
              </table>
            </div>

            <div class="row g-4 mb-3">
              <div class="col-12 col-md-6">
                <h6 class="fw-bold text-uppercase text-muted text-xs mb-2">Difficulty they assigned</h6>
                <div v-for="(n, k) in annotatorModal.difficulties" :key="k" class="d-flex align-items-center gap-2 mb-1">
                  <span class="text-xs" style="min-width:70px">{{ k }}</span>
                  <div class="progress flex-grow-1" style="height:6px"><div class="progress-bar" :class="diffClass(k)"
                       :style="{ width: pct(n, annotatorModal.totals.completed || 1) }"></div></div>
                  <span class="text-xs fw-semibold">{{ n }}</span>
                </div>
                <p v-if="!Object.keys(annotatorModal.difficulties).length" class="text-muted small mb-0">Nothing yet.</p>
              </div>
              <div class="col-12 col-md-6">
                <h6 class="fw-bold text-uppercase text-muted text-xs mb-2">Categories worked</h6>
                <div v-for="(n, k) in annotatorModal.categories" :key="k" class="d-flex align-items-center gap-2 mb-1">
                  <span class="text-xs" style="min-width:70px">{{ k }}</span>
                  <div class="progress flex-grow-1" style="height:6px"><div class="progress-bar bg-primary"
                       :style="{ width: pct(n, annotatorModal.totals.done || 1) }"></div></div>
                  <span class="text-xs fw-semibold">{{ n }}</span>
                </div>
                <p v-if="!Object.keys(annotatorModal.categories).length" class="text-muted small mb-0">Nothing yet.</p>
              </div>
            </div>

            <h6 class="fw-bold text-uppercase text-muted text-xs mb-2">Day by day</h6>
            <div class="table-responsive border rounded mb-3">
              <table class="table table-sm mb-0">
                <thead class="table-light"><tr><th>Date (IST)</th><th class="text-end">Completed</th><th class="text-end">Flagged</th><th class="text-end">Edited</th><th class="text-end">Hours</th><th style="width:180px"></th></tr></thead>
                <tbody>
                  <tr v-for="d in annotatorDays" :key="d.date">
                    <td class="fw-semibold">{{ longDay(d.date) }}
                      <span v-if="d.date === todayIst" class="badge bg-success-subtle text-success ms-1">Today</span>
                    </td>
                    <td class="text-end text-success">{{ d.completed }}</td>
                    <td class="text-end text-warning">{{ d.flagged }}</td>
                    <td class="text-end">{{ d.edited }}</td>
                    <td class="text-end">{{ d.hours }}</td>
                    <td>
                      <div class="progress" style="height:6px">
                        <div class="progress-bar bg-success" :style="{ width: dayBarWidth(d) }"></div>
                      </div>
                    </td>
                  </tr>
                  <tr v-if="!annotatorDays.length"><td colspan="6" class="text-muted small">No activity recorded in this window.</td></tr>
                </tbody>
              </table>
            </div>

            <h6 class="fw-bold text-uppercase text-muted text-xs mb-2">Most recent work</h6>
            <div class="table-responsive border rounded">
              <table class="table table-sm table-hover mb-0">
                <thead class="table-light"><tr><th>#</th><th>Lang</th><th>Cl</th><th>Text</th><th>Difficulty</th><th>State</th><th>When</th></tr></thead>
                <tbody>
                  <tr v-for="it in annotatorModal.recent_items.slice(0, 40)" :key="it.id"
                      class="cursor-pointer" @click="openItem(it.id)">
                    <td class="text-muted">{{ it.id }}</td>
                    <td>{{ it.language }}</td>
                    <td>{{ it.class }}</td>
                    <td class="cell-text" :dir="rtl(it.language) ? 'rtl' : 'ltr'">{{ trim(it.text, 60) }}</td>
                    <td><span v-if="it.final_difficulty" class="badge" :class="badgeFor(it.final_difficulty)">{{ it.final_difficulty }}</span></td>
                    <td>
                      <span v-if="it.is_flagged" class="badge bg-warning-subtle text-warning">flagged</span>
                      <span v-else-if="it.is_edited" class="badge bg-primary-subtle text-primary">edited</span>
                      <span v-else class="badge bg-success-subtle text-success">as-is</span>
                    </td>
                    <td class="text-xs text-muted">{{ fmtDate(it.completed_at) }}</td>
                  </tr>
                  <tr v-if="!annotatorModal.recent_items.length"><td colspan="7" class="text-muted small">No submissions yet.</td></tr>
                </tbody>
              </table>
            </div>
          </template>
        </div>
        <div class="asr-modal-foot">
          <button class="btn btn-outline-secondary me-auto"
                  @click="openMessage({ rater_id: annotatorModal.annotator.id, name: annotatorModal.annotator.name, email: annotatorModal.annotator.email })">
            <i class="bi bi-chat-dots me-1"></i>Message
          </button>
          <button class="btn btn-secondary" @click="annotatorModal = null">Close</button>
        </div>
      </div>
    </div>

    <!-- ══ item detail ══ -->
    <!-- ══ admin preview: the task template exactly as an annotator sees it ══ -->
    <div v-if="preview" class="asr-modal-backdrop" @click.self="preview = null">
      <div class="asr-modal preview-modal">
        <div class="asr-modal-head">
          <div>
            <h5 class="fw-bold mb-0"><i class="bi bi-eye me-2"></i>{{ preview.title }}</h5>
            <div class="text-xs text-muted">Admin preview — exactly what the annotator gets. Nothing you do here is saved.</div>
          </div>
          <button class="btn-close" @click="preview = null"></button>
        </div>
        <div class="asr-modal-body">
          <div v-if="preview.loading" class="text-center py-5"><span class="spinner-border text-secondary"></span></div>
          <div v-else-if="!preview.item" class="text-center text-muted py-5">
            This task has no items to preview yet.
          </div>
          <template v-else>
            <div class="d-flex flex-wrap gap-1 mb-3">
              <span class="badge bg-light text-secondary border">{{ preview.item.task_type_label }}</span>
              <span class="badge bg-light text-secondary border">{{ preview.item.language }}</span>
              <span v-if="preview.item.category" class="badge bg-light text-secondary border">{{ preview.item.category }}</span>
              <span class="badge bg-light text-secondary border">sample prompt #{{ preview.item.id }}</span>
            </div>

            <!-- MDFS template -->
            <MdfsEvaluation v-if="preview.item.task_type === 'audio-mdfs'"
                            :item="preview.item" v-model="preview.scores" />

            <!-- text-review template -->
            <template v-else>
              <span class="badge bg-secondary-subtle text-secondary mb-2 fs-8 text-uppercase">Original prompt</span>
              <div class="p-3 bg-light rounded-3 border-start border-3 border-secondary mb-3">
                <p class="mb-0 text-dark fs-5" :dir="rtl(preview.item.language) ? 'rtl' : 'ltr'">{{ preview.item.original_text }}</p>
              </div>
              <label class="form-label small text-uppercase fw-bold text-primary">
                Prompt text ({{ preview.item.language }}) — the annotator edits only if it is wrong
              </label>
              <textarea v-model="preview.draft" rows="3" class="form-control mb-3"
                        :dir="rtl(preview.item.language) ? 'rtl' : 'ltr'"></textarea>
              <label class="form-label small text-uppercase fw-bold text-primary mb-2">
                How hard is this to read aloud?
              </label>
              <div class="d-flex flex-wrap gap-2">
                <button v-for="d in difficulties" :key="d" type="button"
                        class="btn rounded-pill px-4"
                        :class="preview.difficulty === d
                          ? { Easy: 'btn-success', Medium: 'btn-warning', Hard: 'btn-danger' }[d]
                          : 'btn-outline-secondary'"
                        @click="preview.difficulty = d">{{ d }}</button>
              </div>
            </template>
          </template>
        </div>
      </div>
    </div>

    <div v-if="itemModal" class="asr-modal-backdrop" @click.self="itemModal = null">
      <div class="asr-modal">
        <div class="asr-modal-head">
          <div>
            <h5 class="fw-bold mb-0">Prompt #{{ itemModal.id }}</h5>
            <div class="text-xs text-muted">
              <a href="#" class="text-decoration-none" @click.prevent="openTask(itemModal.task_id)">
                <span class="task-id-badge">#{{ itemModal.task_id }}</span> {{ itemModal.task_label }}
              </a>
              · {{ itemModal.category }}
            </div>
          </div>
          <button class="btn-close" @click="itemModal = null"></button>
        </div>
        <div class="asr-modal-body">
          <div class="mb-3 d-flex flex-wrap gap-1">
            <span class="badge bg-light text-secondary border">{{ itemModal.task_type_label || 'text review' }}</span>
            <span v-if="itemModal.source" class="badge bg-light text-secondary border">source: {{ itemModal.source }}</span>
            <span v-if="itemModal.n_words" class="badge bg-light text-secondary border">{{ itemModal.n_words }} words</span>
            <span class="badge" :class="statusBadge(itemModal.status)">{{ itemModal.status }}</span>
            <span v-if="itemModal.revision" class="badge bg-light text-secondary border">revision {{ itemModal.revision }}</span>
          </div>

          <h6 class="fw-bold text-uppercase text-muted text-xs mb-2">Original text</h6>
          <div class="text-block" :dir="rtl(itemModal.language) ? 'rtl' : 'ltr'">{{ itemModal.original_text }}</div>

          <template v-if="itemModal.is_edited">
            <h6 class="fw-bold text-uppercase text-muted text-xs mb-2 mt-3">Corrected by the annotator</h6>
            <div class="text-block edited-block" :dir="rtl(itemModal.language) ? 'rtl' : 'ltr'">{{ itemModal.text }}</div>
          </template>

          <div class="row g-3 mt-2">
            <div class="col-12 col-md-6">
              <h6 class="fw-bold text-uppercase text-muted text-xs mb-2">Difficulty</h6>
              <p class="mb-1 small"><span class="text-muted">generated:</span>
                <span class="badge ms-1" :class="badgeFor(itemModal.source_difficulty)">{{ itemModal.source_difficulty || 'unset' }}</span></p>
              <p class="mb-0 small"><span class="text-muted">annotator:</span>
                <span v-if="itemModal.final_difficulty" class="badge ms-1" :class="badgeFor(itemModal.final_difficulty)">{{ itemModal.final_difficulty }}</span>
                <span v-else class="text-muted"> not labelled yet</span></p>
            </div>
            <div class="col-12 col-md-6">
              <h6 class="fw-bold text-uppercase text-muted text-xs mb-2">Who &amp; when</h6>
              <p class="mb-1 small"><span class="text-muted">completed by:</span> {{ itemModal.completed_by || '—' }}</p>
              <p class="mb-1 small"><span class="text-muted">claimed:</span> {{ itemModal.claimed_at_ist || '—' }}</p>
              <p class="mb-1 small"><span class="text-muted">completed:</span> {{ itemModal.completed_at_ist || '—' }}</p>
              <p class="mb-0 small"><span class="text-muted">time spent:</span>
                {{ itemModal.time_taken_ms ? (itemModal.time_taken_ms / 1000).toFixed(1) + 's' : '—' }}</p>
            </div>
          </div>

          <div v-if="itemModal.is_flagged" class="alert alert-warning mt-3 py-2 mb-0">
            <i class="bi bi-flag-fill me-1"></i><strong>Flagged:</strong> {{ itemModal.flag_reason }}
          </div>
        </div>
        <div class="asr-modal-foot">
          <button v-if="itemModal.status !== 'available'" class="btn btn-outline-danger me-auto" @click="resetItem(itemModal.id)">
            <i class="bi bi-arrow-counterclockwise me-1"></i>Send back to the pool
          </button>
          <button class="btn btn-secondary" @click="itemModal = null">Close</button>
        </div>
      </div>
    </div>

    <!-- ===================== MESSAGE MODAL ===================== -->
    <transition name="modal-fade">
      <div v-if="messageModal" class="assign-modal-backdrop" @click.self="messageModal = null">
        <div class="assign-modal-card shadow-lg" style="max-width: 520px;">
          <div class="assign-modal-header d-flex justify-content-between align-items-center">
            <div class="d-flex align-items-center gap-3">
              <div class="avatar-circle-lg">{{ (messageModal.rater?.name || '?').charAt(0).toUpperCase() }}</div>
              <div>
                <h5 class="fw-bold mb-0 text-dark">Message annotator</h5>
                <small class="text-muted">{{ messageModal.rater?.name }} · {{ messageModal.rater?.email }}</small>
              </div>
            </div>
            <button class="btn-close" @click="messageModal = null"></button>
          </div>
          <div class="assign-modal-body">
            <!-- Full history with this annotator, stacked like a chat -->
            <div v-if="threadLoading" class="text-center text-muted py-3">
              <span class="spinner-border spinner-border-sm me-2"></span>Loading history…
            </div>
            <div v-else-if="threadItems.length" ref="threadBox" class="msg-thread mb-3">
              <div v-for="item in threadItems"
                   :key="item.kind === 'broadcast' ? 'b-' + item.broadcast_id : 'm-' + item.id"
                   class="msg-bubble" :class="{ broadcast: item.kind === 'broadcast' }">
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
                  <button v-if="item.kind !== 'broadcast'" class="btn btn-link btn-sm p-0 text-secondary"
                          title="Edit this message" @click="startEditThread(item)"><i class="bi bi-pencil"></i></button>
                </div>
                <div class="small text-dark" style="white-space: pre-wrap; word-break: break-word;">{{ item.body }}</div>
                <div class="text-muted fs-9 mt-1">{{ fmtDate(item.created_at) }}<span v-if="item.edited_at"> · edited {{ fmtDate(item.edited_at) }}</span></div>
              </div>
            </div>
            <div v-else class="text-center text-muted small py-2 mb-2">
              <i class="bi bi-chat-square-text d-block fs-4 mb-1 opacity-50"></i>
              No previous messages with this annotator.
            </div>

            <label class="form-label fw-semibold text-dark small mb-1">New message</label>
            <textarea v-model="messageModal.body" class="form-control" rows="3" maxlength="2000"
                      placeholder="Write your message… (they see it in their in-app inbox)"></textarea>
            <div class="text-end text-muted fs-9 mt-1">{{ messageModal.body.length }}/2000</div>
            <div v-if="messageError" class="text-danger small mt-1"><i class="bi bi-exclamation-triangle-fill me-1"></i>{{ messageError }}</div>
          </div>
          <div class="assign-modal-footer d-flex justify-content-end gap-2">
            <button class="btn btn-light border btn-sm" @click="messageModal = null" :disabled="sending">Close</button>
            <button class="btn btn-primary btn-sm d-inline-flex align-items-center gap-1.5"
                    :disabled="sending || !messageModal.body.trim()" @click="sendMessage">
              <span v-if="sending" class="spinner-border spinner-border-sm"></span>
              <i v-else class="bi bi-send-fill"></i>
              <span>Send message</span>
            </button>
          </div>
        </div>
      </div>
    </transition>

    <!-- ===================== BROADCAST MODAL ===================== -->
    <transition name="modal-fade">
      <div v-if="broadcastModal" class="assign-modal-backdrop" @click.self="broadcastModal = null">
        <div class="assign-modal-card shadow-lg" style="max-width: 520px;">
          <div class="assign-modal-header d-flex justify-content-between align-items-center">
            <div class="d-flex align-items-center gap-3">
              <div class="avatar-circle-lg bg-primary-subtle text-primary"><i class="bi bi-broadcast"></i></div>
              <div>
                <h5 class="fw-bold mb-0 text-dark">Broadcast to all annotators</h5>
                <small class="text-muted">Sends the same message to every annotator on this team.</small>
              </div>
            </div>
            <button class="btn-close" @click="broadcastModal = null"></button>
          </div>
          <div class="assign-modal-body">
            <label class="form-label fw-semibold text-dark small">Message</label>
            <textarea v-model="broadcastModal.body" class="form-control" rows="4" maxlength="2000"
                      placeholder="Announcement for everyone…"></textarea>
            <div class="text-end text-muted fs-9 mt-1">{{ broadcastModal.body.length }}/2000</div>
            <div v-if="messageError" class="text-danger small mt-1"><i class="bi bi-exclamation-triangle-fill me-1"></i>{{ messageError }}</div>
          </div>
          <div class="assign-modal-footer d-flex justify-content-end gap-2">
            <button class="btn btn-light border btn-sm" @click="broadcastModal = null" :disabled="sending">Cancel</button>
            <button class="btn btn-primary btn-sm d-inline-flex align-items-center gap-1.5"
                    :disabled="sending || !broadcastModal.body.trim()" @click="sendBroadcast">
              <span v-if="sending" class="spinner-border spinner-border-sm"></span>
              <i v-else class="bi bi-broadcast"></i>
              <span>Broadcast</span>
            </button>
          </div>
        </div>
      </div>
    </transition>

    <!-- ===================== REMOVE (DEACTIVATE) MODAL ===================== -->
    <transition name="modal-fade">
      <div v-if="removeModal" class="assign-modal-backdrop" @click.self="removeModal = null">
        <div class="assign-modal-card shadow-lg" style="max-width: 520px;">
          <div class="assign-modal-header d-flex justify-content-between align-items-center">
            <div class="d-flex align-items-center gap-3">
              <div class="avatar-circle-lg bg-danger-subtle text-danger"><i class="bi bi-person-dash-fill"></i></div>
              <div>
                <h5 class="fw-bold mb-0 text-dark">Deactivate annotator</h5>
                <small class="text-muted">{{ removeModal.rater.name }} · {{ removeModal.rater.email }}</small>
              </div>
            </div>
            <button class="btn-close" @click="removeModal = null"></button>
          </div>
          <div class="assign-modal-body">
            <div class="d-flex align-items-start gap-2 py-2 px-3 rounded-3 bg-warning-subtle mb-3">
              <i class="bi bi-shield-check text-warning-emphasis mt-1"></i>
              <small class="text-dark">
                This <strong>deactivates</strong> the account (they can no longer log in) and
                <strong>unlocks their {{ (removeModal.rater.assigned_task_ids || []).length }} assigned task(s)</strong>
                so others can pick them up. Their submitted annotations are <strong>kept</strong>,
                and this is <strong>reversible</strong> — you can Reactivate them later.
              </small>
            </div>
            <label class="form-label fw-semibold text-dark small">
              Type <code class="text-danger">deactivate {{ removeModal.rater.name }}</code> to confirm
            </label>
            <input v-model="removeModal.confirm" type="text" class="form-control"
                   :class="{ 'is-invalid': removeModal.confirm && !removeConfirmMatches }"
                   :placeholder="`deactivate ${removeModal.rater.name}`"
                   autocomplete="off"
                   @keyup.enter="removeConfirmMatches && deactivateRater()" />
            <div v-if="removeError" class="text-danger small mt-2"><i class="bi bi-exclamation-triangle-fill me-1"></i>{{ removeError }}</div>
          </div>
          <div class="assign-modal-footer d-flex justify-content-end gap-2">
            <button class="btn btn-light border btn-sm" @click="removeModal = null" :disabled="removing">Cancel</button>
            <button class="btn btn-danger btn-sm d-inline-flex align-items-center gap-1.5"
                    :disabled="removing || !removeConfirmMatches" @click="deactivateRater">
              <span v-if="removing" class="spinner-border spinner-border-sm"></span>
              <i v-else class="bi bi-person-dash-fill"></i>
              <span>Deactivate annotator</span>
            </button>
          </div>
        </div>
      </div>
    </transition>

    <!-- ===================== SENT MESSAGES (OUTBOX) MODAL ===================== -->
    <transition name="modal-fade">
      <div v-if="outboxOpen" class="assign-modal-backdrop" @click.self="outboxOpen = false">
        <div class="assign-modal-card shadow-lg" style="max-width: 680px;">
          <div class="assign-modal-header d-flex justify-content-between align-items-center">
            <div class="d-flex align-items-center gap-3">
              <div class="avatar-circle-lg bg-secondary-subtle text-secondary"><i class="bi bi-clock-history"></i></div>
              <div>
                <h5 class="fw-bold mb-0 text-dark">Sent messages</h5>
                <small class="text-muted">Messages and broadcasts you've shared with this team.</small>
              </div>
            </div>
            <button class="btn-close" @click="outboxOpen = false"></button>
          </div>
          <div class="assign-modal-body" style="max-height: 60vh; overflow-y: auto;">
            <div v-if="outboxLoading" class="text-center text-muted py-4">
              <span class="spinner-border spinner-border-sm me-2"></span> Loading…
            </div>
            <div v-else-if="!outbox.length" class="text-center text-muted py-4">
              <i class="bi bi-inbox fs-3 d-block mb-2"></i> You haven't sent any messages yet.
            </div>
            <div v-else class="d-flex flex-column gap-2">
              <div v-for="(item, i) in outbox"
                   :key="item.kind === 'broadcast' ? 'b-' + item.broadcast_id : 'm-' + item.id"
                   class="border rounded-3 p-3">
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
                    <span class="small text-dark fw-semibold">
                      {{ item.kind === 'broadcast' ? `${item.recipients_total} annotator(s)` : item.rater_name }}
                    </span>
                    <span v-if="item.kind === 'broadcast'" class="fs-9 text-muted">{{ item.recipients_read }}/{{ item.recipients_total }} read</span>
                    <span v-else class="fs-9" :class="item.is_read ? 'text-success' : 'text-muted'">
                      <i :class="['bi', item.is_read ? 'bi-check2-all' : 'bi-check2']"></i> {{ item.is_read ? 'Read' : 'Unread' }}
                    </span>
                    <span v-if="item.edited_at" class="badge bg-light text-secondary border">edited</span>
                  </div>
                  <button v-if="item.kind !== 'broadcast' && editingMsg !== i"
                          class="btn btn-link btn-sm p-0 text-secondary flex-shrink-0"
                          title="Edit this message" @click="editingMsg = i; editBody = item.body">
                    <i class="bi bi-pencil"></i>
                  </button>
                </div>

                <template v-if="editingMsg === i">
                  <textarea v-model="editBody" class="form-control form-control-sm mt-2" rows="3" maxlength="2000"></textarea>
                  <div class="d-flex justify-content-end gap-2 mt-2">
                    <button class="btn btn-light border btn-sm" @click="editingMsg = null">Cancel</button>
                    <button class="btn btn-primary btn-sm" @click="saveMessageEdit(item, i)">Save changes</button>
                  </div>
                </template>
                <div v-else class="small text-dark mt-2" style="white-space: pre-wrap; word-break: break-word;">{{ item.body }}</div>

                <div class="text-muted fs-9 mt-1">{{ fmtDate(item.created_at) }}</div>
              </div>
            </div>
          </div>
          <div class="assign-modal-footer d-flex justify-content-end">
            <button class="btn btn-light border btn-sm" @click="outboxOpen = false">Close</button>
          </div>
        </div>
      </div>
    </transition>

    <!-- ===================== LANGUAGES & PULL SIZE MODAL ===================== -->
    <transition name="modal-fade">
      <div v-if="memberModal" class="assign-modal-backdrop" @click.self="memberModal = null">
        <div class="assign-modal-card shadow-lg" style="max-width: 520px;">
          <div class="assign-modal-header d-flex justify-content-between align-items-center">
            <div class="d-flex align-items-center gap-3">
              <div class="avatar-circle-lg">{{ (memberModal.name || '?').charAt(0).toUpperCase() }}</div>
              <div>
                <h5 class="fw-bold mb-0 text-dark">Languages &amp; pull size</h5>
                <small class="text-muted">{{ memberModal.name }}</small>
              </div>
            </div>
            <button class="btn-close" @click="memberModal = null"></button>
          </div>
          <div class="assign-modal-body">
            <div class="d-flex align-items-start gap-2 py-2 px-3 rounded-3 bg-info-subtle mb-3">
              <i class="bi bi-info-circle-fill text-info mt-1"></i>
              <small class="text-info-emphasis">
                What they actually work on is their <strong>assigned tasks</strong>. These two
                settings are the coarse limits: which languages they may be given at all, and how
                many prompts one "Get prompts" hands them.
              </small>
            </div>
            <label class="form-label fw-semibold text-dark small mb-1">
              Languages they may be given <span class="text-muted fw-normal">(none = every language)</span>
            </label>
            <div class="d-flex flex-wrap gap-2 mb-3">
              <label v-for="L in languages" :key="L.language" class="lang-check">
                <input type="checkbox" :value="L.language" v-model="memberModal.languages"> {{ L.language }}
              </label>
            </div>
            <label class="form-label fw-semibold text-dark small mb-1">Prompts per "Get prompts"</label>
            <input type="number" v-model.number="memberModal.pull_size" class="form-control" min="1" max="500">
          </div>
          <div class="assign-modal-footer d-flex justify-content-between align-items-center gap-2">
            <button class="btn btn-outline-danger btn-sm" @click="removeMember">Remove from team</button>
            <div class="d-flex gap-2">
              <button class="btn btn-light border btn-sm" @click="memberModal = null">Cancel</button>
              <button class="btn btn-primary btn-sm d-inline-flex align-items-center gap-1.5"
                      :disabled="savingMember" @click="saveMember">
                <span v-if="savingMember" class="spinner-border spinner-border-sm"></span>
                <i v-else class="bi bi-check2-circle"></i>
                <span>Save</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </transition>

    <!-- ══ export with live progress ══ -->
    <div v-if="exportOpen" class="asr-modal-backdrop" @click.self="closeExport">
      <div class="asr-modal">
        <div class="asr-modal-head">
          <h5 class="fw-bold mb-0">Export the pool</h5>
          <button class="btn-close" @click="closeExport"></button>
        </div>
        <div class="asr-modal-body">
          <template v-if="!exportJob">
            <label class="form-label fw-semibold text-xs text-uppercase text-secondary">Format</label>
            <div class="btn-group w-100 mb-3">
              <button class="btn" :class="exportFormat === 'xlsx' ? 'btn-primary' : 'btn-outline-secondary'"
                      @click="exportFormat = 'xlsx'"><i class="bi bi-file-earmark-excel me-1"></i>Excel</button>
              <button class="btn" :class="exportFormat === 'csv' ? 'btn-primary' : 'btn-outline-secondary'"
                      @click="exportFormat = 'csv'"><i class="bi bi-filetype-csv me-1"></i>CSV</button>
            </div>
            <label class="form-label fw-semibold text-xs text-uppercase text-secondary">Rows</label>
            <select v-model="exportScope" class="form-select mb-3">
              <option value="all">Everything in the pool</option>
              <option value="done">Only annotated prompts</option>
            </select>
            <label class="form-label fw-semibold text-xs text-uppercase text-secondary">Language</label>
            <select v-model="exportLanguage" class="form-select mb-3">
              <option value="">All languages</option>
              <option v-for="L in languages" :key="L.language" :value="L.language">{{ L.language }}</option>
            </select>
            <label class="form-label fw-semibold text-xs text-uppercase text-secondary">Task</label>
            <select v-model="exportTaskId" class="form-select mb-3">
              <option value="">Every task</option>
              <option v-for="t in tasks" :key="t.task_id" :value="String(t.task_id)">
                #{{ t.task_id }} — {{ t.label }}
              </option>
            </select>
            <label class="form-label fw-semibold text-xs text-uppercase text-secondary">Category</label>
            <select v-model="exportCategory" class="form-select">
              <option value="">Every category</option>
              <option v-for="c in subMeta.categories" :key="c" :value="c">{{ c }}</option>
            </select>
            <p class="text-muted text-xs mt-3 mb-0">
              Every row carries the original prompt, what the annotator submitted, the labels,
              who did it, when, and the task it belongs to.
            </p>
          </template>

          <div v-else class="text-center py-2">
            <div class="fw-semibold text-dark mb-3">
              <span v-if="exportJob.status !== 'done' && exportJob.status !== 'error'" class="spinner-border spinner-border-sm me-2"></span>
              <i v-else-if="exportJob.status === 'done'" class="bi bi-check-circle-fill text-success me-2"></i>
              <i v-else class="bi bi-exclamation-octagon-fill text-danger me-2"></i>
              {{ exportLabel }}
            </div>
            <div class="progress" style="height:10px">
              <div class="progress-bar" :class="{ 'progress-bar-striped progress-bar-animated': exportJob.status !== 'done' }"
                   :style="{ width: (exportJob.percent || 0) + '%' }"></div>
            </div>
            <div class="text-xs text-muted mt-2">
              {{ (exportJob.done || 0).toLocaleString() }} / {{ (exportJob.total || 0).toLocaleString() }} rows
              <span v-if="exportJob.percent">· {{ exportJob.percent }}%</span>
            </div>
            <p v-if="exportJob.status === 'error'" class="text-danger small mt-2 mb-0">{{ exportJob.error }}</p>
          </div>
        </div>
        <div class="asr-modal-foot">
          <button class="btn btn-secondary" @click="closeExport">
            {{ exportJob && exportJob.status === 'done' ? 'Close' : 'Cancel' }}
          </button>
          <button v-if="!exportJob" class="btn btn-primary" @click="startExport">
            <i class="bi bi-gear me-1"></i>Build the file
          </button>
          <button v-else-if="exportJob.status === 'done'" class="btn btn-success" :disabled="downloading" @click="downloadExport">
            <span v-if="downloading" class="spinner-border spinner-border-sm me-1"></span>
            <i v-else class="bi bi-download me-1"></i>Download
          </button>
        </div>
      </div>
    </div>

    <!-- simple report overlay -->
    <div v-if="simpleExport" class="asr-modal-backdrop">
      <div class="bg-white rounded shadow-lg px-4 py-3 fw-semibold text-dark d-flex align-items-center">
        <span v-if="simpleExport.state === 'busy'" class="spinner-border spinner-border-sm me-2"></span>
        <i v-else-if="simpleExport.state === 'done'" class="bi bi-check-circle-fill text-success me-2"></i>
        <i v-else class="bi bi-exclamation-octagon-fill text-danger me-2"></i>
        {{ simpleExport.label }}
        <span v-if="simpleExport.state === 'busy'" class="text-muted ms-2">building…</span>
      </div>
    </div>

    <div v-if="toast" class="asr-toast">{{ toast }}</div>
  </div>
</template>

<script setup>
import { ref, computed, reactive, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import { api, authToken, session } from '@/session'
import MdfsEvaluation from '@/components/MdfsEvaluation.vue'
import { API_BASE_URL } from '@/config'
import DiffToggle from '@/components/DiffToggle.vue'

// Which team's dashboard this is (from /<team>/admin); works for any pool team.
const route = useRoute()
const teamKey = computed(() =>
  String(route.params.team || session.team?.key || 'asr').toLowerCase())

// Same icons the TTS dashboard uses for the same ideas, so the two read as one product.
const tabs = [
  { key: 'overview',    label: 'Overview',    icon: 'bi-grid-1x2-fill', hint: 'Key numbers and language stats' },
  { key: 'tasks',       label: 'Tasks',       icon: 'bi-list-task',     hint: 'Every task, who holds it, how far along it is' },
  { key: 'annotators',  label: 'Annotators',  icon: 'bi-people-fill',   hint: 'Assign tasks, message & manage annotators' },
  { key: 'submissions', label: 'Submissions', icon: 'bi-list-check',    hint: 'Every prompt and the submission made against it' },
  { key: 'activity',    label: 'Activity',    icon: 'bi-clock-history', hint: 'Everything that happened, with timestamps' },
  { key: 'admin',       label: 'Admin',       icon: 'bi-gear-fill',     hint: 'Signup PIN, reports and maintenance' },
]
const tab = ref('overview')

const loading = ref(false)
const error = ref('')
const stats = ref({})
const languages = ref([])
const annotators = ref([])
const daily = ref([])
const uploads = ref([])
const staleHours = ref(48)
const difficulties = ref(['Easy', 'Medium', 'Hard'])
const expanded = reactive({})
const lastLoaded = ref('')
const isAutoRefreshActive = ref(true)
const refreshInterval = 10
const countdown = ref(refreshInterval)
let countdownTimer = null
const reclaiming = ref(false)
const toast = ref('')

// Team-level switches the admin controls (from /pool/admin/dashboard).
const teamSettings = ref({ difficulty_annotation: true })
const savingSetting = ref(false)
// The pull-limit input, edited freely and only saved on the button press.
const pullCapDraft = ref(0)

/** Save the ceiling on unfinished prompts one annotator may hold (0 = no limit). */
async function savePullCap() {
  const cap = Math.max(0, Math.floor(Number(pullCapDraft.value) || 0))
  savingSetting.value = true
  try {
    const r = await api('/pool/admin/settings', {
      method: 'POST',
      body: JSON.stringify({ team: teamKey.value, max_open_items: cap }),
    })
    teamSettings.value = r.settings || { ...teamSettings.value, max_open_items: cap }
    pullCapDraft.value = cap
    flash(cap ? `Annotators can now hold at most ${cap} unfinished prompt(s) at a time.`
              : 'The pull limit is off — annotators can hold any number of prompts.')
  } catch (e) {
    flash(e.message)
  } finally {
    savingSetting.value = false
  }
}

/** Set the difficulty-labelling toggle for tasks (optionally one category). on = true / false / null — null clears the override so the level above decides. Each level stores its own value; nothing writes through to another level. */
/** How many annotators should answer each prompt, per PROJECT (kind of work).
 *  A project with no number of its own follows the pool default. Raising it puts
 *  already-finished prompts back in circulation until they have that many answers;
 *  lowering it never discards an answer already given. */
const annotationsPerByType = ref({})
const projectAnnotationsPer = computed(() =>
  annotationsPerByType.value[projectTab.value] || { override: null, effective: 1 })

/** How many times each prompt of this project is answered. Independent of how
 *  many annotators may share a task: this one is about answering the same prompt
 *  more than once, so raising it puts finished prompts back in circulation until
 *  they have that many answers. */
async function setProjectAnnotationsPer(taskType, value) {
  const n = (value === null || value === '') ? null : Math.max(Number(value) || 1, 1)
  const next = { ...(teamSettings.value.annotations_per_prompt_by_task_type || {}) }
  if (n === null) delete next[taskType]
  else next[taskType] = n
  try {
    const r = await api('/pool/admin/settings', {
      method: 'POST',
      body: JSON.stringify({ team: teamKey.value,
                             annotations_per_prompt_by_task_type: next }),
    })
    teamSettings.value = r.settings || teamSettings.value
    flash(n === null
      ? 'This project now follows the pool default.'
      : 'Each prompt here goes to ' + n + ' annotator(s).')
    loadTasks()
  } catch (e) {
    flash(e.message)
  }
}

async function setDifficulty(taskIds, category, on) {
  try {
    const r = await api('/pool/admin/tasks/settings', {
      method: 'POST',
      body: JSON.stringify({
        team: teamKey.value, task_ids: taskIds, category: category || '',
        difficulty_annotation: on === null ? null : !!on,
      }),
    })
    flash(r.message)
    loadTasks()
    if (taskModal.value?.task?.task_id) await openTask(taskModal.value.task.task_id)
  } catch (e) {
    flash(e.message)
  }
}

/** The task's toggle state in the detail modal: the resolved value plus whether it is set on the task itself. */
const modalTaskDiff = computed(() => {
  const ds = taskModal.value?.task?.difficulty_settings
  if (!ds) return { on: true, overridden: false }
  return {
    on: (ds.task_effective ?? ds.task ?? ds.language_effective ?? ds.team_default) !== false,
    overridden: ds.task !== null && ds.task !== undefined,
  }
})

/** Flip whether annotators are asked to label difficulty at all. */
async function toggleDifficultySetting() {
  const next = !(teamSettings.value.difficulty_annotation !== false)
  savingSetting.value = true
  try {
    const r = await api('/pool/admin/settings', {
      method: 'POST',
      body: JSON.stringify({ team: teamKey.value, difficulty_annotation: next }),
    })
    teamSettings.value = r.settings || { ...teamSettings.value, difficulty_annotation: next }
    flash(next ? 'Annotators will now label difficulty on every prompt.'
               : 'Difficulty labelling is now OFF — annotators only review the text.')
  } catch (e) {
    flash(e.message)
  } finally {
    savingSetting.value = false
  }
}

// ── tasks: one per language x class, the unit the admin hands out ──
const tasksSubTab = ref('overview')
const tasks = ref([])
const taskTotals = ref({})
const taskLanguages = ref([])
const taskClasses = ref([])
const taskTypes = ref([])
const taskStates = ref([])

function humanizeType(t) {
  return String(t || '').replace(/[-_]/g, ' ').replace(/^\w/, c => c.toUpperCase())
}
const tasksLoading = ref(false)
const selectedTasks = ref([])
const taskFilters = reactive({ language: '', class: '', type: '', state: '', annotator: '', q: '' })
const taskModal = ref(null)
const taskLoading = ref(false)

// ── assignment ──
const assignModal = ref(null)
const assignCandidates = ref([])
const assignableTasks = ref([])
const assignSearch = ref('')
const assigning = ref(false)
const assignError = ref('')

// ── submissions: every prompt and what was submitted against it ──
const submissions = ref([])
const subLoading = ref(false)
const subPage = ref(1)
const subPages = ref(1)
const subTotal = ref(0)
const subMeta = ref({ tasks: [], languages: [], classes: [], categories: [], annotators: [] })
const subFilters = reactive({ task_id: '', language: '', class: '', category: '',
                              annotator: '', state: 'submitted', difficulty: '',
                              edited: '', flagged: '', changed: '', from: '', to: '', q: '' })

const memberModal = ref(null)
const savingMember = ref(false)
const annotatorModal = ref(null)
const annotatorLoading = ref(false)
const itemModal = ref(null)
const messageModal = ref(null)
const broadcastModal = ref(null)
const sending = ref(false)
const signupPin = ref('')
const pinCopied = ref(false)

// ── annotators tab: members vs the signup approval queue ──
const annotSubTab = ref('members')
const pendingSignups = ref([])
const pendingLoading = ref(false)
const approving = ref(0)

async function loadPending() {
  pendingLoading.value = true
  try {
    pendingSignups.value = (await api('/admin/team/pending')).pending || []
  } catch (e) {
    flash(e.message)
  } finally {
    pendingLoading.value = false
  }
}

/** Let a pending signup into THIS team (they stay visible to other teams until someone approves them). */
async function approveSignup(p) {
  approving.value = p.rater_id
  try {
    const r = await api('/pool/admin/member', {
      method: 'POST',
      body: JSON.stringify({ team: teamKey.value, rater_id: p.rater_id }),
    })
    flash(r.message || `${p.name} is now in the team.`)
    await loadPending()
    load()
  } catch (e) {
    flash(e.message)
  } finally {
    approving.value = 0
  }
}

// ── annotators tab: search, sort, stale alert, menus, drill-down ──
const STALE_DAYS = 5
const raterSearch = ref('')
const showInactive = ref(false)
const showStaleOnly = ref(false)
const raterSort = ref({ key: 'default', dir: 'asc' })
const expandedRaters = ref([])
const raterTasks = reactive({})
const raterTasksLoading = ref(null)
const bulkNudging = ref(false)
const openMenu = ref(null)
const menuPos = reactive({ top: 0, left: 0 })
const removeModal = ref(null)
const removing = ref(false)
const removeError = ref('')
const removeConfirmMatches = computed(() =>
  !!removeModal.value
  && removeModal.value.confirm.trim().toLowerCase() === `deactivate ${removeModal.value.rater.name}`.toLowerCase())
const messageError = ref('')
const threadItems = ref([])
const threadLoading = ref(false)
const threadBox = ref(null)
const outboxOpen = ref(false)
const outbox = ref([])
const outboxLoading = ref(false)
const editingMsg = ref(null)
const editBody = ref('')

const activityPresets = [
  { label: 'Today', days: 0 },
  { label: '7d', days: 7 },
  { label: '30d', days: 30 },
  { label: 'All time', days: null },
]
const activityFrom = ref('')
const activityTo = ref('')
const activityWindow = ref(null)
const activityLoading = ref(false)
const windowDays = ref({})
const todayIst = ref('')

const activity = ref([])
const activityDays = ref(7)
const actLoading = ref(false)
const actFilters = reactive({ event: '', annotator: '', language: '', q: '' })
const actPage = ref(1)
const actPages = ref(1)
const actTotal = ref(0)
const actPerPage = ref(50)
const actSummary = ref({})
const actEventTypes = ['pulled', 'labelled', 'edited & labelled', 'flagged']
const actSummaryTotal = computed(() =>
  Object.values(actSummary.value).reduce((s, n) => s + n, 0))
const actFiltersDirty = computed(() =>
  !!(actFilters.event || actFilters.annotator || actFilters.language || actFilters.q))
const actView = ref('grouped')
const expandedActGroups = ref([])

/** Day sections; inside a day, consecutive events of the same kind by the same
 *  annotator (a pull of 40 prompts, a labelling run) fold into one group. */
const groupedActivity = computed(() => {
  const days = []
  let day = null
  let group = null
  for (const e of activity.value) {
    const dkey = (e.when_ist || '').slice(0, 10)
    if (!day || day.date !== dkey) {
      day = { date: dkey, groups: [], count: 0 }
      days.push(day)
      group = null
    }
    const gkey = `${e.event}|${e.annotator}|${e.language}|${e.class}`
    if (!group || group.key !== gkey) {
      group = { key: gkey, id: `${dkey}#${day.groups.length}`, event: e.event,
                annotator: e.annotator, language: e.language, class: e.class, items: [] }
      day.groups.push(group)
    }
    group.items.push(e)
    day.count += 1
  }
  return days
})

function toggleActGroup(id) {
  const i = expandedActGroups.value.indexOf(id)
  if (i === -1) expandedActGroups.value.push(id)
  else expandedActGroups.value.splice(i, 1)
}

function dayLabel(iso) {
  if (!iso) return '—'
  const [y, m, d] = iso.split('-').map(Number)
  const date = new Date(y, m - 1, d)
  const today = new Date(); today.setHours(0, 0, 0, 0)
  const diff = Math.round((today - date) / 86400000)
  const pretty = date.toLocaleDateString('en-IN', { weekday: 'short', day: '2-digit', month: 'short', year: 'numeric' })
  if (diff === 0) return `Today · ${pretty}`
  if (diff === 1) return `Yesterday · ${pretty}`
  return pretty
}

/** Events arrive newest first, so the range reads oldest → newest. */
function groupTimeRange(g) {
  const first = g.items[g.items.length - 1].when_ist.slice(11, 16)
  const last = g.items[0].when_ist.slice(11, 16)
  return first === last ? last : `${first} – ${last}`
}

function groupSeconds(g) {
  const total = g.items.reduce((s, e) => s + (e.seconds || 0), 0)
  if (!total) return ''
  if (total < 60) return `${Math.round(total)}s`
  const m = Math.floor(total / 60)
  return m < 60 ? `${m}m ${Math.round(total % 60)}s` : `${Math.floor(m / 60)}h ${m % 60}m`
}

const exportOpen = ref(false)
const exportFormat = ref('xlsx')
const exportScope = ref('all')
const exportLanguage = ref('')
const exportTaskId = ref('')
const exportCategory = ref('')
const exportJob = ref(null)
const downloading = ref(false)
const simpleExport = ref(null)
let pollTimer = null

const exportLabel = computed(() => {
  const s = exportJob.value?.status
  if (s === 'done') return 'Your file is ready.'
  if (s === 'error') return 'The export failed.'
  if (s === 'queued') return 'Starting…'
  return 'Building your file…'
})

function pct(n, total) { return total ? `${(100 * n) / total}%` : '0%' }
/** Never show a flat 0% when real work has been done. */
function showPct(p, done) { return (!p && done) ? '<0.1' : (p || 0) }
function diffClass(k) {
  return { Easy: 'bg-success', Medium: 'bg-warning', Hard: 'bg-danger' }[k] || 'bg-secondary'
}
function badgeFor(d) {
  return { easy: 'bg-success-subtle text-success', medium: 'bg-warning-subtle text-warning',
           hard: 'bg-danger-subtle text-danger' }[String(d || '').toLowerCase()]
         || 'bg-light text-secondary border'
}
function statusBadge(s) {
  return { completed: 'bg-success-subtle text-success', flagged: 'bg-warning-subtle text-warning',
           claimed: 'bg-info-subtle text-info', available: 'bg-light text-secondary border' }[s]
         || 'bg-light text-secondary border'
}
function stateBadge(s) {
  return { complete: 'bg-success-subtle text-success', 'in-progress': 'bg-info-subtle text-info',
           'not-started': 'bg-light text-secondary border',
           unassigned: 'bg-danger-subtle text-danger' }[s] || 'bg-light text-secondary border'
}
function pullBadge(s) {
  return { open: 'bg-info-subtle text-info', done: 'bg-success-subtle text-success',
           released: 'bg-light text-secondary border' }[s] || 'bg-light text-secondary border'
}
function rtl(lang) { return String(lang || '').toLowerCase() === 'urdu' }
function trim(t, n = 90) {
  const s = (t || '').replace(/\s+/g, ' ').trim()
  return s.length > n ? s.slice(0, n) + '…' : s
}
function fmtDate(v) {
  if (!v) return '—'
  return new Date(v).toLocaleString('en-IN', { day: '2-digit', month: 'short',
                                               hour: '2-digit', minute: '2-digit' })
}
function toggle(lang) { expanded[lang] = !expanded[lang] }
function flash(msg) {
  toast.value = msg
  setTimeout(() => (toast.value = ''), 2600)
}

/** Rows come from the chosen date window; with no window, from the dashboard. Search, the inactive. */
const shownAnnotators = computed(() => {
  const base = activityWindow.value ? activityWindow.value.raters : annotators.value
  // A windowed row carries only that window's numbers; merge the standing facts
  const facts = Object.fromEntries(annotators.value.map(a => [a.rater_id, a]))
  let rows = base.map(a => ({ ...(facts[a.rater_id] || {}), ...a }))

  const q = raterSearch.value.trim().toLowerCase()
  if (q) rows = rows.filter(a => `${a.name} ${a.email}`.toLowerCase().includes(q))
  if (!showInactive.value) rows = rows.filter(a => a.account_active !== false)
  if (showStaleOnly.value) rows = rows.filter(isStale)

  const { key, dir } = raterSort.value
  const sign = dir === 'asc' ? 1 : -1
  const sorted = [...rows]
  if (key === 'name') sorted.sort((a, b) => sign * (a.name || '').localeCompare(b.name || ''))
  else if (key === 'assigned') sorted.sort((a, b) => sign * ((a.assigned_task_ids?.length || 0) - (b.assigned_task_ids?.length || 0)))
  else if (key === 'completed') sorted.sort((a, b) => sign * ((a.completed || 0) - (b.completed || 0)))
  else if (key === 'lastactive') sorted.sort((a, b) => sign * (new Date(a.last_active || 0) - new Date(b.last_active || 0)))
  else sorted.sort((a, b) => (b.completed || 0) - (a.completed || 0))
  return sorted
})

/** Holding tasks but silent for STALE_DAYS+ days (or never active at all). */
function isStale(a) {
  if (!a || !(a.assigned_task_ids || []).length) return false
  if (a.account_active === false) return false
  if (!a.last_active) return true
  return (Date.now() - new Date(a.last_active).getTime()) / 86400000 >= STALE_DAYS
}
const staleRaters = computed(() => annotators.value.filter(isStale))

function sortRaters(key) {
  raterSort.value = raterSort.value.key === key
    ? { key, dir: raterSort.value.dir === 'asc' ? 'desc' : 'asc' }
    : { key, dir: key === 'name' ? 'asc' : 'desc' }
}
function sortIcon(key) {
  if (raterSort.value.key !== key) return 'bi-arrow-down-up text-muted opacity-50'
  return raterSort.value.dir === 'asc' ? 'bi-sort-up' : 'bi-sort-down'
}

function allTimeFor(id) {
  return annotators.value.find(a => a.rater_id === id)?.completed || 0
}
function raterStatus(a) {
  if (!(a.assigned_task_ids || []).length) return 'Unassigned'
  if (a.in_progress || a.holding) return 'Working'
  if (a.completed) return 'Active'
  return 'Not started'
}
function raterStatusClass(a) {
  const s = raterStatus(a)
  return s === 'Working' ? 'is-working' : s === 'Active' ? 'is-active'
       : s === 'Unassigned' ? 'is-idle' : 'is-new'
}
function raterStatusIcon(a) {
  const s = raterStatus(a)
  return s === 'Working' ? 'bi-hourglass-split' : s === 'Active' ? 'bi-check-circle-fill'
       : s === 'Unassigned' ? 'bi-dash-circle' : 'bi-circle'
}
function timeAgo(iso) {
  if (!iso) return 'never active'
  const mins = Math.floor((Date.now() - new Date(iso).getTime()) / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const h = Math.floor(mins / 60)
  if (h < 24) return `${h}h ago`
  const d = Math.floor(h / 24)
  return d < 30 ? `${d}d ago` : `${Math.floor(d / 30)}mo ago`
}

async function toggleRaterTasks(a) {
  const i = expandedRaters.value.indexOf(a.rater_id)
  if (i !== -1) { expandedRaters.value.splice(i, 1); return }
  expandedRaters.value.push(a.rater_id)
  if (raterTasks[a.rater_id]) return
  raterTasksLoading.value = a.rater_id
  try {
    const d = await api(`/pool/admin/annotator/${a.rater_id}?team=${teamKey.value}`)
    raterTasks[a.rater_id] = d.by_task || []
  } catch (e) {
    flash(e.message)
  } finally {
    raterTasksLoading.value = null
  }
}

// ── pop-menus ──
function toggleMenu(key, ev, width = 240) {
  if (openMenu.value === key) { openMenu.value = null; return }
  const r = ev.currentTarget.getBoundingClientRect()
  menuPos.top = r.bottom + 6
  menuPos.left = Math.max(8, Math.min(r.right - width, window.innerWidth - width - 8))
  openMenu.value = key
}
// Header dropdowns (exports / messages) only -- annotator-row actions are inline buttons.
function runMenu(fn) { fn(); openMenu.value = null }

// ── annotator account actions ──
async function nudgeRater(a) {
  try {
    flash((await api(`/admin/rater/${a.rater_id}/nudge`, {
      method: 'POST', body: JSON.stringify({}),
    })).message)
  } catch (e) {
    flash(e.message)
  }
}

async function remindAllStale() {
  bulkNudging.value = true
  try {
    for (const a of staleRaters.value) {
      await api(`/admin/rater/${a.rater_id}/nudge`, { method: 'POST', body: JSON.stringify({}) })
    }
    flash(`Reminder sent to ${staleRaters.value.length} annotator(s).`)
  } catch (e) {
    flash(e.message)
  } finally {
    bulkNudging.value = false
  }
}

async function deactivateRater() {
  removing.value = true
  removeError.value = ''
  try {
    const r = await api(`/admin/rater/${removeModal.value.rater.rater_id}/deactivate`, {
      method: 'POST', body: JSON.stringify({ confirm: removeModal.value.confirm }),
    })
    flash(r.message)
    removeModal.value = null
    await Promise.all([load(), loadTasks()])
  } catch (e) {
    removeError.value = e.message
  } finally {
    removing.value = false
  }
}

async function reactivateRater(a) {
  try {
    flash((await api(`/admin/rater/${a.rater_id}/reactivate`, {
      method: 'POST', body: JSON.stringify({}),
    })).message)
    await load()
  } catch (e) {
    flash(e.message)
  }
}

// ── outbox ──
async function openOutbox() {
  outboxOpen.value = true
  outboxLoading.value = true
  editingMsg.value = null
  try {
    outbox.value = (await api(`/admin/messages?team=${teamKey.value}`)).items || []
  } catch (e) {
    flash(e.message)
  } finally {
    outboxLoading.value = false
  }
}

async function saveMessageEdit(m, i) {
  try {
    await api(`/admin/message/${m.id}`, {
      method: 'PUT', body: JSON.stringify({ body: editBody.value }),
    })
    outbox.value[i] = { ...m, body: editBody.value, edited_at: new Date().toISOString() }
    editingMsg.value = null
    flash('Message updated.')
  } catch (e) {
    flash(e.message)
  }
}

const windowPreset = computed(() => {
  if (!activityFrom.value && !activityTo.value) return 'All time'
  const today = new Date().toISOString().slice(0, 10)
  if (activityTo.value !== today) return null
  for (const pr of activityPresets) {
    if (pr.days === null) continue
    const d = new Date()
    d.setDate(d.getDate() - pr.days)
    if (activityFrom.value === d.toISOString().slice(0, 10)) return pr.label
  }
  return null
})

function applyPreset(pr) {
  if (pr.days === null) {
    activityFrom.value = ''
    activityTo.value = ''
  } else {
    const from = new Date()
    from.setDate(from.getDate() - pr.days)
    activityFrom.value = from.toISOString().slice(0, 10)
    activityTo.value = new Date().toISOString().slice(0, 10)
  }
  loadActivityWindow()
}

async function loadActivityWindow() {
  activityLoading.value = true
  try {
    const qs = new URLSearchParams({ team: teamKey.value })
    if (activityFrom.value) qs.set('from', activityFrom.value)
    if (activityTo.value) qs.set('to', activityTo.value)
    const d = await api('/pool/admin/rater_activity?' + qs)
    activityWindow.value = (activityFrom.value || activityTo.value) ? d : null
    todayIst.value = d.today
    windowDays.value = Object.fromEntries(d.raters.map(r => [r.rater_id, r.days]))
  } catch (e) {
    flash(e.message)
  } finally {
    activityLoading.value = false
  }
}

const annotatorDays = computed(() => {
  const id = annotatorModal.value?.annotator?.id
  return id ? (windowDays.value[id] || []) : []
})

function dayBarWidth(d) {
  const max = Math.max(1, ...annotatorDays.value.map(x => x.completed + x.flagged))
  return ((d.completed + d.flagged) / max) * 100 + '%'
}

function longDay(iso) {
  const [y, m, dd] = (iso || '').split('-').map(Number)
  if (!y) return iso
  return new Date(y, m - 1, dd).toLocaleDateString('en-IN',
    { weekday: 'short', day: '2-digit', month: 'short' })
}

function setTab(key) {
  tab.value = key
  if (key === 'tasks' && !tasks.value.length) loadTasks()
  if (key === 'submissions') {
    if (!subMeta.value.tasks.length) loadSubMeta()
    if (!submissions.value.length) loadSubmissions(1)
  }
  if (key === 'admin' && !signupPin.value) loadPin()
  if (key === 'activity' && !activity.value.length) loadActivity()
  if (key === 'annotators' && !todayIst.value) loadActivityWindow()
}

function eventBadge(e) {
  if (e === 'pulled') return 'bg-info-subtle text-info'
  if (e === 'flagged') return 'bg-warning-subtle text-warning'
  if (e === 'edited & labelled') return 'bg-primary-subtle text-primary'
  return 'bg-success-subtle text-success'
}

async function loadActivity(page = 1) {
  actLoading.value = true
  try {
    const qs = new URLSearchParams({
      team: teamKey.value, days: String(activityDays.value),
      page: String(page), per_page: String(actPerPage.value),
    })
    if (actFilters.event) qs.set('event', actFilters.event)
    if (actFilters.annotator) qs.set('rater_id', actFilters.annotator)
    if (actFilters.language) qs.set('language', actFilters.language)
    if (actFilters.q.trim()) qs.set('q', actFilters.q.trim())
    const d = await api('/pool/admin/activity?' + qs)
    activity.value = d.events || []
    expandedActGroups.value = []
    actPage.value = d.page || 1
    actPages.value = d.pages || 1
    actTotal.value = d.total ?? (d.events || []).length
    actSummary.value = d.summary || {}
  } catch (e) {
    flash(e.message)
  } finally {
    actLoading.value = false
  }
}

function setActEvent(ev) {
  actFilters.event = actFilters.event === ev ? '' : ev
  loadActivity(1)
}

function resetActFilters() {
  actFilters.event = ''
  actFilters.annotator = ''
  actFilters.language = ''
  actFilters.q = ''
  loadActivity(1)
}

async function load() {
  loading.value = true
  try {
    const d = await api(`/pool/admin/dashboard?team=${teamKey.value}`)
    stats.value = d.stats || {}
    languages.value = d.languages || []
    annotators.value = d.annotators || []
    daily.value = d.daily || []
    uploads.value = d.uploads || []
    staleHours.value = d.stale_claim_hours || 48
    difficulties.value = d.difficulties || difficulties.value
    if (d.settings) {
      // The auto-refresh must not clobber a half-typed pull limit: only follow the server value while the draft is unedited.
      const prev = teamSettings.value.max_open_items || 0
      teamSettings.value = d.settings
      if (pullCapDraft.value === prev) pullCapDraft.value = d.settings.max_open_items || 0
    }
    lastLoaded.value = new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })
    error.value = ''
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

// ── tasks ──────────────────────────────────────────────────────────────────
async function loadTasks() {
  // Spinner only while the table is still empty; the auto-refresh swaps data in place with no flicker.
  tasksLoading.value = !tasks.value.length
  try {
    const d = await api(`/pool/admin/tasks?team=${teamKey.value}`)
    tasks.value = d.tasks || []
    taskTotals.value = d.totals || {}
    taskLanguages.value = d.languages || []
    taskClasses.value = d.classes || []
    taskTypes.value = d.task_types || []
    annotationsPerByType.value = d.annotations_by_task_type || {}
    taskStates.value = d.states || []
    if (typeof d.difficulty_team_default === 'boolean') {
      teamSettings.value = { ...teamSettings.value,
                             difficulty_annotation: d.difficulty_team_default }
    }
  } catch (e) {
    error.value = e.message
  } finally {
    tasksLoading.value = false
  }
}

// ── project heads: each kind of work (task_type) is its own project; the whole tasks tab is scoped to one at a time ──
const projectTab = ref('')
const projectOptions = computed(() => {
  const seen = {}
  for (const t of tasks.value) {
    const key = t.task_type || 'text-review'
    const slot = seen[key] || (seen[key] = {
      key, label: t.task_type_label || humanizeType(key), count: 0, items: 0 })
    slot.count += 1
    slot.items += t.item_count || t.total || 0
  }
  // The original text-review project first, then the rest alphabetically.
  return Object.values(seen).sort((a, b) =>
    (a.key === 'text-review' ? -1 : b.key === 'text-review' ? 1 : a.label.localeCompare(b.label)))
})
watch(projectOptions, (opts) => {
  if (opts.length && !opts.some(o => o.key === projectTab.value)) projectTab.value = opts[0].key
}, { immediate: true })
// Switching project drops the ticked rows: bulk actions must never straddle two projects.
watch(projectTab, () => { selectedTasks.value = [] })
const projectTasks = computed(() =>
  tasks.value.filter(t => (t.task_type || 'text-review') === projectTab.value))
function projectIcon(key) {
  return { 'text-review': 'bi bi-pencil-square', 'audio-mdfs': 'bi bi-headphones' }[key]
    || 'bi bi-tools'
}

// ── admin preview: fetch one sample item and render the real annotator template ──
const preview = ref(null)
async function openPreview(taskOrType) {
  const isTask = typeof taskOrType === 'object'
  preview.value = {
    loading: true, item: null, draft: '', difficulty: '',
    scores: { expression: null, phrasing: null, smoothness: null, pacing: null, comments: '' },
    title: isTask
      ? `Task #${taskOrType.task_id} — ${taskOrType.label || taskOrType.language}`
      : (projectOptions.value.find(p => p.key === taskOrType)?.label || 'Task template'),
  }
  try {
    const qs = new URLSearchParams({ team: teamKey.value, per_page: '1', status: 'available' })
    if (isTask) qs.set('task_id', taskOrType.task_id)
    else qs.set('task_type', taskOrType)
    let d = await api(`/pool/admin/items?${qs}`)
    if (!(d.items || []).length) {          // nothing free right now: preview any item
      qs.delete('status')
      d = await api(`/pool/admin/items?${qs}`)
    }
    const it = (d.items || [])[0] || null
    if (preview.value) {
      preview.value.item = it
      preview.value.draft = it?.original_text || it?.text || ''
    }
  } catch (e) {
    flash(e.message)
    preview.value = null
  } finally {
    if (preview.value) preview.value.loading = false
  }
}

/** The task table filters in the browser: the whole list is one small payload, so every filter is i. */
const shownTasks = computed(() => {
  const q = taskFilters.q.trim().toLowerCase()
  return projectTasks.value.filter(t => {
    if (taskFilters.language && t.language !== taskFilters.language) return false
    if (taskFilters.class && String(t.class) !== taskFilters.class) return false
    if (taskFilters.state && t.state !== taskFilters.state) return false
    if (taskFilters.annotator === 'none' && holdersOf(t).length) return false
    if (taskFilters.annotator && taskFilters.annotator !== 'none'
        && !holdersOf(t).some(a => String(a.rater_id) === taskFilters.annotator)) return false
    if (q) {
      const hay = `${t.task_id} ${t.language} ${t.class} `
        .concat(holdersOf(t).map(a => a.name).join(' ')).toLowerCase()
      if (!hay.includes(q)) return false
    }
    return true
  })
})

const tasksByLanguage = computed(() => {
  const out = {}
  for (const t of projectTasks.value) {
    const L = out[t.language] || (out[t.language] = {
      language: t.language, tasks: [], assigned: 0,
      total: 0, completed: 0, flagged: 0, claimed: 0, available: 0, done: 0,
    })
    L.tasks.push(t)
    if (holdersOf(t).length) L.assigned += 1
    for (const k of ['total', 'completed', 'flagged', 'claimed', 'available', 'done']) L[k] += t[k]
  }
  return Object.values(out)
    .map(L => ({ ...L, progress: L.total ? Math.round(1000 * L.done / L.total) / 10 : 0 }))
    .sort((a, b) => a.language.localeCompare(b.language))
})

const allShownSelected = computed(() =>
  shownTasks.value.length > 0 && shownTasks.value.every(t => selectedTasks.value.includes(t.task_id)))

function toggleTaskPick(id) {
  const i = selectedTasks.value.indexOf(id)
  if (i === -1) selectedTasks.value.push(id)
  else selectedTasks.value.splice(i, 1)
}
function toggleSelectAll() {
  selectedTasks.value = allShownSelected.value ? [] : shownTasks.value.map(t => t.task_id)
}
function resetTaskFilters() {
  Object.keys(taskFilters).forEach(k => { taskFilters[k] = '' })
}

async function openTask(id) {
  if (!id) return
  taskLoading.value = true
  taskModal.value = { task: { task_id: id, label: '', total: 0, categories: [] },
                      annotators: [], pulls: [], assignment_history: [], recent_submissions: [] }
  try {
    taskModal.value = await api(`/pool/admin/task/${id}?team=${teamKey.value}`)
  } catch (e) {
    flash(e.message)
    taskModal.value = null
  } finally {
    taskLoading.value = false
  }
}

const notStartedTasks = computed(() =>
  tasks.value.filter(t => t.state === 'not-started').length)
const almostDoneTasks = computed(() =>
  tasks.value.filter(t => t.progress >= 80 && t.progress < 100).length)

/** Jump from an Overview card straight into the matching task list. */
function focusTasks(state) {
  resetTaskFilters()
  if (state !== 'almostdone') taskFilters.state = state
  setTab('tasks')
  tasksSubTab.value = 'all'
  if (!tasks.value.length) loadTasks()
}

function browseTask(id) {
  taskModal.value = null
  resetSubFilters(false)
  subFilters.task_id = String(id)
  setTab('submissions')
  loadSubmissions(1)
}

function openLanguage(L) {
  setTab('tasks')
  tasksSubTab.value = 'overview'
  expanded[L.language] = true
}

// ── assignment ─────────────────────────────────────────────────────────────

/** Every active holder of a task, whatever shape the API row came in. */
function holdersOf(t) {
  if (!t) return []
  if (t.assignees && t.assignees.length) return t.assignees
  return t.assignee ? [t.assignee] : []
}

function initialOf(name) {
  return (name || '?').trim().charAt(0).toUpperCase() || '?'
}

function holderTitle(a) {
  return `${a.name} — ${a.category ? `only “${a.category}”` : 'whole task'}`
       + (a.assigned_at_ist ? ` · since ${a.assigned_at_ist}` : '')
}

async function openAssign(taskIds = [], raterId = '') {
  assignError.value = ''
  assignSearch.value = ''
  assignModal.value = { rater_ids: raterId ? [Number(raterId)] : [], task_ids: [...taskIds],
                        category: '', mode: 'add' }
  try {
    const d = await api(`/pool/admin/tasks/assignable?team=${teamKey.value}`)
    assignCandidates.value = d.annotators || []
    assignableTasks.value = d.tasks || []
  } catch (e) {
    assignError.value = e.message
  }
}

const assignRaters = computed(() => {
  const picked = new Set((assignModal.value?.rater_ids || []).map(Number))
  return assignCandidates.value.filter(a => picked.has(Number(a.rater_id)))
})

function toggleAssignRater(id) {
  const list = assignModal.value.rater_ids
  const i = list.indexOf(id)
  if (i === -1) list.push(id)
  else list.splice(i, 1)
}

/** Categories offered by the Scope picker: the ones every selected task actually contains. */
const assignCategoryOptions = computed(() => {
  if (!assignModal.value || !assignModal.value.task_ids.length) return []
  const picked = assignableTasks.value.filter(t => assignModal.value.task_ids.includes(t.task_id))
  if (!picked.length) return []
  let common = null
  for (const t of picked) {
    const names = new Set(t.category_names || [])
    common = common === null ? names : new Set([...common].filter(c => names.has(c)))
  }
  return [...(common || [])].sort()
})

const assignableShown = computed(() => {
  const q = assignSearch.value.trim().toLowerCase()
  if (!q) return assignableTasks.value
  return assignableTasks.value.filter(t =>
    `${t.task_id} ${t.label} `
      .concat(holdersOf(t).map(a => a.name).join(' ')).toLowerCase().includes(q))
})

/** Holders of the selected scope who are NOT among the chosen annotators: kept alongside in 'add' mode, taken back in 'replace' mode. */
const assignOtherHolders = computed(() => {
  if (!assignModal.value) return []
  const picked = new Set(assignModal.value.rater_ids.map(Number))
  const cat = assignModal.value.category
  const out = []
  for (const t of assignableTasks.value) {
    if (!assignModal.value.task_ids.includes(t.task_id)) continue
    for (const a of holdersOf(t)) {
      if (picked.has(Number(a.rater_id))) continue
      // a category assign only touches that category's holders; whole-task holders keep the rest either way
      if (cat && a.category !== cat) continue
      out.push(`#${t.task_id}${a.category ? ' · ' + a.category : ''} (${a.name})`)
    }
  }
  return out
})

function toggleAssignPick(id) {
  const list = assignModal.value.task_ids
  const i = list.indexOf(id)
  if (i === -1) list.push(id)
  else list.splice(i, 1)
}

async function saveAssignment() {
  assigning.value = true
  assignError.value = ''
  try {
    const r = await api('/pool/admin/tasks/assign', {
      method: 'POST',
      body: JSON.stringify({ team: teamKey.value,
                             rater_ids: assignModal.value.rater_ids.map(Number),
                             task_ids: assignModal.value.task_ids,
                             category: assignModal.value.category || '',
                             mode: assignModal.value.mode }),
    })
    assignModal.value = null
    selectedTasks.value = []
    flash(r.message)
    await Promise.all([loadTasks(), load()])
  } catch (e) {
    assignError.value = e.message
  } finally {
    assigning.value = false
  }
}

/** Take a task back — from one annotator (pass their assignee row) or from everyone. */
async function unassignTask(t, a = null) {
  const who = a ? a.name
              : (holdersOf(t).map(h => h.name).join(', ') || 'the annotator')
  const scope = a?.category ? ` (their “${a.category}” part)` : ''
  if (!confirm(`Take task #${t.task_id} (${t.label || t.language})${scope} back from ${who}?\n\n`
             + 'Everything already submitted is kept. Any unfinished prompts go back to the '
             + 'pool for the remaining annotators.')) return
  try {
    const body = { team: teamKey.value, task_ids: [t.task_id], return_claimed: true }
    if (a) {
      body.rater_id = a.rater_id
      if (a.category) body.category = a.category
    }
    const r = await api('/pool/admin/tasks/unassign', {
      method: 'POST',
      body: JSON.stringify(body),
    })
    flash(r.message)
    if (!a) taskModal.value = null
    await Promise.all([loadTasks(), load(),
                       a && taskModal.value ? openTask(t.task_id) : Promise.resolve()])
  } catch (e) {
    flash(e.message)
  }
}

// ── submissions ────────────────────────────────────────────────────────────
function subQuery() {
  const qs = new URLSearchParams()
  Object.entries(subFilters).forEach(([k, v]) => { if (v) qs.set(k, v) })
  return qs
}

async function loadSubmissions(p = 1) {
  subLoading.value = true
  try {
    const qs = subQuery()
    qs.set('team', teamKey.value)
    qs.set('page', p)
    qs.set('per_page', 50)
    const d = await api(`/pool/admin/submissions?${qs}`)
    submissions.value = d.items || []
    subPage.value = d.page
    subPages.value = d.pages
    subTotal.value = d.total
  } catch (e) {
    error.value = e.message
  } finally {
    subLoading.value = false
  }
}

async function loadSubMeta() {
  try {
    subMeta.value = await api(`/pool/admin/submissions/filters?team=${teamKey.value}`)
  } catch (e) {
    flash(e.message)
  }
}

function resetSubFilters(reload = true) {
  Object.keys(subFilters).forEach(k => { subFilters[k] = '' })
  subFilters.state = 'submitted'
  if (reload) loadSubmissions(1)
}

function exportSubmissions() {
  const tail = subQuery().toString()
  exportSimple('/pool/admin/export_submissions_csv' + (tail ? `&${tail}` : ''),
               'asr_submissions.csv', 'Submissions')
}

async function openAnnotator(a) {
  annotatorModal.value = { annotator: { name: a.name, email: a.email, id: a.rater_id },
                           totals: {}, by_language: [], recent_items: [],
                           categories: {}, difficulties: {} }
  annotatorLoading.value = true
  try {
    annotatorModal.value = await api(`/pool/admin/annotator/${a.rater_id}?team=${teamKey.value}`)
  } catch (e) {
    flash(e.message)
    annotatorModal.value = null
  } finally {
    annotatorLoading.value = false
  }
}

async function openItem(id) {
  try {
    itemModal.value = (await api(`/pool/admin/item/${id}?team=${teamKey.value}`)).item
  } catch (e) {
    flash(e.message)
  }
}

async function resetItem(id) {
  if (!confirm(`Send prompt #${id} back to the pool? The annotation on this prompt is cleared `
             + 'so someone can redo it. The original text is untouched.')) return
  try {
    flash((await api(`/pool/admin/item/${id}/reset`, { method: 'POST', body: JSON.stringify({ team: teamKey.value }) })).message)
    itemModal.value = null
    await Promise.all([load(), loadSubmissions(subPage.value), loadTasks()])
  } catch (e) {
    flash(e.message)
  }
}

async function reclaim() {
  if (!confirm(`Return every prompt held for more than ${staleHours.value}h to the pool? `
             + 'Finished annotations are not affected.')) return
  reclaiming.value = true
  try {
    flash((await api('/pool/admin/reclaim', { method: 'POST', body: JSON.stringify({ team: teamKey.value }) })).message)
    await load()
  } catch (e) {
    flash(e.message)
  } finally {
    reclaiming.value = false
  }
}

function openEdit(a) {
  memberModal.value = { rater_id: a.rater_id, name: a.name,
                        languages: [...a.allowed_languages], pull_size: a.pull_size }
}
async function saveMember() {
  if (!memberModal.value.rater_id) return
  savingMember.value = true
  try {
    const r = await api('/pool/admin/member', {
      method: 'POST',
      body: JSON.stringify({ team: teamKey.value, rater_id: memberModal.value.rater_id,
                             languages: memberModal.value.languages,
                             pull_size: memberModal.value.pull_size }),
    })
    memberModal.value = null
    flash(r.message)
    await load()
  } catch (e) {
    flash(e.message)
  } finally {
    savingMember.value = false
  }
}
async function removeMember() {
  if (!confirm('Remove this annotator from the ASR team? Their finished work is kept; '
             + 'anything unfinished goes back to the pool.')) return
  try {
    const r = await api('/pool/admin/member', {
      method: 'POST',
      body: JSON.stringify({ team: teamKey.value, rater_id: memberModal.value.rater_id, remove: true }),
    })
    memberModal.value = null
    flash(r.message)
    await load()
  } catch (e) {
    flash(e.message)
  }
}

/** Open the message dialog and pull the whole history with that annotator, the same conversation vi. */
async function openMessage(a) {
  messageError.value = ''
  messageModal.value = { rater: a, body: '' }
  threadItems.value = []
  threadLoading.value = true
  try {
    const d = await api(`/admin/messages?team=${teamKey.value}`)
    threadItems.value = (d.items || [])
      .filter(it => it.kind === 'broadcast' || it.rater_id === a.rater_id)
      .reverse()
    await nextTick()
    if (threadBox.value) threadBox.value.scrollTop = threadBox.value.scrollHeight
  } catch (e) {
    threadItems.value = []
  } finally {
    threadLoading.value = false
  }
}

function startEditThread(item) {
  messageModal.value.body = item.body
  messageModal.value.editing = item.id
}

async function sendMessage() {
  sending.value = true
  messageError.value = ''
  try {
    const editing = messageModal.value.editing
    if (editing) {
      await api(`/admin/message/${editing}`, {
        method: 'PUT', body: JSON.stringify({ body: messageModal.value.body }),
      })
      flash('Message updated.')
    } else {
      await api(`/admin/rater/${messageModal.value.rater.rater_id}/message`, {
        method: 'POST', body: JSON.stringify({ body: messageModal.value.body }),
      })
      flash(`Message sent to ${messageModal.value.rater.name}.`)
    }
    messageModal.value = null
  } catch (e) {
    messageError.value = e.message
  } finally {
    sending.value = false
  }
}

async function sendBroadcast() {
  sending.value = true
  messageError.value = ''
  try {
    const r = await api(`/admin/message/broadcast?team=${teamKey.value}`, {
      method: 'POST', body: JSON.stringify({ body: broadcastModal.value.body }),
    })
    flash(r.message)
    broadcastModal.value = null
  } catch (e) {
    messageError.value = e.message
  } finally {
    sending.value = false
  }
}

async function loadPin() {
  try {
    signupPin.value = (await api('/admin/signup-key')).pin
  } catch (e) {
    flash(e.message)
  }
}
function copyPin() {
  navigator.clipboard?.writeText(signupPin.value)
  pinCopied.value = true
  setTimeout(() => (pinCopied.value = false), 1800)
}

/** Small reports come back in one response -- show a lightweight overlay. */
async function exportSimple(path, filename, label) {
  simpleExport.value = { state: 'busy', label }
  try {
    // paths may carry extra params as "&k=v"; team= always comes first
    const endpoint = path.includes('&') ? `${API_BASE_URL}${path.replace('&', `?team=${teamKey.value}&`)}`
                                        : `${API_BASE_URL}${path}?team=${teamKey.value}`
    const res = await fetch(endpoint,
                            { headers: { Authorization: `Bearer ${authToken()}` } })
    if (!res.ok) throw new Error('The server refused the export.')
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
    simpleExport.value = { state: 'done', label: `${label} downloaded` }
    setTimeout(() => (simpleExport.value = null), 1200)
  } catch (e) {
    simpleExport.value = { state: 'error', label: e.message }
    setTimeout(() => (simpleExport.value = null), 2600)
  }
}

async function startExport() {
  const body = { team: teamKey.value, format: exportFormat.value }
  if (exportScope.value === 'done') body.only_done = true
  if (exportLanguage.value) body.language = exportLanguage.value
  if (exportTaskId.value) body.task_id = Number(exportTaskId.value)
  if (exportCategory.value) body.category = exportCategory.value
  try {
    const res = await api('/pool/admin/export/start', { method: 'POST', body: JSON.stringify(body) })
    exportJob.value = { id: res.job_id, status: 'queued', done: 0, total: 0, percent: 0 }
    pollExport()
  } catch (e) {
    flash(e.message)
  }
}
function pollExport() {
  clearTimeout(pollTimer)
  pollTimer = setTimeout(async () => {
    if (!exportJob.value) return
    try {
      const s = await api(`/pool/admin/export/status/${exportJob.value.id}`)
      exportJob.value = { ...exportJob.value, ...s }
      if (s.status !== 'done' && s.status !== 'error') pollExport()
    } catch {
      pollExport()   // a transient blip must not strand the dialog
    }
  }, 700)
}
function closeExport() {
  clearTimeout(pollTimer)
  exportOpen.value = false
  exportJob.value = null
}

/** The download needs the bearer header, so fetch it as a blob rather than pointing an <a href> at. */
async function downloadExport() {
  downloading.value = true
  try {
    const res = await fetch(`${API_BASE_URL}/pool/admin/export/download/${exportJob.value.id}`,
                            { headers: { Authorization: `Bearer ${authToken()}` } })
    if (!res.ok) throw new Error('The file could not be downloaded.')
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = exportJob.value.filename || `asr_pool_export.${exportJob.value.format || 'csv'}`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
    setTimeout(closeExport, 600)
  } catch (e) {
    flash(e.message)
  } finally {
    downloading.value = false
  }
}

function startTimers() {
  clearInterval(countdownTimer)
  countdown.value = refreshInterval
  countdownTimer = setInterval(() => {
    countdown.value -= 1
    if (countdown.value <= 0) {
      countdown.value = refreshInterval
      // never fight the user: skip the tick while a dialog is open
      if (!memberModal.value && !itemModal.value && !annotatorModal.value
          && !exportOpen.value && !messageModal.value && !broadcastModal.value
          && !taskModal.value && !assignModal.value) {
        load()
        if (tab.value === 'tasks') loadTasks()
      }
    }
  }, 1000)
}

function toggleAutoRefresh() {
  isAutoRefreshActive.value = !isAutoRefreshActive.value
  if (isAutoRefreshActive.value) startTimers()
  else clearInterval(countdownTimer)
}

onMounted(() => {
  // Load-as-you-go: the overview and the task list arrive independently, and each section paints as soon as its own data is in.
  load()
  loadTasks()
  loadPending()   // primes the "Pending approval" badge
  if (isAutoRefreshActive.value) startTimers()
})
onBeforeUnmount(() => {
  clearTimeout(pollTimer)
  clearInterval(countdownTimer)
})
</script>

<style scoped>
/** Same visual language as the TTS admin dashboard. */
.dashboard-container { max-width: 1400px; margin: 0 auto; padding: 0 20px; }
.text-xs { font-size: 0.75rem; }
.cursor-pointer { cursor: pointer; }

.tabs-nav { position: sticky; top: 0; z-index: 5; }
.tab-btn { border: none; transition: all .15s ease; min-width: 130px; }
.tab-btn:hover { transform: translateY(-1px); }

.kpi-card { transition: transform .15s ease, box-shadow .15s ease; }
.kpi-card:hover { transform: translateY(-2px); box-shadow: 0 .5rem 1rem rgba(0,0,0,.1) !important; }
.kpi-icon-wrapper { width: 38px; height: 38px; border-radius: 10px; display: grid; place-items: center; }

.status-dot { width: 8px; height: 8px; border-radius: 50%; background: #cbd5e1; }
.status-dot.active { background: #22c55e; }
.animate-spin { animation: spin 1s linear infinite; }
.animate-pulse { animation: pulse 2s cubic-bezier(.4,0,.6,1) infinite; }
@keyframes pulse { 50% { opacity: .45; } }
@keyframes spin { to { transform: rotate(360deg); } }

/** Pop-menus. Teleported to <body>, which still carries this component's scope attribute, so scoped. */
.menu-backdrop { position: fixed; inset: 0; z-index: 1080; }
.pop-menu { position: fixed; z-index: 1081; background: #fff; border: 1px solid #e2e8f0;
            border-radius: .6rem; box-shadow: 0 12px 28px rgba(15,23,42,.16); padding: .3rem; overflow: hidden; }
.pop-menu-head { font-size: .62rem; text-transform: uppercase; letter-spacing: .04em;
                 color: #94a3b8; font-weight: 700; padding: .4rem .6rem .3rem; }
.pop-item { display: flex; align-items: flex-start; gap: .6rem; width: 100%; border: 0;
            background: none; text-align: left; padding: .45rem .6rem; border-radius: .4rem; color: #0f172a; }
.pop-item:hover { background: #f1f5f9; }
.pop-item i { font-size: .9rem; line-height: 1.25; }
.pop-item span { display: flex; flex-direction: column; min-width: 0; }
.pop-item b { font-size: .78rem; font-weight: 600; }
.pop-item small { font-size: .66rem; color: #94a3b8; }
.pop-item.is-danger { color: #b91c1c; }
.pop-sep { height: 1px; background: #e9ecef; margin: .25rem .3rem; }

/** Annotators tab: the same toolbar, pills, drill-down and pop-menus as TTS. */
.stale-alert { background: #fff8e6; border: 1px solid #ffe08a; color: #7a5b00; border-radius: .5rem; }
.search-wrap { min-width: 230px; }
.search-icon { position: absolute; left: .75rem; top: 50%; transform: translateY(-50%); color: #adb5bd; font-size: .85rem; }
.search-clear { position: absolute; right: .25rem; top: 50%; transform: translateY(-50%); color: #adb5bd; border: none; }
.rater-table thead th { font-size: .7rem; text-transform: uppercase; letter-spacing: .04em;
                        color: #6c757d; font-weight: 700; background: #f8f9fa; }
.sortable-th { cursor: pointer; user-select: none; }
.sortable-th:hover { color: #212529; }
.stale-row { background: #fffdf5; }
.row-open { background: #f8f9ff; }
.avatar-off { background: #e9ecef !important; color: #adb5bd !important; }
.assigned-chip-wrap { max-width: 220px; }
.status-pill { display: inline-flex; align-items: center; gap: .3rem; border-radius: 2rem;
               padding: .1rem .6rem; font-size: .72rem; font-weight: 700; }
.status-pill.is-working { background: #fff4e0; color: #b45309; }
.status-pill.is-active { background: #e6f7ee; color: #0f7b45; }
.status-pill.is-idle { background: #fdecec; color: #b42318; }
.status-pill.is-new { background: #f1f3f5; color: #6c757d; }
.status-pill.is-off { background: #f1f3f5; color: #adb5bd; }
.tasks-num { font-size: 1.05rem; font-weight: 700; color: #212529; }
.stat-pill { border-radius: 2rem; padding: .05rem .5rem; font-size: .68rem; font-weight: 700; }
.stat-pill.warn { background: #fff4e0; color: #b45309; }
.stat-pill.info { background: #e7f1ff; color: #0d6efd; }
.type-chip { display: inline-flex; align-items: center; gap: .35rem; background: #f1f3f5; color: #495057;
             border-radius: 2rem; padding: .1rem .6rem; font-size: .72rem; font-weight: 600; }
.type-chip b { color: #212529; }
.annot-cap { width: 56px; text-align: center; }
.act-chip { display: inline-flex; align-items: center; gap: .4rem; background: #fff; color: #495057;
            border: 1px solid #dee2e6; border-radius: 2rem; padding: .25rem .75rem;
            font-size: .78rem; font-weight: 600; transition: all .15s ease; }
.act-chip:hover { border-color: #adb5bd; background: #f8f9fa; }
.act-chip.active { border-color: #212529; background: #212529; color: #fff; }
.act-chip.active b { color: #fff; }
.act-chip b { color: #212529; }

/* Grouped activity feed */
.act-day { margin-bottom: 1rem; }
.act-day-head { display: flex; align-items: center; gap: .5rem; padding: .45rem .75rem;
                background: #f8f9fa; border: 1px solid #e9ecef; border-radius: 8px 8px 0 0;
                font-size: .85rem; color: #343a40; position: sticky; top: 0; z-index: 2; }
.act-day-body { border: 1px solid #e9ecef; border-top: 0; border-radius: 0 0 8px 8px; overflow: hidden; }
.act-group-row { display: flex; align-items: center; gap: .55rem; width: 100%; text-align: left;
                 background: #fff; border: 0; border-bottom: 1px solid #f1f3f5;
                 padding: .5rem .75rem; font-size: .85rem; }
.act-group-row:hover { background: #f8f9fa; }
.act-count { color: #212529; font-size: .82rem; }
.act-group-items { background: #fbfcfe; border-bottom: 1px solid #f1f3f5; padding: .25rem .75rem .25rem 2.2rem; }
.act-single { display: flex; align-items: center; gap: .55rem; padding: .5rem .75rem .5rem 2.05rem;
              border-bottom: 1px solid #f1f3f5; font-size: .85rem; background: #fff; }
.act-single:hover { background: #f8f9fa; }
.act-time { min-width: 38px; }
.act-day-body > :last-child, .act-day-body .act-group:last-child .act-group-row { border-bottom: 0; }
.drill-btn { border: none; background: transparent; color: #0d6efd; font-size: .72rem; font-weight: 600; padding: 0; }
.drill-btn:hover { text-decoration: underline; }
.drill-row > td { background: #f8f9ff; }
.drill-panel { padding: .85rem 1rem; }
.drill-table thead th { font-size: .66rem; text-transform: uppercase; letter-spacing: .04em;
                        color: #adb5bd; font-weight: 700; }
.rater-action-btn { width: 32px; height: 32px; padding: 0; display: inline-grid; place-items: center; }
.rater-action-btn.is-open { background: #212529; color: #fff; border-color: #212529; }

/** Task screens: the same segmented sub-nav, tiles and id badge the TTS dashboard uses, so the two. */
.preview-modal { max-width: 1100px; width: 96vw; }

.project-head-btn {
  display: flex; flex-direction: column; align-items: center; gap: 2px;
  min-width: 220px; padding: .65rem 1.25rem; border-radius: .9rem;
  border: 2px solid #dee2e6; background: #fff; color: #495057;
  transition: all .15s ease;
}
.project-head-btn:hover { border-color: #adb5bd; transform: translateY(-1px); }
.project-head-btn.active { border-color: #212529; background: #212529; color: #fff; box-shadow: 0 .4rem .9rem rgba(0,0,0,.18); }
.project-head-btn i { font-size: 1.15rem; }
.ph-label { font-weight: 700; font-size: .92rem; }
.ph-count { font-size: .72rem; opacity: .75; }

.tasks-subnav { background: #fff; border: 1px solid #dee2e6; border-radius: 2rem; padding: .25rem; gap: .25rem; }
.subnav-btn { border: none; background: transparent; color: #6c757d; font-weight: 600; font-size: .86rem;
              border-radius: 2rem; padding: .45rem 1.15rem; display: inline-flex; align-items: center;
              gap: .45rem; transition: all .15s ease; }
.subnav-btn:hover { color: #212529; background: #f1f3f5; }
.subnav-btn.active { background: #212529; color: #fff; }
.subnav-badge { background: rgba(255,255,255,.2); border-radius: 1rem; padding: 0 .45rem; font-size: .72rem; }
.subnav-btn:not(.active) .subnav-badge { background: #e9ecef; color: #6c757d; }

.ov-tile { background: #fff; border: 1px solid #dee2e6; border-radius: .6rem; padding: .7rem .9rem;
           min-width: 190px; flex: 1 1 190px; }
.ov-tile .lbl { display: block; font-size: .66rem; font-weight: 700; letter-spacing: .05em;
                text-transform: uppercase; color: #6c757d; }
.ov-tile .val { display: block; font-size: 1.3rem; font-weight: 700; color: #212529; line-height: 1.3; }
.ov-tile .sub { display: block; font-size: .7rem; color: #adb5bd; }

.task-id-badge { display: inline-block; background: #eef2ff; color: #4338ca; border: 1px solid #c7d2fe;
                 border-radius: .4rem; padding: .05rem .4rem; font-size: .75rem; font-weight: 700; }

/** Dialogs. Same shell, spacing, chips and transition as the TTS dashboard, so assigning work or me. */
.assign-modal-backdrop { position: fixed; inset: 0; background: rgba(15,23,42,.55);
                         backdrop-filter: blur(3px); display: flex; align-items: center;
                         justify-content: center; z-index: 1070; padding: 1rem; }
.assign-modal-card { background: #fff; width: 100%; max-width: 620px; max-height: 90vh;
                     border-radius: 18px; display: flex; flex-direction: column; overflow: hidden; }
.assign-modal-header { padding: 1.1rem 1.5rem; border-bottom: 1px solid #eef2f7; flex-shrink: 0; }
.assign-modal-body { padding: 1.25rem 1.5rem; overflow-y: auto; }
.assign-modal-footer { padding: 1rem 1.5rem; border-top: 1px solid #eef2f7; background: #f8fafc; flex-shrink: 0; }
.avatar-circle-lg { width: 46px; height: 46px; border-radius: 50%;
                    background: linear-gradient(135deg, #d8661b, #f4a93c); color: #fff;
                    display: flex; align-items: center; justify-content: center;
                    font-weight: 700; font-size: 1.2rem; flex-shrink: 0; }
.avatar-stack { display: flex; flex-shrink: 0; }
.avatar-stack .stacked { width: 40px; height: 40px; font-size: 1rem; border: 2px solid #fff; }
.avatar-stack .stacked + .stacked { margin-left: -12px; }
.avatar-stack .stacked.more { background: #f1f5f9; color: #64748b; font-size: .8rem; }

/* One annotator holding (part of) a task — the same chip everywhere a holder is shown. */
.holder-chip { display: inline-flex; align-items: center; gap: .3rem; background: #fceee3;
               color: #7c3f10; border: 1px solid #f3cdaa; font-weight: 600; font-size: .72rem;
               padding: .1rem .5rem .1rem .15rem; border-radius: 999px; white-space: nowrap; }
.holder-chip em { font-style: normal; color: #b4530f; background: #fff;
                  border: 1px solid #f3cdaa; border-radius: 999px;
                  padding: 0 .35rem; font-size: .64rem; }
.holder-initial { width: 18px; height: 18px; border-radius: 50%; flex-shrink: 0;
                  background: linear-gradient(135deg, #d8661b, #f4a93c); color: #fff;
                  display: inline-flex; align-items: center; justify-content: center;
                  font-size: .6rem; font-weight: 700; }
.holder-initial.lg { width: 26px; height: 26px; font-size: .72rem; }

/* The richer card used in the task-detail modal, with a per-annotator remove control. */
.holder-pill { display: inline-flex; align-items: center; gap: .55rem; background: #fff;
               border: 1px solid #f3cdaa; border-radius: .65rem; padding: .35rem .6rem; }
.holder-pill .holder-avatar { width: 30px; height: 30px; border-radius: 50%; flex-shrink: 0;
                              background: linear-gradient(135deg, #d8661b, #f4a93c); color: #fff;
                              display: inline-flex; align-items: center; justify-content: center;
                              font-size: .8rem; font-weight: 700; }
.holder-pill .holder-remove { color: #adb5bd; font-size: .9rem; transition: color .15s ease; }
.holder-pill .holder-remove:hover { color: #dc3545; }

/* Share vs replace choice in the assign dialog. */
.mode-card { display: flex; align-items: flex-start; gap: .55rem; border: 1px solid #dee2e6;
             border-radius: .6rem; padding: .55rem .75rem; cursor: pointer; margin: 0;
             transition: border-color .15s ease, background .15s ease; }
.mode-card:hover { border-color: #f3cdaa; }
.mode-card.active { border-color: #d8661b; background: #fceee3; }
.selected-chips { display: flex; flex-wrap: wrap; gap: .35rem; }
.selected-chips .chip { display: inline-flex; align-items: center; gap: .35rem; background: #fceee3;
                        color: #b4530f; border: 1px solid #f3cdaa; font-weight: 600;
                        font-size: .8rem; padding: .25rem .65rem; border-radius: 999px; }
.selected-chips .chip i { cursor: pointer; font-size: .65rem; opacity: .7; transition: opacity .15s ease; }
.selected-chips .chip i:hover { opacity: 1; }
.batch-picker { max-height: 300px; overflow-y: auto; }
.batch-row { cursor: pointer; border-bottom: 1px solid #f1f5f9; margin: 0; transition: background .12s ease; }
.batch-row:last-child { border-bottom: none; }
.batch-row:hover { background-color: #fff7ee !important; box-shadow: inset 3px 0 0 #d8661b; }
.batch-row.selected { background: #fceee3; }
.msg-thread { max-height: 300px; overflow-y: auto; display: flex; flex-direction: column;
              gap: 8px; padding-right: 4px; }
.msg-bubble { background: #f8fafc; border: 1px solid #eef2f7; border-radius: 10px; padding: 10px 12px; }
.msg-bubble.broadcast { background: #fffaf3; border-color: #fbe3c4; }
.lang-check { display: flex; align-items: center; gap: .35rem; border: 1px solid #dee2e6;
              border-radius: 2rem; padding: .2rem .7rem; font-size: .8rem; cursor: pointer; }
.fs-9 { font-size: .7rem; }
.modal-fade-enter-from, .modal-fade-leave-to { opacity: 0; }
.modal-fade-enter-active, .modal-fade-leave-active { transition: opacity .18s ease; }
.modal-fade-enter-active .assign-modal-card,
.modal-fade-leave-active .assign-modal-card { transition: transform .22s cubic-bezier(.34,1.56,.64,1); }
.modal-fade-enter-from .assign-modal-card,
.modal-fade-leave-to .assign-modal-card { transform: translateY(18px) scale(.97); }

.lang-line { cursor: pointer; }
.lang-line:hover { opacity: .85; }
.lang-row { background: #fff; border: none; }
.lang-row:hover { background: #f8f9fa; }

.mini-stat { background: #fff; border: 1px solid #dee2e6; border-radius: .5rem; padding: .5rem .7rem; height: 100%; }
.mini-stat span { display: block; font-size: .68rem; color: #6c757d; text-transform: uppercase; letter-spacing: .04em; font-weight: 700; }
.mini-stat strong { font-size: 1.05rem; color: #212529; }

.avatar-circle { width: 32px; height: 32px; border-radius: 50%; background: #e7f1ff; color: #0d6efd;
                 display: grid; place-items: center; font-weight: 700; font-size: .75rem; }
.cell-text { max-width: 420px; }
.text-muted-2 { color: #adb5bd; }
.filter-bar { background: #f8f9fa; margin: 0 -1.5rem 1rem; padding-left: 1.5rem; padding-right: 1.5rem; }
.date-input { width: 145px; }
.stat-strip { gap: 1.25rem; }
.stat { text-align: center; }
.stat-val { font-weight: 700; font-size: 1.05rem; color: #212529; line-height: 1.1; }
.stat-lbl { font-size: .64rem; text-transform: uppercase; letter-spacing: .05em; color: #adb5bd; font-weight: 700; }
.pin-box { font-size: 1.35rem; letter-spacing: .18em; font-weight: 700; color: #0d6efd;
           background: #e7f1ff; border-radius: .5rem; padding: .35rem .8rem; }
.lang-check { display: flex; align-items: center; gap: .35rem; border: 1px solid #dee2e6;
              border-radius: .5rem; padding: .3rem .6rem; font-size: .85rem; cursor: pointer; }

.spark { display: flex; align-items: flex-end; gap: 2px; height: 80px; }
.spark-bar { flex: 1; background: #0d6efd; border-radius: 2px 2px 0 0; min-height: 3px; opacity: .85; }

.text-block { background: #f8f9fa; border: 1px solid #dee2e6; border-radius: .5rem;
              padding: .8rem 1rem; font-size: 1.05rem; line-height: 1.8; white-space: pre-wrap; }
.edited-block { background: #fff9e6; border-color: #ffe08a; }

.asr-modal-backdrop { position: fixed; inset: 0; background: rgba(33,37,41,.5); display: grid;
                      place-items: center; z-index: 1080; padding: 1rem; }
.asr-modal { background: #fff; border-radius: .75rem; width: 100%; max-width: 560px;
             box-shadow: 0 1.5rem 3rem rgba(0,0,0,.25); display: flex; flex-direction: column; max-height: 90vh; }
.asr-modal.wide { max-width: 960px; }
.asr-modal-head { display: flex; justify-content: space-between; align-items: flex-start;
                  padding: 1rem 1.25rem; border-bottom: 1px solid #dee2e6; flex-shrink: 0; }
.asr-modal-body { padding: 1.25rem; overflow-y: auto; }
.asr-modal-foot { display: flex; gap: .5rem; justify-content: flex-end; padding: 1rem 1.25rem;
                  border-top: 1px solid #dee2e6; flex-shrink: 0; }

.asr-toast { position: fixed; bottom: 1.5rem; left: 50%; transform: translateX(-50%);
             background: #212529; color: #fff; padding: .6rem 1.1rem; border-radius: 2rem;
             font-size: .86rem; z-index: 1100; box-shadow: 0 .5rem 1.5rem rgba(0,0,0,.25); }

/* Small screens: the whole dashboard stays usable on a phone — tabs scroll sideways instead of stacking, dialogs use the full width, and fixed min-widths relax. Desktop is untouched. */
@media (max-width: 767.98px) {
  .dashboard-container { padding: 0 10px; }
  .tabs-nav { flex-wrap: nowrap !important; overflow-x: auto; -webkit-overflow-scrolling: touch;
              scrollbar-width: none; }
  .tabs-nav::-webkit-scrollbar { display: none; }
  .tab-btn { min-width: auto; flex: 1 0 auto; white-space: nowrap;
             padding-left: .8rem; padding-right: .8rem; }
  .asr-modal-backdrop, .assign-modal-backdrop { padding: .5rem; }
  .asr-modal-body, .assign-modal-body { padding: .9rem; }
  .asr-modal-head, .assign-modal-header { padding: .75rem .9rem; }
  .asr-modal-foot, .assign-modal-footer { padding: .75rem .9rem; flex-wrap: wrap; }
  .asr-modal-foot .me-auto { margin-right: 0 !important; }
  .lang-row { flex-wrap: wrap; row-gap: .35rem; }
  .lang-row .progress { flex-basis: 100%; order: 10; }
  .cell-text { max-width: 240px; }
  .ov-tile { min-width: 140px; flex: 1 1 45%; }
  .filter-bar { margin: 0 -0.9rem 1rem; padding-left: .9rem; padding-right: .9rem; }
  .avatar-stack .stacked + .stacked { margin-left: -16px; }
}
</style>
