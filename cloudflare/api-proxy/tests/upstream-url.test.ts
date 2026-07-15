import { describe, expect, it } from "vitest";
import { buildUpstreamUrl } from "../src/upstream-url";

const ORIGIN = "https://agentbook-api-production.up.railway.app";

describe("buildUpstreamUrl", () => {
  it("keeps normal paths on the configured origin", () => {
    const url = buildUpstreamUrl(ORIGIN, "/v1/search", "?q=pgvector");
    expect(url.href).toBe(
      "https://agentbook-api-production.up.railway.app/v1/search?q=pgvector",
    );
  });

  it("blocks protocol-relative SSRF via //host pathnames", () => {
    const url = buildUpstreamUrl(ORIGIN, "//attacker.example/steal", "");
    expect(url.origin).toBe("https://agentbook-api-production.up.railway.app");
    expect(url.host).toBe("agentbook-api-production.up.railway.app");
    // Becomes a same-origin path segment, never a different host.
    expect(url.pathname).toBe("/attacker.example/steal");
  });

  it("blocks triple-slash and mixed leading-slash forms", () => {
    for (const path of ["///evil.com/x", "////evil.com", "/\\evil.com"]) {
      const url = buildUpstreamUrl(ORIGIN, path.replace("\\", "/"), "");
      expect(url.origin).toBe(
        "https://agentbook-api-production.up.railway.app",
      );
    }
  });

  it("preserves query strings without touching origin", () => {
    const url = buildUpstreamUrl(ORIGIN, "/v1/problems", "?limit=18&order=desc");
    expect(url.searchParams.get("limit")).toBe("18");
    expect(url.searchParams.get("order")).toBe("desc");
    expect(url.origin).toBe("https://agentbook-api-production.up.railway.app");
  });

  it("joins when originBase already has a path prefix", () => {
    const url = buildUpstreamUrl(`${ORIGIN}/proxy`, "/v1/tools/manifest", "");
    expect(url.href).toBe(
      "https://agentbook-api-production.up.railway.app/proxy/v1/tools/manifest",
    );
  });
});
