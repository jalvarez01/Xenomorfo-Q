"""Pruebas del ciclo del agente con un cliente falso, sin llamadas a ninguna API.

Contenido principal:
    ClienteFalso: imita cliente.chat.completions.create y devuelve un guion de respuestas.
    Herramientas de prueba (sumar, fallar) y sus esquemas.

Tareas relacionadas: T17 (pruebas sin API), T15 (ciclo del agente).
"""
from __future__ import annotations

import copy
import itertools
import json
from types import SimpleNamespace
from typing import Any, Iterable

from director.agente import (
    INSTRUCCION_CIERRE,
    MENSAJE_NO_EJECUTADA,
    RegistroLlamada,
    ejecutar_agente,
    formatear_registro,
)

MODELO = "modelo-falso"
PROMPT = "Eres una directora de prueba."


# --- Cliente falso ---------------------------------------------------------------------


def texto(contenido: str) -> SimpleNamespace:
    """Respuesta del modelo sin herramientas, con la forma de openai."""
    mensaje = SimpleNamespace(content=contenido, tool_calls=None)
    return SimpleNamespace(choices=[SimpleNamespace(message=mensaje)])


def pide(*llamadas: tuple[str, str, Any]) -> SimpleNamespace:
    """Respuesta del modelo que pide herramientas: cada llamada es (id, nombre, argumentos).

    Si los argumentos no son str se convierten a JSON, como hace la API.
    """
    tool_calls = [
        SimpleNamespace(
            id=id_,
            type="function",
            function=SimpleNamespace(
                name=nombre,
                arguments=args if isinstance(args, str) else json.dumps(args),
            ),
        )
        for id_, nombre, args in llamadas
    ]
    mensaje = SimpleNamespace(content=None, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(message=mensaje)])


class ClienteFalso:
    """Imita cliente.chat.completions.create devolviendo un guion en orden.

    Guarda una copia de los kwargs de cada llamada, porque la lista de mensajes del
    agente sigue cambiando después de cada llamada. Si se da cierre, las llamadas sin
    "tools" lo devuelven sin consumir el guion, como un modelo que seguiría pidiendo
    herramientas pero ya no puede.
    """

    def __init__(
        self, guion: Iterable[SimpleNamespace], cierre: SimpleNamespace | None = None
    ) -> None:
        self._guion = iter(guion)
        self._cierre = cierre
        self.llamadas: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs: Any) -> SimpleNamespace:
        self.llamadas.append(copy.deepcopy(kwargs))
        if self._cierre is not None and "tools" not in kwargs:
            return self._cierre
        return next(self._guion)

    def pendientes(self) -> int:
        """Cuenta las respuestas del guion que no se consumieron (agota el iterador)."""
        return sum(1 for _ in self._guion)


# --- Herramientas de prueba -------------------------------------------------------------


def sumar(a: int, b: int) -> int:
    """Suma dos enteros."""
    return a + b


def fallar() -> str:
    """Siempre lanza una excepción."""
    raise ValueError("falla controlada")


HERRAMIENTAS = {"sumar": sumar, "fallar": fallar}
ESQUEMAS = [
    {
        "type": "function",
        "function": {
            "name": "sumar",
            "description": "Suma dos enteros.",
            "parameters": {
                "type": "object",
                "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
                "required": ["a", "b"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fallar",
            "description": "Siempre falla.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def correr(cliente: ClienteFalso, limite: int = 6, **kwargs: Any):
    """Ejecuta el agente con las herramientas de prueba."""
    return ejecutar_agente(
        "pregunta", HERRAMIENTAS, ESQUEMAS, cliente, MODELO, PROMPT, limite, **kwargs
    )


def mensajes_tool(kwargs: dict) -> dict[str, str]:
    """Devuelve tool_call_id -> contenido de los mensajes "tool" enviados al modelo."""
    return {
        m["tool_call_id"]: m["content"] for m in kwargs["messages"] if m["role"] == "tool"
    }


# --- Casos ----------------------------------------------------------------------------


def test_respuesta_directa_sin_herramientas():
    """Si el modelo responde sin herramientas, no hay registro ni llamadas."""
    cliente = ClienteFalso([texto("hola")])
    resultado = correr(cliente)
    assert resultado.respuesta == "hola"
    assert resultado.registro == []
    assert resultado.llamadas == 0
    assert resultado.limite_alcanzado is False
    primera = cliente.llamadas[0]
    assert primera["tools"] == ESQUEMAS
    assert primera["temperature"] == 0.0
    assert [m["role"] for m in primera["messages"]] == ["system", "user"]


def test_una_herramienta_y_respuesta_final():
    """Una herramienta queda registrada y el modelo recibe su resultado con el id correcto."""
    cliente = ClienteFalso([pide(("c1", "sumar", {"a": 2, "b": 3})), texto("da 5")])
    resultado = correr(cliente)
    assert resultado.respuesta == "da 5"
    assert resultado.llamadas == 1
    assert resultado.limite_alcanzado is False
    entrada = resultado.registro[0]
    assert (entrada.herramienta, entrada.argumentos, entrada.resultado) == (
        "sumar",
        {"a": 2, "b": 3},
        "5",
    )
    assert entrada.error is False
    assert entrada.segundos >= 0
    segunda = cliente.llamadas[1]
    asistente = segunda["messages"][2]
    assert asistente["role"] == "assistant"
    assert asistente["tool_calls"][0]["id"] == "c1"
    assert mensajes_tool(segunda) == {"c1": "5"}


def test_limite_en_turnos_separados():
    """Con ocho pedidos en turnos separados y límite 6, se ejecutan 6 y se cierra sin tools."""
    guion = [pide((f"c{i}", "sumar", {"a": i, "b": 1})) for i in range(8)]
    cliente = ClienteFalso(guion, cierre=texto("cierre"))
    resultado = correr(cliente, limite=6)
    assert resultado.llamadas == 6
    assert len(resultado.registro) == 6
    assert resultado.limite_alcanzado is True
    assert resultado.respuesta == "cierre"
    assert len(cliente.llamadas) == 7
    assert cliente.pendientes() == 2
    ultima = cliente.llamadas[-1]
    assert "tools" not in ultima
    assert ultima["messages"][-1] == {"role": "user", "content": INSTRUCCION_CIERRE}


def test_varias_herramientas_en_un_turno_exceden_el_limite():
    """Las llamadas que exceden el límite no se ejecutan pero sí reciben respuesta."""
    turno1 = pide(("c1", "sumar", {"a": 1, "b": 1}))
    turno2 = pide(*[(f"d{i}", "sumar", {"a": i, "b": 0}) for i in range(4)])
    cliente = ClienteFalso([turno1, turno2, texto("cierre")])
    resultado = correr(cliente, limite=3)
    assert resultado.llamadas == 3
    assert [e.resultado for e in resultado.registro] == ["2", "0", "1"]
    assert resultado.limite_alcanzado is True
    respuestas = mensajes_tool(cliente.llamadas[-1])
    assert set(respuestas) == {"c1", "d0", "d1", "d2", "d3"}
    assert respuestas["d2"] == MENSAJE_NO_EJECUTADA
    assert respuestas["d3"] == MENSAJE_NO_EJECUTADA
    assert "tools" not in cliente.llamadas[-1]


def test_herramienta_inexistente():
    """Una herramienta desconocida devuelve las válidas, cuenta como llamada y es error."""
    cliente = ClienteFalso([pide(("c1", "volar", {})), texto("fin")])
    resultado = correr(cliente)
    assert resultado.llamadas == 1
    entrada = resultado.registro[0]
    assert entrada.error is True
    contenido = json.loads(entrada.resultado)
    assert "error" in contenido
    assert contenido["herramientas_validas"] == ["fallar", "sumar"]
    assert mensajes_tool(cliente.llamadas[1])["c1"] == entrada.resultado


def test_argumentos_json_invalidos():
    """Argumentos que no son JSON se registran como error y el ciclo continúa."""
    cliente = ClienteFalso([pide(("c1", "sumar", "{a: 1")), texto("fin")])
    resultado = correr(cliente)
    assert resultado.respuesta == "fin"
    entrada = resultado.registro[0]
    assert entrada.error is True
    assert "error" in json.loads(entrada.resultado)
    assert entrada.argumentos == {"texto_crudo": "{a: 1"}


def test_argumentos_que_no_corresponden_a_la_funcion():
    """Argumentos con nombres incorrectos se reportan como error sin llamar la función."""
    cliente = ClienteFalso([pide(("c1", "sumar", {"x": 1})), texto("fin")])
    resultado = correr(cliente)
    entrada = resultado.registro[0]
    assert entrada.error is True
    assert "Argumentos inválidos" in json.loads(entrada.resultado)["error"]


def test_excepcion_dentro_de_la_herramienta():
    """Una excepción de la herramienta se devuelve como JSON con su tipo y el ciclo sigue."""
    cliente = ClienteFalso(
        [pide(("c1", "fallar", {})), pide(("c2", "sumar", {"a": 1, "b": 2})), texto("ok")]
    )
    resultado = correr(cliente)
    assert resultado.respuesta == "ok"
    assert resultado.llamadas == 2
    assert json.loads(resultado.registro[0].resultado) == {
        "error": "ValueError: falla controlada"
    }
    assert resultado.registro[0].error is True
    assert resultado.registro[1].error is False


def test_resultado_no_textual_se_serializa_en_json():
    """Un resultado que no es str llega al modelo como JSON sin escapar tildes."""
    herramientas = {"sala": lambda: {"nombre": "Enfermería", "indice": 3}}
    cliente = ClienteFalso([pide(("c1", "sala", "")), texto("fin")])
    resultado = ejecutar_agente("p", herramientas, [], cliente, MODELO, PROMPT)
    assert resultado.registro[0].resultado == '{"nombre": "Enfermería", "indice": 3}'


def test_tope_de_turnos_evita_bucle_infinito():
    """Un modelo que pide herramientas sin fin termina por el tope de turnos."""
    infinito = (pide((f"c{i}", "sumar", {"a": 1, "b": 1})) for i in itertools.count())
    cliente = ClienteFalso(infinito, cierre=texto("cierre"))
    resultado = correr(cliente, limite=10, max_turnos=3)
    assert resultado.limite_alcanzado is True
    assert resultado.llamadas == 3
    assert resultado.respuesta == "cierre"
    assert "tools" not in cliente.llamadas[-1]


def test_guion_sin_fin_termina_con_el_limite_por_defecto():
    """Con el tope por defecto, pedidos infinitos terminan en a lo sumo limite + 3 llamadas."""
    infinito = (pide((f"c{i}", "sumar", {"a": 1, "b": 1})) for i in itertools.count())
    cliente = ClienteFalso(infinito, cierre=texto("cierre"))
    resultado = correr(cliente, limite=6)
    assert resultado.limite_alcanzado is True
    assert resultado.respuesta == "cierre"
    assert resultado.llamadas == 6
    assert len(cliente.llamadas) <= 6 + 3


def test_formatear_registro_recorta_y_marca_errores():
    """El formato numera, recorta resultados largos y marca los errores."""
    registro = [
        RegistroLlamada("sumar", {"a": 1}, "x" * 500, 0.5),
        RegistroLlamada("fallar", {}, '{"error": "e"}', 0.01, error=True),
    ]
    lineas = formatear_registro(registro).splitlines()
    assert lineas[0].startswith("1. sumar(")
    assert "..." in lineas[0]
    assert len(lineas[0]) < 200
    assert lineas[1].endswith("ERROR")
