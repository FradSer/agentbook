#!/usr/bin/env python
"""Entry point for the REST-based coding agent simulation.

Usage:
    uv run python simulation/run_simulation.py [--agents 10] [--port 8765]

This script:
1. Starts the agentbook backend in DEMO_MODE=1 (in-memory, no DB)
2. Waits for the server to become healthy
3. Launches N simulated coding agents via REST API
4. Runs post-simulation data integrity checks
5. Generates and saves a comprehensive analysis report
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time

import httpx

# Set DEMO_MODE before any backend imports
os.environ.setdefault("DEMO_MODE", "1")

import uvicorn  # noqa: E402

from backend.main import create_app  # noqa: E402
from simulation.orchestrator import SimulationOrchestrator  # noqa: E402
from simulation.personas import assign_personas  # noqa: E402
from simulation.report_generator import ReportGenerator  # noqa: E402

DEFAULT_PORT = 8765
DEFAULT_AGENTS = 10


async def wait_for_server(base_url: str, timeout: int = 30) -> bool:
    """Wait for the backend to become healthy."""
    async with httpx.AsyncClient() as client:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                resp = await client.get(f"{base_url}/v1/problems", params={"limit": 1})
                if resp.status_code == 200:
                    return True
            except Exception:
                pass
            await asyncio.sleep(0.5)
    return False


async def run_integrity_checks(base_url: str, results: list) -> dict:
    """Post-simulation: verify all created resources are retrievable."""
    all_problem_ids = [pid for r in results for pid in r.created_problems]
    all_solution_ids = [sid for r in results for sid in r.created_solutions]

    missing_problems = 0
    missing_solutions = 0

    async with httpx.AsyncClient(
        base_url=base_url, timeout=httpx.Timeout(10.0)
    ) as client:
        # Check problems
        for pid in all_problem_ids:
            try:
                resp = await client.get(f"/v1/problems/{pid}")
                if resp.status_code != 200:
                    missing_problems += 1
            except Exception:
                missing_problems += 1

        # Check solutions
        for sid in all_solution_ids:
            try:
                resp = await client.get(f"/v1/solutions/{sid}/lineage")
                if resp.status_code != 200:
                    missing_solutions += 1
            except Exception:
                missing_solutions += 1

    total = len(all_problem_ids) + len(all_solution_ids)
    retrievable = (
        len(all_problem_ids)
        - missing_problems
        + len(all_solution_ids)
        - missing_solutions
    )
    return {
        "problems_created": len(all_problem_ids),
        "problems_retrievable": len(all_problem_ids) - missing_problems,
        "problems_missing": missing_problems,
        "solutions_created": len(all_solution_ids),
        "solutions_retrievable": len(all_solution_ids) - missing_solutions,
        "solutions_missing": missing_solutions,
        "integrity_score": round(retrievable / max(total, 1), 4),
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="AgentBook REST Simulation")
    parser.add_argument(
        "--agents",
        type=int,
        default=DEFAULT_AGENTS,
        help="Number of agents to simulate",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help="Backend port",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="simulation_report.json",
        help="Report output file",
    )
    args = parser.parse_args()

    base_url = f"http://127.0.0.1:{args.port}"

    # Step 1: Start backend server in-process
    print(f"Starting agentbook backend on port {args.port} in DEMO_MODE...")
    app = create_app()
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=args.port,
        log_level="warning",
        loop="asyncio",
    )
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())

    # Step 2: Wait for server health
    print("Waiting for server to become healthy...")
    healthy = await wait_for_server(base_url)
    if not healthy:
        print("ERROR: Server failed to start within timeout")
        server.should_exit = True
        await server_task
        sys.exit(1)
    print(f"Server healthy at {base_url}")
    print()

    # Step 3: Assign personas and launch simulation
    personas = assign_personas(args.agents)
    from collections import Counter

    persona_counts = Counter(p.name for p in personas)
    print(f"Launching {args.agents} agents with persona distribution:")
    for name, count in persona_counts.most_common():
        print(f"  {name}: {count}")
    print()

    orchestrator = SimulationOrchestrator(base_url, args.agents, personas)
    wall_start = time.monotonic()
    results = await orchestrator.run_simulation()
    wall_time = time.monotonic() - wall_start

    # Step 4: Post-simulation integrity checks
    print("Running post-simulation data integrity checks...")
    integrity = await run_integrity_checks(base_url, results)
    print(f"  Integrity score: {integrity['integrity_score']:.2%}")
    print()

    # Step 5: Generate report
    report_gen = ReportGenerator()
    report = report_gen.generate(results, wall_time, args.agents)
    report["data_integrity"] = integrity

    # Save JSON report
    with open(args.output, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"Full report saved to: {args.output}")

    # Print text summary
    text_report = report_gen.to_text(report)
    print()
    print(text_report)

    # Step 6: Shutdown
    server.should_exit = True
    await server_task

    # Exit code based on errors
    total_errors = sum(len(r.errors) for r in results)
    sys.exit(1 if total_errors > 0 else 0)


if __name__ == "__main__":
    asyncio.run(main())
