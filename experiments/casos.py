"""Ejecutor de los 6 casos de prueba de la directora con registro de evidencia (apoyo a T21).

Corre cada caso con una Directora nueva (cada caso en su propia partida, con la misma
semilla) y guarda la evidencia en un JSON y un Markdown: pregunta, valor esperado,
llamadas a herramientas con argumentos y resultados, respuesta, número de llamadas,
si se alcanzó el límite, modelo, temperatura, semilla y latencia.

El valor esperado se calcula con las herramientas directamente, sin el modelo, sobre una
partida nueva con la misma semilla: es la verdad contra la que se compara la respuesta.

Un caso puede tener "preparacion": {"semilla", "ticks"}. Entonces su partida usa esa
semilla y avanza esos ticks con el alienígena por reglas antes de preguntar, y el valor
esperado se calcula después de la misma preparación. C3 la usa para que el tripulante ya
se esté moviendo (ver buscar_preparacion).

Los campos "valoracion" y "correcto" quedan vacíos: la valoración y el análisis son de
T21 a T23 (Simón Mazo). Nunca se escribe la clave ni ninguna variable de entorno.

Uso:
    python -m experiments.casos [--semilla 42] [--salida experiments/resultados]

Contenido principal:
    CASOS: los 6 casos (id, categoria, pregunta, herramientas_esperadas y, si hace falta,
        preparacion).
    calcular_esperado: valor esperado de un caso, sin el modelo.
    preparar_partida, buscar_preparacion: preparación de un caso y búsqueda de la de C3.
    ejecutar_casos: corre los casos y escribe los archivos.
    main: comando.

Tareas relacionadas: T21 (ejecución de casos), T20 (diseño de casos), T22 y T23
(valoración y análisis), T11 (directora).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any

from director.directora import Directora
from director.herramientas import crear_herramientas
from director.llm import ClaveFaltanteError, ConfigLLM, cargar_config
from director.partida import SEMILLA_POR_DEFECTO, Partida
from director.prompt import PROMPT_VERSION

# Carpeta por defecto de los resultados, relativa a la raíz del repositorio.
SALIDA_POR_DEFECTO = "experiments/resultados"
# Ticks que avanza el caso C4, los mismos que pide su pregunta.
TICKS_C4 = 10
# Código de salida cuando falta la clave, igual que python -m director.
CODIGO_SIN_CLAVE = 2
# Búsqueda de la preparación de C3: semillas y ticks a probar, y confianza mínima de la
# predicción para que el caso no sea trivial.
SEMILLAS_BUSQUEDA = range(0, 51)
TICKS_BUSQUEDA = range(5, 16)
CONFIANZA_MIN_C3 = 0.5
# Máximo de ticks por llamada a avanzar (contrato 5.6); la preparación avanza en tramos.
TRAMO_TICKS = 20

CASOS: list[dict[str, Any]] = [
    {"id": "C1", "categoria": "habitual",
     "pregunta": "¿En qué sala está el tripulante y a cuántos pasos está el alienígena?",
     "herramientas_esperadas": ["estado_partida", "ruta_mas_corta"]},
    {"id": "C2", "categoria": "habitual",
     "pregunta": "¿El alienígena está viendo al tripulante en este momento?",
     "herramientas_esperadas": ["ve_tripulante"]},
    {"id": "C3", "categoria": "habitual",
     "pregunta": "¿Hacia qué sala se dirige el tripulante?",
     "herramientas_esperadas": ["predecir_destino"],
     # Resultado de buscar_preparacion(): primera semilla y N, en ese orden, donde el
     # tripulante va hacia otra sala con confianza >= 0.5 (tests/test_casos.py lo revisa).
     "preparacion": {"semilla": 0, "ticks": 11}},
    {"id": "C4", "categoria": "varias herramientas y acción",
     "pregunta": ("El alienígena lleva rato perdido: dale una pista hacia la sala donde está "
                  "el tripulante, avanza 10 ticks y dime si se acercó."),
     "herramientas_esperadas": ["estado_partida", "dar_pista", "avanzar_simulacion",
                                "ruta_mas_corta"]},
    {"id": "C5", "categoria": "límite: sala inexistente",
     "pregunta": "¿Cuántos pasos hay desde la Enfermería hasta el Hangar?",
     "herramientas_esperadas": ["ruta_mas_corta"]},
    {"id": "C6", "categoria": "extra: límite de llamadas",
     "pregunta": "Calcula la distancia del alienígena a cada una de las 8 salas.",
     "herramientas_esperadas": ["ruta_mas_corta"]},
]


def preparar_partida(partida: Partida, ticks: int) -> dict | None:
    """Avanza la partida con el alienígena por reglas, en tramos de hasta 20 ticks.

    Args:
        partida: Partida a preparar.
        ticks: Ticks a avanzar en total; 0 no hace nada.

    Returns:
        El resultado del último tramo, o None si ticks es 0.

    Example:
        >>> preparar_partida(Partida(semilla=0), 11)["tick"]
        11
    """
    resultado = None
    while partida.env.tick < ticks:
        resultado = partida.avanzar(min(TRAMO_TICKS, ticks - partida.env.tick))
        if resultado["capturado"]:
            break
    return resultado


def buscar_preparacion(semillas: range = SEMILLAS_BUSQUEDA, ticks: range = TICKS_BUSQUEDA,
                       confianza_min: float = CONFIANZA_MIN_C3) -> dict | None:
    """Busca una preparación en la que predecir_destino no sea trivial (para C3).

    Recorre las semillas en orden y, para cada una, los ticks en orden; devuelve la
    primera combinación en la que, después de avanzar, no hubo captura y la predicción
    señala una sala distinta de la sala actual del tripulante con confianza mayor o
    igual a confianza_min. Así el caso pregunta por un destino real, no por la sala donde
    ya está.

    Args:
        semillas: Semillas a probar, en orden.
        ticks: Ticks de preparación a probar, en orden.
        confianza_min: Confianza mínima de la predicción.

    Returns:
        {"semilla", "ticks"} de la primera combinación que cumple, o None si ninguna.

    Example:
        >>> buscar_preparacion()
        {'semilla': 0, 'ticks': 11}
    """
    for semilla in semillas:
        for n in ticks:
            partida = Partida(semilla=semilla)
            resultado = preparar_partida(partida, n)
            if resultado is not None and resultado["capturado"]:
                continue
            prediccion = partida.predictor.predecir(partida.env.trayectoria)
            actual = partida.nombre_sala(partida.ultima_sala_tripulante())
            if prediccion["confianza"] >= confianza_min and prediccion["sala"] != actual:
                return {"semilla": semilla, "ticks": n}
    return None


def calcular_esperado(caso_id: str, semilla: int = SEMILLA_POR_DEFECTO) -> dict:
    """Valor esperado de un caso, calculado con las herramientas sin el modelo.

    Cada caso usa una partida nueva con la semilla dada, igual que ejecutar_casos. Si el
    caso tiene preparación, usa la semilla de la preparación y avanza sus ticks antes.

    Args:
        caso_id: "C1" a "C6".
        semilla: Semilla de la partida.

    Returns:
        Diccionario serializable a JSON con los valores que la respuesta debería dar.

    Raises:
        ValueError: Si caso_id no es uno de los 6 casos.

    Example:
        >>> calcular_esperado("C1")
        {'sala_tripulante': 'Bodega', 'pasos_alienigena_tripulante': 15}
    """
    caso = next((c for c in CASOS if c["id"] == caso_id), None)
    if caso is None:
        raise ValueError(f"Caso desconocido: {caso_id}. Casos válidos: "
                         f"{', '.join(c['id'] for c in CASOS)}.")
    partida = _partida_del_caso(caso, semilla)
    h = crear_herramientas(partida)
    if caso_id == "C1":
        return {"sala_tripulante": h["estado_partida"]()["tripulante"]["sala"],
                "pasos_alienigena_tripulante": h["ruta_mas_corta"]("alienigena", "tripulante")["pasos"]}
    if caso_id == "C2":
        return h["ve_tripulante"]()
    if caso_id == "C3":
        # La sala actual ayuda a valorar: la respuesta debe dar el destino, no dónde está.
        return {**h["predecir_destino"](),
                "sala_actual_tripulante": h["estado_partida"]()["tripulante"]["sala"]}
    if caso_id == "C4":
        sala = h["estado_partida"]()["tripulante"]["sala"]
        antes = h["ve_tripulante"]()["distancia_casillas"]
        pista = h["dar_pista"](sala)
        avance = h["avanzar_simulacion"](TICKS_C4)
        despues = h["ve_tripulante"]()["distancia_casillas"]
        return {"sala_pista": sala, "pistas_restantes": pista["pistas_restantes"],
                "pasos_antes": antes, "pasos_despues": despues, "se_acerco": despues < antes,
                "capturado": avance["capturado"], "eventos": avance["eventos"]}
    if caso_id == "C5":
        try:
            h["ruta_mas_corta"]("Enfermería", "Hangar")
        except ValueError as error:
            return {"error": str(error)}
        raise AssertionError("La Enfermería no debería existir en el mapa.")
    if caso_id == "C6":
        distancias = {sala: h["ruta_mas_corta"]("alienigena", sala)["pasos"]
                      for sala in partida.env.mapa.nombres_salas}
        # Hace falta una llamada por sala (8) y el límite es 6: debe declarar el límite.
        return {"pasos_por_sala": distancias, "llamadas_necesarias": len(distancias),
                "limite_alcanzado": True}
    raise ValueError(f"Caso sin valor esperado definido: {caso_id}.")


def _semilla_del_caso(caso: dict, semilla: int) -> int:
    """Semilla de la preparación del caso, o la semilla general si no tiene."""
    return caso.get("preparacion", {}).get("semilla", semilla)


def _partida_del_caso(caso: dict, semilla: int) -> Partida:
    """Partida nueva para un caso, con su preparación aplicada si la tiene."""
    partida = Partida(semilla=_semilla_del_caso(caso, semilla))
    preparar_partida(partida, caso.get("preparacion", {}).get("ticks", 0))
    return partida


def ejecutar_casos(semilla: int = SEMILLA_POR_DEFECTO, salida: str | Path = SALIDA_POR_DEFECTO,
                   cliente: Any = None, config: ConfigLLM | None = None,
                   casos: list[dict] | None = None) -> tuple[Path, Path]:
    """Corre los casos con una Directora nueva cada uno y escribe JSON y Markdown.

    Args:
        semilla: Semilla de cada partida.
        salida: Carpeta donde se escriben los archivos; se crea si no existe.
        cliente: Cliente del modelo. None usa el real de NVIDIA NIM (necesita la clave).
        config: Configuración del modelo. None la lee del entorno.
        casos: Casos a correr. None corre CASOS.

    Returns:
        Rutas del JSON y del Markdown escritos.

    Raises:
        ClaveFaltanteError: Si no se pasó cliente y falta NVIDIA_API_KEY.
    """
    config = config if config is not None else cargar_config()
    casos = CASOS if casos is None else casos
    resultados = []
    for caso in casos:
        semilla_caso = _semilla_del_caso(caso, semilla)
        directora = Directora(semilla=semilla_caso, cliente=cliente, config=config)
        # La misma preparación que calcular_esperado, para comparar sobre el mismo estado.
        preparar_partida(directora.partida, caso.get("preparacion", {}).get("ticks", 0))
        inicio = time.perf_counter()
        resultado = directora.preguntar(caso["pregunta"])
        latencia = time.perf_counter() - inicio
        resultados.append({
            **caso,
            "semilla_caso": semilla_caso,
            "resultado_esperado": calcular_esperado(caso["id"], semilla),
            "respuesta": resultado.respuesta,
            "llamadas": [{"herramienta": r.herramienta, "argumentos": r.argumentos,
                          "resultado": r.resultado, "segundos": round(r.segundos, 4),
                          "error": r.error} for r in resultado.registro],
            "numero_llamadas": resultado.llamadas,
            "limite_alcanzado": resultado.limite_alcanzado,
            "latencia_segundos": round(latencia, 3),
            "valoracion": "",
            "correcto": None,
        })
    informe = {
        "fecha": date.today().isoformat(),
        "prompt_version": PROMPT_VERSION,
        "modelo": config.modelo,
        "temperatura": config.temperatura,
        "semilla": semilla,
        "limite": directora.limite if casos else None,
        "casos": resultados,
    }
    carpeta = Path(salida)
    carpeta.mkdir(parents=True, exist_ok=True)
    base = carpeta / f"casos_{informe['fecha']}_prompt{PROMPT_VERSION}_semilla{semilla}"
    ruta_json = base.with_suffix(".json")
    ruta_md = base.with_suffix(".md")
    ruta_json.write_text(json.dumps(informe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ruta_md.write_text(_markdown(informe), encoding="utf-8")
    return ruta_json, ruta_md


def _texto_preparacion(caso: dict) -> str:
    """Línea del Markdown con la semilla del caso y su preparación, si la tiene."""
    if "preparacion" not in caso:
        return f"**Partida:** semilla {caso['semilla_caso']}, sin preparación."
    return (f"**Partida:** semilla {caso['semilla_caso']}, preparada avanzando "
            f"{caso['preparacion']['ticks']} ticks con el alienígena por reglas antes de "
            "preguntar.")


def _markdown(informe: dict) -> str:
    """Informe legible de los casos, con los mismos datos del JSON."""
    lineas = [
        f"# Casos de prueba de la directora ({informe['fecha']})",
        "",
        f"- Modelo: `{informe['modelo']}`, temperatura {informe['temperatura']}",
        f"- Prompt: versión {informe['prompt_version']}; límite {informe['limite']} llamadas",
        f"- Semilla: {informe['semilla']} (cada caso en una partida nueva; los casos con "
        "preparación usan la suya)",
        "",
        "| Caso | Categoría | Llamadas | Límite alcanzado | Latencia (s) | Correcto |",
        "|---|---|---|---|---|---|",
    ]
    for c in informe["casos"]:
        lineas.append(f"| {c['id']} | {c['categoria']} | {c['numero_llamadas']} | "
                      f"{'sí' if c['limite_alcanzado'] else 'no'} | {c['latencia_segundos']} | |")
    for c in informe["casos"]:
        lineas += [
            "", f"## {c['id']}: {c['categoria']}", "",
            f"**Pregunta:** {c['pregunta']}", "",
            f"**Herramientas esperadas:** {', '.join(c['herramientas_esperadas'])}", "",
            _texto_preparacion(c), "",
            "**Resultado esperado:**", "", "```json",
            json.dumps(c["resultado_esperado"], ensure_ascii=False, indent=2), "```", "",
            "**Llamadas:**", "",
        ]
        if not c["llamadas"]:
            lineas.append("Ninguna.")
        for i, llamada in enumerate(c["llamadas"], start=1):
            marca = " (error)" if llamada["error"] else ""
            lineas.append(f"{i}. `{llamada['herramienta']}"
                          f"({json.dumps(llamada['argumentos'], ensure_ascii=False)})`{marca}: "
                          f"`{llamada['resultado']}`")
        lineas += [
            "", f"**Respuesta:** {c['respuesta']}", "",
            f"**Llamadas:** {c['numero_llamadas']}. **Límite alcanzado:** "
            f"{'sí' if c['limite_alcanzado'] else 'no'}. **Latencia:** {c['latencia_segundos']} s.", "",
            "**Valoración:** (pendiente)", "",
            "**Correcto:** (pendiente)",
        ]
    return "\n".join(lineas) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Corre los casos desde la terminal e imprime las rutas de los archivos.

    Args:
        argv: Argumentos sin el nombre del programa. None usa sys.argv.

    Returns:
        0 si todo salió bien, CODIGO_SIN_CLAVE si falta la clave.
    """
    parser = argparse.ArgumentParser(prog="python -m experiments.casos",
                                     description="Corre los 6 casos de prueba de la directora.")
    parser.add_argument("--semilla", type=int, default=SEMILLA_POR_DEFECTO,
                        help="Semilla de cada partida (por defecto 42).")
    parser.add_argument("--salida", default=SALIDA_POR_DEFECTO,
                        help=f"Carpeta de resultados (por defecto {SALIDA_POR_DEFECTO}).")
    args = parser.parse_args(argv)
    try:
        ruta_json, ruta_md = ejecutar_casos(semilla=args.semilla, salida=args.salida)
    except ClaveFaltanteError as exc:
        print(f"No se pueden correr los casos.\n{exc}", file=sys.stderr)
        return CODIGO_SIN_CLAVE
    print(f"Resultados en {ruta_json} y {ruta_md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
