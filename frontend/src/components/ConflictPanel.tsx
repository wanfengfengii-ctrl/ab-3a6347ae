import type { Conflict } from "../types";

interface Props {
  conflicts: Conflict[];
}

/**
 * 片段冲突清单：每一对在重叠位置字节取值不同的片段。
 * 即使裁决为 UNIQUE/AMBIGUOUS（冲突片段可被最优方案舍弃），这里仍然列出，
 * 让复核员明确区分“片段之间存在冲突”与“最终正文存在歧义”。
 */
export function ConflictPanel({ conflicts }: Props) {
  return (
    <section className="panel conflicts">
      <div className="panel-head">
        <h2>④ 片段冲突位置</h2>
        <span className={"muted" + (conflicts.length ? "" : " ok-text")}>
          {conflicts.length ? `${conflicts.length} 对片段在重叠位置字节不同` : "任意重叠片段的字节均一致"}
        </span>
      </div>

      {conflicts.length === 0 && (
        <p className="muted">无片段冲突。若上方裁决为 IMPOSSIBLE，则原因是 GAP（缺口）。</p>
      )}

      <ul className="conflict-list">
        {conflicts.map((c, i) => (
          <li key={i} className="conflict-item">
            <div className="conflict-head">
              <span className="chip chip-a">{c.a.fragment_id}</span>
              <span className="conflict-x">✕</span>
              <span className="chip chip-b">{c.b.fragment_id}</span>
              <span className="muted">
                （偏移 {c.a.offset} / {c.b.offset}）
              </span>
            </div>
            <div className="conflict-detail">
              首个冲突位置 <b>{c.first_position}</b>：
              <span className="byte byte-a">{c.byte_a}</span> ≠{" "}
              <span className="byte byte-b">{c.byte_b}</span>
              {c.positions.length > 1 && (
                <span className="muted">；共 {c.positions.length} 处：{c.positions.join(", ")}</span>
              )}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
