import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

import { getToken } from '@/utils/auth'

const Layout = () => import('@/components/Layout.vue')

// 登录后才能访问的页面（不含任何登录/注册入口与学习画像页面）
const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/auth/Login.vue'),
    meta: { public: true, title: '登录' },
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/auth/Register.vue'),
    meta: { public: true, title: '注册' },
  },
  {
    path: '/',
    component: Layout,
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard.vue'),
        meta: { title: '学习看板', icon: 'DataAnalysis' },
      },
      {
        path: 'agent',
        name: 'Agent',
        component: () => import('@/views/Agent.vue'),
        meta: { title: '学习小助手', icon: 'ChatLineRound' },
      },
      {
        path: 'agent-tasks',
        name: 'AgentTasks',
        component: () => import('@/views/AgentTasks.vue'),
        meta: { title: '任务轨迹', icon: 'List' },
      },
      {
        path: 'study-plan',
        name: 'StudyPlan',
        component: () => import('@/views/StudyPlan.vue'),
        meta: { title: '学习计划', icon: 'Calendar' },
      },
      {
        path: 'practice',
        name: 'Practice',
        component: () => import('@/views/Practice.vue'),
        meta: { title: '练习', icon: 'EditPen' },
      },
      {
        path: 'wrong-questions',
        name: 'WrongQuestions',
        component: () => import('@/views/WrongQuestions.vue'),
        meta: { title: '错题集', icon: 'Collection' },
      },
      {
        path: 'knowledge-base',
        name: 'KnowledgeBase',
        component: () => import('@/views/KnowledgeBase.vue'),
        meta: { title: '知识库', icon: 'Files' },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/dashboard',
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, _from, next) => {
  const token = getToken()
  if (to.meta.public) {
    // 已登录用户访问登录/注册页 → 跳转看板
    if (token && (to.name === 'Login' || to.name === 'Register')) {
      next({ name: 'Dashboard' })
      return
    }
    next()
    return
  }
  // 未登录访问任何内部页面 → 跳转登录
  if (!token) {
    next({ name: 'Login', query: { redirect: to.fullPath } })
    return
  }
  next()
})

router.afterEach((to) => {
  const title = (to.meta?.title as string) || ''
  document.title = title ? `${title} · 智学 Agent` : '智学 Agent'
})

export default router