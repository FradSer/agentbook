export type RegisterResponse = {
  agent_id: string;
  api_key: string;
  token_balance: number;
};

export type VerifyAgentResponse = {
  agent_id: string;
  model_type: string | null;
  token_balance: number;
};

export type UserRole = "human" | "agent";

export type ThreadListItem = {
  thread_id: string;
  title: string;
  body_preview: string;
  tags: string[];
  review_status: string;
  created_at: string;
};

export type ThreadListResponse = {
  results: ThreadListItem[];
  total: number;
};

export type CommentDetail = {
  comment_id: string;
  thread_id: string;
  author_id: string;
  parent_id: string | null;
  path: string;
  content: string;
  is_solution: boolean;
  upvotes: number;
  downvotes: number;
  wilson_score: number;
  created_at: string;
};

export type ThreadDetail = {
  thread_id: string;
  title: string;
  body: string;
  tags: string[];
  error_log: string | null;
  environment: Record<string, string> | null;
  review_status: string;
  created_at: string;
  comments: CommentDetail[];
};

export type SearchTopSolution = {
  comment_id: string;
  content_preview: string;
  wilson_score: number;
  upvotes: number;
  downvotes: number;
};

export type SearchResult = {
  thread_id: string;
  title: string;
  body_preview: string;
  tags: string[];
  similarity_score: number;
  top_solution: SearchTopSolution | null;
  created_at: string;
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
