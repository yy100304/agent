<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ChatLineRound,
  Calendar,
  Collection,
  DataAnalysis,
  EditPen,
  Files,
} from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

// 固定导航：学习看板 / AI Agent / 学习计划 / 练习 / 错题集 / 知识库
// 注意：登录后不出现任何"登录/注册"入口，仅保留"退出登录"
const menus = [
  { name: 'Dashboard', path: '/dashboard', title: '学习看板', icon: DataAnalysis },
  { name: 'Agent', path: '/agent', title: 'AI Agent', icon: ChatLineRound },
  { name: 'StudyPlan', path: '/study-plan', title: '学习计划', icon: Calendar },
  { name: 'Practice', path: '/practice', title: '练习', icon: EditPen },
  { name: 'WrongQuestions', path: '/wrong-questions', title: '错题集', icon: Collection },
  { name: 'KnowledgeBase', path: '/knowledge-base', title: '知识库', icon: Files },
]

const activeMenu = computed(() => route.path)

function go(path: string) {
  router.push(path)
}

function handleLogout() {
  userStore.logout()
  router.push({ name: 'Login' })
}
</script>

<template>
  <div class="layout">
    <aside class="sidebar">
      <div class="logo">
        <div class="logo-mark">S</div>
        <span class="logo-text">智学 Agent</span>
      </div>
      <nav class="menu">
        <div
          v-for="item in menus"
          :key="item.name"
          class="menu-item"
          :class="{ active: activeMenu === item.path }"
          @click="go(item.path)"
        >
          <el-icon class="menu-icon"><component :is="item.icon" /></el-icon>
          <span class="menu-label">{{ item.title }}</span>
        </div>
      </nav>
      <div class="sidebar-footer">
        <div class="user-chip" @click="handleLogout">
          <el-avatar :size="30" class="user-avatar">
            {{ userStore.user?.username?.slice(0, 1).toUpperCase() || 'U' }}
          </el-avatar>
          <div class="user-meta">
            <span class="user-name">{{ userStore.user?.username || '未登录' }}</span>
            <span class="user-logout">退出登录</span>
          </div>
        </div>
      </div>
    </aside>

    <div class="main">
      <header class="topbar">
        <div class="topbar-left">
          <span class="page-title">{{ (route.meta?.title as string) || '智学 Agent' }}</span>
        </div>
        <div class="topbar-right">
          <span class="topbar-hint">让 AI 主动执行学习任务</span>
        </div>
      </header>

      <main class="content">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>
  </div>
</template>

<style scoped lang="scss">
@use '@/styles/variables.scss' as *;

.layout {
  display: flex;
  min-height: 100vh;
  background: $bg-page;
}

.sidebar {
  width: 224px;
  background: $bg-card;
  border-right: 1px solid $border-light;
  padding: $gap-md 12px;
  display: flex;
  flex-direction: column;
  gap: $gap-md;
  position: sticky;
  top: 0;
  height: 100vh;
}

.logo {
  display: flex;
  align-items: center;
  gap: $gap-sm;
  padding: 8px 4px;
}

.logo-mark {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  background: linear-gradient(135deg, #4f7cf7, #7c5cff);
  color: #fff;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
}

.logo-text {
  font-weight: 600;
  font-size: 16px;
  color: $text-primary;
}

.menu {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: $gap-sm;
  flex: 1;
}

.menu-item {
  display: flex;
  align-items: center;
  gap: $gap-sm;
  padding: 10px 12px;
  border-radius: 12px;
  color: $text-secondary;
  cursor: pointer;
  transition: all 0.15s ease;

  &:hover {
    background: $primary-soft;
    color: $primary;
  }

  &.active {
    background: $primary-soft;
    color: $primary;
    font-weight: 500;
  }
}

.menu-icon {
  font-size: 18px;
}

.sidebar-footer {
  border-top: 1px solid $border-light;
  padding-top: $gap-sm;
}

.user-chip {
  display: flex;
  align-items: center;
  gap: $gap-sm;
  padding: 8px;
  border-radius: 12px;
  cursor: pointer;
  transition: background 0.15s ease;

  &:hover {
    background: $bg-muted;
  }
}

.user-avatar {
  background: linear-gradient(135deg, #4f7cf7, #7c5cff);
  color: #fff;
  font-weight: 600;
  flex-shrink: 0;
}

.user-meta {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.user-name {
  font-size: 13px;
  color: $text-primary;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-logout {
  font-size: 11px;
  color: $text-placeholder;
}

.main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.topbar {
  height: 64px;
  background: $bg-card;
  border-bottom: 1px solid $border-light;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 $gap-lg;
  position: sticky;
  top: 0;
  z-index: 10;
}

.page-title {
  font-size: 16px;
  font-weight: 600;
  color: $text-primary;
}

.topbar-hint {
  font-size: 12px;
  color: $text-placeholder;
}

.content {
  padding: $gap-lg;
  flex: 1;
  min-height: 0;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.18s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
