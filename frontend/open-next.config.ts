import { defineCloudflareConfig } from "@opennextjs/cloudflare";

// Incremental cache stays in-memory by default. Uncomment R2 override in
// wrangler.jsonc and switch to r2-incremental-cache when the bucket exists:
//   import r2IncrementalCache from "@opennextjs/cloudflare/overrides/incremental-cache/r2-incremental-cache";
//   export default defineCloudflareConfig({ incrementalCache: r2IncrementalCache });
export default defineCloudflareConfig({});
