"""验收场景 API 测试：互斥高权片段 / 等分正文 / 缺口 / 冲突 / 非法输入 422。"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _f(fid, off, hexs, w):
    return {"id": fid, "offset": off, "payload_hex": hexs, "weight": w}


# ---------- 等分正文：无重叠的等权切片，唯一还原 ----------

def test_equal_partitions_unique():
    r = client.post(
        "/api/analyze",
        json={
            "target_length": 4,
            "fragments": [
                _f("A", 0, "0011", 5),
                _f("B", 2, "2233", 5),
            ],
        },
    )
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "UNIQUE"
    assert d["bodies"][0]["body_hex"] == "00112233"
    assert sorted(d["bodies"][0]["witness_fragment_ids"]) == ["A", "B"]
    assert d["optimal_weight"] == 10
    assert d["optimal_fragment_count"] == 2
    assert d["impossible_reason"] is None
    assert d["conflicts"] == []


# ---------- 重叠一致：UNIQUE，权重与计数 ----------

def test_overlap_agrees_unique():
    r = client.post(
        "/api/analyze",
        json={
            "target_length": 4,
            "fragments": [
                _f("A", 0, "aabbccdd", 10),
                _f("B", 2, "ccdd", 5),
            ],
        },
    )
    d = r.json()
    assert r.status_code == 200
    assert d["status"] == "UNIQUE"
    assert d["bodies"][0]["body_hex"] == "aabbccdd"
    assert d["optimal_weight"] == 15
    assert d["optimal_fragment_count"] == 2


def test_primary_weight_then_count():
    # A 整段低权重；B+C 等权切片，总权与 A 相同但片段数更多。
    r = client.post(
        "/api/analyze",
        json={
            "target_length": 2,
            "fragments": [
                _f("A", 0, "aabb", 10),
                _f("B", 0, "aa", 5),
                _f("C", 1, "bb", 5),
            ],
        },
    )
    d = r.json()
    # 三片段一致 => 总权 20、数量 3（最大化权重优先）
    assert d["optimal_weight"] == 20
    assert d["optimal_fragment_count"] == 3
    assert d["status"] == "UNIQUE"


# ---------- 高权片段互斥：AMBIGUOUS，双方等高权、等数片段 ----------

def test_mutex_high_weight_fragments_ambiguous():
    r = client.post(
        "/api/analyze",
        json={
            "target_length": 4,
            "fragments": [
                _f("A", 0, "00000000", 100),
                _f("B", 0, "ffffffff", 100),
                _f("E", 0, "0000", 5),   # 与 A 一致
                _f("F", 0, "ffff", 5),   # 与 B 一致
            ],
        },
    )
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "AMBIGUOUS"
    assert d["optimal_weight"] == 105
    assert d["optimal_fragment_count"] == 2
    bodies = d["bodies"]
    assert [b["body_hex"] for b in bodies] == ["00000000", "ffffffff"]
    assert sorted(bodies[0]["witness_fragment_ids"]) == ["A", "E"]
    assert sorted(bodies[1]["witness_fragment_ids"]) == ["B", "F"]
    # 冲突信息保留，便于复核员区分“片段冲突”
    pairs = {(c["a"]["fragment_id"], c["b"]["fragment_id"]) for c in d["conflicts"]}
    assert ("A", "B") in pairs


def test_ambiguous_byte_order_smallest_two():
    r = client.post(
        "/api/analyze",
        json={
            "target_length": 2,
            "fragments": [
                _f("hi", 0, "9090", 10),
                _f("lo", 0, "1010", 10),
                _f("mid", 0, "5050", 10),
            ],
        },
    )
    d = r.json()
    assert d["status"] == "AMBIGUOUS"
    assert [b["body_hex"] for b in d["bodies"]] == ["1010", "5050"]
    assert d["bodies"][0]["witness_fragment_ids"] == ["lo"]
    assert d["bodies"][1]["witness_fragment_ids"] == ["mid"]


# ---------- 缺口：IMPOSSIBLE / GAP ----------

def test_gap_impossible():
    r = client.post(
        "/api/analyze",
        json={
            "target_length": 4,
            "fragments": [
                _f("A", 0, "0011", 5),
                _f("B", 3, "33", 5),  # 位置 2 缺失
            ],
        },
    )
    d = r.json()
    assert d["status"] == "IMPOSSIBLE"
    assert d["impossible_reason"] == "GAP"
    assert d["optimal_weight"] is None
    assert d["bodies"] == []


# ---------- 片段冲突导致无解：IMPOSSIBLE / CONFLICT ----------
# 位置 0 只有 A 能盖、位置 1 只有 B 能盖（双方都必须入选），
# 但 A 与 B 在重叠的位置 1 上字节冲突 => 不存在一致完整覆盖。

def test_conflict_impossible():
    r = client.post(
        "/api/analyze",
        json={
            "target_length": 3,
            "fragments": [
                _f("A", 0, "0011", 10),  # 位置0=00, 位置1=11，独占位置0
                _f("B", 1, "2233", 10),  # 位置1=22, 位置2=33，独占位置2
            ],
        },
    )
    d = r.json()
    assert d["status"] == "IMPOSSIBLE"
    assert d["impossible_reason"] == "CONFLICT"
    assert len(d["conflicts"]) == 1
    c = d["conflicts"][0]
    assert c["first_position"] == 1
    assert c["positions"] == [1]
    assert {c["byte_a"], c["byte_b"]} == {"11", "22"}


def test_full_covering_conflicting_fragments_is_ambiguous_not_impossible():
    # 两个互斥片段各自都能单独完整覆盖 => 歧义（AMBIGUOUS），不是无解。
    # 这正是复核员需要区分的“正文歧义”。
    r = client.post(
        "/api/analyze",
        json={
            "target_length": 2,
            "fragments": [
                _f("A", 0, "0000", 10),
                _f("B", 0, "0101", 10),
            ],
        },
    )
    d = r.json()
    assert d["status"] == "AMBIGUOUS"
    assert [b["body_hex"] for b in d["bodies"]] == ["0000", "0101"]
    assert d["bodies"][0]["witness_fragment_ids"] == ["A"]
    assert d["bodies"][1]["witness_fragment_ids"] == ["B"]
    assert d["optimal_weight"] == 10
    assert d["optimal_fragment_count"] == 1


def test_conflict_localized_but_other_cover_exists_unique():
    # 冲突片段存在，但可以丢弃它，另有一组一致片段完整覆盖。
    r = client.post(
        "/api/analyze",
        json={
            "target_length": 3,
            "fragments": [
                _f("good1", 0, "aabb", 10),
                _f("good2", 2, "cc", 10),
                _f("bad", 0, "bb", 1),  # 与 good1 在位置 0 冲突，可弃
            ],
        },
    )
    d = r.json()
    assert d["status"] == "UNIQUE"
    assert d["bodies"][0]["body_hex"] == "aabbcc"
    assert sorted(d["bodies"][0]["witness_fragment_ids"]) == ["good1", "good2"]
    assert d["optimal_weight"] == 20
    # 冲突仍然报告，复核员能看到被丢弃片段与谁冲突
    pairs = {
        tuple(sorted((c["a"]["fragment_id"], c["b"]["fragment_id"])))
        for c in d["conflicts"]
    }
    assert ("bad", "good1") in pairs
