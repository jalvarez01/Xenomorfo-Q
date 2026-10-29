"""Carga de mapas desde texto.

Símbolos: '#' pared, '.' piso, '+' puerta (transitable), 'L' casillero.

Las salas se anotan en un archivo aparte, "<nombre>_salas.txt", junto al mapa. Su primera
línea es "nombres: A, B, ..." y luego viene una cuadrícula del mismo tamaño que el mapa,
con el índice de sala (un dígito) en cada casilla de piso o casillero, y '#' o '+' donde
el mapa tiene pared o puerta. El formato completo está en docs/entorno.md.

Contenido principal:
    Mapa: cuadrícula de la estación con consultas de paredes, casilleros, vecinos y salas.
    DIRS: desplazamientos de las cuatro direcciones, en el mismo orden que las acciones.

Tareas relacionadas: T06 (mapa y entorno mínimo), T15 (salas para la directora).
"""
from __future__ import annotations

from collections import deque
from pathlib import Path

import numpy as np

# Símbolos del formato de texto de los mapas (un carácter por casilla).
PARED, PISO, PUERTA, CASILLERO = "#", ".", "+", "L"
# Desplazamientos (dx, dy) en casillas. El índice coincide con las acciones 0 a 3 del
# entorno, por eso el orden no se puede cambiar. y crece hacia abajo, como en el texto.
DIRS = ((0, -1), (1, 0), (0, 1), (-1, 0))  # arriba, derecha, abajo, izquierda
# Valor de sala para paredes, puertas y casillas fuera del mapa.
SIN_SALA = -1
# Prefijo de la primera línea de un archivo de salas.
PREFIJO_NOMBRES = "nombres:"
# Sufijo que identifica el archivo de salas de un mapa: vela9.txt -> vela9_salas.txt.
SUFIJO_SALAS = "_salas"


class Mapa:
    """Cuadrícula de la estación construida a partir de filas de texto.

    Las coordenadas se expresan como (x, y): x es la columna e y la fila. Los arreglos
    internos se indexan como [y, x].

    Args:
        filas: Filas del mapa, todas del mismo ancho, con símbolos '#', '.', '+' o 'L'.
        filas_salas: Cuadrícula de salas del mismo tamaño que el mapa: un dígito por
            casilla de piso o casillero, '#' en paredes y '+' en puertas. None si el mapa
            no tiene salas.
        nombres_salas: Nombre de cada sala; el índice en la lista es el dígito de la
            cuadrícula. Obligatorio si se pasa filas_salas.

    Raises:
        ValueError: Si no hay filas, si tienen anchos distintos, si aparece un símbolo
            desconocido o si la anotación de salas no es válida (ver _cargar_salas).

    Attributes:
        filas: Filas de texto originales.
        alto: Número de filas.
        ancho: Número de columnas.
        paredes: Matriz booleana (alto, ancho), True donde hay pared.
        casilleros: Matriz booleana (alto, ancho), True donde hay casillero.
        transitables: Lista de casillas (x, y) por las que se puede caminar, en orden
            de fila y luego columna.
        salas: Matriz np.int16 (alto, ancho) con el índice de sala de cada casilla;
            -1 en paredes y puertas, y en todo el mapa si no hay salas.
        nombres_salas: Nombres de las salas, en orden de índice.
        n_salas: Número de salas; 0 si el mapa no tiene salas.

    Example:
        >>> m = Mapa(["#####", "#.L+#", "#####"])
        >>> m.alto, m.ancho
        (3, 5)
        >>> m.transitables
        [(1, 1), (3, 1)]
        >>> m = Mapa(["#####", "#.+.#", "#####"],
        ...          filas_salas=["#####", "#0+1#", "#####"], nombres_salas=["A", "B"])
        >>> m.n_salas, m.sala(1, 1), m.sala(2, 1), m.sala(3, 1)
        (2, 0, -1, 1)
    """

    def __init__(self, filas: list[str], filas_salas: list[str] | None = None,
                 nombres_salas: list[str] | None = None):
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
        self.salas = np.full((self.alto, self.ancho), SIN_SALA, dtype=np.int16)
        self.nombres_salas: list[str] = []
        self.n_salas = 0
        if filas_salas is not None:
            self._cargar_salas(filas_salas, nombres_salas)

    @classmethod
    def desde_archivo(cls, ruta: str | Path, ruta_salas: str | Path | None = None) -> "Mapa":
        """Carga un mapa desde un archivo de texto UTF-8, con sus salas si existen.

        Ignora las líneas vacías y los espacios al final de cada línea, para tolerar
        archivos editados a mano.

        Args:
            ruta: Ruta al archivo del mapa.
            ruta_salas: Ruta al archivo de salas. Si es None, se busca
                "<nombre>_salas.txt" en la misma carpeta del mapa; si no existe, el mapa
                queda sin salas.

        Returns:
            El mapa construido.

        Raises:
            ValueError: Si el mapa o la anotación de salas no son válidos.
            FileNotFoundError: Si el mapa no existe, o si se pasó ruta_salas y no existe.

        Example:
            >>> m = Mapa.desde_archivo("data/mapas/vela9.txt")
            >>> m.alto, m.ancho, m.n_salas
            (15, 24, 8)
        """
        ruta = Path(ruta)
        if ruta_salas is None:
            candidata = ruta.with_name(f"{ruta.stem}{SUFIJO_SALAS}.txt")
            ruta_salas = candidata if candidata.exists() else None
        if ruta_salas is None:
            return cls(_leer_filas(ruta))
        nombres, filas_salas = _leer_salas(Path(ruta_salas))
        return cls(_leer_filas(ruta), filas_salas, nombres)

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

    def sala(self, x: int, y: int) -> int:
        """Índice de la sala a la que pertenece una casilla.

        Los casilleros pertenecen a la sala en la que están.

        Args:
            x: Columna.
            y: Fila.

        Returns:
            Índice de sala entre 0 y n_salas - 1, o -1 si la casilla es pared, puerta,
            está fuera del mapa o el mapa no tiene salas.

        Example:
            >>> m = Mapa.desde_archivo("data/mapas/vela9.txt")
            >>> m.nombres_salas[m.sala(1, 1)]
            'Médico'
            >>> m.sala(7, 3)
            -1
        """
        if not self.dentro(x, y):
            return SIN_SALA
        return int(self.salas[y, x])

    # ------------------------------------------------------------- internos
    def _cargar_salas(self, filas_salas: list[str], nombres_salas: list[str] | None) -> None:
        """Valida la anotación de salas y llena salas, nombres_salas y n_salas.

        Raises:
            ValueError: Si faltan los nombres, si el tamaño no coincide con el mapa, si
                '#' y '+' no están exactamente donde el mapa tiene pared y puerta, si
                falta un dígito en piso o casillero, si un índice no tiene nombre, si una
                sala no se usa o si una sala no está conectada.
        """
        if not nombres_salas or not all(nombres_salas):
            raise ValueError("Las salas necesitan una lista de nombres no vacíos.")
        n = len(nombres_salas)
        if len(filas_salas) != self.alto or any(len(f) != self.ancho for f in filas_salas):
            raise ValueError(
                f"La anotación de salas debe medir {self.alto} filas por {self.ancho} "
                f"columnas, igual que el mapa.")
        salas = np.full((self.alto, self.ancho), SIN_SALA, dtype=np.int16)
        for y, (fila_mapa, fila_salas) in enumerate(zip(self.filas, filas_salas)):
            for x, (c_mapa, c_sala) in enumerate(zip(fila_mapa, fila_salas)):
                if c_mapa in (PARED, PUERTA):
                    # Paredes y puertas no tienen sala: la puerta separa dos salas y no
                    # pertenece a ninguna.
                    if c_sala != c_mapa:
                        raise ValueError(
                            f"En ({x}, {y}) el mapa tiene '{c_mapa}' y la anotación de "
                            f"salas tiene '{c_sala}'; deben coincidir.")
                    continue
                if not (len(c_sala) == 1 and c_sala in "0123456789"):
                    raise ValueError(
                        f"Falta el índice de sala en ({x}, {y}): el mapa tiene "
                        f"'{c_mapa}' y la anotación tiene '{c_sala}'.")
                indice = int(c_sala)
                if indice >= n:
                    raise ValueError(
                        f"El índice de sala {indice} en ({x}, {y}) no tiene nombre; "
                        f"hay {n} nombres.")
                salas[y, x] = indice
        sin_usar = sorted(set(range(n)) - set(np.unique(salas[salas >= 0]).tolist()))
        if sin_usar:
            raise ValueError(f"Hay salas con nombre que no aparecen en la anotación: {sin_usar}")
        for indice in range(n):
            self._validar_conexion(salas, indice, nombres_salas[indice])
        self.salas = salas
        self.nombres_salas = list(nombres_salas)
        self.n_salas = n

    def _validar_conexion(self, salas: np.ndarray, indice: int, nombre: str) -> None:
        """Revisa que una sala se pueda recorrer entera sin salir de ella.

        Las casillas transitables de la sala deben formar un solo bloque conectado (BFS
        que no sale de la sala) y cada casillero debe tocar una de esas casillas, porque
        un casillero se revisa desde una casilla contigua.

        Raises:
            ValueError: Si la sala no tiene piso, está partida o tiene un casillero que
                no se alcanza desde su propio piso.
        """
        celdas = {(x, y) for y, x in zip(*np.nonzero(salas == indice))}
        piso = {c for c in celdas if self.es_transitable(*c)}
        if not piso:
            raise ValueError(f"La sala {indice} ({nombre}) no tiene casillas de piso.")
        inicio = min(piso)
        vistos = {inicio}
        cola = deque([inicio])
        while cola:
            cx, cy = cola.popleft()
            for dx, dy in DIRS:
                v = (cx + dx, cy + dy)
                if v in piso and v not in vistos:
                    vistos.add(v)
                    cola.append(v)
        if vistos != piso:
            raise ValueError(
                f"La sala {indice} ({nombre}) no está conectada: {len(piso) - len(vistos)} "
                f"casillas de piso no se alcanzan sin salir de ella.")
        for cx, cy in sorted(celdas - piso):
            if not any((cx + dx, cy + dy) in piso for dx, dy in DIRS):
                raise ValueError(
                    f"El casillero en ({cx}, {cy}) de la sala {indice} ({nombre}) no toca "
                    f"ninguna casilla de piso de su sala.")


def _leer_filas(ruta: Path) -> list[str]:
    """Lee las filas no vacías de un archivo de texto, sin espacios finales."""
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    return [l.rstrip() for l in lineas if l.strip()]


def _leer_salas(ruta: Path) -> tuple[list[str], list[str]]:
    """Lee un archivo de salas y separa los nombres de la cuadrícula.

    Raises:
        ValueError: Si la primera línea no empieza con "nombres:".
    """
    filas = _leer_filas(ruta)
    if not filas or not filas[0].startswith(PREFIJO_NOMBRES):
        raise ValueError(f"La primera línea de {ruta.name} debe empezar con '{PREFIJO_NOMBRES}'.")
    nombres = [n.strip() for n in filas[0][len(PREFIJO_NOMBRES):].split(",")]
    return nombres, filas[1:]
