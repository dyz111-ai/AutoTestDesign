def analyze_coverage(
    requirements: list,
    coverage_items: list,
    testcases: list,
) -> dict:
    """
    Analyzes whether each coverage item has a test case and whether
    each requirement is fully covered by its coverage items.
    """

    req_ids = {req["requirement_id"] for req in requirements}
    tc_by_coverage = {tc["coverage_id"]: tc for tc in testcases}
    tc_by_req = {}
    for tc in testcases:
        tc_by_req.setdefault(tc["req_id"], []).append(tc)

    methods_used = {tc["test_method"] for tc in testcases}

    ci_details = []
    covered_ci = 0

    for ci in coverage_items:
        cid = ci["coverage_id"]
        has_tc = cid in tc_by_coverage
        if has_tc:
            covered_ci += 1
        ci_details.append({
            "coverage_id": cid,
            "coverage_item": ci["coverage_item"],
            "related_req": ci["related_req"],
            "status": "COVERED" if has_tc else "NO TEST CASE",
        })

    req_details = []
    fully_covered_reqs = 0

    for req_id in sorted(req_ids):
        related_cis = [ci for ci in coverage_items if ci["related_req"] == req_id]
        missing_ci = [
            ci["coverage_id"]
            for ci in related_cis
            if ci["coverage_id"] not in tc_by_coverage
        ]

        if not related_cis:
            status = "NO COVERAGE ITEMS"
        elif not missing_ci:
            status = "FULLY COVERED"
            fully_covered_reqs += 1
        else:
            status = "PARTIALLY COVERED"

        req_details.append({
            "requirement_id": req_id,
            "status": status,
            "coverage_items": len(related_cis),
            "test_cases": len(tc_by_req.get(req_id, [])),
            "missing_coverage_ids": missing_ci,
        })

    total_ci = len(coverage_items)
    ci_coverage_pct = (covered_ci / total_ci * 100) if total_ci > 0 else 0
    req_coverage_pct = (
        (fully_covered_reqs / len(req_ids) * 100) if req_ids else 0
    )

    return {
        "total_requirements": len(req_ids),
        "fully_covered_requirements": fully_covered_reqs,
        "requirement_coverage_percentage": req_coverage_pct,
        "total_coverage_items": total_ci,
        "covered_coverage_items": covered_ci,
        "coverage_item_coverage_percentage": ci_coverage_pct,
        "test_methods_used": sorted(methods_used),
        "test_methods_count": len(methods_used),
        "coverage_item_details": ci_details,
        "requirement_details": req_details,
    }
