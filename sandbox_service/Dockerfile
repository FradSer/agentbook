# Sandbox microservice — Docker-in-Docker so this service IS a Docker host.
# Deployed as its OWN Railway service, separate from the API (which has no daemon).
# Requires a Railway service configured with a Docker-enabled deploy (the host
# must expose /var/run/docker.sock to the container, e.g. a privileged/volume
# service, or a cloud code-execution wrapper).
FROM docker:27-dind

# python:3.11-slim is pulled lazily by `docker run` inside the service; ensure
# the daemon can reach a registry (or pre-pull in a build step).
RUN apk add --no-cache python3

WORKDIR /app
COPY server.py /app/server.py

ENV PORT=8080
EXPOSE 8080

# Start the Docker daemon, then the HTTP server on top of it.
# SANDBOX_SERVICE_TOKEN must be set (shared with the API's sandbox_service_token).
CMD sh -c "dockerd-entrypoint.sh >/dev/null 2>&1 & sleep 3 && exec python3 /app/server.py"
