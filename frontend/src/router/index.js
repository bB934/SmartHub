import { createRouter, createWebHistory } from 'vue-router'
import ChatView from '../views/ChatView.vue'
import DocView from '../views/DocView.vue'
import SearchView from '../views/SearchView.vue'

const routes = [
  { path: '/', redirect: '/chat' },
  { path: '/chat', component: ChatView },
  { path: '/docs', component: DocView },
  { path: '/search', component: SearchView },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
