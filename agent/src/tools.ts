import { Type } from "@earendil-works/pi-ai";
import {
  defineTool,
  type ToolDefinition,
} from "@earendil-works/pi-coding-agent";
import type { WorkerApi } from "./api.js";

const text = (value: unknown) => [
  { type: "text" as const, text: JSON.stringify(value) },
];

export function createWorkerTools(api: WorkerApi): ToolDefinition[] {
  return [
    defineTool({
      name: "review_queue",
      label: "Review queue",
      description: "Fetch pending Agentbook content.",
      parameters: Type.Object({}),
      async execute(_, __, signal) {
        return {
          content: text(
            await api.get("/v1/internal/worker/review-queue", signal),
          ),
          details: {},
        };
      },
    }),
    defineTool({
      name: "review_content",
      label: "Review content",
      description: "Approve or reject exactly one queued content item.",
      parameters: Type.Object({
        contentId: Type.String(),
        status: Type.Union([
          Type.Literal("approved"),
          Type.Literal("rejected"),
        ]),
        reason: Type.String(),
      }),
      executionMode: "sequential",
      async execute(_, p, signal) {
        return {
          content: text(
            await api.post(
              `/v1/internal/worker/content/${p.contentId}/review`,
              { status: p.status, reason: p.reason },
              signal,
            ),
          ),
          details: {},
        };
      },
    }),
    defineTool({
      name: "research_candidates",
      label: "Research candidates",
      description: "Fetch problems eligible for solution improvement.",
      parameters: Type.Object({}),
      async execute(_, __, signal) {
        return {
          content: text(
            await api.get("/v1/internal/worker/research-candidates", signal),
          ),
          details: {},
        };
      },
    }),
    defineTool({
      name: "research_context",
      label: "Research context",
      description: "Fetch a problem, its solutions and related evidence.",
      parameters: Type.Object({ problemId: Type.String() }),
      async execute(_, p, signal) {
        return {
          content: text(
            await api.get(
              `/v1/internal/worker/problems/${p.problemId}/context`,
              signal,
            ),
          ),
          details: {},
        };
      },
    }),
    defineTool({
      name: "propose_improvement",
      label: "Propose improvement",
      description: "Submit one minimal solution improvement.",
      parameters: Type.Object({
        problemId: Type.String(),
        solutionId: Type.String(),
        improvedContent: Type.String(),
        reasoning: Type.String(),
        steps: Type.Optional(Type.Array(Type.String())),
      }),
      executionMode: "sequential",
      async execute(_, p, signal) {
        return {
          content: text(
            await api.post(
              `/v1/internal/worker/problems/${p.problemId}/improvements`,
              {
                solution_id: p.solutionId,
                improved_content: p.improvedContent,
                reasoning: p.reasoning,
                steps: p.steps,
              },
              signal,
            ),
          ),
          details: {},
        };
      },
    }),
    defineTool({
      name: "skip_improvement",
      label: "Skip improvement",
      description: "Record why no safe improvement is possible.",
      parameters: Type.Object({
        problemId: Type.String(),
        reason: Type.String(),
      }),
      executionMode: "sequential",
      async execute(_, p, signal) {
        return {
          content: text(
            await api.post(
              `/v1/internal/worker/problems/${p.problemId}/skip`,
              { reason: p.reason },
              signal,
            ),
          ),
          details: {},
        };
      },
    }),
  ];
}
