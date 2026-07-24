import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import LoginView from '../views/LoginView.vue'
import SignupView from '@/views/SignupView.vue';
import TestView from '@/views/TestView.vue';
import CompletionView from '@/views/CompletionView.vue';
import DynamicTestView from '@/views/DynamicTestView.vue';
import TrackingPageView from '@/views/TrackingPageView.vue';
import AdminTaskReview from '@/views/AdminTaskReview.vue';

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
      path: '/signup',
      name: 'signup',
      component: SignupView,
    },
    {
      path: '/:id', // Dynamic route for 'id'
      name: 'Test',
      component: TestView, // Use the same HomeView component
      props: true, // Enable passing the 'id' as a prop to the HomeView component
      meta: { requiresAuth: true }
    },
    {
      path: '/test', // Dynamic route for 'id'
      name: 'DynamicTest',
      component: DynamicTestView,
      props: route => ({
        prolific_pid: route.query.PROLIFIC_PID,
        study_id: route.query.STUDY_ID,
        session_id: route.query.SESSION_ID,
      }), // Extract query parameters
      // meta: { requiresAuth: true },
    },
    {
      path: '/tracking',
      name: 'TrackingPage',
      component: TrackingPageView,
      meta: { requiresAuth: true },
    },
    {
      // Admin-only review of a task's submitted annotations (per-annotator tabs).
      // Must be declared before '/:id' would be considered; its 3-segment path
      // never collides with the single-segment '/:id' route.
      path: '/admin/task/:id',
      name: 'AdminTaskReview',
      component: AdminTaskReview,
      props: true,
      meta: { requiresAuth: true },
    },
  ],
});

// Navigation guard to check authentication status before each route navigation
router.beforeEach((to, from, next) => {
  const authToken = localStorage.getItem('authToken');

  if (to.path === '/tracking' || to.path.startsWith('/admin/')) {
    if (!authToken) {
      next({ path: '/login', query: { redirect: to.fullPath } });
    } else {
      let isAdmin = false;
      try {
        const payload = JSON.parse(atob(authToken.split('.')[1]));
        isAdmin = (payload.username === 'admin');
      } catch (e) {
        console.error('Error parsing token:', e);
      }
      if (isAdmin) {
        next();
      } else {
        next('/');
      }
    }
  } else if (to.meta.requiresAuth && !authToken) {
    // Requires auth and not logged in: remember where they were going (including the
    // query string, e.g. ?task=<id> deep links) so login can send them back there.
    next({ path: '/login', query: { redirect: to.fullPath } });
  } else {
    // Continue navigation
    next();
  }
});

export default router;
