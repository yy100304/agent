<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  ChatLineRound,
  Calendar,
  Collection,
  DataAnalysis,
  EditPen,
  Files,
  List,
} from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { useSubjectStore } from '@/stores/subject'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const subjectStore = useSubjectStore()

const showSubject = computed(() => route.name !== 'Agent')
const addVisible = ref(false)
const newSubject = ref('')
const adding = ref(false)

const subjectValue = computed<string>({
  get: () => subjectStore.current,
  set: (value: string) => {
    if (value === '__add__') {
      addVisible.value = true
      return
    }
    subjectStore.setCurrent(value)
  },
})

async function onAddSubject() {
  const name = newSubject.value.trim()
  if (!name || adding.value) return
  adding.value = true
  try {
    await subjectStore.add(name)
    ElMessage.success(`已添加科目「${name}」`)
    addVisible.value = false
    newSubject.value = ''
  } catch {
    /* 拦截器已提示 */
  } finally {
    adding.value = false
  }
}

onMounted(() => {
  subjectStore.load().catch(() => {
    /* 科目加载失败不影响主流程 */
  })
})

// 固定导航：学习看板 / AI Agent / 任务轨迹 / 学习计划 / 练习 / 错题集 / 知识库
// 注意：登录后不出现任何"登录/注册"入口，仅保留"退出登录"
const menus = [
  { name: 'Dashboard', path: '/dashboard', title: '学习看板', icon: DataAnalysis },
  { name: 'Agent', path: '/agent', title: '学习小助手', icon: ChatLineRound },
  { name: 'AgentTasks', path: '/agent-tasks', title: '任务轨迹', icon: List },
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
          <template v-if="showSubject">
            <span class="subject-text">科目</span>
            <el-select
              v-model="subjectValue"
              size="small"
              class="subject-select"
              :loading="subjectStore.loading"
              placeholder="选择科目"
            >
              <el-option
                v-for="item in subjectStore.list"
                :key="item.name"
                :label="item.name"
                :value="item.name"
              >
                <span class="opt-name">{{ item.name }}</span>
                <span class="opt-meta">
                  {{ item.knowledge_points }} 知识点 · {{ item.documents }} 资料
                </span>
              </el-option>
              <el-option label="＋ 新建科目" value="__add__" />
            </el-select>
          </template>
          <span class="topbar-hint">一句话说清目标，剩下的小助手来跑</span>
        </div>
      </header>

      <el-dialog v-model="addVisible" title="新建科目" width="380px">
        <el-input
          v-model="newSubject"
          placeholder="例如：概率论 / 操作系统 / 考研英语"
          maxlength="20"
          show-word-limit
          @keyup.enter="onAddSubject"
        />
        <p class="dialog-tip">
          新增科目后可在顶部切换；计划、练习、错题、知识库会按该科目归集。
        </p>
        <template #footer>
          <el-button @click="addVisible = false">取消</el-button>
          <el-button type="primary" :loading="adding" :disabled="!newSubject.trim()" @click="onAddSubject">
            添加
          </el-button>
        </template>
      </el-dialog>

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

.subject-text {
  font-size: 12px;
  color: $text-placeholder;
}

.subject-select {
  width: 168px;
}

.opt-name {
  float: left;
}

.opt-meta {
  float: right;
  font-size: 11px;
  color: $text-placeholder;
  margin-left: 12px;
}

.dialog-tip {
  margin: 10px 0 0;
  font-size: 12px;
  color: $text-placeholder;
  line-height: 1.7;
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
