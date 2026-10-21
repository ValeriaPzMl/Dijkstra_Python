"""Minimal Flask UI around the original, unchanged dijistra.py implementation."""

from copy import deepcopy
from math import isfinite
import os
import secrets
import threading
import uuid

from flask import Flask, jsonify, request, send_from_directory, session

# The implementation is imported as supplied. Do not modify dijistra.py.
from dijistra import Grafo, Nodo

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("RENDER", "") == "true",
    MAX_CONTENT_LENGTH=64 * 1024,
)

# Intentionally in-memory: use one Gunicorn worker for this no-database prototype.
_GRAPH_STATES = {}
_STATE_LOCK = threading.RLock()
_MAX_NODES = 40


def _new_node(name, role="", level=1):
    return {
        "id": uuid.uuid4().hex[:12],
        "name": name,
        "role": role,
        "level": level,
        "edges": [],
    }


def _initial_state():
    return {
        "nodes": [
            _new_node("A", "start", 0),
            _new_node("B", "finish", 2),
        ],
        "max_level": 2,
        "solution": None,
    }


def _state():
    graph_id = session.get("graph_id")
    if not graph_id:
        graph_id = uuid.uuid4().hex
        session["graph_id"] = graph_id
    with _STATE_LOCK:
        if graph_id not in _GRAPH_STATES:
            _GRAPH_STATES[graph_id] = _initial_state()
        return _GRAPH_STATES[graph_id]


def _state_response(state=None):
    return jsonify(state=deepcopy(state if state is not None else _state()))


def _error(message, status=400, state=None):
    current = state if state is not None else _state()
    return jsonify(error=message, state=deepcopy(current)), status


def _find_node(state, node_id):
    return next((node for node in state["nodes"] if node["id"] == node_id), None)


def _invalidate_solution(state):
    state["solution"] = None


def _normalise_levels(state):
    """Keep start at level 0, finish at the final level, and ordinary nodes between."""
    start = next((node for node in state["nodes"] if node["role"] == "start"), None)
    finish = next((node for node in state["nodes"] if node["role"] == "finish"), None)

    ordinary = []
    for node in state["nodes"]:
        if node is start:
            node["level"] = 0
        elif node is finish:
            continue
        else:
            try:
                node["level"] = max(1, int(node.get("level", 1)))
            except (TypeError, ValueError):
                node["level"] = 1
            ordinary.append(node)

    state["max_level"] = max(2, max((node["level"] for node in ordinary), default=1) + 1)
    if finish:
        finish["level"] = state["max_level"]


def _parse_weight(value):
    if value is None or isinstance(value, bool):
        raise ValueError("Enter a numeric weight greater than or equal to zero.")
    try:
        weight = float(value)
    except (TypeError, ValueError):
        raise ValueError("The weight must be a valid number.")
    if not isfinite(weight) or weight < 0:
        raise ValueError("Dijkstra requires finite, non-negative weights.")
    return int(weight) if weight.is_integer() else weight


def _next_name(state):
    used = {node["name"].strip().casefold() for node in state["nodes"]}
    for index in range(26):
        candidate = chr(ord("A") + index)
        if candidate.casefold() not in used:
            return candidate
    index = 1
    while f"N{index}".casefold() in used:
        index += 1
    return f"N{index}"


def _reassign_endpoint_if_needed(state, deleted_role):
    """Deleting an endpoint promotes a remaining node so endpoints always exist."""
    if deleted_role == "start":
        candidates = [node for node in state["nodes"] if node["role"] != "finish"]
        if candidates:
            candidate = min(candidates, key=lambda item: (item.get("level", 1), state["nodes"].index(item)))
            candidate["role"] = "start"
            candidate["level"] = 0
    elif deleted_role == "finish":
        candidates = [node for node in state["nodes"] if node["role"] != "start"]
        if candidates:
            candidate = max(candidates, key=lambda item: (item.get("level", 1), state["nodes"].index(item)))
            candidate["role"] = "finish"


@app.get("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


@app.get("/api/state")
def get_state():
    with _STATE_LOCK:
        state = _state()
        _normalise_levels(state)
        return _state_response(state)


@app.post("/api/nodes")
def add_node():
    state = _state()
    with _STATE_LOCK:
        if len(state["nodes"]) >= _MAX_NODES:
            return _error(f"This version supports up to {_MAX_NODES} nodes.", 400, state)
        node = _new_node(_next_name(state), level=1)
        state["nodes"].append(node)
        _normalise_levels(state)
        _invalidate_solution(state)
        return _state_response(state)


@app.patch("/api/nodes/<node_id>")
def update_node(node_id):
    state = _state()
    payload = request.get_json(silent=True) or {}
    with _STATE_LOCK:
        node = _find_node(state, node_id)
        if node is None:
            return _error("Node not found.", 404, state)

        if "name" in payload:
            name = str(payload["name"]).strip()
            if len(name) > 24:
                return _error("Node names can contain at most 24 characters.", 400, state)
            if name and any(
                other["id"] != node_id and other["name"].strip().casefold() == name.casefold()
                for other in state["nodes"]
            ):
                return _error("Each node must have a unique name.", 400, state)
            node["name"] = name

        if "role" in payload:
            role = payload["role"]
            if role not in ("", "start", "finish"):
                return _error("Invalid node role.", 400, state)
            if role == "" and node["role"] in ("start", "finish"):
                return _error("The graph must always have a start and a destination. Assign that role to another node instead.", 400, state)
            if node["role"] in ("start", "finish") and role not in ("", node["role"]):
                return _error("Assign Start or Destination to a regular node instead of switching endpoint roles directly.", 400, state)

            if role and role != node["role"]:
                # If this node currently holds an endpoint role, demote it first.
                if node["role"] == "start":
                    node["role"] = ""
                    node["level"] = 1
                elif node["role"] == "finish":
                    node["role"] = ""
                    node["level"] = max(1, state.get("max_level", 2) - 1)

                # Move any existing endpoint of the selected role into the middle.
                for other in state["nodes"]:
                    if other["id"] != node_id and other["role"] == role:
                        other["role"] = ""
                        other["level"] = 1 if role == "start" else max(1, state.get("max_level", 2) - 1)

                node["role"] = role
                node["level"] = 0 if role == "start" else state.get("max_level", 2)
            elif role == node["role"]:
                node["level"] = 0 if role == "start" else state.get("max_level", 2) if role == "finish" else node.get("level", 1)
            else:
                node["role"] = role

        _normalise_levels(state)
        _invalidate_solution(state)
        return _state_response(state)


@app.delete("/api/nodes/<node_id>")
def delete_node(node_id):
    state = _state()
    with _STATE_LOCK:
        node = _find_node(state, node_id)
        if node is None:
            return _error("Node not found.", 404, state)
        if len(state["nodes"]) <= 2:
            return _error("The graph must retain at least two nodes.", 400, state)

        deleted_role = node["role"]
        state["nodes"] = [item for item in state["nodes"] if item["id"] != node_id]
        for item in state["nodes"]:
            item["edges"] = [edge for edge in item["edges"] if edge["to"] != node_id]
        _reassign_endpoint_if_needed(state, deleted_role)
        _normalise_levels(state)
        _invalidate_solution(state)
        return _state_response(state)


@app.post("/api/nodes/<node_id>/level")
def move_node_level(node_id):
    state = _state()
    payload = request.get_json(silent=True) or {}
    direction = payload.get("direction")
    with _STATE_LOCK:
        node = _find_node(state, node_id)
        if node is None:
            return _error("Node not found.", 404, state)
        if node["role"] in ("start", "finish"):
            return _error("The start and destination stay at the outermost levels.", 400, state)
        if direction not in ("left", "right"):
            return _error("Choose left or right to move a node.", 400, state)

        if direction == "left":
            node["level"] = max(1, int(node.get("level", 1)) - 1)
        else:
            # If the node reaches the old final level, normalisation moves the
            # destination one level further right to preserve the endpoint rule.
            node["level"] = int(node.get("level", 1)) + 1
        _normalise_levels(state)
        _invalidate_solution(state)
        return _state_response(state)


@app.post("/api/nodes/<node_id>/edges")
def add_edge(node_id):
    state = _state()
    payload = request.get_json(silent=True) or {}
    with _STATE_LOCK:
        source = _find_node(state, node_id)
        target_id = str(payload.get("to", ""))
        target = _find_node(state, target_id)
        if source is None or target is None:
            return _error("Choose an existing source and destination node.", 400, state)
        if source["id"] == target["id"]:
            return _error("Connect a node to a different node.", 400, state)
        try:
            weight = _parse_weight(payload.get("weight"))
        except ValueError as exc:
            return _error(str(exc), 400, state)

        existing = next((edge for edge in source["edges"] if edge["to"] == target_id), None)
        if existing:
            existing["weight"] = weight
        else:
            source["edges"].append({"to": target_id, "weight": weight})
        _invalidate_solution(state)
        return _state_response(state)


@app.delete("/api/nodes/<node_id>/edges/<target_id>")
def delete_edge(node_id, target_id):
    state = _state()
    with _STATE_LOCK:
        source = _find_node(state, node_id)
        if source is None:
            return _error("Node not found.", 404, state)
        source["edges"] = [edge for edge in source["edges"] if edge["to"] != target_id]
        _invalidate_solution(state)
        return _state_response(state)


@app.post("/api/solve")
def solve():
    state = _state()
    with _STATE_LOCK:
        nodes = state["nodes"]
        if len(nodes) < 2:
            return _error("Add at least two nodes.", 400, state)
        if any(not node["name"].strip() for node in nodes):
            return _error("Complete every node name before solving.", 400, state)
        names = [node["name"].strip().casefold() for node in nodes]
        if len(names) != len(set(names)):
            return _error("Each node must have a unique name.", 400, state)

        starts = [node for node in nodes if node["role"] == "start"]
        finishes = [node for node in nodes if node["role"] == "finish"]
        if len(starts) != 1 or len(finishes) != 1:
            return _error("Choose exactly one start node and one destination node.", 400, state)

        try:
            # The algorithm graph is instantiated only on SOLVE. The original
            # dijistra.py implementation is imported and called unchanged.
            graph = Grafo()
            node_objects = {node["id"]: Nodo(node["name"].strip()) for node in nodes}
            for node in nodes:
                graph.agregar_nodo(node_objects[node["id"]])
            for node in nodes:
                for edge in node["edges"]:
                    destination = _find_node(state, edge["to"])
                    if destination is None:
                        return _error("A connection points to a node that no longer exists.", 400, state)
                    graph.agregar_arista(
                        node_objects[node["id"]],
                        node_objects[destination["id"]],
                        _parse_weight(edge["weight"]),
                    )
            graph.set_inicio(node_objects[starts[0]["id"]])
            graph.set_fin(node_objects[finishes[0]["id"]])
            path, cost = graph.resolver()
        except (ValueError, KeyError) as exc:
            return _error(str(exc), 400, state)

        if path is None or not isfinite(cost):
            state["solution"] = {
                "reachable": False,
                "message": "No path exists between the start and destination.",
            }
        else:
            id_by_name = {node["name"].strip(): node["id"] for node in nodes}
            path_names = [item.nombre for item in path]
            state["solution"] = {
                "reachable": True,
                "pathIds": [id_by_name[name] for name in path_names],
                "pathNames": path_names,
                "cost": cost,
                "message": "Shortest path found.",
            }
        return _state_response(state)


@app.get("/health")
def health():
    return jsonify(status="ok")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
