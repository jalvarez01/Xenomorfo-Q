"""Pruebas de los esquemas de herramientas, su correspondencia con las funciones y el caso C5.

Contenido principal:
    Funciones falsas que siguen el contrato de docs/contratos.md, sección 5.
    ClienteFalso: copia mínima del patrón de tests/test_agente.py, sin llamadas de red.

Tareas relacionadas: T13 (esquemas), T11 (funciones reales), T17 (pruebas sin API).
"""
from __future__ import annotations

import copy
import json
from types import SimpleNamespace
from typing import Any, Iterable

import pytest

from director.agente import ejecutar_agente
from director.esquemas import (
    NOMBRES_HERRAMIENTAS,
    construir_esquemas,
    validar_correspondencia,
)
from director.prompt import construir_prompt_sistema
from sim.env import MAPA_POR_DEFECTO
from sim.mapa import Mapa

SALAS = Mapa.desde_archivo(MAPA_POR_DEFECTO).nombres_salas
ESQUEMAS = construir_esquemas(SALAS)
POR_NOMBRE = {e["function"]["name"]: e["function"] for e in ESQUEMAS}


# --- Funciones falsas que siguen el contrato ----------------------------------------------


def _error_sala(sala: str) -> ValueError:
    """Error de sala inexistente con la lista de salas válidas, como el de T11."""
    return ValueError(f"La sala '{sala}' no existe. Salas válidas: {', '.join(SALAS)}.")


def estado_partida() -> dict:
    """Estado fijo de una partida."""
    return {
        "tick": 0,
        "tripulante": {"x": 1, "y": 1, "sala": SALAS[0]},
        "alienigena": {"x": 5, "y": 5, "sala": SALAS[1], "direccion": "derecha"},
        "pistas_restantes": 3,
        "capturado": False,
    }


def ruta_mas_corta(origen: str, destino: str) -> dict:
    """Ruta falsa; lanza ValueError si una sala no existe."""
    for extremo in (origen, destino):
        if extremo not in SALAS and extremo not in ("tripulante", "alienigena"):
            raise _error_sala(extremo)
    return {"pasos": 7, "camino_resumido": [origen, destino]}


def predecir_destino() -> dict:
    """Predicción fija."""
    return {"sala": SALAS[2], "confianza": 0.6, "acercamiento_casillas": 3, "ticks_analizados": 10}


def ve_tripulante() -> dict:
    """Visión fija."""
    return {"ve": False, "distancia_casillas": 9}


def dar_pista(sala: str) -> dict:
    """Pista falsa."""
    return {"sala": sala, "pistas_restantes": 2}


def avanzar_simulacion(ticks: int) -> dict:
    """Avance falso sin eventos."""
    return {"tick": ticks, "ticks_avanzados": ticks, "eventos": [], "capturado": False}


HERRAMIENTAS = {
    "estado_partida": estado_partida,
    "ruta_mas_corta": ruta_mas_corta,
    "predecir_destino": predecir_destino,
    "ve_tripulante": ve_tripulante,
    "dar_pista": dar_pista,
    "avanzar_simulacion": avanzar_simulacion,
}


# --- Cliente falso (patrón de tests/test_agente.py) -----------------------------------


def texto(contenido: str) -> SimpleNamespace:
    """Respuesta del modelo sin herramientas."""
    mensaje = SimpleNamespace(content=contenido, tool_calls=None)
    return SimpleNamespace(choices=[SimpleNamespace(message=mensaje)])


def pide(id_: str, nombre: str, argumentos: dict) -> SimpleNamespace:
    """Respuesta del modelo que pide una herramienta."""
    llamada = SimpleNamespace(
        id=id_,
        type="function",
        function=SimpleNamespace(name=nombre, arguments=json.dumps(argumentos)),
    )
    mensaje = SimpleNamespace(content=None, tool_calls=[llamada])
    return SimpleNamespace(choices=[SimpleNamespace(message=mensaje)])


class ClienteFalso:
    """Devuelve un guion en orden y guarda copia de los kwargs de cada llamada."""

    def __init__(self, guion: Iterable[SimpleNamespace]) -> None:
        self._guion = iter(guion)
        self.llamadas: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs: Any) -> SimpleNamespace:
        self.llamadas.append(copy.deepcopy(kwargs))
        return next(self._guion)


# --- Estructura de los esquemas ---------------------------------------------------------


def test_seis_esquemas_en_orden():
    """Hay exactamente 6 esquemas con los nombres y el orden de NOMBRES_HERRAMIENTAS."""
    assert len(NOMBRES_HERRAMIENTAS) == 6
    assert tuple(e["function"]["name"] for e in ESQUEMAS) == NOMBRES_HERRAMIENTAS


def test_estructura_valida_para_openai():
    """Cada esquema tiene type, function, name, description y parameters de tipo object."""
    for esquema in ESQUEMAS:
        assert esquema["type"] == "function"
        funcion = esquema["function"]
        assert set(funcion) == {"name", "description", "parameters"}
        assert isinstance(funcion["name"], str) and funcion["name"]
        assert isinstance(funcion["description"], str) and funcion["description"]
        assert funcion["parameters"]["type"] == "object"
        assert isinstance(funcion["parameters"]["properties"], dict)


def test_parametros_del_contrato():
    """Los parámetros de cada herramienta son exactamente los del contrato."""
    esperados = {
        "estado_partida": set(),
        "ruta_mas_corta": {"origen", "destino"},
        "predecir_destino": set(),
        "ve_tripulante": set(),
        "dar_pista": {"sala"},
        "avanzar_simulacion": {"ticks"},
    }
    for nombre, parametros in esperados.items():
        assert set(POR_NOMBRE[nombre]["parameters"]["properties"]) == parametros


def test_required_y_additional_properties():
    """Todos los parámetros son obligatorios y no se aceptan propiedades extra."""
    for funcion in POR_NOMBRE.values():
        parametros = funcion["parameters"]
        assert parametros["additionalProperties"] is False
        assert set(parametros.get("required", [])) == set(parametros["properties"])


def test_rango_de_ticks():
    """ticks es entero con mínimo 1 y máximo 20."""
    ticks = POR_NOMBRE["avanzar_simulacion"]["parameters"]["properties"]["ticks"]
    assert ticks["type"] == "integer"
    assert (ticks["minimum"], ticks["maximum"]) == (1, 20)


def test_sin_enum():
    """Ningún parámetro usa enum, para que una sala inexistente llegue a la herramienta."""
    assert "enum" not in json.dumps(ESQUEMAS)


def test_salas_en_las_descripciones():
    """Los 8 nombres de sala de vela9 aparecen en las descripciones de origen, destino y sala."""
    assert len(SALAS) == 8
    descripciones = [
        POR_NOMBRE["ruta_mas_corta"]["parameters"]["properties"]["origen"]["description"],
        POR_NOMBRE["ruta_mas_corta"]["parameters"]["properties"]["destino"]["description"],
        POR_NOMBRE["dar_pista"]["parameters"]["properties"]["sala"]["description"],
    ]
    for descripcion in descripciones:
        for sala in SALAS:
            assert sala in descripcion
        assert "sin corregirlo" in descripcion
    for especial in ("tripulante", "alienigena"):
        assert especial in descripciones[0] and especial in descripciones[1]


def test_esquemas_serializables():
    """Los esquemas se pueden serializar con json.dumps."""
    assert json.loads(json.dumps(ESQUEMAS, ensure_ascii=False)) == ESQUEMAS


def test_salas_vacias_lanza_error():
    """Sin nombres de sala no se pueden construir los esquemas."""
    with pytest.raises(ValueError):
        construir_esquemas([])


# --- validar_correspondencia -------------------------------------------------------------


def test_correspondencia_con_funciones_del_contrato():
    """Con funciones que siguen el contrato no hay problemas."""
    assert validar_correspondencia(ESQUEMAS, HERRAMIENTAS) == []


def test_detecta_esquema_sin_funcion():
    """Un esquema sin función se reporta."""
    herramientas = {k: v for k, v in HERRAMIENTAS.items() if k != "ve_tripulante"}
    problemas = validar_correspondencia(ESQUEMAS, herramientas)
    assert problemas == ["El esquema 've_tripulante' no tiene función."]


def test_detecta_funcion_sin_esquema():
    """Una función sin esquema se reporta."""
    herramientas = {**HERRAMIENTAS, "teletransportar": lambda: {}}
    problemas = validar_correspondencia(ESQUEMAS, herramientas)
    assert problemas == ["La función 'teletransportar' no tiene esquema."]


def test_detecta_parametro_con_otro_nombre():
    """Un parámetro con otro nombre se reporta en ambos sentidos."""

    def dar_pista_mal(nombre_sala: str) -> dict:
        return {}

    problemas = validar_correspondencia(ESQUEMAS, {**HERRAMIENTAS, "dar_pista": dar_pista_mal})
    texto_problemas = " ".join(problemas)
    assert "no acepta el parámetro 'sala'" in texto_problemas
    assert "'nombre_sala' falta en el esquema" in texto_problemas


def test_detecta_required_incorrecto():
    """Un required que no coincide con los parámetros sin valor por defecto se reporta."""
    esquemas = copy.deepcopy(ESQUEMAS)
    esquemas[1]["function"]["parameters"]["required"] = ["origen"]
    problemas = validar_correspondencia(esquemas, HERRAMIENTAS)
    assert len(problemas) == 1
    assert "ruta_mas_corta" in problemas[0] and "required" in problemas[0]


def test_correspondencia_con_herramientas_reales():
    """Si T11 ya existe, sus funciones reales coinciden con los esquemas."""
    modulo = pytest.importorskip(
        "director.herramientas",
        reason="director/herramientas.py (T11) todavía no existe.",
    )
    reales = getattr(modulo, "HERRAMIENTAS", None)
    if not isinstance(reales, dict):
        pytest.skip("director/herramientas.py no expone un diccionario HERRAMIENTAS.")
    assert validar_correspondencia(ESQUEMAS, reales) == []


# --- Integración con el agente: caso C5 -------------------------------------------------


def test_c5_sala_inexistente_llega_como_error():
    """Una sala inexistente produce un error JSON que llega al modelo y queda registrado."""
    cliente = ClienteFalso(
        [
            pide("c1", "ruta_mas_corta", {"origen": "Enfermería", "destino": "Hangar"}),
            texto("La sala Enfermería no existe."),
        ]
    )
    resultado = ejecutar_agente(
        "¿Cuántos pasos hay de Enfermería al Hangar?",
        HERRAMIENTAS,
        ESQUEMAS,
        cliente,
        "modelo-falso",
        construir_prompt_sistema(SALAS),
    )
    assert cliente.llamadas[0]["tools"] == ESQUEMAS
    entrada = resultado.registro[0]
    assert entrada.herramienta == "ruta_mas_corta"
    assert entrada.argumentos == {"origen": "Enfermería", "destino": "Hangar"}
    assert entrada.error is True
    error = json.loads(entrada.resultado)["error"]
    assert error.startswith("ValueError: La sala 'Enfermería' no existe.")
    for sala in SALAS:
        assert sala in error
    mensajes_tool = [m for m in cliente.llamadas[1]["messages"] if m["role"] == "tool"]
    assert mensajes_tool == [{"role": "tool", "tool_call_id": "c1", "content": entrada.resultado}]
    assert resultado.respuesta == "La sala Enfermería no existe."


def test_c5_sala_inexistente_devuelta_como_dict():
    """Variante de C5: el error devuelto como dict también queda con error=True y llega al modelo."""

    def ruta_con_dict(origen: str, destino: str) -> dict:
        for extremo in (origen, destino):
            if extremo not in SALAS and extremo not in ("tripulante", "alienigena"):
                return {"error": f"La sala '{extremo}' no existe.", "salas_validas": SALAS}
        return {"pasos": 7, "camino_resumido": [origen, destino]}

    herramientas = {**HERRAMIENTAS, "ruta_mas_corta": ruta_con_dict}
    assert validar_correspondencia(ESQUEMAS, herramientas) == []
    cliente = ClienteFalso(
        [
            pide("c1", "ruta_mas_corta", {"origen": "Enfermería", "destino": "Hangar"}),
            texto("La sala Enfermería no existe."),
        ]
    )
    resultado = ejecutar_agente(
        "¿Cuántos pasos hay de Enfermería al Hangar?",
        herramientas,
        ESQUEMAS,
        cliente,
        "modelo-falso",
        construir_prompt_sistema(SALAS),
    )
    entrada = resultado.registro[0]
    assert entrada.error is True
    contenido = json.loads(entrada.resultado)
    assert contenido == {"error": "La sala 'Enfermería' no existe.", "salas_validas": SALAS}
    mensajes_tool = [m for m in cliente.llamadas[1]["messages"] if m["role"] == "tool"]
    assert mensajes_tool == [{"role": "tool", "tool_call_id": "c1", "content": entrada.resultado}]
    assert resultado.respuesta == "La sala Enfermería no existe."
