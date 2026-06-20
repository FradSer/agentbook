// Pyodide runner: loads Pyodide (WASM Python) in a Node subprocess and runs
// submitted code in it. This is the self-hosted, key-free sandbox backend:
// the WASM linear-memory boundary IS the isolation (no host FS, no raw sockets,
// no privileged container, no Docker daemon, no third-party API key).
//
// Protocol (line-delimited JSON on stdin/stdout):
//   stdin:  {"code": "...", "timeout": 15}
//   stdout: {"success": bool, "exit_code": int, "stdout": str, "stderr": str,
//            "duration_seconds": float}

import { createInterface } from "readline";

let pyodide = null;
let pyodideLoading = null;

async function getPyodide() {
  if (pyodide) return pyodide;
  if (pyodideLoading) return pyodideLoading;
  pyodideLoading = (async () => {
    const { loadPyodide } = await import("pyodide");
    // indexURL points at the unpacked pyodide distribution (npm install pyodide
    // ships the runtime files in node_modules/pyodide). Loading is the cold start.
    const { resolve } = await import("path");
    const { pathToFileURL } = await import("url");
    const pkgPath = await import("pyodide/package.json", {
      with: { type: "json" },
    });
    const indexURL = resolve(
      process.cwd(),
      "node_modules/pyodide",
    );
    pyodide = await loadPyodide({ indexURL });
    return pyodide;
  })();
  return pyodideLoading;
}

function runCode(code, timeoutMs) {
  return new Promise(async (resolve) => {
    const start = performance.now();
    let stdout = "";
    let stderr = "";
    let success = true;
    let exitCode = 0;
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      resolve({
        success,
        exit_code: exitCode,
        stdout: stdout.slice(0, 4096),
        stderr: stderr.slice(0, 4096),
        duration_seconds: Math.round((performance.now() - start)) / 1000,
      });
    };
    const timer = setTimeout(() => {
      stderr += `\nTimeout after ${timeoutMs / 1000}s`;
      success = false;
      exitCode = -1;
      finish();
    }, timeoutMs);

    try {
      const py = await getPyodide();
      // Capture stdout/stderr via redirect_stdout/redirect_stderr
      py.setStdout({ batched: (s) => { stdout += s + "\n"; } });
      py.setStderr({ batched: (s) => { stderr += s + "\n"; } });
      await py.runPythonAsync(code);
    } catch (e) {
      success = false;
      exitCode = 1;
      stderr += "\n" + String(e);
    } finally {
      clearTimeout(timer);
      finish();
    }
  });
}

const rl = createInterface({ input: process.stdin });
let pending = 0;
let closed = false;

const maybeExit = () => {
  if (closed && pending === 0) process.exit(0);
};

rl.on("line", async (line) => {
  pending += 1;
  try {
    const req = JSON.parse(line);
    const result = await runCode(
      String(req.code || ""),
      Number(req.timeout || 30) * 1000,
    );
    process.stdout.write(JSON.stringify(result) + "\n");
  } catch (e) {
    process.stdout.write(
      JSON.stringify({
        success: false,
        exit_code: -1,
        stdout: "",
        stderr: String(e),
        duration_seconds: 0,
      }) + "\n",
    );
  } finally {
    pending -= 1;
    maybeExit();
  }
});
rl.on("close", () => {
  closed = true;
  maybeExit();
});
