import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import LoginView from '../views/LoginView.vue'
import SignupView from '@/views/SignupView.vue';
import TestView from '@/views/TestView.vue';
import CompletionView from '@/views/CompletionView.vue';
import AdminTaskReview from '@/views/AdminTaskReview.vue';
import WorkspaceView from '@/views/WorkspaceView.vue';
import OrgOverview from '@/views/OrgOverview.vue';
import AsrWorkspace from '@/views/AsrWorkspace.vue';
import AsrTaskView from '@/views/AsrTaskView.vue';
import TeamDashboardView from '@/views/TeamDashboardView.vue';
import PendingApprovalView from '@/views/PendingApprovalView.vue';

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomeView,
      meta: { requiresAuth: true }, // Add meta field for authentication requirement
    },
    {
      path: '/completion',
      name: 'completion',
      component: CompletionView,
      meta: { requiresAuth: true }, // Add meta field for authentication requirement
    },

    {
      path: '/login',
      name: 'login',
      component: LoginView,
    },
    {
      // One sign-in page for everyone. The old admin URL still resolves.
      path: '/admin/login',
      redirect: '/login',
    },
    {
      path: '/signup',
      name: 'signup',
      component: SignupView,
    },
    {
      // Annotators who belong to more than one team land here to pick a workspace.
      path: '/workspaces',
      name: 'Workspaces',
      component: WorkspaceView,
      meta: { requiresAuth: true },
    },
    {
      // Organisation admin: every team at a glance + admin accounts.
      path: '/org',
      name: 'OrgOverview',
      component: OrgOverview,
      meta: { requiresAuth: true, requiresAdmin: true },
    },
    {
      // Pool annotator: workspace (pull step + queue) for ANY pool-workflow team.
      path: '/pool/:teamKey',
      name: 'PoolWorkspace',
      component: AsrWorkspace,
      meta: { requiresAuth: true },
    },
    {
      path: '/pool/:teamKey/task',
      name: 'PoolTask',
      component: AsrTaskView,
      meta: { requiresAuth: true },
    },
    // Historical ASR URLs still resolve.
    {
      path: '/asr',
      redirect: () => ({ path: '/pool/asr' }),
    },
    {
      path: '/asr/task',
      redirect: to => ({ path: '/pool/asr/task', query: to.query }),
    },
    {
      // Every team's dashboard follows the same '/<team>/admin' shape; the component is picked by the team's workflow, so a new team needs no route change.
      path: '/:team/admin',
      name: 'TeamDashboard',
      component: TeamDashboardView,
      meta: { requiresAuth: true, requiresAdmin: true },
    },
    {
      // Historical URL -- everything that linked to /tracking still works.
      path: '/tracking',
      redirect: '/tts/admin',
    },
    {
      // Signed up but not yet approved into any team: the waiting room. (Was an unrouted path that fell through to the raw test page.)
      path: '/no-workspace',
      name: 'PendingApproval',
      component: PendingApprovalView,
      meta: { requiresAuth: true },
    },
    {
      // Admin-only review of a task's submitted annotations (per-annotator tabs).
      path: '/admin/task/:id',
      name: 'AdminTaskReview',
      component: AdminTaskReview,
      props: true,
      meta: { requiresAuth: true, requiresAdmin: true },
    },
    {
      path: '/:id', // Dynamic route for 'id' -- keep LAST so real paths win
      name: 'Test',
      component: TestView, // Use the same HomeView component
      props: true, // Enable passing the 'id' as a prop to the HomeView component
      meta: { requiresAuth: true }
    },
  ],
});

/** Read the JWT without verifying it -- only used to route, never to authorise (every endpoint re-c. */
function tokenClaims() {
  const token = localStorage.getItem('authToken') || sessionStorage.getItem('authToken');
  if (!token) return null;
  try {
    return JSON.parse(atob(token.split('.')[1]));
  } catch (e) {
    console.error('Error parsing token:', e);
    return null;
  }
}

/** An admin never belongs on an annotator screen. The token already says which kind of admin they a. */
function adminHome(claims) {
  if (!claims) return null;
  const isAdmin = claims.kind === 'admin' || claims.username === 'admin';
  if (!isAdmin) return null;
  if (claims.scope === 'org' || !claims.team) return '/org';
  return `/${claims.team}/admin`;
}

// Routes that only make sense for an annotator; an admin landing here is sent home.
const ANNOTATOR_ONLY = ['/', '/workspaces', '/completion'];
const isAnnotatorPath = (path) =>
  ANNOTATOR_ONLY.includes(path) || path.startsWith('/pool/') || path.startsWith('/asr');

router.beforeEach((to, from, next) => {
  const claims = tokenClaims();
  const home = adminHome(claims);

  if (to.meta.requiresAdmin) {
    if (!claims) {
      next({ path: '/login', query: { redirect: to.fullPath } });
      return;
    }
    next(home ? undefined : '/');
    return;
  }

  if (to.meta.requiresAuth && !claims) {
    // Requires auth and not logged in: remember where they were going (including the
    next({ path: '/login', query: { redirect: to.fullPath } });
    return;
  }

  // A signed-in admin who opens the site root (or any annotator page) goes to
  if (home && isAnnotatorPath(to.path)) {
    next(home);
    return;
  }

  next();
});

export default router;
