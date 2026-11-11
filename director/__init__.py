"""Directora: agente LLM con herramientas que responde preguntas sobre una partida.

Contenido principal:
    ejecutar_agente, ResultadoAgente, RegistroLlamada, formatear_registro: ciclo del agente.
    ConfigLLM, cargar_config, crear_cliente, ClaveFaltanteError: configuración del LLM.
    PredictorDestino: heurística de la herramienta predecir_destino.
    construir_esquemas, validar_correspondencia, NOMBRES_HERRAMIENTAS: esquemas.
    construir_prompt_sistema, PROMPT_VERSION: prompt de sistema.
    Directora, Partida, crear_herramientas: la directora, su partida y sus herramientas.

Tareas relacionadas: T11 (herramientas y directora), T12 (predecir_destino), T13
(esquemas), T14 (configuración del LLM), T15 (ciclo del agente), T16 (prompt de
sistema), T17 (pruebas).
"""
from director.agente import (
    RegistroLlamada,
    ResultadoAgente,
    ejecutar_agente,
    formatear_registro,
)
from director.directora import Directora
from director.esquemas import (
    NOMBRES_HERRAMIENTAS,
    construir_esquemas,
    validar_correspondencia,
)
from director.herramientas import crear_herramientas
from director.llm import ClaveFaltanteError, ConfigLLM, cargar_config, crear_cliente
from director.partida import Partida
from director.prediccion import PredictorDestino
from director.prompt import PROMPT_VERSION, construir_prompt_sistema

__all__ = [
    "ClaveFaltanteError",
    "ConfigLLM",
    "Directora",
    "NOMBRES_HERRAMIENTAS",
    "PROMPT_VERSION",
    "Partida",
    "PredictorDestino",
    "RegistroLlamada",
    "ResultadoAgente",
    "cargar_config",
    "construir_esquemas",
    "construir_prompt_sistema",
    "crear_cliente",
    "crear_herramientas",
    "ejecutar_agente",
    "formatear_registro",
    "validar_correspondencia",
]
