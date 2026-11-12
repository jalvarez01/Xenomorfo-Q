"""Pruebas de las 6 herramientas del agente sobre vela9 con la semilla 42 (T11).

Los valores esperados se calculan por otro camino (BFS propio, posiciones del entorno y
campo_vision), no con las mismas funciones que usan las herramientas.

Tareas relacionadas: T11 (herramientas), T13 (esquemas), D12 y D14 (nombres de sala).
"""
from __future__ import annotations

import json
from collections import deque

import pytest

from director.esquemas import NOMBRES_HERRAMIENTAS, construir_esquemas, validar_correspondencia
from director.herramientas import NOMBRES_DIRECCION, PUERTA, crear_herramientas
from director.partida import Partida
from sim.mapa import SIN_SALA, Mapa
from sim.percepcion import campo_de_vision


@pytest.fixture
def partida() -> Partida:
    """Partida nueva de vela9 con la semilla 42."""
    return Partida(semilla=42)


@pytest.fixture
def h(partida) -> dict:
    """Herramientas ligadas a la partida de la prueba."""
    return crear_herramientas(partida)


def bfs(mapa: Mapa, origen: tuple[int, int]) -> dict[tuple[int, int], int]:
    """Distancias en pasos desde origen a todas las casillas alcanzables (referencia)."""
    dist = {origen: 0}
    cola = deque([origen])
    while cola:
        actual = cola.popleft()
        for vecina in mapa.vecinos(*actual):
            if vecina not in dist:
                dist[vecina] = dist[actual] + 1
                cola.append(vecina)
    return dist


def distancia_a_sala(mapa: Mapa, origen: tuple[int, int], sala: int) -> int:
    """Menor distancia BFS desde origen a una casilla de la sala (referencia)."""
    return min(d for c, d in bfs(mapa, origen).items() if mapa.sala(*c) == sala)


# --- Correspondencia y forma ------------------------------------------------------------


def test_coinciden_con_los_esquemas(partida, h):
    """Las 6 funciones coinciden con sus esquemas: nombres y parámetros."""
    assert tuple(h) == NOMBRES_HERRAMIENTAS
    assert validar_correspondencia(construir_esquemas(partida.env.mapa.nombres_salas), h) == []


def test_todos_los_resultados_son_json(h):
    """Cada resultado se puede enviar al modelo con json.dumps."""
    resultados = [
        h["estado_partida"](), h["ruta_mas_corta"]("alienigena", "Hangar"),
        h["predecir_destino"](), h["ve_tripulante"](), h["dar_pista"]("Bodega"),
        h["avanzar_simulacion"](5),
    ]
    for r in resultados:
        assert json.loads(json.dumps(r, ensure_ascii=False)) == r


# --- estado_partida ---------------------------------------------------------------------


def test_estado_partida_inicial(partida, h):
    """El estado inicial coincide con las posiciones y salas del entorno."""
    env = partida.env
    assert h["estado_partida"]() == {
        "tick": 0,
        "tripulante": {"x": env.tripulante[0], "y": env.tripulante[1], "sala": "Bodega"},
        "alienigena": {"x": env.alien[0], "y": env.alien[1], "sala": "Médico",
                       "direccion": "abajo"},
        "pistas_restantes": 3,
        "capturado": False,
    }


def test_estado_partida_en_puerta_y_direccion(partida, h):
    """En una puerta informa la última sala y la dirección en español."""
    env = partida.env
    env.alien, env.direccion_alien = (7, 3), (1, 0)
    env.trayectoria, env.tripulante = [(1, 12), (2, 12), (3, 12), (6, 12)], (6, 12)
    estado = h["estado_partida"]()
    assert estado["alienigena"]["sala"] == "Médico"
    assert estado["alienigena"]["direccion"] == "derecha"
    assert estado["tripulante"]["sala"] == "Bodega"
    assert set(NOMBRES_DIRECCION.values()) == {"arriba", "derecha", "abajo", "izquierda"}


def test_estado_partida_captura(partida, h):
    """capturado sigue la regla del entorno: contiguos es captura."""
    partida.env.alien, partida.env.tripulante = (2, 11), (2, 12)
    assert h["estado_partida"]()["capturado"] is True


# --- ruta_mas_corta ---------------------------------------------------------------------


def test_ruta_entre_personajes(partida, h):
    """De alienígena a tripulante, los pasos son la distancia BFS entre sus casillas."""
    env = partida.env
    r = h["ruta_mas_corta"]("alienigena", "tripulante")
    assert r["pasos"] == bfs(env.mapa, env.alien)[env.tripulante]
    assert r["camino_resumido"][0] == "Médico" and r["camino_resumido"][-1] == "Bodega"


@pytest.mark.parametrize("origen", ["alienígena", "ALIENIGENA", " Alienigena "])
def test_personaje_con_tilde_y_mayusculas(h, origen):
    """'alienígena' con tilde o mayúsculas es el mismo personaje."""
    assert h["ruta_mas_corta"](origen, "tripulante") == h["ruta_mas_corta"]("alienigena", "tripulante")


def test_ruta_personaje_a_sala_y_sala_a_personaje(partida, h):
    """Personaje a sala y sala a personaje dan la menor distancia BFS a la sala."""
    env = partida.env
    hangar = env.mapa.indice_sala("Hangar")
    assert h["ruta_mas_corta"]("alienigena", "Hangar")["pasos"] == distancia_a_sala(env.mapa, env.alien, hangar)
    assert h["ruta_mas_corta"]("Hangar", "tripulante")["pasos"] == distancia_a_sala(env.mapa, env.tripulante, hangar)


def test_ruta_sala_a_sala_es_la_minima(partida, h):
    """De sala a sala, los pasos son el mínimo entre todas las casillas de las dos salas."""
    mapa = partida.env.mapa
    medico, hangar = mapa.indice_sala("Médico"), mapa.indice_sala("Hangar")
    esperado = min(distancia_a_sala(mapa, c, hangar) for c in mapa.transitables if mapa.sala(*c) == medico)
    assert h["ruta_mas_corta"]("medico", "HANGAR")["pasos"] == esperado


def test_ruta_misma_sala(h):
    """Dentro de la misma sala la ruta es de 0 pasos."""
    assert h["ruta_mas_corta"]("Reactor", "reactor") == {"pasos": 0, "camino_resumido": ["Reactor"]}


def test_camino_resumido_sin_repetidos_y_con_puertas(h):
    """camino_resumido no repite entradas seguidas y marca las puertas como 'puerta'."""
    for origen, destino in [("alienigena", "tripulante"), ("Médico", "Hangar"), ("Bodega", "Comunicaciones")]:
        resumen = h["ruta_mas_corta"](origen, destino)["camino_resumido"]
        assert all(a != b for a, b in zip(resumen, resumen[1:]))
        assert PUERTA in resumen
    assert h["ruta_mas_corta"]("Médico", "Laboratorio")["camino_resumido"] == ["Médico", PUERTA, "Laboratorio"]


def test_ruta_sala_inexistente(h):
    """Una sala que no existe da un error con las salas válidas y los dos personajes."""
    with pytest.raises(ValueError, match="'Enfermería' no existe. Salas válidas: Médico") as info:
        h["ruta_mas_corta"]("Enfermería", "Hangar")
    assert "'tripulante'" in str(info.value) and "'alienigena'" in str(info.value)


def test_ruta_sin_camino():
    """Si no hay camino entre las dos salas, da un error claro."""
    mapa = Mapa(["#######", "#.#.#.#", "#######"],
                filas_salas=["#######", "#0#1#2#", "#######"], nombres_salas=["A", "B", "C"])
    herramientas = crear_herramientas(Partida(mapa=mapa, semilla=0))
    with pytest.raises(ValueError, match="No hay camino entre 'A' y 'C'"):
        herramientas["ruta_mas_corta"]("A", "C")


# --- predecir_destino y ve_tripulante ---------------------------------------------------


def test_predecir_destino_usa_la_trayectoria(partida, h):
    """predecir_destino es el predictor aplicado a env.trayectoria."""
    h["avanzar_simulacion"](12)
    assert h["predecir_destino"]() == partida.predictor.predecir(partida.env.trayectoria)
    assert h["predecir_destino"]()["ticks_analizados"] == 10


def test_ve_tripulante_lejos(partida, h):
    """Al inicio no lo ve y la distancia es la BFS entre los dos."""
    env = partida.env
    assert h["ve_tripulante"]() == {"ve": False, "distancia_casillas": bfs(env.mapa, env.alien)[env.tripulante]}


def test_ve_tripulante_usa_campo_vision(partida, h):
    """Con el tripulante dentro de campo_vision, ve es True."""
    env = partida.env
    env.alien, env.tripulante = (10, 3), (12, 3)
    env.direccion_alien = (1, 0)
    env.campo_vision = campo_de_vision(env.mapa, env.alien, env.direccion_alien)
    assert h["ve_tripulante"]() == {"ve": True, "distancia_casillas": 2}


# --- dar_pista y avanzar_simulacion -----------------------------------------------------


@pytest.mark.parametrize("sala, canonica", [("medico", "Médico"), ("CORREDOR  a", "Corredor A")])
def test_dar_pista_sin_tildes_ni_mayusculas(partida, h, sala, canonica):
    """dar_pista acepta el nombre sin tildes ni mayúsculas y lo pasa canónico al alienígena."""
    assert h["dar_pista"](sala) == {"sala": canonica, "pistas_restantes": 2}
    assert partida.alien.pista_activa == canonica


def test_dar_pista_sala_inexistente_no_gasta(partida, h):
    """Una sala inexistente da error y no gasta la pista."""
    with pytest.raises(ValueError, match="no existe"):
        h["dar_pista"]("Enfermería")
    assert partida.alien.pistas_restantes == 3


def test_cuarta_pista_da_error(h):
    """Después de 3 pistas, la cuarta da un error claro."""
    for sala in ("Hangar", "Reactor", "Bodega"):
        h["dar_pista"](sala)
    with pytest.raises(ValueError, match="No quedan pistas"):
        h["dar_pista"]("Médico")


def test_pista_y_avance_acercan_al_alienigena(partida, h):
    """Tras dar_pista y avanzar, el alienígena se acerca a la sala de la pista."""
    env = partida.env
    hangar = env.mapa.indice_sala("Hangar")
    antes = distancia_a_sala(env.mapa, env.alien, hangar)
    h["dar_pista"]("Hangar")
    assert partida.alien.pista_activa == "Hangar"
    r = h["avanzar_simulacion"](10)
    assert r["ticks_avanzados"] == 10
    assert distancia_a_sala(env.mapa, env.alien, hangar) < antes


@pytest.mark.parametrize("ticks", [0, 21, 2.5, "10"])
def test_avanzar_ticks_invalidos(partida, h, ticks):
    """Fuera de 1 a 20, o si no es entero, da error sin avanzar la partida."""
    with pytest.raises(ValueError, match="ticks"):
        h["avanzar_simulacion"](ticks)
    assert partida.env.tick == 0


def test_avanzar_devuelve_el_contrato(partida, h):
    """avanzar_simulacion devuelve tick, ticks_avanzados, eventos y capturado."""
    r = h["avanzar_simulacion"](20)
    assert set(r) == {"tick", "ticks_avanzados", "eventos", "capturado"}
    assert r["tick"] == partida.env.tick == 20
    assert h["estado_partida"]()["tick"] == 20
    assert h["estado_partida"]()["alienigena"]["sala"] is not None
    assert partida.ultima_sala_alien() != SIN_SALA
