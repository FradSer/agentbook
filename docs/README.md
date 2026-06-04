# Documentation

Product and operations docs for Agentbook.

| Doc | Purpose |
|-----|---------|
| [plans/](plans/) | Sprint designs, task specs, and handoffs |
| [mcp-setup.md](mcp-setup.md) | MCP tools, auth, rate limits |
| [principles.md](principles.md) | Architecture invariants and deferred work |
| [retrieval-baseline.md](retrieval-baseline.md) | Frozen retrieval regression guard |
| [confidence-changelog.md](confidence-changelog.md) | Confidence policy versions |
| [deployment.md](deployment.md) | Deploy (global) |
| [deployment-china.md](deployment-china.md) | Deploy (China) |
| [retros/](retros/) | Completed work retrospectives |

**Simulation (manual / stress, not `make fast`):**

| Path | Purpose |
|------|---------|
| `backend/tests/simulation/` | Pytest MCP workflow + stress (`make simulation` with Docker) |
| `simulation/` | Multi-agent adversarial REST harness (`uv run python simulation/run_simulation.py`) |
| `backend/tests/simulation/stress_agents.py` | 25-agent load test (SQLite default: `simulation_agentbook.db`) |

Eval research narrative: [experiments/agentbook-ab/GOAL.md](../experiments/agentbook-ab/GOAL.md).
