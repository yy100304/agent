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
