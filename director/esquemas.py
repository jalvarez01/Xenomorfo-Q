"""Esquemas de las herramientas de la directora en formato "tools" de OpenAI.

El modelo solo ve estos esquemas, no el código de las herramientas: de sus descripciones
depende que elija bien qué herramienta pedir y con qué argumentos. Los nombres y
parámetros siguen el contrato de docs/contratos.md, sección 5.

Las salas son texto libre, sin enum (decisión D12): así un nombre inexistente llega
intacto a la herramienta, que responde con el error y las salas válidas.

Contenido principal:
    NOMBRES_HERRAMIENTAS: los 6 nombres del contrato, en orden.
    construir_esquemas: arma los 6 esquemas con los nombres de sala del mapa.
    validar_correspondencia: compara esquemas y funciones de Python con inspect.signature.

Tareas relacionadas: T13 (esquemas), T11 (funciones de las herramientas), T15 (ciclo del
agente), T16 (prompt de sistema).
"""
from __future__ import annotations

import inspect
from typing import Any, Callable

# Nombres de las herramientas del contrato, en el orden en que se presentan al modelo.
NOMBRES_HERRAMIENTAS = (
    "estado_partida",
    "ruta_mas_corta",
    "predecir_destino",
    "ve_tripulante",
    "dar_pista",
    "avanzar_simulacion",
)
# Valores especiales de origen y destino en ruta_mas_corta, además de los nombres de sala.
PERSONAJES = ("tripulante", "alienigena")
# Pistas que la directora puede dar en una partida (contrato 5.5).
PISTAS_POR_PARTIDA = 3
# Rango permitido de avanzar_simulacion, en ticks de simulación (contrato 5.6).
TICKS_MIN, TICKS_MAX = 1, 20

# Frase común de los parámetros de sala. Pide no corregir el nombre para que una sala
# inexistente llegue a la herramienta y se reporte (caso de prueba C5).
_SIN_CORREGIR = (
    "Pasa el nombre tal como lo dijo el usuario, sin corregirlo ni cambiarlo por otro "
    "parecido."
)


def _sin_parametros() -> dict:
    """Bloque "parameters" de una herramienta sin argumentos.

    Se omite "required" en vez de dejarlo vacío porque algunos validadores de JSON
    Schema (draft 4) rechazan un "required" sin elementos.
    """
    return {"type": "object", "properties": {}, "additionalProperties": False}


def _esquema(nombre: str, descripcion: str, parametros: dict) -> dict:
    """Envuelve una herramienta en el formato "tools" de OpenAI."""
    return {
        "type": "function",
        "function": {"name": nombre, "description": descripcion, "parameters": parametros},
    }


def construir_esquemas(nombres_salas: list[str]) -> list[dict]:
    """Construye los esquemas de las 6 herramientas de la directora.

    Los nombres de sala se incluyen en las descripciones de origen, destino y sala,
    no como enum, para que el modelo los conozca sin estar obligado a elegir uno.

    Args:
        nombres_salas: Nombres de las salas del mapa, por ejemplo Mapa.nombres_salas.

    Returns:
        Lista de 6 esquemas, en el orden de NOMBRES_HERRAMIENTAS.

    Raises:
        ValueError: Si nombres_salas está vacía.

    Example:
        >>> esquemas = construir_esquemas(["Médico", "Hangar"])
        >>> [e["function"]["name"] for e in esquemas][:2]
        ['estado_partida', 'ruta_mas_corta']
        >>> esquemas[5]["function"]["parameters"]["properties"]["ticks"]["maximum"]
        20
    """
    if not nombres_salas:
        raise ValueError("nombres_salas no puede estar vacía.")
    salas = ", ".join(nombres_salas)
    personajes = " o ".join(f'"{p}"' for p in PERSONAJES)

    def extremo_ruta(papel: str) -> dict:
        return {
            "type": "string",
            "description": (
                f"{papel}: nombre de una sala o {personajes}. Salas válidas: {salas}. "
                f"{_SIN_CORREGIR}"
            ),
        }

    return [
        _esquema(
            "estado_partida",
            "Devuelve el estado actual de la partida: tick, posición (x, y en casillas) y "
            "sala del tripulante y del alienígena, dirección del alienígena, "
            "pistas_restantes y capturado. Si un personaje está en una puerta, su sala es "
            "la última sala visitada. No cambia la partida.",
            _sin_parametros(),
        ),
        _esquema(
            "ruta_mas_corta",
            "Calcula con A* la ruta más corta entre dos salas o personajes. Devuelve pasos "
            "(número de pasos; un paso es una casilla) y camino_resumido (salas y puertas "
            "por las que pasa). Si una sala no existe, devuelve un error con las salas "
            "válidas. No cambia la partida.",
            {
                "type": "object",
                "properties": {
                    "origen": extremo_ruta("Punto de partida"),
                    "destino": extremo_ruta("Punto de llegada"),
                },
                "required": ["origen", "destino"],
                "additionalProperties": False,
            },
        ),
        _esquema(
            "predecir_destino",
            "Estima hacia qué sala va el tripulante según sus últimos 10 ticks. Es una "
            "estimación, no un hecho. Devuelve sala, confianza (de 0 a 1), "
            "acercamiento_casillas (casillas que se acercó a esa sala en la ventana) y "
            "ticks_analizados. No cambia la partida.",
            _sin_parametros(),
        ),
        _esquema(
            "ve_tripulante",
            "Indica si el alienígena ve ahora al tripulante con su visión. Devuelve ve "
            "(verdadero o falso) y distancia_casillas. No cambia la partida.",
            _sin_parametros(),
        ),
        _esquema(
            "dar_pista",
            "CAMBIA LA PARTIDA. Indica al alienígena una sala donde buscar al tripulante; "
            "la pista es una sala, nunca una casilla. Úsala solo si el usuario lo pide "
            f"explícitamente. Gasta una de las {PISTAS_POR_PARTIDA} pistas por partida. "
            "Devuelve sala y pistas_restantes, o un error si no quedan pistas o la sala "
            "no existe.",
            {
                "type": "object",
                "properties": {
                    "sala": {
                        "type": "string",
                        "description": (
                            f"Sala que se indica al alienígena. Salas válidas: {salas}. "
                            f"{_SIN_CORREGIR}"
                        ),
                    }
                },
                "required": ["sala"],
                "additionalProperties": False,
            },
        ),
        _esquema(
            "avanzar_simulacion",
            "CAMBIA LA PARTIDA. Avanza la simulación y devuelve tick, ticks_avanzados, "
            'eventos (lista de textos "tick N: ...") y capturado. Úsala solo si el '
            "usuario lo pide explícitamente. Se detiene antes si hay captura o si se "
            "acaba el tiempo de la partida.",
            {
                "type": "object",
                "properties": {
                    "ticks": {
                        "type": "integer",
                        "minimum": TICKS_MIN,
                        "maximum": TICKS_MAX,
                        "description": f"Ticks a avanzar, de {TICKS_MIN} a {TICKS_MAX}.",
                    }
                },
                "required": ["ticks"],
                "additionalProperties": False,
            },
        ),
    ]


def validar_correspondencia(
    esquemas: list[dict], herramientas: dict[str, Callable[..., Any]]
) -> list[str]:
    """Revisa que cada esquema tenga su función y que los parámetros coincidan.

    El agente llama cada herramienta como funcion(**argumentos), así que lo que importa
    es qué nombres acepta la función por palabra clave.

    Args:
        esquemas: Esquemas en formato "tools" de OpenAI.
        herramientas: Diccionario nombre -> función de Python.

    Returns:
        Lista de problemas en texto; vacía si todo coincide.

    Example:
        >>> def dar_pista(sala: str) -> dict:
        ...     return {"sala": sala, "pistas_restantes": 2}
        >>> esquema = construir_esquemas(["Hangar"])[4]
        >>> validar_correspondencia([esquema], {"dar_pista": dar_pista})
        []
        >>> validar_correspondencia([esquema], {})
        ["El esquema 'dar_pista' no tiene función."]
    """
    problemas: list[str] = []
    por_nombre: dict[str, dict] = {}
    for posicion, esquema in enumerate(esquemas):
        nombre = esquema.get("function", {}).get("name")
        if not nombre:
            problemas.append(f"El esquema en la posición {posicion} no tiene nombre.")
        elif nombre in por_nombre:
            problemas.append(f"El esquema '{nombre}' está repetido.")
        else:
            por_nombre[nombre] = esquema

    for nombre in por_nombre:
        if nombre not in herramientas:
            problemas.append(f"El esquema '{nombre}' no tiene función.")
    for nombre in herramientas:
        if nombre not in por_nombre:
            problemas.append(f"La función '{nombre}' no tiene esquema.")

    for nombre, esquema in por_nombre.items():
        if nombre in herramientas:
            problemas.extend(_comparar_parametros(nombre, esquema, herramientas[nombre]))
    return problemas


def _comparar_parametros(nombre: str, esquema: dict, funcion: Callable[..., Any]) -> list[str]:
    """Compara los parámetros de un esquema con la firma de su función."""
    try:
        firma = inspect.signature(funcion)
    except (TypeError, ValueError):
        return [f"No se puede leer la firma de la función '{nombre}'."]

    parametros = esquema["function"].get("parameters", {})
    en_esquema = set(parametros.get("properties", {}))
    requeridos = set(parametros.get("required", []))

    acepta_cualquiera = any(
        p.kind is inspect.Parameter.VAR_KEYWORD for p in firma.parameters.values()
    )
    # Solo cuentan los parámetros que se pueden pasar por nombre.
    por_nombre = {
        p.name: p
        for p in firma.parameters.values()
        if p.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
    }
    obligatorios = {n for n, p in por_nombre.items() if p.default is inspect.Parameter.empty}

    problemas = []
    for p in firma.parameters.values():
        if p.kind is inspect.Parameter.POSITIONAL_ONLY:
            problemas.append(
                f"'{nombre}': el parámetro '{p.name}' es solo posicional; el agente pasa "
                "los argumentos por nombre."
            )
    if not acepta_cualquiera:
        for extra in sorted(en_esquema - set(por_nombre)):
            problemas.append(f"'{nombre}': la función no acepta el parámetro '{extra}'.")
    for faltante in sorted(obligatorios - en_esquema):
        problemas.append(
            f"'{nombre}': el parámetro obligatorio '{faltante}' falta en el esquema."
        )
    if requeridos != obligatorios:
        problemas.append(
            f"'{nombre}': required del esquema {sorted(requeridos)} no coincide con los "
            f"parámetros sin valor por defecto {sorted(obligatorios)}."
        )
    return problemas
