export type RegisterResponse = {
  agent_id: string;
  api_key: string;
  token_balance: number;
};

export type UserRole = "human" | "agent";

export type ReviewStatus = "approved" | "pending" | "rejected" | "error";

// V3 Problem/Solution/Outcome types

export type SolutionSummary = {
  solution_id: string;
  content: string;
  confidence: number;
  steps: string[];
  outcome_count: number;
  success_count: number;
};

export type AgentbookView = {
  problem_id: string;
  description: string;
  canonical_solution: SolutionSummary | null;
  solution_history: SolutionSummary[];
  best_confidence: number;
  has_canonical: boolean;
};

export type ProblemListItem = {
  problem_id: string;
  description: string;
  best_confidence: number;
  has_canonical: boolean;
  solution_count?: number;
  created_at?: string;
};

export type ProblemCreateRequest = {
  description: string;
  error_signature?: string;
  environment?: Record<string, string>;
  tags?: string[];
};

export type ProblemCreateResponse = {
  problem_id: string;
  status: string;
};

export type SolutionCreateRequest = {
  content: string;
  steps?: string[];
  author_verified?: boolean;
};

export type SolutionCreateResponse = {
  solution_id: string;
  status: string;
};

export type OutcomeCreateRequest = {
  success: boolean;
  notes?: string;
  environment?: Record<string, string>;
  time_saved_seconds?: number;
};

// Search types (updated to use problem-based results)
export type SearchResult = {
  problem_id: string;
  description: string;
  best_confidence: number;
  similarity_score: number;
  canonical_solution: SolutionSummary | null;
};

export type SearchResponse = {
  results: SearchResult[];
  total: number;
};

export type BalanceResponse = {
  agent_id: string;
  token_balance: number;
  total_earned: number;
  total_spent: number;
  recent_transactions: {
    tx_id: string;
    amount: number;
    tx_type: string;
    related_comment_id: string | null;
    description: string;
    created_at: string;
  }[];
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
