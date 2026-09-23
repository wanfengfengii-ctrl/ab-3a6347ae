"""求解器对拍：小规模随机实例上用全枚举子集暴力结果校验 DFS。"""

import itertools
import random

from app.solver import Fragment, solve


def brute(n: int, frags: list[Fragment]):
    m = len(frags)
    best_key = None
    bodies: dict[bytes, int] = {}
    possible_cover = False
    for mask in range(1 << m):
        chosen = [frags[i] for i in range(m) if (mask >> i) & 1]
        # 完整覆盖
        cov = bytearray(n)
        ok_cov = [False] * n
        consistent = True
        fill = {}
        for f in chosen:
            for k, b in enumerate(f.payload):
                p = f.offset + k
                if p in fill and fill[p] != b:
                    consistent = False
                fill[p] = b
                ok_cov[p] = True
        if all(ok_cov):
            possible_cover = True
        if not consistent or not all(ok_cov):
            continue
        w = sum(f.weight for f in chosen)
        key = (w, len(chosen))
        body = bytes(fill[p] for p in range(n))
        if best_key is None or key > best_key:
            best_key = key
            bodies = {body: mask}
        elif key == best_key:
            bodies.setdefault(body, mask)
    return best_key, bodies, possible_cover


def test_solver_matches_brute_force_random_cases():
    rng = random.Random(20260923)
    for case in range(400):
        n = rng.randint(1, 8)
        m = rng.randint(2, 11)
        frags = []
        used_ids = set()
        for i in range(m):
            off = rng.randint(0, n - 1)
            ln = rng.randint(1, n - off)
            payload = bytes(rng.randrange(256) for _ in range(ln))
            fid = f"f{i}"
            frags.append(Fragment(fid, off, payload, rng.randint(1, 20)))
            used_ids.add(fid)

        res = solve(n, frags)
        best_key, bodies, possible_cover = brute(n, frags)

        if best_key is None:
            assert res.status == "IMPOSSIBLE"
            assert res.optimal_weight is None
            # 原因判定：忽略冲突时区间并集能否盖满
            assert res.impossible_reason == ("GAP" if not possible_cover else "CONFLICT")
            continue

        assert res.status in ("UNIQUE", "AMBIGUOUS")
        assert (res.optimal_weight, res.optimal_fragment_count) == best_key
        expected_sorted = sorted(bodies.keys())
        got = [b for b, _ in res.bodies]
        if len(expected_sorted) == 1:
            assert res.status == "UNIQUE"
            assert got == expected_sorted
        else:
            assert res.status == "AMBIGUOUS"
            assert got == expected_sorted[:2], f"case {case}"
            # 见证确实还原对应正文，且是达到最优值的方案
            for body, witness_ids in res.bodies:
                wmask = 0
                for i, f in enumerate(frags):
                    if f.fid in witness_ids:
                        wmask |= 1 << i
                assert witness_ids, "见证不能为空"
                assert bodies[body] is not None
                w = sum(frags[i].weight for i in range(m) if (wmask >> i) & 1)
                assert (w, len(witness_ids)) == best_key
                # 用见证重建正文
                buf = {}
                for i in range(m):
                    if (wmask >> i) & 1:
                        f = frags[i]
                        for k, b in enumerate(f.payload):
                            p = f.offset + k
                            assert buf.get(p, b) == b
                            buf[p] = b
                assert bytes(buf[p] for p in range(n)) == body
