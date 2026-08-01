import path from "node:path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    environmentOptions: {
      jsdom: {
        url: "http://localhost/",
      },
    },
    setupFiles: ["./vitest.setup.ts"],
    globals: true,
    // Run test files sequentially in a single worker. With the `agent`
    // workspace package present, vitest's default thread pool reuses workers
    // across files and jest-dom's `expect.extend` (run in vitest.setup.ts) does
    // not reliably propagate to every reused worker, so matchers like
    // toBeInTheDocument throw `Invalid Chai property` mid-suite. Sequential
    // execution keeps expect.extend on one expect instance for the whole run.
    // Tests still pass in parallel on a checkout without the agent package;
    // this flag is what makes them stable in the monorepo.
    fileParallelism: false,
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
    },
  },
});
