"""Pruebas de Partida: inicio, valores por defecto y última sala de cada personaje (T11).

Tareas relacionadas: T11 (herramientas).
"""
from __future__ import annotations

import pytest

from alien.reglas import AlienReglas
from director.partida import MAX_TICKS_POR_DEFECTO, SEMILLA_POR_DEFECTO, Partida
from sim import EstacionEnv, Mapa
from sim.avance import Avance
from sim.mapa import SIN_SALA


@pytest.fixture
def partida() -> Partida:
    """Partida nueva con la semilla por defecto."""
    return Partida()


def test_valores_por_defecto(partida):
    """Por defecto usa la semilla 42, 300 ticks y vela9, y arma alienígena, avance y predictor."""
    assert SEMILLA_POR_DEFECTO == 42 and MAX_TICKS_POR_DEFECTO == 300
    assert partida.semilla == 42
    assert partida.env.max_ticks == 300
    assert partida.env.mapa.n_salas == 8
    assert isinstance(partida.alien, AlienReglas)
    assert isinstance(partida.avance, Avance)
    assert partida.avance.politica is partida.alien


def test_misma_semilla_misma_partida():
    """Dos partidas con la misma semilla empiezan igual que env.reset con esa semilla."""
    env = EstacionEnv()
    env.reset(42)
    p = Partida(semilla=42)
    assert (p.env.alien, p.env.tripulante) == (env.alien, env.tripulante)
    assert (Partida(semilla=42).env.alien, Partida(semilla=42).env.tripulante) == (env.alien, env.tripulante)


def test_mapa_sin_salas_da_error():
    """Un mapa sin salas no sirve para las herramientas."""
    with pytest.raises(ValueError, match="no tiene salas"):
        Partida(mapa=Mapa(["#####", "#...#", "#####"]))


def test_ultima_sala_tripulante_en_puerta(partida):
    """En una puerta, la sala del tripulante es la última con sala de su trayectoria."""
    env = partida.env
    env.trayectoria = [(5, 3), (6, 3), (7, 3)]  # Médico, Médico, puerta
    env.tripulante = (7, 3)
    assert partida.nombre_sala(partida.ultima_sala_tripulante()) == "Médico"


def test_ultima_sala_tripulante_solo_puertas(partida):
    """Si la trayectoria solo tiene puertas, no hay sala que informar."""
    partida.env.trayectoria = [(7, 3)]
    assert partida.ultima_sala_tripulante() == SIN_SALA


def test_ultima_sala_alien_en_puerta_mira_atras(partida):
    """En una puerta, la sala del alienígena es la de la casilla de atrás según su dirección."""
    env = partida.env
    env.alien = (7, 3)
    env.direccion_alien = (1, 0)  # va hacia la derecha: viene de (6, 3), Médico
    assert partida.nombre_sala(partida.ultima_sala_alien()) == "Médico"
    env.direccion_alien = (-1, 0)  # va hacia la izquierda: viene de (8, 3), Laboratorio
    assert partida.nombre_sala(partida.ultima_sala_alien()) == "Laboratorio"


def test_ultima_sala_alien_usa_la_registrada(partida):
    """Si la casilla de atrás no tiene sala, usa la última registrada tras avanzar."""
    env = partida.env
    partida._registrar_sala_alien()  # en Médico
    env.alien = (7, 3)
    env.direccion_alien = (0, 1)  # atrás queda (7, 2), una pared
    assert partida.nombre_sala(partida.ultima_sala_alien()) == "Médico"


def test_avanzar_actualiza_la_sala_registrada(partida):
    """Después de avanzar, la sala registrada es la del alienígena en ese momento."""
    partida.alien.dar_pista("Laboratorio")
    partida.avanzar(10)
    assert partida.nombre_sala(partida._sala_alien) == "Laboratorio"
