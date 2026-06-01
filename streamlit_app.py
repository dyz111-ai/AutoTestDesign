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
    coverage_items_from_whitebox,
    extract_requirements,
    generate_coverage_items,
    generate_pytest,
    generate_oracle,
    generate_sequences,
    generate_testcases,
    merge_coverage_items,
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
        "optimization_metrics": {},
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _prd_payload() -> str:
    return st.session_state.requirements_text.strip()


def _state_node_id(name: str) -> str:
    """Mermaid-safe node id."""
    slug = "".join(c if c.isalnum() else "_" for c in str(name).strip())
    return f"S_{slug or 'state'}"


def _build_state_diagram_mermaid(model: dict) -> str:
    """Build a Mermaid flowchart: states as nodes, transitions labeled with event/guard."""
    transitions = model.get("transitions", [])
    states = list(model.get("states", []))

    for t in transitions:
        for key in ("from", "to"):
            s = t.get(key, "")
            if s and s not in states:
                states.append(s)

    lines = ["flowchart TD"]
    lines.append(
        "    classDef startNode fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px"
    )
    lines.append(
        "    classDef stateNode fill:#e3f2fd,stroke:#1565c0,stroke-width:1px"
    )

    initial = model.get("initial_state", "")
    if initial:
        lines.append('    __start__(["Initial"]):::startNode')
        lines.append(f"    __start__ --> {_state_node_id(initial)}")

    for state in states:
        sid = _state_node_id(state)
        label = str(state).replace('"', "'")
        lines.append(f'    {sid}["{label}"]:::stateNode')

    for t in transitions:
        frm = _state_node_id(t.get("from", ""))
        to = _state_node_id(t.get("to", ""))
        event = str(t.get("event", "")).replace("\u0022", "'")
        guard = str(t.get("guard", "")).replace("\u0022", "'")
        if guard:
            edge_label = f"{event} / {guard}"
        else:
            edge_label = event or "transition"
        lines.append(f'    {frm} -->|"{edge_label}"| {to}')

    return "\n".join(lines)


def _render_state_model_graph(model: dict):
    if not model or not model.get("transitions"):
        st.caption("Build the state model to see the transition diagram.")
        return
    mermaid = _build_state_diagram_mermaid(model)
    st.markdown("**State Transition Diagram**")
    st.caption("Arrows: state transitions · Labels: event / guard condition")
    html = f"""
    <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
    <pre class="mermaid">{mermaid}</pre>
    <script>
        mermaid.initialize({{ startOnLoad: true, theme: "default", flowchart: {{ useMaxWidth: true }} }});
    </script>
    """
    st.components.v1.html(html, height=480, scrolling=True)


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


def _has_whitebox_artifacts() -> bool:
    model = st.session_state.state_model or {}
    return bool(model.get("transitions")) or bool(st.session_state.whitebox_sequences)


def _whitebox_coverage_items() -> list:
    return coverage_items_from_whitebox(
        st.session_state.state_model,
        _normalize_whitebox_sequences(st.session_state.whitebox_sequences),
        st.session_state.requirements,
    )


def _normalize_whitebox_sequences(sequences: list) -> list:
    """Restore list path/events after data_editor string display."""
    out = []
    for seq in sequences or []:
        s = dict(seq)
        for key in ("path", "events"):
            val = s.get(key)
            if isinstance(val, str) and val.strip():
                s[key] = [
                    p.strip()
                    for p in val.replace(" → ", "→").split("→")
                    if p.strip()
                ]
        out.append(s)
    return out


def _reset_data_editors(*keys: str):
    """Clear st.data_editor widget state so new data is not overwritten."""
    for key in keys:
        st.session_state.pop(key, None)


COVERAGE_ITEM_COLUMNS = ["coverage_id", "coverage_item", "related_req"]

STRATEGY_TC_COLUMNS = [
    "coverage_id",
    "coverage_item",
    "test_method",
    "priority",
    "preconditions",
    "test_data",
    "steps",
    "expected_result",
]


def _row_id(item: dict) -> str:
    return str(item.get("coverage_id") or item.get("tc_id") or "").strip()


def _merge_strategy_tc_rows(
    coverage_items: list,
    coverage_with_strategy: list,
    testcases: list,
) -> list:
    """Merge strategies and test cases for Tab 2 (ordered by coverage items)."""
    strat_map = {
        s.get("coverage_id"): s for s in coverage_with_strategy if s.get("coverage_id")
    }
    tc_map: dict[str, dict] = {}
    for t in testcases:
        key = _row_id(t)
        if key:
            tc_map[key] = t

    rows = []
    for ci in coverage_items:
        cid = ci.get("coverage_id", "")
        if not cid:
            continue
        strat = strat_map.get(cid, {})
        tc = tc_map.get(cid, {})
        rows.append({
            "coverage_id": cid,
            "coverage_item": ci.get("coverage_item") or strat.get("coverage_item", ""),
            "test_method": strat.get("test_method") or tc.get("test_method", ""),
            "priority": tc.get("priority", ""),
            "preconditions": tc.get("preconditions", ""),
            "test_data": tc.get("test_data", ""),
            "steps": _steps_to_str(tc.get("steps", "")),
            "expected_result": tc.get("expected_result", ""),
        })
    return rows


def _split_strategy_tc_rows(
    rows: list,
    coverage_items: list,
) -> tuple[list, list]:
    """Split Tab 2 back into strategies and test cases."""
    ci_map = {c.get("coverage_id"): c for c in coverage_items if c.get("coverage_id")}
    coverage_with_strategy = []
    testcases = []

    for row in rows:
        cid = str(row.get("coverage_id", "")).strip()
        if not cid:
            continue
        ci = ci_map.get(cid, {})
        related_req = ci.get("related_req", "")
        coverage_item = ci.get("coverage_item") or str(row.get("coverage_item", ""))

        test_method = str(row.get("test_method", "")).strip()
        coverage_with_strategy.append({
            "coverage_id": cid,
            "coverage_item": coverage_item,
            "related_req": related_req,
            "test_method": test_method,
        })
        testcases.append({
            "tc_id": cid,
            "req_id": related_req,
            "coverage_id": cid,
            "test_method": test_method,
            "priority": row.get("priority", ""),
            "preconditions": row.get("preconditions", ""),
            "test_data": row.get("test_data", ""),
            "steps": row.get("steps", ""),
            "expected_result": row.get("expected_result", ""),
        })

    return coverage_with_strategy, testcases


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

    return frames


def _build_excel_bytes(frames: dict[str, pd.DataFrame]) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for sheet, df in frames.items():
            if not df.empty:
                df.to_excel(writer, sheet_name=sheet[:31], index=False)
    return buffer.getvalue()


def _export_section():
    st.subheader("7. Export Reports")
    frames = _all_export_frames()
    has_data = any(not df.empty for df in frames.values())

    if not has_data:
        st.info("Generate and edit data above before exporting.")
        return

    app_slug = "autotest_export"

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
        "Interactive workflow: Requirements → Risk → White-box → "
        "Black-box Test Design → Pytest / Export. "
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

    st.subheader("1. Requirements")
    st.session_state.requirements_text = st.text_area(
        "PRD text",
        value=st.session_state.requirements_text,
        height=200,
        placeholder="Paste PRD or numbered requirements here...",
        label_visibility="collapsed",
    )

    sample_path = "sample_prd/login_prd.txt"
    col_load, col_parse = st.columns([1, 1])
    with col_load:
        if st.button("Load sample PRD"):
            try:
                with open(sample_path, encoding="utf-8") as f:
                    st.session_state.requirements_text = f.read()
                st.rerun()
            except OSError:
                st.error(f"Could not load {sample_path}")
    with col_parse:
        parse_clicked = st.button("Parse Requirements", type="primary")

    if parse_clicked:
        text = _prd_payload()
        if not text.strip():
            st.warning("Enter requirements text first.")
        else:
            with st.spinner("Extracting structured requirements..."):
                try:
                    st.session_state.requirements = extract_requirements(text)
                    st.session_state.risk_results = []
                    st.session_state.state_model = {}
                    st.session_state.whitebox_sequences = []
                    st.session_state.coverage_items = []
                    st.session_state.coverage_with_strategy = []
                    st.session_state.testcases = []
                    _reset_data_editors("editor_coverage_items", "editor_strategy_tc")
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

    st.subheader("2. Risk Analysis")
    if st.button(
        "Generate Risk Analysis",
        disabled=not st.session_state.requirements,
    ):
        with st.spinner("Analyzing risks..."):
            try:
                st.session_state.risk_results = analyze_risks(
                    st.session_state.requirements
                )
                st.session_state.state_model = {}
                st.session_state.whitebox_sequences = []
                st.session_state.coverage_items = []
                st.session_state.coverage_with_strategy = []
                st.session_state.testcases = []
                _reset_data_editors("editor_coverage_items", "editor_strategy_tc")
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

    st.subheader("3. State Transition Model & Test Sequences (White-box)")
    st.caption(
        "State paths and transitions from this step can be merged into "
        "**Step 4 → Coverage Items** (auto on generate, or use Import from White-box)."
    )
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
        _render_state_model_graph(model)

        with st.expander("Edit states & transitions (table)", expanded=False):
            states_df = pd.DataFrame({"State": model.get("states", [])})
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
                    "event": st.column_config.TextColumn("Event / Trigger"),
                    "guard": st.column_config.TextColumn("Guard / Condition"),
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

    st.subheader("4. Black-box Test Design")

    st.markdown("**Coverage Items**")
    ci_col1, ci_col2 = st.columns(2)
    with ci_col1:
        gen_ci = st.button(
            "Generate Coverage Items",
            type="primary",
            disabled=not st.session_state.risk_results,
            key="btn_gen_coverage_items",
        )
    with ci_col2:
        import_wb = st.button(
            "Import from White-box",
            disabled=not _has_whitebox_artifacts(),
            key="btn_import_whitebox_ci",
        )

    if gen_ci:
        with st.spinner("Identifying coverage items..."):
            try:
                bb = generate_coverage_items(st.session_state.requirements)
                wb_count = 0
                if _has_whitebox_artifacts():
                    wb = _whitebox_coverage_items()
                    wb_count = len(wb)
                    merged = merge_coverage_items(bb, wb)
                else:
                    merged = bb
                st.session_state.coverage_items = merged
                st.session_state.coverage_with_strategy = []
                st.session_state.testcases = []
                st.session_state.oracles = []
                st.session_state.optimization_metrics = {}
                _reset_data_editors("editor_coverage_items", "editor_strategy_tc")
                if wb_count:
                    st.success(
                        f"Generated {len(bb)} black-box + {wb_count} white-box "
                        f"= {len(merged)} coverage item(s)."
                    )
                else:
                    st.success(
                        f"Generated {len(merged)} coverage item(s)."
                    )
            except Exception as exc:
                st.error(f"Coverage item generation failed: {exc}")

    if import_wb:
        with st.spinner("Importing white-box coverage items..."):
            try:
                wb = _whitebox_coverage_items()
                before = len(st.session_state.coverage_items)
                st.session_state.coverage_items = merge_coverage_items(
                    st.session_state.coverage_items, wb
                )
                added = len(st.session_state.coverage_items) - before
                _reset_data_editors("editor_coverage_items", "editor_strategy_tc")
                st.success(f"Imported {added} white-box coverage item(s).")
            except Exception as exc:
                st.error(f"White-box import failed: {exc}")

    edited_ci = st.data_editor(
        _records_to_df(st.session_state.coverage_items, COVERAGE_ITEM_COLUMNS),
        num_rows="dynamic",
        use_container_width=True,
        key="editor_coverage_items",
    )
    st.session_state.coverage_items = _df_to_records(edited_ci)

    st.markdown("**Strategies & Test Cases**")
    has_coverage = bool(st.session_state.coverage_items)

    if st.button(
        "Generate Strategies & Test Cases",
        type="primary",
        disabled=not has_coverage,
        key="btn_gen_strategy_tc",
    ):
        with st.spinner("Assigning strategies and generating test cases..."):
            try:
                strats = select_strategies(st.session_state.coverage_items)
                raw = generate_testcases(
                    st.session_state.requirements,
                    st.session_state.risk_results,
                    strats,
                    state_model=st.session_state.state_model or None,
                    whitebox_sequences=_normalize_whitebox_sequences(
                        st.session_state.whitebox_sequences
                    ) or None,
                )
                for tc in raw:
                    tc["steps"] = _steps_to_str(tc.get("steps", ""))
                    uid = _row_id(tc)
                    tc["coverage_id"] = uid
                    tc["tc_id"] = uid
                st.session_state.coverage_with_strategy = strats
                st.session_state.testcases = raw
                st.session_state.oracles = []
                st.session_state.optimization_metrics = {}
                _reset_data_editors("editor_strategy_tc")
                methods = {x["test_method"] for x in strats}
                st.success(
                    f"Generated {len(raw)} test case(s) · "
                    f"Techniques: {', '.join(sorted(methods))}"
                )
                if len(methods) < 3:
                    st.warning(
                        "Fewer than 3 techniques used. Edit test_method below."
                    )
            except Exception as exc:
                st.error(f"Strategy / test case generation failed: {exc}")

    if not has_coverage:
        st.info("Generate or add coverage items above first.")

    edited_stc = st.data_editor(
        _records_to_df(
            _merge_strategy_tc_rows(
                st.session_state.coverage_items,
                st.session_state.coverage_with_strategy,
                st.session_state.testcases,
            ),
            STRATEGY_TC_COLUMNS,
        ),
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "coverage_item": st.column_config.TextColumn(
                disabled=True,
                help="Synced from coverage items above",
            ),
            "test_method": st.column_config.SelectboxColumn(options=VALID_METHODS),
            "priority": st.column_config.SelectboxColumn(
                options=["High", "Medium", "Low"]
            ),
            "steps": st.column_config.TextColumn(help="Separate steps with |"),
        },
        key="editor_strategy_tc",
        disabled=not has_coverage,
    )
    if has_coverage:
        strats, tcs = _split_strategy_tc_rows(
            _df_to_records(edited_stc),
            st.session_state.coverage_items,
        )
        st.session_state.coverage_with_strategy = strats
        st.session_state.testcases = tcs

    if st.session_state.testcases:
        st.markdown("**Optimize Test Suite**")
        st.caption("Sort, filter or deduplicate test cases after generation.")

        opt_col1, opt_col2 = st.columns([2, 1])
        with opt_col1:
            opt_strategy = st.radio(
                "Optimization",
                [
                    "risk – Sort & filter by priority",
                    "coverage – Remove redundant cases",
                    "both – Minimize then prioritize",
                ],
                horizontal=True,
                key="opt_strategy",
                label_visibility="collapsed",
            )
        with opt_col2:
            min_prio = st.select_slider(
                "Min priority",
                options=["High", "Medium", "Low"],
                value="Low",
                key="opt_min_priority",
            )

        if st.button("Apply Optimization", key="btn_optimize_suite"):
            strategy_key = opt_strategy.split(" – ")[0]
            with st.spinner("Optimizing..."):
                try:
                    optimized, metrics = optimize_test_suite(
                        st.session_state.testcases,
                        strategy=strategy_key,
                        min_priority=min_prio,
                    )
                    ci_map = {
                        c["coverage_id"]: c
                        for c in st.session_state.coverage_items
                    }
                    for tc in optimized:
                        tc["steps"] = _steps_to_str(tc.get("steps", ""))
                    st.session_state.testcases = optimized
                    st.session_state.coverage_with_strategy = [
                        {
                            "coverage_id": tc["coverage_id"],
                            "coverage_item": ci_map.get(tc["coverage_id"], {}).get(
                                "coverage_item", ""
                            ),
                            "related_req": tc.get("req_id", ""),
                            "test_method": tc.get("test_method", ""),
                        }
                        for tc in optimized
                    ]
                    st.session_state.optimization_metrics = metrics
                    _reset_data_editors("editor_strategy_tc")
                    st.success(
                        f"{metrics['original_count']} → {metrics['optimized_count']} "
                        f"test cases (removed {metrics['removed_count']})."
                    )
                except Exception as exc:
                    st.error(f"Optimization failed: {exc}")

        if st.session_state.optimization_metrics:
            m = st.session_state.optimization_metrics
            mc1, mc2, mc3 = st.columns(3)
            mc1.metric("Count", m.get("optimized_count", 0))
            mc2.metric("Removed", m.get("removed_count", 0))
            mc3.metric("High priority", m.get("high_count", "—"))

    st.divider()

    st.subheader("5. Generate Pytest Files")

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
                    app_name="AutoTestDesign",
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

        app_slug = "generated"
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
    st.subheader("6. Test Oracle Generation (FR 5.0)")
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
            st.info("Parse requirements first (Step 1).")

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
    _export_section()


if __name__ == "__main__":
    main()
