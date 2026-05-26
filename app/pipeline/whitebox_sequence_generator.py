from collections import deque

VALID_COVERAGE_CRITERIA = [
    "all_states",
    "all_transitions",
]


def _build_adjacency(model: dict) -> dict[str, list[dict]]:
    """Build adjacency list from state transition model."""
    adj = {s: [] for s in model["states"]}
    for i, t in enumerate(model["transitions"]):
        adj.setdefault(t["from"], []).append({
            "idx": i,
            "to": t["to"],
            "event": t.get("event", ""),
            "guard": t.get("guard"),
        })
    return adj


def _bfs_shortest_path(adj: dict, start: str, targets: set[str]) -> list[dict] | None:
    """BFS to find shortest path from start to any target state."""
    if start in targets:
        return []
    queue = deque([(start, [])])
    visited = {start}
    while queue:
        current, path = queue.popleft()
        for edge in adj.get(current, []):
            if edge["to"] not in visited:
                new_path = path + [edge]
                if edge["to"] in targets:
                    return new_path
                visited.add(edge["to"])
                queue.append((edge["to"], new_path))
    return None


def _cover_all_states(model: dict, adj: dict) -> list[dict]:
    """Greedy BFS-based path that visits all states."""
    unvisited = set(model["states"])
    current = model["initial_state"]
    path = []

    if current in unvisited:
        unvisited.remove(current)

    while unvisited:
        segment = _bfs_shortest_path(adj, current, unvisited)
        if segment is None:
            break
        path.extend(segment)
        current = segment[-1]["to"]
        if current in unvisited:
            unvisited.remove(current)

    return path


def _cover_all_transitions(model: dict, adj: dict) -> list[dict]:
    """Greedy Eulerian-like path that traverses every transition."""
    uncovered = set(range(len(model["transitions"])))
    current = model["initial_state"]
    path = []

    while uncovered:
        # Prefer an uncovered edge from current state
        best = None
        for edge in adj.get(current, []):
            if edge["idx"] in uncovered:
                best = edge
                break

        if best is None:
            # Find shortest path to a state with uncovered outgoing edges
            states_with_uncovered = {
                model["transitions"][i]["from"]
                for i in uncovered
            }
            segment = _bfs_shortest_path(adj, current, states_with_uncovered)
            if segment is None:
                break
            path.extend(segment)
            current = segment[-1]["to"]
            continue

        path.append(best)
        uncovered.discard(best["idx"])
        current = best["to"]

    return path


def generate_sequences(model: dict, criterion: str) -> list[dict]:
    """
    Generates optimal test sequences from a state transition model
    based on the selected coverage criterion.
    """
    if criterion not in VALID_COVERAGE_CRITERIA:
        criterion = "all_states"

    adj = _build_adjacency(model)

    if criterion == "all_states":
        edges = _cover_all_states(model, adj)
    else:
        edges = _cover_all_transitions(model, adj)

    if not edges:
        return []

    covered_states = set()
    covered_transitions = set()

    steps = [model["initial_state"]]
    events = []

    for edge in edges:
        covered_states.add(edge.get("from", steps[-1]))
        steps.append(edge["to"])
        covered_states.add(edge["to"])
        covered_transitions.add(edge["idx"])
        events.append(edge["event"])

    return [{
        "sequence_id": "WS-01",
        "coverage_criterion": criterion,
        "path": steps,
        "events": events,
        "covered_states": len(covered_states),
        "covered_transitions": len(covered_transitions),
    }]
