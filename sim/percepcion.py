"""Visión del alienígena: línea de vista y cono de visión (T08).

Base de la herramienta ve_tripulante del agente. El alienígena ve una casilla si está a
su alcance, dentro del cono que apunta hacia donde mira y sin paredes en medio. Las
casillas muy cercanas se ven en cualquier dirección, siempre que haya línea de vista.

Las distancias se miden en casillas, en línea recta entre centros (1 casilla = 2 m).
Las puertas y los casilleros no tapan la vista; solo las paredes.

Contenido principal:
    linea_de_vista: True si no hay paredes entre dos casillas (Bresenham).
    ve_casilla: True si el alienígena, desde su posición y dirección, ve una casilla.
    campo_de_vision: matriz booleana con todas las casillas que ve.
    ALCANCE_VISION, COS_MIN_VISION, RADIO_CERCANO: parámetros de la visión.

Tareas relacionadas: T08 (visión), T11 (herramienta ve_tripulante), T10 (eventos de
visión en sim/avance.py). Decisión D7 en docs/decisiones.md.
"""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np

from .mapa import Mapa

# Alcance máximo de la visión, en casillas (7.5 casillas = 15 m).
ALCANCE_VISION = 7.5
# Coseno mínimo entre la dirección del alienígena y la casilla. 0.45 es un semiángulo de
# unos 63 grados, así que el cono abarca unos 127 grados.
COS_MIN_VISION = 0.45
# Distancia, en casillas, por debajo de la cual se ve en cualquier dirección (solo hace
# falta línea de vista). 1.5 incluye las 8 casillas vecinas, también las diagonales.
RADIO_CERCANO = 1.5


@lru_cache(maxsize=None)
def _intermedias(dx: int, dy: int) -> tuple[tuple[int, int], ...]:
    """Desplazamientos de las casillas intermedias de Bresenham de (0, 0) a (dx, dy).

    Bresenham solo depende del desplazamiento, así que se calcula una vez por (dx, dy) y
    se reutiliza desde cualquier origen. No incluye el origen ni el destino.
    """
    x, y = 0, 0
    ax, ay = abs(dx), abs(dy)
    sx = 1 if dx > 0 else -1
    sy = 1 if dy > 0 else -1
    error = ax - ay
    celdas = []
    while (x, y) != (dx, dy):
        doble = 2 * error
        if doble > -ay:
            error -= ay
            x += sx
        if doble < ax:
            error += ax
            y += sy
        celdas.append((x, y))
    return tuple(celdas[:-1])


def linea_de_vista(mapa: Mapa, origen: tuple[int, int], destino: tuple[int, int]) -> bool:
    """Indica si no hay paredes entre dos casillas.

    Recorre la recta de origen a destino con el algoritmo de Bresenham y revisa solo las
    casillas intermedias: el origen y el destino no tapan. Las puertas y los casilleros
    tampoco tapan.

    Bresenham no es simétrico: la recta de A a B puede pasar por casillas distintas que
    la de B a A. Por eso la convención es llamarla siempre desde el alienígena hacia la
    casilla observada.

    Args:
        mapa: Mapa de la estación.
        origen: Casilla (x, y) desde la que se mira (el alienígena).
        destino: Casilla (x, y) observada.

    Returns:
        True si ninguna casilla intermedia es pared.

    Example:
        >>> m = Mapa(["#######", "#..#..#", "#.....#", "#######"])
        >>> linea_de_vista(m, (1, 1), (5, 1))
        False
        >>> linea_de_vista(m, (1, 2), (5, 2))
        True
    """
    ox, oy = origen
    for dx, dy in _intermedias(destino[0] - ox, destino[1] - oy):
        if mapa.es_pared(ox + dx, oy + dy):
            return False
    return True


def ve_casilla(mapa: Mapa, pos: tuple[int, int], direccion: tuple[int, int],
               casilla: tuple[int, int], alcance: float = ALCANCE_VISION,
               cos_min: float = COS_MIN_VISION) -> bool:
    """Indica si el alienígena ve una casilla.

    Reglas, en orden:

    1. Su propia casilla siempre se ve.
    2. Más lejos que alcance no se ve.
    3. Más cerca que RADIO_CERCANO se ve si hay línea de vista, mire hacia donde mire.
    4. En otro caso, el coseno entre la dirección y la casilla debe ser al menos cos_min
       (está dentro del cono) y debe haber línea de vista.

    Args:
        mapa: Mapa de la estación.
        pos: Casilla (x, y) del alienígena.
        direccion: Hacia dónde mira, como (dx, dy) de DIRS; y crece hacia abajo.
        casilla: Casilla (x, y) observada.
        alcance: Distancia máxima, en casillas.
        cos_min: Coseno mínimo del cono.

    Returns:
        True si la casilla se ve.

    Raises:
        ValueError: Si direccion es (0, 0).

    Example:
        >>> m = Mapa(["##########", "#........#", "##########"])
        >>> ve_casilla(m, (1, 1), (1, 0), (6, 1))
        True
        >>> ve_casilla(m, (6, 1), (1, 0), (1, 1))
        False
    """
    if direccion == (0, 0):
        raise ValueError("La dirección del alienígena no puede ser (0, 0).")
    if casilla == pos:
        return True
    dx, dy = casilla[0] - pos[0], casilla[1] - pos[1]
    distancia = math.hypot(dx, dy)
    if distancia > alcance:
        return False
    if distancia < RADIO_CERCANO:
        return linea_de_vista(mapa, pos, casilla)
    # Se normaliza por el largo de la dirección para aceptar vectores que no sean unitarios.
    coseno = (direccion[0] * dx + direccion[1] * dy) / (distancia * math.hypot(*direccion))
    return coseno >= cos_min and linea_de_vista(mapa, pos, casilla)


def campo_de_vision(mapa: Mapa, pos: tuple[int, int], direccion: tuple[int, int],
                    alcance: float = ALCANCE_VISION,
                    cos_min: float = COS_MIN_VISION) -> np.ndarray:
    """Matriz con todas las casillas que ve el alienígena.

    Solo recorre el cuadrado de lado 2 * alcance alrededor de pos, porque lo demás queda
    fuera de alcance. Las paredes nunca se marcan, aunque se vea su cara.

    Args:
        mapa: Mapa de la estación.
        pos: Casilla (x, y) del alienígena.
        direccion: Hacia dónde mira, como (dx, dy) de DIRS.
        alcance: Distancia máxima, en casillas.
        cos_min: Coseno mínimo del cono.

    Returns:
        Matriz booleana (alto, ancho), indexada como [y, x].

    Raises:
        ValueError: Si direccion es (0, 0).

    Example:
        >>> m = Mapa(["#####", "#...#", "#####"])
        >>> campo_de_vision(m, (1, 1), (1, 0)).astype(int).tolist()
        [[0, 0, 0, 0, 0], [0, 1, 1, 1, 0], [0, 0, 0, 0, 0]]
    """
    campo = np.zeros((mapa.alto, mapa.ancho), dtype=bool)
    r = int(math.floor(alcance))
    x0, y0 = pos
    for y in range(max(0, y0 - r), min(mapa.alto, y0 + r + 1)):
        for x in range(max(0, x0 - r), min(mapa.ancho, x0 + r + 1)):
            if not mapa.paredes[y, x] and ve_casilla(mapa, pos, direccion, (x, y),
                                                     alcance, cos_min):
                campo[y, x] = True
    return campo
