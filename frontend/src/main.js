import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import './style.css'

// 导入页面组件
import Home from './views/Home.vue'
import Chat from './views/Chat.vue'
import Knowledge from './views/Knowledge.vue'

// 配置路由
const routes = [
  { path: '/', component: Home, name: 'home', meta: { title: 'Agent 管理' } },
  { path: '/chat/:agentId?', component: Chat, name: 'chat', meta: { title: '对话交互' } },
  { path: '/knowledge', component: Knowledge, name: 'knowledge', meta: { title: '知识库' } }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫：更新页面标题
router.beforeEach((to, from, next) => {
  document.title = `${to.meta.title} - 实验室 Agent 系统` || '实验室 Agent 系统'
  next()
})

const app = createApp(App)
app.use(router)
app.mount('#app')
