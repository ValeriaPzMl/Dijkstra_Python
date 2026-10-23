# Project 2 — Shortest Path with Bidirectional Dijkstra

A web application to build a directed, weighted graph visually and find the
shortest path between a **start** node and a **destination** node using
**bidirectional Dijkstra**.

- **Live version (Render):** https://dijkstra-python.onrender.com/
- **Backend:** Python + Flask ([`app.py`](app.py))
- **Algorithm:** [`dijkstra.py`](dijkstra.py) (standard library only: `heapq`, `itertools`)
- **Frontend:** HTML + JavaScript ([`index.html`](index.html), [`static/app.js`](static/app.js), [`static/style.css`](static/style.css)), drawing the graph with [Cytoscape.js](https://js.cytoscape.org/)

> The code identifiers in `dijkstra.py` are in Spanish (`Nodo` = node,
> `Arista` = edge, `Grafo` = graph, `peso` = weight, `inicio` = start,
> `fin` = end). This README keeps the original names and explains each one.

---

## 1. How `dijkstra.py` and `app.py` relate

`dijkstra.py` is the **base of the algorithm** used by the app. It was written
as a standalone module with its own classes (`Nodo`, `Arista`, `Grafo`) and
can still be run by itself.

The graphical part does not work with those classes directly: the browser
edits a lightweight JSON representation of the graph (nodes, roles, levels,
connections). When the user presses **SOLVE**, `app.py` **rebuilds that graph
as `Grafo`/`Nodo` objects** so it is compatible with the algorithm, calls
`resolver()`, and translates the result (list of `Nodo` + cost) back into
JSON so the interface can highlight the path. In other words, `app.py` is the
adapter between the graphical interface and the algorithm, and the
shortest-path logic itself lives only in `dijkstra.py`.

```
Browser (app.js)  ──JSON──▶  app.py (Flask)  ──Grafo / Nodo──▶  dijkstra.py
       ▲                         │                                   │
       └───── state + solution ◀─┴────────── (path, cost) ◀──────────┘
```

---

## 2. Dijkstra's algorithm

### 2.1 Standard Dijkstra

Dijkstra finds the shortest path from a source node to every other node in a
graph whose edge weights are **non-negative**.

1. Set the distance of the source to `0` and of every other node to `∞`.
2. Put the source in a **priority queue** (min-heap) ordered by distance.
3. Pop the node `u` with the smallest known distance. Since weights are
   non-negative, that distance is final: `u` is marked as visited.
4. For every edge `u → v` with weight `w`, if `dist[u] + w < dist[v]`, update
   `dist[v]`, store `u` as the parent of `v` and push `v` into the queue
   (this is called *relaxing* the edge).
5. Repeat until the queue is empty (or until the destination is popped).
6. Rebuild the path by following the parents from the destination back to
   the source.

With a binary heap its complexity is **O((V + E) log V)**. Its weakness is
that it grows like a "circle" around the source: it explores every node
closer than the destination, in every direction.

### 2.2 Bidirectional Dijkstra (the one used in this project)

Instead of a single search, **two Dijkstra searches run at the same time**:

| Search | Starts at | Follows | Uses |
|---|---|---|---|
| **Forward** (`f`) | start node | outgoing edges (`nodo.aristas`) | `dist_f`, `padre_f`, `pq_f`, `vis_f` |
| **Backward** (`b`) | destination node | incoming edges in reverse (`nodo.entrantes`) | `dist_b`, `padre_b`, `pq_b`, `vis_b` |

Because the graph is directed, the backward search walks the edges "against
the arrow": from a node it goes to the **origin** of each incoming edge. That
is why every `Nodo` keeps both lists, `aristas` and `entrantes`.

How it works:

1. Initialize `dist_f[start] = 0` and `dist_b[destination] = 0`; everything
   else is `∞`. `mejor` (best cost found) starts at `∞`.
2. On each iteration, expand the search whose queue has the **smaller**
   minimum distance (this keeps both "circles" balanced).
3. When relaxing an edge towards `vecino` (neighbor), also check
   `dist_actual + dist_otro[vecino]`: if the other search already reached
   that node, there is a complete path start → `vecino` → destination. If
   that total beats `mejor`, save it and remember `vecino` as the **meeting
   node** (`encuentro`).
4. **Stopping condition:** stop when
   `top(pq_f) + top(pq_b) >= mejor`. Any path not found yet would have to
   cost at least that sum, so it can no longer improve `mejor`.
5. Rebuild the path in two halves:
   - start → meeting node, following `padre_f` and reversing the list;
   - meeting node → destination, following `padre_b` (which already points
     towards the destination).

Each search only needs to cover roughly "half the distance", so the two
small circles usually explore far fewer nodes than the single big circle of
standard Dijkstra. The worst-case complexity is the same,
**O((V + E) log V)**, but in practice it is faster.

If there is no path, the queues empty out without the searches ever meeting
and the method returns `(None, inf)`. If start and destination are the same
node it returns `([start], 0)` immediately.

---

## 3. Data structures, classes, methods and attributes

### 3.1 `dijkstra.py` (the algorithm)

Only the elements used by the app are described.

#### `class Nodo` — a graph node

| Attribute | Type | Description |
|---|---|---|
| `nombre` | `str` | Node name (unique in the app). |
| `aristas` | `list[Arista]` | **Outgoing** edges. Used by the forward search. |
| `entrantes` | `list[Arista]` | **Incoming** edges. Used by the backward search. |

| Method | Description |
|---|---|
| `__init__(nombre)` | Creates the node with empty edge lists. |
| `__repr__()` | Text representation, e.g. `Nodo(A)`. |

#### `class Arista` — a directed, weighted edge

The app never creates it directly; it is created inside
`Grafo.agregar_arista`.

| Attribute | Type | Description |
|---|---|---|
| `origen` | `Nodo` | Node where the edge starts. |
| `destino` | `Nodo` | Node where the edge ends. |
| `peso` | `int`/`float` | Weight (cost). Must be `>= 0`. |

| Method | Description |
|---|---|
| `__init__(origen, destino, peso)` | Creates the edge; raises `ValueError` if the weight is negative (Dijkstra does not support it). |
| `__repr__()` | Text representation, e.g. `A -> B (4)`. |

#### `class Grafo` — the graph and the algorithm

| Attribute | Type | Description |
|---|---|---|
| `nodos` | `list[Nodo]` | Every node in the graph. |
| `inicio` | `Nodo` or `None` | Start node. |
| `fin` | `Nodo` or `None` | Destination node. |

| Method | Description |
|---|---|
| `agregar_nodo(nodo)` | Adds the node if it is not already in the graph and returns it. |
| `agregar_arista(origen, destino, peso)` | Adds both nodes if needed, creates the `Arista`, appends it to `origen.aristas` and to `destino.entrantes`, and returns it. |
| `set_inicio(nodo)` / `set_fin(nodo)` | Set the start / destination node; raise `ValueError` if the node is not in the graph. |
| `resolver()` | Checks that start and destination are set and returns `dijkstra_bidireccional(inicio, fin)` → `(path, cost)`. |
| `dijkstra_bidireccional(origen, destino)` | Runs the bidirectional search described in section 2.2. Returns `(list[Nodo], cost)` or `(None, inf)`. |
| `_expandir(pq, dist, padre, visitados, dist_otro, adelante, mejor, encuentro, contador)` | One step of one search: pops the closest node, marks it visited, relaxes its edges (outgoing if `adelante=True`, incoming otherwise) and updates `mejor`/`encuentro` when it touches the other search. Returns the new `(mejor, encuentro)`. |

#### Data structures inside `dijkstra_bidireccional`

| Name | Structure | Purpose |
|---|---|---|
| `dist_f`, `dist_b` | `dict[Nodo, float]` | Best known distance from the start / to the destination. |
| `padre_f`, `padre_b` | `dict[Nodo, Nodo or None]` | Previous node of each search, used to rebuild the path. |
| `vis_f`, `vis_b` | `set[Nodo]` | Nodes whose distance is already final. |
| `pq_f`, `pq_b` | `list` used as a min-heap (`heapq`) | Priority queues with tuples `(distance, counter, node)`. |
| `contador` | `itertools.count()` | Tie-breaker: if two distances are equal, the heap compares this number instead of comparing `Nodo` objects (which are not comparable). |
| `mejor` | `float` | Cost of the best complete path found so far. |
| `encuentro` | `Nodo` | Meeting node of that best path. |

### 3.2 `app.py` (Flask backend / adapter)

#### Graph state (JSON-friendly dictionaries)

Each browser session has its own graph, stored in memory:

| Structure | Description |
|---|---|
| `_GRAPH_STATES` | `dict[graph_id, state]`. All graphs, keyed by an id saved in the Flask session cookie. |
| `_STATE_LOCK` | `threading.RLock` that protects `_GRAPH_STATES` from concurrent requests. |
| `_MAX_NODES` | Limit of 40 nodes per graph. |
| **state** | `{"nodes": [...], "max_level": int, "solution": dict or None}` |
| **node** | `{"id": str, "name": str, "role": "" / "start" / "finish", "level": int, "edges": [...]}` — `level` is the column where the node is drawn (start = 0, destination = last). |
| **edge** | `{"to": node_id, "weight": number}` — stored in the source node. |
| **solution** | `{"reachable": True, "pathIds": [...], "pathNames": [...], "cost": number, "message": str}` or `{"reachable": False, "message": str}`. |

#### Helper functions

| Function | Description |
|---|---|
| `_new_node(name, role, level)` | Creates a node dictionary with a random 12-character id. |
| `_initial_state()` | New graph with `A` (start, level 0) and `B` (destination, level 2). |
| `_state()` | Returns the graph of the current session, creating it if needed. |
| `_state_response(state)` / `_error(message, status, state)` | Build the JSON responses (a copy of the state, plus an error message when applicable). |
| `_find_node(state, node_id)` | Looks up a node by id. |
| `_invalidate_solution(state)` | Clears the previous result whenever the graph changes. |
| `_normalise_levels(state)` | Keeps start at level 0, regular nodes at level ≥ 1 and the destination one level after the last regular node. |
| `_parse_weight(value)` | Validates that a weight is a finite number `>= 0`. |
| `_next_name(state)` | Next free name: `A`…`Z`, then `N1`, `N2`, … |
| `_reassign_endpoint_if_needed(state, role)` | If the start or destination is deleted, promotes another node so both always exist. |

#### HTTP endpoints

| Method & route | Description |
|---|---|
| `GET /` | Serves `index.html`. |
| `GET /api/state` | Returns the current graph. |
| `POST /api/nodes` | Adds a node. |
| `PATCH /api/nodes/<id>` | Renames a node or changes its role (`start`, `finish`, regular). |
| `DELETE /api/nodes/<id>` | Deletes a node and every edge pointing to it. |
| `POST /api/nodes/<id>/level` | Moves a regular node one level `left` or `right`. |
| `POST /api/nodes/<id>/edges` | Adds a connection `{to, weight}` (or updates its weight if it already exists). |
| `DELETE /api/nodes/<id>/edges/<to>` | Removes a connection. |
| `POST /api/solve` | Validates the graph, builds the `Grafo`, runs `resolver()` and stores the solution. |
| `GET /health` | Health check (`{"status": "ok"}`), used by Render. |

`solve()` is where the two parts meet: it creates one `Nodo` per node
dictionary (`node_objects`), adds them with `agregar_nodo`, creates every
connection with `agregar_arista`, sets the endpoints with `set_inicio` /
`set_fin`, calls `resolver()` and converts the resulting `Nodo` list back to
ids and names.

### 3.3 `static/app.js` (frontend)

- `state`: local copy of the graph returned by the server; every action sends
  a request and redraws with the new state.
- `api(path, method, body)`: sends requests to the backend and shows errors
  in a toast.
- `card(node)`: builds each node card (name, role, connections, form to add
  connections).
- `drawGraph()`: draws the graph with Cytoscape.js, placing each node in the
  column of its `level`; after solving, the path is drawn thick and the rest
  is faded.
- `panels()`: shows the level-move panel of the selected node and the
  result card (total cost and path).

---

## 4. How to create a graph in the interface

The page has three areas: the **node cards** (top), the **graph** (bottom)
and the **SOLVE** button (bottom right).

1. **Initial graph.** It starts with node `A` (**Start**, green border) and
   node `B` (**Destination**, red border).
2. **Add nodes.** Click the **`+`** card at the end of the row. Each new node
   gets the next free name (`C`, `D`, …). Up to 40 nodes.
3. **Rename a node.** Edit the text field of its card (max. 24 characters,
   names must be unique).
4. **Change start / destination.** In the dropdown of a regular node choose
   **Start** or **Destination**; the previous one becomes a regular node.
5. **Add a connection (directed edge).** At the bottom of the **source**
   node's card choose the target node, type the weight (number ≥ 0) and
   press **`+`**. The connection appears as a chip `Target · weight`. Adding
   the same connection again just updates its weight.
   For a two-way connection, add it from both cards.
6. **Remove a connection.** Click the **`×`** on its chip.
7. **Delete a node.** Click the **`×`** in the card header (only when there
   are more than 2 nodes). Its connections are deleted too.
8. **Reorder the drawing (optional).** Click a regular node in the graph
   and use **← Left / Right →** to move it to another column. This only
   changes how it is drawn, not the result.
9. **Solve.** Press **SOLVE**. The result card shows the **total cost** and
   the **path** (e.g. `A → C → D → B`), and the graph highlights the path.
   If there is no path, it shows *"No route found"*. Any later change to
   the graph clears the result.

---

## 5. How to run it

> **Running it locally is not required:** the app is deployed on Render and
> can be used directly at: https://dijkstra-python.onrender.com/

### Requirements

- Python 3.12 or newer
- The packages in [`requirements.txt`](requirements.txt) (Flask and Gunicorn)
- Internet connection in the browser (Cytoscape.js is loaded from a CDN)

### Steps

```bash
# 1. Get the code: clone the repository...
git clone https://github.com/ValeriaPzMl/Dijkstra_Python.git
cd Dijkstra_Python
#    ...or download the ZIP from GitHub (Code → Download ZIP),
#    unzip it and enter the extracted folder

# 2. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app
python app.py
```

Open **http://localhost:5000** in the browser.
`http://localhost:5000/health` should return `{"status":"ok"}`.

### Options

- **Different port:** `PORT=8000 python app.py`
- **Keep the session between restarts:** `SECRET_KEY=any-fixed-text python app.py`
  (otherwise a new key is generated each time and the browser gets a new
  empty graph).
- **Run it like on Render (Gunicorn):**
  ```bash
  gunicorn -w 1 -b 0.0.0.0:5000 app:app
  ```
  Use a **single worker** (`-w 1`): graphs are kept in memory, so with
  several workers each one would have a different copy.

### Run only the algorithm

`dijkstra.py` can also be run on its own (no dependencies). Its example
builds a **20 × 20 grid of 400 nodes** (`N0` … `N399`), where each node has a
directed edge to the right and one downward with weights from 1 to 9, and
finds the shortest path from the top-left corner (`N0`) to the bottom-right
corner (`N399`):

```bash
python dijkstra.py
```

Output:

```
Nodos en el grafo: 400
Camino (39 nodos): N0 -> N1 -> N2 -> N3 -> N4 -> N24 -> N44 -> ... -> N377 -> N397 -> N398 -> N399
Costo total: 106
```

(`Nodos en el grafo` = nodes in the graph, `Camino` = path,
`Costo total` = total cost. The full path is printed; it is shortened here.)

---

## 6. Project structure

```
Dijkstra_Python/
├── app.py            # Flask backend: graph state, API, adapter to dijkstra.py
├── dijkstra.py       # Nodo, Arista, Grafo + bidirectional Dijkstra
├── index.html        # Page layout
├── static/
│   ├── app.js        # Interface logic and drawing (Cytoscape.js)
│   └── style.css     # Styles
├── requirements.txt  # Dependencies (pip)
├── Pipfile           # Dependencies (pipenv)
└── Reporte_Latex/    # LaTeX report and screenshots
```
