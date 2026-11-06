"""Pruebas de las rutas con A* y de la ruta a la sala más cercana (T09).

Contenido principal:
    Casos en mapas pequeños con largos conocidos, errores y, en vela9, comparación con
    BFS en pares de casillas al azar (semilla fija).

Tareas relacionadas: T09 (A*), T11 (herramienta ruta_mas_corta).
"""
from __future__ import annotations

import random
from collections import deque

import pytest

from sim import Mapa
from sim.env import MAPA_POR_DEFECTO
from sim.rutas import ruta, ruta_a_sala

# Una isla de pared en el centro: ir de (1, 2) a (5, 2) obliga a rodearla.
ISLA = Mapa(["#######",
             "#.....#",
             "#.###.#",
             "#.....#",
             "#######"])

# Dos salas separadas por una puerta en (3, 1).
DOS_SALAS = Mapa(["#######",
                  "#..+..#",
                  "#######"],
                 filas_salas=["#######",
                              "#00+11#",
                              "#######"],
                 nombres_salas=["A", "B"])


@pytest.fixture(scope="module")
def vela9() -> Mapa:
    """Mapa por defecto, cargado una sola vez."""
    return Mapa.desde_archivo(MAPA_POR_DEFECTO)


def bfs(mapa: Mapa, origen: tuple[int, int]) -> dict[tuple[int, int], int]:
    """Distancias en pasos desde origen a todas las casillas alcanzables (referencia)."""
    dist = {origen: 0}
    cola = deque([origen])
    while cola:
        actual = cola.popleft()
        for vecina in mapa.vecinos(*actual):
            if vecina not in dist:
                dist[vecina] = dist[actual] + 1
                cola.append(vecina)
    return dist


def es_camino_valido(mapa: Mapa, camino: list[tuple[int, int]]) -> bool:
    """True si cada casilla es transitable y cada par seguido está a un paso."""
    if not all(mapa.es_transitable(*c) for c in camino):
        return False
    return all(abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1 for a, b in zip(camino, camino[1:]))


# --- Mapas pequeños --------------------------------------------------------------------


def test_largo_conocido_en_linea_recta():
    """En un pasillo recto, el camino tiene tantos pasos como la distancia Manhattan."""
    m = Mapa(["#######", "#.....#", "#######"])
    camino = ruta(m, (1, 1), (5, 1))
    assert camino == [(1, 1), (2, 1), (3, 1), (4, 1), (5, 1)]
    assert len(camino) - 1 == 4


def test_pared_obliga_a_rodear():
    """La isla de pared hace el camino de 6 pasos aunque la distancia Manhattan sea 4."""
    camino = ruta(ISLA, (1, 2), (5, 2))
    assert len(camino) - 1 == 6
    assert es_camino_valido(ISLA, camino)


def test_sin_camino_devuelve_none():
    """Dos zonas sin conexión no tienen camino."""
    assert ruta(Mapa(["#####", "#.#.#", "#####"]), (1, 1), (3, 1)) is None


def test_cruza_la_puerta():
    """El camino entre dos salas pasa por la puerta."""
    camino = ruta(DOS_SALAS, (1, 1), (5, 1))
    assert (3, 1) in camino
    assert len(camino) - 1 == 4


def test_nunca_pisa_un_casillero():
    """Con un casillero en línea recta, el camino lo rodea."""
    m = Mapa(["#####", "#...#", "#.L.#", "#...#", "#####"])
    camino = ruta(m, (1, 2), (3, 2))
    assert (2, 2) not in camino
    assert len(camino) - 1 == 4


def test_origen_igual_a_destino():
    """Si origen y destino coinciden, el camino es solo esa casilla."""
    assert ruta(ISLA, (1, 1), (1, 1)) == [(1, 1)]


@pytest.mark.parametrize("origen, destino, motivo", [
    ((0, 0), (1, 1), "no es transitable"),       # pared
    ((1, 1), (9, 9), "fuera del mapa"),
    ((-1, 1), (1, 1), "fuera del mapa"),
])
def test_casillas_invalidas(origen, destino, motivo):
    """Una pared o una casilla fuera del mapa dan un error claro."""
    with pytest.raises(ValueError, match=motivo):
        ruta(ISLA, origen, destino)


def test_destino_en_casillero_da_error():
    """Un casillero no se puede pisar, así que tampoco puede ser destino."""
    m = Mapa(["#####", "#.L.#", "#####"])
    with pytest.raises(ValueError, match="casillero"):
        ruta(m, (1, 1), (2, 1))


def test_es_determinista():
    """La misma consulta siempre devuelve el mismo camino, aunque haya empates."""
    assert ruta(ISLA, (1, 1), (5, 3)) == ruta(ISLA, (1, 1), (5, 3))
    assert ruta(ISLA, (1, 1), (5, 3)) == [(1, 1), (2, 1), (3, 1), (4, 1), (5, 1), (5, 2), (5, 3)]


# --- ruta_a_sala -----------------------------------------------------------------------


def test_ruta_a_sala_llega_a_la_primera_casilla():
    """Desde A, la ruta a B termina en la primera casilla de B tras la puerta."""
    assert ruta_a_sala(DOS_SALAS, (1, 1), 1) == [(1, 1), (2, 1), (3, 1), (4, 1)]


def test_ruta_a_sala_ya_dentro():
    """Si el origen ya está en la sala, el camino es solo el origen."""
    assert ruta_a_sala(DOS_SALAS, (2, 1), 0) == [(2, 1)]


@pytest.mark.parametrize("sala", [2, -1, True, "B"])
def test_ruta_a_sala_indice_invalido(sala):
    """Un índice que no existe (o que no es un entero) da un error claro."""
    with pytest.raises(ValueError, match="no existe"):
        ruta_a_sala(DOS_SALAS, (1, 1), sala)


def test_ruta_a_sala_sin_salas():
    """Un mapa sin salas no admite ruta_a_sala."""
    with pytest.raises(ValueError, match="no tiene salas"):
        ruta_a_sala(ISLA, (1, 1), 0)


# --- vela9 -----------------------------------------------------------------------------


def test_vela9_200_pares_coinciden_con_bfs(vela9):
    """En 200 pares al azar, A* da caminos válidos con el mismo largo que BFS."""
    rng = random.Random(2026)
    distancias = {}
    for _ in range(200):
        origen, destino = rng.choice(vela9.transitables), rng.choice(vela9.transitables)
        if origen not in distancias:
            distancias[origen] = bfs(vela9, origen)
        camino = ruta(vela9, origen, destino)
        assert camino[0] == origen and camino[-1] == destino
        assert es_camino_valido(vela9, camino)
        assert len(camino) - 1 == distancias[origen][destino]


def test_vela9_ruta_a_sala_es_minima(vela9):
    """ruta_a_sala termina en la sala pedida con el largo mínimo de BFS a esa sala."""
    rng = random.Random(7)
    for origen in rng.sample(vela9.transitables, 25):
        dist = bfs(vela9, origen)
        for sala in range(vela9.n_salas):
            camino = ruta_a_sala(vela9, origen, sala)
            assert vela9.sala(*camino[-1]) == sala
            assert es_camino_valido(vela9, camino)
            minimo = min(d for c, d in dist.items() if vela9.sala(*c) == sala)
            assert len(camino) - 1 == minimo
