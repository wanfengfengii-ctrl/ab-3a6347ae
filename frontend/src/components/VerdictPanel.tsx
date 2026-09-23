import type { AnalyzeResponse } from "../types";

interface Props {
  result: AnalyzeResponse;
}

const STATUS_META = {
  UNIQUE: {
    label: "UNIQUE · 正文唯一",
    cls: "verdict-unique",
    desc: "所有最优方案还原的正文完全相同。",
  },
  AMBIGUOUS: {
    label: "AMBIGUOUS · 正文歧义",
    cls: "verdict-ambiguous",
    desc: "存在多个并列最优方案还原出不同正文；下列为按无符号字节序最小的两份。注意：这是“正文歧义”，不是格式/片段冲突错误。",
  },
  IMPOSSIBLE: {
    label: "IMPOSSIBLE · 无法完整一致覆盖",
    cls: "verdict-impossible",
    desc: "",
  },
} as const;

export function VerdictPanel({ result }: Props) {
  const meta = STATUS_META[result.status];
  return (
    <section className={"panel verdict " + meta.cls}>
      <div className="panel-head">
        <h2>③ 裁决</h2>
        <span className="verdict-badge">{meta.label}</span>
      </div>

      {result.status !== "IMPOSSIBLE" && (
        <p className="muted">{meta.desc}</p>
      )}

      {result.status === "IMPOSSIBLE" && (
        <div className="impossible-box">
          <p>
            原因：
            {result.impossible_reason === "GAP" ? (
              <>
                <b className="tag tag-gap">GAP 缺口</b> —— 所有片段的区间并集仍盖不住目标长度，
                至少有一个目标字节没有任何片段承载。
              </>
            ) : (
              <>
                <b className="tag tag-conflict">CONFLICT 片段冲突</b> —— 区间本身能够盖满，
                但任何完整覆盖都必须同时采用一对在重叠位置字节不同的片段。
              </>
            )}
          </p>
          <p className="muted">
            区分要点：GAP 是“缺数据”，CONFLICT 是“数据互相矛盾”；二者都不同于 AMBIGUOUS
            （存在多份自洽的最优正文，数据并不矛盾）。
          </p>
        </div>
      )}

      <div className="opt-grid">
        <div className="opt-cell">
          <div className="opt-label">最优总权重</div>
          <div className="opt-value">{result.optimal_weight ?? "—"}</div>
        </div>
        <div className="opt-cell">
          <div className="opt-label">最优方案片段数</div>
          <div className="opt-value">{result.optimal_fragment_count ?? "—"}</div>
        </div>
      </div>

      {result.status !== "IMPOSSIBLE" && (
        <div className="witness-list">
          {result.bodies.map((b, i) => (
            <div key={i} className="witness-item">
              <span className="witness-tag">候选 #{i + 1} 采用片段（{b.witness_fragment_ids.length}）</span>
              <span className="witness-ids">
                {b.witness_fragment_ids.map((id) => (
                  <span key={id} className="chip">
                    {id}
                  </span>
                ))}
              </span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
