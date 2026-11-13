"""Funciones de las 6 herramientas que la directora puede pedir al modelo (T11).

Cada herramienta es una función de Python con los parámetros exactos de su esquema en
director/esquemas.py, ligada a una Partida. Todas devuelven diccionarios serializables
a JSON. Los errores esperables (sala inexistente, sin camino, ticks fuera de rango, sin
pistas) se lanzan como ValueError con un mensaje claro en español; ejecutar_agente los
convierte en {"error": ...} para el modelo.

Los nombres de sala se comparan sin mayúsculas ni tildes con Mapa.indice_sala (D14),
pero nunca se cambian por uno parecido (D12).

Contenido principal:
    crear_herramientas: diccionario nombre -> función para una Partida.
    PERSONAJES_RUTA: valores especiales de origen y destino en ruta_mas_corta.
    NOMBRES_DIRECCION: nombre en español de cada dirección del alienígena.

Tareas relacionadas: T11 (herramientas), T13 (esquemas), T08 (visión), T09 (A*), T10
(avance), T12 (predecir_destino), T19 (pistas).
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from director.partida import Partida
from sim.mapa import DIRS, SIN_SALA, normalizar_nombre
from sim.rutas import ruta, ruta_a_sala

# Valores especiales de origen y destino, ya normalizados (sin tildes ni mayúsculas):
# así "alienígena", "Alienigena" y "ALIENIGENA" son el mismo personaje.
PERSONAJES_RUTA = ("tripulante", "alienigena")
# Nombre de cada dirección de DIRS, en el mismo orden (arriba, derecha, abajo, izquierda).
NOMBRES_DIRECCION = dict(zip(DIRS, ("arriba", "derecha", "abajo", "izquierda")))
# Entrada de camino_resumido para las casillas de puerta.
PUERTA = "puerta"

Casilla = tuple[int, int]


def crear_herramientas(partida: Partida) -> dict[str, Callable[..., dict]]:
    """Crea las 6 herramientas ligadas a una partida.

    Las funciones cierran sobre la partida, así el modelo no ve ningún parámetro extra:
    las firmas son exactamente las de director/esquemas.py.

    Args:
        partida: Partida que consultan y modifican las herramientas.

    Returns:
        Diccionario nombre -> función, con las claves de NOMBRES_HERRAMIENTAS.

    Example:
        >>> herramientas = crear_herramientas(Partida(semilla=42))
        >>> herramientas["ruta_mas_corta"]("alienigena", "tripulante")
        {'pasos': 15, 'camino_resumido': ['Médico', 'puerta', 'Corredor A', 'puerta', 'Bodega']}
        >>> herramientas["dar_pista"]("bodega")
        {'sala': 'Bodega', 'pistas_restantes': 2}
    """
    mapa = partida.env.mapa

    def estado_partida() -> dict:
        """Estado actual: tick, posiciones y salas, dirección del alienígena, pistas y captura."""
        env = partida.env
        return {
            "tick": env.tick,
            "tripulante": {"x": env.tripulante[0], "y": env.tripulante[1],
                           "sala": partida.nombre_sala(partida.ultima_sala_tripulante())},
            "alienigena": {"x": env.alien[0], "y": env.alien[1],
                           "sala": partida.nombre_sala(partida.ultima_sala_alien()),
                           "direccion": NOMBRES_DIRECCION[env.direccion_alien]},
            "pistas_restantes": partida.alien.pistas_restantes,
            # Misma regla de captura del entorno: distancia Manhattan de 1 o menos.
            "capturado": env._captura(),
        }

    def ruta_mas_corta(origen: str, destino: str) -> dict:
        """Pasos y salas por las que pasa la ruta más corta entre dos salas o personajes."""
        camino = _camino(partida, _extremo(partida, origen), _extremo(partida, destino))
        if camino is None:
            raise ValueError(f"No hay camino entre '{origen}' y '{destino}'.")
        return {"pasos": len(camino) - 1, "camino_resumido": _resumir(partida, camino)}

    def predecir_destino() -> dict:
        """Sala hacia la que parece ir el tripulante según sus últimos 10 ticks."""
        return partida.predictor.predecir(partida.env.trayectoria)

    def ve_tripulante() -> dict:
        """Si el alienígena ve ahora al tripulante y a cuántos pasos está."""
        env = partida.env
        camino = ruta(mapa, env.alien, env.tripulante)
        return {
            "ve": bool(env.campo_vision[env.tripulante[1], env.tripulante[0]]),
            "distancia_casillas": None if camino is None else len(camino) - 1,
        }

    def dar_pista(sala: str) -> dict:
        """Indica al alienígena una sala donde buscar; gasta una de las 3 pistas."""
        # Se resuelve aquí para aceptar "medico" o "corredor a" (D14); AlienReglas recibe
        # el nombre canónico y es quien revisa el presupuesto de pistas.
        return partida.alien.dar_pista(mapa.nombres_salas[mapa.indice_sala(sala)])

    def avanzar_simulacion(ticks: int) -> dict:
        """Avanza la partida de 1 a 20 ticks y devuelve los eventos ocurridos."""
        return partida.avanzar(ticks)

    return {
        "estado_partida": estado_partida,
        "ruta_mas_corta": ruta_mas_corta,
        "predecir_destino": predecir_destino,
        "ve_tripulante": ve_tripulante,
        "dar_pista": dar_pista,
        "avanzar_simulacion": avanzar_simulacion,
    }


def _extremo(partida: Partida, nombre: str) -> tuple[str, Any]:
    """Interpreta un origen o destino: ("casilla", (x, y)) o ("sala", índice).

    Raises:
        ValueError: Si no es un personaje ni una sala; el mensaje lista las opciones.
    """
    normalizado = normalizar_nombre(nombre)
    if normalizado == PERSONAJES_RUTA[0]:
        return "casilla", partida.env.tripulante
    if normalizado == PERSONAJES_RUTA[1]:
        return "casilla", partida.env.alien
    try:
        return "sala", partida.env.mapa.indice_sala(nombre)
    except ValueError as exc:
        raise ValueError(f"{exc} También se aceptan 'tripulante' y 'alienigena'.") from None


def _camino(partida: Partida, origen: tuple[str, Any],
            destino: tuple[str, Any]) -> list[Casilla] | None:
    """Camino más corto entre dos extremos, de origen a destino.

    De sala a sala se prueba ruta_a_sala desde cada casilla transitable de la sala de
    origen y se queda el más corto; en un empate gana la primera casilla en el orden de
    mapa.transitables. Cuesta una búsqueda por casilla de la sala (36 como máximo en
    vela9), unos milisegundos.
    """
    mapa = partida.env.mapa
    (tipo_o, valor_o), (tipo_d, valor_d) = origen, destino
    if tipo_o == "casilla" and tipo_d == "casilla":
        return ruta(mapa, valor_o, valor_d)
    if tipo_o == "casilla":
        return ruta_a_sala(mapa, valor_o, valor_d)
    if tipo_d == "casilla":
        # El camino de la casilla a la sala, al revés, tiene el mismo largo.
        camino = ruta_a_sala(mapa, valor_d, valor_o)
        return None if camino is None else camino[::-1]
    mejor = None
    for casilla in mapa.transitables:
        if mapa.sala(*casilla) != valor_o:
            continue
        camino = ruta_a_sala(mapa, casilla, valor_d)
        if camino is not None and (mejor is None or len(camino) < len(mejor)):
            mejor = camino
    return mejor


def _resumir(partida: Partida, camino: list[Casilla]) -> list[str]:
    """Salas y puertas por las que pasa el camino, en orden y sin repetidos seguidos."""
    mapa = partida.env.mapa
    resumen: list[str] = []
    for x, y in camino:
        sala = mapa.sala(x, y)
        nombre = PUERTA if sala == SIN_SALA else mapa.nombres_salas[sala]
        if not resumen or resumen[-1] != nombre:
            resumen.append(nombre)
    return resumen
