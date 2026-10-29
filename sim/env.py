"""Entorno mínimo de la estación (versión 0, tareas T06 + T10).

Interfaz tipo Gym acordada en la pestaña 'Contratos':
    obs = env.reset(semilla)
    obs, recompensa, terminado, info = env.step(accion)

Versión 0: movimiento y captura. Visión (T07), ruido BFS (T08) y casilleros (T09)
se agregan después sin cambiar esta interfaz.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from .mapa import DIRS, Mapa

MAPA_POR_DEFECTO = Path(__file__).resolve().parent.parent / "data" / "mapas" / "vela9.txt"

# Acciones del alienígena: 0 arriba, 1 derecha, 2 abajo, 3 izquierda, 4 revisar casillero
N_ACCIONES = 5
R_CAPTURA, R_PASO, R_CASILLERO_VACIO = 100.0, -1.0, -5.0


class EstacionEnv:
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
        if semilla is not None:
            self.rng = np.random.default_rng(semilla)
        libres = self.mapa.transitables
        self.alien = libres[self.rng.integers(len(libres))]
        lejos = [c for c in libres if _manhattan(c, self.alien) >= self.distancia_inicial] or libres
        self.tripulante = lejos[self.rng.integers(len(lejos))]
        self.tick = 0
        self.trayectoria = [self.tripulante]
        return self._observacion()

    def step(self, accion: int):
        if not 0 <= accion < N_ACCIONES:
            raise ValueError(f"Acción fuera de rango: {accion}")
        self.tick += 1
        recompensa = R_PASO

        if accion < 4:
            self.alien = self._mover(self.alien, accion)
        else:
            recompensa += R_CASILLERO_VACIO  # T09: revisar casilleros reales

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
        dx, dy = DIRS[accion]
        nueva = (pos[0] + dx, pos[1] + dy)
        return nueva if self.mapa.es_transitable(*nueva) else pos

    def _paso_tripulante(self) -> tuple[int, int]:
        """Bot provisional: se aleja del alienígena si está cerca; si no, camina al azar.
        Los bots con estilos llegan en T11."""
        opciones = self.mapa.vecinos(*self.tripulante) + [self.tripulante]
        opciones = [c for c in opciones if c != self.alien]
        if _manhattan(self.tripulante, self.alien) <= 6:
            mejor = max(_manhattan(c, self.alien) for c in opciones)
            opciones = [c for c in opciones if _manhattan(c, self.alien) == mejor]
        return opciones[self.rng.integers(len(opciones))]

    def _captura(self) -> bool:
        return _manhattan(self.alien, self.tripulante) <= 1

    def _observacion(self) -> np.ndarray:
        """Tensor (4, alto, ancho): paredes, creencia, alien, pista.
        Versión 0: creencia uniforme y pista vacía (llegan en T21 y T19)."""
        obs = np.zeros((4, self.mapa.alto, self.mapa.ancho), dtype=np.float32)
        obs[0] = self.mapa.paredes
        obs[0][self.mapa.casilleros] = 0.5
        libres = ~self.mapa.paredes & ~self.mapa.casilleros
        obs[1][libres] = 1.0 / libres.sum()
        obs[2][self.alien[1], self.alien[0]] = 1.0
        return obs


def _manhattan(a: tuple[int, int], b: tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])
