"""请求校验：所有错误都带精确字段位置 loc，最终渲染为 HTTP 422。

- 字段级错误（类型/取值范围/十六进制格式）定位到 body.fragments[i].<字段>
- 跨字段错误：
  · 重复编号             -> 后出现者 body.fragments[i].id
  · 片段越过目标长度     -> body.fragments[i]
"""

from __future__ import annotations

from typing import Any

from fastapi.exceptions import RequestValidationError
from pydantic import TypeAdapter, ValidationError

from .models import AnalyzeRequest, FragmentIn

_fragment_adapter = TypeAdapter(FragmentIn)


def _err(loc: tuple[Any, ...], msg: str, value: Any, typ: str = "value_error") -> dict[str, Any]:
    return {"loc": ("body", *loc), "msg": msg, "type": typ, "input": value}


def validate_request(payload: Any) -> AnalyzeRequest:
    errors: list[dict[str, Any]] = []

    if not isinstance(payload, dict):
        raise RequestValidationError([_err((), "请求体必须是 JSON 对象", payload, "type_error")])

    # ---- target_length ----
    n = payload.get("target_length")
    n_ok = False
    if "target_length" not in payload:
        errors.append(_err(("target_length",), "field required", None, "missing"))
    elif not isinstance(n, int) or isinstance(n, bool):
        errors.append(_err(("target_length",), "必须是整数", n, "type_error.integer"))
    elif not 1 <= n <= 512:
        errors.append(_err(("target_length",), "必须在 1..512 之间", n, "value_error.range"))
    else:
        n_ok = True

    # ---- fragments ----
    if "fragments" not in payload:
        errors.append(_err(("fragments",), "field required", None, "missing"))
        raise RequestValidationError(errors)
    raws = payload.get("fragments")
    if not isinstance(raws, list):
        errors.append(_err(("fragments",), "必须是数组", raws, "type_error.list"))
        raise RequestValidationError(errors)
    if not 2 <= len(raws) <= 28:
        errors.append(
            _err(("fragments",), f"片段数量必须在 2..28 之间（当前 {len(raws)}）", len(raws))
        )

    checked: list[tuple[int, FragmentIn]] = []  # (原始下标, 校验通过的片段)
    raw_ids: list[tuple[int, str]] = []  # (原始下标, 非空 id 原文)，独立用于查重
    for i, raw in enumerate(raws):
        if not isinstance(raw, dict):
            errors.append(_err(("fragments", i), "片段必须是对象", raw, "type_error"))
            continue
        rid = raw.get("id")
        if isinstance(rid, str) and rid.strip():
            raw_ids.append((i, rid.strip()))
        try:
            frag = _fragment_adapter.validate_python(raw)
        except ValidationError as exc:
            for e in exc.errors():
                errors.append(
                    _err(("fragments", i, *tuple(e.get("loc", ()))), e["msg"], e.get("input"), e["type"])
                )
            continue
        checked.append((i, frag))

    # ---- 跨字段校验 ----
    # 重复编号：独立判定，即使该行另有字段级错误也要报告。
    seen_raw_ids: set[str] = set()
    for i, rid in raw_ids:
        if rid in seen_raw_ids:
            errors.append(_err(("fragments", i, "id"), f"重复的片段编号: {rid}", rid))
        seen_raw_ids.add(rid)
    # 越界：仅对字段级校验通过的片段判定。
    for i, frag in checked:
        if n_ok:
            length = len(bytes.fromhex(frag.payload_hex))
            end = frag.offset + length
            if end > n:
                errors.append(
                    _err(
                        ("fragments", i),
                        f"片段越过目标长度：offset={frag.offset} + 载荷长度={length} = {end} "
                        f"> target_length={n}",
                        {"id": frag.id, "offset": frag.offset, "payload_hex": frag.payload_hex},
                        "value_error.out_of_bounds",
                    )
                )

    if errors:
        raise RequestValidationError(errors)

    return AnalyzeRequest(target_length=n, fragments=[f for _, f in checked])
