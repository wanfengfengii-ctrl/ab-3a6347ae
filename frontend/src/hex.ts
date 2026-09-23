/** 十六进制展示辅助。 */

export function byteAt(hex: string, position: number): string | null {
  const i = position * 2;
  if (i < 0 || i + 1 >= hex.length) return null;
  return hex.slice(i, i + 2);
}

/** 每行 16 字节的十六进制转储（含偏移列与 ASCII）。 */
export interface HexRow {
  address: number;
  cells: { position: number; hex: string }[];
  ascii: string;
}

export function toHexRows(hex: string, bytesPerRow = 16): HexRow[] {
  const total = Math.floor(hex.length / 2);
  const rows: HexRow[] = [];
  for (let addr = 0; addr < total; addr += bytesPerRow) {
    const cells: HexRow["cells"] = [];
    let ascii = "";
    for (let p = addr; p < Math.min(addr + bytesPerRow, total); p++) {
      const b = parseInt(hex.slice(p * 2, p * 2 + 2), 16);
      cells.push({ position: p, hex: hex.slice(p * 2, p * 2 + 2) });
      ascii += b >= 0x20 && b <= 0x7e ? String.fromCharCode(b) : "·";
    }
    rows.push({ address: addr, cells, ascii });
  }
  return rows;
}

/** 判断某个位置落在哪些片段的覆盖区间（offset..offset+len）。 */
export function coveringFragment(
  fragments: { id: string; offset: number; length: number }[],
  position: number,
): string[] {
  return fragments
    .filter((f) => position >= f.offset && position < f.offset + f.length)
    .map((f) => f.id);
}
