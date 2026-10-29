"""Entorno mínimo de la estación (versión 0, tareas T06 + T10).

Interfaz tipo Gym acordada en la pestaña 'Contratos':
    obs = env.reset(semilla)
    obs, recompensa, terminado, info = env.step(accion)

Versión 0: movimiento y captura. Visión (T07), ruido BFS (T08) y casilleros (T09)
se agregan después sin cambiar esta interfaz.

Contenido principal:
    EstacionEnv: el entorno, con el alienígena controlado por el agente y un tripulante
        movido por un bot provisional.
    Constantes de acciones y recompensas.

El contrato completo está en docs/contratos.md.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from .mapa import DIRS, Mapa

# Mapa que se usa cuando no se pasa ninguno. Se resuelve desde la ubicación del paquete
# para que funcione sin importar el directorio de trabajo.
MAPA_POR_DEFECTO = Path(__file__).resolve().parent.parent / "data" / "mapas" / "vela9.txt"

# Acciones del alienígena: 0 arriba, 1 derecha, 2 abajo, 3 izquierda, 4 revisar casillero
N_ACCIONES = 5
# Recompensas en puntos: R_CAPTURA al atrapar al tripulante, R_PASO en cada tick
# (empuja a capturar rápido) y R_CASILLERO_VACIO como castigo adicional por revisar
# un casillero sin nadie.
R_CAPTURA, R_PASO, R_CASILLERO_VACIO = 100.0, -1.0, -5.0


class EstacionEnv:
    """Entorno de caza en la estación con interfaz tipo Gym.

    El agente controla al alienígena. El tripulante se mueve después de cada acción
    con un bot provisional. Hay captura cuando la distancia Manhattan entre ambos es
    1 o menos.

    Args:
        mapa: Un Mapa ya construido o la ruta a un archivo de mapa.
        max_ticks: Ticks máximos por episodio antes de cortarlo sin captura.
        distancia_inicial: Distancia Manhattan mínima entre alienígena y tripulante al
            iniciar, en casillas.
        semilla: Semilla del generador aleatorio. None usa una semilla del sistema.

    Raises:
        ValueError: Si el mapa no es válido.
        FileNotFoundError: Si se pasa una ruta que no existe.

    Attributes:
        mapa: Mapa de la estación.
        rng: Generador aleatorio; controla posiciones iniciales y el bot.
        alien: Posición (x, y) del alienígena.
        tripulante: Posición (x, y) del tripulante.
        tick: Ticks transcurridos en el episodio actual.
        trayectoria: Posiciones del tripulante en el episodio, incluida la inicial.

    Example:
        >>> env = EstacionEnv()
        >>> obs = env.reset(42)
        >>> obs.shape
        (4, 15, 24)
    """

    def __init__(self, mapa: Mapa | str | Path = MAPA_POR_DEFECTO, max_ticks: int = 300,
                 distancia_inicial: int = 10, semilla: int | None = None):
        self.mapa = mapa if isinstance(mapa, Mapa) else Mapa.desde_archivo(mapa)
        self.max_ticks = max_ticks
        self.distancia_inicial = distancia_inicial
        self.rng = np.random.default_rng(semilla)
        self.alien = self.tripulante = (0, 0)
        self.tick = 0
        self.trayectoria: list[tuple[int, int]] = []

    # ------------------------------------------------------------------ API
    def reset(self, semilla: int | None = None) -> np.ndarray:
        """Inicia un episodio nuevo.

        Ubica al alienígena en una casilla transitable al azar y al tripulante a por lo
        menos distancia_inicial casillas de él.

        Args:
            semilla: Si se pasa, reinicia el generador aleatorio para que el episodio
                sea reproducible. Si es None, continúa con el generador actual.

        Returns:
            Observación inicial de forma (4, alto, ancho) y tipo float32.
        """
        if semilla is not None:
            self.rng = np.random.default_rng(semilla)
        libres = self.mapa.transitables
        self.alien = libres[self.rng.integers(len(libres))]
        # Si el mapa es muy pequeño y ninguna casilla cumple la distancia, se acepta
        # cualquiera para no dejar el episodio sin tripulante.
        lejos = [c for c in libres if _manhattan(c, self.alien) >= self.distancia_inicial] or libres
        self.tripulante = lejos[self.rng.integers(len(lejos))]
        self.tick = 0
        self.trayectoria = [self.tripulante]
        return self._observacion()

    def step(self, accion: int) -> tuple[np.ndarray, float, bool, dict]:
        """Avanza un tick: mueve al alienígena, luego al tripulante, y revisa captura.

        Args:
            accion: 0 arriba, 1 derecha, 2 abajo, 3 izquierda, 4 revisar casillero.

        Returns:
            Tupla (obs, recompensa, terminado, info):
                obs: Observación (4, alto, ancho) float32.
                recompensa: R_PASO más R_CAPTURA si hubo captura y R_CASILLERO_VACIO
                    si la acción fue 4.
                terminado: True si hubo captura o se llegó a max_ticks.
                info: Diccionario con 'tick', 'capturado' y 'distancia_real'.

        Raises:
            ValueError: Si la acción está fuera de 0 a 4.

        Example:
            >>> env = EstacionEnv()
            >>> _ = env.reset(42)
            >>> env.step(1)[1:]
            (-1.0, False, {'tick': 1, 'capturado': False, 'distancia_real': 10})
        """
        if not 0 <= accion < N_ACCIONES:
            raise ValueError(f"Acción fuera de rango: {accion}")
        self.tick += 1
        recompensa = R_PASO

        if accion < 4:
            self.alien = self._mover(self.alien, accion)
        else:
            recompensa += R_CASILLERO_VACIO  # T09: revisar casilleros reales

        # Se revisa la captura antes y después de mover al tripulante: si el alienígena
        # llega a su lado, el tripulante no alcanza a escapar en ese mismo tick.
        capturado = self._captura()
        if not capturado:
            self.tripulante = self._paso_tripulante()
            self.trayectoria.append(self.tripulante)
            capturado = self._captura()

        if capturado:
            recompensa += R_CAPTURA
        terminado = capturado or self.tick >= self.max_ticks
        info = {"tick": self.tick, "capturado": capturado,
                "distancia_real": _manhattan(self.alien, self.tripulante)}
        return self._observacion(), recompensa, terminado, info

    # ------------------------------------------------------------- internos
    def _mover(self, pos: tuple[int, int], accion: int) -> tuple[int, int]:
        """Aplica una acción de movimiento; si choca, se queda en el sitio."""
        dx, dy = DIRS[accion]
        nueva = (pos[0] + dx, pos[1] + dy)
        return nueva if self.mapa.es_transitable(*nueva) else pos

    def _paso_tripulante(self) -> tuple[int, int]:
        """Bot provisional: se aleja del alienígena si está cerca; si no, camina al azar.
        Los bots con estilos llegan en T11."""
        # Quedarse quieto es una opción válida; así nunca se queda sin movimientos.
        opciones = self.mapa.vecinos(*self.tripulante) + [self.tripulante]
        opciones = [c for c in opciones if c != self.alien]
        # 6 casillas es el radio en el que el bot "nota" al alienígena y huye.
        if _manhattan(self.tripulante, self.alien) <= 6:
            mejor = max(_manhattan(c, self.alien) for c in opciones)
            opciones = [c for c in opciones if _manhattan(c, self.alien) == mejor]
        return opciones[self.rng.integers(len(opciones))]

    def _captura(self) -> bool:
        """True si el alienígena está en la misma casilla o en una contigua."""
        return _manhattan(self.alien, self.tripulante) <= 1

    def _observacion(self) -> np.ndarray:
        """Tensor (4, alto, ancho): paredes, creencia, alien, pista.
        Versión 0: creencia uniforme y pista vacía (llegan en T21 y T19)."""
        obs = np.zeros((4, self.mapa.alto, self.mapa.ancho), dtype=np.float32)
        obs[0] = self.mapa.paredes
        # 0.5 distingue los casilleros de las paredes sin abrir una capa adicional.
        obs[0][self.mapa.casilleros] = 0.5
        libres = ~self.mapa.paredes & ~self.mapa.casilleros
        obs[1][libres] = 1.0 / libres.sum()
        obs[2][self.alien[1], self.alien[0]] = 1.0
        return obs


def _manhattan(a: tuple[int, int], b: tuple[int, int]) -> int:
    """Distancia Manhattan entre dos casillas (x, y), en casillas."""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])
