"""重建台求解核心。

问题
----
目标正文长度 n 字节；片段 i 覆盖连续区间 [offset_i, offset_i+len_i)，携带逐字节
取值与正权重 w_i。方案是片段集合，它“有效”当且仅当：

1. 完整覆盖：并集 = [0, n)（无缺口）；
2. 两两一致：被选片段在任意重叠位置上的字节相同（无冲突）。

优化目标：先最大化总权重，权重相同再最大化片段数。
裁决：
- UNIQUE     —— 所有最优方案还原的正文相同；
- AMBIGUOUS  —— 最优方案可还原多份正文；返回按无符号字节序最小的两份及各自见证；
- IMPOSSIBLE —— 不存在完整一致覆盖；原因为 GAP（区间本身盖不满）或 CONFLICT
                （忽略冲突时能盖满，但任何盖满的选择都必须拆开某对冲突）。

算法（m <= 28，n <= 512）
-------------------------
从“所有片段都保留”出发，在冲突图上做保/删分支的加权 MaxSAT 式 DFS：
- 状态 (S 已选, R 已删, U 未定)；S 始终两两一致。
- 选冲突度最高的未定片段 a 分支：
  · 保留 a => 与 a 冲突的未定片段全部强制删除；
  · 删除 a。
  每个一致集合在决策树上恰好出现一次。
- 强制保留：某未覆盖位置只被唯一一个未定片段覆盖时，该片段必须保留
  （保留即连锁删除其冲突对手；若它与 S 冲突 => 此路无解）。
- 剪枝：
  · S∪U 的区间并集盖不满 [0,n)（覆盖用位掩码 O(1) 判定）；
  · 乐观上界 (w(S)+w(U), |S|+|U|) 劣于已知最优。
- U 中已无冲突且覆盖完整 => 全部保留，直接成为候选方案
  （权重均为正、数量为次级目标，任何删除都更差）。

正文多样性：只记录达到最优 (权重, 数量) 的、字典序最小的两份不同正文及其见证。
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import Conflict, ConflictSide


@dataclass(frozen=True)
class Fragment:
    fid: str
    offset: int
    payload: bytes
    weight: int

    @property
    def end(self) -> int:
        return self.offset + len(self.payload)


@dataclass
class SolveResult:
    status: str  # UNIQUE | AMBIGUOUS | IMPOSSIBLE
    optimal_weight: int | None
    optimal_fragment_count: int | None
    impossible_reason: str | None  # GAP | CONFLICT | None
    bodies: list[tuple[bytes, list[str]]]
    conflicts: list[Conflict]


def _pair_conflict(fi: Fragment, fj: Fragment) -> tuple[list[int], int, int, int] | None:
    """返回 (所有冲突位置, 首个冲突位置, fi 字节, fj 字节)，不冲突返回 None。"""
    lo = max(fi.offset, fj.offset)
    hi = min(fi.end, fj.end)
    if lo >= hi:
        return None
    ai, bi, span = lo - fi.offset, lo - fj.offset, hi - lo
    pa, pb = fi.payload[ai : ai + span], fj.payload[bi : bi + span]
    if pa == pb:
        return None
    positions: list[int] = []
    first, ba, bb = -1, 0, 0
    for k in range(span):
        x, y = pa[k], pb[k]
        if x != y:
            p = lo + k
            positions.append(p)
            if first == -1:
                first, ba, bb = p, x, y
    return positions, first, ba, bb


def conflict_report(fragments: list[Fragment]) -> list[Conflict]:
    """所有相互冲突的片段对（含位置与双方字节），供前端展示“片段冲突”。"""
    out: list[Conflict] = []
    for i in range(len(fragments)):
        for j in range(i + 1, len(fragments)):
            hit = _pair_conflict(fragments[i], fragments[j])
            if hit is None:
                continue
            positions, first, ba, bb = hit
            out.append(
                Conflict(
                    a=ConflictSide(fragment_id=fragments[i].fid, offset=fragments[i].offset),
                    b=ConflictSide(fragment_id=fragments[j].fid, offset=fragments[j].offset),
                    first_position=first,
                    positions=positions,
                    byte_a=f"{ba:02x}",
                    byte_b=f"{bb:02x}",
                )
            )
    return out


def solve(target_length: int, raw_fragments: list[Fragment]) -> SolveResult:
    n = target_length
    m = len(raw_fragments)
    full = (1 << n) - 1

    # 冲突边与覆盖位掩码
    bad = [0] * m
    cover = [0] * m
    for i, f in enumerate(raw_fragments):
        cover[i] = sum(1 << p for p in range(f.offset, f.end))
        for j in range(i + 1, m):
            if _pair_conflict(f, raw_fragments[j]) is not None:
                bad[i] |= 1 << j
                bad[j] |= 1 << i

    weights = [f.weight for f in raw_fragments]
    all_mask = (1 << m) - 1

    best_key: tuple[int, int] = (-1, -1)
    body_witness: dict[bytes, int] = {}  # body -> 一个达到它的最优完整选择掩码
    smallest: list[bytes] = []  # 字典序最小的至多两份不同正文

    def render(mask: int) -> bytes:
        buf = bytearray(n)
        for i in range(m):
            if (mask >> i) & 1:
                f = raw_fragments[i]
                buf[f.offset : f.end] = f.payload
        return bytes(buf)

    def accept(mask: int, weight: int, count: int) -> None:
        nonlocal best_key, smallest
        key = (weight, count)
        if key < best_key:
            return
        body = render(mask)
        if key > best_key:
            best_key = key
            body_witness.clear()
            body_witness[body] = mask
            smallest = [body]
        elif body not in body_witness:
            body_witness[body] = mask
            smallest.append(body)
            smallest.sort()
            if len(smallest) > 2:
                smallest.pop()

    def dfs(selected: int, removed: int, w_sel: int, c_sel: int) -> None:
        # ---- 强制保留传播 ----
        while True:
            undecided = all_mask & ~(selected | removed)
            cov_sel = 0
            cov_und = 0
            w_und = 0
            for i in range(m):
                if (selected >> i) & 1:
                    cov_sel |= cover[i]
                elif (undecided >> i) & 1:
                    cov_und |= cover[i]
                    w_und += weights[i]

            # 剪枝 1：连“忽略冲突的区间并集”都盖不满
            if (cov_sel | cov_und) != full:
                return

            # 剪枝 2：乐观上界劣于已知最优
            c_und = undecided.bit_count()
            if (w_sel + w_und, c_sel + c_und) < best_key:
                return

            active_bad = 0  # 至少涉及一个未定片段的冲突边
            for i in range(m):
                if (undecided >> i) & 1 and (bad[i] & undecided):
                    active_bad |= 1 << i

            if active_bad == 0:
                # 未定片段彼此不冲突（且与 selected 不冲突，否则早被强制删除）
                # => 全部保留即本分支最优候选
                accept(selected | undecided, w_sel + w_und, c_sel + c_und)
                return

            # 未覆盖位置中，被未定片段“恰好覆盖一次”的位置 => 该片段必须保留
            uncovered = full & ~cov_sel
            once = 0
            multi = 0
            for i in range(m):
                if (undecided >> i) & 1:
                    c = cover[i] & uncovered
                    multi |= once & c
                    once |= c
            essential_bits = once & ~multi
            forced: list[int] = []
            if essential_bits:
                for i in range(m):
                    if (undecided >> i) & 1 and (cover[i] & essential_bits):
                        forced.append(i)
            if not forced:
                break  # 交给分支

            for a in forced:
                if bad[a] & selected:
                    return  # 必须保留的片段与已选片段冲突 => 无解
                partners = bad[a] & undecided
                selected |= 1 << a
                removed |= partners
                w_sel += weights[a]
                c_sel += 1
                undecided &= ~(1 << a)
                undecided &= ~partners
        # ---- 分支：冲突度最高的未定片段 ----
        undecided = all_mask & ~(selected | removed)
        a = -1
        best_degree = -1
        for i in range(m):
            if (undecided >> i) & 1:
                degree = (bad[i] & undecided).bit_count()
                if degree > best_degree:
                    best_degree, a = degree, i

        # 分支 1：保留 a，连锁删除其冲突对手（先探索，通常更快拿到高质量解）
        partners = bad[a] & undecided
        dfs(selected | (1 << a), removed | partners, w_sel + weights[a], c_sel + 1)
        # 分支 2：删除 a
        dfs(selected, removed | (1 << a), w_sel, c_sel)

    dfs(0, 0, 0, 0)

    all_conflicts = conflict_report(raw_fragments)

    if best_key[0] < 0:
        # 无完整一致覆盖：忽略冲突时区间并集能否盖满？
        union_end = 0
        for lo, hi in sorted((f.offset, f.end) for f in raw_fragments):
            if lo > union_end:
                break
            union_end = max(union_end, hi)
            if union_end >= n:
                break
        reason = "GAP" if union_end < n else "CONFLICT"
        return SolveResult(
            status="IMPOSSIBLE",
            optimal_weight=None,
            optimal_fragment_count=None,
            impossible_reason=reason,
            bodies=[],
            conflicts=all_conflicts,
        )

    w, c = best_key
    status = "UNIQUE" if len(smallest) == 1 else "AMBIGUOUS"
    bodies = [
        (
            body,
            [raw_fragments[i].fid for i in range(m) if (body_witness[body] >> i) & 1],
        )
        for body in smallest
    ]
    return SolveResult(
        status=status,
        optimal_weight=w,
        optimal_fragment_count=c,
        impossible_reason=None,
        bodies=bodies,
        conflicts=all_conflicts,
    )
