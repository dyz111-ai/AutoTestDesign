"""
Interactive QA test design workspace (Streamlit).

Run: streamlit run streamlit_app.py
"""

import json
from io import BytesIO

import pandas as pd
import streamlit as st

from app.pipeline import (
    VALID_COVERAGE_CRITERIA,
    VALID_METHODS,
    analyze_risks,
    build_state_model,
    extract_requirements,
    generate_coverage_items,
    generate_sequences,
    generate_testcases,
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
    return pd.DataFrame(records)[columns]


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

    tc_rows = []
    for tc in tcs:
        row = dict(tc)
        row["steps"] = _steps_to_str(row.get("steps", ""))
        tc_rows.append(row)

    seq_rows = []
    for seq in seqs:
        row = dict(seq)
        row["path"] = " → ".join(row.get("path", []))
        row["events"] = " → ".join(row.get("events", []))
        seq_rows.append(row)

    return {
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


def _build_excel_bytes(frames: dict[str, pd.DataFrame]) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for sheet, df in frames.items():
            if not df.empty:
                df.to_excel(writer, sheet_name=sheet[:31], index=False)
    return buffer.getvalue()


def _export_section():
    st.subheader("10. Export Reports")
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
    _export_section()


if __name__ == "__main__":
    main()
