import heapq
import itertools

class Nodo:
    def __init__(self, nombre):
        self.nombre = nombre
        self.aristas = []   # aristas que salen de este nodo
        self.entrantes = []

    def __repr__(self):
        return f"Nodo({self.nombre})"
    
class Arista:
    def __init__(self, origen, destino, peso):
        if peso < 0:
            raise ValueError("Dijkstra no admite pesos negativos")
        self.origen = origen      # objeto Nodo
        self.destino = destino    # objeto Nodo
        self.peso = peso

    def __repr__(self):
        return f"{self.origen.nombre} -> {self.destino.nombre} ({self.peso})"
    

class Grafo:
    def __init__(self):
        self.nodos = []      # lista de objetos Nodo
        self.inicio = None   # objeto Nodo
        self.fin = None      # objeto Nodo

    def agregar_nodo(self, nodo):
        if nodo not in self.nodos:
            self.nodos.append(nodo)
        return nodo

    def agregar_arista(self, origen, destino, peso):
        self.agregar_nodo(origen)
        self.agregar_nodo(destino)
        arista = Arista(origen, destino, peso)
        origen.aristas.append(arista)
        destino.entrantes.append(arista) 
        return arista

    def set_inicio(self, nodo):
        if nodo not in self.nodos:
            raise ValueError(f"{nodo} no está en el grafo")
        self.inicio = nodo

    def set_fin(self, nodo):
        if nodo not in self.nodos:
            raise ValueError(f"{nodo} no está en el grafo")
        self.fin = nodo

    def dijkstra_bidireccional(self, origen, destino, pasos=None):
        # pasos: lista opcional donde se registra cada paso (para la animación)
        if origen is destino:
            return [origen], 0

        inf = float('inf')
        dist_f = {n: inf for n in self.nodos}    # f = forward (adelante)
        dist_b = {n: inf for n in self.nodos}    # b = backward (atrás)
        padre_f = {n: None for n in self.nodos}
        padre_b = {n: None for n in self.nodos}
        vis_f, vis_b = set(), set()
        contador = itertools.count()

        dist_f[origen] = 0
        dist_b[destino] = 0
        pq_f = [(0, next(contador), origen)]
        pq_b = [(0, next(contador), destino)]

        mejor = inf
        encuentro = None

        while pq_f and pq_b:
            if pq_f[0][0] + pq_b[0][0] >= mejor:
                break   # ya nada puede mejorar el camino

            if pq_f[0][0] <= pq_b[0][0]:
                mejor, encuentro = self._expandir(pq_f, dist_f, padre_f, vis_f,
                                                  dist_b, True, mejor, encuentro, contador, pasos)
            else:
                mejor, encuentro = self._expandir(pq_b, dist_b, padre_b, vis_b,
                                                  dist_f, False, mejor, encuentro, contador, pasos)

        if encuentro is None:
            return None, inf

        # mitad 1: inicio → encuentro (al revés, como antes)
        camino = []
        actual = encuentro
        while actual is not None:
            camino.append(actual)
            actual = padre_f[actual]
        camino.reverse()

        # mitad 2: encuentro → fin (padre_b ya apunta hacia el fin)
        actual = padre_b[encuentro]
        while actual is not None:
            camino.append(actual)
            actual = padre_b[actual]

        return camino, mejor

    def resolver(self, pasos=None):
        if self.inicio is None or self.fin is None:
            raise ValueError("Primero define el nodo de inicio y el de fin")
        return self.dijkstra_bidireccional(self.inicio, self.fin, pasos)
    def _expandir(self, pq, dist, padre, visitados, dist_otro, adelante,
                  mejor, encuentro, contador, pasos=None):
        busqueda = "f" if adelante else "b"
        d, _, nodo = heapq.heappop(pq)
        if nodo in visitados:
            return mejor, encuentro
        visitados.add(nodo)
        if pasos is not None:   # nodo con menor peso → pasa a visitado
            pasos.append({"tipo": "visitar", "busqueda": busqueda,
                          "nodo": nodo.nombre, "dist": d})

        aristas = nodo.aristas if adelante else nodo.entrantes
        for arista in aristas:
            vecino = arista.destino if adelante else arista.origen
            nueva = d + arista.peso
            mejora = nueva < dist[vecino]

            if mejora:
                dist[vecino] = nueva
                padre[vecino] = nodo
                heapq.heappush(pq, (nueva, next(contador), vecino))

            if pasos is not None:   # se calcula el peso del vecino por esta arista
                pasos.append({"tipo": "relajar", "busqueda": busqueda,
                              "origen": arista.origen.nombre,
                              "destino": arista.destino.nombre,
                              "nodo": vecino.nombre, "dist": nueva,
                              "mejora": mejora})

            # ¿la otra búsqueda ya llegó a este vecino? → hay un camino completo
            total = nueva + dist_otro[vecino]
            if total < mejor:
                mejor = total
                encuentro = vecino
                if pasos is not None:
                    pasos.append({"tipo": "encuentro", "nodo": vecino.nombre,
                                  "costo": total})

        return mejor, encuentro
    
if __name__=="__main__":
    FILAS, COLS = 20, 20   # cuadrícula de 20 x 20 = 400 nodos
    g = Grafo()
    N = [Nodo(f"N{i}") for i in range(FILAS * COLS)]

    for fila in range(FILAS):
        for col in range(COLS):
            i = fila * COLS + col
            if col < COLS - 1:   # arista hacia la derecha
                peso = (i * 53 + 13 + fila * 7) % 9 + 1
                g.agregar_arista(N[i], N[i + 1], peso)
            if fila < FILAS - 1:  # arista hacia abajo
                peso = (i * 53 + 26 + fila * 7) % 9 + 1
                g.agregar_arista(N[i], N[i + COLS], peso)

    g.set_inicio(N[0])
    g.set_fin(N[-1])

    camino, costo = g.resolver()
    print(f"Nodos en el grafo: {len(g.nodos)}")
    print(f"Camino ({len(camino)} nodos): {' -> '.join(n.nombre for n in camino)}")
    print(f"Costo total: {costo}")