.PHONY: test fast smoke e2e simulation agentbook-tests perf perf-real eval eval-real eval-real-if-key full frontend-lint frontend-build

test: fast

fast:
	uv run pytest -m "not smoke and not perf and not eval"

eval:
	uv run pytest backend/tests/eval -m eval -v

eval-real:
	RUN_REAL_EVAL=1 uv run pytest backend/tests/eval -m eval -v

# eval-real-if-key runs the real-mode eval when VOYAGE_API_KEY is set, and
# emits a clean skip message otherwise. Lets `make full` include real-mode
# coverage on machines that have the credential without breaking the build
# on no-key boxes (CI default).
eval-real-if-key:
	@if [ -n "$$VOYAGE_API_KEY" ]; then \
		echo "==> Running eval-real (VOYAGE_API_KEY detected)"; \
		RUN_REAL_EVAL=1 uv run pytest backend/tests/eval -m eval -v; \
	else \
		echo "==> Skipping eval-real (set VOYAGE_API_KEY to enable real-mode regression guard)"; \
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
	RUN_PERF_TESTS=1 RUN_REAL_EMBED_TESTS=1 uv run pytest -m perf -k real_openrouter_embedding

frontend-lint:
	cd frontend && pnpm lint

frontend-build:
	cd frontend && pnpm build

full: fast smoke perf eval eval-real-if-key frontend-lint frontend-build
