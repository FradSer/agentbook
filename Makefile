.PHONY: test fast smoke perf perf-real full frontend-lint frontend-build

test: fast

fast:
	uv run pytest -m "not smoke and not perf"

smoke:
	RUN_DOCKER_TESTS=1 uv run pytest -m smoke

perf:
	RUN_PERF_TESTS=1 uv run pytest -m perf

perf-real:
	RUN_PERF_TESTS=1 RUN_REAL_EMBED_TESTS=1 uv run pytest -m perf -k real_openrouter_embedding

frontend-lint:
	cd frontend && pnpm lint

frontend-build:
	cd frontend && pnpm build

full: fast smoke perf frontend-lint frontend-build
