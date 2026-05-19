# Local Knowledge RAG Workbench

这是一个面向本地部署的私有资料问答系统。你可以上传 PDF、Word、PPT、Markdown 或 TXT 文档，系统会把文档切片、写入向量库，并在聊天时优先检索当前账号上传的资料，再组织成回答。

本仓库已经针对 Windows 本地运行做过适配：可以不安装 MySQL、Redis、Docker 或 Ollama，直接使用 SQLite、进程内缓存和阿里百炼 DashScope API 跑通完整流程。

## 适合做什么

- 个人资料库问答：论文、课程资料、读书笔记、技术文档。
- 企业内部文档问答：制度、产品手册、培训材料、项目文档。
- 客服或售前知识库原型：上传产品资料后按文档内容回答。
- RAG 学习项目：查看文档切片、向量检索、BM25 检索、重排序、流式回答的完整链路。

它不是联网搜索工具。系统主要回答来自你上传的资料。

## 功能概览

- 用户注册、登录和 JWT 鉴权。
- 每个用户拥有独立知识库，检索时按 `user_id` 隔离。
- 支持上传 `.pdf`、`.txt`、`.md`、`.docx`、`.pptx`。
- 支持文档切片、MD5 去重、文档列表、切片查看和删除。
- 使用 ChromaDB 做向量库。
- 使用向量检索 + BM25 关键词检索的混合检索。
- 查询时使用 HyDE 思路增强检索。
- 支持重排序和流式回答。
- 前端提供聊天、资料库、会话记录、个人中心页面。

## 本地访问地址

本地默认端口如下：

| 服务 | 地址 | 说明 |
| --- | --- | --- |
| 前端 | `http://127.0.0.1:3010/` | Vue + Vite 页面 |
| FastAPI 后端 | `http://127.0.0.1:8010` | 聊天、RAG、知识库接口 |
| Django 用户服务 | `http://127.0.0.1:8011` | 注册、登录、用户资料接口 |

如果你机器上端口冲突，可以改启动命令中的端口，同时同步修改前端代理环境变量。

## 技术结构

```text
front/                Vue 3 前端
backend/              FastAPI + LangChain RAG 服务
DjangoUserService/    Django 用户服务
backend/data/         本地向量库、SQLite、上传资料缓存，默认不提交
```

核心调用链：

```text
用户提问
  -> FastAPI 鉴权
  -> 按 user_id 检索当前用户文档
  -> HyDE 生成检索查询
  -> Chroma 向量检索 + BM25 关键词检索
  -> 文档重排序
  -> 大模型总结回答
  -> SSE 流式返回前端
```

## 环境要求

建议环境：

- Windows 10/11
- Python 3.11
- Node.js 18 或更新版本
- Git
- `uv`
- 阿里百炼 / DashScope API Key

安装 `uv`：

```powershell
py -m pip install uv -i https://pypi.tuna.tsinghua.edu.cn/simple
```

确认命令可用：

```powershell
py --version
node --version
npm.cmd --version
uv --version
```

## 克隆项目

```powershell
git clone https://github.com/yuchen123hh/LangChain-RAG-FastAPI-Service-local.git
cd LangChain-RAG-FastAPI-Service-local
```

## 配置 API Key

本地运行使用你电脑环境变量里的 `DASHSCOPE_API_KEY`。不要把真实 API Key 写进 Git 仓库。

当前 PowerShell 临时配置：

```powershell
$env:DASHSCOPE_API_KEY="你的阿里百炼APIKey"
```

如果要长期生效，可以在 Windows 系统环境变量里添加 `DASHSCOPE_API_KEY`。

后端代码也兼容 `ALIYUN_ACCESS_KEY_SECRET`，但本仓库推荐使用 `DASHSCOPE_API_KEY`，避免把 key 写到 `.env`。

## 安装依赖

### FastAPI 后端

```powershell
cd backend
uv sync --python 3.11
```

### Django 用户服务

```powershell
cd ..\DjangoUserService
uv sync --python 3.11
```

### 前端

```powershell
cd ..\front
npm.cmd ci
```

## 创建本地配置文件

`.env` 文件只用于本地运行，已经被 `.gitignore` 忽略。

### `backend\.env`

```env
LLM_TYPE=ALIYUN
ALIYUN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
CHAT_MODEL_NAME=qwen3-max

EMBED_MODEL_TYPE=ALIYUN
ALIYUN_EMBED_MODEL_NAME=text-embedding-v4

VISION_MODEL_TYPE=ALIYUN
VISION_CHAT_MODEL_NAME=qwen-vl-max

DB_ENGINE=sqlite
SQLITE_DATABASE=data/chat_history.sqlite3

REDIS_BACKEND=memory
RATE_LIMIT_ENABLED=false

DJANGO_API_URL=http://127.0.0.1:8011

LANGCHAIN_TRACING_V2=false
SKIP_RERANKER_MODEL_CHECK=true

SECRET_KEY=MY_LOCAL_JWT_SECRET_CHANGE_ME
ALGORITHM=HS256
```

### `DjangoUserService\.env`

```env
JWT_SECRET_KEY=MY_LOCAL_JWT_SECRET_CHANGE_ME

DB_ENGINE=sqlite
SQLITE_DATABASE=data/user_service.sqlite3

REDIS_BACKEND=memory
CELERY_BROKER_URL=memory://
CELERY_RESULT_BACKEND=cache+memory://
REDIS_CACHE_URL=redis://localhost:6379/1
```

注意：`backend\.env` 的 `SECRET_KEY` 必须和 `DjangoUserService\.env` 的 `JWT_SECRET_KEY` 完全一致，否则登录后的 token 不能被 FastAPI 验证。

## 初始化数据库

用户服务第一次运行前需要迁移数据库：

```powershell
cd DjangoUserService
.\.venv\Scripts\python.exe manage.py migrate
```

本地 SQLite 文件会生成在：

```text
DjangoUserService/data/user_service.sqlite3
```

聊天历史 SQLite 会在 FastAPI 启动时自动创建：

```text
backend/data/chat_history.sqlite3
```

这些本地数据文件不会被提交。

## 启动服务

打开三个 PowerShell 终端，分别执行下面命令。

### 1. 启动 Django 用户服务

```powershell
cd D:\codex\LangChain-RAG-FastAPI-Service-master\DjangoUserService
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8011 --noreload
```

### 2. 启动 FastAPI 后端

```powershell
cd D:\codex\LangChain-RAG-FastAPI-Service-master\backend
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8010
```

### 3. 启动前端

```powershell
cd D:\codex\LangChain-RAG-FastAPI-Service-master\front
$env:VITE_BACKEND_TARGET="http://127.0.0.1:8010"
$env:VITE_USER_SERVICE_TARGET="http://127.0.0.1:8011"
npm.cmd run dev -- --host 127.0.0.1 --port 3010
```

浏览器打开：

```text
http://127.0.0.1:3010/
```

## 使用流程

1. 打开前端页面。
2. 注册账号或使用测试账号登录。
3. 进入“资料库”页面。
4. 上传 PDF、Word、PPT、Markdown 或 TXT。
5. 等待切片和索引完成。
6. 回到“问答”页面。
7. 提问和上传资料相关的问题。
8. 查看回答中的检索轨迹和会话记录。

## 验证服务是否正常

FastAPI 健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8010/health/live
Invoke-RestMethod http://127.0.0.1:8010/health/ready
```

前端检查：

```powershell
Invoke-WebRequest http://127.0.0.1:3010/
```

用户接口可以通过注册和登录验证：

```powershell
$body = @{
  username = "demo_user"
  email = "demo_user@example.com"
  telephone = "13900000001"
  password = "123456"
  confirm_password = "123456"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://127.0.0.1:8011/user/register/" -Method POST -Body $body -ContentType "application/json"
```

## 本地开发模式和生产模式的区别

本地开发默认：

- `DB_ENGINE=sqlite`
- `REDIS_BACKEND=memory`
- `EMBED_MODEL_TYPE=ALIYUN`
- `SKIP_RERANKER_MODEL_CHECK=true`

这样可以快速跑通，不需要安装 MySQL、Redis、Docker 或本地模型。

如果要部署到更正式的环境，建议改回：

- MySQL 保存用户和会话数据
- Redis 做缓存、限流和 token 黑名单
- 单独准备模型缓存目录
- 使用稳定的进程管理工具运行 FastAPI、Django 和前端构建产物

## 常见问题

### 1. 登录后聊天接口返回 401

检查两个 `.env` 里的 JWT 密钥是否一致：

```text
backend SECRET_KEY
DjangoUserService JWT_SECRET_KEY
```

### 2. 大模型调用失败

确认本机有 `DASHSCOPE_API_KEY`：

```powershell
echo $env:DASHSCOPE_API_KEY
```

如果为空，需要重新配置。

### 3. 前端能打开但接口不通

检查三个服务是否都在监听：

```powershell
netstat -ano | Select-String ':8010|:8011|:3010'
```

同时确认前端启动时设置了：

```powershell
$env:VITE_BACKEND_TARGET="http://127.0.0.1:8010"
$env:VITE_USER_SERVICE_TARGET="http://127.0.0.1:8011"
```

### 4. 上传文档后问答没有检索结果

先确认：

- 已登录。
- 文档上传成功。
- 上传的是支持格式。
- 提问内容和文档内容相关。
- 当前账号和上传账号是同一个。

知识库按用户隔离，不会检索其他用户上传的资料。

### 5. 不想每次都开三个终端

可以用 PowerShell 脚本或进程管理工具封装启动命令。当前仓库先保留显式启动方式，便于调试。

## 文件不会提交的内容

`.gitignore` 已经排除：

- `.env`
- `.venv/`
- `node_modules/`
- `dist/`
- `data/`
- `logs/`
- `*.sqlite3`
- Python 缓存文件

因此 API Key、本地数据库、上传资料、向量库和日志不会进入 GitHub。

## 更多说明

本地启动命令也整理在：

[LOCAL_DEPLOY.md](./LOCAL_DEPLOY.md)
