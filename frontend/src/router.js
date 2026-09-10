import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'Play', component: () => import('@/pages/Play.vue') },
  { path: '/runs', name: 'Runs', component: () => import('@/pages/Runs.vue') },
  { path: '/iwads', name: 'Iwads', component: () => import('@/pages/Iwads.vue') },
]

// Served by Frappe at /doom (www/doom.html) and /doom/<anything> (hooks.py).
export default createRouter({ history: createWebHistory('/doom'), routes })
