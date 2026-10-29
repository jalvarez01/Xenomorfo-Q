"""Pruebas de las salas explícitas del mapa (T15)."""
import pytest

from sim import Mapa
from sim.env import MAPA_POR_DEFECTO

NOMBRES_VELA9 = ["Médico", "Laboratorio", "Comunicaciones", "Corredor A", "Corredor B",
                 "Bodega", "Reactor", "Hangar"]

# Mapa pequeño con dos salas separadas por una puerta, base de los casos inválidos.
MAPA = ["#######",
        "#..+..#",
        "#######"]
SALAS = ["#######",
         "#00+11#",
         "#######"]


@pytest.fixture(scope="module")
def vela9() -> Mapa:
    """Mapa por defecto cargado una sola vez para todas las pruebas."""
    return Mapa.desde_archivo(MAPA_POR_DEFECTO)


def test_vela9_tiene_ocho_salas_con_nombre(vela9):
    """vela9 carga 8 salas con los nombres de su archivo de anotación."""
    assert vela9.n_salas == 8
    assert vela9.nombres_salas == NOMBRES_VELA9


@pytest.mark.parametrize("casilla, esperada", [
    ((1, 1), 0), ((8, 1), 1), ((16, 1), 2), ((9, 5), 3), ((13, 5), 4),
    ((1, 10), 5), ((7, 10), 6), ((17, 10), 7),
    ((7, 3), -1), ((0, 0), -1), ((-1, 3), -1), ((24, 3), -1),
])
def test_vela9_salas_conocidas(vela9, casilla, esperada):
    """Casillas conocidas devuelven su sala; puertas, paredes y fuera del mapa dan -1."""
    assert vela9.sala(*casilla) == esperada


def test_vela9_toda_casilla_caminable_o_casillero_tiene_sala(vela9):
    """Todo piso y todo casillero de vela9 pertenece a alguna sala."""
    for y in range(vela9.alto):
        for x in range(vela9.ancho):
            if vela9.filas[y][x] in ".L":
                assert vela9.sala(x, y) >= 0, (x, y)


def test_vela9_casillero_pertenece_a_su_sala(vela9):
    """El casillero de Comunicaciones en (20, 2) tiene la sala 2."""
    assert vela9.es_casillero(20, 2) and vela9.sala(20, 2) == 2


def test_anotacion_valida_minima():
    """El mapa pequeño de referencia carga sus dos salas sin errores."""
    m = Mapa(MAPA, SALAS, ["A", "B"])
    assert (m.sala(1, 1), m.sala(3, 1), m.sala(5, 1)) == (0, -1, 1)


@pytest.mark.parametrize("salas, nombres", [
    (["#######", "#00+11#"], ["A", "B"]),                    # tamaño distinto
    (["#######", "#00+11", "#######"], ["A", "B"]),           # fila más corta
    (["##0####", "#00+11#", "#######"], ["A", "B"]),          # dígito en pared
    (["#######", "#0.+11#", "#######"], ["A", "B"]),          # falta dígito en piso
    (["#######", "#00011#", "#######"], ["A", "B"]),          # dígito en puerta
    (["#######", "#00+12#", "#######"], ["A", "B"]),          # índice sin nombre
    (["#######", "#00+00#", "#######"], ["A", "B"]),          # sala 1 sin usar
    (["#######", "#00+11#", "#######"], None),                # sin nombres
])
def test_anotacion_invalida(salas, nombres):
    """Una anotación con tamaño, símbolos, índices o nombres incorrectos lanza ValueError."""
    with pytest.raises(ValueError):
        Mapa(MAPA, salas, nombres)


def test_sala_desconectada():
    """Una sala partida en dos bloques sin conexión propia lanza ValueError."""
    with pytest.raises(ValueError, match="no está conectada"):
        Mapa(["#####", "#.#.#", "#####"], ["#####", "#0#0#", "#####"], ["A"])


def test_sala_unida_solo_por_puerta_esta_desconectada():
    """Dos bloques de la misma sala unidos solo por una puerta no cuentan como conectados."""
    with pytest.raises(ValueError, match="no está conectada"):
        Mapa(MAPA, ["#######", "#00+00#", "#######"], ["A"])


def test_mapa_sin_archivo_de_salas(tmp_path):
    """Un mapa sin archivo de salas carga con n_salas 0 y sala() devuelve -1."""
    ruta = tmp_path / "chico.txt"
    ruta.write_text("\n".join(MAPA) + "\n", encoding="utf-8")
    m = Mapa.desde_archivo(ruta)
    assert m.n_salas == 0 and m.nombres_salas == []
    assert m.sala(1, 1) == -1


def test_archivo_de_salas_explicito(tmp_path):
    """desde_archivo usa ruta_salas cuando se pasa, aunque tenga otro nombre."""
    ruta = tmp_path / "chico.txt"
    ruta.write_text("\n".join(MAPA) + "\n", encoding="utf-8")
    anotacion = tmp_path / "otra.txt"
    anotacion.write_text("nombres: A, B\n" + "\n".join(SALAS) + "\n", encoding="utf-8")
    m = Mapa.desde_archivo(ruta, ruta_salas=anotacion)
    assert m.nombres_salas == ["A", "B"] and m.sala(4, 1) == 1


def test_archivo_de_salas_sin_nombres(tmp_path):
    """Un archivo de salas sin la línea 'nombres:' lanza ValueError."""
    ruta = tmp_path / "chico.txt"
    ruta.write_text("\n".join(MAPA) + "\n", encoding="utf-8")
    (tmp_path / "chico_salas.txt").write_text("\n".join(SALAS) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="nombres:"):
        Mapa.desde_archivo(ruta)
