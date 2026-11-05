"""Directora: agente LLM con herramientas que responde preguntas sobre una partida.

Contenido principal:
    ejecutar_agente, ResultadoAgente, RegistroLlamada, formatear_registro: ciclo del agente.
    ConfigLLM, cargar_config, crear_cliente, ClaveFaltanteError: configuración del LLM.
    construir_esquemas, validar_correspondencia, NOMBRES_HERRAMIENTAS: esquemas.
    construir_prompt_sistema, PROMPT_VERSION: prompt de sistema.

Tareas relacionadas: T13 (esquemas), T14 (configuración del LLM), T15 (ciclo del
agente), T16 (prompt de sistema), T17 (pruebas).
"""
from director.agente import (
    RegistroLlamada,
    ResultadoAgente,
    ejecutar_agente,
    formatear_registro,
)
from director.esquemas import (
    NOMBRES_HERRAMIENTAS,
    construir_esquemas,
    validar_correspondencia,
)
from director.llm import ClaveFaltanteError, ConfigLLM, cargar_config, crear_cliente
from director.prompt import PROMPT_VERSION, construir_prompt_sistema

__all__ = [
    "ClaveFaltanteError",
    "ConfigLLM",
    "NOMBRES_HERRAMIENTAS",
    "PROMPT_VERSION",
    "RegistroLlamada",
    "ResultadoAgente",
    "cargar_config",
    "construir_esquemas",
    "construir_prompt_sistema",
    "crear_cliente",
    "ejecutar_agente",
    "formatear_registro",
    "validar_correspondencia",
]
