"""Simulación de la estación: mapa en cuadrícula y entorno de caza.

Contenido principal:
    Mapa: carga y consultas del mapa (sim/mapa.py).
    EstacionEnv: entorno tipo Gym del alienígena y el tripulante (sim/env.py).
    Visión del alienígena (sim/percepcion.py), rutas con A* (sim/rutas.py) y avance con
    eventos (sim/avance.py), que se importan desde sus módulos.

Tareas relacionadas: T07 (mapa, salas y entorno), T08 (visión), T09 (A*) y T10 (avance
y eventos).
"""
from .mapa import Mapa
from .env import EstacionEnv

__all__ = ["Mapa", "EstacionEnv"]
