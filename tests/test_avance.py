"""Pruebas del avance de la simulación con registro de eventos (T10).

Contenido principal:
    EnvGuionado: entorno de prueba donde el tripulante sigue un recorrido fijo y la
        visión del alienígena se lee de una lista (la visión real llega en T08).
    Políticas simples del alienígena: siempre a la derecha, quieto y acciones en orden.

Tareas relacionadas: T10 (avance y eventos).
"""
from __future__ import annotations

import json

import pytest

from sim import EstacionEnv, Mapa
from sim.avance import TOPE_TICKS, Avance

# Dos salas en línea: A (x 1-4) y B (x 6-14), separadas por la puerta (5, 1).
MAPA = Mapa(["################",
             "#....+.........#",
             "################"],
            filas_salas=["################",
                         "#0000+111111111#",
                         "################"],
            nombres_salas=["A", "B"])


class EnvGuionado(EstacionEnv):
    """Entorno de prueba: el tripulante sigue un recorrido fijo y la visión es una lista.

    Args:
        recorrido: Casillas a las que se mueve el tripulante, una por tick; cuando se
            acaban, se queda quieto.
        vision: Valor de info["ve_tripulante"] en cada tick (el primero es el tick 1).
            None para no informar visión, como el entorno actual.
        max_ticks: Ticks máximos de la partida.
    """

    def __init__(self, recorrido=None, vision=None, max_ticks=300):
        super().__init__(MAPA, max_ticks=max_ticks)
        self.recorrido = list(recorrido or [])
        self.vision = vision

    def _paso_tripulante(self):
        """Siguiente casilla del recorrido, o la actual si ya no quedan."""
        if len(self.recorrido) > 0:
            return self.recorrido.pop(0)
        return self.tripulante

    def step(self, accion):
        """Igual que el entorno, y agrega ve_tripulante si hay lista de visión."""
        obs, recompensa, terminado, info = super().step(accion)
        if self.vision is not None:
            info["ve_tripulante"] = self.vision[info["tick"] - 1]
        return obs, recompensa, terminado, info


def partida(env: EstacionEnv, alien: tuple[int, int], tripulante: tuple[int, int]) -> EstacionEnv:
    """Inicia la partida y ubica a los dos personajes en casillas elegidas."""
    env.reset(semilla=0)
    env.alien = alien
    env.tripulante = tripulante
    env.trayectoria = [tripulante]
    return env


def derecha(env):
    """Política de prueba: el alienígena siempre se mueve a la derecha."""
    return 1


def quieto(env):
    """Política de prueba: el alienígena revisa un casillero, así que no se mueve."""
    return 4


def en_orden(*acciones):
    """Política de prueba que devuelve las acciones dadas, una por tick."""
    pendientes = list(acciones)

    def politica(env):
        return pendientes.pop(0)

    return politica


# --- Eventos ----------------------------------------------------------------------------


def test_alien_entra_a_otra_sala():
    """Al cruzar la puerta y entrar a B, se registra el tick en que entró."""
    env = partida(EnvGuionado(), alien=(3, 1), tripulante=(14, 1))
    r = Avance(env, derecha).avanzar(3)
    assert r == {"tick": 3, "ticks_avanzados": 3,
                 "eventos": ["tick 3: el alienígena entró a B"], "capturado": False}


def test_pisar_la_puerta_y_volver_no_es_evento():
    """Entrar a una puerta y regresar a la misma sala no cuenta como cambio de sala."""
    env = partida(EnvGuionado(), alien=(4, 1), tripulante=(14, 1))
    r = Avance(env, en_orden(1, 3)).avanzar(2)  # derecha a la puerta, izquierda de vuelta
    assert r["eventos"] == []


def test_tripulante_entra_a_otra_sala():
    """El tripulante pasa de B a A por la puerta y se registra al llegar a A."""
    env = partida(EnvGuionado(recorrido=[(6, 1), (5, 1), (4, 1)]),
                  alien=(14, 1), tripulante=(7, 1))
    r = Avance(env, quieto).avanzar(3)
    assert r["eventos"] == ["tick 3: el tripulante entró a A"]


def test_captura_detiene_el_avance():
    """Si hay captura, se detiene antes de completar los ticks pedidos."""
    env = partida(EnvGuionado(), alien=(3, 1), tripulante=(5, 1))
    r = Avance(env, derecha).avanzar(10)
    assert r == {"tick": 1, "ticks_avanzados": 1,
                 "eventos": ["tick 1: el alienígena capturó al tripulante"], "capturado": True}


def test_fin_por_tiempo():
    """Al llegar a max_ticks se detiene y lo informa como evento."""
    env = partida(EnvGuionado(max_ticks=3), alien=(1, 1), tripulante=(14, 1))
    r = Avance(env, quieto).avanzar(5)
    assert r["ticks_avanzados"] == 3
    assert r["eventos"] == ["tick 3: se acabó el tiempo de la partida (3 ticks)"]
    assert r["capturado"] is False


def test_vio_y_perdio_de_vista():
    """Con visión en info, se registra cuándo lo vio y cuándo lo perdió."""
    env = partida(EnvGuionado(vision=[False, True, True, False]),
                  alien=(1, 1), tripulante=(14, 1))
    r = Avance(env, quieto).avanzar(4)
    assert r["eventos"] == ["tick 2: el alienígena vio al tripulante",
                            "tick 4: el alienígena perdió de vista al tripulante"]


def test_la_vision_se_recuerda_entre_llamadas():
    """Si lo veía al final de una llamada, en la siguiente solo se informa cuando lo pierde."""
    env = partida(EnvGuionado(vision=[True, True, False]), alien=(1, 1), tripulante=(14, 1))
    avance = Avance(env, quieto)
    assert avance.avanzar(1)["eventos"] == ["tick 1: el alienígena vio al tripulante"]
    assert avance.avanzar(2)["eventos"] == ["tick 3: el alienígena perdió de vista al tripulante"]


def test_sin_vision_no_hay_eventos_de_vista():
    """Mientras el entorno no informe ve_tripulante, no se inventan eventos de visión."""
    env = partida(EnvGuionado(), alien=(1, 1), tripulante=(14, 1))
    assert Avance(env, quieto).avanzar(5)["eventos"] == []


def test_historial_acumula_todas_las_llamadas():
    """historial guarda los eventos de toda la partida; cada resultado, solo los suyos."""
    env = partida(EnvGuionado(recorrido=[(6, 1), (5, 1), (4, 1)]),
                  alien=(1, 1), tripulante=(7, 1))
    avance = Avance(env, quieto)
    primero = avance.avanzar(3)
    segundo = avance.avanzar(2)
    assert primero["eventos"] == ["tick 3: el tripulante entró a A"]
    assert segundo["eventos"] == []
    assert avance.historial == ["tick 3: el tripulante entró a A"]


def test_resultado_serializable_a_json():
    """El resultado se puede enviar al modelo con json.dumps sin conversiones."""
    env = partida(EnvGuionado(), alien=(3, 1), tripulante=(14, 1))
    r = Avance(env, derecha).avanzar(3)
    assert json.loads(json.dumps(r, ensure_ascii=False)) == r


# --- Límites y errores ------------------------------------------------------------------


def test_se_pueden_avanzar_20_ticks():
    """El tope es inclusivo: 20 ticks se aceptan."""
    env = partida(EnvGuionado(), alien=(1, 1), tripulante=(14, 1))
    assert Avance(env, quieto).avanzar(TOPE_TICKS)["ticks_avanzados"] == 20


@pytest.mark.parametrize("ticks", [0, -3, 21, 100, 2.5, "5", True])
def test_ticks_invalidos(ticks):
    """Fuera de 1 a 20, o si no es un entero, da un error claro sin avanzar la partida."""
    env = partida(EnvGuionado(), alien=(1, 1), tripulante=(14, 1))
    with pytest.raises(ValueError, match="ticks"):
        Avance(env, quieto).avanzar(ticks)
    assert env.tick == 0


def test_no_se_avanza_despues_de_una_captura():
    """Con la partida terminada por captura, avanzar de nuevo da un error claro."""
    env = partida(EnvGuionado(), alien=(3, 1), tripulante=(5, 1))
    avance = Avance(env, derecha)
    avance.avanzar(1)
    with pytest.raises(ValueError, match="capturado"):
        avance.avanzar(1)


def test_no_se_avanza_despues_del_tiempo():
    """Con la partida terminada por tiempo, avanzar de nuevo da un error claro."""
    env = partida(EnvGuionado(max_ticks=2), alien=(1, 1), tripulante=(14, 1))
    avance = Avance(env, quieto)
    avance.avanzar(2)
    with pytest.raises(ValueError, match="máximo de 2 ticks"):
        avance.avanzar(1)


def test_accion_invalida_de_la_politica():
    """Si la política devuelve una acción que no existe, el error del entorno llega claro."""
    env = partida(EnvGuionado(), alien=(1, 1), tripulante=(14, 1))
    with pytest.raises(ValueError, match="Acción fuera de rango"):
        Avance(env, en_orden(9)).avanzar(1)


# --- vela9 ------------------------------------------------------------------------------


def test_vela9_partida_completa():
    """En vela9 con el bot real, avanzar de a 20 ticks lleva la partida hasta el final."""
    env = EstacionEnv(max_ticks=100)
    env.reset(semilla=3)
    avance = Avance(env, derecha)
    ticks_totales = 0
    while env.tick < env.max_ticks:
        r = avance.avanzar(20)
        ticks_totales += r["ticks_avanzados"]
        for evento in r["eventos"]:
            assert evento.startswith("tick ")
        if r["capturado"]:
            break
    assert ticks_totales == env.tick
