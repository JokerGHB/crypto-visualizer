import { createRouter, createWebHistory } from 'vue-router';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: () => import('../views/Home.vue') },
    {
      path: '/playground',
      name: 'playground',
      component: () => import('../views/Playground.vue'),
    },
    { path: '/sbox', name: 'sbox', component: () => import('../views/SBox.vue') },
    {
      path: '/exercise',
      name: 'exercise',
      component: () => import('../views/Exercise.vue'),
    },
    {
      path: '/history',
      name: 'history',
      component: () => import('../views/History.vue'),
    },
    { path: '/login', name: 'login', component: () => import('../views/Login.vue') },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
  scrollBehavior() {
    return { top: 0 };
  },
});

export default router;