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
│   │   ├── tools/          # Agent Tools
│   │   ├── rag/            # RAG 与向量库
│   │   └── utils/          # 工具函数
│   ├── requirements.txt
│   └── .env.example
├── frontend/               # Vue 3 前端
│   ├── src/
│   │   ├── api/            # API 调用封装
│   │   ├── components/     # 通用组件
│   │   ├── router/         # 路由
│   │   ├── stores/         # Pinia 状态
│   │   ├── styles/         # 全局样式
│   │   ├── utils/          # 工具
│   │   └── views/          # 页面
│   └── package.json
├── data/                   # 数据库与上传文件
├── docs/                   # 项目文档
└── README.md
```

## 启动方式

### 后端

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API 文档：`http://localhost:8000/docs`

### 前端

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

前端默认运行在 `http://localhost:5173`。

## 开发阶段计划

- [x] **阶段一**：项目骨架、登录注册、基础 Dashboard
- [ ] **阶段二**：LLM Service 接入
- [ ] **阶段三**：StudyAgent + 5 个核心 Tool
- [ ] **阶段四**：RAG 知识库（PDF 上传 + 向量检索）
- [ ] **阶段五**：练习系统（AI 出题、自动批改、错题本）
- [ ] **阶段六**：学习画像 + 学习统计
- [ ] **阶段七**：自动调整学习计划

## 创新点

1. **目标驱动的学习 Agent**：从「回答问题」升级为「主动执行学习任务」
2. **多工具协同**：Agent 调用 5 个学习工具完成任务
3. **个人学习画像**：基于真实学习数据构建
4. **RAG + 个人课程资料**：结合用户自己的学习材料
5. **反馈驱动的自适应**：根据学习结果自动调整学习计划