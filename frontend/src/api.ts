import type { AnalyzeResponse, FragmentInput, ValidationError } from "./types";

export async function analyze(
  targetLength: string,
  fragments: FragmentInput[],
  signal?: AbortSignal,
): Promise<{ ok: true; data: AnalyzeResponse } | { ok: false; errors: ValidationError[]; status: number }> {
  let res: Response;
  try {
    res = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        target_length: targetLength === "" ? null : Number(targetLength),
        fragments: fragments.map((f) => ({
          id: f.id,
          offset: f.offset === "" ? null : Number(f.offset),
          payload_hex: f.payload_hex.trim(),
          weight: f.weight === "" ? null : Number(f.weight),
        })),
      }),
      signal,
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    return { ok: false, status: 0, errors: [{ loc: [], msg: "无法连接业务 API", type: "network" }] };
  }

  if (res.ok) {
    return { ok: true, data: (await res.json()) as AnalyzeResponse };
  }
  if (res.status === 422) {
    const body = (await res.json()) as { detail: ValidationError[] };
    return { ok: false, status: 422, errors: body.detail ?? [] };
  }
  return { ok: false, status: res.status, errors: [{ loc: [], msg: `服务异常 HTTP ${res.status}`, type: "server" }] };
}

/** 从 422 的 loc 中取出片段下标与字段名。 */
export function locateError(loc: (string | number)[]): { index: number | null; field: string | null } {
  const i = loc.indexOf("fragments");
  if (i >= 0 && typeof loc[i + 1] === "number") {
    const field = typeof loc[i + 2] === "string" ? (loc[i + 2] as string) : null;
    return { index: loc[i + 1] as number, field };
  }
  const top = loc[loc.length - 1];
  return { index: null, field: typeof top === "string" ? top : null };
}
