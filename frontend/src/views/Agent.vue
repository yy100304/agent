<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { ChatLineRound, Promotion, Refresh } from '@element-plus/icons-vue'

import {
  getRuns,
  getTeam,
  getWorkflows,
  streamChat,
  type AgentCard,
  type RunSummary,
  type TraceEvent,
  type WorkflowSpec,
} from '@/api/agent'
import { renderMarkdown } from '@/utils/markdown'

// ===== 会话 =====

const SESSION_KEY = 'studyflow_agent_session'

function sessionId(): string {
  let sid = localStorage.getItem(SESSION_KEY)
  if (!sid) {
    sid = `s_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`
    localStorage.setItem(SESSION_KEY, sid)
  }
  return sid
}

// ===== 状态 =====

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  streaming?: boolean
  status?: string
}

interface TraceItem {
  key: number
  event: TraceEvent
}

const messages = reactive<ChatMessage[]>([])
const traceItems = reactive<TraceItem[]>([])
const input = ref('')
const sending = ref(false)
const traceKey = ref(0)
const activeAgent = ref('')          // 当前正在执行的子 Agent
const dispatchLabel = ref('')        // 本次调度标签
const lastLatency = ref<number | null>(null)

const team = ref<AgentCard[]>([])
const workflows = ref<WorkflowSpec[]>([])
const runs = ref<RunSummary[]>([])
const sideTab = ref<'trace' | 'history'>('trace')

const chatBody = ref<HTMLDivElement | null>(null)

const labelColors: Record<string, 'primary' | 'success' | 'warning' | 'danger' | 'info'> = {
  knowledge_explain: 'primary',
  quiz_coaching: 'warning',
  notes_organizing: 'success',
  multi_task: 'danger',
  non_learning: 'info',
}

const canSend = computed(() => !!input.value.trim() && !sending.value)

// ===== 聊天 =====

async function onSend() {
  const text = input.value.trim()
  if (!text || sending.value) return

  input.value = ''
  sending.value = true
  messages.push({ role: 'user', content: text })
  traceItems.length = 0
  dispatchLabel.value = ''
  activeAgent.value = ''
  lastLatency.value = null
  sideTab.value = 'trace'

  const placeholder: ChatMessage = {
    role: 'assistant',
    content: '',
    streaming: true,
    status: '正在识别任务类型…',
  }
  messages.push(placeholder)
  await scrollToBottom()

  try {
    await streamChat(text, sessionId(), (event) => onEvent(event, placeholder))
  } catch (e: any) {
    placeholder.streaming = false
    placeholder.content = '> ⚠️ 连接中断，请稍后重试。'
    ElMessage.error(e?.message || '请求失败')
  } finally {
    placeholder.streaming = false
    sending.value = false
    loadRuns()
    await scrollToBottom()
  }
}

function onEvent(event: TraceEvent, placeholder: ChatMessage) {
  // delta 为展示层流式分块，不进入执行轨迹面板（避免刷屏）
  if (event.type !== 'delta') {
    traceKey.value += 1
    traceItems.push({ key: traceKey.value, event })
  }

  switch (event.type) {
    case 'status':
      placeholder.status = event.text || ''
      break
    case 'dispatch':
      dispatchLabel.value = event.label_name || ''
      placeholder.status = `任务识别为「${event.label_name}」，正在调度对应智能体…`
      break
    case 'agent_start':
      activeAgent.value = event.agent || ''
      placeholder.status = `${event.name} 正在执行（第 ${event.attempt} 轮）…`
      break
    case 'tool':
      placeholder.status = `正在检索学习知识库…`
      break
    case 'validate':
      placeholder.status = event.passed
        ? '输出验证通过，正在生成结果…'
        : '验证未通过，正在自我修正…'
      break
    case 'retry':
      placeholder.status = `自我循环：第 ${event.attempt} 轮修正中…`
      break
    case 'delta':
      // 流式输出：逐块追加并即时重渲染，形成打字机效果
      placeholder.content += event.text || ''
      placeholder.status = ''
      // 流式期间直接贴底（不用平滑动画，避免频繁抖动）
      nextTick(() => {
        if (chatBody.value) chatBody.value.scrollTop = chatBody.value.scrollHeight
      })
      break
    case 'final':
      // 完整内容幂等确认（delta 已累积完成，此处不重复追加）
      placeholder.content = event.content || placeholder.content
      placeholder.status = ''
      scrollToBottom()
      break
    case 'done':
      lastLatency.value = event.latency_ms ?? null
      break
    case 'error':
      placeholder.content = `> ⚠️ ${event.message || '执行出错'}`
      placeholder.status = ''
      break
  }
}

async function scrollToBottom() {
  await nextTick()
  chatBody.value?.scrollTo({ top: chatBody.value.scrollHeight, behavior: 'smooth' })
}

function newSession() {
  localStorage.removeItem(SESSION_KEY)
  messages.length = 0
  traceItems.length = 0
  dispatchLabel.value = ''
  activeAgent.value = ''
  lastLatency.value = null
  sessionId()
  ElMessage.success('已开启新会话')
}

// ===== 渲染辅助 =====

function md(content: string): string {
  return renderMarkdown(content)
}

function traceIcon(ev: TraceEvent): string {
  switch (ev.type) {
    case 'dispatch': return '🧭'
    case 'agent_start': return '🤖'
    case 'tool': return '🔍'
    case 'validate': return ev.passed ? '✅' : '❌'
    case 'retry': return '🔁'
    case 'plan': return '🗂️'
    case 'done': return '🏁'
    default: return '·'
  }
}

function traceText(ev: TraceEvent): string {
  switch (ev.type) {
    case 'status': return ev.text || ''
    case 'dispatch':
      return `调度判定：${ev.label_name}（${ev.channel === 'llm' ? 'LLM 意图识别' : '规则路由'}）`
    case 'agent_start':
      return `${ev.name} 开始执行（第 ${ev.attempt} 轮）`
    case 'tool': return `工具调用 ${ev.tool}：${ev.summary || ''}`
    case 'validate': {
      const score = ev.score != null ? `，质量分 ${Math.round(ev.score * 100)}` : ''
      return `结果验证：${ev.passed ? '通过' : '未通过'}${score}`
    }
    case 'retry': return `自我循环修正：${(ev.feedback || '').slice(0, 40)}`
    case 'plan':
      return `拆解为 ${ev.tasks?.length || 0} 个子任务：${(ev.tasks || []).map(t => t.title).join(' → ')}`
    case 'done': return `执行完成，耗时 ${ev.latency_ms}ms`
    default: return ev.type
  }
}

// ===== 加载 =====

async function loadRuns() {
  try {
    runs.value = await getRuns(15)
  } catch { /* 静默 */ }
}

onMounted(async () => {
  try {
    team.value = await getTeam()
    workflows.value = await getWorkflows()
  } catch { /* 静默 */ }
  loadRuns()
})
</script>

<template>
  <div class="agent-page">
    <!-- ===== 左：对话区 ===== -->
    <section class="chat card">
      <header class="chat-head">
        <div class="chat-title">
          <el-icon class="title-icon"><ChatLineRound /></el-icon>
          <div>
            <div class="title-text">智学多智能体平台</div>
            <div class="title-sub">
              意图识别 → 动态调度 → 工具检索 → 执行 → 验证 → 自我修正
            </div>
          </div>
        </div>
        <div class="chat-actions">
          <el-tag v-if="lastLatency != null" size="small" effect="plain" type="info">
            上次耗时 {{ lastLatency }}ms
          </el-tag>
          <el-button size="small" :icon="Refresh" @click="newSession">新会话</el-button>
        </div>
      </header>

      <div ref="chatBody" class="chat-body">
        <div v-if="messages.length === 0" class="chat-empty">
          <div class="empty-icon">🤖</div>
          <h3>和多智能体团队聊聊吧</h3>
          <div class="empty-tips">
            <button class="tip-chip" @click="input = '什么是割点？'">什么是割点？</button>
            <button class="tip-chip" @click="input = '帮我出5道图论题'">帮我出 5 道图论题</button>
            <button class="tip-chip" @click="input = '讲解一下树，然后出2道练习题'">
              讲解树 + 出 2 道题（多任务）
            </button>
            <button class="tip-chip" @click="input = '整理笔记：树的定义是无回路连通图，n个顶点有n-1条边，任意两点路径唯一'">
              整理一段笔记
            </button>
          </div>
        </div>

        <div
          v-for="(msg, i) in messages"
          :key="i"
          class="msg-row"
          :class="msg.role === 'user' ? 'mine' : 'bot'"
        >
          <div class="avatar" :class="msg.role">
            {{ msg.role === 'user' ? '我' : '🤖' }}
          </div>
          <div class="bubble-wrap">
            <div v-if="msg.role === 'assistant'" class="bubble md-content" v-html="md(msg.content)" />
            <div v-else class="bubble user-bubble">{{ msg.content }}</div>
            <div v-if="msg.streaming && msg.status" class="streaming-bar">
              <span class="dot-flashing" />
              <span>{{ msg.status }}</span>
            </div>
          </div>
        </div>
      </div>

      <footer class="chat-input">
        <el-input
          v-model="input"
          type="textarea"
          :rows="2"
          resize="none"
          placeholder="输入学习问题，多智能体团队将自动协作处理…"
          :disabled="sending"
          @keydown.enter.exact.prevent="onSend"
        />
        <el-button
          type="primary"
          class="send-btn"
          :icon="Promotion"
          :loading="sending"
          :disabled="!canSend"
          @click="onSend"
        >
          发送
        </el-button>
      </footer>
    </section>

    <!-- ===== 右：平台面板 ===== -->
    <aside class="side">
      <!-- Agent 团队 -->
      <section class="card side-card">
        <h3 class="side-title">Agent 团队（{{ team.length + 1 }}）</h3>
        <div class="team-grid">
          <div class="team-member dispatcher">
            <span class="member-icon">🧭</span>
            <span class="member-name">主调度 Agent</span>
            <span class="member-desc">意图识别 · 动态路由</span>
          </div>
          <div
            v-for="a in team"
            :key="a.id"
            class="team-member"
            :class="{ active: activeAgent === a.id }"
          >
            <span class="member-icon">{{ a.banner.replace(/^>\s*/, '').slice(0, 2) }}</span>
            <span class="member-name">{{ a.name.replace(' Agent', '') }}</span>
            <span class="member-desc">{{ a.tools.length ? '工具：知识库检索' : a.description }}</span>
          </div>
        </div>
      </section>

      <!-- 轨迹 / 历史 -->
      <section class="card side-card grow">
        <div class="side-tabs">
          <button
            class="side-tab"
            :class="{ on: sideTab === 'trace' }"
            @click="sideTab = 'trace'"
          >
            执行轨迹
          </button>
          <button
            class="side-tab"
            :class="{ on: sideTab === 'history' }"
            @click="sideTab = 'history'"
          >
            运行记录
          </button>
        </div>

        <div v-show="sideTab === 'trace'" class="trace-list">
          <div v-if="!traceItems.length" class="trace-empty">
            发送消息后，这里实时展示多智能体协作过程
          </div>
          <div v-for="item in traceItems" :key="item.key" class="trace-item">
            <span class="trace-ico">{{ traceIcon(item.event) }}</span>
            <span class="trace-text">{{ traceText(item.event) }}</span>
          </div>
        </div>

        <div v-show="sideTab === 'history'" class="run-list">
          <div v-if="!runs.length" class="trace-empty">暂无运行记录</div>
          <div v-for="r in runs" :key="r.id" class="run-item">
            <div class="run-top">
              <el-tag size="small" :type="labelColors[r.label] || 'info'" effect="light">
                {{ r.label_name }}
              </el-tag>
              <span class="run-latency">{{ r.latency_ms }}ms</span>
              <span class="run-pass" :class="r.passed ? 'ok' : 'bad'">
                {{ r.passed ? '验证通过' : '未通过' }}
              </span>
            </div>
            <div class="run-msg">{{ r.message }}</div>
            <div class="run-meta">
              Agents: {{ r.agent_ids.join(' → ') || '-' }} · Self-Loop {{ r.attempts }} 轮
            </div>
          </div>
        </div>
      </section>

      <!-- 工作流定义 -->
      <section class="card side-card">
        <h3 class="side-title">动态路由 · 工作流</h3>
        <div v-for="wf in workflows" :key="wf.label" class="wf-row">
          <el-tag size="small" :type="labelColors[wf.label] || 'info'" effect="plain">
            {{ wf.label_name }}
          </el-tag>
          <span class="wf-nodes">
            {{ wf.nodes.map(n => n.name.replace(' Agent', '')).join(' → ') }}
            <span v-if="wf.self_loop" class="wf-loop">↻ 自循环+验证</span>
          </span>
        </div>
      </section>
    </aside>
  </div>
</template>

<style scoped lang="scss">
@use '@/styles/variables.scss' as *;

.agent-page {
  display: grid;
  grid-template-columns: 1fr 350px;
  gap: $gap-md;
  height: calc(100vh - 64px - 2 * #{$gap-lg});
  min-height: 560px;

  @media (max-width: 1100px) {
    grid-template-columns: 1fr;
    height: auto;
  }
}

.card {
  background: $bg-card;
  border-radius: $radius-md;
  box-shadow: $shadow-sm;
  border: 1px solid $border-light;
}

// ===== 对话区 =====
.chat {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.chat-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  border-bottom: 1px solid $border-light;
}

.chat-title {
  display: flex;
  align-items: center;
  gap: 12px;
}

.title-icon {
  font-size: 24px;
  color: $primary;
}

.title-text {
  font-size: 16px;
  font-weight: 600;
}

.title-sub {
  font-size: 12px;
  color: $text-placeholder;
  margin-top: 2px;
}

.chat-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.chat-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.chat-empty {
  margin: auto;
  text-align: center;

  .empty-icon {
    font-size: 44px;
    margin-bottom: 8px;
  }

  h3 {
    margin: 0 0 16px;
    font-size: 17px;
  }
}

.empty-tips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
  max-width: 420px;
  margin: 0 auto;
}

.tip-chip {
  padding: 7px 14px;
  border-radius: 999px;
  border: 1px solid $border-base;
  background: $bg-muted;
  color: $text-regular;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s ease;

  &:hover {
    border-color: $primary;
    color: $primary;
    background: $primary-soft;
  }
}

.msg-row {
  display: flex;
  gap: 10px;
  max-width: 86%;

  &.mine {
    align-self: flex-end;
    flex-direction: row-reverse;
  }
}

.avatar {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  background: $bg-muted;
  color: $text-secondary;

  &.mine {
    background: linear-gradient(135deg, #4f7cf7, #7c5cff);
    color: #fff;
    font-weight: 600;
  }
}

.bubble-wrap {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.bubble {
  padding: 12px 16px;
  border-radius: 14px;
  font-size: 14px;
  line-height: 1.7;
}

.user-bubble {
  background: linear-gradient(135deg, #4f7cf7, #6c7cff);
  color: #fff;
  border-top-right-radius: 4px;
  white-space: pre-wrap;
}

.md-content {
  background: $bg-muted;
  border-top-left-radius: 4px;
  width: 100%;

  :deep(h2), :deep(h3), :deep(h4) {
    margin: 12px 0 6px;
    font-size: 14.5px;
    font-weight: 600;
    color: $text-primary;

    &:first-child {
      margin-top: 0;
    }
  }

  :deep(p) {
    margin: 6px 0;
  }

  :deep(blockquote) {
    margin: 8px 0;
    padding: 8px 12px;
    border-left: 3px solid $primary;
    background: $primary-soft;
    border-radius: 6px;
    color: $text-regular;
  }

  :deep(ul) {
    margin: 6px 0;
    padding-left: 20px;

    li {
      margin: 3px 0;
    }
  }

  :deep(hr) {
    border: none;
    border-top: 1px dashed $border-base;
    margin: 12px 0;
  }

  :deep(code) {
    background: rgba(79, 124, 247, 0.12);
    padding: 1px 6px;
    border-radius: 4px;
    font-size: 13px;
  }

  :deep(strong) {
    color: $text-primary;
  }
}

.streaming-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: $primary;
  padding: 0 4px;
}

.dot-flashing {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: $primary;
  animation: flash 1s ease infinite alternate;
}

@keyframes flash {
  from { opacity: 0.25; }
  to { opacity: 1; }
}

.chat-input {
  display: flex;
  gap: 12px;
  align-items: flex-end;
  padding: 14px 20px;
  border-top: 1px solid $border-light;
}

.send-btn {
  height: 54px;
  padding: 0 22px;
  font-size: 14px;
}

// ===== 右侧面板 =====
.side {
  display: flex;
  flex-direction: column;
  gap: $gap-md;
  min-height: 0;
  overflow-y: auto;

  @media (max-width: 1100px) {
    overflow: visible;
  }
}

.side-card {
  padding: 16px;
}

.side-card.grow {
  flex: 1;
  min-height: 260px;
  display: flex;
  flex-direction: column;
}

.side-title {
  margin: 0 0 12px;
  font-size: 14px;
  font-weight: 600;
}

.team-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.team-member {
  border: 1px solid $border-light;
  border-radius: 12px;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 3px;
  transition: all 0.2s ease;
  background: $bg-card;

  &.dispatcher {
    grid-column: 1 / -1;
    flex-direction: row;
    align-items: center;
    gap: 10px;
    background: linear-gradient(135deg, rgba(79, 124, 247, 0.08), rgba(124, 92, 255, 0.08));

    .member-desc {
      margin-left: auto;
    }
  }

  &.active {
    border-color: $primary;
    background: $primary-soft;
    box-shadow: 0 0 0 2px rgba(79, 124, 247, 0.15);
  }
}

.member-icon {
  font-size: 16px;
}

.member-name {
  font-size: 12.5px;
  font-weight: 600;
  color: $text-primary;
}

.member-desc {
  font-size: 11px;
  color: $text-placeholder;
}

.side-tabs {
  display: flex;
  gap: 6px;
  margin-bottom: 12px;
}

.side-tab {
  flex: 1;
  padding: 7px 0;
  border-radius: 9px;
  border: 1px solid $border-light;
  background: $bg-card;
  font-size: 12.5px;
  color: $text-secondary;
  cursor: pointer;

  &.on {
    background: $primary-soft;
    color: $primary;
    border-color: rgba(79, 124, 247, 0.35);
    font-weight: 600;
  }
}

.trace-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.trace-empty {
  margin: auto;
  text-align: center;
  font-size: 12.5px;
  color: $text-placeholder;
  padding: 30px 10px;
  line-height: 1.8;
}

.trace-item {
  display: flex;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 8px;
  font-size: 12.5px;
  line-height: 1.5;
  color: $text-regular;
  background: $bg-muted;
  animation: fadeIn 0.25s ease;

  .trace-ico {
    flex-shrink: 0;
  }
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(3px); }
  to { opacity: 1; transform: none; }
}

.run-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.run-item {
  border: 1px solid $border-light;
  border-radius: 10px;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.run-top {
  display: flex;
  align-items: center;
  gap: 8px;
}

.run-latency {
  font-size: 11px;
  color: $text-placeholder;
}

.run-pass {
  font-size: 11px;
  margin-left: auto;

  &.ok { color: $success; }
  &.bad { color: $danger; }
}

.run-msg {
  font-size: 12.5px;
  color: $text-primary;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.run-meta {
  font-size: 11px;
  color: $text-placeholder;
}

.wf-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 0;
  font-size: 12.5px;
  color: $text-regular;
}

.wf-nodes {
  min-width: 0;
}

.wf-loop {
  color: $warning;
  font-size: 11px;
}
</style>
