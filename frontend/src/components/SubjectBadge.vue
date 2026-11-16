<script setup lang="ts">
import { computed } from 'vue'

import { useSubjectStore } from '@/stores/subject'

const props = withDefaults(defineProps<{ prefix?: string }>(), { prefix: '科目' })

const subjectStore = useSubjectStore()

const text = computed(() => `${props.prefix}：${subjectStore.label}`)
const hint = computed(() => {
  const item = subjectStore.currentItem
  if (!item) return '可在顶部切换或新增科目'
  return `知识点 ${item.knowledge_points} · 题目 ${item.questions} · 计划 ${item.plans} · 资料 ${item.documents}`
})
</script>

<template>
  <el-tooltip :content="hint" placement="top" :show-after="300">
    <el-tag class="subject-badge" size="small" effect="plain" type="primary">{{ text }}</el-tag>
  </el-tooltip>
</template>

<style scoped>
.subject-badge {
  cursor: default;
}
</style>
