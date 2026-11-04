"""Pruebas de la heurística de predecir_destino con trayectorias construidas (T12).

Contenido principal:
    Casos en un mapa pequeño (resultados calculables a mano) y en vela9, con las
    trayectorias escritas casilla por casilla para poder seguirlas sobre el mapa.

Tareas relacionadas: T12 (predecir_destino).
"""
from __future__ import annotations

import json

import pytest

from director.prediccion import VENTANA_TICKS, PredictorDestino
from sim import EstacionEnv, Mapa
from sim.env import MAPA_POR_DEFECTO

# Tres salas en línea: A (x 1-2), B (x 4-5) y C (x 7-8), separadas por puertas.
LINEA = Mapa(["##########",
              "#..+..+..#",
              "##########"],
             filas_salas=["##########",
                          "#00+11+22#",
                          "##########"],
             nombres_salas=["A", "B", "C"])


@pytest.fixture(scope="module")
def vela9() -> Mapa:
    """Mapa por defecto, cargado una sola vez."""
    return Mapa.desde_archivo(MAPA_POR_DEFECTO)


@pytest.fixture(scope="module")
def predictor(vela9) -> PredictorDestino:
    """Predictor de vela9; precalcula las distancias una sola vez."""
    return PredictorDestino(vela9)


# --- Mapa pequeño: valores calculables a mano -----------------------------------------


def test_distancias_a_sala_en_linea():
    """La distancia es 0 dentro de la sala y cuenta pasos a través de las puertas."""
    p = PredictorDestino(LINEA)
    assert p.distancia((1, 1), 0) == 0
    assert p.distancia((1, 1), 1) == 3  # (2,1) -> puerta (3,1) -> (4,1)
    assert p.distancia((1, 1), 2) == 6
    assert p.distancia((3, 1), 0) == 1  # una puerta no pertenece a ninguna sala


def test_camina_directo_a_una_sala():
    """Saliendo de A hacia el este, la sala más cercana adelante es B, con confianza 1."""
    r = PredictorDestino(LINEA).predecir([(1, 1), (2, 1), (3, 1)])
    assert r == {"sala": "B", "confianza": 1.0, "acercamiento_casillas": 2,
                 "ticks_analizados": 2}


def test_atraviesa_una_sala_hacia_la_siguiente():
    """Si entra a B y la cruza sin detenerse, el destino pasa a ser C."""
    r = PredictorDestino(LINEA).predecir([(3, 1), (4, 1), (5, 1), (6, 1)])
    assert r["sala"] == "C"
    assert r["confianza"] == 1.0


def test_llega_a_una_sala_y_se_queda():
    """Si llega a B y se queda quieto, B gana aunque C esté más adelante."""
    r = PredictorDestino(LINEA).predecir([(1, 1), (2, 1), (3, 1), (4, 1), (4, 1)])
    assert r["sala"] == "B"
    # 3 de 4 ticks lo acercaron a B: el tick quieto baja la confianza.
    assert r["confianza"] == 0.75


def test_quieto_devuelve_su_sala_con_confianza_cero():
    """Sin acercarse a ninguna sala, se informa la sala actual y confianza 0."""
    r = PredictorDestino(LINEA).predecir([(5, 1)] * 6)
    assert r["sala"] == "B"
    assert r["confianza"] == 0.0
    assert r["acercamiento_casillas"] == 0


def test_una_sola_posicion():
    """Al inicio de la partida hay una posición: sala actual, 0 ticks, confianza 0."""
    assert PredictorDestino(LINEA).predecir([(8, 1)]) == {
        "sala": "C", "confianza": 0.0, "acercamiento_casillas": 0, "ticks_analizados": 0}


def test_solo_en_puertas_da_sala_none():
    """Si en toda la ventana estuvo en una puerta, no hay sala que informar."""
    assert PredictorDestino(LINEA).predecir([(3, 1), (3, 1)])["sala"] is None


def test_se_aleja_vuelve_a_su_sala():
    """Si se aleja de C hacia el oeste sin entrar a otra sala, el destino es B o A, no C."""
    r = PredictorDestino(LINEA).predecir([(8, 1), (7, 1), (6, 1)])
    assert r["sala"] == "B"


def test_solo_cuenta_la_ventana():
    """Lo que pasó antes de los últimos ticks no influye en la predicción."""
    p = PredictorDestino(LINEA, ventana=2)
    # Va hacia el este y después vuelve hacia el oeste en los dos últimos ticks.
    r = p.predecir([(1, 1), (2, 1), (3, 1), (4, 1), (5, 1), (4, 1), (3, 1)])
    assert r["sala"] == "A"
    assert r["ticks_analizados"] == 2


def test_resultado_serializable_a_json():
    """El resultado se puede enviar al modelo con json.dumps sin conversiones."""
    r = PredictorDestino(LINEA).predecir([(1, 1), (2, 1)])
    assert json.loads(json.dumps(r, ensure_ascii=False)) == r


# --- Errores ----------------------------------------------------------------------------


def test_trayectoria_vacia():
    """Una trayectoria vacía da un error claro."""
    with pytest.raises(ValueError, match="vacía"):
        PredictorDestino(LINEA).predecir([])


@pytest.mark.parametrize("casilla", [(0, 0), (20, 1), (-1, 1)])
def test_casilla_no_transitable(casilla):
    """Paredes o casillas fuera del mapa en la trayectoria dan un error claro."""
    with pytest.raises(ValueError, match="no es transitable"):
        PredictorDestino(LINEA).predecir([(1, 1), casilla])


def test_mapa_sin_salas():
    """Un mapa sin salas no se puede usar para predecir."""
    with pytest.raises(ValueError, match="no tiene salas"):
        PredictorDestino(Mapa(["#####", "#...#", "#####"]))


def test_ventana_invalida():
    """La ventana debe ser de al menos un tick."""
    with pytest.raises(ValueError, match="ventana"):
        PredictorDestino(LINEA, ventana=0)


# --- vela9 ------------------------------------------------------------------------------


def test_vela9_todas_las_salas_se_alcanzan(predictor, vela9):
    """vela9 está conectado: desde toda casilla transitable se llega a todas las salas."""
    for casilla in vela9.transitables:
        for sala in range(vela9.n_salas):
            assert predictor.distancia(casilla, sala) is not None


def test_vela9_de_medico_a_laboratorio(predictor):
    """Al cruzar la puerta de Médico y entrar al Laboratorio, el destino es Laboratorio."""
    # Fila 3, de (2, 3) a (10, 3): la puerta (7, 3) está en el camino.
    trayectoria = [(2, 3), (3, 3), (4, 3), (5, 3), (6, 3), (7, 3), (8, 3), (9, 3), (10, 3)]
    r = predictor.predecir(trayectoria)
    assert r["sala"] == "Laboratorio"
    assert r["confianza"] >= 0.5


def test_vela9_baja_del_corredor_a_la_bodega(predictor):
    """Bajando por el Corredor A hacia la puerta de abajo a la izquierda, va a Bodega."""
    # Hacia el oeste por la fila 6, baja por la columna 4 (en (3, 7) hay un casillero)
    # y entra a la puerta (3, 9).
    trayectoria = [(8, 6), (7, 6), (6, 6), (5, 6), (4, 6), (4, 7), (4, 8), (3, 8), (3, 9)]
    r = predictor.predecir(trayectoria)
    assert r["sala"] == "Bodega"


def test_vela9_cruza_el_corredor_b_hacia_el_hangar(predictor):
    """Desde el Corredor B hacia la puerta (20, 9), el destino es Hangar."""
    trayectoria = [(13, 7), (14, 7), (15, 7), (16, 7), (17, 7), (18, 7),
                   (18, 8), (19, 8), (20, 8), (20, 9)]
    r = predictor.predecir(trayectoria)
    assert r["sala"] == "Hangar"
    # Desde (13, 7) hay dos rutas de 9 pasos al Hangar (por la puerta (20, 9) o por el
    # Reactor), así que uno de los 9 pasos no acorta la distancia: 8 de 9 ticks.
    assert r["acercamiento_casillas"] == 8
    assert r["confianza"] == 0.89


def test_vela9_usa_solo_los_ultimos_10_ticks(predictor):
    """Una trayectoria larga solo usa los últimos VENTANA_TICKS ticks."""
    # Primero cruza toda la fila 12 hacia el este (Bodega, Reactor, Hangar)...
    tramo1 = [(x, 12) for x in range(1, 22)]
    # ...y después sube por el Hangar y el Corredor B hasta Comunicaciones.
    tramo2 = [(21, 11), (21, 10), (20, 10), (20, 9), (20, 8), (20, 7), (20, 6),
              (19, 6), (19, 5), (19, 4), (19, 3), (19, 2)]
    r = predictor.predecir(tramo1 + tramo2)
    assert r["ticks_analizados"] == VENTANA_TICKS
    assert r["sala"] == "Comunicaciones"


def test_vela9_con_el_entorno(predictor, vela9):
    """Con la trayectoria real de EstacionEnv, la sala es válida y la confianza en [0, 1]."""
    env = EstacionEnv(vela9)
    env.reset(semilla=7)
    for _ in range(25):
        env.step(1)
        r = predictor.predecir(env.trayectoria)
        assert r["sala"] in vela9.nombres_salas or r["sala"] is None
        assert 0.0 <= r["confianza"] <= 1.0
        assert r["ticks_analizados"] == min(env.tick, VENTANA_TICKS)
