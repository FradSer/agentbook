import { describe, expect, it } from "vitest";
import {
  CORPUS_TTL_SECONDS,
  MANIFEST_TTL_SECONDS,
  decideCachePolicy,
} from "../src/cache-policy";

describe("decideCachePolicy", () => {
  it("refuses non-GET/HEAD methods", () => {
    for (const method of ["POST", "PUT", "PATCH", "DELETE", "OPTIONS"]) {
      const decision = decideCachePolicy(method, "/v1/search", false);
      expect(decision).toEqual({
        cache: false,
        reason: "non-idempotent method",
      });
    }
  });

  it("refuses any request with Authorization", () => {
    const decision = decideCachePolicy("GET", "/v1/search", true);
    expect(decision).toEqual({
      cache: false,
      reason: "authorization present",
    });
  });

  it("never caches MCP transport", () => {
    expect(decideCachePolicy("GET", "/mcp", false).cache).toBe(false);
    expect(decideCachePolicy("GET", "/mcp/session", false).cache).toBe(false);
  });

  it("never caches auth, books, or live research SSE", () => {
    expect(decideCachePolicy("GET", "/v1/auth/verify", false).cache).toBe(
      false,
    );
    expect(decideCachePolicy("POST", "/v1/books", false).cache).toBe(false);
    expect(
      decideCachePolicy("GET", "/v1/dashboard/research/stream", false).cache,
    ).toBe(false);
    expect(
      decideCachePolicy("GET", "/v1/dashboard/research/live", false).cache,
    ).toBe(false);
  });

  it("caches public corpus GETs with short TTL", () => {
    const cases = [
      ["/v1/search", "public search"],
      ["/v1/problems", "public problem list"],
      ["/v1/problems/abc-123", "public problem detail"],
      ["/v1/problems/abc-123/timeline", "public problem timeline"],
      ["/v1/solutions/sol-9/lineage", "public solution lineage"],
    ] as const;

    for (const [path, reason] of cases) {
      expect(decideCachePolicy("GET", path, false)).toEqual({
        cache: true,
        ttlSeconds: CORPUS_TTL_SECONDS,
        reason,
      });
    }
  });

  it("caches tools manifest longer", () => {
    expect(decideCachePolicy("GET", "/v1/tools/manifest", false)).toEqual({
      cache: true,
      ttlSeconds: MANIFEST_TTL_SECONDS,
      reason: "public tools manifest",
    });
  });

  it("allows HEAD on the same allowlist as GET", () => {
    expect(decideCachePolicy("HEAD", "/v1/problems", false).cache).toBe(true);
  });

  it("strips trailing slashes before matching", () => {
    expect(decideCachePolicy("GET", "/v1/search/", false)).toEqual({
      cache: true,
      ttlSeconds: CORPUS_TTL_SECONDS,
      reason: "public search",
    });
  });

  it("does not cache write-adjacent or dashboard paths by default", () => {
    expect(decideCachePolicy("GET", "/v1/dashboard/radar", false).cache).toBe(
      false,
    );
    expect(decideCachePolicy("GET", "/docs", false).cache).toBe(false);
    expect(decideCachePolicy("GET", "/v1/health-metrics", false).cache).toBe(
      false,
    );
  });
});
