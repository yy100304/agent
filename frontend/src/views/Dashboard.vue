<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import { Aim, AlarmClock, CircleCheck, MagicStick, TrendCharts } from '@element-plus/icons-vue'

import {
  completeTask,
  getDashboard,
  type DashboardSummary,
} from '@/api/dashboard'
import SubjectBadge from '@/components/SubjectBadge.vue'
import { useSubjectStore } from '@/stores/subject'

const router = useRouter()
const subjectStore = useSubjectStore()
const loading = ref(false)
const completing = ref<number | null>(null)
const data = ref<DashboardSummary | null>(null)

const studyTimeEl = ref<HTMLDivElement | null>(null)
const accuracyEl = ref<HTMLDivElement | null>(null)
let studyTimeChart: echarts.ECharts | null = null
let accuracyChart: echarts.ECharts | null = null

const taskDone = computed(
  () => data.value?.stats.today_task_completed ?? 0
)
const taskTotal = computed(() => data.value?.stats.today_task_total ?? 0)
const taskProgress = computed(() =>
  taskTotal.value ? Math.round((taskDone.value / taskTotal.value) * 100) : 0
)

function fmtMinutes(min: number): string {
  if (min <= 0) return '0min'
  const h = Math.floor(min / 60)
  const m = min % 60
  if (h <= 0) return `${m}min`
  if (m === 0) return `${h}h`
  return `${h}h ${m}min`
}

async function onToggleTask(taskId: number) {
  completing.value = taskId
  try {
    await completeTask(taskId)
    ElMessage.success('任务完成，已记入今日学习时长')
    await loadDashboard()
  } catch (e) {
    console.error(e)
  } finally {
    completing.value = null
  }
}

function goPractice() {
  router.push('/practice')
}

function goPlan() {
  router.push('/study-plan')
}

function renderCharts() {
  if (!data.value) return
  if (studyTimeEl.value && !studyTimeChart) studyTimeChart = echarts.init(studyTimeEl.value)
  if (accuracyEl.value && !accuracyChart) accuracyChart = echarts.init(accuracyEl.value)

  if (studyTimeChart) {
    studyTimeChart.setOption({
      grid: { left: 36, right: 12, top: 16, bottom: 28 },
      tooltip: { trigger: 'axis' },
      xAxis: {
        type: 'category',
        data: data.value.study_time_trend.map((p) => p.date.slice(5)),
        axisLine: { lineStyle: { color: '#cbd5e1' } },
        axisLabel: { color: '#64748b' },
      },
      yAxis: {
        type: 'value',
        splitLine: { lineStyle: { color: '#eef2f7' } },
        axisLabel: { color: '#64748b' },
      },
      series: [
        {
          type: 'line',
          smooth: true,
          symbol: 'circle',
          symbolSize: 6,
          data: data.value.study_time_trend.map((p) => p.value),
          lineStyle: { width: 3, color: '#4f7cf7' },
          itemStyle: { color: '#4f7cf7' },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(79, 124, 247, 0.28)' },
              { offset: 1, color: 'rgba(79, 124, 247, 0.02)' },
            ]),
          },
        },
      ],
    })
  }

  if (accuracyChart) {
    accuracyChart.setOption({
      grid: { left: 40, right: 12, top: 16, bottom: 28 },
      tooltip: {
        trigger: 'axis',
        // 数据已是 0~100 的百分比，此处直接补 % 即可（不可再乘 100）
        valueFormatter: (v: number | string) => `${v}%`,
      },
      xAxis: {
        type: 'category',
        data: data.value.accuracy_trend.map((p) => p.date.slice(5)),
        axisLine: { lineStyle: { color: '#cbd5e1' } },
        axisLabel: { color: '#64748b' },
      },
      yAxis: {
        type: 'value',
        min: 0,
        max: 100,
        splitLine: { lineStyle: { color: '#eef2f7' } },
        axisLabel: { color: '#64748b', formatter: '{value}%' },
      },
      series: [
        {
          type: 'line',
          smooth: true,
          symbol: 'circle',
          symbolSize: 6,
          // 无答题的日期用 connectNulls 平滑连接，避免出现断裂
          connectNulls: true,
          data: data.value.accuracy_trend.map((p) =>
            p.value === null ? null : Math.round(p.value * 100)
          ),
          lineStyle: { width: 3, color: '#7c5cff' },
          itemStyle: { color: '#7c5cff' },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(124, 92, 255, 0.25)' },
              { offset: 1, color: 'rgba(124, 92, 255, 0.02)' },
            ]),
          },
        },
      ],
    })
  }
}

async function loadDashboard() {
  loading.value = true
  try {
    data.value = await getDashboard(subjectStore.current || undefined)
    await new Promise((r) => requestAnimationFrame(r))
    renderCharts()
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

function onResize() {
  studyTimeChart?.resize()
  accuracyChart?.resize()
}

watch(
  () => subjectStore.current,
  () => loadDashboard(),
)

onMounted(() => {
  loadDashboard()
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  studyTimeChart?.dispose()
  accuracyChart?.dispose()
})
</script>

<template>
  <div class="dashboard" v-loading="loading">
    <!-- ===== 欢迎区 ===== -->
    <section class="hero card">
      <div class="hero-text">
        <div class="greeting-row">
          <div class="greeting">{{ data?.greeting || '欢迎回来' }}</div>
          <SubjectBadge />
        </div>
        <div class="hero-sub">
          <span class="day-badge">今天是你的学习第 {{ data?.study_day_count ?? 1 }} 天</span>
          <template v-if="data?.exam">
            <span class="divider-dot">·</span>
            <span class="exam-badge">
              距离{{ data.exam.subject }}考试还有
              <b>{{ data.exam.days_left }}</b> 天
            </span>
          </template>
          <template v-else>
            <span class="divider-dot">·</span>
            <span class="hero-plain">今天也要加油完成学习目标。</span>
          </template>
        </div>
      </div>
    </section>

    <div class="grid">
      <!-- ===== 今日学习任务（核心区） ===== -->
      <section class="tasks card">
        <div class="section-head">
          <h3>今日学习任务</h3>
          <span class="progress-text">{{ taskDone }}/{{ taskTotal }} · {{ taskProgress }}%</span>
        </div>
        <el-progress
          :percentage="taskProgress"
          :stroke-width="8"
          :show-text="false"
          class="task-progress"
        />
        <div v-if="taskTotal === 0" class="empty-tasks">
          今天暂时没有任务。去和小助手聊聊，让它帮你排一份学习计划吧。
          <el-button type="primary" link @click="router.push('/agent')">找 Agent 定计划</el-button>
        </div>
        <ul class="task-list">
          <li
            v-for="t in data?.today_tasks || []"
            :key="t.id"
            class="task-item"
            :class="{ done: t.completed }"
          >
            <el-icon
              class="task-check"
              :class="{ done: t.completed }"
              @click="!t.completed && onToggleTask(t.id)"
            >
              <CircleCheck />
            </el-icon>
            <div class="task-body">
              <div class="task-title">{{ t.title }}</div>
              <div class="task-meta">
                <el-tag v-if="t.knowledge_point_name" size="small" effect="plain" round>
                  {{ t.knowledge_point_name }}
                </el-tag>
                <span class="task-minutes">{{ t.estimated_minutes }}min</span>
              </div>
            </div>
            <span v-if="t.completed" class="done-label">已完成</span>
          </li>
        </ul>
      </section>

      <!-- ===== 学习数据概览 ===== -->
      <section class="overview card">
        <div class="section-head">
          <h3>学习状态</h3>
        </div>
        <div class="overview-grid">
          <div class="ov-item">
            <div class="ov-icon time"><el-icon><AlarmClock /></el-icon></div>
            <div class="ov-value">{{ fmtMinutes(data?.stats.today_minutes ?? 0) }}</div>
            <div class="ov-label">今日学习时间</div>
          </div>
          <div class="ov-item">
            <div class="ov-icon rate"><el-icon><TrendCharts /></el-icon></div>
            <div class="ov-value">{{ taskProgress }}%</div>
            <div class="ov-label">今日任务完成率</div>
          </div>
          <div class="ov-item">
            <div class="ov-icon aim"><el-icon><Aim /></el-icon></div>
            <div class="ov-value">
              {{ data?.stats.recent_accuracy != null ? Math.round(data.stats.recent_accuracy * 100) + '%' : '—' }}
            </div>
            <div class="ov-label">最近正确率</div>
          </div>
          <div class="ov-item wide">
            <div class="ov-label">当前薄弱知识点</div>
            <div class="weak-tags">
              <el-tag
                v-for="w in data?.stats.weak_points || []"
                :key="w"
                type="danger"
                effect="light"
                round
              >
                {{ w }}
              </el-tag>
              <span v-if="!(data?.stats.weak_points || []).length" class="weak-empty">
                暂无明显薄弱点，继续保持
              </span>
            </div>
          </div>
        </div>
      </section>
    </div>

    <!-- ===== 学习趋势 ===== -->
    <section class="charts">
      <div class="card chart-card">
        <div class="section-head">
          <h3>最近 7 天学习时间</h3>
          <span class="chart-sub">分钟</span>
        </div>
        <div ref="studyTimeEl" class="chart-canvas" />
      </div>
      <div class="card chart-card">
        <div class="section-head">
          <h3>最近 7 天正确率</h3>
          <span class="chart-sub">按答题日期</span>
        </div>
        <div ref="accuracyEl" class="chart-canvas" />
      </div>
    </section>

    <!-- ===== Agent 建议 ===== -->
    <section class="suggestion card">
      <div class="suggestion-head">
        <div class="suggestion-icon"><el-icon><MagicStick /></el-icon></div>
        <h3>Agent 学习建议</h3>
      </div>
      <p class="suggestion-text">{{ data?.agent_suggestion?.text }}</p>
      <div class="suggestion-actions">
        <el-button type="primary" @click="goPractice">开始练习</el-button>
        <el-button @click="goPlan">查看计划</el-button>
      </div>
    </section>
  </div>
</template>

<style scoped lang="scss">
@use '@/styles/variables.scss' as *;

.dashboard {
  display: flex;
  flex-direction: column;
  gap: $gap-lg;
  max-width: 1200px;
  margin: 0 auto;
}

.card {
  background: $bg-card;
  border-radius: $radius-md;
  box-shadow: $shadow-sm;
  border: 1px solid $border-light;
  padding: $gap-lg;
}

.hero {
  background: linear-gradient(135deg, rgba(79, 124, 247, 0.08), rgba(124, 92, 255, 0.08));
}

.greeting-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}

.greeting {
  font-size: 22px;
  font-weight: 600;
  color: $text-primary;
}

.hero-sub {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  color: $text-secondary;
  font-size: 14px;
}

.day-badge,
.exam-badge {
  padding: 4px 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.75);
  border: 1px solid $border-light;
}

.exam-badge b {
  color: $primary;
  font-size: 16px;
  margin: 0 2px;
}

.divider-dot {
  color: $text-placeholder;
}

.hero-plain {
  color: $text-secondary;
}

.grid {
  display: grid;
  grid-template-columns: 3fr 2fr;
  gap: $gap-md;

  @media (max-width: 1024px) {
    grid-template-columns: 1fr;
  }
}

.section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 12px;

  h3 {
    margin: 0;
    font-size: 15px;
    font-weight: 600;
    color: $text-primary;
  }
}

.progress-text {
  font-size: 13px;
  color: $text-secondary;
}

.task-progress {
  margin-bottom: 14px;
}

.empty-tasks {
  color: $text-secondary;
  font-size: 13px;
  padding: 12px 0;
  line-height: 1.8;
}

.task-list {
  display: flex;
  flex-direction: column;
}

.task-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 8px;
  border-radius: 12px;
  transition: background 0.15s ease;

  &:hover {
    background: $bg-muted;
  }

  &.done {
    opacity: 0.62;
  }
}

.task-check {
  font-size: 22px;
  color: #cbd5e1;
  cursor: pointer;
  flex-shrink: 0;
  transition: color 0.15s ease;

  &:hover {
    color: $primary;
  }

  &.done {
    color: $success;
    cursor: default;
  }
}

.task-body {
  flex: 1;
  min-width: 0;
}

.task-title {
  font-size: 14px;
  color: $text-primary;
  margin-bottom: 4px;

  .done & {
    text-decoration: line-through;
    color: $text-secondary;
  }
}

.task-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.task-minutes {
  font-size: 12px;
  color: $text-placeholder;
}

.done-label {
  font-size: 12px;
  color: $success;
}

.overview-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: $gap-md;
}

.ov-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px;
  border-radius: 12px;
  background: $bg-muted;
}

.ov-icon {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 17px;

  &.time {
    background: rgba(79, 124, 247, 0.12);
    color: $primary;
  }
  &.rate {
    background: rgba(22, 163, 74, 0.12);
    color: $success;
  }
  &.aim {
    background: rgba(245, 158, 11, 0.14);
    color: $warning;
  }
}

.ov-value {
  font-size: 20px;
  font-weight: 600;
  color: $text-primary;
}

.ov-label {
  font-size: 12px;
  color: $text-secondary;
}

.ov-item.wide {
  grid-column: 1 / -1;
}

.weak-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 4px;
}

.weak-empty {
  font-size: 13px;
  color: $text-placeholder;
}

.charts {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: $gap-md;

  @media (max-width: 1024px) {
    grid-template-columns: 1fr;
  }
}

.chart-card {
  display: flex;
  flex-direction: column;
}

.chart-sub {
  font-size: 12px;
  color: $text-placeholder;
}

.chart-canvas {
  width: 100%;
  height: 220px;
}

.suggestion {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.suggestion-head {
  display: flex;
  align-items: center;
  gap: 10px;

  h3 {
    margin: 0;
    font-size: 15px;
    font-weight: 600;
  }
}

.suggestion-icon {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  background: linear-gradient(135deg, #4f7cf7, #7c5cff);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 17px;
}

.suggestion-text {
  margin: 0;
  color: $text-regular;
  line-height: 1.7;
  background: $bg-muted;
  border-radius: 12px;
  padding: 14px 16px;
}

.suggestion-actions {
  display: flex;
  gap: 12px;
}
</style>
