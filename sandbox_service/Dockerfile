# Sandbox microservice — e2b cloud backend (deployable on non-privileged Railway).
# Isolation lives in e2b's cloud sandbox, NOT in this process, so this service
# runs unprivileged and safe. Set E2B_API_KEY + SANDBOX_SERVICE_TOKEN.
# (A DinD fallback exists for local dev only — it needs a privileged host.)
FROM python:3.11-slim

WORKDIR /app
RUN pip install --no-cache-dir e2b-code-interpreter

COPY server.py /app/server.py

ENV PORT=8080
EXPOSE 8080

# E2B_API_KEY and SANDBOX_SERVICE_TOKEN must be set at deploy time.
CMD ["python", "/app/server.py"]
