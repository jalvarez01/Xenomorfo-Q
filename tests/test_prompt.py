"""Pruebas del prompt de sistema de la directora.

Tareas relacionadas: T16 (prompt de sistema), T17 (pruebas sin API).
"""
from __future__ import annotations

import re

import pytest

from director.esquemas import NOMBRES_HERRAMIENTAS
from director.prompt import PROMPT_VERSION, construir_prompt_sistema
from sim.env import MAPA_POR_DEFECTO
from sim.mapa import Mapa

SALAS = Mapa.desde_archivo(MAPA_POR_DEFECTO).nombres_salas
PROMPT = construir_prompt_sistema(SALAS)
# Máximo de palabras del prompt; se envía en cada llamada al modelo.
MAX_PALABRAS = 450
# Caracteres permitidos: ASCII imprimible, saltos de línea y letras y signos del español.
PERMITIDOS = re.compile(r"[\x20-\x7E\náéíóúÁÉÍÓÚñÑüÜ¿¡]*")


def test_incluye_salas_herramientas_limite_y_pistas():
    """El prompt menciona las 8 salas, las 6 herramientas, el límite y las pistas."""
    assert len(SALAS) == 8
    for sala in SALAS:
        assert sala in PROMPT
    for herramienta in NOMBRES_HERRAMIENTAS:
        assert herramienta in PROMPT
    assert "máximo 6 llamadas" in PROMPT
    assert "Hay 3 pistas" in PROMPT


def test_cambia_con_limite_y_pistas():
    """El texto depende de limite y pistas_max, no de valores escritos a mano."""
    otro = construir_prompt_sistema(SALAS, limite=4, pistas_max=2)
    assert otro != PROMPT
    assert "máximo 4 llamadas" in otro
    assert "Hay 2 pistas" in otro
    assert construir_prompt_sistema(SALAS, limite=4) != PROMPT
    assert construir_prompt_sistema(SALAS, pistas_max=2) != PROMPT


def test_solo_caracteres_de_texto_en_espanol():
    """El prompt no contiene emojis ni caracteres fuera del texto en español."""
    assert PERMITIDOS.fullmatch(PROMPT)


def test_menos_de_450_palabras():
    """El prompt tiene menos de 450 palabras."""
    assert len(PROMPT.split()) < MAX_PALABRAS


def test_version_y_salas_vacias():
    """PROMPT_VERSION es un texto no vacío y sin salas se lanza ValueError."""
    assert isinstance(PROMPT_VERSION, str) and PROMPT_VERSION
    with pytest.raises(ValueError):
        construir_prompt_sistema([])
