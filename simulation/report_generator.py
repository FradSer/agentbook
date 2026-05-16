"""Analysis report generator for simulation results.

Produces comprehensive JSON and text reports covering:
- Per-agent metrics
- System-level latency and throughput
- Data integrity
- Rate limiting behavior
- Confidence evolution
- Concurrency analysis
- Error report
- Operation breakdown
- Persona comparison
"""

from __future__ import annotations

import re
from collections import Counter

from simulation.orchestrator import AgentSimulationResult


class ReportGenerator:
    """Generates comprehensive analysis reports from simulation results."""

    def generate(
        self,
        results: list[AgentSimulationResult],
        wall_time: float,
        num_agents: int,
    ) -> dict:
        """Generate a full analysis report."""
        return {
            "simulation_summary": self._summary(results, wall_time, num_agents),
            "per_agent_metrics": self._per_agent(results),
            "system_level_metrics": self._system_metrics(results, wall_time),
            "rate_limiting_analysis": self._rate_limiting(results),
            "confidence_evolution": self._confidence_evolution(results),
            "concurrency_analysis": self._concurrency(results, wall_time),
            "error_report": self._error_report(results),
            "operation_breakdown": self._operation_breakdown(results),
            "persona_comparison": self._persona_comparison(results),
        }

    def _summary(
        self, results: list[AgentSimulationResult], wall_time: float, num_agents: int
    ) -> dict:
        total_ops = sum(len(r.operations) for r in results)
        total_errors = sum(len(r.errors) for r in results)
        total_problems = sum(len(r.created_problems) for r in results)
        total_solutions = sum(len(r.created_solutions) for r in results)
        total_outcomes = sum(r.reported_outcomes for r in results)
        total_rate_limits = sum(r.rate_limit_hits for r in results)
        return {
            "num_agents": num_agents,
            "wall_time_seconds": round(wall_time, 2),
            "total_operations": total_ops,
            "total_problems_created": total_problems,
            "total_solutions_created": total_solutions,
            "total_outcomes_reported": total_outcomes,
            "total_errors": total_errors,
            "total_rate_limit_hits": total_rate_limits,
            "error_rate": round(total_errors / max(total_ops, 1), 4),
            "throughput_ops_per_second": round(total_ops / max(wall_time, 0.01), 2),
        }

    def _per_agent(self, results: list[AgentSimulationResult]) -> list[dict]:
        agents = []
        for r in results:
            ops_by_type: Counter = Counter()
            for op in r.operations:
                parts = op.operation.split(" ", 1)
                if len(parts) >= 2:
                    method = parts[0]
                    path = parts[1].split("?")[0]
                    normalized = re.sub(r"/[0-9a-f-]{36}", "/{id}", path)
                    ops_by_type[f"{method} {normalized}"] += 1
                else:
                    ops_by_type[op.operation] += 1
            agents.append(
                {
                    "agent_id": r.agent_id,
                    "persona": r.persona_name,
                    "model_type": r.model_type,
                    "total_operations": len(r.operations),
                    "operations_by_type": dict(ops_by_type),
                    "problems_created": len(r.created_problems),
                    "solutions_created": len(r.created_solutions),
                    "outcomes_reported": r.reported_outcomes,
                    "rate_limit_hits": r.rate_limit_hits,
                    "errors": len(r.errors),
                    "total_time_seconds": round(r.total_time, 2),
                    "latency_stats": {
                        k: round(v, 4) for k, v in r.latency_stats.items()
                    },
                }
            )
        return agents

    def _system_metrics(
        self, results: list[AgentSimulationResult], wall_time: float
    ) -> dict:
        all_latencies = [op.latency_seconds for r in results for op in r.operations]
        if not all_latencies:
            return {
                "total_operations": 0,
                "throughput_ops_per_second": 0,
                "latency_percentiles": {},
                "success_rate": 0,
            }
        sorted_lat = sorted(all_latencies)
        n = len(sorted_lat)
        total_ops = sum(len(r.operations) for r in results)
        successes = sum(1 for r in results for op in r.operations if op.success)
        return {
            "total_operations": total_ops,
            "throughput_ops_per_second": round(total_ops / max(wall_time, 0.01), 2),
            "latency_percentiles": {
                "p50": round(sorted_lat[int(n * 0.5)], 4),
                "p90": round(sorted_lat[min(int(n * 0.90), n - 1)], 4),
                "p95": round(sorted_lat[min(int(n * 0.95), n - 1)], 4),
                "p99": round(sorted_lat[min(int(n * 0.99), n - 1)], 4),
                "min": round(sorted_lat[0], 4),
                "max": round(sorted_lat[-1], 4),
                "avg": round(sum(sorted_lat) / n, 4),
            },
            "success_rate": round(successes / max(n, 1), 4),
        }

    def _rate_limiting(self, results: list[AgentSimulationResult]) -> dict:
        rate_limited_ops = []
        by_endpoint: Counter = Counter()
        for r in results:
            for op in r.operations:
                if op.status_code == 429:
                    rate_limited_ops.append(
                        {
                            "agent_id": r.agent_id,
                            "operation": op.operation,
                            "latency": round(op.latency_seconds, 4),
                        }
                    )
                    by_endpoint[op.operation] += 1
        return {
            "total_rate_limit_hits": sum(r.rate_limit_hits for r in results),
            "affected_agents": len([r for r in results if r.rate_limit_hits > 0]),
            "rate_limited_operations": rate_limited_ops[:20],
            "by_endpoint": dict(by_endpoint),
        }

    def _confidence_evolution(self, results: list[AgentSimulationResult]) -> dict:
        confidence_values = []
        for r in results:
            for op in r.operations:
                if "outcomes" in op.operation and op.success and op.response_data:
                    conf = op.response_data.get("solution_confidence_updated")
                    if conf is not None:
                        confidence_values.append(
                            {
                                "agent_id": r.agent_id,
                                "confidence": conf,
                            }
                        )
        values = [v["confidence"] for v in confidence_values]
        return {
            "total_confidence_updates": len(confidence_values),
            "values": confidence_values[:50],
            "min_confidence": min(values) if values else None,
            "max_confidence": max(values) if values else None,
        }

    def _concurrency(
        self, results: list[AgentSimulationResult], wall_time: float
    ) -> dict:
        times = [r.total_time for r in results]
        sequential_sum = sum(times)
        return {
            "min_agent_time": round(min(times), 2),
            "max_agent_time": round(max(times), 2),
            "avg_agent_time": round(sum(times) / max(len(times), 1), 2),
            "wall_clock": round(wall_time, 2),
            "sequential_sum": round(sequential_sum, 2),
            "speedup_vs_sequential": round(sequential_sum / max(wall_time, 0.01), 1),
            "concurrency_efficiency": round(wall_time / max(max(times), 0.01), 2),
        }

    def _error_report(self, results: list[AgentSimulationResult]) -> dict:
        all_errors = []
        for r in results:
            for err in r.errors:
                all_errors.append(
                    {"agent_id": r.agent_id, "persona": r.persona_name, **err}
                )
        by_msg: Counter = Counter(e.get("error", "")[:100] for e in all_errors)
        by_agent: Counter = Counter(e["agent_id"] for e in all_errors)
        return {
            "total_errors": len(all_errors),
            "errors_by_message": dict(by_msg.most_common(10)),
            "errors_by_agent": dict(by_agent),
            "sample_errors": all_errors[:10],
        }

    def _operation_breakdown(self, results: list[AgentSimulationResult]) -> dict:
        op_counter: Counter = Counter()
        for r in results:
            for op in r.operations:
                parts = op.operation.split(" ", 1)
                if len(parts) >= 2:
                    method = parts[0]
                    path = parts[1].split("?")[0]
                    normalized = re.sub(r"/[0-9a-f-]{36}", "/{id}", path)
                    op_counter[f"{method} {normalized}"] += 1
                else:
                    op_counter[op.operation] += 1
        return dict(op_counter.most_common())

    def _persona_comparison(self, results: list[AgentSimulationResult]) -> dict:
        by_persona: dict[str, dict] = {}
        for r in results:
            if r.persona_name not in by_persona:
                by_persona[r.persona_name] = {
                    "agents": 0,
                    "total_ops": 0,
                    "total_errors": 0,
                    "total_problems": 0,
                    "total_solutions": 0,
                    "total_outcomes": 0,
                    "total_rate_limits": 0,
                    "latencies": [],
                }
            stats = by_persona[r.persona_name]
            stats["agents"] += 1
            stats["total_ops"] += len(r.operations)
            stats["total_errors"] += len(r.errors)
            stats["total_problems"] += len(r.created_problems)
            stats["total_solutions"] += len(r.created_solutions)
            stats["total_outcomes"] += r.reported_outcomes
            stats["total_rate_limits"] += r.rate_limit_hits
            for op in r.operations:
                stats["latencies"].append(op.latency_seconds)

        for stats in by_persona.values():
            lats = stats.pop("latencies")
            if lats:
                stats["avg_latency"] = round(sum(lats) / len(lats), 4)
            stats["ops_per_agent"] = round(
                stats["total_ops"] / max(stats["agents"], 1), 1
            )

        return by_persona

    # ── Output formats ───────────────────────────────────────────────

    def to_text(self, report: dict) -> str:
        lines: list[str] = []
        s = report["simulation_summary"]
        lines.append("=" * 70)
        lines.append("  AgentBook REST Simulation Report")
        lines.append("=" * 70)
        lines.append("")
        lines.append(
            f"  Agents: {s['num_agents']}  |  "
            f"Wall time: {s['wall_time_seconds']}s  |  "
            f"Throughput: {s['throughput_ops_per_second']} ops/s"
        )
        lines.append(
            f"  Total operations: {s['total_operations']}  |  "
            f"Error rate: {s['error_rate']:.2%}"
        )
        lines.append(
            f"  Problems: {s['total_problems_created']}  |  "
            f"Solutions: {s['total_solutions_created']}  |  "
            f"Outcomes: {s['total_outcomes_reported']}"
        )
        lines.append(
            f"  Errors: {s['total_errors']}  |  "
            f"Rate limit hits: {s['total_rate_limit_hits']}"
        )
        lines.append("")

        # System metrics
        sm = report["system_level_metrics"]
        lp = sm.get("latency_percentiles", {})
        lines.append("-" * 70)
        lines.append("  System-Level Metrics")
        lines.append("-" * 70)
        lines.append(f"  Success rate: {sm['success_rate']:.2%}")
        if lp:
            lines.append(
                f"  Latency:  p50={lp['p50'] * 1000:.1f}ms  "
                f"p95={lp['p95'] * 1000:.1f}ms  "
                f"p99={lp['p99'] * 1000:.1f}ms  "
                f"max={lp['max'] * 1000:.1f}ms"
            )
        lines.append("")

        # Per-agent table
        lines.append("-" * 70)
        lines.append("  Per-Agent Metrics")
        lines.append("-" * 70)
        header = (
            f"{'Agent':<12} {'Persona':<12} {'Model':<30} "
            f"{'Ops':>4} {'Probs':>5} {'Sols':>4} "
            f"{'Out':>3} {'429':>3} {'Err':>3} {'Time':>7}"
        )
        lines.append(header)
        for a in report["per_agent_metrics"]:
            lines.append(
                f"{a['agent_id']:<12} {a['persona']:<12} "
                f"{a['model_type']:<30} {a['total_operations']:>4} "
                f"{a['problems_created']:>5} {a['solutions_created']:>4} "
                f"{a['outcomes_reported']:>3} {a['rate_limit_hits']:>3} "
                f"{a['errors']:>3} {a['total_time_seconds']:>6.2f}s"
            )
        lines.append("")

        # Concurrency
        ca = report["concurrency_analysis"]
        lines.append("-" * 70)
        lines.append("  Concurrency Analysis")
        lines.append("-" * 70)
        lines.append(
            f"  Agent time:  min={ca['min_agent_time']:.2f}s  "
            f"max={ca['max_agent_time']:.2f}s  "
            f"avg={ca['avg_agent_time']:.2f}s"
        )
        lines.append(f"  Wall clock:  {ca['wall_clock']:.2f}s")
        lines.append(f"  Speedup vs sequential:  {ca['speedup_vs_sequential']:.1f}x")
        lines.append(f"  Concurrency efficiency:  {ca['concurrency_efficiency']:.2f}")
        lines.append("")

        # Rate limiting
        rl = report["rate_limiting_analysis"]
        lines.append("-" * 70)
        lines.append("  Rate Limiting Analysis")
        lines.append("-" * 70)
        lines.append(
            f"  Total hits: {rl['total_rate_limit_hits']}  |  "
            f"Affected agents: {rl['affected_agents']}"
        )
        if rl["by_endpoint"]:
            lines.append("  By endpoint:")
            for ep, count in rl["by_endpoint"].items():
                lines.append(f"    {ep}: {count}")
        lines.append("")

        # Confidence evolution
        ce = report["confidence_evolution"]
        lines.append("-" * 70)
        lines.append("  Confidence Evolution")
        lines.append("-" * 70)
        lines.append(
            f"  Updates: {ce['total_confidence_updates']}  |  "
            f"Range: {ce['min_confidence']:.3f} - {ce['max_confidence']:.3f}"
            if ce["min_confidence"] is not None
            else "  No confidence updates recorded"
        )
        lines.append("")

        # Operation breakdown
        lines.append("-" * 70)
        lines.append("  Operation Breakdown")
        lines.append("-" * 70)
        for op, count in report["operation_breakdown"].items():
            lines.append(f"    {op:<45} {count:>4}")
        lines.append("")

        # Persona comparison
        lines.append("-" * 70)
        lines.append("  Persona Comparison")
        lines.append("-" * 70)
        for persona, stats in report["persona_comparison"].items():
            lines.append(
                f"  {persona:<12}: "
                f"{stats['agents']} agents, "
                f"{stats['total_ops']} ops, "
                f"{stats['total_problems']} problems, "
                f"{stats['total_solutions']} solutions, "
                f"{stats['total_outcomes']} outcomes, "
                f"avg_latency={stats.get('avg_latency', 0) * 1000:.1f}ms"
            )
        lines.append("")

        # Errors
        er = report["error_report"]
        lines.append("-" * 70)
        lines.append(f"  Error Report ({er['total_errors']} errors)")
        lines.append("-" * 70)
        if er["total_errors"] > 0:
            for msg, count in list(er["errors_by_message"].items())[:5]:
                lines.append(f"  [{count}x] {msg[:80]}")
        else:
            lines.append("  No errors detected.")
        lines.append("")
        lines.append("=" * 70)

        return "\n".join(lines)
