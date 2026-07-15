/**
 * Cloudflare Worker: reverse-proxy Agentbook's Railway API through the CF edge.
 *
 * - Public anonymous GETs on an allowlist get short edge TTL (see cache-policy).
 * - Writes, Authorization-bearing requests, MCP, and SSE always hit origin.
 * - Forwards client IP so Railway/slowapi rate limits stay per-client, not per-edge.
 */

import { decideCachePolicy } from "./cache-policy";
import { buildUpstreamUrl } from "./upstream-url";

export interface Env {
  /** Railway (or other) origin base URL, e.g. https://agentbook-api-production.up.railway.app */
  ORIGIN_API_URL: string;
}

const HOP_BY_HOP = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailers",
  "transfer-encoding",
  "upgrade",
  "host",
  "cf-connecting-ip",
  "cf-ray",
  "cf-visitor",
  "cf-ipcountry",
  "x-forwarded-proto",
  "x-forwarded-for",
]);

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const originBase = (env.ORIGIN_API_URL ?? "").replace(/\/$/, "");
    if (!originBase) {
      return new Response("ORIGIN_API_URL is not configured", { status: 500 });
    }

    const incoming = new URL(request.url);
    let upstream: URL;
    try {
      upstream = buildUpstreamUrl(
        originBase,
        incoming.pathname,
        incoming.search,
      );
    } catch {
      return new Response("Invalid upstream path", { status: 400 });
    }

    const headers = filterRequestHeaders(request.headers);
    const clientIp = request.headers.get("CF-Connecting-IP");
    if (clientIp) {
      headers.set("X-Forwarded-For", clientIp);
      headers.set("X-Real-IP", clientIp);
    }
    headers.set("X-Forwarded-Proto", incoming.protocol.replace(":", ""));

    const hasAuthorization = request.headers.has("Authorization");
    const hasCookie = request.headers.has("Cookie");
    const policy = decideCachePolicy(
      request.method,
      incoming.pathname,
      hasAuthorization,
      hasCookie,
    );

    const init: RequestInit & { cf?: Record<string, unknown> } = {
      method: request.method,
      headers,
      redirect: "manual",
    };

    if (request.method !== "GET" && request.method !== "HEAD") {
      init.body = request.body;
      // @ts-expect-error -- Workers duplex streaming for request bodies
      init.duplex = "half";
    }

    if (policy.cache) {
      // Force edge caching of JSON API responses regardless of origin headers.
      init.cf = {
        cacheEverything: true,
        cacheTtl: policy.ttlSeconds,
        cacheTtlByStatus: {
          "200-299": policy.ttlSeconds,
          "404": 10,
          "500-599": 0,
        },
      };
    } else {
      init.cf = {
        cacheTtl: 0,
        cacheEverything: false,
      };
    }

    const upstreamResponse = await fetch(upstream, init);
    const responseHeaders = filterResponseHeaders(upstreamResponse.headers);

    if (policy.cache && upstreamResponse.ok) {
      responseHeaders.set(
        "Cache-Control",
        `public, s-maxage=${policy.ttlSeconds}, max-age=0`,
      );
      responseHeaders.set("X-Agentbook-Edge-Cache", "eligible");
      responseHeaders.set(
        "X-Agentbook-Edge-TTL",
        String(policy.ttlSeconds),
      );
    } else {
      responseHeaders.set("Cache-Control", "no-store");
      responseHeaders.set("X-Agentbook-Edge-Cache", "bypass");
      // Bypass reason is internal — only emit when the operator opts in via
      // a shared debug header (never expose allowlist logic by default).
      if (request.headers.get("X-Agentbook-Edge-Debug") === "1") {
        responseHeaders.set("X-Agentbook-Edge-Bypass-Reason", policy.reason);
      }
    }

    // Preserve SSE / streaming: do not buffer at intermediaries when possible.
    if (
      incoming.pathname.startsWith("/v1/dashboard/research/stream") ||
      incoming.pathname.startsWith("/mcp")
    ) {
      responseHeaders.set("X-Accel-Buffering", "no");
    }

    return new Response(upstreamResponse.body, {
      status: upstreamResponse.status,
      statusText: upstreamResponse.statusText,
      headers: responseHeaders,
    });
  },
};

function filterRequestHeaders(source: Headers): Headers {
  const out = new Headers();
  for (const [key, value] of source.entries()) {
    if (HOP_BY_HOP.has(key.toLowerCase())) continue;
    out.set(key, value);
  }
  return out;
}

function filterResponseHeaders(source: Headers): Headers {
  const out = new Headers();
  for (const [key, value] of source.entries()) {
    const lower = key.toLowerCase();
    if (HOP_BY_HOP.has(lower)) continue;
    // Origin may emit no-store; we rewrite Cache-Control ourselves.
    if (lower === "cache-control") continue;
    out.set(key, value);
  }
  return out;
}
