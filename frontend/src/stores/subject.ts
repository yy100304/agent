import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { createSubject, getSubjects, type SubjectItem } from '@/api/subjects'

const STORAGE_KEY = 'studyflow_subject'

/**
 * 全局科目：除 AI Agent 外，各模块共用「当前科目」
 * - 侧边栏/顶栏可切换与新增科目
 * - 计划 / 练习 / 错题 / 知识库按当前科目过滤
 */
export const useSubjectStore = defineStore('subject', () => {
  const current = ref<string>(localStorage.getItem(STORAGE_KEY) || '')
  const list = ref<SubjectItem[]>([])
  const loading = ref(false)

  const options = computed(() => list.value.map((item) => item.name))
  const currentItem = computed(
    () => list.value.find((item) => item.name === current.value) || null,
  )
  const label = computed(() => current.value || '未选择科目')

  function setCurrent(name: string) {
    if (!name) return
    current.value = name
    localStorage.setItem(STORAGE_KEY, name)
  }

  async function load() {
    loading.value = true
    try {
      list.value = await getSubjects()
      if (!current.value || !list.value.some((item) => item.name === current.value)) {
        // 优先选有内容的科目
        const preferred =
          list.value.find(
            (item) => item.knowledge_points + item.plans + item.documents > 0,
          ) || list.value[0]
        if (preferred) setCurrent(preferred.name)
      }
    } finally {
      loading.value = false
    }
  }

  async function add(name: string): Promise<SubjectItem> {
    const created = await createSubject(name.trim())
    await load()
    setCurrent(created.name)
    return created
  }

  return { current, list, loading, options, currentItem, label, setCurrent, load, add }
})
