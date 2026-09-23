import type { FragmentInput } from "./types";

export interface Example {
  name: string;
  description: string;
  target_length: string;
  fragments: FragmentInput[];
}

const f = (id: string, offset: number, payload_hex: string, weight: number): FragmentInput => ({
  id,
  offset: String(offset),
  payload_hex,
  weight: String(weight),
});

export const EXAMPLES: Example[] = [
  {
    name: "等分正文",
    description: "两个无重叠片段首尾相接，唯一还原 4 字节正文。",
    target_length: "4",
    fragments: [f("A", 0, "0011", 5), f("B", 2, "2233", 5)],
  },
  {
    name: "高权片段互斥（歧义）",
    description: "两份高权片段各自声称不同的完整正文且互不相容，最优值并列 → AMBIGUOUS。",
    target_length: "4",
    fragments: [
      f("A", 0, "00000000", 100),
      f("B", 0, "ffffffff", 100),
      f("E", 0, "0000", 5),
      f("F", 0, "ffff", 5),
    ],
  },
  {
    name: "缺口（IMPOSSIBLE）",
    description: "片段之间留有未覆盖位置 2，任何方案都无法覆盖全文。",
    target_length: "4",
    fragments: [f("A", 0, "0011", 5), f("B", 3, "33", 5)],
  },
  {
    name: "片段冲突（IMPOSSIBLE）",
    description: "两个片段都必须入选才能覆盖全文，但重叠位置字节不同 → 无法一致覆盖。",
    target_length: "3",
    fragments: [f("A", 0, "0011", 10), f("B", 1, "2233", 10)],
  },
  {
    name: "重叠一致 · 权重叠加",
    description: "重叠内容相同，片段全部采用，总权重与片段数同时最大。",
    target_length: "4",
    fragments: [f("A", 0, "aabbccdd", 10), f("B", 2, "ccdd", 5)],
  },
];
