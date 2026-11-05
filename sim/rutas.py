"""Rutas más cortas con A* sobre el mapa (T09).

Base de la herramienta ruta_mas_corta del agente. Se camina en 4 direcciones con costo
1 por paso, por piso y puertas; las paredes y los casilleros no se cruzan (son los
vecinos de Mapa.vecinos). La heurística es la distancia Manhattan, que con estos
movimientos nunca sobreestima, así que A* devuelve siempre un camino de largo mínimo.

Los caminos son listas de casillas (x, y) que incluyen el origen y el destino. El número
de pasos es len(camino) - 1.

Contenido principal:
    ruta: camino más corto entre dos casillas.
    ruta_a_sala: camino más corto desde una casilla hasta la sala indicada.

Tareas relacionadas: T09 (A*), T11 (herramienta ruta_mas_corta). Decisión D11 en
docs/decisiones.md.
"""
from __future__ import annotations

import heapq
from collections.abc import Callable
from itertools import count

from .mapa import Mapa

Casilla = tuple[int, int]


def ruta(mapa: Mapa, origen: Casilla, destino: Casilla) -> list[Casilla] | None:
    """Camino más corto entre dos casillas transitables, con A*.

    Desempate determinista: entre casillas con el mismo f = g + h se expande primero la
    de menor h (la más cerca del destino); si siguen empatadas, la que entró antes a la
    frontera. Los vecinos se generan en el orden de DIRS (arriba, derecha, abajo,
    izquierda). Así, para un mismo mapa y extremos, el camino siempre es el mismo.

    Args:
        mapa: Mapa de la estación.
        origen: Casilla (x, y) de partida.
        destino: Casilla (x, y) de llegada.

    Returns:
        Lista de casillas de origen a destino, ambos incluidos; [origen] si son la misma
        casilla; None si no hay camino.

    Raises:
        ValueError: Si origen o destino está fuera del mapa o no es transitable.

    Example:
        >>> m = Mapa(["#####", "#...#", "#.#.#", "#...#", "#####"])
        >>> ruta(m, (1, 1), (3, 3))
        [(1, 1), (2, 1), (3, 1), (3, 2), (3, 3)]
        >>> len(ruta(m, (1, 1), (3, 3))) - 1
        4
    """
    _validar(mapa, origen, "origen")
    _validar(mapa, destino, "destino")
    return _a_estrella(mapa, origen, lambda c: c == destino,
                       lambda c: abs(c[0] - destino[0]) + abs(c[1] - destino[1]))


def ruta_a_sala(mapa: Mapa, origen: Casilla, sala: int) -> list[Casilla] | None:
    """Camino más corto desde una casilla hasta la casilla transitable más cercana de una sala.

    Es A* con varias metas: la heurística es la menor distancia Manhattan a las casillas
    transitables de la sala. El mínimo de heurísticas admisibles y consistentes también
    lo es, así que el camino tiene el largo mínimo a la sala. Los casilleros de la sala
    no cuentan como meta porque no se pisan.

    Args:
        mapa: Mapa de la estación, con salas.
        origen: Casilla (x, y) de partida.
        sala: Índice de la sala, de 0 a mapa.n_salas - 1.

    Returns:
        Lista de casillas desde origen hasta la primera casilla de la sala; [origen] si
        ya está en la sala; None si no se llega.

    Raises:
        ValueError: Si el mapa no tiene salas, si el índice no existe o si origen está
            fuera del mapa o no es transitable.

    Example:
        >>> m = Mapa(["#######", "#..+..#", "#######"],
        ...          filas_salas=["#######", "#00+11#", "#######"], nombres_salas=["A", "B"])
        >>> ruta_a_sala(m, (1, 1), 1)
        [(1, 1), (2, 1), (3, 1), (4, 1)]
    """
    if mapa.n_salas == 0:
        raise ValueError("El mapa no tiene salas; ruta_a_sala las necesita.")
    if isinstance(sala, bool) or not isinstance(sala, int) or not 0 <= sala < mapa.n_salas:
        raise ValueError(
            f"La sala {sala!r} no existe; los índices válidos van de 0 a {mapa.n_salas - 1}.")
    _validar(mapa, origen, "origen")
    metas = [c for c in mapa.transitables if mapa.sala(*c) == sala]
    return _a_estrella(mapa, origen, lambda c: mapa.sala(*c) == sala,
                       lambda c: min(abs(c[0] - x) + abs(c[1] - y) for x, y in metas))


def _validar(mapa: Mapa, casilla: Casilla, nombre: str) -> None:
    """Lanza ValueError si la casilla está fuera del mapa o no se puede pisar."""
    x, y = casilla
    if not mapa.dentro(x, y):
        raise ValueError(f"El {nombre} {casilla} está fuera del mapa "
                         f"({mapa.ancho} columnas por {mapa.alto} filas).")
    if not mapa.es_transitable(x, y):
        raise ValueError(f"El {nombre} {casilla} no es transitable: es pared o casillero.")


def _a_estrella(mapa: Mapa, origen: Casilla, es_meta: Callable[[Casilla], bool],
                heuristica: Callable[[Casilla], int]) -> list[Casilla] | None:
    """A* genérico con costo 1 por paso; devuelve el camino a la primera meta expandida."""
    orden = count()  # desempate por orden de llegada a la frontera
    g = {origen: 0}
    padre: dict[Casilla, Casilla] = {}
    h0 = heuristica(origen)
    frontera = [(h0, h0, next(orden), origen)]
    cerradas = set()
    while frontera:
        _, _, _, actual = heapq.heappop(frontera)
        if actual in cerradas:
            continue  # entrada vieja: ya se expandió con un g menor
        if es_meta(actual):
            camino = [actual]
            while camino[-1] in padre:
                camino.append(padre[camino[-1]])
            return camino[::-1]
        cerradas.add(actual)
        for vecina in mapa.vecinos(*actual):
            nuevo_g = g[actual] + 1
            if vecina not in g or nuevo_g < g[vecina]:
                g[vecina] = nuevo_g
                padre[vecina] = actual
                h = heuristica(vecina)
                heapq.heappush(frontera, (nuevo_g + h, h, next(orden), vecina))
    return None
