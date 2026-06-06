import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from './views/Dashboard.vue'

const routes = [
  { path: '/', redirect: '/dashboard' },
  { path: '/dashboard', name: 'Dashboard', component: Dashboard },
  { path: '/calendar', name: 'Calendar', component: () => import('./views/Calendar.vue') },
  { path: '/report', name: 'Report', component: () => import('./views/Report.vue') },
  { path: '/history', name: 'History', component: () => import('./views/History.vue') },
  { path: '/suggest', name: 'Suggest', component: () => import('./views/Suggest.vue') },
  { path: '/pay', name: 'Pay', component: () => import('./views/Pay.vue') },
  { path: '/health', name: 'Health', component: () => import('./views/Health.vue') },
  { path: '/annual-fees', name: 'AnnualFees', component: () => import('./views/AnnualFees.vue') },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
