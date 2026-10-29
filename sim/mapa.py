"""Carga de mapas desde texto.

Símbolos: '#' pared, '.' piso, '+' puerta (transitable), 'L' casillero.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

PARED, PISO, PUERTA, CASILLERO = "#", ".", "+", "L"
DIRS = ((0, -1), (1, 0), (0, 1), (-1, 0))  # arriba, derecha, abajo, izquierda


class Mapa:
    def __init__(self, filas: list[str]):
        if not filas or len({len(f) for f in filas}) != 1:
            raise ValueError("El mapa debe tener filas no vacías y del mismo ancho.")
        validos = {PARED, PISO, PUERTA, CASILLERO}
        for y, fila in enumerate(filas):
            malos = set(fila) - validos
            if malos:
                raise ValueError(f"Símbolos no válidos en la fila {y}: {malos}")
        self.filas = filas
        self.alto, self.ancho = len(filas), len(filas[0])
        self.paredes = np.array([[c == PARED for c in f] for f in filas], dtype=bool)
        self.casilleros = np.array([[c == CASILLERO for c in f] for f in filas], dtype=bool)
        self.transitables = [(x, y) for y in range(self.alto) for x in range(self.ancho)
                             if self.es_transitable(x, y)]

    @classmethod
    def desde_archivo(cls, ruta: str | Path) -> "Mapa":
        lineas = Path(ruta).read_text(encoding="utf-8").splitlines()
        return cls([l.rstrip() for l in lineas if l.strip()])

    def dentro(self, x: int, y: int) -> bool:
        return 0 <= x < self.ancho and 0 <= y < self.alto

    def es_pared(self, x: int, y: int) -> bool:
        return not self.dentro(x, y) or bool(self.paredes[y, x])

    def es_casillero(self, x: int, y: int) -> bool:
        return self.dentro(x, y) and bool(self.casilleros[y, x])

    def es_transitable(self, x: int, y: int) -> bool:
        """Piso o puerta: se puede caminar. Los casilleros no se cruzan caminando."""
        return not self.es_pared(x, y) and not self.es_casillero(x, y)

    def vecinos(self, x: int, y: int) -> list[tuple[int, int]]:
        return [(x + dx, y + dy) for dx, dy in DIRS if self.es_transitable(x + dx, y + dy)]
