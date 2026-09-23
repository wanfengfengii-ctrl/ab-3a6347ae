"""FastAPI 入口：档案片段重建台业务 API。"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .models import AnalyzeResponse, BodyWitness
from .solver import Fragment, solve
from .validation import validate_request

app = FastAPI(
    title="档案片段重建台",
    version="1.0.0",
    description="导入重叠字节片段，求最优一致覆盖并裁决正文唯一性。",
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    # 统一 422 响应体：{"detail": [{"loc": [...], "msg": ..., "type": ...}, ...]}
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze(request: Request) -> AnalyzeResponse:
    try:
        payload = await request.json()
    except Exception:
        raise RequestValidationError(
            [{"loc": ("body",), "msg": "请求体必须是合法 JSON", "type": "type_error.json"}]
        )
    req = validate_request(payload)

    fragments = [
        Fragment(
            fid=f.id,
            offset=f.offset,
            payload=bytes.fromhex(f.payload_hex),
            weight=f.weight,
        )
        for f in req.fragments
    ]
    result = solve(req.target_length, fragments)

    return AnalyzeResponse(
        status=result.status,  # type: ignore[arg-type]
        target_length=req.target_length,
        optimal_weight=result.optimal_weight,
        optimal_fragment_count=result.optimal_fragment_count,
        impossible_reason=result.impossible_reason,  # type: ignore[arg-type]
        bodies=[
            BodyWitness(body_hex=body.hex(), witness_fragment_ids=ids)
            for body, ids in result.bodies
        ],
        conflicts=result.conflicts,
    )


# 构建后的前端静态资源（Docker 镜像中由多阶段构建拷入）。
import os

_static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
if os.path.isdir(_static_dir):
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")
