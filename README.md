# 本地 RAG 医疗问答系统

这是一个可以在 Windows 本地运行的医疗知识问答系统。用户登录后可以直接提问常见疾病、症状判断、检查方向、用药注意事项、复诊条件等问题；系统会先检索本地医疗语料，再调用大模型生成回答。

项目默认使用阿里百炼 DashScope 大模型，API Key 从本机环境变量读取。仓库内置 10 万条医疗知识卡 Markdown 语料，直接走本地关键词检索，不需要先导入向量库，也不会因为导入语料产生 embedding 费用。

> 注意：本项目适合学习、毕业设计、RAG 原型验证和健康科普场景，不替代执业医师诊断、处方或急救指导。

## 主要功能

- 本地医疗问答：围绕常见疾病、常见症状、检查方向、危险信号和就诊科室进行问答。
- 内置医疗语料：仓库自带 10 万条知识卡，覆盖呼吸、心血管、消化、内分泌、神经、泌尿、骨科、皮肤、感染、儿科、妇产科、五官、心理睡眠等方向。
- 资料库上传：支持 PDF、TXT、Markdown、Word、PPT，上传后可切片并写入 Chroma 向量库。
- 混合检索：内置 Markdown 关键词检索 + Chroma 向量检索 + SQLite 关键词检索。
- 流式回答：前端实时显示回答内容和检索轨迹。
- 用户系统：Django 提供注册、登录、JWT 鉴权；FastAPI 负责 RAG 和聊天接口。
- 本地即用：默认 SQLite 和内存缓存，不强制安装 MySQL、Redis、Docker。

## 技术栈

| 模块 | 技术 |
| --- | --- |
| 前端 | Vue 3、Vite、Vant、Pinia |
| RAG 后端 | FastAPI、LangChain、ChromaDB、SQLite |
| 用户服务 | Django、Django REST Framework、JWT |
| 大模型 | 阿里百炼 DashScope，默认 `qwen3-max` |
| Embedding | 阿里百炼 `text-embedding-v4`，仅上传新文档或手动导入向量时使用 |
| 本地语料检索 | Markdown 知识卡 + 自定义关键词检索器 |

## 目录说明

```text
front/                         前端页面
backend/                       FastAPI RAG 服务
DjangoUserService/             Django 用户服务
docs/rag_test_corpus/split_100k 内置 10 万条医疗语料，已拆分为 20 个 Markdown 文件
scripts/                       Windows 一键安装、启动、停止脚本
tools/                         语料生成和可选向量导入工具
```

## 运行环境

建议使用：

- Windows 10/11
- Python 3.11
- Node.js 18 或更高版本
- Git
- 阿里百炼 DashScope API Key

检查环境：

```powershell
py --version
node --version
npm.cmd --version
git --version
```

## 1. 克隆项目

```powershell
git clone https://github.com/yuchen123hh/Local-Medical-RAG-QA.git
cd Local-Medical-RAG-QA
```

## 2. 配置 API Key

系统会从环境变量读取你的 DashScope API Key，不需要写进代码。

临时配置，只在当前 PowerShell 窗口生效：

```powershell
$env:DASHSCOPE_API_KEY="你的阿里百炼APIKey"
```

长期配置，写入当前 Windows 用户环境变量：

```powershell
[Environment]::SetEnvironmentVariable("DASHSCOPE_API_KEY", "你的阿里百炼APIKey", "User")
```

配置后重新打开 PowerShell，再检查：

```powershell
$env:DASHSCOPE_API_KEY
```

## 3. 一键安装依赖

首次运行执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
```

这个脚本会完成：

- 安装 `uv`。
- 复制 `backend/.env.example` 为 `backend/.env`。
- 复制 `DjangoUserService/.env.example` 为 `DjangoUserService/.env`。
- 安装 FastAPI 后端依赖。
- 安装 Django 用户服务依赖。
- 执行 Django 数据库迁移。
- 安装前端依赖。

如果你只想安装后端和用户服务，可以跳过前端：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1 -SkipFrontend
```

## 4. 启动系统

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_all_windows.ps1
```

默认地址：

| 服务 | 地址 |
| --- | --- |
| 前端页面 | `http://127.0.0.1:3010/` |
| FastAPI 接口文档 | `http://127.0.0.1:8010/docs` |
| Django 用户服务 | `http://127.0.0.1:8011` |

停止服务：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stop_all_windows.ps1
```

## 5. 使用方法

1. 打开 `http://127.0.0.1:3010/`。
2. 注册一个账号并登录。
3. 进入聊天页面，直接提问，例如：
   - `感冒头晕鼻塞怎么办，需要吃什么药吗？`
   - `高血压平时要注意哪些指标？`
   - `孩子发热咳嗽什么时候需要去医院？`
   - `糖尿病人脚麻要考虑什么问题？`
4. 进入资料库页面，可以看到内置医疗知识库。
5. 如需加入自己的资料，点击资料库上传 PDF、Word、PPT、Markdown 或 TXT。

## 内置医疗语料说明

语料位置：

```text
docs/rag_test_corpus/split_100k/
```

这批语料被拆成 20 个 Markdown 文件，每个文件约 5000 条知识卡，总量约 10 万条。每条知识卡包含：

- 疾病所属系统
- 疾病名称
- 使用场景
- 适用人群
- 风险分层
- 常见表现
- 辅助检查
- 鉴别方向
- 处理原则
- 危险信号
- 建议就诊科室
- RAG 检索关键词

为了让项目从 GitHub 下载后更容易运行，系统默认直接检索这些 Markdown 文件，而不是要求你先把 10 万条语料导入 Chroma。这样启动快，也不会产生 embedding 导入费用。

## 是否需要导入向量库

默认不需要。

内置医疗语料已经可以直接参与问答。只有你想测试“10 万条语料全部写入 Chroma 向量库”的效果时，才需要运行可选导入脚本：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\import_medical_corpus_windows.ps1
```

注意：这个脚本会调用 embedding API，可能产生费用。导入后的 Chroma 数据会保存在 `backend/data/chromadb/`，这个目录不会提交到 GitHub。

## API Key 和费用

- 聊天回答会调用大模型 API，可能产生模型调用费用。
- 默认内置医疗语料检索不调用 embedding，不产生导入费用。
- 上传你自己的新文档时，系统会为新文档生成 embedding，可能产生费用。
- 仓库不会提交真实 API Key。请在本机环境变量 `DASHSCOPE_API_KEY` 中配置。

## 常见问题

### 1. 登录后问答报 401 或 403

确认 backend/.env 里的 `SECRET_KEY` 和 DjangoUserService/.env 里的 `JWT_SECRET_KEY` 完全一致。默认模板里已经一致，不要只改其中一个。

### 2. 资料库显示为空

正常情况下会显示“内置医疗知识库｜常见疾病诊疗语料（100000条）”。如果没有显示，检查：

```powershell
Test-Path docs\rag_test_corpus\split_100k
```

并确认 `backend/.env` 中：

```env
BUILTIN_MEDICAL_CORPUS_ENABLED=true
```

### 3. 提问没有医疗知识库效果

先确认 FastAPI 后端正在运行，并查看日志：

```powershell
Get-Content logs\fastapi-rag-service.err.log -Tail 80
Get-Content logs\fastapi-rag-service.out.log -Tail 80
```

也可以直接打开 `http://127.0.0.1:8010/docs` 测试接口。

### 4. 端口被占用

改启动端口：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_all_windows.ps1 -BackendPort 8020 -UserPort 8021 -FrontPort 3020
```

### 5. 不想使用阿里百炼

可以改 `backend/.env`，把 `LLM_TYPE` 和 `EMBED_MODEL_TYPE` 都设置为 `OLLAMA`，并提前准备好本地 Ollama 模型。这个模式适合完全离线测试，但模型效果取决于本机显卡和模型大小。

## 重要声明

本项目输出内容只用于知识检索和健康科普参考，不构成诊断、处方、治疗方案或急救指导。真实患者应咨询执业医师；出现胸痛、呼吸困难、意识障碍、严重出血、持续高热、抽搐、偏瘫、剧烈腹痛等危险信号时，应立即就医。
