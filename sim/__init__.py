"""Simulación de la estación: mapa en cuadrícula y entorno de caza.

Contenido principal:
    Mapa: carga y consultas del mapa (sim/mapa.py).
    EstacionEnv: entorno tipo Gym del alienígena y el tripulante (sim/env.py).

Tareas relacionadas: T07 (mapa, salas y entorno); planeadas T08 (visión), T09 (A*) y
T10 (avance y eventos).
"""
from .mapa import Mapa
from .env import EstacionEnv

__all__ = ["Mapa", "EstacionEnv"]
