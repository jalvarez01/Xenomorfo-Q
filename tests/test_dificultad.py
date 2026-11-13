"""Pruebas de los niveles de dificultad del panel (D19), sin red.

Lo principal: el nivel normal y los valores por defecto dejan todo como antes. Las huellas
de las partidas con semilla son las mismas de tests/test_panel.py, tomadas antes de
agregar los niveles, y los valores esperados de los casos son los de la evidencia oficial.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from alien.reglas import PISTAS_POR_PARTIDA, AlienReglas
from director import llm
from director.directora import Directora
from director.herramientas import crear_herramientas
from director.llm import ConfigLLM
from director.partida import Partida
from experiments.casos import CASOS, calcular_esperado
from panel.sesion import NIVELES, PistaAutomatica, Sesion
from sim.avance import Avance
from sim.env import EstacionEnv
from sim.mapa import Mapa
from sim.percepcion import ALCANCE_VISION
from tests.test_panel import HUELLA_STEP_42, HUELLAS_PARTIDA, huella_step, levantar

RAIZ = Path(__file__).resolve().parent.parent
EVIDENCIA = RAIZ / "experiments" / "resultados" / "casos_2026-11-12_prompt2_semilla42.json"
# Pasillo recto de 60 casillas con dos salas, para las persecuciones guionadas.
LARGO = 60


@pytest.fixture(autouse=True)
def entorno(monkeypatch):
    """Sin .env del equipo y con una clave falsa: ninguna prueba llama al modelo."""
    monkeypatch.setattr(llm, "_cargar_dotenv", lambda: None)
    monkeypatch.setenv(llm.VAR_CLAVE, "clave-falsa-dificultad")


def pasillo() -> Mapa:
    """Mapa de un pasillo recto de LARGO casillas: sala A a la izquierda, B a la derecha."""
    mitad = LARGO // 2
    return Mapa(["#" * (LARGO + 2), "#" + "." * LARGO + "#", "#" * (LARGO + 2)],
                filas_salas=["#" * (LARGO + 2), "#" + "0" * mitad + "1" * (LARGO - mitad) + "#",
                             "#" * (LARGO + 2)],
                nombres_salas=["A", "B"])


def colocar(env: EstacionEnv, alien: tuple[int, int], tripulante: tuple[int, int],
            direccion: tuple[int, int] = (1, 0)) -> None:
    """Pone a los dos personajes a mano y recalcula la visión, como si el tick empezara ahí."""
    env.alien, env.tripulante = alien, tripulante
    env.trayectoria = [tripulante]
    env.direccion_alien = direccion
    env.campo_vision = env._calcular_vision()


def huella_partida_por(partida: Partida) -> str:
    """Misma huella que tests/test_panel.huella_partida, sobre una Partida ya creada."""
    env = partida.env
    while env.tick < env.max_ticks:
        if partida.avanzar(20)["capturado"]:
            break
    datos = [list(c) for c in env.trayectoria] + [list(env.alien), env.tick,
                                                  int(env.rng.integers(1 << 30))]
    return hashlib.sha256(json.dumps(datos).encode()).hexdigest()


# --- Normal es la partida de siempre ----------------------------------------------------


@pytest.mark.parametrize("semilla", sorted(HUELLAS_PARTIDA))
def test_normal_identico_a_antes(semilla):
    """El nivel normal del panel, la directora y la partida por defecto dan las huellas de antes."""
    sesion = Sesion(semilla=semilla, config=ConfigLLM())
    assert sesion.nivel == "normal"
    assert huella_partida_por(sesion.directora.partida) == HUELLAS_PARTIDA[semilla]
    assert huella_partida_por(Directora(semilla=semilla, config=ConfigLLM()).partida) == HUELLAS_PARTIDA[semilla]
    assert huella_partida_por(Partida(semilla=semilla)) == HUELLAS_PARTIDA[semilla]


def test_normal_step_identico_a_antes():
    """200 pasos de env.step con el alcance por defecto explícito dan la misma huella."""
    assert huella_step(42) == HUELLA_STEP_42
    assert EstacionEnv().alcance_vision == ALCANCE_VISION == 7.5


def test_normal_no_activa_nada():
    """En normal no hay parámetros nuevos: ni alcance distinto, ni paso extra, ni pista automática."""
    assert NIVELES["normal"].opciones_partida() == {}
    partida = Sesion(semilla=42, config=ConfigLLM()).directora.partida
    assert partida.env.alcance_vision == ALCANCE_VISION
    assert partida.alien.paso_extra_cada is None
    assert partida.avance.tras_tick is None


@pytest.mark.parametrize("caso", [c["id"] for c in CASOS])
def test_evidencia_oficial_sin_cambios(caso):
    """Los valores esperados de los 6 casos siguen siendo los de la corrida oficial."""
    oficial = {c["id"]: c["resultado_esperado"]
               for c in json.loads(EVIDENCIA.read_text(encoding="utf-8"))["casos"]}
    assert calcular_esperado(caso) == oficial[caso]


# --- Paso extra al perseguir ------------------------------------------------------------


def perseguir(paso_extra_cada: int | None, ticks: int = 40) -> tuple[bool, int]:
    """Tripulante guionado que huye a la derecha por el pasillo; (capturado, tick)."""
    env = EstacionEnv(pasillo(), alcance_vision=10 if paso_extra_cada else ALCANCE_VISION)
    env.reset(0)
    colocar(env, alien=(1, 1), tripulante=(4, 1))
    avance = Avance(env, AlienReglas(env, paso_extra_cada=paso_extra_cada))
    for _ in range(ticks):
        if avance.avanzar(1, accion_tripulante=1)["capturado"]:
            return True, env.tick
    return False, env.tick


def test_dificil_alcanza_a_quien_huye_y_normal_nunca():
    """Huyendo a la misma velocidad, normal nunca lo alcanza; con el paso extra sí."""
    assert perseguir(None) == (False, 40)
    capturado, tick = perseguir(3)
    assert capturado and tick <= 9


def test_paso_extra_respeta_paredes_y_no_usa_el_azar():
    """Contra una pared el paso extra solo gira; no cambia el estado del generador."""
    env = EstacionEnv(pasillo())
    env.reset(0)
    colocar(env, alien=(1, 1), tripulante=(10, 1))
    antes = env.rng.bit_generator.state
    info = env.paso_extra_alien(3)  # izquierda: pared
    assert env.alien == (1, 1) and env.direccion_alien == (-1, 0)
    assert info["capturado"] is False and info["tick"] == env.tick
    env.paso_extra_alien(1)
    assert env.alien == (2, 1)
    assert env.rng.bit_generator.state == antes
    with pytest.raises(ValueError):
        env.paso_extra_alien(9)


def test_paso_extra_revisa_la_captura_antes_y_despues():
    """Si ya lo capturó no se mueve; si el paso lo deja al lado, informa la captura."""
    env = EstacionEnv(pasillo())
    env.reset(0)
    colocar(env, alien=(5, 1), tripulante=(6, 1))
    assert env.paso_extra_alien(3)["capturado"] is True and env.alien == (5, 1)
    colocar(env, alien=(5, 1), tripulante=(7, 1))
    assert env.paso_extra_alien(1)["capturado"] is True and env.alien == (6, 1)


def test_accion_extra_solo_al_perseguir_y_cada_n_ticks():
    """Sin paso_extra_cada nunca hay paso extra; con él, solo al perseguir y en múltiplos de N."""
    env = EstacionEnv(pasillo())
    env.reset(0)
    colocar(env, alien=(1, 1), tripulante=(5, 1))
    alien = AlienReglas(env, paso_extra_cada=3)
    alien.decidir()
    assert alien.estado == "persigue"
    env.tick = 2
    assert alien.accion_extra() is None
    env.tick = 3
    assert alien.accion_extra() == 1
    alien.estado = "patrulla"
    assert alien.accion_extra() is None
    assert AlienReglas(env).accion_extra() is None
    with pytest.raises(ValueError):
        AlienReglas(env, paso_extra_cada=0)


# --- Visión y herramientas --------------------------------------------------------------


def test_las_herramientas_leen_el_alcance_actual():
    """ve_tripulante usa el alcance de la partida: a 9 casillas solo lo ve con alcance 10."""
    resultados = {}
    for alcance in (ALCANCE_VISION, 10):
        partida = Partida(semilla=0, mapa=pasillo(), alcance_vision=alcance)
        colocar(partida.env, alien=(1, 1), tripulante=(10, 1))
        resultados[alcance] = crear_herramientas(partida)["ve_tripulante"]()["ve"]
    assert resultados == {ALCANCE_VISION: False, 10: True}


def test_dificil_usa_alcance_10_en_toda_la_sesion():
    """En difícil la partida de la directora tiene alcance 10 y paso extra cada 3 ticks."""
    sesion = Sesion(semilla=42, config=ConfigLLM(), nivel="dificil")
    partida = sesion.directora.partida
    assert partida.env.alcance_vision == 10 and partida.alien.paso_extra_cada == 3
    assert sesion.estado()["alcance_vision"] == 10


# --- Pista automática (pesadilla) -------------------------------------------------------


def test_pesadilla_da_pista_tras_25_ticks_sin_verlo():
    """Semilla 42: no lo ve en los primeros 25 ticks y en el 25 llega la pista a su sala real."""
    sesion = Sesion(semilla=42, config=ConfigLLM(), nivel="pesadilla")
    for _ in range(25):
        sesion.paso()
    textos = [r["texto"] for r in sesion.registro]
    assert not any("vio al tripulante" in t for t in textos)
    sala_real = sesion.directora.partida.nombre_sala(sesion.directora.partida.ultima_sala_tripulante())
    assert f"tick 25: directora automática: pista hacia {sala_real}" in textos
    estado = sesion.estado()
    assert estado["pistas_auto_restantes"] == 2 and estado["pistas_auto_max"] == 3
    assert estado["pistas_restantes"] == PISTAS_POR_PARTIDA


def test_pista_automatica_como_maximo_3():
    """Sin verlo nunca, da una pista cada 25 ticks y se detiene en 3."""
    partida = Partida(semilla=42)
    regla = PistaAutomatica(partida, ticks_sin_ver=25, maximo=3)
    dadas = [t for t in range(1, 201) if regla(partida.env, {"ve_tripulante": False})]
    assert dadas == [25, 50, 75] and regla.restantes == 0
    # Verlo reinicia la cuenta.
    regla = PistaAutomatica(partida, ticks_sin_ver=25, maximo=3)
    for _ in range(24):
        regla(partida.env, {"ve_tripulante": False})
    regla(partida.env, {"ve_tripulante": True})
    assert regla(partida.env, {"ve_tripulante": False}) == [] and regla.sin_ver == 1


def test_pistas_automaticas_no_gastan_las_de_la_directora():
    """Con las 3 automáticas usadas, la directora conserva y puede gastar sus 3."""
    partida = Partida(semilla=42)
    regla = PistaAutomatica(partida, ticks_sin_ver=1, maximo=3)
    for _ in range(5):
        regla(partida.env, {"ve_tripulante": False})
    assert regla.restantes == 0 and partida.alien.pistas_restantes == PISTAS_POR_PARTIDA
    dar_pista = crear_herramientas(partida)["dar_pista"]
    assert [dar_pista("Hangar")["pistas_restantes"] for _ in range(3)] == [2, 1, 0]
    # Y al revés: sin pistas de la directora, la automática sigue funcionando.
    regla = PistaAutomatica(partida, ticks_sin_ver=1, maximo=1)
    assert regla(partida.env, {"ve_tripulante": False})[0].startswith("directora automática")


def test_la_directora_avanza_con_la_regla_automatica():
    """Los ticks que avanza la directora (avanzar_simulacion) también cuentan para la regla."""
    sesion = Sesion(semilla=42, config=ConfigLLM(), nivel="pesadilla")
    herramientas = crear_herramientas(sesion.directora.partida)
    eventos = herramientas["avanzar_simulacion"](20)["eventos"] + herramientas["avanzar_simulacion"](5)["eventos"]
    assert any("directora automática: pista hacia" in e for e in eventos)


# --- Selector en el servidor ------------------------------------------------------------


def test_selector_reinicia_con_la_misma_semilla():
    """Cambiar el nivel reinicia la partida con la misma semilla; sin nivel se conserva."""
    pedir, srv = levantar(Sesion(semilla=7, config=ConfigLLM()))
    try:
        for _ in range(4):
            pedir("/api/paso", {})
        codigo, estado = pedir("/api/reiniciar", {"semilla": 7, "nivel": "dificil"})
        nuevo = Sesion(semilla=7, config=ConfigLLM()).estado()
        assert codigo == 200 and estado["tick"] == 0 and estado["semilla"] == 7
        assert estado["nivel"] == "dificil" and estado["nivel_texto"] == "Difícil"
        assert estado["alcance_vision"] == 10
        assert (estado["tripulante"], estado["alien"]["x"], estado["alien"]["y"]) == \
               (nuevo["tripulante"], nuevo["alien"]["x"], nuevo["alien"]["y"])
        assert pedir("/api/estado")[1]["nivel"] == "dificil"
        assert pedir("/api/reiniciar", {"semilla": 8})[1]["nivel"] == "dificil"
        codigo, cuerpo = pedir("/api/reiniciar", {"semilla": 7, "nivel": "imposible"})
        assert codigo == 409 and "Nivel desconocido" in cuerpo["error"]
        assert pedir("/api/reiniciar", {"semilla": 7, "nivel": "normal"})[1]["nivel"] == "normal"
    finally:
        srv.shutdown()
        srv.server_close()


def test_la_pagina_tiene_el_selector():
    """La página trae un botón por nivel y muestra el nivel en la etiqueta del mapa."""
    from panel.servidor import PAGINA
    pagina = PAGINA.read_text(encoding="utf-8")
    for clave in NIVELES:
        assert f'data-nivel="{clave}"' in pagina
    assert "E.nivel_texto" in pagina and "Dificultad" in pagina
