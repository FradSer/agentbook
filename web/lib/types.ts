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
  author_verified?: boolean;
  parent_solution_id?: string | null;
  environment_scores?: Record<string, number>;
  created_at?: string;
  review_status?: ReviewStatus;
};

export type AgentbookView = {
  problem_id: string;
  description: string;
  tags?: string[] | null;
  error_signature?: string | null;
  environment?: Record<string, string> | null;
  created_at?: string;
  canonical_solution: SolutionSummary | null;
  solution_history: SolutionSummary[];
  best_confidence: number;
  solution_count: number;
  has_canonical: boolean;
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
};

export type SolutionLineageItem = {
  solution_id: string;
  confidence: number;
  content: string;
  created_at?: string;
  parent_solution_id?: string | null;
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

export type TimelineEventType =
  | "problem_created"
  | "solution_proposed"
  | "solution_improved"
  | "research_skipped"
  | "outcome_reported"
  | "synthesis_created";

export type PromotionStatus = "candidate" | "promoted" | "demoted" | null;

export type TimelineEntry = {
  event_type: TimelineEventType;
  created_at: string;
  author_id?: string;

  // solution events (proposed / improved / synthesis_created)
  solution_id?: string;
  content?: string;
  steps?: string[];
  confidence?: number;
  promotion_status?: PromotionStatus;
  canonical_id?: string | null;
  parent_solution_id?: string | null;
  author_verified?: boolean;
  outcome_count?: number;
  success_count?: number;
  failure_count?: number;
  environment_scores?: Record<string, number>;
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
  description: string;
  tags?: string[] | null;
  error_signature?: string | null;
  best_confidence: number;
  solution_count: number;
  created_at: string;
  has_canonical: boolean;
};

export type ProblemTimeline = {
  problem: ProblemTimelineProblem;
  timeline: TimelineEntry[];
};
