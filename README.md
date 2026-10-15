# Project 2 — Bidirectional Dijkstra

A Python implementation of **bidirectional Dijkstra** that finds the shortest path between two nodes of a directed graph with non-negative weights. All the code lives in [`dijistra.py`](dijistra.py). It uses no external libraries, only `heapq` and `itertools` from the standard library.

> The code identifiers are in Spanish (`Nodo` = node, `Arista` = edge, `Grafo` = graph, `peso` = weight, etc.). This README keeps the original names and explains each one.

---

## 1. How to use it

### Requirements
- Python 3.8 or newer (tested with Python 3.14).
- No dependencies to install.

### Run the included example

```bash
# (optional) activate the virtual environment
source venv/bin/activate

python dijistra.py
```

The example builds a **10 × 10 grid** of nodes (`N0` … `N99`). Each node has one edge to the right and one edge downward, with weights between 1 and 9. The program finds the shortest path from the top-left corner (`N0`) to the bottom-right corner (`N99`).

Expected output:

```
[Nodo(N0), Nodo(N10), Nodo(N11), Nodo(N12), Nodo(N22), Nodo(N32), Nodo(N33), Nodo(N34), Nodo(N35), Nodo(N45), Nodo(N55), Nodo(N56), Nodo(N57), Nodo(N58), Nodo(N68), Nodo(N78), Nodo(N79), Nodo(N89), Nodo(N99)]
51
```

The first line is the list of nodes on the path and the second line is its total cost.

### Use it with your own graph

```python
from dijistra import Nodo, Grafo

g = Grafo()
a, b, c, d = Nodo("A"), Nodo("B"), Nodo("C"), Nodo("D")

g.agregar_arista(a, b, 4)
g.agregar_arista(a, c, 1)
g.agregar_arista(c, b, 2)
g.agregar_arista(b, d, 5)

g.set_inicio(a)
g.set_fin(d)

camino, costo = g.resolver()
print(camino)  # [Nodo(A), Nodo(C), Nodo(B), Nodo(D)]
print(costo)   # 8
```

Notes:
- Edges are **directed**. `agregar_arista(a, b, 4)` lets you go from `A` to `B` but not from `B` to `A`. For a two-way connection, add both edges.
- Nodes are added to the graph automatically when an edge that uses them is created.
- If no path exists, `resolver()` returns `(None, inf)`.
- You can also call `g.dijkstra_bidireccional(origen, destino)` directly, without setting a start and end node first.

---

## 2. Dijkstra's algorithm explained

### Classic Dijkstra

Dijkstra's algorithm finds the lowest-cost path from a source node to the other nodes of a graph whose edge weights are **non-negative**.

1. Give the source a distance of `0` and every other node a distance of `∞`.
2. Push the source into a **priority queue** (min-heap) ordered by distance.
3. While the queue is not empty:
   - Pop the node with the smallest known distance. That distance is now final, so the node is marked as **visited**.
   - For each neighbor, compute `current_distance + edge_weight`. If that is smaller than the neighbor's current distance, update it (this is called **relaxing** the edge), store the current node as the neighbor's **parent**, and push the neighbor into the queue.
4. Rebuild the path by following the parents from the destination back to the source.

This works because, with no negative weights, once a node is popped with the smallest distance, no later path can reach it more cheaply. That is why the `Arista` class rejects negative weights.

**Complexity:** `O((V + E) log V)` with a binary heap, where `V` is the number of nodes and `E` the number of edges.

### Bidirectional version (what this project implements)

Instead of a single search from the start node, **two Dijkstra searches run at the same time**:

- **Forward search:** starts at the start node and follows edges in their normal direction (`nodo.aristas`).
- **Backward search:** starts at the end node and follows edges in reverse (`nodo.entrantes`).

On each iteration, the algorithm expands whichever search has the smaller distance at the top of its queue, so both searches advance in a balanced way.

Whenever one search relaxes an edge into a neighbor that the other search has already reached, a complete path exists with cost:

```
forward_distance(neighbor) + backward_distance(neighbor)
```

If that cost is lower than the best found so far (`mejor`), it is saved along with the node where the two searches meet (`encuentro`).

**Stopping condition:** the loop ends when

```
top_of_forward_queue + top_of_backward_queue >= mejor
```

because any path not yet discovered would cost at least that sum, so it can no longer improve the result.

**Path reconstruction:**
1. From `encuentro`, follow `padre_f` back to the start node and reverse the list. This gives the `start → meeting point` half.
2. From `encuentro`, follow `padre_b`, which already points toward the end node. This gives the `meeting point → end` half.

**Advantage:** each search only has to cover roughly half the distance, so in practice it visits far fewer nodes than regular Dijkstra, especially on large graphs.

---

## 3. Data structures, classes, methods and attributes

### Data structures used

| Structure | Where it is used | Purpose |
|---|---|---|
| **List** (`list`) | `Grafo.nodos`, `Nodo.aristas`, `Nodo.entrantes`, the resulting path | Stores the graph's nodes, the adjacency lists (outgoing and incoming) and the final path. |
| **Adjacency list** | `Nodo.aristas` / `Nodo.entrantes` | The graph representation: each node keeps the edges that leave it and the edges that arrive at it. Incoming edges let the backward search walk the graph in reverse. |
| **Priority queue / min-heap** (`heapq`) | `pq_f`, `pq_b` | Retrieves the node with the smallest pending distance for each search in `O(log n)`. Each entry is a tuple `(distance, counter, node)`. |
| **Dictionary** (`dict`) | `dist_f`, `dist_b`, `padre_f`, `padre_b` | The shortest known distance to each node and the previous node on the path, for each direction. |
| **Set** (`set`) | `vis_f`, `vis_b` | Checks in `O(1)` whether a node was already visited (its distance is final) so it is not processed twice. |
| **Counter** (`itertools.count`) | `contador` | Produces a unique, increasing number for each heap entry. It breaks ties when two entries have the same distance, so Python never tries to compare two `Nodo` objects (which are not comparable). |

### `Nodo` class (node)

Represents a vertex of the graph.

| Attribute | Type | Description |
|---|---|---|
| `nombre` | `str` | The node's identifier (for example `"N0"`). |
| `aristas` | `list[Arista]` | Edges that **leave** this node. Used by the forward search. |
| `entrantes` | `list[Arista]` | Edges that **arrive** at this node. Used by the backward search. |

| Method | Description |
|---|---|
| `__init__(nombre)` | Creates the node with its name and empty edge lists. |
| `__repr__()` | Returns `Nodo(name)` so the node prints in a readable way. |

### `Arista` class (edge)

Represents a weighted, directed connection between two nodes.

| Attribute | Type | Description |
|---|---|---|
| `origen` | `Nodo` | The node the edge leaves from. |
| `destino` | `Nodo` | The node the edge arrives at. |
| `peso` | `int` / `float` | The cost of traversing the edge. Must be ≥ 0. |

| Method | Description |
|---|---|
| `__init__(origen, destino, peso)` | Creates the edge. Raises `ValueError` if the weight is negative, because Dijkstra does not work correctly with negative weights. |
| `__repr__()` | Returns the text `origin -> destination (weight)`. |

### `Grafo` class (graph)

Holds the nodes, the start and end nodes, and the search algorithm.

| Attribute | Type | Description |
|---|---|---|
| `nodos` | `list[Nodo]` | All nodes in the graph. |
| `inicio` | `Nodo` or `None` | Start node used by `resolver()`. |
| `fin` | `Nodo` or `None` | End node used by `resolver()`. |

| Method | Description |
|---|---|
| `__init__()` | Creates an empty graph with no start or end node. |
| `agregar_nodo(nodo)` | Adds the node if it is not in the graph yet, and returns it. |
| `agregar_arista(origen, destino, peso)` | Adds both nodes if needed, creates the `Arista`, appends it to `origen.aristas` and `destino.entrantes`, and returns it. |
| `set_inicio(nodo)` | Sets the start node. Raises `ValueError` if the node is not in the graph. |
| `set_fin(nodo)` | Sets the end node. Raises `ValueError` if the node is not in the graph. |
| `resolver()` | Checks that the start and end nodes are set and runs `dijkstra_bidireccional(inicio, fin)`. Returns `(path, cost)`. |
| `dijkstra_bidireccional(origen, destino)` | The main algorithm. Initializes the structures for both searches, alternates between them by calling `_expandir` until the stopping condition holds, and rebuilds the path. Returns `(list_of_nodes, cost)`, or `(None, inf)` if there is no path. If `origen` and `destino` are the same node, it returns `([origen], 0)`. |
| `_expandir(pq, dist, padre, visitados, dist_otro, adelante, mejor, encuentro, contador)` | Private helper that performs **one step** of one of the two searches. It pops the closest node from the heap, marks it as visited, and relaxes its edges (outgoing if `adelante=True`, incoming if `False`). It also checks whether any neighbor was already reached by the other search, to update `mejor` and `encuentro`. Returns the updated `(mejor, encuentro)`. |

#### Internal variables of `dijkstra_bidireccional`

| Variable | Description |
|---|---|
| `dist_f`, `dist_b` | Shortest known distance from the start node (forward) and to the end node (backward). |
| `padre_f`, `padre_b` | Previous node in each search, used to rebuild the path. |
| `vis_f`, `vis_b` | Nodes already processed in each direction. |
| `pq_f`, `pq_b` | Priority queue of each search. |
| `mejor` | Cost of the best complete path found so far. |
| `encuentro` | The node where the two searches meet on the best path. |
| `contador` | Tie-breaker for the heap tuples. |

---

## 4. Project structure

```
Proyecto2_dijistra/
├── dijistra.py   # Nodo, Arista and Grafo classes plus a usage example
├── venv/         # Virtual environment (optional)
└── README.md
```
