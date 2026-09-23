# syntax=docker/dockerfile:1

# ---- 前端构建阶段 ----
FROM node:22-bookworm-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi
COPY frontend/ ./
# vite.config.ts 中 outDir=../backend/static
RUN npm run build

# ---- 运行 + verify 一体镜像：python 运行时，内置 node 供 verify 执行前端构建 ----
FROM python:3.11-slim-bookworm AS runtime

# 从官方 node 镜像拷入 node 与 npm（verify 服务需要跑 npm run build）
COPY --from=node:22-bookworm-slim /usr/local/bin/node /usr/local/bin/node
COPY --from=node:22-bookworm-slim /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -sf ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
 && ln -sf ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
 && apt-get update \
 && apt-get install -y --no-install-recommends libstdc++6 ca-certificates bash \
 && rm -rf /var/lib/apt/lists/* \
 && node --version && npm --version

RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend/ /app/backend/
# 预构建的前端静态资源（由 FastAPI 在 / 托管）
COPY --from=frontend /app/backend/static /app/backend/static
# 前端源码与依赖：verify 一次性服务会重新执行一次 npm run build
COPY frontend/ /app/frontend/
COPY --from=frontend /app/frontend/node_modules /app/frontend/node_modules
COPY scripts/ /app/scripts/
RUN chmod +x /app/scripts/verify.sh

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=4s --start-period=5s --retries=5 \
  CMD python3 -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3).status == 200 else 1)"

WORKDIR /app/backend
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
