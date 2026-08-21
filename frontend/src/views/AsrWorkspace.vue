<template>
  <div class="page-container py-5">
    <div class="container">

      <!-- Greeting Banner -->
      <div class="welcome-banner p-4 p-md-5 rounded-4 shadow-lg mb-5 text-white position-relative overflow-hidden">
        <div class="banner-gradient"></div>
        <div class="row align-items-center position-relative z-index-1">
          <div class="col-md-8">
            <h1 class="display-5 fw-bold mb-2">Welcome back, {{ displayUsername }}!</h1>
            <p class="lead opacity-85 mb-0">
              Here are the tasks assigned to you. Take prompts from a task, fix the text where
              it is wrong, and mark how hard it is to read aloud.
            </p>
          </div>
          <div class="col-md-4 text-md-end mt-4 mt-md-0">
            <div class="banner-badge px-4 py-2 rounded-pill d-inline-block">
              <i class="bi bi-person-badge me-2"></i>
              <span class="fw-semibold text-uppercase tracking-wider small">{{ teamName }}</span>
            </div>
          </div>
        </div>

        <!-- Quick actions: overall progress + resume -->
        <div v-if="tasks.length" class="banner-progress mt-4 pt-4 position-relative z-index-1">
          <div class="d-flex flex-column flex-md-row align-items-md-center gap-3">
            <router-link v-if="stats.outstanding" :to="taskPath"
                         class="btn btn-continue fw-semibold px-4 py-2 rounded-pill shadow-sm d-inline-flex align-items-center gap-2 flex-shrink-0">
              <i class="bi bi-play-circle-fill"></i>
              Resume — {{ stats.outstanding }} prompt(s) in your queue
            </router-link>
            <span v-else-if="!overallTotal || overallDone >= overallTotal"
                  class="all-done-pill fw-semibold px-4 py-2 rounded-pill d-inline-flex align-items-center gap-2 flex-shrink-0">
              <i class="bi bi-check2-circle"></i> All assigned work completed
            </span>
            <button v-else class="btn btn-continue fw-semibold px-4 py-2 rounded-pill shadow-sm d-inline-flex align-items-center gap-2 flex-shrink-0"
                    @click="scrollToPull">
              <i class="bi bi-download"></i> Take prompts to start
            </button>

            <div class="flex-grow-1 w-100">
              <div class="d-flex justify-content-between small fw-semibold mb-1">
                <span><i class="bi bi-graph-up-arrow me-1"></i>Overall progress</span>
                <span>{{ overallDone.toLocaleString() }} / {{ overallTotal.toLocaleString() }} prompts · {{ overallProgress }}%</span>
              </div>
              <div class="progress banner-progress-bar rounded-pill" style="height: 9px;">
                <div class="progress-bar bg-white rounded-pill" role="progressbar"
                     :style="{ width: overallProgress + '%' }"></div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Annotator inbox: messages from the admin -->
      <div v-if="messages.length" class="card border-0 shadow-sm rounded-4 mb-5 overflow-hidden inbox-card">
        <div class="card-header bg-white py-3 border-0 d-flex align-items-center justify-content-between">
          <h5 class="mb-0 d-flex align-items-center gap-2 text-dark">
            <i class="bi bi-inbox-fill text-primary"></i>
            <span>Messages from admin</span>
            <span class="badge rounded-pill bg-light text-secondary border">{{ messages.length }}</span>
            <span v-if="unreadCount" class="badge rounded-pill bg-danger">{{ unreadCount }} new</span>
          </h5>
          <button v-if="unreadCount" class="btn btn-sm btn-outline-secondary" @click="markAllRead" :disabled="isMarkingRead">
            <span v-if="isMarkingRead" class="spinner-border spinner-border-sm me-1"></span>
            <i v-else class="bi bi-check2-all me-1"></i> Mark all read
          </button>
        </div>
        <div class="card-body pt-0">
          <ul class="list-unstyled mb-0 inbox-list">
            <li v-for="m in messages" :key="m.id"
                class="inbox-item p-3 rounded-3 mb-2 d-flex gap-3 align-items-start"
                :class="[notifKind(m.category), { unread: !m.is_read }]">
              <span class="inbox-avatar flex-shrink-0" :class="notifKind(m.category)">
                <i class="bi" :class="notifIcon(m.category)"></i>
              </span>
              <div class="flex-grow-1 min-w-0">
                <div class="d-flex justify-content-between align-items-center gap-2 mb-1">
                  <span class="inbox-chip" :class="notifKind(m.category)">
                    {{ notifLabel(m.category) }}
                    <span v-if="!m.is_read" class="inbox-new-dot"></span>
                  </span>
                  <small class="text-muted flex-shrink-0">{{ formatMsgDate(m.created_at) }}</small>
                </div>
                <p class="mb-0 text-dark-emphasis inbox-body">{{ m.body }}</p>
              </div>
            </li>
          </ul>
        </div>
      </div>

      <!-- Stats Summary Grid -->
      <div class="row g-4 mb-5">
        <div class="col-6 col-md-3" v-for="stat in statsCards" :key="stat.title">
          <div class="stat-card p-4 rounded-4 shadow-sm bg-white border border-light-subtle hover-lift">
            <div class="d-flex justify-content-between align-items-center mb-2">
              <span class="text-muted fw-medium small text-uppercase">{{ stat.title }}</span>
              <div :class="['stat-icon px-2 py-1 rounded-3', stat.bgClass, stat.textClass]">
                <i :class="stat.icon"></i>
              </div>
            </div>
            <h3 class="fw-bold mb-0 text-dark">{{ stat.value }}</h3>
            <small class="text-muted">{{ stat.sub }}</small>
          </div>
        </div>
      </div>

      <!-- My work by type of task — the same numbers the admin sees for payment -->
      <div v-if="workByType.length" class="card border-0 shadow-sm rounded-4 mb-5 overflow-hidden">
        <div class="card-header bg-white py-3 border-0 d-flex align-items-center justify-content-between">
          <h5 class="mb-0 d-flex align-items-center gap-2 text-dark">
            <i class="bi bi-cash-stack text-success"></i>
            <span>My work by type of task</span>
          </h5>
          <span class="badge rounded-pill bg-light text-secondary border">counts &amp; time your payment is based on</span>
        </div>
        <div class="card-body pt-0">
          <div class="table-responsive">
            <table class="table table-sm align-middle mb-0">
              <thead class="table-light"><tr>
                <th>Type of work</th>
                <th class="text-end">Submitted</th>
                <th class="text-end">Completed</th>
                <th class="text-end">Flagged</th>
                <th class="text-end">Text edited</th>
                <th class="text-end">Time spent (h)</th>
              </tr></thead>
              <tbody>
                <tr v-for="tt in workByType" :key="tt.task_type">
                  <td class="fw-semibold text-dark">{{ tt.task_type_label }}</td>
                  <td class="text-end fw-semibold">{{ tt.submitted.toLocaleString() }}</td>
                  <td class="text-end text-success">{{ tt.completed.toLocaleString() }}</td>
                  <td class="text-end text-warning">{{ tt.flagged }}</td>
                  <td class="text-end">{{ tt.edited }}</td>
                  <td class="text-end">{{ tt.hours }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div v-if="isLoading" class="text-center py-5">
        <div class="spinner-border text-primary" role="status" style="width: 3rem; height: 3rem;">
          <span class="visually-hidden">Loading...</span>
        </div>
        <p class="text-muted mt-3 fw-medium">Loading your assigned tasks, please wait...</p>
      </div>

      <div v-else-if="error" class="alert alert-danger p-4 rounded-4 shadow-sm border-0 d-flex align-items-start gap-3" role="alert">
        <i class="bi bi-exclamation-triangle-fill fs-3 text-danger"></i>
        <div class="flex-grow-1">
          <h5 class="fw-bold mb-1">Failed to load your tasks</h5>
          <p class="mb-0 text-secondary">{{ error }}</p>
          <button @click="refresh" class="btn btn-outline-danger btn-sm mt-3 px-4 rounded-pill">Try Again</button>
        </div>
      </div>

      <template v-else>
        <!-- ══ Take prompts — the ASR step on top of the TTS workspace ══ -->
        <div v-if="tasks.length" ref="pullPanel" class="card border-0 shadow-sm rounded-4 mb-5 overflow-hidden pull-card">
          <div class="card-header bg-white border-0 pt-4 px-4 pb-0">
            <div class="d-flex flex-wrap align-items-center justify-content-between gap-2">
              <div>
                <h5 class="mb-1 d-flex align-items-center gap-2 fw-bold text-dark">
                  <span class="pull-icon"><i class="bi bi-download"></i></span>
                  <span>Take prompts from a task</span>
                </h5>
                <p class="text-muted small mb-0">
                  Choose how much of a task you want now. What you take is locked to you —
                  nobody else can be given the same prompts.
                </p>
              </div>
              <span class="badge rounded-pill px-3 py-2"
                    :class="matching ? 'bg-success-subtle text-success' : 'bg-danger-subtle text-danger'">
                <i class="bi bi-collection me-1"></i>{{ matching.toLocaleString() }} match
              </span>
            </div>
          </div>
          <div class="card-body p-4">
            <div class="row g-3 align-items-end">
              <div class="col-12 col-lg-5">
                <label class="form-label small fw-semibold text-uppercase text-secondary">Task</label>
                <select v-model.number="pick.task_id" class="form-select" @change="onTaskChange">
                  <optgroup v-for="g in pullTaskGroups" :key="g.key" :label="g.label">
                    <option v-for="t in g.tasks" :key="t.task_id" :value="t.task_id">
                      #{{ t.task_id }} — {{ t.label || `${t.language} · Class ${t.class}` }}
                      ({{ t.available_total.toLocaleString() }} free)
                    </option>
                  </optgroup>
                </select>
              </div>
              <div class="col-6 col-lg-3">
                <label class="form-label small fw-semibold text-uppercase text-secondary">Type of prompt</label>
                <select v-model="pick.category" class="form-select" @change="fitCount()">
                  <option value="">Any type</option>
                  <option v-for="c in (currentTask?.available_by_category || [])" :key="c.category" :value="c.category">
                    {{ c.category }} ({{ c.available.toLocaleString() }})
                  </option>
                </select>
              </div>
              <div class="col-6 col-lg-2">
                <label class="form-label small fw-semibold text-uppercase text-secondary">How many</label>
                <select v-model.number="pick.count" class="form-select">
                  <option v-for="n in countOptions" :key="n" :value="n">{{ n }}</option>
                </select>
              </div>
              <div class="col-6 col-lg-2 d-grid">
                <button class="btn btn-success rounded-pill py-2 d-flex align-items-center justify-content-center gap-2"
                        :disabled="pulling || !matching || atCap" @click="pullWork">
                  <span v-if="pulling" class="spinner-border spinner-border-sm"></span>
                  <i v-else class="bi bi-download"></i>
                  {{ pulling ? 'Getting…' : 'Get prompts' }}
                </button>
              </div>
            </div>
            <p class="text-muted small mb-0 mt-3">
              <span v-if="atCap" class="text-danger">
                You are holding {{ heldNow }} unfinished prompt(s) — the limit is
                {{ openCap }} at a time. Submit those first, then you can pull more.
              </span>
              <span v-else-if="!matching">Nothing left for that combination — try another type of prompt.</span>
              <span v-else>Prompts come in batches of {{ countOptions.join(', ') }}. Take a batch,
                annotate it, then take the next.
                <template v-if="openCap"> You can hold at most {{ openCap }} unfinished
                  prompt(s) at a time<template v-if="allowance < pick.count"> — right now
                  you can take {{ allowance }} more</template>.</template>
              </span>
            </p>

            <!-- What you are working on -->
            <div v-if="pulls.length" class="mt-4 pt-4 border-top">
              <h6 class="fw-bold text-dark mb-3 fs-7">
                <i class="bi bi-hourglass-split me-1 text-warning"></i>What you are working on
              </h6>
              <div class="table-responsive">
                <table class="table table-sm align-middle mb-0 pull-table">
                  <thead>
                    <tr>
                      <th>Task</th><th>Slice</th><th>Taken (IST)</th>
                      <th class="text-end">Prompts</th><th class="text-end">Done</th>
                      <th style="width:150px">Progress</th><th class="text-end">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="p in pulls" :key="p.pull_id">
                      <td>
                        <span class="task-id-badge">#{{ p.task_id }}</span>
                        <span class="ms-2 fw-semibold text-dark">{{ p.task_label }}</span>
                      </td>
                      <td class="text-muted fs-8">
                        {{ p.category || 'whole task' }}<span v-if="p.source_difficulty"> · {{ p.source_difficulty }}</span>
                      </td>
                      <td class="text-muted fs-8 text-nowrap">{{ p.created_at_ist }}</td>
                      <td class="text-end">{{ p.item_count }}</td>
                      <td class="text-end text-success fw-semibold">{{ p.done }}</td>
                      <td>
                        <div class="progress" style="height:6px">
                          <div class="progress-bar bg-success" :style="{ width: p.progress + '%' }"></div>
                        </div>
                        <small class="text-muted fs-9">{{ p.claimed }} left</small>
                      </td>
                      <td class="text-end text-nowrap">
                        <router-link v-if="p.claimed" :to="`${taskPath}?pull=${p.pull_id}`"
                                     class="btn btn-sm btn-outline-primary rounded-pill">
                          Annotate <i class="bi bi-arrow-right"></i>
                        </router-link>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <p class="text-muted fs-9 mt-2 mb-0">
                <i class="bi bi-clock-history me-1"></i>Anything you do not finish goes back to the
                pool when you sign out (or after a day on its own) — everything you already
                submitted stays yours.
              </p>
            </div>
          </div>
        </div>

        <!-- Filter and Search Row -->
        <div class="row g-3 align-items-center justify-content-between mb-4">
          <div class="col-12 col-lg-5">
            <div class="input-group search-bar border shadow-sm rounded-pill overflow-hidden bg-white">
              <span class="input-group-text border-0 bg-white text-muted px-3"><i class="bi bi-search"></i></span>
              <input type="text" v-model="searchQuery"
                     class="form-control border-0 shadow-none py-2.5 fs-7 bg-white"
                     placeholder="Search your tasks by id, language or class..." />
              <button v-if="searchQuery" @click="searchQuery = ''" class="btn border-0 bg-white text-muted pe-3">
                <i class="bi bi-x-lg"></i>
              </button>
            </div>
          </div>

          <div class="col-12 col-lg-7 d-flex flex-wrap gap-2 justify-content-lg-end">
            <select v-model="selectedLanguage" class="form-select filter-select shadow-sm border rounded-pill py-2 px-3 bg-white" style="width: auto; min-width: 150px;">
              <option value="">All Languages</option>
              <option v-for="lang in uniqueLanguages" :key="lang" :value="lang">{{ lang }}</option>
            </select>

            <div class="bg-white p-1 rounded-pill shadow-sm border d-flex gap-1">
              <button v-for="status in ['all', 'Not Started', 'In Progress', 'Completed']" :key="status"
                      @click="selectedStatus = status"
                      :class="['btn btn-sm rounded-pill px-3 py-1.5 fw-semibold text-capitalize', selectedStatus === status ? 'btn-dark text-white' : 'btn-light text-secondary border-0 bg-transparent']">
                {{ status === 'all' ? 'All Tasks' : status }}
              </button>
            </div>

            <button @click="refresh" class="btn btn-light shadow-sm rounded-pill px-3" :disabled="isLoading" title="Refresh">
              <i :class="['bi bi-arrow-clockwise', isLoading ? 'animate-spin' : '']"></i>
            </button>
          </div>
        </div>

        <!-- Empty State -->
        <div v-if="filteredTasks.length === 0" class="empty-state-card text-center p-5 rounded-4 shadow-sm bg-white border border-light-subtle">
          <div class="empty-illustration mb-4">
            <svg viewBox="0 0 120 120" width="100" height="100" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="60" cy="60" r="50" fill="#f8fafc" />
              <path d="M40 55 L55 70 L80 40" stroke="#cbd5e1" stroke-width="6" stroke-linecap="round" stroke-linejoin="round" />
              <circle cx="85" cy="85" r="15" fill="#f1f5f9" />
              <path d="M80 85 L90 85" stroke="#94a3b8" stroke-width="2" stroke-linecap="round" />
              <path d="M85 80 L85 90" stroke="#94a3b8" stroke-width="2" stroke-linecap="round" />
            </svg>
          </div>
          <h4 class="fw-bold text-dark mb-2">No Assigned Tasks Found</h4>
          <p class="text-muted max-w-sm mx-auto mb-4">
            {{ tasks.length === 0
               ? 'You currently do not have any tasks assigned to your account.'
               : 'No tasks match your selected search query or filters.' }}
          </p>
          <div v-if="tasks.length === 0" class="alert alert-warning d-inline-block rounded-pill py-2 px-4 fs-7 mb-0">
            <i class="bi bi-info-circle-fill me-2"></i> Please contact your project administrator to assign tasks.
          </div>
          <button v-else @click="resetFilters" class="btn btn-dark rounded-pill px-4">Clear All Filters</button>
        </div>

        <!-- Task Cards Grid, one section per project (kind of work) -->
        <div v-else>
         <div v-for="group in groupedTasks" :key="group.key" class="mb-4">
          <div v-if="groupedTasks.length > 1" class="d-flex align-items-center gap-2 mb-3">
            <span class="project-chip"><i :class="group.icon + ' me-1'"></i>{{ group.label }}</span>
            <span class="text-muted small">{{ group.tasks.length }} task(s)</span>
            <hr class="flex-grow-1 my-0">
          </div>
          <div class="row g-4">
          <div v-for="task in group.tasks" :key="task.task_id" class="col-md-6 col-xl-4">
            <div class="task-card card h-100 border-0 shadow-sm rounded-4 overflow-hidden position-relative">
              <div :class="['status-bar', getStatusClass(task.myStatus)]"></div>

              <div class="card-body p-4 d-flex flex-column h-100">
                <div class="d-flex justify-content-between align-items-center mb-3">
                  <span :class="['badge rounded-pill px-3 py-1.5 fs-8 text-white shadow-sm', getLanguageBadgeClass(task.language)]">
                    {{ task.language }}
                  </span>
                  <span class="task-id fw-bold text-secondary text-uppercase fs-8">Task #{{ task.task_id }}</span>
                </div>

                <h5 class="fw-bold text-dark mb-2 text-truncate-2">
                  {{ task.label || `${task.language} · Class ${task.class}` }}
                </h5>
                <p class="text-secondary small mb-3 flex-grow-1">
                  Type: <span class="fw-semibold text-dark">{{ task.task_type_label || 'Text review' }}</span><br>
                  <span v-if="task.assigned_categories" class="d-inline-flex flex-wrap gap-1 my-1">
                    <span class="text-muted me-1">Your part:</span>
                    <span v-for="c in task.assigned_categories" :key="c"
                          class="badge bg-info-subtle text-info-emphasis border border-info-subtle rounded-pill">{{ c }}</span>
                  </span>
                  <br v-if="task.assigned_categories">
                  <span class="text-muted">{{ task.total.toLocaleString() }} prompts ·
                    {{ task.available_total.toLocaleString() }} still free to take</span>
                </p>

                <div class="mb-3">
                  <div class="d-flex justify-content-between text-xs mb-1.5">
                    <span class="text-muted fw-medium">Your progress</span>
                    <span class="fw-bold text-dark">
                      {{ task.mine.done.toLocaleString() }} / {{ task.total.toLocaleString() }} ({{ myPercent(task) }}%)
                    </span>
                  </div>
                  <div class="progress rounded-pill bg-light" style="height: 8px; overflow: hidden;">
                    <div :class="['progress-bar rounded-pill progress-bar-striped progress-bar-animated', getProgressBarClass(task.myStatus)]"
                         role="progressbar" :style="{ width: myPercent(task) + '%' }"></div>
                  </div>
                  <div v-if="task.mine.claimed" class="text-xs text-warning-emphasis mt-1">
                    <i class="bi bi-hourglass-split me-1"></i>{{ task.mine.claimed }} in your queue right now
                  </div>
                </div>

                <div class="d-flex align-items-center justify-content-between pt-3 border-top mt-auto">
                  <span :class="['badge px-2.5 py-1.5 rounded-pill fs-9 fw-bold d-inline-flex align-items-center gap-1', getStatusBadgeStyle(task.myStatus)]">
                    <i :class="['bi', getStatusIcon(task.myStatus)]"></i>
                    {{ task.myStatus }}
                  </span>

                  <div class="d-flex gap-1">
                    <button v-if="task.available_total" class="btn btn-sm btn-outline-primary rounded-pill px-3 fw-semibold"
                            title="Take prompts from this task" @click="takeFrom(task)">
                      <i class="bi bi-download"></i>
                    </button>
                    <router-link v-if="task.mine.claimed" :to="`${taskPath}?task=${task.task_id}`"
                                 :class="['btn btn-sm rounded-pill px-4 py-2 fw-semibold d-flex align-items-center gap-1.5 shadow-sm', getButtonClass(task.myStatus)]">
                      <span>{{ getButtonText(task.myStatus) }}</span>
                      <i class="bi bi-arrow-right-short fs-5 lh-1"></i>
                    </router-link>
                    <button v-else class="btn btn-sm btn-primary rounded-pill px-4 py-2 fw-semibold d-flex align-items-center gap-1.5 shadow-sm"
                            :disabled="!task.available_total" @click="takeFrom(task)">
                      <span>Start</span><i class="bi bi-arrow-right-short fs-5 lh-1"></i>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
          </div>
         </div>
        </div>

        <!-- ══ Work you have done: every prompt you submitted ══ -->
        <div v-if="doneTotal || myWorkFiltered" class="card border-0 shadow-sm rounded-4 mt-5">
          <div class="card-header bg-white border-0 pt-4 px-4 pb-0">
            <div class="d-flex flex-wrap align-items-center justify-content-between gap-2">
              <div>
                <h5 class="mb-1 d-flex align-items-center gap-2 fw-bold text-dark">
                  <span class="work-icon"><i class="bi bi-journal-check"></i></span>
                  <span>Work you have done</span>
                </h5>
                <p class="text-muted small mb-0">
                  Every prompt you submitted, with the original next to your version.
                  Click a row to see the whole record — and to edit your submission if you
                  want to change it.
                </p>
              </div>
              <button class="btn btn-sm btn-outline-secondary rounded-pill px-3" @click="downloadMyWork">
                <i class="bi bi-download me-1"></i>Download my work (CSV)
              </button>
            </div>
          </div>
          <div class="card-body p-4">
            <div class="d-flex flex-wrap gap-2 align-items-center mb-3">
              <select v-model="workFilters.task_id" class="form-select form-select-sm w-auto" @change="loadMyWork(1)">
                <option value="">All my tasks</option>
                <option v-for="t in tasks" :key="t.task_id" :value="String(t.task_id)">
                  #{{ t.task_id }} — {{ t.language }} · Class {{ t.class }}
                </option>
              </select>
              <select v-model="workFilters.category" class="form-select form-select-sm w-auto" @change="loadMyWork(1)">
                <option value="">Any type</option>
                <option v-for="c in workCategories" :key="c" :value="c">{{ c }}</option>
              </select>
              <select v-model="workFilters.difficulty" class="form-select form-select-sm w-auto" @change="loadMyWork(1)">
                <option value="">Any difficulty</option>
                <option v-for="d in ['Easy', 'Medium', 'Hard']" :key="d" :value="d">{{ d }}</option>
              </select>
              <select v-model="workFilters.state" class="form-select form-select-sm w-auto" @change="loadMyWork(1)">
                <option value="submitted">Everything I submitted</option>
                <option value="completed">Completed only</option>
                <option value="flagged">Flagged only</option>
              </select>
              <div class="form-check form-check-inline ms-1">
                <input class="form-check-input" type="checkbox" id="myEdited" v-model="workFilters.edited"
                       true-value="1" false-value="" @change="loadMyWork(1)">
                <label class="form-check-label text-xs" for="myEdited">I edited the text</label>
              </div>
              <input v-model="workFilters.q" class="form-control form-control-sm" style="width:200px"
                     placeholder="Search text or prompt ID…" @keyup.enter="loadMyWork(1)">
              <button class="btn btn-sm btn-outline-secondary" @click="loadMyWork(1)"><i class="bi bi-search"></i></button>
              <button class="btn btn-sm btn-outline-secondary" @click="resetWorkFilters">Clear</button>
              <span class="ms-auto text-xs text-muted">{{ workTotal.toLocaleString() }} prompt(s)</span>
            </div>

            <div v-if="workLoading" class="text-center py-4"><span class="spinner-border spinner-border-sm text-secondary"></span></div>
            <template v-else>
              <div class="table-responsive">
                <table class="table table-sm table-hover align-middle mb-0 work-table">
                  <thead>
                    <tr>
                      <th style="width:70px">Task</th><th style="width:70px">Prompt</th>
                      <th>Type</th><th>What you submitted</th><th>Difficulty</th>
                      <th>State</th><th class="text-nowrap">When (IST)</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="it in myWork" :key="it.id" class="cursor-pointer" @click="openWork(it)">
                      <td><span class="task-id-badge">#{{ it.task_id }}</span></td>
                      <td class="text-muted">{{ it.id }}</td>
                      <td class="text-muted fs-8">{{ it.category }}</td>
                      <td class="work-text" :dir="rtl(it.language) ? 'rtl' : 'ltr'">
                        <div>{{ trim(it.text) }}</div>
                        <div v-if="it.is_edited" class="fs-9 text-muted">was: <s>{{ trim(it.original_text, 55) }}</s></div>
                      </td>
                      <td>
                        <span v-if="it.final_difficulty" class="badge" :class="diffBadge(it.final_difficulty)">{{ it.final_difficulty }}</span>
                        <span v-else class="text-muted fs-8">—</span>
                      </td>
                      <td>
                        <span v-if="it.is_flagged" class="badge bg-warning-subtle text-warning">flagged</span>
                        <span v-else-if="it.is_edited" class="badge bg-primary-subtle text-primary">edited</span>
                        <span v-else class="badge bg-success-subtle text-success">as-is</span>
                      </td>
                      <td class="text-muted fs-8 text-nowrap">{{ it.completed_at_ist }}</td>
                    </tr>
                    <tr v-if="!myWork.length"><td colspan="7" class="text-center text-muted py-4">Nothing matches those filters.</td></tr>
                  </tbody>
                </table>
              </div>
              <div v-if="workPages > 1" class="d-flex justify-content-center align-items-center gap-3 mt-3">
                <button class="btn btn-sm btn-outline-secondary rounded-pill" :disabled="workPage <= 1" @click="loadMyWork(workPage - 1)">Previous</button>
                <span class="text-xs text-muted">Page {{ workPage }} of {{ workPages }}</span>
                <button class="btn btn-sm btn-outline-secondary rounded-pill" :disabled="workPage >= workPages" @click="loadMyWork(workPage + 1)">Next</button>
              </div>
            </template>
          </div>
        </div>

        <!-- Everything you have done: the tree, every granularity -->
        <div v-if="tree.languages?.length" class="card border-0 shadow-sm rounded-4 mt-5">
          <div class="card-header bg-white border-0 pt-4 px-4 pb-0 d-flex flex-wrap align-items-center gap-2">
            <h5 class="fw-bold text-dark mb-0"><i class="bi bi-diagram-3 me-2 text-primary"></i>Everything you have done</h5>
            <div class="ms-auto d-flex gap-2 align-items-center fs-8">
              <span class="badge bg-success-subtle text-success rounded-pill">{{ tree.totals?.completed ?? 0 }} completed</span>
              <span class="badge bg-warning-subtle text-warning rounded-pill">{{ tree.totals?.flagged ?? 0 }} flagged</span>
              <span class="badge bg-info-subtle text-info rounded-pill">{{ tree.totals?.claimed ?? 0 }} in queue</span>
            </div>
          </div>
          <div class="card-body p-4">
            <div class="tree">
              <div v-for="L in tree.languages" :key="L.language" class="tree-node">
                <button class="tree-row" @click="openTree[L.language] = !openTree[L.language]">
                  <i class="bi" :class="openTree[L.language] ? 'bi-chevron-down' : 'bi-chevron-right'"></i>
                  <span class="tree-name">{{ L.language }}</span>
                  <span class="tree-count">{{ L.done }} done<span v-if="L.claimed"> · {{ L.claimed }} in queue</span></span>
                  <div class="progress tree-bar"><div class="progress-bar bg-success" :style="{ width: L.progress + '%' }"></div></div>
                </button>

                <div v-if="openTree[L.language]" class="tree-children">
                  <div v-for="K in L.classes" :key="K.class" class="tree-node">
                    <button class="tree-row" @click="openTree[L.language + K.class] = !openTree[L.language + K.class]">
                      <i class="bi" :class="openTree[L.language + K.class] ? 'bi-chevron-down' : 'bi-chevron-right'"></i>
                      <span class="task-id-badge me-2">#{{ K.task_id }}</span>
                      <span class="tree-name">Class {{ K.class }}</span>
                      <span class="tree-count">{{ K.done }} done<span v-if="K.claimed"> · {{ K.claimed }} in queue</span></span>
                      <div class="progress tree-bar"><div class="progress-bar bg-success" :style="{ width: K.progress + '%' }"></div></div>
                    </button>

                    <div v-if="openTree[L.language + K.class]" class="tree-children">
                      <div v-for="C in K.categories" :key="C.category" class="tree-leaf">
                        <span class="tree-name">{{ C.category }}</span>
                        <span class="tree-count">
                          {{ C.completed }} completed<span v-if="C.flagged"> · {{ C.flagged }} flagged</span><span v-if="C.claimed"> · {{ C.claimed }} in queue</span>
                        </span>
                        <span class="tree-diffs">
                          <span v-for="(n, d) in C.difficulties" :key="d" class="badge me-1" :class="diffBadge(d)">{{ d }} {{ n }}</span>
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </template>

      <!-- ══ one submission in full ══ -->
      <div v-if="workModal" class="work-modal-backdrop" @click.self="workModal = null">
        <div class="work-modal">
          <div class="work-modal-head">
            <div>
              <h5 class="fw-bold mb-0">Prompt #{{ workModal.id }}</h5>
              <div class="text-xs text-muted">
                <span class="task-id-badge">#{{ workModal.task_id }}</span>
                {{ workModal.task_label }} · {{ workModal.category }}
              </div>
            </div>
            <button class="btn-close" @click="workModal = null"></button>
          </div>
          <div class="work-modal-body">
            <h6 class="fw-bold text-uppercase text-muted text-xs mb-2">Original prompt</h6>
            <div class="text-block" :dir="rtl(workModal.language) ? 'rtl' : 'ltr'">{{ workModal.original_text }}</div>

            <!-- ── edit mode: change the submission and save it again ── -->
            <template v-if="editMode">
              <h6 class="fw-bold text-uppercase text-muted text-xs mb-2 mt-3">
                <i class="bi bi-pencil-square me-1"></i>Edit your submission
              </h6>
              <textarea v-model="editText" rows="4" class="form-control"
                        :dir="rtl(workModal.language) ? 'rtl' : 'ltr'" spellcheck="false"></textarea>
              <div v-if="workModal.need_difficulty !== false && (!workModal.task_type || workModal.task_type === 'text-review')" class="d-flex flex-wrap gap-2 mt-3">
                <button v-for="d in ['Easy', 'Medium', 'Hard']" :key="d" type="button"
                        class="btn btn-sm rounded-pill px-3"
                        :class="editDifficulty === d
                                ? ({ Easy: 'btn-success', Medium: 'btn-warning', Hard: 'btn-danger' }[d])
                                : 'btn-outline-secondary'"
                        @click="editDifficulty = d">{{ d }}</button>
              </div>
              <p v-if="workModal.is_flagged" class="text-warning small mt-2 mb-0">
                <i class="bi bi-flag-fill me-1"></i>This prompt is currently flagged — saving an edit
                will submit it as annotated instead.
              </p>
              <p v-if="editError" class="text-danger small mt-2 mb-0">
                <i class="bi bi-exclamation-circle me-1"></i>{{ editError }}
              </p>
            </template>

            <template v-else-if="workModal.is_edited">
              <h6 class="fw-bold text-uppercase text-muted text-xs mb-2 mt-3">Your correction</h6>
              <div class="text-block edited-block" :dir="rtl(workModal.language) ? 'rtl' : 'ltr'">{{ workModal.text }}</div>
            </template>

            <div class="row g-3 mt-2">
              <div class="col-12 col-md-6">
                <h6 class="fw-bold text-uppercase text-muted text-xs mb-2">Difficulty</h6>
                <p class="mb-1 small"><span class="text-muted">suggested:</span>
                  <span class="badge ms-1 bg-light text-secondary border">{{ workModal.source_difficulty || 'unset' }}</span></p>
                <p class="mb-0 small"><span class="text-muted">you said:</span>
                  <span v-if="workModal.final_difficulty" class="badge ms-1" :class="diffBadge(workModal.final_difficulty)">
                    {{ workModal.final_difficulty }}</span>
                  <span v-else class="text-muted"> —</span></p>
              </div>
              <div class="col-12 col-md-6">
                <h6 class="fw-bold text-uppercase text-muted text-xs mb-2">When</h6>
                <p class="mb-1 small"><span class="text-muted">taken:</span> {{ workModal.claimed_at_ist || '—' }}</p>
                <p class="mb-1 small"><span class="text-muted">submitted:</span> {{ workModal.completed_at_ist || '—' }}</p>
                <p class="mb-0 small"><span class="text-muted">time spent:</span>
                  {{ workModal.time_taken_ms ? (workModal.time_taken_ms / 1000).toFixed(1) + 's' : '—' }}</p>
              </div>
            </div>

            <div v-if="workModal.is_flagged" class="alert alert-warning mt-3 py-2 mb-0">
              <i class="bi bi-flag-fill me-1"></i><strong>You flagged this:</strong> {{ workModal.flag_reason }}
            </div>
            <div v-if="workModal.notes" class="alert alert-light border mt-3 py-2 mb-0">
              <strong>Your note:</strong> {{ workModal.notes }}
            </div>
          </div>
          <div class="work-modal-foot">
            <template v-if="editMode">
              <button class="btn btn-outline-secondary me-auto" :disabled="editSaving"
                      @click="editMode = false">Cancel</button>
              <button class="btn btn-success" :disabled="editSaving || !canSaveEdit" @click="saveEdit">
                <span v-if="editSaving" class="spinner-border spinner-border-sm me-1"></span>
                <i v-else class="bi bi-cloud-arrow-up-fill me-1"></i>Save changes
              </button>
            </template>
            <template v-else>
              <button class="btn btn-outline-primary me-auto" @click="startEdit">
                <i class="bi bi-pencil-square me-1"></i>Edit
              </button>
              <button class="btn btn-secondary" @click="workModal = null">Close</button>
            </template>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, reactive, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { api, session, loadIdentity } from '@/session'
import { API_BASE_URL } from '@/config'

const router = useRouter()
const route = useRoute()
// Which pool team this workspace belongs to (from /pool/<teamKey>).
const teamKey = computed(() => String(route.params.teamKey || 'asr').toLowerCase())
const taskPath = computed(() => `/pool/${teamKey.value}/task`)

const displayUsername = ref('Annotator')
const isLoading = ref(true)
const error = ref('')

const tasks = ref([])
const pulls = ref([])
const stats = ref({})
const tree = ref({ languages: [], totals: {} })
const openTree = reactive({})
const pullPanel = ref(null)

const pulling = ref(false)
const pick = ref({ task_id: null, category: '', count: 20 })

// Annotator inbox (admin -> annotator messages), same as the TTS workspace
const messages = ref([])
const unreadCount = ref(0)
const isMarkingRead = ref(false)
let msgPollTimer = null

// Filtering & search
const searchQuery = ref('')
const selectedLanguage = ref('')
const selectedStatus = ref('all')

// "Work you have done": their own submissions, browsable
const myWork = ref([])
const workLoading = ref(false)
const workPage = ref(1)
const workPages = ref(1)
const workTotal = ref(0)
const workModal = ref(null)
const workFilters = reactive({ task_id: '', category: '', difficulty: '',
                               state: 'submitted', edited: '', q: '' })

const teamName = computed(() => stats.value.team_name || 'My workspace')
const currentTask = computed(() => tasks.value.find(t => t.task_id === pick.value.task_id) || null)

/** A task's status for THIS annotator: they hold the whole task, so their target is the whole task. */
function statusOf(t) {
  if (t.total && t.mine.done >= t.total) return 'Completed'
  if (t.mine.done || t.mine.claimed) return 'In Progress'
  return 'Not Started'
}

const decorated = computed(() => tasks.value.map(t => ({ ...t, myStatus: statusOf(t) })))

const uniqueLanguages = computed(() =>
  [...new Set(tasks.value.map(t => t.language).filter(Boolean))].sort())

const filteredTasks = computed(() => decorated.value.filter(t => {
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    const hay = `${t.task_id} ${t.language} class ${t.class}`.toLowerCase()
    if (!hay.includes(q)) return false
  }
  if (selectedLanguage.value && t.language !== selectedLanguage.value) return false
  if (selectedStatus.value !== 'all' && t.myStatus !== selectedStatus.value) return false
  return true
}))

const workByType = computed(() => stats.value.by_task_type || [])

// ── project grouping: each kind of work under its own heading ──
const PROJECT_ICONS = { 'text-review': 'bi bi-pencil-square', 'audio-mdfs': 'bi bi-headphones',
                        'translation-correction': 'bi bi-translate' }
function projectGroups(list) {
  const groups = {}
  for (const t of list) {
    const key = t.task_type || 'text-review'
    const g = groups[key] || (groups[key] = {
      key, label: t.task_type_label || 'Text review',
      icon: PROJECT_ICONS[key] || 'bi bi-tools', tasks: [] })
    g.tasks.push(t)
  }
  // The original text-review project first, then the rest alphabetically.
  return Object.values(groups).sort((a, b) =>
    (a.key === 'text-review' ? -1 : b.key === 'text-review' ? 1 : a.label.localeCompare(b.label)))
}
/** The filtered task cards, sectioned per project. */
const groupedTasks = computed(() => projectGroups(filteredTasks.value))
/** The pull panel's task dropdown, grouped the same way. */
const pullTaskGroups = computed(() => projectGroups(tasks.value))

const statsCards = computed(() => {
  const d = decorated.value
  return [
    { title: 'Tasks Assigned', value: d.length, sub: `${stats.value.available_total?.toLocaleString() || 0} prompts free to take`,
      icon: 'bi-collection-fill', bgClass: 'bg-primary-subtle', textClass: 'text-primary' },
    { title: 'Not Started', value: d.filter(t => t.myStatus === 'Not Started').length, sub: 'nothing taken yet',
      icon: 'bi-circle', bgClass: 'bg-secondary-subtle', textClass: 'text-secondary' },
    { title: 'In Progress', value: d.filter(t => t.myStatus === 'In Progress').length,
      sub: `${stats.value.outstanding || 0} prompt(s) in your queue`,
      icon: 'bi-hourglass-split', bgClass: 'bg-warning-subtle', textClass: 'text-warning' },
    { title: 'Completed', value: d.filter(t => t.myStatus === 'Completed').length,
      sub: `${stats.value.completed_today || 0} prompt(s) done today`,
      icon: 'bi-check-circle-fill', bgClass: 'bg-success-subtle', textClass: 'text-success' },
  ]
})

const overallTotal = computed(() => tasks.value.reduce((s, t) => s + (t.total || 0), 0))
const overallDone = computed(() => tasks.value.reduce((s, t) => s + (t.mine?.done || 0), 0))
const overallProgress = computed(() =>
  overallTotal.value ? Math.round((overallDone.value / overallTotal.value) * 100) : 0)

/** How many prompts are still free for exactly the chosen combination. */
const matching = computed(() => {
  const t = currentTask.value
  if (!t) return 0
  if (!pick.value.category) return t.available_total
  return t.available_by_category.find(x => x.category === pick.value.category)?.available || 0
})

/** Prompts are handed out in fixed batches; take a batch, finish it, take the next. */
const countOptions = computed(() => stats.value.batch_sizes || [20, 30, 50])

/** The ceiling on unfinished prompts one annotator may hold at once (0 = none). The server enforces it; these only drive the button state and the explanation. */
const openCap = computed(() => stats.value.max_open_items || 0)
const heldNow = computed(() => stats.value.outstanding || 0)
const atCap = computed(() => openCap.value > 0 && heldNow.value >= openCap.value)
const allowance = computed(() =>
  openCap.value ? Math.max(0, openCap.value - heldNow.value) : Infinity)

function fitCount() {
  const opts = countOptions.value
  if (!opts.includes(pick.value.count)) pick.value.count = opts[0] || 20
}
function onTaskChange() {
  pick.value.category = ''
  fitCount()
}
function scrollToPull() {
  pullPanel.value?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}
function takeFrom(task) {
  pick.value.task_id = task.task_id
  onTaskChange()
  nextTick(scrollToPull)
}
function resetFilters() {
  searchQuery.value = ''
  selectedLanguage.value = ''
  selectedStatus.value = 'all'
}

// ---- visual helpers, identical to the TTS workspace ----
function myPercent(t) { return t.total ? Math.round((t.mine.done / t.total) * 100) : 0 }
function getLanguageBadgeClass(lang) {
  return { hindi: 'bg-orange', english: 'bg-navy', bengali: 'bg-indigo', gujarati: 'bg-teal',
           kannada: 'bg-cyan', malayalam: 'bg-emerald', marathi: 'bg-pink', tamil: 'bg-crimson',
           telugu: 'bg-violet', urdu: 'bg-purple', assamese: 'bg-navy', punjabi: 'bg-teal',
         }[(lang || '').toLowerCase()] || 'bg-secondary'
}
function getStatusClass(s) {
  return s === 'Completed' ? 'status-completed' : s === 'In Progress' ? 'status-in-progress' : 'status-not-started'
}
function getStatusBadgeStyle(s) {
  if (s === 'Completed') return 'bg-success-subtle text-success border border-success-subtle'
  if (s === 'In Progress') return 'bg-warning-subtle text-warning-emphasis border border-warning-subtle'
  return 'bg-light text-muted border'
}
function getStatusIcon(s) {
  return s === 'Completed' ? 'bi-check-circle-fill' : s === 'In Progress' ? 'bi-hourglass-split' : 'bi-circle'
}
function getProgressBarClass(s) {
  return s === 'Completed' ? 'bg-success' : s === 'In Progress' ? 'bg-warning' : 'bg-secondary'
}
function getButtonClass(s) {
  if (s === 'Completed') return 'btn-outline-success'
  if (s === 'In Progress') return 'btn-warning text-dark'
  return 'btn-primary text-white'
}
function getButtonText(s) { return s === 'Completed' ? 'Review' : s === 'In Progress' ? 'Resume' : 'Start' }
function diffBadge(d) {
  return { Easy: 'bg-success-subtle text-success', Medium: 'bg-warning-subtle text-warning',
           Hard: 'bg-danger-subtle text-danger' }[d] || 'bg-light text-secondary border'
}

// ---- data ----
async function refresh() {
  // The full-page spinner only on the very first load; later refreshes swap the numbers in place so the screen never flickers.
  isLoading.value = tasks.value.length === 0
  error.value = ''
  try {
    const [w, t] = await Promise.all([
      api(`/pool/my/workspace?team=${teamKey.value}`),
      api(`/pool/my/tree?team=${teamKey.value}`),
    ])
    tasks.value = w.tasks || []
    pulls.value = w.pulls || []
    stats.value = { ...w.stats, team_name: w.team?.name,
                    batch_sizes: w.batch_sizes || [20, 30, 50],
                    max_open_items: w.max_open_items || 0 }
    tree.value = t
    if (!currentTask.value) {
      const first = tasks.value.find(x => x.available_total > 0) || tasks.value[0]
      if (first) { pick.value.task_id = first.task_id; onTaskChange() }
    } else {
      fitCount()
    }
  } catch (e) {
    error.value = e.message
  } finally {
    isLoading.value = false
  }
}

async function pullWork() {
  pulling.value = true
  error.value = ''
  try {
    const res = await api('/pool/pull', {
      method: 'POST',
      body: JSON.stringify({
        team: teamKey.value,
        task_id: pick.value.task_id,
        category: pick.value.category,
        count: pick.value.count,
      }),
    })
    await refresh()
    if (res.claimed) router.push(`${taskPath.value}?pull=${res.pull_id}`)
  } catch (e) {
    error.value = e.message
  } finally {
    pulling.value = false
  }
}

// ---- work you have done ----
const doneTotal = computed(() => stats.value.completed_total || 0)
const myWorkFiltered = computed(() =>
  Object.entries(workFilters).some(([k, v]) => v && k !== 'state'))
const workCategories = computed(() => {
  const set = new Set()
  for (const t of tasks.value) {
    for (const c of t.available_by_category || []) set.add(c.category)
  }
  for (const it of myWork.value) if (it.category) set.add(it.category)
  return [...set].sort()
})

function workQuery() {
  const qs = new URLSearchParams()
  Object.entries(workFilters).forEach(([k, v]) => { if (v) qs.set(k, v) })
  return qs
}

async function loadMyWork(p = 1) {
  workLoading.value = true
  try {
    const qs = workQuery()
    qs.set('team', teamKey.value)
    qs.set('page', p)
    qs.set('per_page', 25)
    const d = await api(`/pool/my/submissions?${qs}`)
    myWork.value = d.items || []
    workPage.value = d.page
    workPages.value = d.pages
    workTotal.value = d.total
  } catch (e) {
    error.value = e.message
  } finally {
    workLoading.value = false
  }
}

function resetWorkFilters() {
  Object.keys(workFilters).forEach(k => { workFilters[k] = '' })
  workFilters.state = 'submitted'
  loadMyWork(1)
}

// ---- editing a submission (submitted work always stays with the annotator, and it stays editable) ----
const editMode = ref(false)
const editText = ref('')
const editDifficulty = ref('')
const editSaving = ref(false)
const editError = ref('')

function openWork(it) {
  workModal.value = it
  editMode.value = false
  editError.value = ''
}

function startEdit() {
  editText.value = workModal.value.text || ''
  editDifficulty.value = workModal.value.final_difficulty || ''
  editError.value = ''
  editMode.value = true
}

const canSaveEdit = computed(() =>
  !!editText.value.trim()
  && (workModal.value?.need_difficulty === false || !!editDifficulty.value))

async function saveEdit() {
  if (!canSaveEdit.value || editSaving.value) return
  editSaving.value = true
  editError.value = ''
  try {
    const body = { item_id: workModal.value.id, text: editText.value }
    if (editDifficulty.value) body.difficulty = editDifficulty.value
    const r = await api('/pool/submit', { method: 'POST', body: JSON.stringify(body) })
    // keep fields the submit response does not know about (need_difficulty, task_label)
    workModal.value = { ...workModal.value, ...r.item }
    editMode.value = false
    loadMyWork(workPage.value)
  } catch (e) {
    editError.value = e.message
  } finally {
    editSaving.value = false
  }
}

async function downloadMyWork() {
  const token = localStorage.getItem('authToken') || sessionStorage.getItem('authToken')
  const res = await fetch(`${API_BASE_URL}/pool/my/export_submissions_csv?team=${teamKey.value}`,
                          { headers: { Authorization: `Bearer ${token}` } })
  if (!res.ok) { error.value = 'The download could not be prepared.'; return }
  const url = URL.createObjectURL(await res.blob())
  const a = document.createElement('a')
  a.href = url
  a.download = `my_${teamKey.value}_work.csv`
  a.click()
  URL.revokeObjectURL(url)
}

const RTL_LANGUAGES = ['urdu', 'arabic', 'sindhi', 'kashmiri']
function rtl(lang) { return RTL_LANGUAGES.includes(String(lang || '').toLowerCase()) }
function trim(t, n = 80) {
  const s = (t || '').replace(/\s+/g, ' ').trim()
  return s.length > n ? s.slice(0, n) + '…' : s
}

// ---- inbox ----
async function loadMessages() {
  try {
    const token = localStorage.getItem('authToken') || sessionStorage.getItem('authToken')
    if (!token) return
    const resp = await fetch(`${API_BASE_URL}/rater/messages`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!resp.ok) return
    const data = await resp.json()
    messages.value = data.messages || []
    unreadCount.value = data.unread_count || 0
  } catch (e) {
    console.error('Error loading messages:', e)
  }
}

async function markAllRead() {
  if (isMarkingRead.value || !unreadCount.value) return
  isMarkingRead.value = true
  try {
    const token = localStorage.getItem('authToken') || sessionStorage.getItem('authToken')
    const resp = await fetch(`${API_BASE_URL}/rater/messages/read`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    })
    if (resp.ok) {
      messages.value = messages.value.map(m => ({ ...m, is_read: true }))
      unreadCount.value = 0
    }
  } catch (e) {
    console.error('Error marking messages read:', e)
  } finally {
    isMarkingRead.value = false
  }
}

function formatMsgDate(iso) {
  if (!iso) return ''
  const d = new Date(/[Zz]|[+-]\d\d:\d\d$/.test(iso) ? iso : iso + 'Z')
  if (isNaN(d.getTime())) return ''
  return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}
const notifKind = (c) => c === 'nudge' ? 'nudge' : c === 'broadcast' ? 'broadcast' : 'message'
const notifIcon = (c) => c === 'nudge' ? 'bi-bell-fill' : c === 'broadcast' ? 'bi-broadcast' : 'bi-chat-left-text-fill'
const notifLabel = (c) => c === 'nudge' ? 'Task reminder' : c === 'broadcast' ? 'Announcement' : 'Message'

onMounted(async () => {
  await loadIdentity()
  displayUsername.value = session.name || 'Annotator'
  await refresh()
  loadMessages()
  loadMyWork(1)
  msgPollTimer = setInterval(loadMessages, 30000)
})

onUnmounted(() => {
  if (msgPollTimer) clearInterval(msgPollTimer)
})
</script>

<style scoped>
.page-container { min-height: calc(100vh - 40px); background-color: #f8fafc; }

/** Greeting banner */
.welcome-banner { border-radius: 20px; background-color: #1e293b; position: relative;
                  overflow: hidden; border: 1px solid rgba(255,255,255,.05); }
.banner-gradient { position: absolute; top: 0; left: 0; width: 100%; height: 100%;
                   background: linear-gradient(135deg, #d8661b 0%, #f4a93c 100%); opacity: .95; z-index: 0; }
.z-index-1 { z-index: 1; }
.opacity-85 { opacity: .85; }
.banner-badge { background-color: rgba(255,255,255,.18); backdrop-filter: blur(10px);
                border: 1px solid rgba(255,255,255,.2); color: #fff; }
.banner-progress { border-top: 1px solid rgba(255,255,255,.25); }
.banner-progress-bar { background-color: rgba(255,255,255,.25) !important; }
.btn-continue { background-color: #fff; color: #b4530f; border: none;
                transition: transform .2s ease, box-shadow .2s ease; }
.btn-continue:hover { color: #8a3f0d; transform: translateY(-1px); box-shadow: 0 8px 18px rgba(0,0,0,.18); }
.all-done-pill { background-color: rgba(255,255,255,.2); border: 1px solid rgba(255,255,255,.35); color: #fff; }
.tracking-wider { letter-spacing: .08em; }

/** Stat cards */
.stat-card { transition: transform .2s ease, box-shadow .2s ease; }
.hover-lift:hover { transform: translateY(-4px); box-shadow: 0 .5rem 1rem rgba(0,0,0,.08) !important; }
.stat-icon { display: inline-flex; align-items: center; justify-content: center; font-size: .9rem; }

/** Language badge colours, same palette as the TTS workspace */
.bg-orange { background-color: #e27c3e !important; }
.bg-navy { background-color: #1e3a8a !important; }
.bg-indigo { background-color: #4f46e5 !important; }
.bg-teal { background-color: #0d9488 !important; }
.bg-cyan { background-color: #0891b2 !important; }
.bg-emerald { background-color: #059669 !important; }
.bg-pink { background-color: #db2777 !important; }
.bg-crimson { background-color: #be123c !important; }
.bg-violet { background-color: #7c3aed !important; }
.bg-purple { background-color: #9333ea !important; }

.filter-select { font-size: .85rem; font-weight: 500; color: #475569; }
.search-bar input::placeholder { color: #94a3b8; font-size: .9rem; }

/** Task cards */
.project-chip { display: inline-flex; align-items: center; background: #212529; color: #fff;
                border-radius: 2rem; padding: .35rem .95rem; font-weight: 700; font-size: .85rem; }
.task-card { transition: transform .2s ease, box-shadow .2s ease; }
.task-card:hover { transform: translateY(-4px); box-shadow: 0 .75rem 1.5rem rgba(0,0,0,.08) !important; }
.status-bar { height: 5px; width: 100%; }
.status-completed { background: linear-gradient(90deg, #10b981, #34d399); }
.status-in-progress { background: linear-gradient(90deg, #f59e0b, #fbbf24); }
.status-not-started { background: linear-gradient(90deg, #cbd5e1, #e2e8f0); }
.task-id { letter-spacing: .04em; }
.text-truncate-2 { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
                   overflow: hidden; line-height: 1.35; }
.text-xs { font-size: .75rem; }
.fs-7 { font-size: .9rem; }
.fs-8 { font-size: .78rem; }
.fs-9 { font-size: .7rem; }
.empty-state-card { border-style: dashed !important; }
.max-w-sm { max-width: 26rem; }
.animate-spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/** Inbox, identical to the TTS workspace */
.inbox-card { border: 1px solid rgba(0,0,0,.04) !important; }
.inbox-list { max-height: 430px; overflow-y: auto; padding-right: 4px; }
.inbox-item { background: #f8fafc; border: 1px solid #eef2f7; }
.inbox-item.unread { background: #fff; border-color: #dbeafe; box-shadow: 0 1px 4px rgba(0,0,0,.04); }
.inbox-avatar { width: 34px; height: 34px; border-radius: 10px; display: grid; place-items: center; color: #fff; }
.inbox-avatar.broadcast { background: linear-gradient(135deg, #f4a93c, #d8661b); }
.inbox-avatar.nudge { background: linear-gradient(135deg, #fbbf24, #f59e0b); }
.inbox-avatar.message { background: linear-gradient(135deg, #818cf8, #4f46e5); }
.inbox-chip { font-size: .68rem; font-weight: 700; text-transform: uppercase; letter-spacing: .04em;
              border-radius: 1rem; padding: .1rem .6rem; }
.inbox-chip.broadcast { background: #fff1e2; color: #c2410c; }
.inbox-chip.nudge { background: #fef3c7; color: #b45309; }
.inbox-chip.message { background: #e0e7ff; color: #4338ca; }
.inbox-new-dot { width: 7px; height: 7px; border-radius: 50%; background: #ef4444; margin-left: 6px; display: inline-block; }
.inbox-body { white-space: pre-wrap; word-break: break-word; line-height: 1.6; }
.min-w-0 { min-width: 0; }

/** The ASR pull panel */
.pull-card { border: 1px solid rgba(15,23,42,.06) !important; }
.pull-icon { width: 30px; height: 30px; border-radius: 9px; display: grid; place-items: center;
             background: linear-gradient(135deg, #34d399, #059669); color: #fff; font-size: .85rem; }
.pull-table th { font-size: .7rem; text-transform: uppercase; letter-spacing: .04em; color: #94a3b8; font-weight: 700; }
.task-id-badge { display: inline-block; background: #eef2ff; color: #4338ca; border: 1px solid #c7d2fe;
                 border-radius: .4rem; padding: .05rem .4rem; font-size: .75rem; font-weight: 700; }

/** Work you have done */
.work-icon { width: 30px; height: 30px; border-radius: 9px; display: grid; place-items: center;
             background: linear-gradient(135deg, #818cf8, #4f46e5); color: #fff; font-size: .85rem; }
.work-table th { font-size: .7rem; text-transform: uppercase; letter-spacing: .04em; color: #94a3b8; font-weight: 700; }
.work-text { max-width: 420px; }
.cursor-pointer { cursor: pointer; }
.work-modal-backdrop { position: fixed; inset: 0; background: rgba(15,23,42,.5); display: grid;
                       place-items: center; z-index: 1080; padding: 1rem; }
.work-modal { background: #fff; border-radius: .9rem; width: 100%; max-width: 620px;
              max-height: 88vh; display: flex; flex-direction: column; }
.work-modal-head { display: flex; justify-content: space-between; align-items: flex-start;
                   padding: 1.1rem 1.25rem; border-bottom: 1px solid #e9ecef; }
.work-modal-body { padding: 1.25rem; overflow-y: auto; }
.work-modal-foot { display: flex; justify-content: flex-end; padding: 1rem 1.25rem;
                   border-top: 1px solid #e9ecef; }
.text-block { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: .5rem;
              padding: .8rem 1rem; white-space: pre-wrap; line-height: 1.6; }
.edited-block { background: #fff9e6; border-color: #ffe08a; }

/** Progress tree */
.tree-node { border-left: 2px solid #eef2ff; padding-left: .25rem; }
.tree-row { display: flex; align-items: center; gap: .6rem; width: 100%; background: transparent;
            border: none; padding: .5rem .6rem; border-radius: .5rem; text-align: left; }
.tree-row:hover { background: #f8fafc; }
.tree-name { font-weight: 600; color: #212529; min-width: 120px; }
.tree-count { font-size: .78rem; color: #6c757d; }
.tree-bar { height: 6px; flex-grow: 1; max-width: 260px; margin-left: auto; }
.tree-children { padding-left: 1.4rem; }
.tree-leaf { display: flex; align-items: center; gap: .6rem; padding: .3rem .6rem; font-size: .82rem; }
.tree-leaf .tree-name { min-width: 110px; font-weight: 500; color: #495057; }
.tree-diffs { margin-left: auto; font-size: .7rem; }
</style>
