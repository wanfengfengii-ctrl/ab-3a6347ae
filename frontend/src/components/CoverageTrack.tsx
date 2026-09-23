import { useMemo } from "react";

export interface Span {
  id: string;
  offset: number;
  length: number;
  kind: "adopted" | "other";
}

interface Props {
  targetLength: number;
  spans: Span[];
  conflictPositions: Set<number>;
  gapPositions: Set<number>;
}

/**
 * 覆盖示意图：一条按目标长度等分的轨道，每个片段一行，
 * 冲突位置红、缺口位置斜纹填充，帮助复核员一眼定位。
 */
export function CoverageTrack({ targetLength, spans, conflictPositions, gapPositions }: Props) {
  const pct = (n: number) => `${(n / targetLength) * 100}%`;

  const marks = useMemo(() => {
    const cs = [...conflictPositions].sort((a, b) => a - b);
    const gs = [...gapPositions].sort((a, b) => a - b);
    return { cs, gs };
  }, [conflictPositions, gapPositions]);

  return (
    <section className="panel coverage">
      <div className="panel-head">
        <h2>采用片段与冲突 / 缺口位置</h2>
        <span className="legend">
          <i className="lg lg-adopted" /> 采用
          <i className="lg lg-other" /> 未采用
          <i className="lg lg-conflict" /> 冲突字节
          <i className="lg lg-gap" /> 缺口
        </span>
      </div>

      <div className="ruler">
        <span style={{ left: "0%" }}>0</span>
        <span style={{ left: "50%", transform: "translateX(-50%)" }}>{Math.floor(targetLength / 2)}</span>
        <span style={{ right: 0 }}>{targetLength - 1}</span>
      </div>

      <div className="track">
        {/* 顶层位置标记：冲突与缺口 */}
        <div className="track-marks">
          {marks.cs.map((p) => (
            <i key={`c${p}`} className="mark mark-conflict" style={{ left: pct(p), width: pct(1) }} title={`冲突位置 ${p}`} />
          ))}
          {marks.gs.map((p) => (
            <i key={`g${p}`} className="mark mark-gap" style={{ left: pct(p), width: pct(1) }} title={`缺口位置 ${p}`} />
          ))}
        </div>

        {spans.length === 0 && <p className="muted">（无片段）</p>}
        {spans.map((s) => (
          <div className="track-row" key={s.id}>
            <span className="track-label">{s.id}</span>
            <div className="track-bar">
              <div
                className={"seg seg-" + s.kind}
                style={{ left: pct(s.offset), width: pct(s.length) }}
                title={`${s.id}: offset=${s.offset}, len=${s.length}`}
              />
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
