# 智学 Agent (StudyFlow Agent)

> 一个能够感知学生学习状态、制定学习计划、调用学习工具、分析学习结果，并根据反馈自主调整学习计划的个人智能学习 Agent。

## 项目愿景

普通 AI：用户问 → AI 答。

**智学 Agent**：用户提出学习目标 → Agent 感知学习状态 → 自主规划 → 调用工具执行 → 获取反馈 → 更新学习画像 → 自动调整下一步行动。

## 技术栈

### 前端
- Vue 3 + Vite + TypeScript
- Element Plus
- Vue Router + Pinia
- Axios
- ECharts

### 后端
- Python 3.11+
- FastAPI + Pydantic
- SQLAlchemy + SQLite（可平滑切换 MySQL）
- JWT 鉴权

### Agent / RAG
- LLM Service（OpenAI 兼容接口）
- Chroma / FAISS 向量数据库
- PDF / TXT / MD 文档解析

## 目录结构

```
agent/
├── backend/                # FastAPI 后端
│   ├── app/
│   │   ├── api/            # 路由层
│   │   ├── core/           # 配置、安全、日志
│   │   ├── database/       # SQLAlchemy 初始化
│   │   ├── models/         # ORM 模型
│   │   ├── schemas/        # Pydantic Schema
│   │   ├── services/       # 业务服务
│   │   ├── agents/         # Agent 实现
│   │   │   ├── core/       # 基础框架：BaseAgent / AgentTask / 注册表
│   │   │   ├── learning_analysis_agent.py    # 学情分析
│   │   │   ├── knowledge_retrieval_agent.py  # 知识检索
│   │   │   ├── study_planning_agent.py       # 学习计划
│   │   │   ├── question_generation_agent.py  # 练习生成
│   │   │   ├── result_validation_agent.py    # 结果验证
│   │   │   ├── master/     # 主控编排：意图解析 / 规划 / 调度 / 汇总 / 落库
│   │   │   └── workflow/   # 工作流引擎 + Self-Loop（失败分类 / 修正策略 / 恢复）
│   │   ├── tools/          # Agent Tools
│   │   ├── rag/            # RAG 与向量库
│   │   └── utils/          # 工具函数
│   ├── requirements.txt
│   ├── run.py              # 开发启动脚本
│   ├── test_*.py           # 各阶段独立测试脚本（见「测试」章节）
│   └── .env.example
├── frontend/               # Vue 3 前端
│   ├── src/
│   │   ├── api/            # API 调用封装
│   │   ├── components/     # 通用组件
│   │   ├── router/         # 路由
│   │   ├── stores/         # Pinia 状态
│   │   ├── styles/         # 全局样式
│   │   ├── utils/          # 工具
│   │   └── views/          # 页面（StudyPlan / KnowledgeBase / AgentTasks=执行档案）
│   └── package.json
├── data/                   # 数据库与上传文件
├── docs/                   # 项目文档
└── README.md
```

## 启动方式

### 一键启动（Windows 推荐）

双击项目根目录的 `start-dev.bat`，会同时拉起前后端并自动打开浏览器。

| 服务 | 地址 |
|---|---|
| 前端页面 | http://localhost:5173 |
| 学习计划页 | http://localhost:5173/study-plan |
| 知识库页（上传资料） | http://localhost:5173/knowledge-base |
| 任务轨迹页（执行档案 / Self-Loop） | http://localhost:5173/agent-tasks |
| 后端 API | http://127.0.0.1:8000 |
| 接口文档（Swagger） | http://127.0.0.1:8000/docs |
| 测试账号 | `demo / demo123` |

停止服务：关闭两个启动窗口，或运行 `stop-dev.bat`。

### 手动启动后端

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env          # 按需填写 LLM_API_KEY，缺省则走内置题库降级
python run.py                 # 读取 .env 中的 HOST / PORT，默认 0.0.0.0:8000
```

等价的 uvicorn 命令：

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 手动启动前端

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

前端固定 `5173` 端口，并通过 Vite 代理把 `/api` 转发到 `http://localhost:8000`
（可用 `VITE_API_PROXY_TARGET` 覆盖）。

### LLM 配置（可选）

`backend/.env` 中的 `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` 决定是否启用 AI 出题：

- **未配置 Key**：题目全部来自内置题库，数量仍按请求补齐（不编造、不重复）；
- **使用推理模型**（如 DeepSeek 推理版）：推理内容会先占用 token 预算，可能出现
  `content` 为空。`LLMService` 检测到空内容时会自动放大预算重试一次；
  出题侧默认预算为 `max(3000, 题量 × 800)`，避免题目 JSON 被截断。

## 测试

各阶段均为**可独立运行**的测试脚本，位于 `backend/` 目录，执行方式：

```powershell
cd backend
$env:PYTHONIOENCODING="utf-8"
.\.venv\Scripts\python.exe test_question_generation_agent.py
```

脚本最后一行输出 `结果: N 通过, M 失败`，退出码非 0 表示存在失败。

| 脚本 | 覆盖内容 |
|---|---|
| `test_agent_core.py` | Agent 基类状态机、超时、重试、日志、注册表 |
| `test_agent_platform.py` | 多智能体平台团队/工作流/SSE/轨迹落库 |
| `test_learning_agent.py` | 学情分析：真实数据、数据不足如实上报、用户隔离 |
| `test_knowledge_retrieval_agent.py` | 知识检索：命中/未命中、结构化输出、降级 |
| `test_study_planning_agent.py` | 学习计划：每日时长预算、薄弱点优先、事务回滚 |
| `test_question_generation_agent.py` | 练习生成：题型/难度参数、数量补题、题库兜底、库内去重、部分成功、注册表 |
| `test_question_agent_http.py` | `/api/questions/generate` 接入：Agent 状态头、兜底、partial、旧请求兼容 |
| `test_result_validation_agent.py` | 结果验证：数量/字段/一致性校验、LLM 辅助、只读性 |
| `test_master_agent.py` | 主控 Agent：意图解析、任务规划、多 Agent 协同、失败隔离、部分成功 |
| `test_master_api.py` | `/api/agent/tasks` 接口：提交/列表/详情/取消/恢复、用户隔离 |
| `test_self_loop.py` | Self-Loop：只补缺口、轮次上限、预算原地压缩、不可修复、数据库错误、幂等、日志清理 |
| `test_question_count_guarantee.py` | 练习生成「数量不达标」回归：多轮补题、宽容解析、题库分层补齐 |

> 说明：`test_api.py` 为全链路 HTTP 冒烟测试，需先启动后端服务后再运行。
> 工作流引擎（`WorkflowEngine`）的编排与修正行为由 `test_self_loop.py` 覆盖。

第九阶段验收基线（2026-11-15）：`test_self_loop.py` 42 项全通过，
第三～八阶段回归全通过；已知既有问题见「更新记录 · 遗留问题」。

## 已实现能力

- [x] **阶段一**：项目骨架、登录注册、基础 Dashboard
- [x] **阶段二**：Agent 基础架构（执行状态机、超时/重试、结构化日志、注册表）
- [x] **阶段三**：学情分析 Agent（真实数据、薄弱点、数据不足如实上报）
- [x] **阶段四**：知识检索 Agent（复用检索能力、结构化重点/难点）
- [x] **阶段五**：学习计划 Agent（每日时长预算硬校验、单一事务写入）
- [x] **阶段六**：练习生成 Agent（题型/难度/薄弱点开关、数量补题、LLM 失败题库兜底（含多选）、任务内+库内去重、部分成功、统一注册表、`/api/questions/generate` 接入、练习页状态提示）
- [x] **阶段七**：结果验证 Agent（程序化校验 + 可选 LLM 辅助评分）
- [x] **阶段八**：主控 Agent + `/api/agent/tasks`（意图解析 → 规划 → 调度 → 校验 → 汇总 → 落库）
- [x] **阶段九**：工作流引擎与 Self-Loop（只补缺口、轮次上限、预算原地压缩、不可修复如实上报、数据库错误转人工确认、幂等、日志清理）
- [x] **阶段九前端**：`/agent-tasks` 任务轨迹页（历史任务 / 步骤 / 自我修正轮次 / 校验记录 / 日志）
- [x] **学习计划页** `/study-plan`：计划列表、考试倒计时、按日期分组的任务、完成打卡、进度与「安排说明」（AI 为什么这样排）
- [x] **知识库页** `/knowledge-base`：上传入口（TXT / Markdown / CSV / JSON / PDF / DOCX；扫描版 PDF 自动 OCR，单文件 ≤ 100 MB）→ 解析切块入库 → 检索测试 → 预览 / 删除
- [x] **资料进入 RAG**：Agent 讲解时先检索内置知识库，再检索「我的资料」，命中后注入参考上下文并在轨迹中展示来源
- [x] **任务轨迹定位**：`/agent-tasks` 收敛为「执行档案」（只读追溯 + 取消 / 安全恢复），不再与 AI 对话页重复
- [x] **响应提速**：规则优先调度（省一次模型往返）、可选 LLM 评分默认关闭、token 级流式输出（首字更快）
- [x] 练习生成数量保证：多轮补题 + 宽容解析 + 题库分层补齐（`QuestionService.generate`）

## 创新点

1. **目标驱动的学习 Agent**：从「回答问题」升级为「主动执行学习任务」
2. **多工具协同**：Agent 调用 5 个学习工具完成任务
3. **个人学习画像**：基于真实学习数据构建
4. **RAG + 个人课程资料**：结合用户自己的学习材料
5. **反馈驱动的自适应**：根据学习结果自动调整学习计划
6. **结果质量闭环**：写入型 Agent 均带数量/字段/落库一致性校验，异常可回滚、可重生成

## 接口说明：`POST /api/questions/generate`

练习生成统一走第六阶段 Agent，**请求体与响应体保持原有约定**（响应仍是题目列表），
新增字段全部可选：

```jsonc
{
  "knowledge_point_id": 4,
  "count": 5,
  "difficulty": "medium",        // 可选，支持 easy/medium/hard 与简单/中等/困难
  "question_types": ["single_choice", "multiple_choice"],  // 可选
  "use_weak_points": true        // 可选，默认结合薄弱知识点
}
```

Agent 执行状态通过响应头回传（前端可据此提示「部分完成」）：

| 响应头 | 含义 |
|---|---|
| `X-Agent-Status` | `success` / `partial` / `failed` |
| `X-Requested-Count` | 请求数量 |
| `X-Actual-Count` | 实际生成并保存的数量 |
| `X-Agent-Attempts` | 生成轮次 |
| `X-Agent-Fallback` | 其中题库兜底的条数 |
| `X-Agent-Reason` | 失败 / 部分成功原因（URL 编码） |

未生成任何题目时按旧约定返回 `400` 并携带原因。

> 前端通过 Vite 代理访问时是同源请求；若直连 `http://localhost:8000`
> （`VITE_API_BASE_URL`），后端 CORS 已通过 `expose_headers` 暴露上述响应头，
> 否则浏览器会隐藏它们。

练习页会在题目列表上方展示生成结果：完整成功显示实际数量，部分成功显示
「要求 / 实际 / 未完成 / 原因」，完全失败显示错误原因，已生成的题目仍可正常作答。

## 接口说明：`/api/agent/tasks`（主控 Agent 任务）

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/agent/tasks` | 提交自然语言需求，同步返回完整执行结果（含自我修正过程） |
| `GET` | `/api/agent/tasks` | 当前用户历史任务列表（`limit` / `offset`，严格用户隔离） |
| `GET` | `/api/agent/tasks/{task_id}` | 任务详情：执行计划、步骤、校验记录、执行日志与最终结果 |
| `POST` | `/api/agent/tasks/{task_id}/cancel` | 请求取消（步骤间隙安全停止，已写入数据保持完整） |
| `POST` | `/api/agent/tasks/{task_id}/resume` | 安全恢复（已完成步骤不重跑；写入型步骤先确认副作用） |

请求体：

```jsonc
{
  "message": "帮我生成10道关系与闭包的练习题。",
  "options": {                    // 可选，优先级高于自然语言解析
    "count": 10,
    "difficulty": "medium",
    "knowledge_point": "关系与闭包",
    "exam_date": "2026-11-22",
    "daily_minutes": 120
  }
}
```

响应关键字段（前端「任务轨迹」页按此渲染）：

| 字段 | 含义 |
|---|---|
| `task_status` | `success` / `partial` / `failed` |
| `executed_agents` | 实际参与执行的 Agent 顺序 |
| `agent_results[]` | 每步状态、错误、原始输出 |
| `final_result.summary` | 面向用户的执行结论（含真实数量，不谎报） |
| `final_result.issues` / `warnings` | 待处理问题与告警 |
| `final_result.self_loop` | 自我修正总览：`repair_count` / `max_repair_rounds` / `stopped_reason` / `rounds[]` |

`self_loop.rounds[]` 每轮包含：`failure_type` / `failure_label`（数量不足、超预算、数据库错误…）、
`before` / `after`（修正前后真实数量）、`actions[]`（`rerun` 重跑 / `confirm` 先确认写入）、
`validation`（复验是否通过、通过项数、遗留 `issues`）。详情接口另外返回落库的
`steps[]`（workflow_steps）与 `evaluations[]`（agent_evaluations，含每轮校验得分）。

> `stopped_reason` 取值：`passed`（一次通过）、`not_repairable`（不可自动修复）、
> `still_failing`（修正后仍未通过）、`max_rounds`（达到最大轮次）、
> `manual_check`（写入结果未知，需人工确认）、`cancelled`（已取消）。

## 接口说明：知识库资料 `/api/knowledge-docs`

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/knowledge-docs/formats` | 支持的格式与学科选项（前端文案） |
| `POST` | `/api/knowledge-docs/upload` | 上传资料（multipart：`file` + 可选 `title` / `subject`），解析后切块入库 |
| `GET` | `/api/knowledge-docs` | 当前用户资料列表（支持 `q` / `subject` 过滤） |
| `GET` | `/api/knowledge-docs/{id}` | 资料详情（含正文，供预览） |
| `GET` | `/api/knowledge-docs/search?q=` | 在当前用户资料中做关键词检索（验证 RAG 是否可用） |
| `DELETE` | `/api/knowledge-docs/{id}` | 删除资料（仅本人） |

- 支持格式：`.txt` / `.md` / `.markdown` / `.csv` / `.json` / `.log` / `.pdf`（PDF 依赖 `pypdf`）；
- 单篇正文上限 20 万字符，按 500 字切块并保留 50 字重叠；同名资料覆盖更新；
- 检索为本地关键词加权（中文二元组 + 英文整词），命中片段作为参考资料注入 Agent 提示词。

## 接口说明：学习计划 `/api/study-plans`

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/study-plans` | 计划列表（Dashboard 倒计时复用） |
| `GET` | `/api/study-plans/{plan_id}` | 计划详情：任务列表（按日期）、完成进度、考试倒计时、`adjustment_log` |

> 任务完成仍走 `PUT /api/tasks/{task_id}/complete`（同时写入学习行为记录）。

## 响应速度相关配置（`.env`）

| 变量 | 默认值 | 说明 |
|---|---|---|
| `AGENT_STREAM_TOKENS` | `true` | 对话回复使用 token 级流式输出（首字更快，失败自动降级为整段生成） |
| `AGENT_LLM_VALIDATION` | `false` | 是否额外调用 LLM 做输出质量评分（每次多一轮模型往返，默认只用规则校验） |

调度策略：关键词规则优先，规则判不出学习意图时才请求 LLM 分类（省一次模型往返）。
实测同一提问：首字 14.2s → 3.1s，总耗时 15.0s → 5.7s。

## 更新记录

### 2026-11-15

- **前端体验修复（4 项）**：
  - **AI 响应提速**：调度改为「规则优先，识别不出再问 LLM」（省一次 3~5s 往返）、
    可选 LLM 质量评分默认关闭、主答案改为 token 级流式；前端新增 `delta_reset` 处理
    （自我修正时丢弃未通过验证的内容）。实测同一提问：首字 14.2s → 3.1s，总耗时 15.0s → 5.7s。
  - **「任务轨迹」定位收敛为执行档案**：去掉与对话页重复的提交入口，改为只读追溯
    （步骤 / Self-Loop 轮次 / 落库校验 / 日志）+ 取消 / 安全恢复，并在页头说明与 AI Agent 的分工。
  - **学习计划页落地** `/study-plan`：计划列表 + 考试倒计时 + 按日期分组的任务 + 完成打卡 +
    进度 + 「安排说明」（为什么这样排）；后端新增 `GET /api/study-plans/{plan_id}`。
  - **知识库落地** `/knowledge-base`：新增 `knowledge_documents` 表与 `/api/knowledge-docs`
    上传 / 列表 / 详情 / 删除 / 检索接口（PDF 解析用 `pypdf`），上传资料会进入 Agent 讲解的
    RAG 上下文，轨迹里能看到「我的资料·xxx」命中来源。
- **本轮回归**：`test_agent_platform.py` 19/19（流式断言适配 `delta_reset`）、
  九阶段 42/42、数量保证 26/26、二～八阶段全通过；`test_master_agent.py` 仍有 3 项既有失败。
- **第九阶段（Self-Loop）修复 + 前端接入**：
  - 修复 `WorkflowEngine._is_passed`：没有校验步骤时按「产物 → 产出 Agent」映射判定
    （`question_set` → `question_generation` 且以 `count_met` 为准，检索以 `found` 为准），
    修正轮次不再被误判为「仍未通过」；
  - `test_self_loop.py` 数据准备加固：显式指定知识点、注入真实答题记录、新增 `reset_user()`
    统一复位，测试可重复执行（42 项全通过，连续两次结果一致）；
  - 新增前端「任务轨迹」页 `/agent-tasks`：提交需求、历史任务、执行步骤、
    Self-Loop 轮次（失败类型 / 修正前后数量 / 执行动作 / 复验结论）、落库校验记录与执行日志；
  - 新增 `frontend/src/api/agentTasks.ts`，对接 `/api/agent/tasks` 全套接口
    （列表 / 详情 / 提交 / 取消 / 恢复）。
- **第九阶段验收结果**：`test_self_loop.py` 42/42；第三～八阶段回归
  19 / 28 / 26 / 29 / 79 / 33 / 57 / 42 / 19 项全部通过；
  `test_question_count_guarantee.py` 26/26、`test_agent_platform.py` 19/19。
- **遗留问题**（既有数据态，非本次修改引入）：
  - 未指定知识点的出题请求会落到学科下第一个知识点；若该知识点题库已饱和
    （如演示数据中的「集合」），关闭 LLM 时出题会 0 道 —— 建议后续按薄弱点 / 最近练习知识点选点；
  - `test_master_agent.py` 有 3 项受此影响（`出题-数量与参数准确`、`部分成功-数量如实`、
    `部分成功-摘要使用真实数字`）；
  - `test_api.py` 因演示账号考试日期已过期（Dashboard `exam=None`）在打印阶段报 `TypeError`，
    重建演示数据后可运行。

- **多选题兜底 + partial 状态展示**（第六阶段遗留问题）：
  - 内置题库由 19 道扩充到 25 道，新增 6 道多选题（集合/关系/函数/图论/树/命题逻辑各 1，答案均为 3 个正确项）；
  - 题库兜底支持按题型过滤，`question_types=["multiple_choice"]` 时不再返回 0 道；
  - 后端 CORS 增加 `expose_headers`（`X-Agent-*`），并新增 `X-Agent-Reason` 响应头（URL 编码）；
  - 练习页新增生成结果提示（成功/部分成功/失败），补充多选题复选框渲染与作答；
  - 修复前端生成请求超时（30s → 180s，AI 出题较慢会被中断）；
  - 测试：单元 79 项、HTTP 33 项，并通过浏览器实测三种状态与多选作答。
- 练习生成 Agent 收尾（仍属第六阶段）：
  - 新增 **LLM 失败时的题库兜底**：复用 `QuestionService.bank_fallback_items`
    （由原 `_generate_from_bank` 抽出，支持排除题库/库内已有题干、按题型筛选），
    兜底题目同样经过字段校验、任务内去重和库内去重，不足时返回 `partial`；
  - `/api/questions/generate` 改为统一调用练习生成 Agent（保持原路径、请求体与响应体兼容），
    执行状态通过 `X-Agent-Status` 等响应头回传；请求体新增可选
    `question_types` / `use_weak_points` / `knowledge_point`；
  - 部分成功继续落库已校验题目，`status=partial` 并如实返回 `requested_count` / `actual_count`；
  - 新增 HTTP 接入测试 `test_question_agent_http.py`（23 项），单元测试扩至 73 项。

### 2026-11-14

- **第六阶段（练习生成 Agent）完善**（`app/agents/question_generation_agent.py`）：
  - 新增参数：`question_types`（单选/多选/判断/简答，支持中文与列表/逗号串）、
    `difficulty`（easy/medium/hard 与简单/中等/困难）、`use_weak_points`（是否结合薄弱知识点）；
  - 校验增强：题型必须命中用户要求、选项 2~5 个、答案字母/判断值/简答答案合法、解析必填、难度字段合法；
  - 去重升级：任务内重复 + **数据库同知识点已有题目**双重判重，重复题不计入有效数量；
  - 落库改为复用 `QuestionService.save_questions`（单一事务，失败回滚，只增不删）；
  - 结果三态：`success` / `partial`（保存已生成的有效题目并如实报告 n/m）/ `failed`，
    输出补充 `status`、`requested_count`、`actual_count`、`attempts`、`invalid_count`、
    `duplicate_count`、`questions`、`execution_time`、`logs`；
  - 新增 `app/agents/registration.py`：统一注册练习生成等专业 Agent，`create_app()` 启动时幂等注册；
  - 测试扩充至 65 项（题型参数、中文难度、关闭弱项、库内去重、部分成功、注册表、参数校验等）。
- 新增**结果验证 Agent**（`app/agents/result_validation_agent.py`）：
  - 支持 `question_set` / `study_plan` / `learning_analysis` / `knowledge_retrieval` / `generic` 五类目标；
  - 程序化校验数量、字段、题型、选项、去重、每日时长、落库与归属一致性；
  - 校验分层（critical / warning），失败输出 `issues` + `suggestions` 供 Self-Loop 使用；
  - 只读、不抛异常，LLM 辅助评分默认关闭（`use_llm=True` 才调用）；
  - 配套测试 `test_result_validation_agent.py`（53 项）。
- 修复**练习生成数量不达标**（`/api/questions/generate` 链路）：
  - 旧实现整批请求 + 整批 Pydantic 校验，题量偏大导致 JSON 截断、单题题型异常导致整批作废；
  - 现改为分片请求（每片 ≤5 道）+ 逐条宽容解析 + 题型/难度/答案归一化；
  - 数量不足按缺口多轮补题（最多 3 轮），仍不足按「本知识点 → 同学科 → 全库」用真实题库补齐；
  - 题干归一化去重，题库不足时如实返回实际数量，不编造、不重复；
  - 新增回归测试 `test_question_count_guarantee.py`（26 项）。
- 练习生成 Agent 同步改为分片请求，避免同类问题。
- 修复**推理模型出题返回空内容**：
  - 原因：`deepseek-flash` 属推理模型，token 预算先被 `reasoning_content` 消耗，
    `message.content` 为空，导致每次都降级到内置题库；
  - `LLMService.chat` 增加空内容兜底：检测到空内容时自动放大预算（最高 16000）重试一次，
    并把请求超时放宽到 120s；
  - 出题侧默认预算提升为 `max(3000, 题量 × 800)`，`structured_output` 支持自定义 `max_tokens`；
  - 实测：`count=5` 返回 5 道、`count=10` 返回 10 道，`source` 均为 `ai`。