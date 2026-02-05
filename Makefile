.PHONY: test fast smoke perf perf-real full web-lint web-build

test: fast

fast:
	uv run pytest -m "not smoke and not perf"

smoke:
	RUN_DOCKER_TESTS=1 uv run pytest -m smoke

perf:
	RUN_PERF_TESTS=1 uv run pytest -m perf

perf-real:
	RUN_PERF_TESTS=1 RUN_REAL_EMBED_TESTS=1 uv run pytest -m perf -k real_openrouter_embedding

web-lint:
	cd web && pnpm lint

web-build:
	cd web && pnpm build

full: fast smoke perf web-lint web-build
