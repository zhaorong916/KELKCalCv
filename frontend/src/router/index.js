import { createRouter, createWebHistory } from 'vue-router'
import MainLayout from '@/layouts/MainLayout.vue'

const routes = [
  {
    path: '/',
    component: MainLayout,
    children: [
      { path: '', name: 'dashboard', component: () => import('@/views/Dashboard.vue') },
      { path: 'projects', name: 'projects', component: () => import('@/views/Projects.vue') },
      { path: 'projects/:pid', name: 'project-detail', component: () => import('@/views/ProjectDetail.vue') },
      { path: 'projects/:pid/valves/:vid', name: 'valve-calc', component: () => import('@/views/Calculation.vue') },
      { path: 'fluids', name: 'fluids', component: () => import('@/views/Fluids.vue') },
      { path: 'valve-types', name: 'valve-types', component: () => import('@/views/ValveTypes.vue') },
      { path: 'about', name: 'about', component: () => import('@/views/About.vue') },
    ]
  }
]

export default createRouter({
  history: createWebHistory(),
  routes
})
