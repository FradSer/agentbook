import {
  createAgentSession,
  ModelRuntime,
  SessionManager,
} from "@earendil-works/pi-coding-agent";
import { WorkerApi } from "./api.js";
import { config, validateConfig } from "./config.js";
import { createWorkerTools } from "./tools.js";

const INSTRUCTIONS = `You are Agentbook's production worker. Use only registered tools. First process every pending review item, making one approve/reject tool call per item. Then select at most one research candidate, inspect its evidence, and make exactly one propose_improvement or skip_improvement tool call. Never use shell, filesystem, network, or unregistered tools.`;

// The configured model id is registered explicitly because it may be a
// Workers AI or dynamic Gateway model that is not in pi-ai's built-in catalog.
// Its baseUrl points at the Gateway /compat endpoint, and the Gateway owns any
// upstream provider credentials. Agentbook's Pi runs on Railway and calls the
// Gateway directly without an intermediary provider proxy.
function gatewayCompatBaseUrl(): string {
  return `https://gateway.ai.cloudflare.com/v1/${config.cloudflareAccountId}/${config.cloudflareGatewayId}/compat`;
}

function registerDynamicModel(runtime: ModelRuntime): void {
  runtime.registerProvider("cloudflare-ai-gateway", {
    apiKey: config.cloudflareApiKey,
    models: [
      {
        id: config.model,
        name: config.model,
        api: "openai-completions",
        baseUrl: gatewayCompatBaseUrl(),
        reasoning: true,
        input: ["text"],
        cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
        contextWindow: 131072,
        maxTokens: 8192,
        compat: {
          supportsStore: false,
          supportsDeveloperRole: false,
          supportsReasoningEffort: false,
          maxTokensField: "max_tokens",
          supportsStrictMode: false,
          supportsLongCacheRetention: false,
          sendSessionAffinityHeaders: true,
        },
      },
    ],
  });
}

async function runCycle(): Promise<void> {
  const runtime = await ModelRuntime.create();
  registerDynamicModel(runtime);
  const model = runtime.getModel("cloudflare-ai-gateway", config.model);
  if (!model)
    throw new Error(
      `Pi cannot resolve ${config.model} through Cloudflare AI Gateway`,
    );
  const { session } = await createAgentSession({
    model,
    modelRuntime: runtime,
    sessionManager: SessionManager.inMemory(),
    // "builtin" disables the default read/bash/edit/write tools but KEEPS the
    // customTools array enabled. The earlier "all" was a showstopper: pi-ai's
    // runtime turns noTools==="all" into an empty allowedToolNames Set, whose
    // isAllowedTool predicate rejects EVERY name — including the six custom
    // Agentbook tools — so the session exposed zero tools and session.prompt()
    // produced a text-only no-op (process-alive health looked green, no review
    // or improve call ever fired). "builtin" leaves allowedToolNames undefined,
    // so the predicate short-circuits true for customTools while the builtin
    // tools stay inactive. See @earendil-works/pi-coding-agent sdk.d.ts / docs.
    noTools: "builtin",
    customTools: createWorkerTools(new WorkerApi()),
  });
  // The old Python loop capped every cycle at 1500s (agent_max_cycle_seconds)
  // to stop a model that keeps re-issuing tool calls from looping indefinitely
  // under a green process-alive health check. pi 0.83.0's turn loop is an
  // unbounded while(true) (agent-loop.js) with no iteration cap and no total-
  // time deadline; it only exits when the model stops issuing tool calls. A
  // misbehaving model can therefore run one cycle for hours. Race prompt()
  // against a 1500s wall clock so a stuck cycle aborts and the next poll runs.
  const CYCLE_DEADLINE_MS = 1_500_000;
  let deadlineTimer: ReturnType<typeof setTimeout> | undefined;
  try {
    await Promise.race([
      session.prompt(INSTRUCTIONS, { source: "interactive" }),
      new Promise<never>((_, reject) => {
        deadlineTimer = setTimeout(() => {
          void session.abort().catch(() => undefined);
          reject(new Error("Pi cycle exceeded 1500s deadline"));
        }, CYCLE_DEADLINE_MS);
      }),
    ]);
  } finally {
    if (deadlineTimer) clearTimeout(deadlineTimer);
    session.dispose();
  }
}

async function main(): Promise<void> {
  validateConfig();
  for (;;) {
    try {
      await runCycle();
    } catch (error) {
      console.error("Pi worker cycle failed", error);
    }
    await new Promise((resolve) => setTimeout(resolve, config.pollIntervalMs));
  }
}

void main();
