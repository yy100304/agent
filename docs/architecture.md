# 智学 Agent（StudyFlow Agent）· 技术架构设计

> 本文档是项目的总体架构设计，作为后续所有开发阶段的设计蓝图。

---

## 1. 总体架构

```
┌─────────────────────────────────────────────────────────────┐
│                     前端 Vue 3 SPA                          │
│  登录/注册 · Dashboard · Agent 对话 · 学习计划 · 练习        │
│  学习画像 · 知识库管理                                       │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP / JSON（Axios + JWT）
┌──────────────────────────▼──────────────────────────────────┐
│                    FastAPI 后端（单体）                      │
│                                                             │
│  ┌─────────┐   ┌──────────┐   ┌────────────────────────┐   │
│  │  api/   │──▶│ services │──▶│      models (ORM)      │   │
│  └────┬────┘   └────┬─────┘   └───────────┬────────────┘   │
│       │             │                     │                │
│       │      ┌──────▼───────┐    ┌────────▼────────┐       │
│       │      │  StudyAgent  │    │  SQLAlchemy     │       │
│       │      │ (规划/决策)  │    │  (SQLite/MySQL) │       │
│       │      └──────┬───────┘    └─────────────────┘       │
│       │             │                                        │
│       │      ┌──────▼───────────────────────────────┐      │
│       │      │ Tools (5 个核心工具)                  │      │
│       │      │ get_learning_profile                  │      │
│       │      │ generate_study_plan                   │      │
│       │      │ search_knowledge_base (RAG)           │      │
│       │      │ generate_questions                    │      │
│       │      │ analyze_learning                      │      │
│       │      └──────┬───────────────────────┬───────┘      │
│       │             │                       │               │
│       │      ┌──────▼──────┐        ┌──────▼───────┐       │
│       │      │ LLMService  │        │  VectorStore │       │
│       │      │ (OpenAI 兼容)│        │ (Chroma)     │       │
│       │      └─────────────┘        └──────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

## 2. 数据库 ER 关系

```
users (1) ──── (N) study_plans ──── (N) study_tasks ──── (N:1) knowledge_points
  │                                                  │
  │                                                  │
  ├── (N) answers (N:1) questions (N:1) ─────────────┘
  │           │
  │           └── (1:1 自动生成) wrong_questions (N:1 users)
  │
  ├── (N) learning_records (N:1 knowledge_points)
  │
  └── (1:1 per KP) learning_profiles (N:1 knowledge_points)
```

| 表 | 说明 | 关键关系 |
|---|---|---|
| users | 用户 | 1:N study_plans / answers / wrong_questions / learning_records / learning_profiles |
| knowledge_points | 知识点（按学科） | 1:N questions / study_tasks / learning_records / learning_profiles |
| study_plans | 学习计划 | N:1 users；1:N study_tasks |
| study_tasks | 计划中的任务 | N:1 study_plans；N:1 knowledge_points |
| questions | 题库（AI 生成） | N:1 knowledge_points；1:N answers |
| answers | 用户答题记录 | N:1 users；N:1 questions |
| wrong_questions | 错题本 | N:1 users；N:1 questions |
| learning_records | 学习行为记录 | N:1 users；N:1 knowledge_points |
| learning_profiles | 知识点掌握度画像 | 1:1 (users, knowledge_points) |

## 3. API 清单（按阶段交付）

### 阶段一（已完成）
| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /api/auth/register | 注册 |
| POST | /api/auth/login | 登录（JWT） |
| GET | /api/user/profile | 当前用户资料 |
| PUT | /api/user/profile | 更新资料 |
| GET | /api/dashboard | Dashboard 汇总 |

### 阶段三（Agent）
| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /api/chat | Agent 对话（SSE 流式返回） |
| GET | /api/learning/profile | 学习画像 |
| GET | /api/learning/statistics | 学习统计 |

### 阶段四~五（计划/练习/知识库）
| 方法 | 路径 | 说明 |
|---|---|---|
| GET/POST/PUT | /api/study-plans[/{id}] | 计划 CRUD |
| GET | /api/tasks | 任务列表 |
| PUT | /api/tasks/{id}/complete | 完成任务 |
| POST | /api/questions/generate | AI 出题 |
| POST | /api/questions/{id}/answer | 提交答案（自动批改） |
| GET | /api/wrong-questions | 错题本 |
| POST | /api/documents/upload | 上传文档 |
| GET | /api/documents | 文档列表 |
| DELETE | /api/documents/{id} | 删除文档 |

## 4. Agent 工作流（ReAct 式，不暴露内部 CoT）

```
用户输入（学习目标/问题/请求）
        │
        ▼
┌──────────────────┐
│ 1. 意图理解       │  LLM 判断：制定计划？知识问答？出题？分析？
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 2. 规划           │  LLM 决定调用哪些 Tool、按什么顺序
└────────┬─────────┘         │
         ▼                   │（每次 Tool 调用都推送状态到前端：
┌──────────────────┐         │ "正在获取学习数据…"）
│ 3. Tool 执行      │◀────────┘
│  - get_learning_profile
│  - generate_study_plan
│  - search_knowledge_base
│  - generate_questions
│  - analyze_learning
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 4. 观察           │  将 Tool 结果回填给 LLM（Observation）
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 5. 决策           │  继续调用其他 Tool？还是生成最终回答？
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 6. 行动           │  必要时写库（计划调整/画像更新/错题记录）
└────────┬─────────┘
         ▼
┌──────────────────┐
│ 7. 最终回答       │  汇总为用户可读的自然语言
└──────────────────┘
```

**关键设计**：前端只展示第 2/3 步的"任务状态"（如"正在分析你的知识点掌握情况…"），不展示模型内部推理。

## 5. Tool 设计

| Tool | 输入 | 输出 | 副作用 |
|---|---|---|---|
| get_learning_profile | user_id | 各知识点掌握度、最近正确率、错题数、学习时长 | 无（只读） |
| generate_study_plan | 考试日期、每日时长、科目、画像 | 计划摘要 | 写入 study_plans + study_tasks |
| search_knowledge_base | 查询文本、Top-K | 文档名、相关段落、页码、相似度 | 无（只读 RAG） |
| generate_questions | 知识点、数量、难度（由掌握度动态决定） | 题目列表（单选/判断/简答） | 写入 questions |
| analyze_learning | user_id | 学习统计、薄弱点、增/减建议 | 可选：调整明日 study_tasks |

所有 Tool 注册到统一的 ToolRegistry，Agent 通过 function calling 协议调用。

## 6. RAG 工作流

```
【离线入库】
上传 PDF/TXT/MD
    → pypdf 文本提取（含页码）
    → 按 CHUNK_SIZE=500 / OVERLAP=50 切分
    → EMBEDDING_MODEL 向量化
    → Chroma 持久化（documents 表同时记录元数据与处理状态）

【在线检索】
search_knowledge_base(query)
    → query 向量化
    → Chroma 相似度 Top-5
    → 返回 {文档名, 段落, 页码, 相似度}
    → LLM 基于检索结果回答
    → 明确标注"来自你的资料" / "通用知识"
    → 检索失败时降级为普通 LLM 回答
```

VectorStore 封装接口，Chroma ↔ FAISS 可切换。

## 7. 掌握度计算与自动调整

**掌握度更新公式**（每知识点）：
```
答题后：mastery = 0.6 × 历史掌握度 + 0.4 × 难度加权表现（easy=0.9 / medium=1.0 / hard=1.15）
错题复习：mastery += 0.05（温和增量，封顶 95%，绝不直接置 100%）
```

**自动调整逻辑**（analyze_learning 触发）：
- 掌握度 < 0.6 → 该知识点明日任务时长 +20 分钟，题目难度下调
- 掌握度 > 0.85 → 减少重复训练，题目难度上调
- 调整记录写入 plan 的 adjustment_log，前端展示"为什么调整"

## 8. 页面结构与职责分工（v2 重构）

```
/            登录 / 注册（仅网站入口，登录后完全隐藏）
/dashboard   学习看板 —— "我现在的学习状态怎么样？"（欢迎区/今日任务/数据概览/7天趋势/Agent建议）
/agent       AI Agent —— "下一步我应该怎么学？"
/study-plan  学习计划
/practice    练习 —— AI 出题 / 做题 / 自动批改 / 解析 / 错题自动入库
/wrong-questions 错题集 —— "我过去哪些地方做错了？"（筛选/详情/重新练习/标记已掌握）
/knowledge-base  知识库
```

注意：**"学习画像"不再有独立页面**，但 `learning_profiles` 表、
`get_learning_profile()` 数据能力完整保留，由 Agent / Dashboard / 错题复习共同读写。

## 9. 错题闭环

```
答题错误 → AI 分析错误原因（无 LLM 时规则降级）→ wrong_questions 入库
    → 错题集筛选/查看/详情
    → 重新练习（generate_questions 生成同知识点类似题，状态 → 复习中）
    → 标记已掌握（mastered=true + 画像掌握度 +5%）
    → Agent 读取错题分布 → 生成针对性建议 / 调整学习计划
```

## 10. 开发阶段计划

| 阶段 | 内容 | 状态 |
|---|---|---|
| 一 | 骨架 + 登录注册 + Dashboard | ✅ 完成 |
| 二 | 数据层重构：8 张表 + LLMService（降级）+ 题库 + 批改 + 错题集 + 练习闭环 + 演示种子数据 | ✅ 完成 |
| 三 | StudyAgent + /api/chat（SSE）+ 5 Tools 注册 | 待开发 |
| 四 | RAG（上传、切分、Embedding、Chroma、检索问答） | 待开发 |
| 五 | 学习计划页 + Agent 自动调整计划 | 待开发 |
| 六 | 知识库页面 + Dashboard 打磨 | 待开发 |
