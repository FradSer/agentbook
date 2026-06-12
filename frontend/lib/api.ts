import type {
  LiveResearchSnapshot,
  MetricsResponse,
  ProblemListItem,
  ProblemTimeline,
  RadarResponse,
  ResearchResponse,
  SearchResponse,
  UsageDashboard,
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

export async function getProblems(
  options: {
    limit?: number;
    offset?: number;
    sortBy?: string;
    order?: string;
  } = {},
): Promise<ProblemListItem[]> {
  const params = new URLSearchParams();
  params.set("limit", String(options.limit ?? 18));
  if (options.offset) params.set("offset", String(options.offset));
  if (options.sortBy) params.set("sort_by", options.sortBy);
  if (options.order) params.set("order", options.order);
  return request<ProblemListItem[]>(`/v1/problems?${params.toString()}`);
}

export async function getProblemTimeline(
  problemId: string,
): Promise<ProblemTimeline> {
  return request<ProblemTimeline>(`/v1/problems/${problemId}/timeline`);
}

export async function fetchRadar(): Promise<RadarResponse> {
  return request<RadarResponse>("/v1/dashboard/radar");
}

export async function fetchMetrics(): Promise<MetricsResponse> {
  return request<MetricsResponse>("/v1/dashboard/metrics");
}

export async function fetchUsageDashboard(): Promise<UsageDashboard> {
  return request<UsageDashboard>("/v1/dashboard/usage");
}

export async function fetchLiveResearchSnapshot(
  signal?: AbortSignal,
): Promise<LiveResearchSnapshot> {
  return request<LiveResearchSnapshot>("/v1/dashboard/research/live", {
    signal,
  });
}

export type HealthMetrics = {
  sandbox_pass_rate_24h: number;
  verified_outcome_count_24h: number;
  single_identity_cluster_count_24h: number;
  counters: Record<string, number>;
  generated_at: string;
};

export async function fetchHealthMetrics(): Promise<HealthMetrics> {
  return request<HealthMetrics>("/v1/health-metrics");
}

export async function searchProblems(
  q: string,
  options: { errorLog?: string; limit?: number; signal?: AbortSignal } = {},
): Promise<SearchResponse> {
  const params = new URLSearchParams({ q, limit: String(options.limit ?? 18) });
  if (options.errorLog) params.set("error_log", options.errorLog);
  return request<SearchResponse>(`/v1/search?${params.toString()}`, {
    signal: options.signal,
  });
}

export async function fetchResearchActivity(
  memoryId: string,
  options: { limit?: number; signal?: AbortSignal } = {},
): Promise<ResearchResponse> {
  const params = new URLSearchParams({
    memory_id: memoryId,
    limit: String(options.limit ?? 50),
  });
  return request<ResearchResponse>(
    `/v1/research-activity?${params.toString()}`,
    {
      signal: options.signal,
    },
  );
}

export { ApiError };
