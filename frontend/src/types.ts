export interface FragmentInput {
  id: string;
  offset: string;
  payload_hex: string;
  weight: string;
}

export interface ConflictSide {
  fragment_id: string;
  offset: number;
}

export interface Conflict {
  a: ConflictSide;
  b: ConflictSide;
  first_position: number;
  positions: number[];
  byte_a: string;
  byte_b: string;
}

export interface BodyWitness {
  body_hex: string;
  witness_fragment_ids: string[];
}

export type VerdictStatus = "UNIQUE" | "AMBIGUOUS" | "IMPOSSIBLE";
export type ImpossibleReason = "GAP" | "CONFLICT" | null;

export interface AnalyzeResponse {
  status: VerdictStatus;
  target_length: number;
  optimal_weight: number | null;
  optimal_fragment_count: number | null;
  impossible_reason: ImpossibleReason;
  bodies: BodyWitness[];
  conflicts: Conflict[];
}

export interface ValidationError {
  loc: (string | number)[];
  msg: string;
  type: string;
}
