<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import {
  generateQuestions,
  getKnowledgePoints,
  submitAnswer,
  type KnowledgePoint,
  type Question,
  type AnswerResult,
} from '@/api/questions'
import { usePracticeStore } from '@/stores/practice'

const practiceStore = usePracticeStore()

const loading = ref(false)
const submitting = ref(false)
const knowledgePoints = ref<KnowledgePoint[]>([])

const form = reactive({
  knowledge_point_id: undefined as number | undefined,
  count: 5,
})

interface QuizItem {
  question: Question
  myAnswer: string
  result: AnswerResult | null
}

const quiz = ref<QuizItem[]>([])
const quizTitle = ref('')

const subjectOptions = computed(() => {
  const set = new Set(knowledgePoints.value.map((k) => k.subject))
  return Array.from(set)
})

const difficultyText: Record<string, string> = {
  easy: '简单',
  medium: '中等',
  hard: '困难',
}
const typeText: Record<string, string> = {
  single_choice: '单选题',
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
    ElMessage.warning('请先选择知识点')
    return
  }
  loading.value = true
  try {
    const questions = await generateQuestions({
      knowledge_point_id: form.knowledge_point_id,
      count: form.count,
    })
    if (!questions.length) {
      ElMessage.warning('未能生成题目，请稍后再试')
      return
    }
    const kp = knowledgePoints.value.find((k) => k.id === form.knowledge_point_id)
    quizTitle.value = `${kp?.name ?? '练习'} · ${questions.length} 道题`
    quiz.value = questions.map((q) => ({ question: q, myAnswer: '', result: null }))
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

async function onSubmit(item: QuizItem) {
  if (!item.myAnswer.trim()) {
    ElMessage.warning('请先填写答案')
    return
  }
  submitting.value = true
  try {
    item.result = await submitAnswer(item.question.id, item.myAnswer.trim())
  } catch (e) {
    console.error(e)
  } finally {
    submitting.value = false
  }
}

function retry(item: QuizItem) {
  item.result = null
  item.myAnswer = ''
}

function onRetryAll() {
  quiz.value.forEach((q) => {
    q.result = null
    q.myAnswer = ''
  })
}

onMounted(async () => {
  // 错题集"重新练习"带来的预置题目
  if (practiceStore.presetQuestions?.length) {
    quiz.value = practiceStore.presetQuestions.map((q) => ({
      question: q,
      myAnswer: '',
      result: null,
    }))
    quizTitle.value = practiceStore.presetTitle
    practiceStore.clearPreset()
  }
  try {
    knowledgePoints.value = await getKnowledgePoints()
    if (!form.knowledge_point_id && knowledgePoints.value.length) {
      form.knowledge_point_id = knowledgePoints.value[0].id
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
        <h3>AI 出题</h3>
        <span class="gen-hint">题目难度会根据你的知识点掌握度自动调整</span>
      </div>
      <div class="gen-form">
        <el-select
          v-model="form.knowledge_point_id"
          placeholder="选择知识点"
          style="width: 200px"
        >
          <el-option
            v-for="k in knowledgePoints"
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
          生成练习
        </el-button>
      </div>
    </section>

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
              AI 生成
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

    <el-empty v-else-if="!loading" description="选择知识点，让 AI 为你出一组练习题" />
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

.gen-form {
  display: flex;
  gap: $gap-sm;
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
