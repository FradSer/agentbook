import { config } from "./config.js";

export class WorkerApi {
  async get<T>(path: string): Promise<T> {
    return this.request<T>(path);
  }

  async post<T>(path: string, body: unknown): Promise<T> {
    return this.request<T>(path, { method: "POST", body: JSON.stringify(body) });
  }

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    // Bound each backend tool-call leg. The old Python loop relied on the
    // OS/undici defaults; this Node fetch is bare without an AbortSignal, so a
    // stalled backend (Railway deploy churn, a hung DB query) would hang the
    // worker cycle indefinitely under a green process-alive health check. 30s
    // per request is well under the 1500s cycle cap in main.ts and lets the
    // agent retry the next poll rather than wedging on one call.
    const response = await fetch(`${config.apiUrl}${path}`, {
      ...init,
      headers: {
        Authorization: `Bearer ${config.workerApiKey}`,
        "Content-Type": "application/json",
        ...init.headers,
      },
      signal: AbortSignal.timeout(30_000),
    });
    if (!response.ok) throw new Error(`worker API ${response.status}: ${await response.text()}`);
    return response.json() as Promise<T>;
  }
}
