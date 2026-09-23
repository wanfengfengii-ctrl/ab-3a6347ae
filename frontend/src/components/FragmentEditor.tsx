import type { FragmentInput, ValidationError } from "../types";
import { locateError } from "../api";

interface Props {
  targetLength: string;
  fragments: FragmentInput[];
  errors: ValidationError[];
  onTargetLength: (v: string) => void;
  onChange: (index: number, field: keyof FragmentInput, value: string) => void;
  onAdd: () => void;
  onRemove: (index: number) => void;
  onLoadExample: (index: number) => void;
  exampleNames: string[];
}

export function FragmentEditor({
  targetLength,
  fragments,
  errors,
  onTargetLength,
  onChange,
  onAdd,
  onRemove,
  onLoadExample,
  exampleNames,
}: Props) {
  const fieldErrors = (index: number, field: string): string[] =>
    errors
      .filter((e) => {
        const loc = locateError(e.loc);
        return loc.index === index && loc.field === field;
      })
      .map((e) => e.msg);

  const rowErrors = (index: number): string[] =>
    errors
      .filter((e) => {
        const loc = locateError(e.loc);
        return loc.index === index && loc.field === null;
      })
      .map((e) => e.msg);

  const topErrors = (field: string): string[] =>
    errors
      .filter((e) => {
        const loc = locateError(e.loc);
        return loc.index === null && loc.field === field;
      })
      .map((e) => e.msg);

  const globalErrors = errors.filter((e) => locateError(e.loc).index === null && locateError(e.loc).field === null);

  const cell = (errs: string[]) => (errs.length ? " cell-error" : "");

  return (
    <section className="panel editor">
      <div className="panel-head">
        <h2>① 输入区 · 目标与片段</h2>
        <div className="examples">
          <span className="muted">载入示例：</span>
          {exampleNames.map((name, i) => (
            <button key={name} type="button" className="btn-chip" onClick={() => onLoadExample(i)}>
              {name}
            </button>
          ))}
        </div>
      </div>

      <label className="target-row">
        <span>目标长度（字节，1–512）</span>
        <input
          className={topErrors("target_length").length ? "input-error" : ""}
          value={targetLength}
          onChange={(e) => onTargetLength(e.target.value)}
          inputMode="numeric"
          style={{ width: 120 }}
        />
        <span className="muted">当前 {fragments.length} / 28 个片段（需 2–28）</span>
      </label>
      {topErrors("target_length").map((m, i) => (
        <div key={i} className="field-msg">
          {m}
        </div>
      ))}

      <div className="table-wrap">
        <table className="frag-table">
          <thead>
            <tr>
              <th style={{ width: 40 }}>#</th>
              <th style={{ width: 150 }}>唯一编号</th>
              <th style={{ width: 110 }}>偏移（≥0）</th>
              <th>十六进制载荷（非空、偶数位）</th>
              <th style={{ width: 130 }}>可信权重 1–1000000</th>
              <th style={{ width: 48 }}></th>
            </tr>
          </thead>
          <tbody>
            {fragments.map((frag, i) => (
              <FragmentRows
                key={i}
                i={i}
                frag={frag}
                onChange={onChange}
                onRemove={onRemove}
                fieldErrors={fieldErrors}
                rowErrors={rowErrors}
                cell={cell}
              />
            ))}
          </tbody>
        </table>
      </div>

      <div className="editor-actions">
        <button type="button" className="btn" onClick={onAdd} disabled={fragments.length >= 28}>
          ＋ 新增片段
        </button>
        {topErrors("fragments").map((m, i) => (
          <span key={i} className="field-msg inline">
            {m}
          </span>
        ))}
        {globalErrors.map((e, i) => (
          <span key={i} className="field-msg inline">
            {e.msg}
          </span>
        ))}
      </div>
    </section>
  );
}

interface RowProps {
  i: number;
  frag: FragmentInput;
  onChange: (index: number, field: keyof FragmentInput, value: string) => void;
  onRemove: (index: number) => void;
  fieldErrors: (index: number, field: string) => string[];
  rowErrors: (index: number) => string[];
  cell: (errs: string[]) => string;
}

function FragmentRows({ i, frag, onChange, onRemove, fieldErrors, rowErrors, cell }: RowProps) {
  const msgs = [
    ...fieldErrors(i, "id"),
    ...fieldErrors(i, "offset"),
    ...fieldErrors(i, "payload_hex"),
    ...fieldErrors(i, "weight"),
    ...rowErrors(i),
  ];
  return (
    <>
      <tr>
        <td className="muted idx">{i}</td>
        <td className={cell(fieldErrors(i, "id"))}>
          <input value={frag.id} onChange={(e) => onChange(i, "id", e.target.value)} placeholder="如 A-01" />
        </td>
        <td className={cell(fieldErrors(i, "offset"))}>
          <input
            value={frag.offset}
            onChange={(e) => onChange(i, "offset", e.target.value)}
            inputMode="numeric"
          />
        </td>
        <td className={"mono" + cell(fieldErrors(i, "payload_hex"))}>
          <input
            value={frag.payload_hex}
            onChange={(e) => onChange(i, "payload_hex", e.target.value)}
            placeholder="如 deadbeef"
            spellCheck={false}
          />
        </td>
        <td className={cell(fieldErrors(i, "weight"))}>
          <input
            value={frag.weight}
            onChange={(e) => onChange(i, "weight", e.target.value)}
            inputMode="numeric"
          />
        </td>
        <td>
          <button type="button" className="btn-del" onClick={() => onRemove(i)} title="删除该片段">
            ✕
          </button>
        </td>
      </tr>
      {msgs.length > 0 && (
        <tr className="err-row">
          <td />
          <td colSpan={5}>
            {msgs.map((m, k) => (
              <div key={k} className="field-msg">
                {m}
              </div>
            ))}
          </td>
        </tr>
      )}
    </>
  );
}
