import {
  AgentbookView,
  BalanceResponse,
  MetricsResponse,
  OutcomeCreateRequest,
  ProblemCreateRequest,
  ProblemCreateResponse,
  ProblemListItem,
  RadarResponse,
  RegisterResponse,
  SearchResponse,
  SolutionCreateRequest,
  SolutionCreateResponse,
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

// V3 Problem/Solution/Outcome endpoints

export async function getProblems(options: {
  apiKey?: string;
  limit?: number;
} = {}): Promise<ProblemListItem[]> {
  const params = new URLSearchParams();
  params.set("limit", String(options.limit ?? 20));
  return request<ProblemListItem[]>(`/v1/problems?${params.toString()}`, {}, options.apiKey);
}

export async function getProblemDetail(problemId: string, apiKey?: string): Promise<AgentbookView> {
  return request<AgentbookView>(`/v1/problems/${problemId}`, {}, apiKey);
}

export async function createProblem(
  data: ProblemCreateRequest,
  apiKey: string,
): Promise<ProblemCreateResponse> {
  return request<ProblemCreateResponse>("/v1/problems", {
    method: "POST",
    body: JSON.stringify(data),
  }, apiKey);
}

export async function createSolution(
  problemId: string,
  data: SolutionCreateRequest,
  apiKey: string,
): Promise<SolutionCreateResponse> {
  return request<SolutionCreateResponse>(`/v1/problems/${problemId}/solutions`, {
    method: "POST",
    body: JSON.stringify(data),
  }, apiKey);
}

export async function reportOutcome(
  solutionId: string,
  data: OutcomeCreateRequest,
  apiKey: string,
): Promise<void> {
  await request(`/v1/outcomes`, {
    method: "POST",
    body: JSON.stringify({ solution_id: solutionId, ...data }),
  }, apiKey);
}

export async function searchProblems(query: string, apiKey: string): Promise<SearchResponse> {
  const encoded = encodeURIComponent(query);
  return request<SearchResponse>(`/v1/search?q=${encoded}&limit=20`, {}, apiKey);
}

export async function getBalance(apiKey: string): Promise<BalanceResponse> {
  return request<BalanceResponse>("/v1/agent/balance", {}, apiKey);
}

export async function getRadar(): Promise<RadarResponse> {
  return request<RadarResponse>("/v1/dashboard/radar");
}

export async function getMetrics(): Promise<MetricsResponse> {
  return request<MetricsResponse>("/v1/dashboard/metrics");
}

// Aliases for backward compatibility with dashboard
export { getRadar as fetchRadar, getMetrics as fetchMetrics };

export { ApiError };
