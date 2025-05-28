import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import LoginView from '../views/LoginView.vue'
import SignupView from '@/views/SignupView.vue';
import TestView from '@/views/TestView.vue';
import CompletionView from '@/views/CompletionView.vue';
import DynamicTestView from '@/views/DynamicTestView.vue';
import TrackingPageView from '@/views/TrackingPageView.vue';

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
  ],
});

// Navigation guard to check authentication status before each route navigation
router.beforeEach((to, from, next) => {
  const authToken = localStorage.getItem('authToken');

  if (to.meta.requiresAuth && !authToken) {
    // If route requires authentication and authToken is not present, redirect to login
    next('/login');
  // } else if (!to.meta.requiresAuth && authToken) {
  //   // If route does not require authentication and authToken is present, redirect to home
  //   next('/');
  } else {
    // Continue navigation
    next();
  }
});

export default router;
