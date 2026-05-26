from app.core.prd_parser import load_prd
from app.pipeline import (
    VALID_COVERAGE_CRITERIA,
    VALID_METHODS,
    analyze_coverage,
    analyze_risks,
    build_state_model,
    extract_requirements,
    generate_coverage_items,
    generate_sequences,
    generate_testcases,
    select_strategies,
)
from app.export import (
    export_coverage,
    export_coverage_items,
    export_risk_analysis,
    export_state_model,
    export_test_strategies,
    export_testcases,
    export_whitebox_sequences,
)


def main():
    print("🚀 AI Test Case Generator Started")

    prd_path = "sample_prd/login_prd.txt"
    prd_content = load_prd(prd_path)

    if not prd_content:
        print("❌ Failed to load PRD")
        return

    print("\n📄 PRD Loaded Successfully")

    print("\n🧠 Extracting Requirements using AI...\n")
    requirements = extract_requirements(prd_content)
    print("✅ Requirements Extracted\n")

    print("\n⚠️ Analyzing Risks & Priorities...\n")
    risk_results = analyze_risks(requirements)
    print("✅ Risk Analysis Completed\n")

    print("\n📋 Risk Analysis Report:")
    for item in risk_results:
        print(
            f"  {item['requirement_id']} | Score: {item['risk_score']} | "
            f"{item['priority']} | {item['reason']}"
        )

    print("\n🔧 Building State Transition Model (White-box)...\n")
    state_model = build_state_model(requirements)
    print("✅ State Model Built\n")

    print(f"  Initial State: {state_model.get('initial_state', 'N/A')}")
    print(f"  States ({len(state_model.get('states', []))}): "
          f"{', '.join(state_model.get('states', []))}")
    print(f"  Transitions: {len(state_model.get('transitions', []))}")
    for t in state_model.get("transitions", []):
        guard = f" [{t['guard']}]" if t.get("guard") else ""
        print(f"    {t['from']} --({t.get('event', '')}){guard}--> {t['to']}")

    print(f"\n🧬 Generating White-box Test Sequences...\n")
    all_sequences = []
    for criterion in VALID_COVERAGE_CRITERIA:
        sequences = generate_sequences(state_model, criterion)
        all_sequences.extend(sequences)
        print(f"  Criterion: {criterion}")
        for seq in sequences:
            print(f"    {seq['sequence_id']} | {seq['coverage_criterion']} | "
                  f"States: {seq['covered_states']} | "
                  f"Transitions: {seq['covered_transitions']}")
            print(f"    Path: {' → '.join(seq['path'])}")
    print("✅ White-box Sequences Generated\n")

    print("\n🎯 Identifying Coverage Items...\n")
    coverage_items = generate_coverage_items(requirements)
    print("✅ Coverage Items Identified\n")

    print("\n📋 Coverage Items:")
    for ci in coverage_items:
        print(f"  {ci['coverage_id']} | {ci['coverage_item']} | {ci['related_req']}")

    print("\n📐 Selecting Test Strategies...\n")
    coverage_with_strategy = select_strategies(coverage_items)
    print("✅ Test Strategies Selected\n")

    print("\n📋 Test Strategies:")
    for item in coverage_with_strategy:
        print(
            f"  {item['coverage_id']} | {item['coverage_item']} | "
            f"{item['test_method']}"
        )

    methods_used = {item["test_method"] for item in coverage_with_strategy}
    print(f"\n  Techniques used: {', '.join(sorted(methods_used))}")
    if len(methods_used) < 3:
        print(
            f"  ⚠️ Warning: only {len(methods_used)} technique(s) used; "
            f"assignment requires at least 3. Available: {', '.join(VALID_METHODS)}"
        )

    print("\n🧪 Generating Test Cases...\n")
    testcases = generate_testcases(
        requirements, risk_results, coverage_with_strategy
    )
    print("✅ Test Cases Generated\n")

    print("\n📋 Test Cases:")
    for tc in testcases:
        expected = tc.get("expected_result", "")
        if len(expected) > 60:
            expected = expected[:60] + "..."
        print(
            f"  {tc['tc_id']} | {tc['coverage_id']} | {tc['test_method']} | "
            f"{tc['priority']} | {expected}"
        )

    print("\n📊 Analyzing Coverage...\n")
    coverage_result = analyze_coverage(
        requirements, coverage_items, testcases
    )

    print("📈 Coverage Summary:")
    print(f"Total Requirements: {coverage_result['total_requirements']}")
    print(
        f"Fully Covered Requirements: "
        f"{coverage_result['fully_covered_requirements']}"
    )
    print(
        f"Requirement Coverage %: "
        f"{coverage_result['requirement_coverage_percentage']:.2f}%"
    )
    print(f"Total Coverage Items: {coverage_result['total_coverage_items']}")
    print(
        f"Covered Coverage Items: "
        f"{coverage_result['covered_coverage_items']}"
    )
    print(
        f"Coverage Item Coverage %: "
        f"{coverage_result['coverage_item_coverage_percentage']:.2f}%"
    )
    print(
        f"Test Methods Used ({coverage_result['test_methods_count']}): "
        f"{', '.join(coverage_result['test_methods_used'])}"
    )

    print("\n📁 Exporting Reports...\n")

    export_coverage_items(coverage_items)
    export_test_strategies(coverage_with_strategy)
    export_testcases(testcases)
    export_risk_analysis(risk_results)
    export_coverage(coverage_result)
    export_state_model(state_model)
    export_whitebox_sequences(all_sequences)

    print("\n🎉 All Reports Generated Successfully!")


if __name__ == "__main__":
    main()
