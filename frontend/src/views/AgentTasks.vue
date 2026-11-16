<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'

import SubjectBadge from '@/components/SubjectBadge.vue'
import {
  cancelAgentTask,
  getAgentTask,
  listAgentTasks,
  resumeAgentTask,
  type AgentTaskBrief,
  type AgentTaskDetail,
  type AgentTaskResult,
  type SelfLoopRound,
  type SelfLoopSummary,
  type Snapshot,
} from '@/api/agentTasks'

// ===== 常量 =====

const STATUS_META: Record<
  string,
  { text: string; type: 'success' | 'warning' | 'danger' | 'info' | 'primary' }
> = {
  pending: { text: '排队中', type: 'info' },
  running: { text: '执行中', type: 'primary' },
  need_input: { text: '待补充信息', type: 'warning' },
  success: { text: '成功', type: 'success' },
  partial: { text: '部分完成', type: 'warning' },
  failed: { text: '失败', type: 'danger' },
  skipped: { text: '已跳过', type: 'info' },
  cancelled: { text: '已取消', type: 'info' },
}

const STOP_REASON: Record<string, string> = {
  passed: '一次通过（无需修正）',
  not_repairable: '不可自动修复',
  still_failing: '修正后仍未通过',
  max_rounds: '达到最大修正轮次',
  manual_check: '需人工确认',
  cancelled: '已取消',
}

const ACTION_KIND: Record<string, string> = {
  rerun: '重跑 Agent',
  confirm: '先确认写入',
}

const SNAPSHOT_FIELDS: { key: keyof Snapshot; label: string }[] = [
  { key: 'requested_count', label: '要求数量' },
  { key: 'actual_count', label: '实际数量' },
  { key: 'task_count', label: '任务数' },
  { key: 'plan_id', label: '计划 ID' },
  { key: 'found', label: '检索命中' },
  { key: 'sufficient', label: '学情充分' },
]

const STEP_STATUS: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
  success: 'success',
  partial: 'warning',
  failed: 'danger',
  skipped: 'info',
  running: 'warning',
}

// ===== 状态 =====

const router = useRouter()
const acting = ref(false)
const loadingList = ref(false)
const loadingDetail = ref(false)
const tasks = ref<AgentTaskBrief[]>([])
const detail = ref<AgentTaskDetail | null>(null)
const activeId = ref('')
const showLogs = ref(false)

const result = computed<AgentTaskResult | null>(() => {
  const value = detail.value?.result
  return value && typeof value === 'object' ? (value as AgentTaskResult) : null
})

const selfLoop = computed<SelfLoopSummary | null>(() => {
  return result.value?.final_result?.self_loop ?? null
})

const summaryText = computed(() => {
  const payload = result.value
  return payload?.final_result?.summary || payload?.summary || ''
})

const executedAgents = computed(() => result.value?.executed_agents || [])

// 任务识别出的科目（来自主控意图解析，便于按科目归档查看）
const taskSubject = computed(() => {
  const intent = result.value?.parsed_intent as Record<string, unknown> | undefined
  const value = intent?.subject
  return typeof value === 'string' && value.trim() ? value.trim() : ''
})

const pendingQuestions = computed<string[]>(() => {
  const pending = result.value?.final_result?.pending_questions
  return Array.isArray(pending) ? pending : []
})

const annotations = computed(() => {
  const payload = result.value
  const final = payload?.final_result
  if (!final) return [] as { kind: 'issue' | 'warning'; text: string }[]
  return [
    ...(final.issues || []).map((text) => ({ kind: 'issue' as const, text })),
    ...(final.warnings || []).map((text) => ({ kind: 'warning' as const, text })),
  ]
})

// ===== 渲染辅助 =====

function statusMeta(status?: string) {
  return STATUS_META[status || ''] || { text: status || '未知', type: 'info' as const }
}

function stopReasonText(reason?: string) {
  if (!reason) return '—'
  return STOP_REASON[reason] || reason
}

function snapshotValue(snap: Snapshot | undefined, key: keyof Snapshot): string {
  const value = snap?.[key]
  if (value === undefined || value === null || value === '') return '—'
  if (typeof value === 'boolean') return value ? '是' : '否'
  return String(value)
}

/** 只展示有意义的"调整前 → 调整后"对比行 */
function diffRows(round: SelfLoopRound) {
  return SNAPSHOT_FIELDS.map((field) => {
    const before = snapshotValue(round.before, field.key)
    const after = snapshotValue(round.after, field.key)
    return { label: field.label, before, after, changed: before !== after }
  }).filter((row) => row.before !== '—' || row.after !== '—')
}

function validationText(round: SelfLoopRound): string {
  const val = round.validation
  if (!val) return '未校验'
  const counts =
    val.passed_count != null && val.check_count != null
      ? `（${val.passed_count}/${val.check_count} 项）`
      : ''
  return val.passed ? `校验通过${counts}` : `校验未通过${counts}`
}

function formatElapsed(seconds?: number | null): string {
  if (seconds === null || seconds === undefined) return ''
  return seconds >= 1 ? `${seconds.toFixed(2)}s` : `${Math.round(seconds * 1000)}ms`
}

function taskTime(value?: string | null): string {
  if (!value) return ''
  return value.replace('T', ' ').slice(0, 19)
}

// ===== 数据加载 =====

async function loadTasks(autoSelect = false) {
  loadingList.value = true
  try {
    tasks.value = await listAgentTasks(20, 0)
    if (autoSelect || (!activeId.value && tasks.value.length)) {
      const first = tasks.value[0]
      if (first) await selectTask(first.task_id)
    }
  } catch {
    /* 拦截器已提示 */
  } finally {
    loadingList.value = false
  }
}

async function selectTask(taskId: string) {
  if (!taskId) return
  activeId.value = taskId
  loadingDetail.value = true
  try {
    detail.value = await getAgentTask(taskId)
  } catch {
    detail.value = null
  } finally {
    loadingDetail.value = false
  }
}

function goAgent() {
  router.push({ name: 'Agent' })
}

async function onCancel() {
  if (!detail.value || acting.value) return
  acting.value = true
  try {
    const res = await cancelAgentTask(detail.value.task_id)
    ElMessage.success(res.detail || '已请求取消')
    await loadTasks()
    await selectTask(detail.value.task_id)
  } catch {
    /* 拦截器已提示 */
  } finally {
    acting.value = false
  }
}

async function onResume() {
  if (!detail.value || acting.value) return
  try {
    await ElMessageBox.confirm(
      '恢复会从中断处继续：已完成的步骤不会重跑，写入型步骤会先确认是否已落库。',
      '恢复执行',
      { type: 'info', confirmButtonText: '继续执行', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  acting.value = true
  try {
    const res = await resumeAgentTask(detail.value.task_id)
    ElMessage.success(`已恢复：${statusMeta(res.task_status).text}`)
    await loadTasks()
    await selectTask(detail.value.task_id)
  } catch {
    /* 拦截器已提示 */
  } finally {
    acting.value = false
  }
}

onMounted(() => loadTasks(true))
</script>

<template>
  <div class="tasks-page">
    <!-- ===== 定位说明：这里只做执行档案，不发起对话 ===== -->
    <section class="card intro-card">
      <div class="intro-main">
        <div class="intro-title">
          <h2 class="card-title">执行档案 · 可追溯 / 可恢复</h2>
          <SubjectBadge />
        </div>
        <p class="card-sub">
          这里不发起对话：记录主控 Agent 每次任务的执行计划、步骤耗时、结果校验与自我修正轮次
          （失败类型、修正前后数量、复验结论）；中断的任务支持「取消」与「安全恢复」。
          发起新任务请到
          <button class="link" @click="goAgent">和小助手对话</button>。
        </p>
      </div>
      <div class="intro-actions">
        <el-button :icon="Refresh" :loading="loadingList" @click="loadTasks()">刷新</el-button>
        <el-button type="primary" @click="goAgent">找小助手发起任务</el-button>
      </div>
    </section>

    <div class="grid">
      <!-- ===== 任务列表 ===== -->
      <section class="card list-card">
        <header class="list-head">
          <h3>历史任务</h3>
          <el-button text size="small" :icon="Refresh" :loading="loadingList" @click="loadTasks()">
            刷新
          </el-button>
        </header>

        <div v-loading="loadingList" class="task-list">
          <div v-if="!tasks.length" class="empty-tip">
            还没有任务记录，先在上方提交一句学习需求吧。
          </div>
          <button
            v-for="item in tasks"
            :key="item.task_id"
            class="task-item"
            :class="{ active: item.task_id === activeId }"
            @click="selectTask(item.task_id)"
          >
            <div class="task-top">
              <el-tag size="small" effect="light" :type="statusMeta(item.status).type">
                {{ statusMeta(item.status).text }}
              </el-tag>
              <span class="task-time">{{ taskTime(item.created_at) }}</span>
            </div>
            <div class="task-title">{{ item.title }}</div>
          </button>
        </div>
      </section>

      <!-- ===== 任务详情 ===== -->
      <section class="card detail-card">
        <div v-if="!detail" class="empty-tip big">
          选择左侧任务查看执行步骤、校验结果与自我修正过程。
        </div>

        <div v-else v-loading="loadingDetail" class="detail-body">
          <header class="detail-head">
            <div class="detail-title">
              <el-tag effect="dark" :type="statusMeta(detail.status).type">
                {{ statusMeta(detail.status).text }}
              </el-tag>
              <el-tag v-if="taskSubject" size="small" effect="plain" type="primary">
                {{ taskSubject }}
              </el-tag>
              <h3>{{ detail.title }}</h3>
            </div>
            <div class="detail-meta">
              <span v-if="result?.execution_time != null">耗时 {{ formatElapsed(result.execution_time) }}</span>
              <span>{{ taskTime(detail.created_at) }}</span>
              <span class="mono">{{ detail.task_id.slice(0, 8) }}</span>
            </div>
            <div class="detail-actions">
              <el-button
                v-if="['running', 'pending'].includes(detail.status)"
                size="small"
                :loading="acting"
                @click="onCancel"
              >
                取消执行
              </el-button>
              <el-button
                v-if="['failed', 'partial', 'cancelled', 'running'].includes(detail.status)"
                size="small"
                type="primary"
                plain
                :loading="acting"
                @click="onResume"
              >
                安全恢复
              </el-button>
            </div>
          </header>

          <p v-if="detail.error" class="error-line">{{ detail.error }}</p>

          <!-- 结论摘要 -->
          <section v-if="summaryText" class="block">
            <h4 class="block-title">执行结论</h4>
            <pre class="summary-text">{{ summaryText }}</pre>
          </section>

          <!-- 待补充信息（need_input） -->
          <section v-if="pendingQuestions.length" class="block">
            <h4 class="block-title">需要补充的信息</h4>
            <ul class="issue-list">
              <li v-for="item in pendingQuestions" :key="item" class="warning">{{ item }}</li>
            </ul>
          </section>

          <div v-if="executedAgents.length" class="agent-line">
            <span class="agent-label">参与 Agent</span>
            <el-tag
              v-for="name in executedAgents"
              :key="name"
              size="small"
              effect="plain"
              class="agent-tag"
            >
              {{ name }}
            </el-tag>
          </div>

          <!-- ===== Self-Loop ===== -->
          <section class="block">
            <div class="block-head">
              <h4 class="block-title">自我修正（Self-Loop）</h4>
              <div v-if="selfLoop" class="loop-chips">
                <el-tag size="small" effect="plain" type="primary">
                  修正 {{ selfLoop.repair_count }} / {{ selfLoop.max_repair_rounds }} 轮
                </el-tag>
                <el-tag size="small" effect="plain" type="info">
                  {{ stopReasonText(selfLoop.stopped_reason) }}
                </el-tag>
              </div>
            </div>

            <div v-if="!selfLoop" class="loop-pass neutral">
              <span class="loop-pass-icon">ℹ️</span>
              <div>
                <strong>本次没有执行修正流程</strong>
                <p>任务未产生可校验产物（例如等待补充信息或已取消），因此没有修正轮次。</p>
              </div>
            </div>

            <div
              v-else-if="!selfLoop.rounds.length && selfLoop.repair_count === 0"
              class="loop-pass"
            >
              <span class="loop-pass-icon">✅</span>
              <div>
                <strong>本任务未触发自我修正</strong>
                <p>{{ stopReasonText(selfLoop.stopped_reason || 'passed') }}</p>
              </div>
            </div>

            <div v-else class="round-list">
              <article v-for="round in selfLoop.rounds" :key="round.round" class="round-card">
                <header class="round-head">
                  <span class="round-no">第 {{ round.round }} 轮</span>
                  <el-tag size="small" effect="light" type="warning">
                    {{ round.failure_label || round.failure_type }}
                  </el-tag>
                  <span class="round-target">{{ round.target }}</span>
                  <span
                    class="round-status"
                    :class="round.validation?.passed ? 'ok' : 'bad'"
                  >
                    {{ validationText(round) }}
                  </span>
                  <span v-if="round.elapsed != null" class="round-elapsed">
                    {{ formatElapsed(round.elapsed) }}
                  </span>
                </header>

                <p v-if="round.reason" class="round-reason">{{ round.reason }}</p>

                <div v-if="diffRows(round).length" class="diff-table">
                  <div class="diff-row diff-header">
                    <span>指标</span><span>修正前</span><span>修正后</span>
                  </div>
                  <div
                    v-for="row in diffRows(round)"
                    :key="row.label"
                    class="diff-row"
                    :class="{ changed: row.changed }"
                  >
                    <span>{{ row.label }}</span>
                    <span>{{ row.before }}</span>
                    <span>{{ row.after }}</span>
                  </div>
                </div>

                <div class="round-actions">
                  <div v-for="(action, index) in round.actions" :key="index" class="action-row">
                    <el-tag
                      size="small"
                      effect="plain"
                      :type="action.kind === 'confirm' ? 'danger' : 'primary'"
                    >
                      {{ ACTION_KIND[action.kind] || action.kind }}
                    </el-tag>
                    <span class="action-agent">{{ action.agent }}</span>
                    <span class="action-reason">{{ action.reason }}</span>
                  </div>
                </div>

                <ul v-if="round.validation?.issues?.length" class="issue-list">
                  <li v-for="issue in round.validation.issues" :key="issue">{{ issue }}</li>
                </ul>
              </article>
            </div>
          </section>

          <!-- 问题与告警 -->
          <section v-if="annotations.length" class="block">
            <h4 class="block-title">问题与告警</h4>
            <ul class="issue-list">
              <li
                v-for="(item, index) in annotations"
                :key="index"
                :class="item.kind === 'issue' ? 'issue' : 'warning'"
              >
                {{ item.text }}
              </li>
            </ul>
          </section>

          <!-- 执行步骤 -->
          <section v-if="detail.steps.length" class="block">
            <h4 class="block-title">执行步骤</h4>
            <div class="step-list">
              <div v-for="step in detail.steps" :key="step.order" class="step-row">
                <span class="step-no">{{ step.order }}</span>
                <span class="step-agent">{{ step.agent }}</span>
                <el-tag size="small" effect="light" :type="STEP_STATUS[step.status] || 'info'">
                  {{ step.status }}
                </el-tag>
                <span class="step-time">
                  {{ taskTime(step.started_at).slice(11) || '—' }}
                  <template v-if="step.finished_at">→ {{ taskTime(step.finished_at).slice(11) }}</template>
                </span>
                <span v-if="step.error" class="step-error">{{ step.error }}</span>
              </div>
            </div>
          </section>

          <!-- 校验记录 -->
          <section v-if="detail.evaluations.length" class="block">
            <h4 class="block-title">校验记录（落库）</h4>
            <div class="eval-list">
              <div v-for="(item, index) in detail.evaluations" :key="index" class="eval-row">
                <span class="eval-round">第 {{ item.round }} 轮</span>
                <span class="eval-target">{{ item.target }}</span>
                <el-tag size="small" effect="light" :type="item.passed ? 'success' : 'danger'">
                  {{ item.passed ? '通过' : '未通过' }}
                </el-tag>
                <span v-if="item.score != null" class="eval-score">
                  得分 {{ Math.round((item.score || 0) * 100) }}
                </span>
              </div>
            </div>
          </section>

          <!-- 日志 -->
          <section v-if="detail.logs.length" class="block">
            <div class="block-head">
              <h4 class="block-title">执行日志（{{ detail.logs.length }}）</h4>
              <el-button text size="small" @click="showLogs = !showLogs">
                {{ showLogs ? '收起' : '展开' }}
              </el-button>
            </div>
            <div v-show="showLogs" class="log-list">
              <div v-for="(log, index) in detail.logs" :key="index" class="log-row">
                <span class="log-level" :class="log.level">{{ log.level }}</span>
                <span class="log-agent">{{ log.agent }}</span>
                <span class="log-msg">{{ log.message }}</span>
              </div>
            </div>
          </section>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped lang="scss">
@use '@/styles/variables.scss' as *;

.tasks-page {
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

.intro-card {
  padding: $gap-md $gap-lg;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: $gap-lg;

  @media (max-width: 900px) {
    flex-direction: column;
    align-items: flex-start;
  }
}

.intro-main {
  min-width: 0;
}

.intro-title {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.card-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: $text-primary;
}

.card-sub {
  margin: 6px 0 0;
  font-size: 12px;
  color: $text-placeholder;
  line-height: 1.7;
}

.intro-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.link {
  border: none;
  background: none;
  padding: 0;
  color: $primary;
  font-size: 12px;
  cursor: pointer;
  text-decoration: underline;
}

.detail-actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
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

.list-card {
  padding: $gap-sm;
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 320px);
  min-height: 320px;
}

.list-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 4px $gap-xs;

  h3 {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
  }
}

.task-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.empty-tip {
  padding: $gap-lg;
  text-align: center;
  font-size: 12.5px;
  color: $text-placeholder;
  line-height: 1.8;

  &.big {
    padding: 80px $gap-lg;
  }
}

.task-item {
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

.task-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.task-time {
  font-size: 11px;
  color: $text-placeholder;
}

.task-title {
  font-size: 12.5px;
  color: $text-primary;
  line-height: 1.5;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
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
  flex-wrap: wrap;
}

.detail-title {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;

  h3 {
    margin: 0;
    font-size: 15px;
    font-weight: 600;
    color: $text-primary;
  }
}

.detail-meta {
  display: flex;
  gap: $gap-sm;
  font-size: 12px;
  color: $text-placeholder;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}

.error-line {
  margin: 0;
  padding: 8px 12px;
  border-radius: 8px;
  background: rgba(239, 68, 68, 0.08);
  color: $danger;
  font-size: 12.5px;
}

.block {
  border-top: 1px dashed $border-base;
  padding-top: $gap-sm;
}

.block-title {
  margin: 0 0 $gap-xs;
  font-size: 13.5px;
  font-weight: 600;
  color: $text-primary;
}

.block-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: $gap-sm;
}

.loop-chips {
  display: flex;
  gap: 6px;
}

.summary-text {
  margin: 0;
  padding: 10px 12px;
  background: $bg-muted;
  border-radius: 10px;
  font-size: 12.5px;
  line-height: 1.7;
  color: $text-regular;
  white-space: pre-wrap;
  font-family: inherit;
}

.agent-line {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.agent-label {
  font-size: 12px;
  color: $text-placeholder;
}

.agent-tag {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}

.loop-pass {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(22, 163, 74, 0.08);
  border: 1px solid rgba(22, 163, 74, 0.2);

  strong {
    font-size: 13px;
    color: $success;
  }

  p {
    margin: 4px 0 0;
    font-size: 12px;
    color: $text-secondary;
  }
}

.loop-pass.neutral {
  background: $bg-muted;
  border-color: $border-base;

  strong {
    color: $text-primary;
  }
}

.loop-pass-icon {
  font-size: 16px;
}

.round-list {
  display: flex;
  flex-direction: column;
  gap: $gap-sm;
}

.round-card {
  border: 1px solid $border-base;
  border-radius: 12px;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: linear-gradient(180deg, rgba(79, 124, 247, 0.04), transparent 60%);
}

.round-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.round-no {
  font-size: 12.5px;
  font-weight: 600;
  color: $primary;
}

.round-target {
  font-size: 11.5px;
  color: $text-placeholder;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}

.round-status {
  font-size: 11.5px;
  margin-left: auto;

  &.ok { color: $success; }
  &.bad { color: $danger; }
}

.round-elapsed {
  font-size: 11px;
  color: $text-placeholder;
}

.round-reason {
  margin: 0;
  font-size: 12.5px;
  color: $text-regular;
  line-height: 1.6;
}

.diff-table {
  border: 1px solid $border-light;
  border-radius: 10px;
  overflow: hidden;
  font-size: 12px;
}

.diff-row {
  display: grid;
  grid-template-columns: 1.1fr 1fr 1fr;
  padding: 6px 10px;
  color: $text-secondary;
  border-bottom: 1px solid $border-light;

  &:last-child {
    border-bottom: none;
  }

  &.diff-header {
    background: $bg-muted;
    color: $text-placeholder;
    font-size: 11.5px;
  }

  &.changed {
    background: rgba(79, 124, 247, 0.06);
    color: $text-primary;
    font-weight: 500;
  }
}

.round-actions {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.action-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: $text-regular;
}

.action-agent {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  color: $text-secondary;
}

.action-reason {
  color: $text-placeholder;
  min-width: 0;
}

.issue-list {
  margin: 0;
  padding-left: 18px;
  font-size: 12px;
  color: $text-regular;
  line-height: 1.7;

  li.issue { color: $danger; }
  li.warning { color: $warning; }
}

.step-list {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.step-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: $text-regular;
  padding: 5px 8px;
  border-radius: 8px;
  background: $bg-muted;
}

.step-no {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: $primary-soft;
  color: $primary;
  font-size: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.step-agent {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}

.step-time {
  margin-left: auto;
  color: $text-placeholder;
  font-size: 11px;
}

.step-error {
  color: $danger;
  font-size: 11.5px;
}

.eval-list {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.eval-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: $text-regular;
}

.eval-round {
  color: $primary;
  font-weight: 600;
}

.eval-target {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  color: $text-secondary;
}

.eval-score {
  margin-left: auto;
  color: $text-placeholder;
  font-size: 11.5px;
}

.log-list {
  max-height: 260px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 3px;
  border: 1px solid $border-light;
  border-radius: 10px;
  padding: 8px;
  background: #0f172a08;
}

.log-row {
  display: flex;
  gap: 8px;
  font-size: 11.5px;
  line-height: 1.5;
  color: $text-regular;
}

.log-level {
  width: 52px;
  flex-shrink: 0;
  text-transform: uppercase;
  font-size: 10.5px;
  color: $text-placeholder;

  &.warning { color: $warning; }
  &.error { color: $danger; }
  &.info { color: $primary; }
}

.log-agent {
  width: 110px;
  flex-shrink: 0;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  color: $text-secondary;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.log-msg {
  min-width: 0;
  word-break: break-all;
}
</style>
