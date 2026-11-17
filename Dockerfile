# ============ 1. 构建前端 ============
FROM node:20-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ============ 2. 运行后端（同时托管前端） ============
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_ENV=production \
    DEBUG=false \
    HOST=0.0.0.0 \
    PORT=8000 \
    SEED_DEMO=true

# rapidocr / opencv 需要的系统库
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ ./backend/
COPY --from=web /web/dist ./frontend/dist

WORKDIR /app/backend

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import os,urllib.request;urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/health', timeout=3)"

# 首次启动写入演示数据（demo / demo123），已存在则自动跳过；不需要时传 SEED_DEMO=false
CMD ["sh", "-c", "if [ \"$SEED_DEMO\" = \"true\" ]; then python seed_demo.py || true; fi; exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips=*"]
