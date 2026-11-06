"""Pruebas de la visión del alienígena y su integración con el entorno (T08).

Contenido principal:
    Casos en mapas pequeños para la línea de vista, el cono y los radios, y casos del
    entorno para direccion_alien, campo_vision e info["ve_tripulante"].

Tareas relacionadas: T08 (visión), T10 (eventos de visión en Avance).
"""
from __future__ import annotations

import pytest

from sim import EstacionEnv, Mapa
from sim.avance import Avance
from sim.env import MAPA_POR_DEFECTO
from sim.percepcion import (
    ALCANCE_VISION,
    RADIO_CERCANO,
    campo_de_vision,
    linea_de_vista,
    ve_casilla,
)
from sim.rutas import ruta

# Pasillo recto de 12 casillas libres (x 1 a 12), sin obstáculos.
PASILLO = Mapa(["##############",
                "#............#",
                "##############"])

# Sala abierta con una pared vertical en x = 6, de la fila 2 a la 4.
CON_PARED = Mapa(["############",
                  "#..........#",
                  "#.....#....#",
                  "#.....#....#",
                  "#.....#....#",
                  "############"])

# Sala abierta de 10 por 3 casillas, sin obstáculos.
ABIERTA = Mapa(["############",
                "#..........#",
                "#..........#",
                "#..........#",
                "############"])


def colocar(env: EstacionEnv, alien: tuple[int, int], tripulante: tuple[int, int]) -> None:
    """Inicia la partida y ubica a los dos personajes en casillas elegidas."""
    env.reset(semilla=0)
    env.alien, env.tripulante = alien, tripulante
    env.trayectoria = [tripulante]


# --- Línea de vista --------------------------------------------------------------------


def test_pared_tapa_la_vista():
    """Una pared entre las dos casillas corta la línea de vista."""
    assert linea_de_vista(CON_PARED, (3, 3), (9, 3)) is False


def test_pasillo_abierto_no_tapa():
    """En un pasillo sin paredes en medio hay línea de vista."""
    assert linea_de_vista(PASILLO, (1, 1), (12, 1)) is True


def test_puerta_y_casillero_no_tapan():
    """Las puertas y los casilleros en medio no cortan la línea de vista."""
    m = Mapa(["#########", "#..+.L..#", "#########"])
    assert linea_de_vista(m, (1, 1), (7, 1)) is True


def test_origen_y_destino_no_tapan():
    """Mirar hacia una pared contigua no se corta por la pared misma."""
    assert linea_de_vista(PASILLO, (1, 1), (0, 1)) is True


# --- Cono y radios ---------------------------------------------------------------------


def test_casilla_detras_lejos_no_se_ve_y_al_frente_si():
    """Una casilla a 3 casillas detrás no se ve; la misma casilla al frente sí."""
    assert 3 > RADIO_CERCANO
    assert ve_casilla(PASILLO, (5, 1), (1, 0), (2, 1)) is False
    assert ve_casilla(PASILLO, (5, 1), (-1, 0), (2, 1)) is True


def test_mas_alla_del_alcance_no_se_ve():
    """A 8 casillas (más que ALCANCE_VISION) no se ve; a 7 sí."""
    assert 7 < ALCANCE_VISION < 8
    assert ve_casilla(PASILLO, (1, 1), (1, 0), (9, 1)) is False
    assert ve_casilla(PASILLO, (1, 1), (1, 0), (8, 1)) is True


def test_casilla_contigua_detras_se_ve():
    """Las casillas a menos de RADIO_CERCANO se ven aunque estén detrás, incluso en diagonal."""
    assert ve_casilla(ABIERTA, (5, 2), (1, 0), (4, 2)) is True
    assert ve_casilla(ABIERTA, (5, 2), (1, 0), (4, 1)) is True


def test_propia_casilla_se_ve():
    """La casilla del alienígena siempre se ve."""
    assert ve_casilla(PASILLO, (3, 1), (0, 1), (3, 1)) is True


def test_direccion_nula_da_error():
    """Una dirección (0, 0) no define un cono y lanza ValueError."""
    with pytest.raises(ValueError, match="dirección"):
        ve_casilla(PASILLO, (3, 1), (0, 0), (5, 1))


def test_campo_de_vision_nunca_marca_paredes():
    """En vela9, desde cualquier casilla y dirección, el campo no incluye paredes."""
    vela9 = Mapa.desde_archivo(MAPA_POR_DEFECTO)
    for pos in vela9.transitables[::7]:
        for direccion in ((0, -1), (1, 0), (0, 1), (-1, 0)):
            campo = campo_de_vision(vela9, pos, direccion)
            assert not (campo & vela9.paredes).any()
            assert campo[pos[1], pos[0]]


# --- Entorno ---------------------------------------------------------------------------


def test_accion_1_mira_a_la_derecha():
    """La acción 1 deja al alienígena mirando a la derecha, aunque choque."""
    env = EstacionEnv(PASILLO)
    colocar(env, alien=(12, 1), tripulante=(1, 1))
    assert env.direccion_alien == (0, 1)
    env.step(1)
    assert env.alien == (12, 1)
    assert env.direccion_alien == (1, 0)


def test_accion_4_conserva_la_direccion():
    """La acción 4 no mueve al alienígena ni cambia hacia dónde mira."""
    env = EstacionEnv(PASILLO)
    colocar(env, alien=(6, 1), tripulante=(1, 1))
    env.step(3)
    env.step(4)
    assert env.direccion_alien == (-1, 0)


def test_info_trae_ve_tripulante():
    """step() informa ve_tripulante como bool y campo_vision tiene la forma del mapa."""
    env = EstacionEnv()
    env.reset(semilla=42)
    _, _, _, info = env.step(1)
    assert isinstance(info["ve_tripulante"], bool)
    assert env.campo_vision.shape == (env.mapa.alto, env.mapa.ancho)


def test_ve_al_tripulante_en_sala_abierta():
    """Mirando hacia el tripulante en una sala sin obstáculos, lo ve."""
    env = EstacionEnv(ABIERTA)
    colocar(env, alien=(1, 2), tripulante=(6, 2))
    _, _, _, info = env.step(1)
    assert info["ve_tripulante"] is True


def test_no_lo_ve_con_una_pared_en_medio():
    """Con la pared entre los dos, no lo ve aunque mire hacia él."""
    env = EstacionEnv(CON_PARED)
    colocar(env, alien=(2, 3), tripulante=(9, 3))
    _, _, _, info = env.step(1)
    assert info["ve_tripulante"] is False


# --- Integración con Avance ------------------------------------------------------------


def test_avance_registra_que_lo_vio_antes_de_la_captura():
    """En vela9, un alienígena que persigue por la ruta más corta lo ve antes de capturarlo."""
    def persigue(env: EstacionEnv) -> int:
        camino = ruta(env.mapa, env.alien, env.tripulante)
        dx, dy = camino[1][0] - env.alien[0], camino[1][1] - env.alien[1]
        return [(0, -1), (1, 0), (0, 1), (-1, 0)].index((dx, dy))

    env = EstacionEnv()
    env.reset(semilla=4)
    avance = Avance(env, persigue)
    while not avance.avanzar(20)["capturado"]:
        pass
    eventos = avance.historial
    vio = [i for i, e in enumerate(eventos) if "vio al tripulante" in e]
    captura = [i for i, e in enumerate(eventos) if "capturó" in e]
    assert vio and captura
    assert vio[0] < captura[0]
