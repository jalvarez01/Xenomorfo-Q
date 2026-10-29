"""Simulación de la estación: mapa en cuadrícula y entorno de caza.

Contenido principal:
    Mapa: carga y consultas del mapa (sim/mapa.py).
    EstacionEnv: entorno tipo Gym del alienígena y el tripulante (sim/env.py).

Tareas relacionadas: T06 a T11.
"""
from .mapa import Mapa
from .env import EstacionEnv

__all__ = ["Mapa", "EstacionEnv"]
