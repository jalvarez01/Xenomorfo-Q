"""Directora: agente LLM con herramientas que responde preguntas sobre una partida.

Contenido principal:
    ejecutar_agente, ResultadoAgente, RegistroLlamada, formatear_registro: ciclo del agente.
    ConfigLLM, cargar_config, crear_cliente, ClaveFaltanteError: configuración del LLM.
    PredictorDestino: heurística de la herramienta predecir_destino.

Tareas relacionadas: T14 (configuración del LLM), T15 (ciclo del agente), T17 (pruebas),
T12 (predecir_destino).
"""
from director.agente import (
    RegistroLlamada,
    ResultadoAgente,
    ejecutar_agente,
    formatear_registro,
)
from director.llm import ClaveFaltanteError, ConfigLLM, cargar_config, crear_cliente
from director.prediccion import PredictorDestino

__all__ = [
    "ClaveFaltanteError",
    "ConfigLLM",
    "PredictorDestino",
    "RegistroLlamada",
    "ResultadoAgente",
    "cargar_config",
    "crear_cliente",
    "ejecutar_agente",
    "formatear_registro",
]
