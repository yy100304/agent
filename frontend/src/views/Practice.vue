<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import {
  generateQuestionsWithMeta,
  getKnowledgePoints,
  submitAnswer,
  type GenerateMeta,
  type KnowledgePoint,
  type Question,
  type AnswerResult,
} from '@/api/questions'
import SubjectBadge from '@/components/SubjectBadge.vue'
import { usePracticeStore } from '@/stores/practice'
import { useSubjectStore } from '@/stores/subject'

const practiceStore = usePracticeStore()
const subjectStore = useSubjectStore()

const loading = ref(false)
const submitting = ref(false)
const knowledgePoints = ref<KnowledgePoint[]>([])
const genMeta = ref<GenerateMeta | null>(null)

const form = reactive({
  knowledge_point_id: undefined as number | undefined,
  count: 5,
})

interface QuizItem {
  question: Question
  myAnswer: string
  selected: string[]
  result: AnswerResult | null
}

const quiz = ref<QuizItem[]>([])
const quizTitle = ref('')

const LETTERS = ['A', 'B', 'C', 'D', 'E']

const alertType = computed(() => {
  if (genMeta.value?.status === 'success') return 'success'
  if (genMeta.value?.status === 'partial') return 'warning'
  return 'error'
})

const missingCount = computed(() => {
  if (!genMeta.value) return 0
  return Math.max(0, genMeta.value.requestedCount - genMeta.value.actualCount)
})

const subjectOptions = computed(() => {
  const set = new Set(knowledgePoints.value.map((k) => k.subject))
  return Array.from(set)
})

// 当前科目下的知识点（顶部切换科目后联动）
const subjectKps = computed(() => {
  const current = subjectStore.current
  if (!current) return knowledgePoints.value
  return knowledgePoints.value.filter((k) => k.subject === current)
})

watch(subjectKps, (list) => {
  if (!list.some((k) => k.id === form.knowledge_point_id)) {
    form.knowledge_point_id = list[0]?.id
  }
})

watch(
  () => subjectStore.current,
  () => {
    quiz.value = []
    genMeta.value = null
    quizTitle.value = ''
  },
)

const difficultyText: Record<string, string> = {
  easy: '简单',
  medium: '中等',
  hard: '困难',
}
const typeText: Record<string, string> = {
  single_choice: '单选题',
  multiple_choice: '多选题',
  true_false: '判断题',
  short_answer: '简答题',
}

const answeredCount = computed(() => quiz.value.filter((q) => q.result).length)
const correctCount = computed(
  () => quiz.value.filter((q) => q.result?.is_correct).length
)
const allAnswered = computed(
  () => quiz.value.length > 0 && answeredCount.value === quiz.value.length
)

async function onGenerate() {
  if (!form.knowledge_point_id) {
    ElMessage.warning('先选个知识点吧')
    return
  }
  loading.value = true
  genMeta.value = null
  try {
    const { questions, meta } = await generateQuestionsWithMeta({
      knowledge_point_id: form.knowledge_point_id,
      count: form.count,
    })
    genMeta.value = meta

    if (!questions.length) {
      quiz.value = []
      quizTitle.value = ''
      ElMessage.warning(meta.reason || '未能生成题目，请稍后再试')
      return
    }
    const kp = knowledgePoints.value.find((k) => k.id === form.knowledge_point_id)
    quizTitle.value = `${kp?.name ?? '练习'} · ${questions.length} 道题`
    quiz.value = questions.map((q) => ({
      question: q,
      myAnswer: '',
      selected: [],
      result: null,
    }))
  } catch (e) {
    console.error(e)
    const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
    genMeta.value = {
      status: 'failed',
      requestedCount: form.count,
      actualCount: 0,
      attempts: 0,
      fallbackCount: 0,
      reason: typeof detail === 'string' ? detail : '生成失败，请稍后再试',
    }
    quiz.value = []
    quizTitle.value = ''
  } finally {
    loading.value = false
  }
}

function buildAnswer(item: QuizItem): string {
  if (item.question.question_type === 'multiple_choice') {
    return [...item.selected].sort().join('')
  }
  return item.myAnswer.trim()
}

async function onSubmit(item: QuizItem) {
  const answer = buildAnswer(item)
  if (!answer) {
    ElMessage.warning(
      item.question.question_type === 'multiple_choice'
        ? '请至少选择一个选项'
        : '请先填写答案'
    )
    return
  }
  submitting.value = true
  try {
    item.result = await submitAnswer(item.question.id, answer)
  } catch (e) {
    console.error(e)
  } finally {
    submitting.value = false
  }
}

function retry(item: QuizItem) {
  item.result = null
  item.myAnswer = ''
  item.selected = []
}

function onRetryAll() {
  quiz.value.forEach((q) => {
    q.result = null
    q.myAnswer = ''
    q.selected = []
  })
}

onMounted(async () => {
  // 错题集"重新练习"带来的预置题目
  if (practiceStore.presetQuestions?.length) {
    quiz.value = practiceStore.presetQuestions.map((q) => ({
      question: q,
      myAnswer: '',
      selected: [],
      result: null,
    }))
    quizTitle.value = practiceStore.presetTitle
    practiceStore.clearPreset()
  }
  try {
    knowledgePoints.value = await getKnowledgePoints()
    if (!form.knowledge_point_id && subjectKps.value.length) {
      form.knowledge_point_id = subjectKps.value[0].id
    }
  } catch (e) {
    console.error(e)
  }
})
</script>

<template>
  <div class="practice">
    <!-- ===== 生成区 ===== -->
    <section class="card gen-card">
      <div class="gen-title">
        <h3>小助手出题</h3>
        <SubjectBadge />
        <span class="gen-hint">小助手会看着你的掌握度挑难度，薄弱的地方多练几道</span>
      </div>
      <div class="gen-form">
        <el-select
          v-model="form.knowledge_point_id"
          placeholder="想练哪个知识点"
          style="width: 200px"
        >
          <el-option
            v-for="k in subjectKps"
            :key="k.id"
            :label="`${k.subject} · ${k.name}`"
            :value="k.id"
          />
        </el-select>
        <el-select v-model="form.count" style="width: 110px">
          <el-option :value="3" label="3 道题" />
          <el-option :value="5" label="5 道题" />
          <el-option :value="10" label="10 道题" />
        </el-select>
        <el-button type="primary" :loading="loading" @click="onGenerate">
          {{ loading ? '小助手正在出题…' : '让小助手出题' }}
        </el-button>
      </div>
      <p v-if="loading" class="gen-loading">
        正在挑题、编排难度，通常 10 秒内就好，稍等一下～
      </p>
    </section>

    <!-- ===== 生成结果提示（success / partial / failed）===== -->
    <el-alert
      v-if="genMeta"
      class="gen-alert"
      :type="alertType"
      :closable="true"
      show-icon
      @close="genMeta = null"
    >
      <template #title>
        <span v-if="genMeta.status === 'success'">
          出好了：{{ genMeta.actualCount }} 道题<template v-if="genMeta.fallbackCount">（其中 {{ genMeta.fallbackCount }} 道是从题库里挑的）</template>，开始练吧
        </span>
        <span v-else-if="genMeta.status === 'partial'">
          先凑到 {{ genMeta.actualCount }}/{{ genMeta.requestedCount }} 道，还差 {{ missingCount }} 道
        </span>
        <span v-else>
          这次没出成，换个知识点或者稍后再试试
        </span>
      </template>
      <div
        v-if="genMeta.reason && genMeta.status !== 'success'"
        class="alert-reason"
      >
        {{ genMeta.status === 'partial' ? '原因：' : '' }}{{ genMeta.reason }}
      </div>
    </el-alert>

    <!-- ===== 做题区 ===== -->
    <template v-if="quiz.length">
      <section class="quiz-head card">
        <div class="quiz-title">
          {{ quizTitle }}
          <span class="quiz-score" v-if="answeredCount">
            已答 {{ answeredCount }}/{{ quiz.length }} · 正确 {{ correctCount }}
          </span>
        </div>
        <el-button v-if="allAnswered" size="small" @click="onRetryAll">
          再练一次
        </el-button>
      </section>

      <article
        v-for="(item, idx) in quiz"
        :key="item.question.id"
        class="card quiz-card"
      >
        <div class="q-head">
          <span class="q-index">{{ idx + 1 }}</span>
          <div class="q-tags">
            <el-tag size="small" effect="plain">
              {{ typeText[item.question.question_type] }}
            </el-tag>
            <el-tag size="small" effect="plain" type="info">
              {{ difficultyText[item.question.difficulty] }}
            </el-tag>
            <el-tag v-if="item.question.source === 'ai'" size="small" type="warning" effect="plain">
              小助手出品
            </el-tag>
          </div>
        </div>

        <p class="q-content">{{ item.question.content }}</p>

        <!-- 单选题 -->
        <el-radio-group
          v-if="item.question.question_type === 'single_choice'"
          v-model="item.myAnswer"
          class="q-options"
          :disabled="!!item.result"
        >
          <el-radio
            v-for="(opt, i) in item.question.options || []"
            :key="i"
            :value="['A', 'B', 'C', 'D', 'E'][i]"
            class="q-option"
          >
            {{ ['A', 'B', 'C', 'D', 'E'][i] }}. {{ opt }}
          </el-radio>
        </el-radio-group>

        <!-- 多选题 -->
        <el-checkbox-group
          v-else-if="item.question.question_type === 'multiple_choice'"
          v-model="item.selected"
          class="q-options"
          :disabled="!!item.result"
        >
          <el-checkbox
            v-for="(opt, i) in item.question.options || []"
            :key="i"
            :value="LETTERS[i]"
            class="q-option"
          >
            {{ LETTERS[i] }}. {{ opt }}
          </el-checkbox>
        </el-checkbox-group>

        <!-- 判断题 -->
        <el-radio-group
          v-else-if="item.question.question_type === 'true_false'"
          v-model="item.myAnswer"
          class="q-options"
          :disabled="!!item.result"
        >
          <el-radio value="正确" class="q-option">正确</el-radio>
          <el-radio value="错误" class="q-option">错误</el-radio>
        </el-radio-group>

        <!-- 简答题 -->
        <el-input
          v-else
          v-model="item.myAnswer"
          type="textarea"
          :rows="3"
          placeholder="请输入你的答案"
          :disabled="!!item.result"
        />

        <!-- 批改结果 -->
        <div v-if="item.result" class="q-result" :class="item.result.is_correct ? 'right' : 'wrong'">
          <div class="q-result-head">
            <b>{{ item.result.is_correct ? '✓ 回答正确' : '✗ 回答错误' }}</b>
            <span v-if="item.question.question_type === 'short_answer'">
              得分：{{ Math.round(item.result.score * 100) }}分
            </span>
          </div>
          <div v-if="!item.result.is_correct" class="q-answer">
            正确答案：{{ item.result.correct_answer }}
          </div>
          <div v-if="item.result.explanation" class="q-explanation">
            <span class="exp-label">解析：</span>{{ item.result.explanation }}
          </div>
          <el-button size="small" text @click="retry(item)">重做本题</el-button>
        </div>

        <div v-else class="q-submit">
          <el-button
            type="primary"
            :loading="submitting"
            @click="onSubmit(item)"
          >
            提交答案
          </el-button>
        </div>
      </article>
    </template>

    <el-empty v-else-if="!loading" description="挑个知识点，小助手马上给你出几道题" />
  </div>
</template>

<style scoped lang="scss">
@use '@/styles/variables.scss' as *;

.practice {
  display: flex;
  flex-direction: column;
  gap: $gap-md;
  max-width: 860px;
  margin: 0 auto;
}

.card {
  background: $bg-card;
  border-radius: $radius-md;
  box-shadow: $shadow-sm;
  border: 1px solid $border-light;
  padding: $gap-lg;
}

.gen-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: $gap-md;
  flex-wrap: wrap;
}

.gen-title {
  h3 {
    margin: 0 0 4px;
    font-size: 16px;
    font-weight: 600;
  }
}

.gen-hint {
  font-size: 12px;
  color: $text-placeholder;
}

.gen-loading {
  flex-basis: 100%;
  margin: 8px 0 0;
  font-size: 12px;
  color: $primary;
}

.gen-form {
  display: flex;
  gap: $gap-sm;
}

.gen-alert {
  padding: 10px 14px;
}

.alert-reason {
  margin-top: 2px;
  font-size: 12px;
  line-height: 1.6;
  opacity: 0.85;
}

.quiz-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px $gap-lg;
}

.quiz-title {
  font-size: 15px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 12px;
}

.quiz-score {
  font-size: 12px;
  font-weight: 400;
  color: $text-secondary;
}

.quiz-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.q-head {
  display: flex;
  align-items: center;
  gap: 10px;
}

.q-index {
  width: 26px;
  height: 26px;
  border-radius: 8px;
  background: $primary-soft;
  color: $primary;
  font-weight: 600;
  font-size: 13px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.q-tags {
  display: flex;
  gap: 6px;
}

.q-content {
  margin: 0;
  font-size: 15px;
  line-height: 1.7;
  color: $text-primary;
}

.q-options {
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: stretch;
}

.q-option {
  height: auto;
  padding: 8px 12px;
  margin-right: 0 !important;
  border-radius: 10px;
  border: 1px solid $border-light;

  &:hover {
    border-color: $primary;
  }
}

.q-result {
  border-radius: 12px;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 13px;

  &.right {
    background: rgba(22, 163, 74, 0.08);
    border: 1px solid rgba(22, 163, 74, 0.25);

    .q-result-head b {
      color: $success;
    }
  }

  &.wrong {
    background: rgba(239, 68, 68, 0.06);
    border: 1px solid rgba(239, 68, 68, 0.25);

    .q-result-head b {
      color: $danger;
    }
  }
}

.q-result-head {
  display: flex;
  align-items: center;
  gap: 10px;
}

.q-answer {
  color: $success;
  font-weight: 500;
}

.q-explanation {
  color: $text-regular;
  line-height: 1.6;

  .exp-label {
    color: $text-secondary;
  }
}

.q-submit {
  display: flex;
  justify-content: flex-end;
}
</style>
