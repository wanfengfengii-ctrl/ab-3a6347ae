#!/usr/bin/env bash
# verify 一次性服务入口：代码测试 -> 前端构建 -> API 冒烟。
# 任一步失败立即以非零退出码退出，全部成功退出码 0。
# 环境变量：
#   PYTHON    解释器（默认 python3）
#   BASE_URL  已运行的 API 地址（设置后冒烟直连，不再自行拉起 uvicorn）
set -euo pipefail

PYTHON="${PYTHON:-python3}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "== [1/3] 后端代码测试（pytest） =="
cd "$ROOT_DIR/backend"
"$PYTHON" -m pytest -q

echo "== [2/3] 前端构建（tsc 类型检查 + vite build） =="
cd "$ROOT_DIR/frontend"
npm run build

echo "== [3/3] API 冒烟（健康检查 + UNIQUE/AMBIGUOUS/IMPOSSIBLE/422） =="
cd "$ROOT_DIR/backend"
"$PYTHON" scripts/smoke_api.py

echo "== VERIFY PASSED =="
