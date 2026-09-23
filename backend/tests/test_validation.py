"""非法输入：全部必须返回 HTTP 422，且 detail 中带字段位置 loc。"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _f(fid="A", off=0, hexs="aa", w=1):
    return {"id": fid, "offset": off, "payload_hex": hexs, "weight": w}


def _locs(r):
    return [tuple(e["loc"]) for e in r.json()["detail"]]


def test_missing_fields_422():
    r = client.post("/api/analyze", json={})
    assert r.status_code == 422
    locs = _locs(r)
    assert ("body", "target_length") in locs
    assert ("body", "fragments") in locs


def test_target_length_bounds():
    for bad_n in (0, -1, 513, 10000):
        r = client.post("/api/analyze", json={"target_length": bad_n, "fragments": [_f(), _f(off=1)]})
        assert r.status_code == 422, bad_n
        assert ("body", "target_length") in _locs(r)


def test_fragment_count_bounds():
    for m in (0, 1, 29):
        r = client.post(
            "/api/analyze",
            json={"target_length": 512, "fragments": [_f(fid=f"A{i}", off=i) for i in range(m)]},
        )
        assert r.status_code == 422, m
        assert ("body", "fragments") in _locs(r)


def test_duplicate_ids_point_to_later_index():
    r = client.post(
        "/api/analyze",
        json={
            "target_length": 2,
            "fragments": [
                _f(fid="X", off=0, hexs="aabb"),
                _f(fid="Y", off=0, hexs="aa"),
                _f(fid="X", off=1, hexs="bb"),
            ],
        },
    )
    assert r.status_code == 422
    assert ("body", "fragments", 2, "id") in _locs(r)


def test_bad_hex_odd_length():
    r = client.post(
        "/api/analyze",
        json={"target_length": 2, "fragments": [_f(hexs="abc"), _f(off=1, hexs="bb")]},
    )
    assert r.status_code == 422
    assert ("body", "fragments", 0, "payload_hex") in _locs(r)


def test_bad_hex_chars():
    r = client.post(
        "/api/analyze",
        json={"target_length": 2, "fragments": [_f(hexs="zz"), _f(off=1, hexs="bb")]},
    )
    assert r.status_code == 422
    assert ("body", "fragments", 0, "payload_hex") in _locs(r)


def test_empty_payload():
    r = client.post(
        "/api/analyze",
        json={"target_length": 2, "fragments": [_f(hexs=""), _f(off=1, hexs="bb")]},
    )
    assert r.status_code == 422
    assert ("body", "fragments", 0, "payload_hex") in _locs(r)


def test_negative_offset():
    r = client.post(
        "/api/analyze",
        json={"target_length": 2, "fragments": [_f(off=-1), _f(off=0, hexs="aabb")]},
    )
    assert r.status_code == 422
    assert ("body", "fragments", 0, "offset") in _locs(r)


def test_weight_bounds():
    for bad_w in (0, -5, 1_000_001):
        r = client.post(
            "/api/analyze",
            json={"target_length": 2, "fragments": [_f(w=bad_w, hexs="aabb"), _f()]},
        )
        assert r.status_code == 422, bad_w
        assert ("body", "fragments", 0, "weight") in _locs(r)


def test_out_of_bounds_fragment():
    r = client.post(
        "/api/analyze",
        json={
            "target_length": 2,
            "fragments": [
                _f(off=1, hexs="aabb"),  # 右端 3 > 2
                _f(off=0, hexs="aa"),
            ],
        },
    )
    assert r.status_code == 422
    assert ("body", "fragments", 0) in _locs(r)


def test_wrong_types_422():
    r = client.post(
        "/api/analyze",
        json={"target_length": "4", "fragments": [_f(w="high"), _f()]},
    )
    assert r.status_code == 422
    locs = _locs(r)
    assert ("body", "target_length") in locs
    assert ("body", "fragments", 0, "weight") in locs


def test_empty_id_422():
    r = client.post(
        "/api/analyze",
        json={"target_length": 2, "fragments": [_f(fid="   "), _f(hexs="aabb")]},
    )
    assert r.status_code == 422
    assert ("body", "fragments", 0, "id") in _locs(r)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
