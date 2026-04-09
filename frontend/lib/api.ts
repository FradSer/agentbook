import type {
  AgentbookView,
  MetricsResponse,
  ProblemListItem,
  ProblemTimeline,
  RadarResponse,
  SolutionLineageItem,
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

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  if (!API_BASE_URL) {
    throw new ApiError(500, "NEXT_PUBLIC_API_URL is not configured");
  }

  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");

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

// V3 Problem/Solution/Outcome endpoints

export async function getProblems(
  options: {
    limit?: number;
    offset?: number;
    sortBy?: string;
    order?: string;
  } = {},
): Promise<ProblemListItem[]> {
  const params = new URLSearchParams();
  params.set("limit", String(options.limit ?? 20));
  if (options.offset) params.set("offset", String(options.offset));
  if (options.sortBy) params.set("sort_by", options.sortBy);
  if (options.order) params.set("order", options.order);
  return request<ProblemListItem[]>(`/v1/problems?${params.toString()}`);
}

export async function getProblemDetail(
  problemId: string,
): Promise<AgentbookView> {
  return request<AgentbookView>(`/v1/problems/${problemId}`);
}

export async function getProblemTimeline(
  problemId: string,
): Promise<ProblemTimeline> {
  return request<ProblemTimeline>(`/v1/problems/${problemId}/timeline`);
}

export async function getSolutionLineage(
  solutionId: string,
): Promise<{ lineage: SolutionLineageItem[] }> {
  return request<{ lineage: SolutionLineageItem[] }>(
    `/v1/solutions/${solutionId}/lineage`,
  );
}

export async function getRadar(): Promise<RadarResponse> {
  return request<RadarResponse>("/v1/dashboard/radar");
}

export async function getMetrics(): Promise<MetricsResponse> {
  return request<MetricsResponse>("/v1/dashboard/metrics");
}

// Aliases for backward compatibility with dashboard
export { ApiError, getMetrics as fetchMetrics, getRadar as fetchRadar };
