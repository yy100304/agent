import { defineStore } from 'pinia'
import { ref } from 'vue'

import type { Question } from '@/api/questions'

/**
 * 练习状态：错题集"重新练习"生成的题目带到练习页作答
 */
export const usePracticeStore = defineStore('practice', () => {
  // 从错题集跳转过来的预置题目（null 表示普通练习模式）
  const presetQuestions = ref<Question[] | null>(null)
  const presetTitle = ref<string>('')

  function setPreset(questions: Question[], title: string) {
    presetQuestions.value = questions
    presetTitle.value = title
  }

  function clearPreset() {
    presetQuestions.value = null
    presetTitle.value = ''
  }

  return { presetQuestions, presetTitle, setPreset, clearPreset }
})