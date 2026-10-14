"""Query latency benchmarking engine comparing pre- and post-optimization execution times.
Strict zero em dash policy enforced.
"""
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict


@dataclass
class BenchmarkComparisonResult:
    query_name: str
    pre_optimization_ms: float
    post_optimization_ms: float
    speedup_multiplier: float
    latency_reduction_pct: float
    pre_rows_examined: int
    post_rows_examined: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class QueryBenchmarker:
    """Measures and compares database query latencies before and after optimization."""

    def __init__(self):
        self.comparisons: List[BenchmarkComparisonResult] = []

    def compare_latencies(
        self,
        query_name: str,
        pre_ms: float,
        post_ms: float,
        pre_rows: int = 100000,
        post_rows: int = 10
    ) -> BenchmarkComparisonResult:
        """Calculate speedup and latency reduction metrics."""
        pre_safe = max(pre_ms, 0.001)
        post_safe = max(post_ms, 0.001)
        multiplier = round(pre_safe / post_safe, 2)
        reduction_pct = round(((pre_safe - post_safe) / pre_safe) * 100.0, 2)

        result = BenchmarkComparisonResult(
            query_name=query_name,
            pre_optimization_ms=round(pre_ms, 3),
            post_optimization_ms=round(post_ms, 3),
            speedup_multiplier=multiplier,
            latency_reduction_pct=reduction_pct,
            pre_rows_examined=pre_rows,
            post_rows_examined=post_rows
        )
        self.comparisons.append(result)
        return result

    def benchmark_execution_function(
        self,
        query_name: str,
        func_baseline,
        func_optimized,
        iterations: int = 100
    ) -> BenchmarkComparisonResult:
        """Measure actual execution functions over N iterations."""
        # Baseline timing
        t0 = time.perf_counter()
        for _ in range(iterations):
            func_baseline()
        t1 = time.perf_counter()
        pre_ms = ((t1 - t0) / iterations) * 1000.0

        # Optimized timing
        t2 = time.perf_counter()
        for _ in range(iterations):
            func_optimized()
        t3 = time.perf_counter()
        post_ms = ((t3 - t2) / iterations) * 1000.0

        return self.compare_latencies(
            query_name=query_name,
            pre_ms=pre_ms,
            post_ms=post_ms
        )

    def calculate_aggregate_metrics(self) -> Dict[str, Any]:
        """Aggregate all recorded benchmark comparisons."""
        if not self.comparisons:
            return {
                "total_queries_benchmarked": 0,
                "average_speedup_multiplier": 1.0,
                "average_latency_reduction_pct": 0.0
            }

        avg_speedup = sum(c.speedup_multiplier for c in self.comparisons) / len(self.comparisons)
        avg_reduction = sum(c.latency_reduction_pct for c in self.comparisons) / len(self.comparisons)

        return {
            "total_queries_benchmarked": len(self.comparisons),
            "average_speedup_multiplier": round(avg_speedup, 2),
            "average_latency_reduction_pct": round(avg_reduction, 2),
            "details": [c.to_dict() for c in self.comparisons]
        }
