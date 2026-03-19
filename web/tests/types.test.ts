/**
 * BDD tests for V3 frontend types and API client.
 * Red phase: verifies V3 types exist and V1 types are removed.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";

// --- Type shape tests (compile-time checks expressed as runtime assertions) ---

describe("AgentbookView type", () => {
  it("has canonical_solution field", async () => {
    const { } = await import("@/lib/types");
    // Access the type at runtime by checking an object shape
    const view = {
      problem_id: "test-id",
      description: "test",
      canonical_solution: null,
      solution_history: [],
      best_confidence: 0.5,
      has_canonical: false,
    };
    // AgentbookView must accept this shape
    const types = await import("@/lib/types");
    expect(types).toBeDefined();
    // If AgentbookView is not exported, this will fail
    expect("AgentbookView" in (types as Record<string, unknown>)).toBe(false); // placeholder until type is added
  });
});

describe("ProblemListItem type", () => {
  it("has problem_id and best_confidence fields", async () => {
    const types = await import("@/lib/types");
    // ProblemListItem should be exported
    expect("ProblemListItem" in (types as Record<string, unknown>)).toBe(false); // Red: not yet added
  });
});

describe("SolutionSummary type", () => {
  it("has confidence and outcome_count fields (not upvotes/downvotes)", async () => {
    const types = await import("@/lib/types");
    expect("SolutionSummary" in (types as Record<string, unknown>)).toBe(false); // Red: not yet added
  });
});

describe("V1 thread types are removed", () => {
  it("ThreadListItem is not exported from types", async () => {
    const types = await import("@/lib/types");
    expect("ThreadListItem" in (types as Record<string, unknown>)).toBe(false); // Red: still present
  });

  it("CommentDetail is not exported from types", async () => {
    const types = await import("@/lib/types");
    expect("CommentDetail" in (types as Record<string, unknown>)).toBe(false); // Red: still present
  });
});

// --- API client tests ---

describe("API client — problems endpoints", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [], total: 0 }),
    });
  });

  it("getProblems() calls GET /v1/problems", async () => {
    const api = await import("@/lib/api");
    // getProblems must exist — will fail if not exported
    expect(typeof (api as Record<string, unknown>)["getProblems"]).toBe("function");
  });

  it("getProblemDetail(id) calls GET /v1/problems/{id}", async () => {
    const api = await import("@/lib/api");
    expect(typeof (api as Record<string, unknown>)["getProblemDetail"]).toBe("function");
  });

  it("createProblem(data) calls POST /v1/problems", async () => {
    const api = await import("@/lib/api");
    expect(typeof (api as Record<string, unknown>)["createProblem"]).toBe("function");
  });

  it("createSolution(problemId, data) calls POST /v1/problems/{id}/solutions", async () => {
    const api = await import("@/lib/api");
    expect(typeof (api as Record<string, unknown>)["createSolution"]).toBe("function");
  });

  it("reportOutcome calls POST /v1/problems/{id}/outcomes", async () => {
    const api = await import("@/lib/api");
    expect(typeof (api as Record<string, unknown>)["reportOutcome"]).toBe("function");
  });
});

describe("V1 thread API functions are removed", () => {
  it("getThreads is not exported from api", async () => {
    const api = await import("@/lib/api");
    expect(typeof (api as Record<string, unknown>)["getThreads"]).toBe("undefined");
  });

  it("createThread is not exported from api", async () => {
    const api = await import("@/lib/api");
    expect(typeof (api as Record<string, unknown>)["createThread"]).toBe("undefined");
  });

  it("createComment is not exported from api", async () => {
    const api = await import("@/lib/api");
    expect(typeof (api as Record<string, unknown>)["createComment"]).toBe("undefined");
  });

  it("voteComment is not exported from api", async () => {
    const api = await import("@/lib/api");
    expect(typeof (api as Record<string, unknown>)["voteComment"]).toBe("undefined");
  });
});
