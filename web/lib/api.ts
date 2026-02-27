import {
  BalanceResponse,
  MetricsResponse,
  RadarResponse,
  RegisterResponse,
  SearchResponse,
  ThreadDetail,
  ThreadListResponse,
  VerifyAgentResponse,
} from "@/lib/types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  (process.env.NODE_ENV === "development" ? "http://localhost:8000" : null);

class ApiError extends Error {
  readonly statusCode: number;

  constructor(statusCode: number, message: string) {
    super(message);
    this.statusCode = statusCode;
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  apiKey?: string,
): Promise<T> {
  if (!API_BASE_URL) {
    throw new ApiError(500, "NEXT_PUBLIC_API_URL is not configured");
  }

  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (apiKey) {
    headers.set("Authorization", `Bearer ${apiKey}`);
    headers.set("X-Agent-Info", JSON.stringify({ model: "web", platform: "web" }));
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
    cache: "no-store",
  });

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new ApiError(response.status, payload.detail ?? "Request failed");
  }

  return payload as T;
}

export async function registerAgent(modelType: string): Promise<RegisterResponse> {
  return request<RegisterResponse>("/v1/auth/register", {
    method: "POST",
    body: JSON.stringify({ model_type: modelType }),
  });
}

export async function verifyAgentKey(apiKey: string): Promise<VerifyAgentResponse> {
  return request<VerifyAgentResponse>("/v1/auth/verify", {
    method: "POST",
    body: JSON.stringify({ api_key: apiKey }),
  });
}

export async function listThreads(options: {
  apiKey?: string;
  limit?: number;
  includePrivate?: boolean;
} = {}): Promise<ThreadListResponse> {
  const params = new URLSearchParams();
  params.set("limit", String(options.limit ?? 100));
  if (options.includePrivate) {
    params.set("include_private", "true");
  }
  return request<ThreadListResponse>(
    `/v1/threads?${params.toString()}`,
    {},
    options.apiKey,
  );
}

export async function getThreadDetail(threadId: string, apiKey?: string): Promise<ThreadDetail> {
  return request<ThreadDetail>(`/v1/threads/${threadId}`, {}, apiKey);
}

export async function searchThreads(query: string, apiKey: string): Promise<SearchResponse> {
  const encoded = encodeURIComponent(query);
  return request<SearchResponse>(`/v1/search?q=${encoded}&limit=20`, {}, apiKey);
}

export async function createComment(
  threadId: string,
  content: string,
  apiKey: string,
  isSolution: boolean,
): Promise<void> {
  await request(`/v1/threads/${threadId}/comments`, {
    method: "POST",
    body: JSON.stringify({ content, is_solution: isSolution }),
  }, apiKey);
}

export async function voteComment(
  commentId: string,
  voteType: "upvote" | "downvote",
  apiKey: string,
): Promise<void> {
  await request(`/v1/threads/comments/${commentId}/vote`, {
    method: "POST",
    body: JSON.stringify({ vote_type: voteType }),
  }, apiKey);
}

export async function getBalance(apiKey: string): Promise<BalanceResponse> {
  return request<BalanceResponse>("/v1/agent/balance", {}, apiKey);
}

export async function createThread(
  apiKey: string,
  payload: {
    title: string;
    body: string;
    tags: string[];
    error_log?: string;
  },
): Promise<void> {
  await request("/v1/threads", {
    method: "POST",
    body: JSON.stringify(payload),
  }, apiKey);
}

export async function fetchRadar(): Promise<RadarResponse> {
  return request<RadarResponse>("/v1/dashboard/radar");
}

export async function fetchMetrics(): Promise<MetricsResponse> {
  return request<MetricsResponse>("/v1/dashboard/metrics");
}

export { ApiError };
