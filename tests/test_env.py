"""Pruebas del entorno mínimo de la estación y de la carga de mapas (T06, T10)."""
import numpy as np
import pytest

from sim import EstacionEnv, Mapa


def jugar(env: EstacionEnv, semilla: int, acciones: list[int]) -> list[tuple]:
    """Juega una partida con acciones fijas y devuelve el estado tras cada paso.

    Args:
        env: Entorno a usar.
        semilla: Semilla para reset().
        acciones: Acciones a aplicar en orden; se detiene si el episodio termina.

    Returns:
        Lista de tuplas (alien, tripulante, recompensa, terminado), una por paso.
    """
    env.reset(semilla)
    pasos = []
    for a in acciones:
        obs, r, fin, info = env.step(a)
        pasos.append((env.alien, env.tripulante, r, fin))
        if fin:
            break
    return pasos


def test_misma_semilla_misma_partida():
    """Con la misma semilla y las mismas acciones, la partida se repite igual."""
    acciones = [0, 1, 2, 3, 1, 1, 2, 0] * 10
    assert jugar(EstacionEnv(), 7, acciones) == jugar(EstacionEnv(), 7, acciones)


def test_observacion_forma_y_tipo():
    """La observación tiene 4 capas float32, un alien one-hot y creencia que suma 1."""
    env = EstacionEnv()
    obs = env.reset(1)
    assert obs.shape == (4, env.mapa.alto, env.mapa.ancho)
    assert obs.dtype == np.float32
    assert obs[2].sum() == 1.0
    assert np.isclose(obs[1].sum(), 1.0)


def test_no_atraviesa_paredes():
    """Ni el alienígena ni el tripulante terminan en paredes o casilleros."""
    env = EstacionEnv()
    env.reset(3)
    for _ in range(200):
        env.step(int(env.rng.integers(4)))
        assert env.mapa.es_transitable(*env.alien)
        assert env.mapa.es_transitable(*env.tripulante)


def test_captura_da_recompensa_y_termina():
    """Quedar contiguo al tripulante da 99 (100 - 1) y termina el episodio."""
    env = EstacionEnv()
    env.reset(0)
    env.alien, env.tripulante = (2, 1), (4, 1)
    _, r, fin, info = env.step(1)  # el alien avanza a (3, 1), adyacente
    assert info["capturado"] and fin and r == 99.0


def test_mapa_invalido():
    """Un símbolo desconocido en el mapa lanza ValueError."""
    with pytest.raises(ValueError):
        Mapa(["###", "#X#", "###"])
