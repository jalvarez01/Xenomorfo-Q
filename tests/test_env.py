import numpy as np
import pytest

from sim import EstacionEnv, Mapa


def jugar(env, semilla, acciones):
    env.reset(semilla)
    pasos = []
    for a in acciones:
        obs, r, fin, info = env.step(a)
        pasos.append((env.alien, env.tripulante, r, fin))
        if fin:
            break
    return pasos


def test_misma_semilla_misma_partida():
    acciones = [0, 1, 2, 3, 1, 1, 2, 0] * 10
    assert jugar(EstacionEnv(), 7, acciones) == jugar(EstacionEnv(), 7, acciones)


def test_observacion_forma_y_tipo():
    env = EstacionEnv()
    obs = env.reset(1)
    assert obs.shape == (4, env.mapa.alto, env.mapa.ancho)
    assert obs.dtype == np.float32
    assert obs[2].sum() == 1.0
    assert np.isclose(obs[1].sum(), 1.0)


def test_no_atraviesa_paredes():
    env = EstacionEnv()
    env.reset(3)
    for _ in range(200):
        env.step(int(env.rng.integers(4)))
        assert env.mapa.es_transitable(*env.alien)
        assert env.mapa.es_transitable(*env.tripulante)


def test_captura_da_recompensa_y_termina():
    env = EstacionEnv()
    env.reset(0)
    env.alien, env.tripulante = (2, 1), (4, 1)
    _, r, fin, info = env.step(1)  # el alien avanza a (3, 1), adyacente
    assert info["capturado"] and fin and r == 99.0


def test_mapa_invalido():
    with pytest.raises(ValueError):
        Mapa(["###", "#X#", "###"])
