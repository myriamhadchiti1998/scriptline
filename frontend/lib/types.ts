export type IdeaStatus = "pending" | "approved" | "rejected";
export type ScriptStatus = "queued" | "writing" | "reviewing" | "revising" | "delivered" | "held" | "failed";

export interface IceReasoning {
  impact: string;
  confidence: string;
  ease: string;
  verdict: string;
  risk_flags: string[];
}

export interface Idea {
  id: number;
  run_id: number;
  client_id: string;
  status: IdeaStatus;
  concept_hook: string;
  creative_type: string;
  angle: string;
  lead_type: string;
  hook_family: string;
  proof_point_ids: string[];
  target_avatar: string;
  pain_addressed: string;
  funnel_stage: "cold" | "retargeting";
  strategist_note: string;
  ice_impact: number;
  ice_confidence: number;
  ice_ease: number;
  ice_total: number;
  ice_reasoning: IceReasoning;
  nearest_prior_id: number | null;
  nearest_prior_similarity: number | null;
  decision_note: string | null;
  decided_at: string | null;
  created_at: string;
  script: { id: number; status: ScriptStatus } | null;
}

export interface CodeCheck {
  level: "hard" | "flag";
  item: number;
  message: string;
  excerpt: string;
}

export interface ReviewItem {
  id: number;
  name: string;
  passed: boolean;
  ai_score: number;
  evidence: string;
  reasoning: string;
  code_checks: CodeCheck[];
  fail_reasons: string[];
}

export interface Review {
  passed: boolean;
  failed_items: number[];
  score: number;
  items: ReviewItem[];
  voice: Record<string, number | string>;
  claim_audit: { claim: string; proof_id: string }[];
  flag_rulings: { phrase: string; acceptable: boolean; reason: string }[];
  metrics: {
    seconds_range: [number, number];
    total_words_range: [number, number];
    avg_sentence_words: number;
    max_sentence_words: number;
    [k: string]: unknown;
  };
  top_fix: string;
  judge_model: string;
  pass_rule: string;
}

export interface ScriptContent {
  title: string;
  production_notes: string[];
  hook_plan?: { hook: string; interrupt_type: string; door: string }[];
  hook_1: string;
  hook_2: string;
  hook_3: string;
  body: { pain: string; promise: string; proof: string; cta: string };
  open_loop: { opened_with: string; closed_with: string };
  claims: { claim: string; proof_id: string }[];
}

export interface ScriptVersion {
  version: number;
  content: ScriptContent;
  review: Review | null;
  passed: number | null;
  created_at: string;
}

export interface Script {
  id: number;
  idea_id: number;
  client_id: string;
  status: ScriptStatus;
  current_version: number;
  review_score: number | null;
  docx_path: string | null;
  md_path: string | null;
  error: string | null;
  created_at: string;
  updated_at: string;
  idea: Idea;
  latest: ScriptVersion | null;
  version_count: number;
  docx_available: boolean;
  versions?: ScriptVersion[];
}

export interface Run {
  id: number;
  status: "running" | "completed" | "failed";
  trigger: string;
  batch_size: number;
  generated: number;
  kept: number;
  duplicates_dropped: number;
  invalid_dropped: number;
  error: string | null;
  created_at: string;
  finished_at: string | null;
}

export interface Summary {
  ideas: Record<IdeaStatus, number>;
  scripts: Record<ScriptStatus, number>;
  runs: Run[];
  learning: {
    ideas_in_memory: number;
    human_decisions: number;
    approval_rate: number | null;
    exemplars_available: number;
    first_pass_rate: number | null;
    watchouts: string;
  };
}

export interface EventRow {
  id: number;
  ts: string;
  kind: string;
  ref_id: number | null;
  level: "info" | "success" | "warn" | "error";
  message: string;
}

export interface Health {
  ok: boolean;
  provider: string;
  api_key_set: boolean;
  models: Record<string, string>;
  max_revisions: number;
  pass_score: number;
}

export interface GateTest {
  all_held: boolean;
  results: {
    script: string;
    text: string;
    held: boolean;
    failed_items: number[];
    caught_by_code_items: number[];
    top_reasons: string[];
  }[];
}

export type ProofBank = Record<string, { type: string; text: string }>;
