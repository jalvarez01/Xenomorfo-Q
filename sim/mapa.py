"""Carga de mapas desde texto.

Símbolos: '#' pared, '.' piso, '+' puerta (transitable), 'L' casillero.

Contenido principal:
    Mapa: cuadrícula de la estación con consultas de paredes, casilleros y vecinos.
    DIRS: desplazamientos de las cuatro direcciones, en el mismo orden que las acciones.

Tareas relacionadas: T06 (mapa y entorno mínimo).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

# Símbolos del formato de texto de los mapas (un carácter por casilla).
PARED, PISO, PUERTA, CASILLERO = "#", ".", "+", "L"
# Desplazamientos (dx, dy) en casillas. El índice coincide con las acciones 0 a 3 del
# entorno, por eso el orden no se puede cambiar. y crece hacia abajo, como en el texto.
DIRS = ((0, -1), (1, 0), (0, 1), (-1, 0))  # arriba, derecha, abajo, izquierda


class Mapa:
    """Cuadrícula de la estación construida a partir de filas de texto.

    Las coordenadas se expresan como (x, y): x es la columna e y la fila. Los arreglos
    internos se indexan como [y, x].

    Args:
        filas: Filas del mapa, todas del mismo ancho, con símbolos '#', '.', '+' o 'L'.

    Raises:
        ValueError: Si no hay filas, si tienen anchos distintos o si aparece un símbolo
            desconocido.

    Attributes:
        filas: Filas de texto originales.
        alto: Número de filas.
        ancho: Número de columnas.
        paredes: Matriz booleana (alto, ancho), True donde hay pared.
        casilleros: Matriz booleana (alto, ancho), True donde hay casillero.
        transitables: Lista de casillas (x, y) por las que se puede caminar, en orden
            de fila y luego columna.

    Example:
        >>> m = Mapa(["#####", "#.L+#", "#####"])
        >>> m.alto, m.ancho
        (3, 5)
        >>> m.transitables
        [(1, 1), (3, 1)]
    """

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
        # Se precalcula una sola vez porque reset() sortea posiciones de esta lista en
        # cada episodio.
        self.transitables = [(x, y) for y in range(self.alto) for x in range(self.ancho)
                             if self.es_transitable(x, y)]

    @classmethod
    def desde_archivo(cls, ruta: str | Path) -> "Mapa":
        """Carga un mapa desde un archivo de texto UTF-8.

        Ignora las líneas vacías y los espacios al final de cada línea, para tolerar
        archivos editados a mano.

        Args:
            ruta: Ruta al archivo del mapa.

        Returns:
            El mapa construido.

        Raises:
            ValueError: Si el contenido no es un mapa válido.
            FileNotFoundError: Si el archivo no existe.

        Example:
            >>> m = Mapa.desde_archivo("data/mapas/vela9.txt")
            >>> m.alto, m.ancho
            (15, 24)
        """
        lineas = Path(ruta).read_text(encoding="utf-8").splitlines()
        return cls([l.rstrip() for l in lineas if l.strip()])

    def dentro(self, x: int, y: int) -> bool:
        """Indica si la casilla está dentro de los límites del mapa.

        Args:
            x: Columna.
            y: Fila.

        Returns:
            True si 0 <= x < ancho y 0 <= y < alto.
        """
        return 0 <= x < self.ancho and 0 <= y < self.alto

    def es_pared(self, x: int, y: int) -> bool:
        """Indica si la casilla es pared.

        Fuera del mapa se considera pared, así quien llama no tiene que revisar límites.

        Args:
            x: Columna.
            y: Fila.

        Returns:
            True si es pared o está fuera del mapa.
        """
        return not self.dentro(x, y) or bool(self.paredes[y, x])

    def es_casillero(self, x: int, y: int) -> bool:
        """Indica si la casilla es un casillero.

        Args:
            x: Columna.
            y: Fila.

        Returns:
            True si la casilla está dentro del mapa y es un casillero.
        """
        return self.dentro(x, y) and bool(self.casilleros[y, x])

    def es_transitable(self, x: int, y: int) -> bool:
        """Piso o puerta: se puede caminar. Los casilleros no se cruzan caminando.

        Args:
            x: Columna.
            y: Fila.

        Returns:
            True si la casilla es piso o puerta.
        """
        return not self.es_pared(x, y) and not self.es_casillero(x, y)

    def vecinos(self, x: int, y: int) -> list[tuple[int, int]]:
        """Casillas transitables contiguas (sin diagonales).

        Args:
            x: Columna.
            y: Fila.

        Returns:
            Lista de casillas (x, y) en el orden de DIRS: arriba, derecha, abajo,
            izquierda.

        Example:
            >>> Mapa(["#####", "#...#", "#####"]).vecinos(2, 1)
            [(3, 1), (1, 1)]
        """
        return [(x + dx, y + dy) for dx, dy in DIRS if self.es_transitable(x + dx, y + dy)]
