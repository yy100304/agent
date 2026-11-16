<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Calendar, Delete, Edit, Plus, Refresh } from '@element-plus/icons-vue'

import {
  completePlanTask,
  createPlanTask,
  createStudyPlan,
  deletePlanTask,
  deleteStudyPlan,
  getStudyPlanDetail,
  getStudyPlans,
  updatePlanTask,
  updateStudyPlan,
  type PlanTask,
  type StudyPlanBrief,
  type StudyPlanDetail,
} from '@/api/plans'
import SubjectBadge from '@/components/SubjectBadge.vue'
import { useSubjectStore } from '@/stores/subject'

const router = useRouter()
const subjectStore = useSubjectStore()

const plans = ref<StudyPlanBrief[]>([])
const detail = ref<StudyPlanDetail | null>(null)
const activeId = ref<number | null>(null)
const loadingList = ref(false)
const loadingDetail = ref(false)
const completing = ref<number | null>(null)

// ===== 自己写计划：计划表单 / 任务表单 =====
const planDialog = ref(false)
const planSaving = ref(false)
const planForm = reactive({
  id: null as number | null,
  title: '',
  subject: '',
  exam_date: '',
  daily_minutes: 60,
  description: '',
})

const taskDialog = ref(false)
const taskSaving = ref(false)
const taskForm = reactive({
  id: null as number | null,
  title: '',
  description: '',
  scheduled_date: '',
  estimated_minutes: 30,
})

const WEEK = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']

const planDialogTitle = computed(() => (planForm.id ? '编辑计划' : '新建学习计划'))
const taskDialogTitle = computed(() => (taskForm.id ? '编辑任务' : '添加任务'))

function todayStr(): string {
  const now = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}

function resetPlanForm() {
  planForm.id = null
  planForm.title = ''
  planForm.subject = subjectStore.current || ''
  planForm.exam_date = ''
  planForm.daily_minutes = 60
  planForm.description = ''
}

function openCreatePlan() {
  resetPlanForm()
  planDialog.value = true
}

function openEditPlan() {
  if (!detail.value) return
  planForm.id = detail.value.id
  planForm.title = detail.value.title
  planForm.subject = detail.value.subject
  planForm.exam_date = detail.value.exam_date || ''
  planForm.daily_minutes = detail.value.daily_minutes
  planForm.description = detail.value.description || ''
  planDialog.value = true
}

async function submitPlan() {
  const title = planForm.title.trim()
  if (!title) {
    ElMessage.warning('先给计划起个名字吧')
    return
  }
  planSaving.value = true
  try {
    const payload = {
      title,
      subject: planForm.subject.trim() || subjectStore.current || '通用',
      exam_date: planForm.exam_date || null,
      daily_minutes: planForm.daily_minutes,
      description: planForm.description.trim(),
    }
    if (planForm.id) {
      await updateStudyPlan(planForm.id, payload)
      ElMessage.success('计划已更新')
      planDialog.value = false
      await loadPlans()
    } else {
      const created = await createStudyPlan(payload)
      ElMessage.success('计划建好了，接下来自己往里加任务')
      planDialog.value = false
      // 新计划的科目和当前科目不同时，跟着切过去，否则列表里看不到它
      if (created.subject && subjectStore.current && created.subject !== subjectStore.current) {
        subjectStore.setCurrent(created.subject)
      } else {
        await loadPlans(false)
      }
    }
  } catch {
    /* 拦截器已提示 */
  } finally {
    planSaving.value = false
  }
}

function openCreateTask(scheduledDate?: string) {
  if (!activeId.value) return
  taskForm.id = null
  taskForm.title = ''
  taskForm.description = ''
  taskForm.scheduled_date = scheduledDate || todayStr()
  taskForm.estimated_minutes = 30
  taskDialog.value = true
}

function openEditTask(task: PlanTask) {
  taskForm.id = task.id
  taskForm.title = task.title
  taskForm.description = task.description || ''
  taskForm.scheduled_date = task.scheduled_date
  taskForm.estimated_minutes = task.estimated_minutes
  taskDialog.value = true
}

async function submitTask() {
  const title = taskForm.title.trim()
  if (!title) {
    ElMessage.warning('任务内容不能为空')
    return
  }
  if (!activeId.value) return
  taskSaving.value = true
  try {
    const payload = {
      title,
      description: taskForm.description.trim() || null,
      scheduled_date: taskForm.scheduled_date || todayStr(),
      estimated_minutes: taskForm.estimated_minutes,
    }
    if (taskForm.id) {
      await updatePlanTask(taskForm.id, payload)
      ElMessage.success('任务已更新')
    } else {
      await createPlanTask(activeId.value, payload)
      ElMessage.success('任务已加到计划里')
    }
    taskDialog.value = false
    await selectPlan(activeId.value)
  } catch {
    /* 拦截器已提示 */
  } finally {
    taskSaving.value = false
  }
}

async function onRemoveTask(task: PlanTask) {
  try {
    await ElMessageBox.confirm(`删除任务「${task.title}」？`, '删除任务', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await deletePlanTask(task.id)
    ElMessage.success('任务已删除')
    if (activeId.value) await selectPlan(activeId.value)
  } catch {
    /* 拦截器已提示 */
  }
}

async function onRemovePlan() {
  if (!detail.value) return
  try {
    await ElMessageBox.confirm(`删除计划「${detail.value.title}」及其所有任务？`, '删除计划', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await deleteStudyPlan(detail.value.id)
    ElMessage.success('计划已删除')
    activeId.value = null
    detail.value = null
    await loadPlans(false)
  } catch {
    /* 拦截器已提示 */
  }
}

// 只展示当前科目的计划（未选科目时展示全部）
const visiblePlans = computed(() => {
  const current = subjectStore.current
  if (!current) return plans.value
  return plans.value.filter((plan) => plan.subject === current)
})

const groups = computed(() => {
  const tasks = detail.value?.tasks || []
  const map = new Map<string, PlanTask[]>()
  for (const task of tasks) {
    const key = task.scheduled_date
    if (!map.has(key)) map.set(key, [])
    map.get(key)!.push(task)
  }
  return [...map.entries()]
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([date, items]) => ({
      date,
      label: dateLabel(date),
      weekday: weekdayLabel(date),
      minutes: items.reduce((sum, t) => sum + (t.estimated_minutes || 0), 0),
      done: items.filter((t) => t.completed).length,
      items,
    }))
})

const adjustNotes = computed(() => {
  const raw = detail.value?.adjustment_log
  if (!raw) return [] as string[]
  try {
    const log = JSON.parse(raw)
    const notes: string[] = []
    if (log?.source) notes.push(`生成来源：${log.source}`)
    if (Array.isArray(log?.weak_points) && log.weak_points.length) {
      notes.push(`优先安排薄弱知识点：${log.weak_points.join('、')}`)
    }
    if (Array.isArray(log?.focus_points) && log.focus_points.length) {
      notes.push(`重点覆盖：${log.focus_points.join('、')}`)
    }
    if (Array.isArray(log?.self_loop)) {
      for (const entry of log.self_loop) {
        const parts: string[] = []
        for (const item of entry?.adjustments || []) {
          parts.push(`${item.date} 由 ${item.before} 分钟压到 ${item.after} 分钟`)
        }
        notes.push(
          `自我修正：${entry?.reason || '按约束调整'}${parts.length ? `（${parts.join('；')}）` : ''}`,
        )
      }
    }
    return notes
  } catch {
    return []
  }
})

function dateLabel(value: string): string {
  const [, month, day] = value.split('-')
  return `${Number(month)} 月 ${Number(day)} 日`
}

function weekdayLabel(value: string): string {
  const date = new Date(`${value}T00:00:00`)
  return Number.isNaN(date.getTime()) ? '' : WEEK[(date.getDay() + 6) % 7]
}

function countdownText(plan: StudyPlanBrief | StudyPlanDetail | null): string {
  if (!plan?.exam_date) return '无考试日期'
  const days = Math.round(
    (new Date(`${plan.exam_date}T00:00:00`).getTime() - Date.now()) / 86400000,
  )
  if (days > 1) return `距考试 ${days} 天`
  if (days === 1) return '明天考试'
  if (days === 0) return '今天考试'
  return '考试日期已过'
}

function countdownType(plan: StudyPlanBrief | StudyPlanDetail | null) {
  if (!plan?.exam_date) return 'info' as const
  const days = Math.round(
    (new Date(`${plan.exam_date}T00:00:00`).getTime() - Date.now()) / 86400000,
  )
  if (days < 0) return 'info' as const
  if (days <= 3) return 'danger' as const
  if (days <= 7) return 'warning' as const
  return 'success' as const
}

async function loadPlans(keepActive = true) {
  loadingList.value = true
  try {
    plans.value = await getStudyPlans()
    const candidates = visiblePlans.value
    const exists = candidates.some((p) => p.id === activeId.value)
    if (!keepActive || !exists) activeId.value = candidates[0]?.id ?? null
    if (activeId.value) await selectPlan(activeId.value as number)
    else detail.value = null
  } catch {
    /* 拦截器已提示 */
  } finally {
    loadingList.value = false
  }
}

// 切换科目：重新挑选属于该科目的计划
watch(
  () => subjectStore.current,
  () => loadPlans(false),
)

async function selectPlan(planId: number) {
  activeId.value = planId
  loadingDetail.value = true
  try {
    detail.value = await getStudyPlanDetail(planId)
  } catch {
    detail.value = null
  } finally {
    loadingDetail.value = false
  }
}

async function onComplete(task: PlanTask) {
  if (task.completed || completing.value) return
  completing.value = task.id
  try {
    await completePlanTask(task.id)
    ElMessage.success('已完成，学习时长已记录')
    if (activeId.value) await selectPlan(activeId.value)
  } catch {
    /* 拦截器已提示 */
  } finally {
    completing.value = null
  }
}

function goAgent() {
  router.push({ name: 'Agent', query: { ask: '帮我制定复习计划' } })
}

onMounted(() => loadPlans(false))
</script>

<template>
  <div class="plan-page">
    <div class="grid">
      <!-- ===== 计划列表 ===== -->
      <aside class="card plans-card">
        <header class="card-head">
          <h3>我的计划</h3>
          <div class="head-actions">
            <el-button size="small" type="primary" :icon="Plus" @click="openCreatePlan">
              新建
            </el-button>
            <el-button text size="small" :icon="Refresh" :loading="loadingList" @click="loadPlans()">
              刷新
            </el-button>
          </div>
        </header>

        <div class="plan-subject">
          <SubjectBadge />
        </div>

        <div v-loading="loadingList" class="plan-list">
          <div v-if="!visiblePlans.length" class="empty">
            <p class="empty-title">{{ subjectStore.current ? `「${subjectStore.current}」还没有学习计划` : '还没有学习计划' }}</p>
            <p class="empty-sub">自己定考试日期和每天想学多久，再逐天写任务，比让 AI 猜更贴合你的节奏。</p>
            <el-button type="primary" size="small" :icon="Plus" @click="openCreatePlan">
              自己写一份计划
            </el-button>
            <p class="empty-hint">
              懒得写？
              <el-link type="primary" :underline="false" @click="goAgent">让小助手起草一份</el-link>
            </p>
          </div>

          <button
            v-for="plan in visiblePlans"
            :key="plan.id"
            class="plan-item"
            :class="{ active: plan.id === activeId }"
            @click="selectPlan(plan.id)"
          >
            <div class="plan-top">
              <span class="plan-title">{{ plan.title }}</span>
              <el-tag size="small" effect="light" :type="countdownType(plan)">
                {{ countdownText(plan) }}
              </el-tag>
            </div>
            <div class="plan-meta">
              <span>{{ plan.subject }}</span>
              <span>每日 {{ plan.daily_minutes }} 分钟</span>
              <span v-if="plan.exam_date">考试 {{ plan.exam_date }}</span>
            </div>
          </button>
        </div>
      </aside>

      <!-- ===== 计划详情 ===== -->
      <section class="card detail-card">
        <div v-if="!detail" class="empty big">
          <p class="empty-title">选择左侧计划查看每日任务</p>
          <p class="empty-sub">还没有计划？自己写一份就好：标题、考试日期、每天多少分钟，然后逐天加任务。</p>
          <el-button type="primary" size="small" :icon="Plus" @click="openCreatePlan">
            自己写一份计划
          </el-button>
          <p class="empty-hint">
            想让小助手先起草也可以：
            <el-link type="primary" :underline="false" @click="goAgent">去和小助手说</el-link>
          </p>
        </div>

        <div v-else v-loading="loadingDetail" class="detail-body">
          <header class="detail-head">
            <div>
              <h2 class="detail-title">{{ detail.title }}</h2>
              <div class="detail-meta">
                <SubjectBadge />
                <el-tag size="small" effect="plain">{{ detail.subject }}</el-tag>
                <span v-if="detail.exam_date">考试日期 {{ detail.exam_date }}</span>
                <span>每日预算 {{ detail.daily_minutes }} 分钟</span>
                <span>共 {{ detail.total_tasks }} 个任务</span>
              </div>
            </div>
            <div class="detail-actions">
              <el-tag effect="dark" :type="countdownType(detail)">{{ countdownText(detail) }}</el-tag>
              <el-button size="small" :icon="Edit" @click="openEditPlan">编辑计划</el-button>
              <el-button size="small" type="danger" plain :icon="Delete" @click="onRemovePlan">
                删除
              </el-button>
            </div>
          </header>

          <section class="plan-content" :class="{ blank: !detail.description }">
            <header class="content-head">
              <h4>计划内容</h4>
              <el-button text size="small" :icon="Edit" @click="openEditPlan">编辑</el-button>
            </header>
            <p v-if="detail.description" class="content-text">{{ detail.description }}</p>
            <p v-else class="content-blank">
              这部分由你自己写：要复习的范围、目标、注意事项……点右上角「编辑」补上。
            </p>
          </section>

          <div class="progress-row">
            <div class="progress-bar">
              <div class="progress-inner" :style="{ width: `${Math.round(detail.progress * 100)}%` }" />
            </div>
            <span class="progress-text">
              已完成 {{ detail.completed_tasks }}/{{ detail.total_tasks }}（{{
                Math.round(detail.progress * 100)
              }}%）
            </span>
          </div>

          <section v-if="adjustNotes.length" class="notes">
            <h4>安排说明</h4>
            <ul>
              <li v-for="note in adjustNotes" :key="note">{{ note }}</li>
            </ul>
          </section>

          <div v-if="!groups.length" class="empty">
            <p class="empty-title">这份计划还是空的</p>
            <p class="empty-sub">自己写第一条吧：想看什么、大概花多久，写完就能勾完成。</p>
            <el-button type="primary" size="small" :icon="Plus" @click="openCreateTask()">
              写第一条任务
            </el-button>
          </div>

          <div v-for="group in groups" :key="group.date" class="day-group">
            <header class="day-head">
              <span class="day-date"><el-icon><Calendar /></el-icon> {{ group.label }}</span>
              <span class="day-week">{{ group.weekday }}</span>
              <span class="day-minutes">{{ group.minutes }} 分钟</span>
              <span class="day-done">{{ group.done }}/{{ group.items.length }} 已完成</span>
              <el-button
                text
                size="small"
                :icon="Plus"
                class="day-add"
                @click="openCreateTask(group.date)"
              >
                加任务
              </el-button>
            </header>

            <div
              v-for="task in group.items"
              :key="task.id"
              class="task-row"
              :class="{ done: task.completed }"
            >
              <el-checkbox
                :model-value="task.completed"
                :disabled="task.completed || completing === task.id"
                @change="onComplete(task)"
              />
              <div class="task-main">
                <div class="task-title">{{ task.title }}</div>
                <div v-if="task.description" class="task-desc">{{ task.description }}</div>
              </div>
              <el-tag v-if="task.knowledge_point_name" size="small" effect="plain" type="info">
                {{ task.knowledge_point_name }}
              </el-tag>
              <span class="task-minutes">{{ task.estimated_minutes }}′</span>
              <span class="task-actions">
                <el-button text size="small" :icon="Edit" @click="openEditTask(task)" />
                <el-button
                  text
                  size="small"
                  type="danger"
                  :icon="Delete"
                  @click="onRemoveTask(task)"
                />
              </span>
            </div>
          </div>

          <el-button
            v-if="detail"
            class="add-task-btn"
            :icon="Plus"
            plain
            @click="openCreateTask()"
          >
            添加任务
          </el-button>
        </div>
      </section>
    </div>

    <!-- ===== 计划表单（自己写） ===== -->
    <el-dialog v-model="planDialog" :title="planDialogTitle" width="460px" destroy-on-close>
      <el-form label-width="84px" label-position="right">
        <el-form-item label="计划名称">
          <el-input v-model="planForm.title" placeholder="如：离散数学期末冲刺" maxlength="128" />
        </el-form-item>
        <el-form-item label="科目">
          <el-select
            v-model="planForm.subject"
            filterable
            allow-create
            default-first-option
            clearable
            placeholder="选科目或直接输入"
            style="width: 100%"
          >
            <el-option v-for="name in subjectStore.options" :key="name" :label="name" :value="name" />
          </el-select>
        </el-form-item>
        <el-form-item label="考试日期">
          <el-date-picker
            v-model="planForm.exam_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="不填就是长期计划"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="每日预算">
          <el-input-number v-model="planForm.daily_minutes" :min="10" :max="720" :step="10" />
          <span class="unit-hint">分钟 / 天</span>
        </el-form-item>
        <el-form-item label="计划内容">
          <el-input
            v-model="planForm.description"
            type="textarea"
            :rows="5"
            maxlength="5000"
            show-word-limit
            placeholder="自己写：复习范围、这次想达到什么目标、有什么要特别注意（留空也可以，之后再补）"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="planDialog = false">取消</el-button>
        <el-button type="primary" :loading="planSaving" @click="submitPlan">
          {{ planForm.id ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- ===== 任务表单（自己写） ===== -->
    <el-dialog v-model="taskDialog" :title="taskDialogTitle" width="500px" destroy-on-close>
      <el-form label-width="84px" label-position="right">
        <el-form-item label="做什么">
          <el-input
            v-model="taskForm.title"
            placeholder="如：看完第 3 章并做 10 道例题"
            maxlength="255"
          />
        </el-form-item>
        <el-form-item label="安排到">
          <el-date-picker
            v-model="taskForm.scheduled_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="哪天做"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="预计用时">
          <el-input-number v-model="taskForm.estimated_minutes" :min="5" :max="600" :step="5" />
          <span class="unit-hint">分钟</span>
        </el-form-item>
        <el-form-item label="备注">
          <el-input
            v-model="taskForm.description"
            type="textarea"
            :rows="3"
            maxlength="2000"
            placeholder="可选：页码、题号、要重点看的地方"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="taskDialog = false">取消</el-button>
        <el-button type="primary" :loading="taskSaving" @click="submitTask">
          {{ taskForm.id ? '保存' : '添加' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
@use '@/styles/variables.scss' as *;

.plan-page {
  display: flex;
  flex-direction: column;
  gap: $gap-md;
}

.card {
  background: $bg-card;
  border-radius: $radius-md;
  box-shadow: $shadow-sm;
  border: 1px solid $border-light;
}

.grid {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: $gap-md;
  align-items: start;

  @media (max-width: 1100px) {
    grid-template-columns: 1fr;
  }
}

.plans-card {
  padding: $gap-sm;
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: calc(100vh - 200px);
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 2px 4px;

  h3 {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
    color: $text-primary;
  }
}

.head-actions {
  display: flex;
  align-items: center;
  gap: 2px;
}

.plan-subject {
  padding: 0 4px 6px;
}

.plan-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  overflow-y: auto;
}

.plan-item {
  text-align: left;
  border: 1px solid $border-light;
  border-radius: 12px;
  background: $bg-card;
  padding: 10px 12px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 6px;
  transition: all 0.15s ease;

  &:hover {
    border-color: rgba(79, 124, 247, 0.35);
    background: $primary-soft;
  }

  &.active {
    border-color: $primary;
    background: $primary-soft;
    box-shadow: 0 0 0 2px rgba(79, 124, 247, 0.12);
  }
}

.plan-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.plan-title {
  font-size: 13px;
  font-weight: 600;
  color: $text-primary;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.plan-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 11.5px;
  color: $text-placeholder;
}

.empty {
  padding: $gap-lg $gap-md;
  text-align: center;

  &.big {
    padding: 70px $gap-lg;
  }
}

.empty-title {
  margin: 0 0 6px;
  font-size: 13.5px;
  font-weight: 600;
  color: $text-primary;
}

.empty-sub {
  margin: 0 0 12px;
  font-size: 12px;
  color: $text-placeholder;
  line-height: 1.7;
}

.empty-hint {
  margin: 10px 0 0;
  font-size: 11.5px;
  color: $text-placeholder;

  :deep(.el-link) {
    font-size: 11.5px;
    vertical-align: baseline;
  }
}

.unit-hint {
  margin-left: 8px;
  font-size: 12px;
  color: $text-placeholder;
}

.detail-card {
  padding: $gap-md $gap-lg $gap-lg;
  min-height: 320px;
}

.detail-body {
  display: flex;
  flex-direction: column;
  gap: $gap-md;
}

.detail-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: $gap-md;
}

.detail-title {
  margin: 0 0 8px;
  font-size: 16px;
  font-weight: 600;
  color: $text-primary;
}

.detail-meta {
  display: flex;
  align-items: center;
  gap: $gap-sm;
  flex-wrap: wrap;
  font-size: 12px;
  color: $text-placeholder;
}

.detail-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.progress-row {
  display: flex;
  align-items: center;
  gap: $gap-sm;
}

.progress-bar {
  flex: 1;
  height: 8px;
  border-radius: 999px;
  background: $bg-muted;
  overflow: hidden;
}

.progress-inner {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, $primary, #6ea8ff);
  transition: width 0.3s ease;
}

.progress-text {
  font-size: 12px;
  color: $text-secondary;
  white-space: nowrap;
}

.plan-content {
  border: 1px solid $border-light;
  border-radius: 10px;
  padding: 10px 12px;
  background: $bg-muted;

  &.blank {
    border-style: dashed;
  }
}

.content-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;

  h4 {
    margin: 0;
    font-size: 12.5px;
    color: $text-primary;
  }
}

.content-text {
  margin: 0;
  font-size: 12.5px;
  line-height: 1.8;
  color: $text-secondary;
  white-space: pre-wrap;
  word-break: break-word;
}

.content-blank {
  margin: 0;
  font-size: 12px;
  line-height: 1.7;
  color: $text-placeholder;
}

.notes {
  border: 1px dashed $border-base;
  border-radius: 10px;
  padding: 10px 12px;
  background: $bg-muted;

  h4 {
    margin: 0 0 6px;
    font-size: 12.5px;
    color: $text-primary;
  }

  ul {
    margin: 0;
    padding-left: 18px;
    font-size: 12px;
    color: $text-secondary;
    line-height: 1.7;
  }
}

.day-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.day-head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 2px;
  border-bottom: 1px dashed $border-light;
  font-size: 12px;
  color: $text-placeholder;
}

.day-date {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12.5px;
  font-weight: 600;
  color: $text-primary;
}

.day-week {
  color: $primary;
}

.day-minutes {
  margin-left: auto;
}

.day-add {
  padding: 0 4px;
  height: 22px;
}

.task-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 9px 10px;
  border: 1px solid $border-light;
  border-radius: 10px;
  background: $bg-card;

  &.done {
    background: $bg-muted;

    .task-title {
      color: $text-placeholder;
      text-decoration: line-through;
    }
  }

  &:hover .task-actions {
    opacity: 1;
  }
}

.task-actions {
  display: flex;
  align-items: center;
  gap: 0;
  margin-left: 2px;
  opacity: 0;
  transition: opacity 0.15s ease;

  :deep(.el-button + .el-button) {
    margin-left: 2px;
  }

  :deep(.el-button) {
    padding: 2px 4px;
    height: 22px;
  }
}

.task-main {
  flex: 1;
  min-width: 0;
}

.task-title {
  font-size: 12.5px;
  color: $text-primary;
  line-height: 1.6;
}

.task-desc {
  margin-top: 2px;
  font-size: 11.5px;
  color: $text-placeholder;
  line-height: 1.6;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.task-minutes {
  font-size: 11.5px;
  color: $text-secondary;
  white-space: nowrap;
  padding-top: 2px;
}

.add-task-btn {
  align-self: flex-start;
  border-style: dashed;
}
</style>
