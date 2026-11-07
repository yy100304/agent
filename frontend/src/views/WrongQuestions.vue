<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import {
  getWrongQuestions,
  markWrongMastered,
  practiceSimilar,
  type WrongQuestion,
  type WrongQuestionStats,
} from '@/api/wrongQuestions'
import { getKnowledgePoints, type KnowledgePoint } from '@/api/questions'
import { usePracticeStore } from '@/stores/practice'

const router = useRouter()
const practiceStore = usePracticeStore()

const loading = ref(false)
const items = ref<WrongQuestion[]>([])
const stats = ref<WrongQuestionStats>({ total: 0, unmastered: 0, reviewing: 0, mastered: 0 })
const knowledgePoints = ref<KnowledgePoint[]>([])

const filter = reactive({
  subject: 'all',
  knowledge_point_id: undefined as number | undefined,
  status: 'all',
  difficulty: 'all',
})

// 科目下拉项（从数据推导，保证与实际一致）
const subjectOptions = computed(() => {
  const set = new Set(knowledgePoints.value.map((k) => k.subject))
  return Array.from(set)
})

// 联动：选择科目后知识点下拉随之变化
const kpOptions = computed(() =>
  knowledgePoints.value.filter(
    (k) => filter.subject === 'all' || k.subject === filter.subject
  )
)

const statusText: Record<string, string> = {
  unmastered: '未掌握',
  reviewing: '复习中',
  mastered: '已掌握',
}
const statusTag: Record<string, 'danger' | 'warning' | 'success'> = {
  unmastered: 'danger',
  reviewing: 'warning',
  mastered: 'success',
}
const difficultyText: Record<string, string> = {
  easy: '简单',
  medium: '中等',
  hard: '困难',
}

async function load() {
  loading.value = true
  try {
    const res = await getWrongQuestions({
      subject: filter.subject,
      knowledge_point_id: filter.knowledge_point_id,
      status: filter.status,
      difficulty: filter.difficulty,
    })
    items.value = res.items
    stats.value = res.stats
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

function onSubjectChange() {
  filter.knowledge_point_id = undefined
  load()
}

function onFilterChange() {
  load()
}

// ===== 详情抽屉 =====
const drawerVisible = ref(false)
const current = ref<WrongQuestion | null>(null)

function openDetail(w: WrongQuestion) {
  current.value = w
  drawerVisible.value = true
}

// ===== 标记已掌握 =====
const mastering = ref<number | null>(null)

async function onMaster(w: WrongQuestion) {
  mastering.value = w.id
  try {
    const res = await markWrongMastered(w.id)
    ElMessage.success(res.message)
    drawerVisible.value = false
    await load()
  } catch (e) {
    console.error(e)
  } finally {
    mastering.value = null
  }
}

// ===== 重新练习 =====
const practicing = ref<number | null>(null)

async function onPractice(w: WrongQuestion) {
  practicing.value = w.id
  try {
    const questions = await practiceSimilar(w.id)
    if (!questions.length) {
      ElMessage.warning('未能生成类似题，请稍后再试')
      return
    }
    practiceStore.setPreset(
      questions,
      `错题重练 · ${w.knowledge_point_name}`
    )
    drawerVisible.value = false
    router.push('/practice')
  } catch (e) {
    console.error(e)
  } finally {
    practicing.value = null
  }
}

onMounted(async () => {
  load()
  try {
    knowledgePoints.value = await getKnowledgePoints()
  } catch (e) {
    console.error(e)
  }
})
</script>

<template>
  <div class="wrong-questions">
    <!-- ===== 头部统计 ===== -->
    <section class="head card">
      <div class="head-left">
        <h2 class="title">我的错题集</h2>
        <div class="stats">
          <span class="stat">共 <b>{{ stats.total }}</b> 道错题</span>
          <el-divider direction="vertical" />
          <span class="stat">未掌握：<b class="danger">{{ stats.unmastered }}</b></span>
          <span class="stat">复习中：<b class="warning">{{ stats.reviewing }}</b></span>
          <span class="stat">已掌握：<b class="success">{{ stats.mastered }}</b></span>
        </div>
      </div>
    </section>

    <!-- ===== 筛选栏 ===== -->
    <section class="filters card">
      <div class="filter-item">
        <span class="filter-label">科目</span>
        <el-select v-model="filter.subject" style="width: 140px" @change="onSubjectChange">
          <el-option label="全部" value="all" />
          <el-option v-for="s in subjectOptions" :key="s" :label="s" :value="s" />
        </el-select>
      </div>
      <div class="filter-item">
        <span class="filter-label">知识点</span>
        <el-select
          v-model="filter.knowledge_point_id"
          style="width: 140px"
          clearable
          placeholder="全部"
          @change="onFilterChange"
        >
          <el-option
            v-for="k in kpOptions"
            :key="k.id"
            :label="k.name"
            :value="k.id"
          />
        </el-select>
      </div>
      <div class="filter-item">
        <span class="filter-label">状态</span>
        <el-select v-model="filter.status" style="width: 120px" @change="onFilterChange">
          <el-option label="全部" value="all" />
          <el-option label="未掌握" value="unmastered" />
          <el-option label="复习中" value="reviewing" />
          <el-option label="已掌握" value="mastered" />
        </el-select>
      </div>
      <div class="filter-item">
        <span class="filter-label">难度</span>
        <el-select v-model="filter.difficulty" style="width: 120px" @change="onFilterChange">
          <el-option label="全部" value="all" />
          <el-option label="简单" value="easy" />
          <el-option label="中等" value="medium" />
          <el-option label="困难" value="hard" />
        </el-select>
      </div>
    </section>

    <!-- ===== 错题卡片 ===== -->
    <div v-loading="loading" class="list">
      <el-empty v-if="!loading && items.length === 0" description="没有符合条件的错题，太棒了！" />
      <article v-for="w in items" :key="w.id" class="wq-card card">
        <div class="wq-tags">
          <el-tag size="small" effect="plain">{{ w.subject }} · {{ w.knowledge_point_name }}</el-tag>
          <el-tag size="small" :type="statusTag[w.status]" effect="light">
            {{ statusText[w.status] }}
          </el-tag>
        </div>
        <p class="wq-content">{{ w.content }}</p>
        <div class="wq-answers">
          <div class="answer-row">
            <span class="answer-label">我的答案：</span>
            <span class="answer-value wrong">{{ w.my_answer }}</span>
          </div>
          <div class="answer-row">
            <span class="answer-label">正确答案：</span>
            <span class="answer-value right">{{ w.correct_answer }}</span>
          </div>
        </div>
        <div v-if="w.reason" class="wq-reason">
          <span class="reason-label">错误原因：</span>{{ w.reason }}
        </div>
        <div class="wq-footer">
          <span class="wq-difficulty">难度：{{ difficultyText[w.difficulty] || w.difficulty }}</span>
          <div class="wq-actions">
            <el-button size="small" @click="openDetail(w)">查看解析</el-button>
            <el-button
              size="small"
              type="primary"
              plain
              :loading="practicing === w.id"
              @click="onPractice(w)"
            >
              重新练习
            </el-button>
            <el-button
              v-if="!w.mastered"
              size="small"
              type="success"
              plain
              :loading="mastering === w.id"
              @click="onMaster(w)"
            >
              标记已掌握
            </el-button>
          </div>
        </div>
      </article>
    </div>

    <!-- ===== 详情抽屉 ===== -->
    <el-drawer
      v-model="drawerVisible"
      :title="current ? `${current.subject} · ${current.knowledge_point_name}` : '错题详情'"
      size="480px"
    >
      <template v-if="current">
        <div class="detail-block">
          <h4>原题</h4>
          <p class="detail-text">{{ current.content }}</p>
          <div v-if="current.options" class="detail-options">
            <div v-for="(opt, i) in current.options" :key="i" class="option-row">
              <b>{{ ['A', 'B', 'C', 'D', 'E'][i] }}.</b> {{ opt }}
            </div>
          </div>
        </div>
        <div class="detail-block">
          <h4>我的答案</h4>
          <p class="detail-text wrong">{{ current.my_answer }}</p>
        </div>
        <div class="detail-block">
          <h4>正确答案</h4>
          <p class="detail-text right">{{ current.correct_answer }}</p>
        </div>
        <div class="detail-block">
          <h4>AI 解析</h4>
          <p class="detail-text">{{ current.explanation || '暂无解析' }}</p>
        </div>
        <div class="detail-block">
          <h4>错误原因</h4>
          <p class="detail-text">{{ current.reason || '—' }}</p>
        </div>
        <div class="detail-block">
          <h4>相关知识点</h4>
          <el-tag effect="plain" round>{{ current.knowledge_point_name }}</el-tag>
        </div>
        <div class="detail-block">
          <h4>推荐学习内容</h4>
          <p class="detail-text">{{ current.suggestion || '建议重新学习相关概念后完成针对性练习。' }}</p>
          <div class="detail-actions">
            <el-button type="primary" @click="onPractice(current)">生成类似题</el-button>
            <el-button v-if="!current.mastered" type="success" plain @click="onMaster(current)">
              标记已掌握
            </el-button>
          </div>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<style scoped lang="scss">
@use '@/styles/variables.scss' as *;

.wrong-questions {
  display: flex;
  flex-direction: column;
  gap: $gap-md;
  max-width: 960px;
  margin: 0 auto;
}

.card {
  background: $bg-card;
  border-radius: $radius-md;
  box-shadow: $shadow-sm;
  border: 1px solid $border-light;
  padding: $gap-lg;
}

.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.title {
  margin: 0 0 8px;
  font-size: 20px;
  font-weight: 600;
}

.stats {
  display: flex;
  align-items: center;
  gap: 12px;
  color: $text-secondary;
  font-size: 13px;

  b {
    font-size: 15px;
    &.danger {
      color: $danger;
    }
    &.warning {
      color: $warning;
    }
    &.success {
      color: $success;
    }
  }
}

.filters {
  display: flex;
  align-items: center;
  gap: $gap-lg;
  flex-wrap: wrap;
  padding: 14px $gap-lg;
}

.filter-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.filter-label {
  font-size: 13px;
  color: $text-secondary;
}

.list {
  display: flex;
  flex-direction: column;
  gap: $gap-md;
  min-height: 200px;
}

.wq-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.wq-tags {
  display: flex;
  gap: 8px;
}

.wq-content {
  margin: 0;
  font-size: 15px;
  color: $text-primary;
  line-height: 1.6;
}

.wq-answers {
  display: flex;
  gap: $gap-lg;
  background: $bg-muted;
  border-radius: 10px;
  padding: 10px 14px;
}

.answer-row {
  font-size: 13px;
}

.answer-label {
  color: $text-secondary;
}

.answer-value {
  font-weight: 600;

  &.wrong {
    color: $danger;
  }
  &.right {
    color: $success;
  }
}

.wq-reason {
  font-size: 13px;
  color: $text-regular;
  line-height: 1.6;

  .reason-label {
    color: $text-secondary;
  }
}

.wq-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.wq-difficulty {
  font-size: 12px;
  color: $text-placeholder;
}

.wq-actions {
  display: flex;
  gap: 8px;
}

// 抽屉
.detail-block {
  margin-bottom: 18px;

  h4 {
    margin: 0 0 8px;
    font-size: 13px;
    color: $text-secondary;
    font-weight: 600;
  }
}

.detail-text {
  margin: 0;
  font-size: 14px;
  color: $text-primary;
  line-height: 1.7;

  &.wrong {
    color: $danger;
  }
  &.right {
    color: $success;
  }
}

.detail-options {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 14px;
}

.option-row b {
  color: $primary;
  margin-right: 4px;
}

.detail-actions {
  display: flex;
  gap: 10px;
  margin-top: 12px;
}
</style>
