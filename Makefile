.PHONY: test fast smoke e2e simulation agentbook-tests perf perf-real eval eval-real eval-real-if-key full frontend-lint frontend-build

test: fast

fast:
	uv run pytest backend/tests/unit backend/tests/features -m "not smoke and not perf and not eval"

eval:
	uv run pytest backend/tests/eval -m eval -v

eval-real:
	RUN_REAL_EVAL=1 uv run pytest backend/tests/eval -m eval -v

# eval-real-if-gateway runs the real-mode eval when the Gateway is configured,
# and emits a clean skip message otherwise.
eval-real-if-key:
	@if [ -n "$$AI_GATEWAY_BASE_URL" ] && [ -n "$$AI_GATEWAY_AUTH_TOKEN" ]; then \
		echo "==> Running eval-real (AI Gateway detected)"; \
		RUN_REAL_EVAL=1 uv run pytest backend/tests/eval -m eval -v; \
	else \
		echo "==> Skipping eval-real (set AI_GATEWAY_BASE_URL and AI_GATEWAY_AUTH_TOKEN)"; \
	fi

smoke:
	RUN_DOCKER_TESTS=1 uv run pytest -m smoke

e2e:
	RUN_DOCKER_TESTS=1 uv run pytest backend/tests/integration/test_e2e_matrix.py backend/tests/integration/test_e2e_workflow.py -m "e2e or smoke" -q

simulation:
	RUN_DOCKER_TESTS=1 uv run pytest backend/tests/simulation -m simulation -q

agentbook-tests: e2e simulation

perf:
	RUN_PERF_TESTS=1 uv run pytest -m perf

perf-real:
	RUN_PERF_TESTS=1 RUN_REAL_EMBED_TESTS=1 uv run pytest -m perf -k real_gateway_embedding

frontend-lint:
	cd frontend && pnpm lint

frontend-build:
	cd frontend && pnpm build

full: fast smoke perf eval eval-real-if-key frontend-lint frontend-build
