"""Pruebas del alienígena por reglas y de las pistas con presupuesto (T18, T19).

Contenido principal:
    preparar: ubica al alienígena y al tripulante en un mapa pequeño, con la visión
        recalculada, para probar una decisión a la vez.
    EnvSinVista: entorno de prueba donde el alienígena nunca ve al tripulante, para
        probar la patrulla y las pistas sin que una persecución las interrumpa.

Tareas relacionadas: T18 (reglas), T19 (pistas), T10 (evento de pista en Avance).
"""
from __future__ import annotations

import json

import pytest

from alien.reglas import PATRULLA, PERSIGUE, PISTA, AlienReglas, centro_de_sala
from sim import EstacionEnv, Mapa
from sim.avance import Avance
from sim.percepcion import campo_de_vision

# Dos salas: A (x 1-4) y B (x 6-9), unidas por la puerta (5, 1).
MAPA = Mapa(["###########",
             "#....+....#",
             "#....#....#",
             "###########"],
            filas_salas=["###########",
                         "#0000+1111#",
                         "#0000#1111#",
                         "###########"],
            nombres_salas=["A", "B"])
DERECHA, IZQUIERDA = (1, 0), (-1, 0)


def preparar(alien: tuple[int, int], direccion: tuple[int, int],
             tripulante: tuple[int, int]) -> EstacionEnv:
    """Partida en MAPA con los personajes y la dirección elegidos y la visión al día."""
    env = EstacionEnv(MAPA)
    env.reset(semilla=0)
    env.alien = alien
    env.tripulante = tripulante
    env.trayectoria = [tripulante]
    mover_vista(env, direccion)
    return env


def mover_vista(env: EstacionEnv, direccion: tuple[int, int]) -> None:
    """Cambia hacia dónde mira el alienígena y recalcula lo que ve."""
    env.direccion_alien = direccion
    env.campo_vision = campo_de_vision(env.mapa, env.alien, direccion)


class EnvSinVista(EstacionEnv):
    """Entorno de prueba: el alienígena nunca ve al tripulante."""

    def reset(self, semilla=None):
        """Igual que el entorno, con el campo de visión vacío."""
        obs = super().reset(semilla)
        self.campo_vision[:] = False
        return obs

    def step(self, accion):
        """Igual que el entorno, con el campo de visión vacío."""
        resultado = super().step(accion)
        self.campo_vision[:] = False
        return resultado


# --- Árbol de decisión ------------------------------------------------------------------


def test_centro_de_sala():
    """El centro es la casilla transitable más cercana al promedio de la sala."""
    assert centro_de_sala(MAPA, 0) == (2, 1)
    assert centro_de_sala(MAPA, 1) == (7, 1)


def test_si_lo_ve_lo_persigue():
    """Si el tripulante está en su campo de visión, da el paso hacia él."""
    env = preparar(alien=(3, 1), direccion=DERECHA, tripulante=(8, 1))
    alien = AlienReglas(env)
    assert alien.decidir() == 1  # derecha
    assert alien.estado == PERSIGUE
    assert alien.ultima_vista == (8, 1)


def test_si_no_lo_ve_patrulla():
    """Sin verlo y sin pista, va al centro de su sala para empezar la patrulla."""
    env = preparar(alien=(1, 1), direccion=IZQUIERDA, tripulante=(8, 2))
    alien = AlienReglas(env)
    assert alien.decidir() == 1  # hacia el centro de A, (2, 1)
    assert alien.estado == PATRULLA


def test_no_hace_trampa():
    """Si no lo ve, la decisión no depende de dónde está el tripulante."""
    acciones = []
    for tripulante in [(8, 2), (9, 1), (6, 2)]:
        env = preparar(alien=(1, 1), direccion=IZQUIERDA, tripulante=tripulante)
        assert not env.campo_vision[tripulante[1], tripulante[0]]
        acciones.append(AlienReglas(env).decidir())
    assert acciones == [acciones[0]] * 3


def test_si_lo_pierde_va_a_la_ultima_casilla_donde_lo_vio():
    """Después de perderlo de vista, sigue hacia la última casilla donde lo vio."""
    env = preparar(alien=(3, 1), direccion=DERECHA, tripulante=(8, 1))
    alien = AlienReglas(env)
    alien.decidir()  # lo ve en (8, 1)
    env.tripulante = (9, 2)
    mover_vista(env, IZQUIERDA)  # ya no lo ve
    assert alien.decidir() == 1  # sigue hacia (8, 1)
    assert alien.estado == PERSIGUE


def test_si_llega_a_la_ultima_casilla_y_no_esta_patrulla():
    """Al llegar a la última casilla donde lo vio sin encontrarlo, vuelve a patrullar."""
    env = preparar(alien=(3, 1), direccion=IZQUIERDA, tripulante=(9, 2))
    alien = AlienReglas(env)
    alien.ultima_vista = (3, 1)
    alien.decidir()
    assert alien.ultima_vista is None
    assert alien.estado == PATRULLA


# --- Pistas (T19) -----------------------------------------------------------------------


def test_con_pista_va_a_esa_sala():
    """Con una pista vigente y sin ver al tripulante, va hacia el centro de esa sala."""
    env = preparar(alien=(1, 1), direccion=IZQUIERDA, tripulante=(8, 2))
    alien = AlienReglas(env)
    assert alien.dar_pista("B") == {"sala": "B", "pistas_restantes": 2}
    assert alien.decidir() == 1  # hacia (7, 1)
    assert alien.estado == PISTA
    assert alien.pista_activa == "B"


def test_verlo_tiene_prioridad_sobre_la_pista():
    """Si lo ve, lo persigue aunque haya pista; la pista sigue vigente para después."""
    env = preparar(alien=(3, 1), direccion=DERECHA, tripulante=(8, 1))
    alien = AlienReglas(env)
    alien.dar_pista("A")  # A queda a la izquierda; el tripulante, a la derecha
    assert alien.decidir() == 1
    assert alien.estado == PERSIGUE
    assert alien.pista_activa == "A"


def test_al_llegar_a_la_sala_de_la_pista_se_cumple():
    """En el paso que llega al centro de la sala, la pista se cumple y deja un evento."""
    env = preparar(alien=(6, 1), direccion=IZQUIERDA, tripulante=(9, 2))
    alien = AlienReglas(env)
    alien.dar_pista("B")
    assert alien.decidir() == 1  # de (6, 1) a (7, 1), el centro de B
    assert alien.pista_activa is None
    assert alien.tomar_eventos() == ["el alienígena llegó a B, la sala de la pista"]
    assert alien.tomar_eventos() == []


def test_pista_dada_estando_en_el_centro():
    """Si ya está en el centro de la sala de la pista, se cumple de inmediato."""
    env = preparar(alien=(7, 1), direccion=IZQUIERDA, tripulante=(9, 2))
    alien = AlienReglas(env)
    alien.dar_pista("B")
    alien.decidir()
    assert alien.pista_activa is None
    assert alien.estado == PATRULLA


def test_maximo_tres_pistas():
    """Se pueden dar 3 pistas; la cuarta da un error claro y no cambia nada."""
    alien = AlienReglas(preparar(alien=(1, 1), direccion=IZQUIERDA, tripulante=(8, 2)))
    restantes = [alien.dar_pista(s)["pistas_restantes"] for s in ["A", "B", "A"]]
    assert restantes == [2, 1, 0]
    with pytest.raises(ValueError, match="No quedan pistas"):
        alien.dar_pista("B")
    assert alien.pistas_restantes == 0
    assert alien.pista_activa == "A"


def test_sala_inexistente():
    """Una sala que no existe da un error con las salas válidas y no gasta pista."""
    alien = AlienReglas(preparar(alien=(1, 1), direccion=IZQUIERDA, tripulante=(8, 2)))
    with pytest.raises(ValueError, match="La sala 'Enfermería' no existe. Salas válidas: A, B"):
        alien.dar_pista("Enfermería")
    assert alien.pistas_restantes == 3
    assert alien.pista_activa is None


def test_nombre_sin_importar_mayusculas_ni_espacios():
    """La sala se reconoce sin importar mayúsculas ni espacios en los extremos."""
    alien = AlienReglas(preparar(alien=(1, 1), direccion=IZQUIERDA, tripulante=(8, 2)))
    assert alien.dar_pista("  b ")["sala"] == "B"


def test_una_pista_nueva_reemplaza_la_anterior():
    """La última pista dada es la que sigue."""
    alien = AlienReglas(preparar(alien=(1, 1), direccion=IZQUIERDA, tripulante=(8, 2)))
    alien.dar_pista("A")
    alien.dar_pista("B")
    assert alien.pista_activa == "B"


def test_resultado_de_dar_pista_serializable():
    """El resultado de dar_pista se puede enviar al modelo con json.dumps."""
    alien = AlienReglas(preparar(alien=(1, 1), direccion=IZQUIERDA, tripulante=(8, 2)))
    r = alien.dar_pista("B")
    assert json.loads(json.dumps(r, ensure_ascii=False)) == r


def test_mapa_sin_salas():
    """Sin salas no hay centros que patrullar ni pistas posibles."""
    env = EstacionEnv(Mapa(["#####", "#...#", "#####"]), distancia_inicial=1)
    env.reset(semilla=0)
    with pytest.raises(ValueError, match="no tiene salas"):
        AlienReglas(env)


# --- vela9 ------------------------------------------------------------------------------


def test_vela9_patrulla_visita_todas_las_salas():
    """Sin ver nunca al tripulante, la patrulla pasa por el centro de las 8 salas."""
    env = EnvSinVista(max_ticks=400)
    env.reset(semilla=1)
    alien = AlienReglas(env)
    visitadas = set()
    for _ in range(400):
        if env.alien in alien.centros:
            visitadas.add(alien.centros.index(env.alien))
        _, _, terminado, _ = env.step(alien.decidir())
        if terminado:
            break
    assert visitadas == set(range(8))


def test_vela9_evento_de_pista_en_avance():
    """Avance registra la llegada a la sala de la pista en el tick en que llega al centro."""
    env = EnvSinVista()
    env.reset(semilla=4)
    alien = AlienReglas(env)
    alien.dar_pista("Hangar")
    avance = Avance(env, alien)
    centro = alien.centros[env.mapa.nombres_salas.index("Hangar")]
    for _ in range(100):
        r = avance.avanzar(1)
        if any("la sala de la pista" in e for e in r["eventos"]):
            assert env.alien == centro
            assert f"tick {env.tick}: el alienígena llegó a Hangar, la sala de la pista" in r["eventos"]
            return
        if r["capturado"]:
            pytest.fail("Hubo captura antes de llegar a la sala de la pista.")
    pytest.fail("Nunca llegó a la sala de la pista.")


def test_vela9_captura_en_la_mayoria_de_partidas():
    """Con la visión real y Avance, el alienígena captura en la mayoría de 20 partidas."""
    capturas = 0
    for semilla in range(20):
        env = EstacionEnv()
        env.reset(semilla)
        alien = AlienReglas(env)
        avance = Avance(env, alien)
        while env.tick < env.max_ticks:
            r = avance.avanzar(20)
            assert alien.estado in (PERSIGUE, PISTA, PATRULLA)
            if r["capturado"]:
                capturas += 1
                break
    # Hoy son 18 de 20; el margen evita que un cambio menor del bot rompa la prueba.
    assert capturas >= 15
