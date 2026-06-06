export type ReviewStatus = "approved" | "pending" | "rejected" | "error";

// V3 Problem/Solution/Outcome types

export type SolutionSummary = {
  solution_id: string;
  content: string;
  confidence: number;
  steps: string[];
  outcome_count: number;
  success_count: number;
  author_id?: string;
  llm_model?: string | null;
  parent_solution_id?: string | null;
  created_at?: string;
  review_status?: ReviewStatus;
};

export type ProblemListItem = {
  problem_id: string;
  description: string;
  best_confidence: number;
  has_canonical: boolean;
  solution_count: number;
  tags?: string[] | null;
  error_signature?: string | null;
  environment?: Record<string, string> | null;
  created_at?: string;
  last_activity_at?: string;
  is_being_researched?: boolean;
};

export type RadarProblem = {
  problem_id: string;
  description: string;
  agent_count: number;
  solution_count?: number;
  resolution_rate?: number;
  last_24h_resolve_calls?: number;
  created_at?: string;
  prev_confidence?: number;
  curr_confidence?: number;
  confidence_delta_7d?: number;
};

export type RadarResponse = {
  trending: RadarProblem[];
  new_unsolved: RadarProblem[];
  degrading: RadarProblem[];
};

export type MetricValue = {
  value: number;
  trend: string | null;
  target?: number;
};

export type MetricsResponse = {
  resolution_rate: MetricValue;
  median_ttr_seconds: MetricValue;
  avg_solution_confidence: MetricValue;
  knowledge_coverage: { value: number; trend: string | null };
  knowledge_freshness: MetricValue;
  solutions_needing_synthesis: number;
  stale_solutions: number;
};

// Problem timeline (notebook update chain)

export type PromotionStatus = "candidate" | "promoted" | "demoted" | null;

export type TimelineEntry = {
  event_type:
    | "problem_created"
    | "solution_proposed"
    | "solution_improved"
    | "research_skipped"
    | "outcome_reported"
    | "synthesis_created";
  created_at: string;
  author_id?: string;
  llm_model?: string | null;

  // solution events (proposed / improved / synthesis_created)
  solution_id?: string;
  content?: string;
  steps?: string[];
  confidence?: number;
  promotion_status?: PromotionStatus;
  canonical_id?: string | null;
  parent_solution_id?: string | null;
  outcome_count?: number;
  success_count?: number;
  failure_count?: number;
  review_status?: ReviewStatus;

  // merged from ResearchCycle (solution_improved)
  reasoning?: string;
  confidence_delta?: number;
  previous_best_confidence?: number;
  research_status?: string;

  // outcome_reported
  success?: boolean;
  environment?: Record<string, string>;
  notes?: string | null;
  time_saved_seconds?: number | null;
  weight?: number;

  // problem_created
  description?: string;
  tags?: string[] | null;
  error_signature?: string | null;

  // research_skipped
  status?: string;
};

export type ProblemTimelineProblem = {
  problem_id: string;
  author_id: string;
  llm_model?: string | null;
  description: string;
  tags?: string[] | null;
  error_signature?: string | null;
  best_confidence: number;
  solution_count: number;
  created_at: string;
  updated_at: string;
  has_canonical: boolean;
  /** Points at the row that is the merged canonical book when set. */
  canonical_solution_id?: string | null;
  is_being_researched?: boolean;
};

/** Server-resolved content for the Solution (book) panel — aligns with ``canonical_solution_id`` when set. */
export type BookSolutionPayload = {
  solution_id: string;
  author_id: string;
  content: string;
  steps?: string[];
  root_cause_pattern?: string | null;
  localization_cues?: string[];
  verification?: { command?: string; expected?: string }[];
  root_cause_class?: string | null;
  confidence: number;
  promotion_status?: string | null;
  outcome_count?: number;
  success_count?: number;
  failure_count?: number;
  llm_model?: string | null;
  created_at: string;
  is_synthesized: boolean;
};

export type ProblemTimeline = {
  problem: ProblemTimelineProblem;
  timeline: TimelineEntry[];
  book_solution: BookSolutionPayload | null;
};

// Search

export type SearchResultBestSolution = {
  solution_id: string;
  content_preview: string;
  confidence: number;
};

export type SearchResult = {
  problem_id: string;
  description_preview: string;
  tags: string[];
  solution_count: number;
  best_confidence: number;
  similarity_score: number;
  best_solution: SearchResultBestSolution | null;
  created_at: string;
};

export type SearchResponse = {
  results: SearchResult[];
  total: number;
  no_good_match: boolean;
};

export type SandboxRun = {
  success: boolean;
  notes: string;
  created_at: string;
};

export type ResearchItem = {
  cycle_id: string;
  created_at: string;
  status: string;
  previous_best_confidence: number;
  new_confidence: number;
  reasoning: string;
  sandbox_run: SandboxRun | null;
};

export type ResearchResponse = {
  items: ResearchItem[];
  total: number;
  has_more: boolean;
};

// Live research banner (SSE + REST snapshot)

export type LiveResearchActive = {
  problem_id: string;
  description: string;
  solution_count: number;
  best_confidence: number;
  research_started_at: string; // ISO 8601 UTC
  elapsed_seconds: number;
};

export type LiveResearchRecentCycle = {
  problem_id: string;
  description: string;
  status:
    | "improved"
    | "no_improvement"
    | "no_solution_proposed"
    | "synthesis_completed"
    | string;
  created_at: string; // ISO 8601 UTC
  new_confidence: number;
};

export type LiveResearchSnapshot = {
  active: LiveResearchActive[];
  last_cycle_at: string | null; // ISO 8601 UTC or null
  recent_cycles?: LiveResearchRecentCycle[];
  cycles_last_7_days?: number;
  now: string; // ISO 8601 UTC
};
