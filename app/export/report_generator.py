import os

import pandas as pd


def export_coverage_items(coverage_items: list):
    rows = [
        {
            "Coverage ID": item["coverage_id"],
            "Coverage Item": item["coverage_item"],
            "Related Req": item["related_req"],
        }
        for item in coverage_items
    ]

    _write_csv(rows, "output/coverage_items.csv")
    print("✅ Coverage items exported to output/coverage_items.csv")


def export_test_strategies(coverage_with_strategy: list):
    rows = [
        {
            "Coverage ID": item["coverage_id"],
            "Coverage Item": item["coverage_item"],
            "Related Req": item["related_req"],
            "Test Method": item["test_method"],
        }
        for item in coverage_with_strategy
    ]

    _write_csv(rows, "output/test_strategies.csv")
    print("✅ Test strategies exported to output/test_strategies.csv")


def export_testcases(testcases: list):
    rows = []

    for tc in testcases:
        steps = tc["steps"]
        if isinstance(steps, list):
            steps_str = " | ".join(steps)
        else:
            steps_str = str(steps)

        rows.append({
            "TC ID": tc["tc_id"],
            "Req ID": tc["req_id"],
            "Coverage ID": tc["coverage_id"],
            "Test Method": tc["test_method"],
            "Priority": tc["priority"],
            "Preconditions": tc["preconditions"],
            "Test Data": tc["test_data"],
            "Steps": steps_str,
            "Expected Result": tc["expected_result"],
        })

    _write_csv(rows, "output/testcases.csv")
    print("✅ Testcases exported to output/testcases.csv")


def export_coverage(coverage_result: dict):
    rows = []

    for detail in coverage_result["requirement_details"]:
        missing = detail.get("missing_coverage_ids", [])
        rows.append({
            "Requirement ID": detail["requirement_id"],
            "Status": detail["status"],
            "Coverage Items": detail["coverage_items"],
            "Test Cases": detail["test_cases"],
            "Missing Coverage IDs": ", ".join(missing),
        })

    _write_csv(rows, "output/coverage_report.csv")
    print("✅ Coverage report exported to output/coverage_report.csv")


def export_risk_analysis(risk_results: list):
    rows = [
        {
            "Requirement ID": item["requirement_id"],
            "Risk Score": item["risk_score"],
            "Priority": item["priority"],
            "Reason": item["reason"],
        }
        for item in risk_results
    ]

    _write_csv(rows, "output/risk_analysis.csv")
    print("✅ Risk analysis exported to output/risk_analysis.csv")


def export_state_model(model: dict):
    rows = []
    for t in model.get("transitions", []):
        rows.append({
            "From State": t["from"],
            "To State": t["to"],
            "Event": t.get("event", ""),
            "Guard": t.get("guard", ""),
        })

    _write_csv(rows, "output/state_model.csv")
    print("✅ State model exported to output/state_model.csv")


def export_whitebox_sequences(sequences: list):
    rows = []
    for seq in sequences:
        rows.append({
            "Sequence ID": seq["sequence_id"],
            "Coverage Criterion": seq["coverage_criterion"],
            "Path": " → ".join(seq["path"]),
            "Events": " → ".join(seq["events"]),
            "Covered States": seq["covered_states"],
            "Covered Transitions": seq["covered_transitions"],
        })

    _write_csv(rows, "output/whitebox_sequences.csv")
    print("✅ White-box sequences exported to output/whitebox_sequences.csv")


def _write_csv(rows: list, path: str):
    df = pd.DataFrame(rows)
    os.makedirs("output", exist_ok=True)
    df.to_csv(path, index=False)
