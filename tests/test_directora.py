"""Pruebas de la Directora con un cliente falso, sin llamadas de red (T11).

Contenido principal:
    ClienteFalso: devuelve un guion de respuestas del modelo y guarda cada llamada.
    pide, texto: respuestas del modelo con y sin herramientas.

Tareas relacionadas: T11 (directora), T17 (pruebas sin API).
"""
from __future__ import annotations

import copy
import json
from types import SimpleNamespace
from typing import Any, Iterable

import pytest

from director import llm
from director.directora import Directora
from director.esquemas import NOMBRES_HERRAMIENTAS
from director.llm import ClaveFaltanteError, ConfigLLM


def texto(contenido: str) -> SimpleNamespace:
    """Respuesta del modelo sin herramientas."""
    mensaje = SimpleNamespace(content=contenido, tool_calls=None)
    return SimpleNamespace(choices=[SimpleNamespace(message=mensaje)])


def pide(id_: str, nombre: str, argumentos: dict) -> SimpleNamespace:
    """Respuesta del modelo que pide una herramienta."""
    llamada = SimpleNamespace(id=id_, type="function",
                              function=SimpleNamespace(name=nombre, arguments=json.dumps(argumentos)))
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=None, tool_calls=[llamada]))])


class ClienteFalso:
    """Devuelve el guion en orden y guarda una copia de los kwargs de cada llamada."""

    def __init__(self, guion: Iterable[SimpleNamespace]) -> None:
        self._guion = iter(guion)
        self.llamadas: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs: Any) -> SimpleNamespace:
        self.llamadas.append(copy.deepcopy(kwargs))
        return next(self._guion)


@pytest.fixture(autouse=True)
def sin_clave(monkeypatch):
    """Aísla las pruebas de la clave real y de cualquier .env local."""
    monkeypatch.setattr(llm, "_cargar_dotenv", lambda: None)
    monkeypatch.delenv(llm.VAR_CLAVE, raising=False)


def test_estado_y_ruta_quedan_en_el_registro():
    """El modelo pide estado_partida y ruta_mas_corta; el registro tiene ambas con sus resultados."""
    cliente = ClienteFalso([
        pide("c1", "estado_partida", {}),
        pide("c2", "ruta_mas_corta", {"origen": "alienigena", "destino": "tripulante"}),
        texto("El tripulante está en Bodega, a 15 pasos."),
    ])
    d = Directora(semilla=42, cliente=cliente, config=ConfigLLM())
    r = d.preguntar("¿Dónde está el tripulante y a cuántos pasos?")
    assert r.respuesta == "El tripulante está en Bodega, a 15 pasos."
    assert [e.herramienta for e in r.registro] == ["estado_partida", "ruta_mas_corta"]
    assert json.loads(r.registro[0].resultado)["tripulante"]["sala"] == "Bodega"
    assert json.loads(r.registro[1].resultado)["pasos"] == 15
    assert not any(e.error for e in r.registro)
    primera = cliente.llamadas[0]
    assert [t["function"]["name"] for t in primera["tools"]] == list(NOMBRES_HERRAMIENTAS)
    assert primera["messages"][0]["content"] == d.prompt
    assert primera["model"] == ConfigLLM().modelo and primera["temperature"] == 0.0


def test_sala_inexistente_llega_como_error_al_modelo():
    """Una sala inexistente vuelve al modelo como JSON de error con las salas válidas."""
    cliente = ClienteFalso([
        pide("c1", "ruta_mas_corta", {"origen": "Enfermería", "destino": "Hangar"}),
        texto("La Enfermería no existe."),
    ])
    r = Directora(cliente=cliente, config=ConfigLLM()).preguntar("¿De la Enfermería al Hangar?")
    assert r.registro[0].error is True
    error = json.loads(r.registro[0].resultado)["error"]
    assert "'Enfermería' no existe" in error and "Médico" in error
    tool = [m for m in cliente.llamadas[1]["messages"] if m["role"] == "tool"]
    assert tool == [{"role": "tool", "tool_call_id": "c1", "content": r.registro[0].resultado}]


def test_la_partida_persiste_entre_preguntas():
    """Una pista dada en una pregunta sigue vigente en la siguiente."""
    cliente = ClienteFalso([
        pide("c1", "dar_pista", {"sala": "hangar"}), texto("Listo."),
        pide("c2", "estado_partida", {}), texto("Quedan 2 pistas."),
    ])
    d = Directora(cliente=cliente, config=ConfigLLM())
    d.preguntar("Dale una pista hacia el hangar.")
    r = d.preguntar("¿Cuántas pistas quedan?")
    assert json.loads(r.registro[0].resultado)["pistas_restantes"] == 2
    # Cada pregunta empieza con solo el sistema y la pregunta: no hay historial.
    assert [m["role"] for m in cliente.llamadas[2]["messages"]] == ["system", "user"]


def test_sin_clave_no_falla_hasta_preguntar():
    """Sin NVIDIA_API_KEY se puede crear la directora; preguntar sin cliente lanza ClaveFaltanteError."""
    d = Directora()
    assert d.herramientas["estado_partida"]()["tick"] == 0
    with pytest.raises(ClaveFaltanteError, match="NVIDIA_API_KEY"):
        d.preguntar("¿Dónde está el tripulante?")


def test_reiniciar_crea_otra_partida():
    """reiniciar empieza una partida nueva y las herramientas apuntan a ella."""
    d = Directora(semilla=42, config=ConfigLLM())
    d.herramientas["avanzar_simulacion"](5)
    d.reiniciar()
    assert d.partida.semilla == 42 and d.herramientas["estado_partida"]()["tick"] == 0
    d.reiniciar(semilla=7)
    assert d.partida.semilla == 7


def test_limite_llega_al_prompt_y_al_ciclo():
    """El límite se refleja en el prompt y corta el ciclo."""
    cliente = ClienteFalso([pide(f"c{i}", "estado_partida", {}) for i in range(3)] + [texto("cierre")])
    d = Directora(cliente=cliente, config=ConfigLLM(), limite=2)
    assert "máximo 2 llamadas" in d.prompt
    r = d.preguntar("Consulta mucho.")
    assert r.llamadas == 2 and r.limite_alcanzado is True
