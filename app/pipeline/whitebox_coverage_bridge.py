"""Bridge white-box artifacts (state model, sequences) into black-box coverage items."""


def _guess_related_req(text: str, requirements: list) -> str:
    if not requirements:
        return ""
    text_lower = text.lower()
    keywords = (
        "login", "password", "lock", "email", "auth", "fail", "attempt",
        "reset", "forgot", "session", "state", "transition",
    )
    for req in requirements:
        desc = str(req.get("description", "")).lower()
        if any(k in desc and k in text_lower for k in keywords):
            return req["requirement_id"]
    return requirements[0]["requirement_id"]


def coverage_items_from_whitebox(
    state_model: dict,
    sequences: list,
    requirements: list,
) -> list:
    """
    Map state transitions and test sequences to coverage items
    for merging into the black-box coverage table.
    """
    items = []
    idx = 1
    seen_transitions: set[tuple] = set()

    for seq in sequences or []:
        path = seq.get("path") or []
        if isinstance(path, str):
            path = [s.strip() for s in path.split("→") if s.strip()]
        events = seq.get("events") or []
        if isinstance(events, str):
            events = [s.strip() for s in events.split("→") if s.strip()]

        path_str = " → ".join(path)
        event_str = " → ".join(events) if events else ""
        criterion = seq.get("coverage_criterion", "sequence")
        desc = f"State path ({criterion}): {path_str}"
        if event_str:
            desc += f" | events: {event_str}"

        items.append({
            "coverage_id": f"WB-{idx:02d}",
            "coverage_item": desc,
            "related_req": _guess_related_req(desc, requirements),
            "source": "whitebox",
            "whitebox_path": path,
            "whitebox_events": events,
        })
        idx += 1

    for t in state_model.get("transitions", []) if state_model else []:
        key = (t.get("from", ""), t.get("to", ""), t.get("event", ""))
        if key in seen_transitions:
            continue
        seen_transitions.add(key)

        event = t.get("event", "")
        guard = t.get("guard", "")
        desc = f"Transition {t.get('from')} → {t.get('to')} on {event}"
        if guard:
            desc += f" [{guard}]"

        items.append({
            "coverage_id": f"WB-{idx:02d}",
            "coverage_item": desc,
            "related_req": _guess_related_req(desc, requirements),
            "source": "whitebox",
            "whitebox_from": t.get("from"),
            "whitebox_to": t.get("to"),
            "whitebox_event": event,
            "whitebox_guard": guard,
        })
        idx += 1

    return items


def merge_coverage_items(blackbox_items: list, whitebox_items: list) -> list:
    """Merge black-box and white-box coverage items; white-box IDs must not clash."""
    used_ids = {c.get("coverage_id") for c in blackbox_items}
    merged = [dict(c) for c in blackbox_items]

    for item in whitebox_items:
        entry = dict(item)
        cid = entry.get("coverage_id", "")
        while cid in used_ids:
            n = int(cid.split("-")[-1]) + 1 if "-" in cid else len(used_ids) + 1
            prefix = cid.rsplit("-", 1)[0] if "-" in cid else "WB"
            cid = f"{prefix}-{n:02d}"
            entry["coverage_id"] = cid
        used_ids.add(cid)
        merged.append(entry)

    return merged
