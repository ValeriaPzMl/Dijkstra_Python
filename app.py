"""Minimal Flask UI around the untouched dijistra.py implementation."""

from copy import deepcopy
from math import isfinite
import os
import secrets
import threading
import uuid

from flask import Flask, jsonify, request, send_from_directory, session

# Import the original implementation; do not change the algorithm in dijistra.py.
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

# This intentionally stays in process memory to keep the project database-free.
# Use one Gunicorn worker on Render so a browser session always reaches this state.
_GRAPH_STATES = {}
_STATE_LOCK = threading.RLock()
_MAX_NODES = 40


def _new_node(name, role=""):
    return {"id": uuid.uuid4().hex[:12], "name": name, "role": role, "edges": []}


def _initial_state():
    return {
        "nodes": [
            _new_node("A", "start"),
            _new_node("B", "finish"),
        ],
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


def _parse_weight(value):
    if value is None or isinstance(value, bool):
        raise ValueError("Indica un peso numérico mayor o igual a cero.")
    try:
        weight = float(value)
    except (TypeError, ValueError):
        raise ValueError("El peso debe ser un número válido.")
    if not isfinite(weight) or weight < 0:
        raise ValueError("Dijkstra requiere pesos finitos mayores o iguales a cero.")
    return int(weight) if weight.is_integer() else weight


def _next_name(state):
    index = len(state["nodes"])
    if index < 26:
        return chr(ord("A") + index)
    return f"N{index + 1}"


@app.get("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


@app.get("/api/state")
def get_state():
    with _STATE_LOCK:
        return _state_response(_state())


@app.post("/api/nodes")
def add_node():
    state = _state()
    with _STATE_LOCK:
        if len(state["nodes"]) >= _MAX_NODES:
            return _error(f"El límite de esta versión es de {_MAX_NODES} nodos.", 400, state)
        node = _new_node(_next_name(state))
        state["nodes"].append(node)
        _invalidate_solution(state)
        return _state_response(state)


@app.patch("/api/nodes/<node_id>")
def update_node(node_id):
    state = _state()
    payload = request.get_json(silent=True) or {}
    with _STATE_LOCK:
        node = _find_node(state, node_id)
        if node is None:
            return _error("No se encontró ese nodo.", 404, state)

        if "name" in payload:
            name = str(payload["name"]).strip()
            if len(name) > 24:
                return _error("El nombre admite hasta 24 caracteres.", 400, state)
            if name and any(
                other["id"] != node_id and other["name"].strip().casefold() == name.casefold()
                for other in state["nodes"]
            ):
                return _error("Cada nodo debe tener un nombre único.", 400, state)
            node["name"] = name

        if "role" in payload:
            role = payload["role"]
            if role not in ("", "start", "finish"):
                return _error("El tipo de nodo no es válido.", 400, state)
            if role:
                for other in state["nodes"]:
                    if other["id"] != node_id and other["role"] == role:
                        other["role"] = ""
            node["role"] = role

        _invalidate_solution(state)
        return _state_response(state)


@app.delete("/api/nodes/<node_id>")
def delete_node(node_id):
    state = _state()
    with _STATE_LOCK:
        node = _find_node(state, node_id)
        if node is None:
            return _error("No se encontró ese nodo.", 404, state)
        if len(state["nodes"]) <= 2:
            return _error("El grafo debe conservar al menos dos nodos.", 400, state)

        state["nodes"] = [item for item in state["nodes"] if item["id"] != node_id]
        for item in state["nodes"]:
            item["edges"] = [edge for edge in item["edges"] if edge["to"] != node_id]
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
            return _error("Selecciona un nodo de origen y uno de destino que existan.", 400, state)
        if source["id"] == target["id"]:
            return _error("En esta interfaz, conecta un nodo con otro nodo distinto.", 400, state)
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
            return _error("No se encontró el nodo de origen.", 404, state)
        source["edges"] = [edge for edge in source["edges"] if edge["to"] != target_id]
        _invalidate_solution(state)
        return _state_response(state)


@app.post("/api/solve")
def solve():
    state = _state()
    with _STATE_LOCK:
        nodes = state["nodes"]
        if len(nodes) < 2:
            return _error("Añade al menos dos nodos.", 400, state)
        if any(not node["name"].strip() for node in nodes):
            return _error("Completa el nombre de todos los nodos antes de resolver.", 400, state)
        names = [node["name"].strip().casefold() for node in nodes]
        if len(names) != len(set(names)):
            return _error("Cada nodo debe tener un nombre único.", 400, state)

        starts = [node for node in nodes if node["role"] == "start"]
        finishes = [node for node in nodes if node["role"] == "finish"]
        if len(starts) != 1 or len(finishes) != 1:
            return _error("Selecciona exactamente un nodo de inicio y uno de destino.", 400, state)

        try:
            # The graph is instantiated ONLY when SOLVE is pressed. The algorithm
            # module itself is imported as-is and remains unchanged.
            graph = Grafo()
            node_objects = {node["id"]: Nodo(node["name"].strip()) for node in nodes}
            for node in nodes:
                graph.agregar_nodo(node_objects[node["id"]])
            for node in nodes:
                for edge in node["edges"]:
                    destination = _find_node(state, edge["to"])
                    if destination is None:
                        return _error("Hay una conexión cuyo nodo de destino ya no existe.", 400, state)
                    weight = _parse_weight(edge["weight"])
                    graph.agregar_arista(
                        node_objects[node["id"]],
                        node_objects[destination["id"]],
                        weight,
                    )
            graph.set_inicio(node_objects[starts[0]["id"]])
            graph.set_fin(node_objects[finishes[0]["id"]])
            path, cost = graph.resolver()
        except (ValueError, KeyError) as exc:
            return _error(str(exc), 400, state)

        if path is None or not isfinite(cost):
            state["solution"] = {
                "reachable": False,
                "message": "No existe una ruta entre el inicio y el destino.",
            }
        else:
            id_by_name = {node["name"].strip(): node["id"] for node in nodes}
            path_names = [item.nombre for item in path]
            state["solution"] = {
                "reachable": True,
                "pathIds": [id_by_name[name] for name in path_names],
                "pathNames": path_names,
                "cost": cost,
                "message": "Ruta mínima encontrada.",
            }
        return _state_response(state)


@app.get("/health")
def health():
    return jsonify(status="ok")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
