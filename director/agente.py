"""Ciclo del agente LLM con herramientas y límite de llamadas.

La directora responde preguntas sobre una partida pidiendo herramientas al modelo. Este
módulo implementa el ciclo pregunta -> herramientas -> respuesta, equivalente a
run_agent_with_budget de Lecture11, sin depender de las herramientas concretas: recibe
un diccionario nombre -> función y sus esquemas en formato "tools" de OpenAI.

Regla del límite (decisión D9): cuenta cada herramienta ejecutada, no cada turno del
modelo. Al agotarse, el modelo responde una última vez sin herramientas.

Contenido principal:
    ejecutar_agente: corre el ciclo y devuelve un ResultadoAgente.
    ResultadoAgente: respuesta final, registro, si se alcanzó el límite y número de llamadas.
    RegistroLlamada: una herramienta ejecutada, con argumentos, resultado y tiempo.
    formatear_registro: texto legible del registro para el notebook.

Tareas relacionadas: T15 (ciclo del agente), T14 (cliente LLM), T17 (pruebas sin API),
T11 y T12 (herramientas reales), T13 (esquemas), T16 (prompt de sistema).
"""
from __future__ import annotations

import inspect
import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable

# Número máximo de herramientas ejecutadas por pregunta (llamadas, no turnos del modelo).
LIMITE_POR_DEFECTO = 6
# Turnos del modelo permitidos por encima del límite. Protege contra un modelo que pide
# herramientas sin ejecutar ninguna; con 2 de margen nunca corta un ciclo normal.
TURNOS_EXTRA = 2
# Longitud máxima, en caracteres, del resultado mostrado por formatear_registro.
LARGO_RESULTADO_REGISTRO = 120
# Resultado para cada tool_call que no se ejecuta porque el límite se agotó en ese turno.
# La API exige un mensaje "tool" por cada tool_call_id, aunque no se ejecute.
MENSAJE_NO_EJECUTADA = json.dumps(
    {"error": "No ejecutada: se alcanzó el límite de llamadas"}, ensure_ascii=False
)
# Instrucción de cierre que se agrega antes de la última llamada al modelo sin herramientas.
INSTRUCCION_CIERRE = (
    "Se alcanzó el límite de llamadas a herramientas. No pidas más herramientas. "
    "Responde la pregunta original usando solo la información ya obtenida y di "
    "explícitamente que alcanzaste el límite de llamadas."
)


@dataclass
class RegistroLlamada:
    """Una herramienta ejecutada por el agente.

    Attributes:
        herramienta: Nombre pedido por el modelo (puede no existir).
        argumentos: Argumentos decodificados. Si el JSON era inválido, guarda el texto
            original en la clave "texto_crudo".
        resultado: Texto devuelto al modelo (JSON en caso de error).
        segundos: Duración de la ejecución medida con time.perf_counter.
        error: True si la llamada terminó en error.
    """

    herramienta: str
    argumentos: dict
    resultado: str
    segundos: float
    error: bool = False


@dataclass
class ResultadoAgente:
    """Resultado de ejecutar_agente.

    Attributes:
        respuesta: Texto final del modelo.
        registro: Herramientas ejecutadas, en orden.
        limite_alcanzado: True si se agotó el límite de llamadas o el tope de turnos.
        llamadas: Número de herramientas ejecutadas (igual a len(registro)).
    """

    respuesta: str
    registro: list[RegistroLlamada] = field(default_factory=list)
    limite_alcanzado: bool = False
    llamadas: int = 0


def _a_texto(valor: Any) -> str:
    """Convierte el resultado de una herramienta en texto para el modelo.

    default=str evita que un objeto no serializable rompa el ciclo.
    """
    if isinstance(valor, str):
        return valor
    return json.dumps(valor, ensure_ascii=False, default=str)


def _error(mensaje: str, **extra: Any) -> str:
    """Arma el JSON de error que recibe el modelo."""
    return json.dumps({"error": mensaje, **extra}, ensure_ascii=False)


def _ejecutar_herramienta(
    nombre: str, texto_argumentos: str | None, herramientas: dict[str, Callable[..., Any]]
) -> RegistroLlamada:
    """Ejecuta una herramienta pedida por el modelo sin dejar escapar excepciones.

    Args:
        nombre: Nombre de la herramienta pedida.
        texto_argumentos: Argumentos como texto JSON, tal como llegan del modelo.
        herramientas: Diccionario nombre -> función.

    Returns:
        El registro de la llamada, con error=True si algo falló.
    """
    inicio = time.perf_counter()
    argumentos: dict = {}

    def registro(resultado: str, error: bool) -> RegistroLlamada:
        return RegistroLlamada(
            nombre, argumentos, resultado, time.perf_counter() - inicio, error
        )

    if nombre not in herramientas:
        return registro(
            _error(
                f"La herramienta '{nombre}' no existe.",
                herramientas_validas=sorted(herramientas),
            ),
            True,
        )

    # Algunos modelos mandan "" cuando la herramienta no tiene parámetros.
    texto = (texto_argumentos or "").strip() or "{}"
    try:
        decodificados = json.loads(texto)
    except json.JSONDecodeError as exc:
        argumentos = {"texto_crudo": texto_argumentos}
        return registro(_error(f"Los argumentos no son JSON válido: {exc}"), True)
    if not isinstance(decodificados, dict):
        argumentos = {"texto_crudo": texto_argumentos}
        return registro(_error("Los argumentos deben ser un objeto JSON."), True)
    argumentos = decodificados

    funcion = herramientas[nombre]
    # Se valida la firma antes de llamar para distinguir argumentos mal formados de un
    # TypeError lanzado dentro de la herramienta.
    try:
        firma = inspect.signature(funcion)
    except (TypeError, ValueError):
        firma = None  # Funciones sin firma inspeccionable: se llaman directamente.
    if firma is not None:
        try:
            firma.bind(**argumentos)
        except TypeError as exc:
            return registro(
                _error(f"Argumentos inválidos para '{nombre}': {exc}"), True
            )

    try:
        valor = funcion(**argumentos)
    except Exception as exc:  # noqa: BLE001 - cualquier fallo se reporta al modelo.
        return registro(_error(f"{type(exc).__name__}: {exc}"), True)
    # El contrato 5 permite devolver los errores como {"error": ...} en vez de lanzarlos;
    # el modelo recibe el dict tal cual, pero el registro debe marcarlo como error.
    return registro(_a_texto(valor), isinstance(valor, dict) and "error" in valor)


def _mensaje_asistente(mensaje: Any) -> dict:
    """Convierte el mensaje del asistente con tool_calls en un dict para reenviarlo."""
    return {
        "role": "assistant",
        # Algunos backends rechazan content=None junto a tool_calls; "" es equivalente.
        "content": mensaje.content or "",
        "tool_calls": [
            {
                "id": llamada.id,
                "type": "function",
                "function": {
                    "name": llamada.function.name,
                    "arguments": llamada.function.arguments,
                },
            }
            for llamada in mensaje.tool_calls
        ],
    }


def ejecutar_agente(
    pregunta: str,
    herramientas: dict[str, Callable[..., Any]],
    esquemas: list[dict],
    cliente: Any,
    modelo: str,
    prompt_sistema: str,
    limite: int = LIMITE_POR_DEFECTO,
    temperatura: float = 0.0,
    *,
    max_turnos: int | None = None,
) -> ResultadoAgente:
    """Responde una pregunta dejando que el modelo pida herramientas, con un límite.

    En cada turno el modelo recibe los esquemas. Si no pide herramientas, su contenido es
    la respuesta final. Si pide, se ejecutan en orden mientras quede límite; las que
    sobran reciben MENSAJE_NO_EJECUTADA y no cuentan. Al agotar el límite (o el tope de
    turnos) se hace una última llamada sin herramientas con INSTRUCCION_CIERRE.

    Ningún error de herramienta rompe el ciclo: se devuelve al modelo como JSON
    {"error": ...} y queda en el registro con error=True.

    Args:
        pregunta: Pregunta del usuario.
        herramientas: Diccionario nombre -> función de Python.
        esquemas: Esquemas de las herramientas en formato "tools" de OpenAI.
        cliente: Objeto con chat.completions.create(**kwargs) (real o falso).
        modelo: Nombre del modelo.
        prompt_sistema: Mensaje de sistema.
        limite: Máximo de herramientas ejecutadas.
        temperatura: Temperatura de muestreo.
        max_turnos: Máximo de turnos del modelo con herramientas. Por defecto
            limite + TURNOS_EXTRA.

    Returns:
        Un ResultadoAgente con la respuesta, el registro y si se alcanzó el límite.

    Raises:
        ValueError: Si limite es negativo o max_turnos es menor que 1.

    Example:
        >>> resultado = ejecutar_agente(
        ...     "¿Dónde está el tripulante?", herramientas, esquemas, cliente,
        ...     config.modelo, prompt_sistema, temperatura=config.temperatura,
        ... )  # doctest: +SKIP
        >>> print(formatear_registro(resultado.registro))  # doctest: +SKIP
    """
    if limite < 0:
        raise ValueError(f"limite debe ser >= 0; se recibió {limite}.")
    if max_turnos is None:
        max_turnos = limite + TURNOS_EXTRA
    if max_turnos < 1:
        raise ValueError(f"max_turnos debe ser >= 1; se recibió {max_turnos}.")

    mensajes: list[dict] = [
        {"role": "system", "content": prompt_sistema},
        {"role": "user", "content": pregunta},
    ]
    registro: list[RegistroLlamada] = []

    for _ in range(max_turnos):
        respuesta = cliente.chat.completions.create(
            model=modelo, messages=mensajes, tools=esquemas, temperature=temperatura
        )
        mensaje = respuesta.choices[0].message
        if not mensaje.tool_calls:
            return ResultadoAgente(mensaje.content or "", registro, False, len(registro))

        mensajes.append(_mensaje_asistente(mensaje))
        for llamada in mensaje.tool_calls:
            if len(registro) < limite:
                entrada = _ejecutar_herramienta(
                    llamada.function.name, llamada.function.arguments, herramientas
                )
                registro.append(entrada)
                contenido = entrada.resultado
            else:
                contenido = MENSAJE_NO_EJECUTADA
            mensajes.append(
                {"role": "tool", "tool_call_id": llamada.id, "content": contenido}
            )
        if len(registro) >= limite:
            break

    # Cierre por límite o por tope de turnos: sin tools, el modelo no puede pedir más.
    mensajes.append({"role": "user", "content": INSTRUCCION_CIERRE})
    respuesta = cliente.chat.completions.create(
        model=modelo, messages=mensajes, temperature=temperatura
    )
    return ResultadoAgente(
        respuesta.choices[0].message.content or "", registro, True, len(registro)
    )


def formatear_registro(registro: list[RegistroLlamada]) -> str:
    """Muestra el registro de llamadas de forma legible, una línea por herramienta.

    Args:
        registro: Lista de RegistroLlamada, normalmente ResultadoAgente.registro.

    Returns:
        Texto con número, herramienta, argumentos, resultado recortado y tiempo.

    Example:
        >>> r = RegistroLlamada("sumar", {"a": 2, "b": 3}, "5", 0.0012)
        >>> print(formatear_registro([r]))
        1. sumar({"a": 2, "b": 3}) -> 5 [0.001 s]
        >>> print(formatear_registro([]))
        Sin llamadas a herramientas.
    """
    if not registro:
        return "Sin llamadas a herramientas."
    lineas = []
    for numero, entrada in enumerate(registro, start=1):
        resultado = entrada.resultado.replace("\n", " ")
        if len(resultado) > LARGO_RESULTADO_REGISTRO:
            resultado = resultado[: LARGO_RESULTADO_REGISTRO - 3] + "..."
        argumentos = json.dumps(entrada.argumentos, ensure_ascii=False, default=str)
        marca = " ERROR" if entrada.error else ""
        lineas.append(
            f"{numero}. {entrada.herramienta}({argumentos}) -> {resultado} "
            f"[{entrada.segundos:.3f} s]{marca}"
        )
    return "\n".join(lineas)
