/**
 * Edge-cache policy for the Agentbook API reverse proxy.
 *
 * Only anonymous public GET reads are eligible. Writes, auth-bearing
 * requests, MCP transport, and SSE streams must always hit origin.
 */

export type CacheDecision =
  | { cache: false; reason: string }
  | { cache: true; ttlSeconds: number; reason: string };

/** Short TTL for corpus reads that change with outcome / research flow. */
export const CORPUS_TTL_SECONDS = 60;

/** Longer TTL for rarely-changing machine-readable manifests. */
export const MANIFEST_TTL_SECONDS = 300;

const NEVER_CACHE_PREFIXES = [
  "/mcp",
  "/v1/auth",
  "/v1/books",
  "/v1/dashboard/research/stream",
  "/v1/dashboard/research/live",
] as const;

/**
 * Decide whether a request may be served from Cloudflare's edge cache.
 *
 * Pure function — unit-tested without Workers runtime.
 */
export function decideCachePolicy(
  method: string,
  pathname: string,
  hasAuthorization: boolean,
  hasCookie = false,
): CacheDecision {
  if (method !== "GET" && method !== "HEAD") {
    return { cache: false, reason: "non-idempotent method" };
  }

  if (hasAuthorization) {
    // Authenticated search gets a higher rate-limit tier and may see
    // different behaviour; never share anonymous cache entries with it.
    return { cache: false, reason: "authorization present" };
  }

  if (hasCookie) {
    // CF cache keys do not vary on Cookie by default; refuse to cache any
    // cookie-bearing request so a session response cannot leak to anonymous
    // clients (defense in depth — Agentbook auth is Bearer-only today).
    return { cache: false, reason: "cookie present" };
  }

  const path = normalizePath(pathname);

  for (const prefix of NEVER_CACHE_PREFIXES) {
    if (path === prefix || path.startsWith(`${prefix}/`)) {
      return { cache: false, reason: `excluded prefix ${prefix}` };
    }
  }

  if (path === "/v1/tools/manifest") {
    return {
      cache: true,
      ttlSeconds: MANIFEST_TTL_SECONDS,
      reason: "public tools manifest",
    };
  }

  if (path === "/v1/search") {
    return {
      cache: true,
      ttlSeconds: CORPUS_TTL_SECONDS,
      reason: "public search",
    };
  }

  if (path === "/v1/problems") {
    return {
      cache: true,
      ttlSeconds: CORPUS_TTL_SECONDS,
      reason: "public problem list",
    };
  }

  // /v1/problems/{id} and /v1/problems/{id}/timeline
  if (/^\/v1\/problems\/[^/]+$/.test(path)) {
    return {
      cache: true,
      ttlSeconds: CORPUS_TTL_SECONDS,
      reason: "public problem detail",
    };
  }
  if (/^\/v1\/problems\/[^/]+\/timeline$/.test(path)) {
    return {
      cache: true,
      ttlSeconds: CORPUS_TTL_SECONDS,
      reason: "public problem timeline",
    };
  }

  if (/^\/v1\/solutions\/[^/]+\/lineage$/.test(path)) {
    return {
      cache: true,
      ttlSeconds: CORPUS_TTL_SECONDS,
      reason: "public solution lineage",
    };
  }

  return { cache: false, reason: "not in allowlist" };
}

function normalizePath(pathname: string): string {
  if (pathname.length > 1 && pathname.endsWith("/")) {
    return pathname.slice(0, -1);
  }
  return pathname || "/";
}
