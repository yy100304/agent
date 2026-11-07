<script setup lang="ts">
import { useRoute } from 'vue-router'

const route = useRoute()
const title = (route.meta?.title as string) || '开发中'

const tips: Record<string, string> = {
  'AI Agent': '即将接入 StudyAgent：理解学习目标 → 读取画像与错题 → 调用工具 → 生成并自动调整学习计划。',
  学习计划: '即将支持考试日期、每日学习时长与 Agent 自动生成的个性化学习任务。',
  知识库: '即将支持 PDF / TXT / Markdown 上传，并基于 RAG 检索你自己的课程资料回答问题。',
}
</script>

<template>
  <div class="placeholder">
    <div class="card-padded inner">
      <div class="badge">下一阶段</div>
      <h2>{{ title }}</h2>
      <p>{{ tips[title] || '该模块正在规划中，敬请期待。' }}</p>
      <el-alert
        type="info"
        show-icon
        :closable="false"
        title="MVP 优先"
        description="我们正在按阶段稳步推进，每完成一个模块都会进行验证再进入下一阶段。"
      />
    </div>
  </div>
</template>

<style scoped lang="scss">
@use '@/styles/variables.scss' as *;

.placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 60vh;
}

.card-padded {
  background: $bg-card;
  border-radius: $radius-md;
  box-shadow: $shadow-sm;
  border: 1px solid $border-light;
}

.inner {
  max-width: 560px;
  text-align: center;
}

.badge {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 999px;
  background: $primary-soft;
  color: $primary;
  font-size: 12px;
  margin-bottom: 12px;
}

h2 {
  margin: 0 0 8px;
  font-size: 22px;
  font-weight: 600;
  color: $text-primary;
}

p {
  color: $text-secondary;
  margin: 0 0 24px;
  line-height: 1.6;
}
</style>