"""
Test Suite Optimization (FR 7.0).

Two complementary strategies:
  1. Risk-based prioritization  – sort / filter by risk priority.
  2. Coverage-efficiency minimization – remove redundant test cases so that
     each (coverage_id, test_method) pair is represented at most once,
     keeping the highest-priority representative.
"""

_PRIORITY_ORDER = {"High": 0, "Medium": 1, "Low": 2}


# ---------------------------------------------------------------------------
# Strategy 1: Risk-based prioritization
# ---------------------------------------------------------------------------

def prioritize_by_risk(
    testcases: list,
    min_priority: str = "Low",
) -> tuple[list, dict]:
    """
    Sorts test cases High → Medium → Low and optionally filters out cases
    below *min_priority*.

    Returns:
        (optimized_list, metrics_dict)
    """
    threshold = _PRIORITY_ORDER.get(min_priority, 2)

    filtered = [
        tc for tc in testcases
        if _PRIORITY_ORDER.get(tc.get("priority", "Low"), 2) <= threshold
    ]
    sorted_tcs = sorted(
        filtered,
        key=lambda tc: _PRIORITY_ORDER.get(tc.get("priority", "Low"), 2),
    )

    metrics = {
        "strategy": "Risk-based Prioritization",
        "original_count": len(testcases),
        "optimized_count": len(sorted_tcs),
        "removed_count": len(testcases) - len(sorted_tcs),
        "min_priority_filter": min_priority,
        "high_count": sum(1 for tc in sorted_tcs if tc.get("priority") == "High"),
        "medium_count": sum(1 for tc in sorted_tcs if tc.get("priority") == "Medium"),
        "low_count": sum(1 for tc in sorted_tcs if tc.get("priority") == "Low"),
    }
    return sorted_tcs, metrics


# ---------------------------------------------------------------------------
# Strategy 2: Coverage-efficiency minimization
# ---------------------------------------------------------------------------

def minimize_by_coverage(testcases: list) -> tuple[list, dict]:
    """
    Deduplicates the test suite so each (coverage_id, test_method) pair
    is represented by at most one test case — the one with the highest
    risk priority.

    Returns:
        (optimized_list, metrics_dict)
    """
    seen: dict[tuple, dict] = {}

    for tc in testcases:
        key = (tc.get("coverage_id", ""), tc.get("test_method", ""))
        existing = seen.get(key)
        if existing is None:
            seen[key] = tc
        else:
            if (
                _PRIORITY_ORDER.get(tc.get("priority", "Low"), 2)
                < _PRIORITY_ORDER.get(existing.get("priority", "Low"), 2)
            ):
                seen[key] = tc

    optimized = list(seen.values())
    optimized.sort(
        key=lambda tc: _PRIORITY_ORDER.get(tc.get("priority", "Low"), 2)
    )

    metrics = {
        "strategy": "Coverage-Efficiency Minimization",
        "original_count": len(testcases),
        "optimized_count": len(optimized),
        "removed_count": len(testcases) - len(optimized),
        "unique_coverage_method_pairs": len(seen),
    }
    return optimized, metrics


# ---------------------------------------------------------------------------
# Combined optimizer
# ---------------------------------------------------------------------------

def optimize_test_suite(
    testcases: list,
    strategy: str = "risk",
    min_priority: str = "Low",
) -> tuple[list, dict]:
    """
    Entry point for FR 7.0.

    strategy:
        "risk"      – Risk-based prioritization only.
        "coverage"  – Coverage-efficiency minimization only.
        "both"      – Minimization first, then risk prioritization.
    min_priority:
        "High" | "Medium" | "Low"  (used only when strategy includes 'risk').
    """
    if strategy == "risk":
        return prioritize_by_risk(testcases, min_priority)

    if strategy == "coverage":
        return minimize_by_coverage(testcases)

    # "both": minimise first, then sort/filter by risk
    minimized, m1 = minimize_by_coverage(testcases)
    final, m2 = prioritize_by_risk(minimized, min_priority)
    combined_metrics = {
        "strategy": "Coverage Minimization + Risk Prioritization",
        "original_count": m1["original_count"],
        "after_minimization": m1["optimized_count"],
        "optimized_count": m2["optimized_count"],
        "removed_count": m1["original_count"] - m2["optimized_count"],
        "min_priority_filter": min_priority,
        "high_count": m2["high_count"],
        "medium_count": m2["medium_count"],
        "low_count": m2["low_count"],
    }
    return final, combined_metrics
