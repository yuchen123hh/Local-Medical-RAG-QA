# 本地部署速查

## 第一次安装

```powershell
git clone https://github.com/yuchen123hh/Local-Medical-RAG-QA.git
cd Local-Medical-RAG-QA
[Environment]::SetEnvironmentVariable("DASHSCOPE_API_KEY", "你的阿里百炼APIKey", "User")
powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
```

重新打开 PowerShell 后启动：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_all_windows.ps1
```

访问：

```text
http://127.0.0.1:3010/
```

## 日常启动

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_all_windows.ps1
```

## 停止服务

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stop_all_windows.ps1
```

## 日志位置

```text
logs/django-user-service.out.log
logs/django-user-service.err.log
logs/fastapi-rag-service.out.log
logs/fastapi-rag-service.err.log
logs/vue-frontend.out.log
logs/vue-frontend.err.log
```

## 语料说明

项目内置 10 万条医疗知识卡，位于：

```text
docs/rag_test_corpus/split_100k/
```

默认直接检索这些 Markdown 语料，不需要导入向量库，不产生 embedding 导入费用。

可选导入 Chroma：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\import_medical_corpus_windows.ps1
```

这个导入会调用 embedding API，可能产生费用。
