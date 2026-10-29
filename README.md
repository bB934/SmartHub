# SmartHub — 企业级 RAG 知识库

基于 **FastAPI + Vue 3** 的企业级检索增强生成（RAG）知识库系统，支持多租户、文档可见性控制、向量与全文混合检索、流式问答与引用溯源。

## 技术栈

| 层 | 选型 |
|---|---|
| 后端框架 | FastAPI + Uvicorn |
| 关系型存储 | MySQL + SQLAlchemy 2.x + Alembic |
| 向量库 | Milvus（2048 维） |
| 全文检索 | Elasticsearch |
| 任务队列 | Celery + Redis（本地回退 BackgroundTasks） |
| Embedding | OpenRouter `nvidia/nemotron-3.5-embed-1b:free`（2048 维） |
| 生成 LLM | OpenRouter `recursive/flint-v1.0:free` |
| 重排序 | OpenRouter `nvidia/nemotron-3.5-rerank-8b:free` |
| 前端 | Vue 3 + Vite + Vue Router |
| 监控 | prometheus-fastapi-instrumentator（`/metrics`） |

## 目录结构

```
SmartHub/
├── app/
│   ├── api/v1/          # 文档上传 / 问答流式 / 混合检索
│   ├── core/            # 配置、上下文（租户头）、ACL
│   ├── db/              # MySQL / Milvus / ES 客户端
│   ├── ingest/          # 解析、切片、入库流水线（蓝绿切换）
│   ├── llm/             # LLM 网关、提示词、语义缓存
│   ├── rag/             # 向量化
│   ├── retrieve/        # 混合召回 + RRF 融合 + 精排
│   ├── tasks/           # Celery 任务与任务仓储
│   └── models/          # SQLAlchemy 模型
├── frontend/            # Vue 3 前端
├── migrations/          # Alembic 迁移
├── requirements.txt
├── .env.example
└── test_main.http       # 接口自测（PyCharm / REST Client）
```

## 快速开始

### 1. 环境准备

- Python 3.11+
- MySQL 8 / Milvus / Elasticsearch 8 / Redis（可用 Docker 起）

### 2. 后端

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# 编辑 .env，填入 OPENROUTER_API_KEY 及各存储地址

alembic upgrade head       # 建表
uvicorn app.main:app --port 8000 --reload
```

接口文档：http://127.0.0.1:8000/api/docs
健康检查：http://127.0.0.1:8000/health

### 3. 前端

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173，默认代理到 8000
```

生产构建：

```bash
cd frontend && npm run build
# 构建后 FastAPI 会直接托管 frontend/dist，访问 http://127.0.0.1:8000 即可
```

## 核心流程

**文档入库**：上传 → 解析（pdf/docx/md/txt）→ 切片 → 向量化 → 双写 ES + Milvus（新版本）→ 蓝绿切换 → 旧版本清理。

**问答**：用户问题向量化 → ES + Milvus 混合召回 → RRF 融合 → rerank 精排 → 拼装带编号出处的 prompt → LLM 流式生成 → 句末 `[1][2]` 标注引用 → 语义缓存。

## 配置说明

所有配置均通过 `.env` 注入，详见 [.env.example](.env.example)。关键项：

| 变量 | 说明 |
|---|---|
| `OPENROUTER_API_KEY` | embedding / LLM / rerank 共用的 Key |
| `MYSQL_URL` | 关系库连接串 |
| `MILVUS_URI` | 向量库地址 |
| `ES_URL` | 全文检索地址 |
| `REDIS_URL` | Celery broker / backend |

## 接口概览

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/doc/upload` | 上传文档并触发入库 |
| GET | `/api/v1/doc` | 文档列表 |
| GET | `/api/v1/doc/{id}/task` | 入库任务进度 |
| DELETE | `/api/v1/doc/{id}` | 删除文档及索引 |
| POST | `/api/v1/search` | 混合检索 |
| POST | `/api/v1/chat/stream` | 流式问答（SSE） |

## License

MIT
