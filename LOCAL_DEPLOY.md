# Local Deployment

This project is configured to run locally without external MySQL or Redis.

## Services

- FastAPI backend: http://127.0.0.1:8010
- Django user service: http://127.0.0.1:8011
- Vue frontend: http://127.0.0.1:3010

## Local Runtime Choices

- Python services use Python 3.11 virtual environments created by `uv`.
- `backend/.env` maps the Aliyun/DashScope API key from your shell environment. Keep `DASHSCOPE_API_KEY` configured locally.
- `DB_ENGINE=sqlite` is used for local development.
- `REDIS_BACKEND=memory` is used for local development.
- `SKIP_RERANKER_MODEL_CHECK=true` avoids downloading the reranker model during service startup.

## Start Commands

Run each command in a separate terminal.

```powershell
cd D:\codex\LangChain-RAG-FastAPI-Service-master\DjangoUserService
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8011 --noreload
```

```powershell
cd D:\codex\LangChain-RAG-FastAPI-Service-master\backend
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8010
```

```powershell
cd D:\codex\LangChain-RAG-FastAPI-Service-master\front
$env:VITE_BACKEND_TARGET="http://127.0.0.1:8010"
$env:VITE_USER_SERVICE_TARGET="http://127.0.0.1:8011"
npm.cmd run dev -- --host 127.0.0.1 --port 3010
```

## Verification

```powershell
Invoke-RestMethod http://127.0.0.1:8010/health/live
Invoke-RestMethod http://127.0.0.1:8010/health/ready
Invoke-WebRequest http://127.0.0.1:3010/
```
