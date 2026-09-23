import { useEffect, useMemo, useRef, useState } from "react";
import { analyze } from "./api";
import { EXAMPLES } from "./examples";
import type { AnalyzeResponse, FragmentInput, ValidationError } from "./types";
import { FragmentEditor } from "./components/FragmentEditor";
import { VerdictPanel } from "./components/VerdictPanel";
import { HexView } from "./components/HexView";
import { CoverageTrack, type Span } from "./components/CoverageTrack";
import { ConflictPanel } from "./components/ConflictPanel";

const DEBOUNCE_MS = 450;

function emptyFragment(): FragmentInput {
  return { id: "", offset: "", payload_hex: "", weight: "" };
}

export default function App() {
  const [targetLength, setTargetLength] = useState(EXAMPLES[0].target_length);
  const [fragments, setFragments] = useState<FragmentInput[]>(EXAMPLES[0].fragments.map((x) => ({ ...x })));
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [errors, setErrors] = useState<ValidationError[]>([]);
  const [pending, setPending] = useState(false);
  const [activeBody, setActiveBody] = useState(0);

  const abortRef = useRef<AbortController | null>(null);
  const reqSeq = useRef(0);

  // 输入一旦变化：立即撤下旧裁决与旧错误，防抖后重新请求。
  const bump = () => {
    setResult(null);
    setErrors([]);
    setPending(true);
  };

  useEffect(() => {
    bump();
    const seq = ++reqSeq.current;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    const timer = setTimeout(async () => {
      const r = await analyze(targetLength, fragments, controller.signal);
      if (seq !== reqSeq.current) return; // 已被更新的输入取代
      setPending(false);
      if (r.ok) {
        setResult(r.data);
        setErrors([]);
        setActiveBody(0);
      } else {
        setResult(null);
        setErrors(r.errors);
      }
    }, DEBOUNCE_MS);

    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targetLength, fragments]);

  const updateField = (index: number, field: keyof FragmentInput, value: string) => {
    setFragments((prev) => prev.map((f, i) => (i === index ? { ...f, [field]: value } : f)));
  };
  const addFragment = () => setFragments((prev) => (prev.length >= 28 ? prev : [...prev, emptyFragment()]));
  const removeFragment = (index: number) => setFragments((prev) => prev.filter((_, i) => i !== index));
  const loadExample = (i: number) => {
    const ex = EXAMPLES[i];
    setTargetLength(ex.target_length);
    setFragments(ex.fragments.map((x) => ({ ...x })));
  };

  // 从当前输入解析片段区间（用于覆盖轨道；非法字段跳过）。
  const parsedSpans = useMemo(() => {
    const out: { id: string; offset: number; length: number }[] = [];
    for (const f of fragments) {
      const off = Number(f.offset);
      const hex = f.payload_hex.trim();
      if (!f.id || !Number.isInteger(off) || off < 0 || !/^[0-9a-fA-F]*$/.test(hex) || hex.length % 2 !== 0 || hex.length === 0) {
        continue;
      }
      out.push({ id: f.id, offset: off, length: hex.length / 2 });
    }
    return out;
  }, [fragments]);

  const n = Number(targetLength);
  const validN = Number.isInteger(n) && n >= 1 && n <= 512;

  const { trackSpans, conflictPositions, gapPositions } = useMemo(() => {
    const spans: Span[] = parsedSpans.map((s) => ({ ...s, kind: "other" as const }));
    const cpos = new Set<number>();
    const gpos = new Set<number>();
    if (result) {
      const witness = new Set(result.bodies[Math.min(activeBody, Math.max(0, result.bodies.length - 1))]?.witness_fragment_ids ?? []);
      for (const s of spans) if (witness.has(s.id)) s.kind = "adopted";
      for (const c of result.conflicts) for (const p of c.positions) cpos.add(p);
      if (result.status === "IMPOSSIBLE" && result.impossible_reason === "GAP" && validN) {
        const covered = new Array<boolean>(n).fill(false);
        for (const s of parsedSpans) {
          for (let p = s.offset; p < s.offset + s.length && p < n; p++) {
            if (p >= 0) covered[p] = true;
          }
        }
        covered.forEach((v, p) => {
          if (!v) gpos.add(p);
        });
      }
    }
    return { trackSpans: spans, conflictPositions: cpos, gapPositions: gpos };
  }, [parsedSpans, result, activeBody, n, validN]);

  const hasResult = !!result;

  return (
    <div className="app">
      <header className="app-header">
        <h1>档案片段重建台</h1>
        <p className="subtitle">
          导入或编辑重叠字节片段 → 业务 API 返回最优一致覆盖：先最大化总权重，再最大化片段数；
          裁决 <code>UNIQUE</code> / <code>AMBIGUOUS</code> / <code>IMPOSSIBLE</code>。
        </p>
        <div className={"status-line" + (pending ? " pending" : "")}>
          {pending ? "⏳ 输入已变更，正在重新分析，旧裁决已撤下…" : hasResult ? "✓ 裁决为最新输入的结果" : ""}
        </div>
      </header>

      <FragmentEditor
        targetLength={targetLength}
        fragments={fragments}
        errors={errors}
        onTargetLength={setTargetLength}
        onChange={updateField}
        onAdd={addFragment}
        onRemove={removeFragment}
        onLoadExample={loadExample}
        exampleNames={EXAMPLES.map((e) => e.name)}
      />

      {errors.length > 0 && (
        <section className="panel error-panel">
          <h2>输入校验未通过（HTTP 422）</h2>
          <ul>
            {errors.map((e, i) => (
              <li key={i}>
                <span className="loc">loc = [{e.loc.map((x) => JSON.stringify(x)).join(", ")}]</span>
                <span className="msg">{e.msg}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {hasResult && result && (
        <>
          <VerdictPanel result={result} />
          {result.status !== "IMPOSSIBLE" && (
            <HexView
              targetLength={result.target_length}
              bodies={result.bodies}
              activeBody={activeBody}
              onActiveBody={setActiveBody}
              fragmentSpans={parsedSpans}
            />
          )}
          <CoverageTrack
            targetLength={validN ? n : result.target_length || 1}
            spans={trackSpans}
            conflictPositions={conflictPositions}
            gapPositions={gapPositions}
          />
          <ConflictPanel conflicts={result.conflicts} />
        </>
      )}

      {!hasResult && !pending && errors.length === 0 && (
        <section className="panel placeholder">
          <p className="muted">编辑片段后将自动请求分析…</p>
        </section>
      )}

      <footer className="app-footer">
        字段位置（loc）遵循 <code>body.fragments[i].field</code>；正文按无符号字节序排序。
      </footer>
    </div>
  );
}
