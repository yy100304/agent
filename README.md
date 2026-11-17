# 智学 Agent · StudyFlow Agent

> 一个能感知学习状态、自己排计划、调用学习工具、校验结果并在失败时自我修正的个人学习 Agent。

普通 AI 是「问一句答一句」；**智学 Agent** 是「提一个学习目标 → 感知学情 → 自主规划 → 调用工具执行 → 结果校验 → 失败自动补做 → 更新学习画像」。

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![Vue](https://img.shields.io/badge/Vue-3-42B883?logo=vue.js&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)

## 在线体验

> 部署完成后这里会给出公开地址；本地开发见下节。

- 演示账号：`demo / demo123`（首次启动自动写入演示数据）
- 也可以直接在登录页注册新账号

## 功能一览

| 模块 | 能力 |
|---|---|
| AI 对话（Agent） | 自然语言提需求，主控 Agent 拆解意图、调度专业 Agent、流式返回 |
| 学习计划 | 自己新建计划、手写「计划内容」与每日任务；也可让 Agent 生成，支持考试倒计时、打卡、进度 |
| 练习 | 按知识点 / 题型 / 难度出题，数量不达标自动补题，LLM 不可用时回退内置题库 |
| 错题本 | 错因归类、重做、掌握度追踪 |
| 知识库（RAG） | 上传 TXT/MD/CSV/JSON/PDF/DOCX（扫描版 PDF 支持 OCR）→ 切块入库 → 检索增强讲解 |
| 任务轨迹 | 每一步执行、Self-Loop 修正轮次、落库校验与日志全过程可追溯 |
| 数据看板 | 学习时长、正确率、薄弱点画像 |

## 技术栈

- **前端**：Vue 3 + Vite + TypeScript + Element Plus + Pinia + ECharts
- **后端**：FastAPI + Pydantic v2 + SQLAlchemy 2 + SQLite（可切 MySQL）+ JWT
- **Agent**：自研多 Agent 框架（注册表 / 状态机 / 超时重试 / 结构化日志）+ 工作流引擎 + Self-Loop（失败分类 → 修正策略 → 复验）
- **RAG**：文档解析切块 + 关键词/向量检索（Chroma 可选）
- **LLM**：任意 OpenAI 兼容接口（OpenAI / DeepSeek / 通义 等），**不配置 Key 也能完整体验**（自动降级题库 + 规则讲解）

## 快速开始

### 方式一：Docker 一条命令（推荐，前后端同一个端口）

```bash
git clone https://github.com/yy100304/agent.git
cd agent

docker build -t studyflow-agent .
docker run -d --name studyflow -p 8000:8000 \
  -e SECRET_KEY="$(python -c 'import secrets;print(secrets.token_urlsafe(48))')" \
  -v "$PWD/data:/app/backend/data" \
  studyflow-agent
```

打开 <http://localhost:8000> 即可（后端同时托管前端页面与 `/api`）。
需要 AI 能力时追加 `-e LLM_API_KEY=sk-xxx -e LLM_BASE_URL=https://api.deepseek.com/v1 -e LLM_MODEL=deepseek-chat`。

### 方式二：本地开发（前后端分离 + 热更新）

```bash
# 后端
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows；macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # 按需填 LLM_API_KEY
python seed_demo.py             # 可选：写入演示数据（demo/demo123）
python run.py                   # http://127.0.0.1:8000

# 前端（另开一个终端）
cd frontend
npm install
cp .env.example .env
npm run dev                     # http://localhost:5173（/api 由 Vite 代理到 8000）
```

Windows 也可直接双击 `start-dev.bat` 一键拉起前后端。

## 部署到公网（让任何人都能打开链接使用）

镜像自带前端构建产物，**一个容器 = 一个网址**，无需再单独部署静态站点。

### 1. 云托管 / 容器平台（最省事）

| 平台 | 步骤 |
|---|---|
| 腾讯云 CloudBase 云托管 / 阿里云 SAE | 选「容器镜像」→ 关联 GitHub 仓库（自动按 `Dockerfile` 构建）→ 端口填 `8000` → 加环境变量 |
| Render / Railway / Fly.io | 新建 Web Service → 连接仓库 → 平台识别 `Dockerfile` → 设置环境变量与持久盘（挂到 `/app/backend/data`） |
| 任意云服务器 | `docker run -d -p 80:8000 --restart=always ...`，前面套 Nginx + HTTPS |

必填环境变量：

```env
SECRET_KEY=<随机长串>
APP_ENV=production
DEBUG=false
LLM_API_KEY=<你的 key，可留空>
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
CORS_ORIGINS=["https://你的域名"]      # 同源部署可省略
```

> **数据持久化**：SQLite 库、上传文件、日志都在 `/app/backend/data`，平台若提供磁盘请挂载到该目录；
> 没有持久盘时数据会在重启后恢复到初始演示状态（体验不受影响）。
> 也可把 `DATABASE_URL` 指向 MySQL / PostgreSQL 等外部数据库。

### 2. 反向代理示例（自有服务器）

```nginx
server {
    listen 80;
    server_name study.example.com;
    client_max_body_size 120M;          # 知识库上传上限
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;        # Agent 生成较慢
    }
}
```

`docker run` 时不要漏 `--proxy-headers`（Dockerfile 已内置）。

## 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `APP_ENV` / `DEBUG` | `development` / `True` | 生产请设为 `production` / `false` |
| `SECRET_KEY` | 占位值 | JWT 签名密钥，**公网部署必须改** |
| `DATABASE_URL` | `sqlite:///../data/studyflow.db` | 支持任意 SQLAlchemy URL |
| `FRONTEND_DIST` | 自动探测 `frontend/dist` | 前端产物目录 |
| `CORS_ORIGINS` | `localhost:5173` | JSON 数组；同源部署无需配置 |
| `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` | 空 / OpenAI | 留空则走内置题库与规则讲解 |
| `AGENT_STREAM_TOKENS` | `true` | token 级流式输出（首字更快） |
| `AGENT_LLM_VALIDATION` | `false` | 是否额外用 LLM 做结果评分 |
| `UPLOAD_DIR` / `LOG_DIR` / `CHROMA_PERSIST_DIR` | `../data/*` | 相对 `backend/` 运行目录 |
| `MAX_UPLOAD_SIZE_MB` | `20` | 单文件上传上限 |

## 目录结构

```
agent/
├── backend/
│   ├── app/
│   │   ├── api/          # 路由：auth / questions / study_plans / knowledge_docs / agent_tasks …
│   │   ├── agents/       # 多 Agent：学情分析、检索、计划、出题、结果验证、主控、工作流
│   │   ├── core/         # 配置、安全、日志
│   │   ├── models/       # SQLAlchemy 模型
│   │   ├── schemas/      # Pydantic 模型
│   │   ├── services/     # 业务服务（题库、学习记录、资料解析…）
│   │   └── main.py       # FastAPI 入口（含前端静态托管）
│   ├── requirements.txt
│   ├── run.py            # 本地启动
│   └── seed_demo.py      # 演示数据
├── frontend/
│   └── src/{api,components,router,stores,styles,views}
├── docs/                 # 架构说明与更新记录
├── Dockerfile            # 单镜像：构建前端 + 运行后端
└── README.md
```

## 主要接口

| 分组 | 路径 | 说明 |
|---|---|---|
| 鉴权 | `POST /api/auth/register`、`POST /api/auth/login` | JWT（Bearer） |
| Agent | `POST /api/agent/tasks` | 提交自然语言任务，返回执行计划 / 步骤 / Self-Loop / 校验 |
| 学习计划 | `GET/POST /api/study-plans`、`PATCH/DELETE /api/study-plans/{id}` | 计划列表、创建、修改、删除 |
| 计划任务 | `POST /api/study-plans/{id}/tasks`、`PATCH/DELETE /api/study-plans/tasks/{id}`、`PUT /api/tasks/{id}/complete` | 手写任务、改期、打卡 |
| 练习 | `POST /api/questions/generate` | 出题（状态经 `X-Agent-*` 响应头回传） |
| 知识库 | `/api/knowledge-docs/*` | 上传、列表、详情、检索、删除 |
| 健康检查 | `GET /health` | 平台探活 |

完整契约见运行后的 `/docs`（Swagger UI）。

## 测试

`backend/test_*.py` 为一组可独立运行的验收脚本：

```powershell
cd backend
$env:PYTHONIOENCODING="utf-8"
.\.venv\Scripts\python.exe test_self_loop.py
```

脚本最后输出 `结果: N 通过, M 失败`，退出码非 0 即失败。覆盖 Agent 框架、五类专业 Agent、主控编排、工作流 Self-Loop、题库兜底、HTTP 接入等。

## 文档

- [`docs/architecture.md`](docs/architecture.md)：模块划分与 Agent 编排设计
- [`docs/CHANGELOG.md`](docs/CHANGELOG.md)：版本更新记录与遗留问题

## 开源协议

[MIT](LICENSE) © 2026 yy100304
