import { useState } from "react";
import type { BodyWitness } from "../types";
import { toHexRows } from "../hex";

interface Props {
  targetLength: number;
  bodies: BodyWitness[];
  activeBody: number;
  onActiveBody: (i: number) => void;
  fragmentSpans: { id: string; offset: number; length: number }[];
}

/**
 * 正文十六进制转储：每行 16 字节，带地址列、ASCII 列；
 * 悬停字节可查看覆盖它的采用片段；属于见证片段的字节加底色。
 */
export function HexView({ targetLength, bodies, activeBody, onActiveBody, fragmentSpans }: Props) {
  const [hover, setHover] = useState<number | null>(null);
  const active = Math.min(activeBody, bodies.length - 1);
  const body = bodies[active];
  if (!body) return null;

  const witnessSet = new Set(body.witness_fragment_ids);
  const rows = toHexRows(body.body_hex.padEnd(targetLength * 2, "0"));

  const coveringAt = (p: number) =>
    fragmentSpans
      .filter((s) => witnessSet.has(s.id) && p >= s.offset && p < s.offset + s.length)
      .map((s) => s.id);

  return (
    <section className="panel hexview">
      <div className="panel-head">
        <h2>② 正文十六进制</h2>
        {bodies.length > 1 && (
          <div className="body-tabs" role="tablist">
            {bodies.map((b, i) => (
              <button
                key={i}
                role="tab"
                aria-selected={i === active}
                className={"btn-chip" + (i === active ? " active" : "")}
                onClick={() => onActiveBody(i)}
                title={b.body_hex}
              >
                候选正文 #{i + 1}（字节序第 {i + 1} 小）
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="hex-meta">
        <span className="mono">{body.body_hex}</span>
      </div>

      <div className="hex-dump" onMouseLeave={() => setHover(null)}>
        {rows.map((row) => (
          <div className="hex-row" key={row.address}>
            <span className="hex-addr">{String(row.address).padStart(4, "0")}</span>
            <span className="hex-cells">
              {row.cells.map((c) => (
                <span
                  key={c.position}
                  className={"hex-cell" + (hover === c.position ? " hover" : "")}
                  onMouseEnter={() => setHover(c.position)}
                >
                  {c.hex}
                </span>
              ))}
            </span>
            <span className="hex-ascii mono">{row.ascii}</span>
          </div>
        ))}
      </div>

      <div className="hex-tip">
        {hover === null ? (
          <span className="muted">悬停任意字节查看该位置由哪些采用片段覆盖。共 {targetLength} 字节。</span>
        ) : (
          <span>
            位置 <b>{hover}</b>（0x{hover.toString(16).padStart(2, "0")}）=
            <b className="mono"> {body.body_hex.slice(hover * 2, hover * 2 + 2)}</b>
            ，覆盖片段：{coveringAt(hover).length ? coveringAt(hover).join("、") : "（无）"}
          </span>
        )}
      </div>
    </section>
  );
}
