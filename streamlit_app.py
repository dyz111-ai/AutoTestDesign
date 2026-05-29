"""
Interactive QA test design workspace (Streamlit).

Run: streamlit run streamlit_app.py
"""

import json
import os
import subprocess
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st

from app.pipeline import (
    VALID_COVERAGE_CRITERIA,
    VALID_METHODS,
    analyze_risks,
    batch_generate_oracles,
    build_state_model,
    extract_requirements,
    generate_coverage_items,
    generate_pytest,
    generate_oracle,
    generate_sequences,
    generate_testcases,
    optimize_test_suite,
    select_strategies,
)

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

def _init_state():
    defaults = {
        "app_name": "",
        "requirements_text": "",
        "requirements": [],
        "risk_results": [],
        "state_model": {},
        "coverage_criterion": "all_states",
        "whitebox_sequences": [],
        "coverage_items": [],
        "coverage_with_strategy": [],
        "testcases": [],
        "source_files": {},
        "generated_pytest": "",
        "project_dir": "",
        "pytest_output": "",
        "oracles": [],
        "optimized_testcases": [],
        "optimization_metrics": {},
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _prd_payload() -> str:
    app = st.session_state.app_name.strip()
    body = st.session_state.requirements_text.strip()
    if app:
        return f"Target Application: {app}\n\nRequirements:\n{body}"
    return body


def _steps_to_str(steps) -> str:
    if isinstance(steps, list):
        return " | ".join(str(s) for s in steps)
    return str(steps) if steps is not None else ""


def _steps_from_str(text) -> list:
    if not text or (isinstance(text, float) and pd.isna(text)):
        return []
    return [s.strip() for s in str(text).split("|") if s.strip()]


def _records_to_df(records: list, columns: list) -> pd.DataFrame:
    if not records:
        return pd.DataFrame(columns=columns)
    df = pd.DataFrame(records)
    # Keep only the requested columns that exist in the data
    available = [c for c in columns if c in df.columns]
    return df[available]


def _df_to_records(df: pd.DataFrame) -> list:
    if df is None or df.empty:
        return []
    return df.fillna("").to_dict("records")


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------

def _all_export_frames() -> dict[str, pd.DataFrame]:
    reqs = st.session_state.requirements
    risks = st.session_state.risk_results
    model = st.session_state.state_model
    seqs = st.session_state.whitebox_sequences
    cis = st.session_state.coverage_items
    strategies = st.session_state.coverage_with_strategy
    tcs = st.session_state.testcases
    oracles = st.session_state.oracles
    opt_tcs = st.session_state.optimized_testcases

    tc_rows = []
    for tc in tcs:
        row = dict(tc)
        row["steps"] = _steps_to_str(row.get("steps", ""))
        tc_rows.append(row)

    opt_rows = []
    for tc in opt_tcs:
        row = dict(tc)
        row["steps"] = _steps_to_str(row.get("steps", ""))
        opt_rows.append(row)

    seq_rows = []
    for seq in seqs:
        row = dict(seq)
        row["path"] = " → ".join(row.get("path", []))
        row["events"] = " → ".join(row.get("events", []))
        seq_rows.append(row)

    frames = {
        "requirements": _records_to_df(
            reqs, ["requirement_id", "description", "type"]
        ),
        "risk_analysis": _records_to_df(
            risks, ["requirement_id", "risk_score", "priority", "reason"]
        ),
        "state_model": _records_to_df(
            model.get("transitions", []),
            ["from", "to", "event", "guard"],
        ),
        "whitebox_sequences": _records_to_df(
            seq_rows,
            [
                "sequence_id", "coverage_criterion",
                "path", "events",
                "covered_states", "covered_transitions",
            ],
        ),
        "coverage_items": _records_to_df(
            cis, ["coverage_id", "coverage_item", "related_req"]
        ),
        "test_strategies": _records_to_df(
            strategies,
            ["coverage_id", "coverage_item", "related_req", "test_method"],
        ),
        "testcases": _records_to_df(
            tc_rows,
            [
                "tc_id",
                "req_id",
                "coverage_id",
                "test_method",
                "priority",
                "preconditions",
                "test_data",
                "steps",
                "expected_result",
            ],
        ),
    }

    if oracles:
        frames["test_oracles"] = _records_to_df(
            oracles,
            [
                "tc_id",
                "coverage_id",
                "requirement_id",
                "test_data",
                "expected_output",
                "validation_rules",
                "oracle_type",
                "rationale",
            ],
        )

    if opt_rows:
        frames["optimized_testcases"] = _records_to_df(
            opt_rows,
            [
                "tc_id",
                "req_id",
                "coverage_id",
                "test_method",
                "priority",
                "preconditions",
                "test_data",
                "steps",
                "expected_result",
            ],
        )

    return frames


def _build_excel_bytes(frames: dict[str, pd.DataFrame]) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for sheet, df in frames.items():
            if not df.empty:
                df.to_excel(writer, sheet_name=sheet[:31], index=False)
    return buffer.getvalue()


def _export_section():
    st.subheader("12. Export Reports")
    frames = _all_export_frames()
    has_data = any(not df.empty for df in frames.values())

    if not has_data:
        st.info("Generate and edit data above before exporting.")
        return

    app_slug = (
        st.session_state.app_name.strip().replace(" ", "_") or "qa_export"
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        for name, df in frames.items():
            if df.empty:
                continue
            st.download_button(
                label=f"CSV: {name}",
                data=df.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"{app_slug}_{name}.csv",
                mime="text/csv",
                key=f"dl_csv_{name}",
            )

    with col2:
        payload = {
            "app_name": st.session_state.app_name,
            "requirements": st.session_state.requirements,
            "risk_analysis": st.session_state.risk_results,
            "state_model": st.session_state.state_model,
            "whitebox_sequences": st.session_state.whitebox_sequences,
            "coverage_items": st.session_state.coverage_items,
            "test_strategies": st.session_state.coverage_with_strategy,
            "testcases": [
                {**tc, "steps": _steps_from_str(_steps_to_str(tc.get("steps", "")))}
                for tc in st.session_state.testcases
            ],
        }
        st.download_button(
            label="JSON (all artifacts)",
            data=json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
            file_name=f"{app_slug}_full_export.json",
            mime="application/json",
            key="dl_json_all",
        )

    with col3:
        excel_bytes = _build_excel_bytes(frames)
        st.download_button(
            label="Excel (all sheets)",
            data=excel_bytes,
            file_name=f"{app_slug}_full_export.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
            key="dl_xlsx_all",
        )

    st.caption(
        "Exports reflect the latest values in the editable tables above."
    )


# ---------------------------------------------------------------------------
# Main UI
# ---------------------------------------------------------------------------

def main():
    st.set_page_config(
        page_title="AutoTestDesign",

        layout="wide",
    )
    _init_state()

    st.title("AutoTestDesign")
    st.caption(
        "Interactive workflow: Requirements → Risk → State Model → "
        "White-box Sequences → Coverage Items → Test Strategies → Test Cases. "
        "Review and edit each step before export."
    )

    # -------------------------------------------------------------------
    # 0. Source Files (placed at top; processing happens at step 10)
    # -------------------------------------------------------------------
    st.subheader("0. Source Files Under Test")

    col_dir, col_files = st.columns([1, 2])

    with col_dir:
        st.session_state.project_dir = st.text_input(
            "Project root directory",
            value=st.session_state.project_dir,
            placeholder="/path/to/your/project",
            help=(
                "Filesystem path to the project.  Generated pytest files "
                "will be saved to this directory's `tests/` subfolder and "
                "executed from here."
            ),
            key="input_project_dir",
        )

    with col_files:
        uploaded_files = st.file_uploader(
            "Select source files (.py) to test",
            type=["py"],
            accept_multiple_files=True,
            key="pytest_source_uploader",
            help=(
                "Upload the Python source files that define the functions/"
                "classes under test.  The LLM uses these to generate "
                "correct imports and function calls."
            ),
        )

    if uploaded_files:
        source_files = {}
        for uf in uploaded_files:
            try:
                content = uf.read().decode("utf-8")
            except UnicodeDecodeError:
                st.warning(f"Skipping {uf.name}: not a UTF-8 text file.")
                continue
            source_files[uf.name] = content
        st.session_state.source_files = source_files

        if source_files:
            st.caption(
                f"Loaded {len(source_files)} file(s): "
                + ", ".join(f"`{n}`" for n in source_files)
            )

    st.divider()

    st.subheader("1. Target Application Name")
    st.session_state.app_name = st.text_input(
        "Application name",
        value=st.session_state.app_name,
        placeholder="e.g. Web Login Module",
        label_visibility="collapsed",
    )

    st.subheader("2. Requirements")
    st.session_state.requirements_text = st.text_area(
        "PRD text",
        value=st.session_state.requirements_text,
        height=200,
        placeholder="Paste PRD or numbered requirements here...",
        label_visibility="collapsed",
    )

    sample_path = "sample_prd/login_prd.txt"
    if st.button("Load sample PRD"):
        try:
            with open(sample_path, encoding="utf-8") as f:
                st.session_state.requirements_text = f.read()
            st.session_state.app_name = "Web Login Module"
            st.rerun()
        except OSError:
            st.error(f"Could not load {sample_path}")

    st.divider()

    st.subheader("3. Parse Requirements")
    if st.button("Parse Requirements", type="primary"):
        text = _prd_payload()
        if not text.strip():
            st.warning("Enter application name and/or requirements first.")
        else:
            with st.spinner("Extracting structured requirements..."):
                try:
                    st.session_state.requirements = extract_requirements(text)
                    st.session_state.risk_results = []
                    st.session_state.coverage_items = []
                    st.session_state.coverage_with_strategy = []
                    st.session_state.testcases = []
                    st.success(
                        f"Parsed {len(st.session_state.requirements)} requirement(s)."
                    )
                except Exception as exc:
                    st.error(f"Parse failed: {exc}")
    edited_req = st.data_editor(
        _records_to_df(
            st.session_state.requirements,
            ["requirement_id", "description", "type"],
        ),
        num_rows="dynamic",
        use_container_width=True,
        key="editor_requirements",
    )
    st.session_state.requirements = _df_to_records(edited_req)

    st.divider()

    st.subheader("4. Risk Analysis")
    if st.button(
        "Generate Risk Analysis",
        disabled=not st.session_state.requirements,
    ):
        with st.spinner("Analyzing risks..."):
            try:
                st.session_state.risk_results = analyze_risks(
                    st.session_state.requirements
                )
                st.session_state.coverage_items = []
                st.session_state.coverage_with_strategy = []
                st.session_state.testcases = []
                st.success("Risk analysis complete.")
            except Exception as exc:
                st.error(f"Risk analysis failed: {exc}")
    edited_risk = st.data_editor(
        _records_to_df(
            st.session_state.risk_results,
            ["requirement_id", "risk_score", "priority", "reason"],
        ),
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "risk_score": st.column_config.NumberColumn(
                min_value=1, max_value=10, step=1
            ),
            "priority": st.column_config.SelectboxColumn(
                options=["High", "Medium", "Low"]
            ),
        },
        key="editor_risk",
    )
    risk_records = _df_to_records(edited_risk)
    for row in risk_records:
        try:
            row["risk_score"] = int(row["risk_score"])
        except (TypeError, ValueError):
            row["risk_score"] = 5
    st.session_state.risk_results = risk_records

    st.divider()

    st.subheader("5. State Transition Model (White-box)")
    if st.button(
        "Build State Model",
        disabled=not st.session_state.risk_results,
    ):
        with st.spinner("Building state transition model..."):
            try:
                st.session_state.state_model = build_state_model(
                    st.session_state.requirements
                )
                st.session_state.whitebox_sequences = []
                st.success(
                    f"Model has {len(st.session_state.state_model.get('states', []))} states "
                    f"and {len(st.session_state.state_model.get('transitions', []))} transitions."
                )
            except Exception as exc:
                st.error(f"State model build failed: {exc}")

    model = st.session_state.state_model
    if model:
        st.caption(
            f"Initial State: **{model.get('initial_state', 'N/A')}** | "
            f"States: {len(model.get('states', []))} | "
            f"Transitions: {len(model.get('transitions', []))}"
        )

        states_df = pd.DataFrame(
            {"State": model.get("states", [])}
        )
        edited_states = st.data_editor(
            states_df,
            num_rows="dynamic",
            use_container_width=True,
            key="editor_states",
        )

        trans_cols = ["from", "to", "event", "guard"]
        trans_df = _records_to_df(model.get("transitions", []), trans_cols)
        edited_trans = st.data_editor(
            trans_df,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "from": st.column_config.TextColumn("From State"),
                "to": st.column_config.TextColumn("To State"),
                "event": st.column_config.TextColumn("Event"),
                "guard": st.column_config.TextColumn("Guard"),
            },
            key="editor_transitions",
        )

        st.session_state.state_model = {
            "states": _df_to_records(edited_states),
            "transitions": _df_to_records(edited_trans),
            "initial_state": model.get("initial_state", ""),
        }
        st.session_state.state_model["states"] = [
            s["State"] if isinstance(s, dict) else s
            for s in st.session_state.state_model["states"]
        ]

    st.divider()

    st.subheader("6. White-box Test Sequences")
    st.session_state.coverage_criterion = st.selectbox(
        "Coverage Criterion",
        options=VALID_COVERAGE_CRITERIA,
        index=(
            VALID_COVERAGE_CRITERIA.index(st.session_state.coverage_criterion)
            if st.session_state.coverage_criterion in VALID_COVERAGE_CRITERIA
            else 0
        ),
        key="select_criterion",
    )

    if st.button(
        "Generate Sequences",
        disabled=not st.session_state.state_model,
    ):
        with st.spinner("Generating test sequences..."):
            try:
                st.session_state.whitebox_sequences = generate_sequences(
                    st.session_state.state_model,
                    st.session_state.coverage_criterion,
                )
                st.success(
                    f"Generated {len(st.session_state.whitebox_sequences)} sequence(s)."
                )
            except Exception as exc:
                st.error(f"Sequence generation failed: {exc}")

    seq_cols = [
        "sequence_id", "coverage_criterion",
        "path", "events",
        "covered_states", "covered_transitions",
    ]
    seq_df = _records_to_df(st.session_state.whitebox_sequences, seq_cols)
    for col in ["path", "events"]:
        if col in seq_df.columns:
            seq_df[col] = seq_df[col].apply(
                lambda x: " → ".join(x) if isinstance(x, list) else str(x) if x else ""
            )
    edited_seq = st.data_editor(
        seq_df,
        num_rows="dynamic",
        use_container_width=True,
        key="editor_sequences",
    )
    st.session_state.whitebox_sequences = _df_to_records(edited_seq)

    st.divider()

    st.subheader("7. Coverage Items")
    if st.button(
        "Generate Coverage Items",
        disabled=not st.session_state.risk_results,
    ):
        with st.spinner("Identifying coverage items..."):
            try:
                st.session_state.coverage_items = generate_coverage_items(
                    st.session_state.requirements
                )
                st.session_state.coverage_with_strategy = []
                st.session_state.testcases = []
                st.success(
                    f"Generated {len(st.session_state.coverage_items)} coverage item(s)."
                )
            except Exception as exc:
                st.error(f"Coverage item generation failed: {exc}")
    edited_ci = st.data_editor(
        _records_to_df(
            st.session_state.coverage_items,
            ["coverage_id", "coverage_item", "related_req"],
        ),
        num_rows="dynamic",
        use_container_width=True,
        key="editor_coverage",
    )
    st.session_state.coverage_items = _df_to_records(edited_ci)

    st.divider()

    st.subheader("8. Test Strategies")
    if st.button(
        "Generate Test Strategies",
        disabled=not st.session_state.coverage_items,
    ):
        with st.spinner("Selecting test strategies..."):
            try:
                st.session_state.coverage_with_strategy = select_strategies(
                    st.session_state.coverage_items
                )
                st.session_state.testcases = []
                methods = {
                    x["test_method"]
                    for x in st.session_state.coverage_with_strategy
                }
                st.success(
                    f"Strategies assigned. Techniques used: {', '.join(sorted(methods))}"
                )
                if len(methods) < 3:
                    st.warning(
                        "Fewer than 3 techniques used. Edit the table or regenerate."
                    )
            except Exception as exc:
                st.error(f"Strategy selection failed: {exc}")
    edited_strat = st.data_editor(
        _records_to_df(
            st.session_state.coverage_with_strategy,
            ["coverage_id", "coverage_item", "related_req", "test_method"],
        ),
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "test_method": st.column_config.SelectboxColumn(options=VALID_METHODS),
        },
        key="editor_strategies",
    )
    st.session_state.coverage_with_strategy = _df_to_records(edited_strat)

    st.divider()

    st.subheader("9. Test Cases")
    if st.button(
        "Generate Test Cases",
        disabled=not st.session_state.coverage_with_strategy,
    ):
        with st.spinner("Generating test cases..."):
            try:
                raw = generate_testcases(
                    st.session_state.requirements,
                    st.session_state.risk_results,
                    st.session_state.coverage_with_strategy,
                )
                for tc in raw:
                    tc["steps"] = _steps_to_str(tc.get("steps", ""))
                st.session_state.testcases = raw
                st.success(f"Generated {len(raw)} test case(s).")
            except Exception as exc:
                st.error(f"Test case generation failed: {exc}")
    edited_tc = st.data_editor(
        _records_to_df(
            st.session_state.testcases,
            [
                "tc_id",
                "req_id",
                "coverage_id",
                "test_method",
                "priority",
                "preconditions",
                "test_data",
                "steps",
                "expected_result",
            ],
        ),
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "test_method": st.column_config.SelectboxColumn(options=VALID_METHODS),
            "priority": st.column_config.SelectboxColumn(
                options=["High", "Medium", "Low"]
            ),
            "steps": st.column_config.TextColumn(help="Separate steps with |"),
        },
        key="editor_testcases",
    )
    st.session_state.testcases = _df_to_records(edited_tc)

    st.divider()

    # -----------------------------------------------------------------------
    # 10. Generate Pytest Files (processing happens here)
    # -----------------------------------------------------------------------
    st.subheader("10. Generate Pytest Files")

    gen_disabled = (
        not st.session_state.testcases
        or not st.session_state.source_files
    )

    if st.button(
        "Generate Pytest Files",
        type="primary",
        disabled=gen_disabled,
        key="btn_generate_pytest",
    ):
        with st.spinner(
            "Generating pytest file from test cases and source code..."
        ):
            try:
                st.session_state.generated_pytest = generate_pytest(
                    testcases=st.session_state.testcases,
                    source_files=st.session_state.source_files,
                    app_name=st.session_state.app_name,
                )
                st.session_state.pytest_output = ""
                st.success("Pytest file generated.")
            except Exception as exc:
                st.error(f"Pytest generation failed: {exc}")

    if st.session_state.generated_pytest:
        st.caption("Preview — edit in the text area below if needed:")
        edited_code = st.text_area(
            "Generated pytest code",
            value=st.session_state.generated_pytest,
            height=300,
            key="editor_pytest_code",
            label_visibility="collapsed",
        )
        st.session_state.generated_pytest = edited_code

        app_slug = (
            st.session_state.app_name.strip().replace(" ", "_")
            or "generated"
        )
        st.download_button(
            label="Download pytest file",
            data=st.session_state.generated_pytest.encode("utf-8"),
            file_name=f"test_{app_slug}.py",
            mime="text/x-python",
            key="dl_pytest_file",
        )

        # ---- Save to disk and run pytest ----
        project_dir = st.session_state.project_dir.strip()
        if project_dir and os.path.isdir(project_dir):
            tests_dir = os.path.join(project_dir, "tests")
            os.makedirs(tests_dir, exist_ok=True)

            if st.button(
                "Save & Run Pytest",
                type="secondary",
                key="btn_run_pytest",
            ):
                test_path = os.path.join(
                    tests_dir, f"test_{app_slug}.py"
                )
                try:
                    with open(test_path, "w", encoding="utf-8") as f:
                        f.write(st.session_state.generated_pytest)
                    st.success(
                        f"Saved to `{test_path}`"
                    )
                except OSError as exc:
                    st.error(f"Failed to save pytest file: {exc}")

                # ---- Run pytest ----
                with st.spinner(
                    f"Running pytest in `{project_dir}`..."
                ):
                    try:
                        result = subprocess.run(
                            [
                                "python", "-m", "pytest",
                                os.path.relpath(test_path, project_dir),
                                "-v",
                            ],
                            cwd=project_dir,
                            capture_output=True,
                            text=True,
                            timeout=120,
                        )
                        st.session_state.pytest_output = (
                            result.stdout + result.stderr
                        )
                    except subprocess.TimeoutExpired:
                        st.session_state.pytest_output = (
                            "Pytest timed out after 120 seconds."
                        )
                    except FileNotFoundError:
                        st.session_state.pytest_output = (
                            "`pytest` not found.  "
                            "Install it with: pip install pytest"
                        )
                    except Exception as exc:
                        st.session_state.pytest_output = (
                            f"Failed to run pytest: {exc}"
                        )
        elif project_dir:
            st.warning(
                f"Directory `{project_dir}` does not exist.  "
                "Specify a valid project directory above to save & run."
            )

        # ---- Display pytest output ----
        if st.session_state.pytest_output:
            st.subheader("Pytest Output")
            st.code(st.session_state.pytest_output, language="text")
            if "failed" in st.session_state.pytest_output.lower():
                st.warning(
                    "Some tests failed — review the output above."
                )
            else:
                st.success("All tests passed!" if st.session_state.pytest_output.strip() else "")
        # ---- End save & run ----

    st.divider()

    # -----------------------------------------------------------------------
    # FR 5.0 – Test Oracle Generation
    # -----------------------------------------------------------------------
    st.subheader("10. Test Oracle Generation (FR 5.0)")
    st.caption(
        "Select a requirement and enter specific test data to synthesize a "
        "precise expected result and validation rules."
    )

    oracle_mode = st.radio(
        "Oracle generation mode",
        ["Single Oracle (interactive)", "Batch – enrich all test cases"],
        horizontal=True,
        key="oracle_mode",
    )

    if oracle_mode == "Single Oracle (interactive)":
        req_options = {
            f"{r['requirement_id']}: {r['description'][:60]}": r
            for r in st.session_state.requirements
        }
        if req_options:
            selected_label = st.selectbox(
                "Requirement", list(req_options.keys()), key="oracle_req_select"
            )
            selected_req = req_options[selected_label]
            oracle_input = st.text_area(
                "Test data / input scenario",
                placeholder="e.g. email=test@example.com, password=abc (7 chars)",
                key="oracle_input",
                height=80,
            )
            if st.button(
                "Generate Oracle",
                type="primary",
                disabled=not oracle_input.strip(),
            ):
                with st.spinner("Synthesizing test oracle..."):
                    try:
                        result = generate_oracle(selected_req, oracle_input.strip())
                        st.success("Oracle generated.")
                        col_a, col_b = st.columns(2)
                        with col_a:
                            st.markdown("**Expected Output**")
                            st.info(result.get("expected_output", "—"))
                            st.markdown(f"**Oracle Type:** `{result.get('oracle_type', '—')}`")
                        with col_b:
                            st.markdown("**Validation Rules**")
                            for rule in result.get("validation_rules", []):
                                st.markdown(f"- {rule}")
                        st.markdown("**Rationale**")
                        st.write(result.get("rationale", "—"))
                    except Exception as exc:
                        st.error(f"Oracle generation failed: {exc}")
        else:
            st.info("Parse requirements first (Step 3).")

    else:
        st.caption(
            "Generates an oracle for every test case using its requirement "
            "context and test data. This calls the LLM once per test case."
        )
        n_tcs = len(st.session_state.testcases)
        if st.button(
            f"Batch Generate Oracles ({n_tcs} test cases)",
            type="primary",
            disabled=not st.session_state.testcases,
        ):
            with st.spinner(f"Generating {n_tcs} oracles..."):
                try:
                    oracles = batch_generate_oracles(
                        st.session_state.requirements,
                        st.session_state.testcases,
                    )
                    st.session_state.oracles = oracles
                    st.success(f"Generated {len(oracles)} oracles.")
                except Exception as exc:
                    st.error(f"Batch oracle generation failed: {exc}")

        if st.session_state.oracles:
            oracle_df_cols = [
                "tc_id", "coverage_id", "requirement_id",
                "test_data", "expected_output", "oracle_type", "rationale",
            ]
            oracle_display = []
            for o in st.session_state.oracles:
                row = {c: o.get(c, "") for c in oracle_df_cols}
                row["validation_rules"] = " | ".join(o.get("validation_rules", []))
                oracle_display.append(row)
            st.dataframe(
                pd.DataFrame(oracle_display),
                use_container_width=True,
            )

    st.divider()

    # -----------------------------------------------------------------------
    # FR 7.0 – Test Suite Optimization
    # -----------------------------------------------------------------------
    st.subheader("11. Test Suite Optimization (FR 7.0)")
    st.caption(
        "Prioritize or minimize the generated test suite based on risk or "
        "coverage efficiency."
    )

    opt_strategy = st.radio(
        "Optimization strategy",
        [
            "risk – Sort & filter by risk priority",
            "coverage – Remove redundant test cases",
            "both – Minimize then prioritize",
        ],
        horizontal=True,
        key="opt_strategy",
    )
    strategy_key = opt_strategy.split(" – ")[0]

    min_prio = st.select_slider(
        "Minimum priority to keep (for risk-based strategies)",
        options=["High", "Medium", "Low"],
        value="Low",
        key="opt_min_priority",
    )

    if st.button(
        "Optimize Test Suite",
        type="primary",
        disabled=not st.session_state.testcases,
    ):
        source = st.session_state.testcases
        with st.spinner("Optimizing..."):
            try:
                optimized, metrics = optimize_test_suite(
                    source, strategy=strategy_key, min_priority=min_prio
                )
                st.session_state.optimized_testcases = optimized
                st.session_state.optimization_metrics = metrics
                st.success(
                    f"Optimized: {metrics['original_count']} → "
                    f"{metrics['optimized_count']} test cases "
                    f"(removed {metrics['removed_count']})."
                )
            except Exception as exc:
                st.error(f"Optimization failed: {exc}")

    if st.session_state.optimization_metrics:
        m = st.session_state.optimization_metrics
        cols = st.columns(4)
        cols[0].metric("Original", m.get("original_count", 0))
        cols[1].metric("Optimized", m.get("optimized_count", 0))
        cols[2].metric("Removed", m.get("removed_count", 0))
        cols[3].metric(
            "High priority",
            m.get("high_count", "—"),
        )
        st.caption(f"Strategy applied: **{m.get('strategy', '—')}**")

    if st.session_state.optimized_testcases:
        edited_opt = st.data_editor(
            _records_to_df(
                st.session_state.optimized_testcases,
                [
                    "tc_id",
                    "req_id",
                    "coverage_id",
                    "test_method",
                    "priority",
                    "preconditions",
                    "test_data",
                    "steps",
                    "expected_result",
                ],
            ),
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "test_method": st.column_config.SelectboxColumn(options=VALID_METHODS),
                "priority": st.column_config.SelectboxColumn(
                    options=["High", "Medium", "Low"]
                ),
                "steps": st.column_config.TextColumn(help="Separate steps with |"),
            },
            key="editor_optimized",
        )
        st.session_state.optimized_testcases = _df_to_records(edited_opt)

    st.divider()
    _export_section()


if __name__ == "__main__":
    main()
