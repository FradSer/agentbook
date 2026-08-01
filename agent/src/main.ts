import { createAgentSession, ModelRuntime, SessionManager } from "@earendil-works/pi-coding-agent";
import { WorkerApi } from "./api.js";
import { config, validateConfig } from "./config.js";
import { createWorkerTools } from "./tools.js";

const INSTRUCTIONS = `You are Agentbook's production worker. Use only registered tools. First process every pending review item, making one approve/reject tool call per item. Then select at most one research candidate, inspect its evidence, and make exactly one propose_improvement or skip_improvement tool call. Never use shell, filesystem, network, or unregistered tools.`;

// The `dynamic/` model id is not in pi-ai's built-in cloudflare-ai-gateway
// catalog (which only lists workers-ai/@cf/... and known passthrough models),
// so ModelRuntime.getModel cannot resolve it without registration. We inject it
// as a custom model whose baseUrl points at the gateway /compat endpoint; pi
// then sends {"model":"dynamic/deepseek-v4-flash",...} to /compat/chat/completions
// and the gateway's dynamic route forwards it to DeepSeek with its own stored
// upstream key. Mirrors the codeterrier Worker /ai/v1 proxy path, but without
// an intermediary Worker since agentbook's Pi runs on Railway and calls the
// gateway directly.
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
        cost: { input: 0.14, output: 0.28, cacheRead: 0.0028, cacheWrite: 0 },
        contextWindow: 1000000,
        maxTokens: 384000,
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
  if (!model) throw new Error(`Pi cannot resolve ${config.model} through Cloudflare AI Gateway`);
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
  try {
    await session.prompt(INSTRUCTIONS, { source: "interactive" });
  } finally {
    session.dispose();
  }
}

async function main(): Promise<void> {
  validateConfig();
  for (;;) {
    try { await runCycle(); } catch (error) { console.error("Pi worker cycle failed", error); }
    await new Promise((resolve) => setTimeout(resolve, config.pollIntervalMs));
  }
}

void main();
