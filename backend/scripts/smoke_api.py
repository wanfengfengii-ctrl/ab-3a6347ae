#!/usr/bin/env python3
"""API 冒烟：启动 uvicorn（如未指定 BASE_URL），跑通健康检查与三类裁决 + 422。

成功退出码 0，任一断言失败退出码 1。供 verify 一次性服务与本地复用：
    python scripts/smoke_api.py                # 自行拉起服务
    BASE_URL=http://localhost:8000 python scripts/smoke_api.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PORT = int(os.environ.get("SMOKE_PORT", "8000"))
BASE_URL = os.environ.get("BASE_URL")


def post(path: str, payload: dict) -> tuple[int, dict]:
    req = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def get(path: str) -> tuple[int, dict]:
    with urllib.request.urlopen(BASE_URL + path, timeout=5) as resp:
        return resp.status, json.loads(resp.read())


def check(name: str, cond: bool, detail: str = "") -> None:
    if not cond:
        print(f"[SMOKE] FAIL: {name} {detail}")
        raise SystemExit(1)
    print(f"[SMOKE] ok: {name}")


def main() -> None:
    # UNIQUE
    st, d = post(
        "/api/analyze",
        {
            "target_length": 4,
            "fragments": [
                {"id": "A", "offset": 0, "payload_hex": "0011", "weight": 5},
                {"id": "B", "offset": 2, "payload_hex": "2233", "weight": 5},
            ],
        },
    )
    check("unique status 200", st == 200, str(st))
    check("UNIQUE verdict", d["status"] == "UNIQUE", d.get("status"))
    check("unique body", d["bodies"][0]["body_hex"] == "00112233")
    check("optimum 10/2", (d["optimal_weight"], d["optimal_fragment_count"]) == (10, 2))

    # AMBIGUOUS（高权片段互斥）
    st, d = post(
        "/api/analyze",
        {
            "target_length": 2,
            "fragments": [
                {"id": "hi", "offset": 0, "payload_hex": "9090", "weight": 10},
                {"id": "lo", "offset": 0, "payload_hex": "1010", "weight": 10},
            ],
        },
    )
    check("AMBIGUOUS verdict", st == 200 and d["status"] == "AMBIGUOUS", str(d)[:200])
    check("byte-order two smallest", [b["body_hex"] for b in d["bodies"]] == ["1010", "9090"])
    check("witnesses present", {tuple(b["witness_fragment_ids"]) for b in d["bodies"]} == {("lo",), ("hi",)})

    # IMPOSSIBLE / GAP
    st, d = post(
        "/api/analyze",
        {
            "target_length": 4,
            "fragments": [
                {"id": "A", "offset": 0, "payload_hex": "0011", "weight": 5},
                {"id": "B", "offset": 3, "payload_hex": "33", "weight": 5},
            ],
        },
    )
    check("IMPOSSIBLE GAP", d["status"] == "IMPOSSIBLE" and d["impossible_reason"] == "GAP")

    # 422 + 字段位置
    st, d = post(
        "/api/analyze",
        {
            "target_length": 2,
            "fragments": [
                {"id": "X", "offset": 0, "payload_hex": "aabb", "weight": 1},
                {"id": "X", "offset": 0, "payload_hex": "bad", "weight": 0},
            ],
        },
    )
    check("422 returned", st == 422, str(st))
    locs = [tuple(e["loc"]) for e in d["detail"]]
    check("dup id located", ("body", "fragments", 1, "id") in locs, str(locs))
    check("bad hex located", ("body", "fragments", 1, "payload_hex") in locs, str(locs))
    check("bad weight located", ("body", "fragments", 1, "weight") in locs, str(locs))

    print("[SMOKE] ALL PASSED")


if __name__ == "__main__":
    proc = None
    if not BASE_URL:
        BASE_URL = f"http://127.0.0.1:{PORT}"
        backend_dir = Path(__file__).resolve().parents[1]
        proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(PORT)],
            cwd=backend_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(60):
            try:
                get("/api/health")
                break
            except Exception:
                time.sleep(0.5)
        else:
            proc.terminate()
            print("[SMOKE] server did not become ready")
            raise SystemExit(1)
    try:
        st, _ = get("/api/health")
        check("health", st == 200)
        main()
    finally:
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
