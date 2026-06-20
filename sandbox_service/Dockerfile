# Sandbox microservice — pyodide WASM backend (self-hosted, key-free, default).
# Isolation is the WASM linear-memory boundary (no host FS, no raw sockets),
# so this runs unprivileged on standard Railway with ZERO operator setup.
# e2b is an optional faster/cloud backend (set E2B_API_KEY); DinD is dev-only.
FROM python:3.11-slim

# Node for the pyodide WASM runner; npm installs the pyodide runtime (~15MB,
# cold-start loads it once). No Docker daemon needed.
RUN apt-get update && apt-get install -y --no-install-recommends nodejs npm && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY server.py pyodide_runner.mjs package.json ./
RUN npm install --omit=dev --no-audit --no-fund

ENV PORT=8080
EXPOSE 8080

# No third-party key required by default. SANDBOX_SERVICE_TOKEN gates access.
CMD ["python", "/app/server.py"]
