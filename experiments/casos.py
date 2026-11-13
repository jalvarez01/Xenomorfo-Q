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

Cada caso trae además una comparación automática (cada dato esperado contra lo que dice
la respuesta) y una "valoracion_sugerida" derivada de ella. Los campos "valoracion" y
"correcto" quedan vacíos: la valoración y el análisis son de T21 a T23 (Simón Mazo).
Nunca se escribe la clave ni ninguna variable de entorno.

Uso:
    python -m experiments.casos [--semilla 42] [--salida experiments/resultados]
    python -m experiments.casos --recomparar experiments/resultados/<archivo>.json

Contenido principal:
    CASOS: los 6 casos (id, categoria, pregunta, herramientas_esperadas y, si hace falta,
        preparacion).
    calcular_esperado: valor esperado de un caso, sin el modelo.
    preparar_partida, buscar_preparacion: preparación de un caso y búsqueda de la de C3.
    comparar, sugerir_valoracion, recomparar: comparación automática, valoración sugerida
        y recálculo sobre una evidencia guardada.
    ejecutar_casos: corre los casos y escribe los archivos.
    main: comando.

Tareas relacionadas: T21 (ejecución de casos), T20 (diseño de casos), T22 y T23
(valoración y análisis), T11 (directora).
"""
from __future__ import annotations

import argparse
import json
import re
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
from sim.mapa import normalizar_nombre

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


def _dice_numero(texto: str, valor: float) -> bool:
    """True si el número aparece en el texto como número suelto (acepta 0.5, 0,5 y 50 %)."""
    variantes = {f"{valor:g}", f"{valor:g}".replace(".", ",")}
    if isinstance(valor, float) and 0 < valor < 1:
        variantes.add(f"{valor * 100:g} ?%")
    return any(re.search(rf"(?<![\d.,]){v}(?![\d]|[.,]\d)", texto) for v in variantes)


def _dice_nombre(texto: str, nombre: str) -> bool:
    """True si el nombre aparece en el texto, sin importar mayúsculas ni tildes."""
    return normalizar_nombre(nombre) in normalizar_nombre(texto)


def comparar(caso_id: str, esperado: dict, respuesta: str, llamadas: list[dict],
             limite_alcanzado: bool) -> list[dict]:
    """Compara cada dato esperado de un caso con lo que dice la respuesta.

    La comparación es textual y deliberadamente simple: busca en la respuesta cada número
    y cada nombre esperado. Sirve para revisar rápido; la valoración final la hace una
    persona (T22).

    Args:
        caso_id: "C1" a "C6".
        esperado: Resultado de calcular_esperado para el caso.
        respuesta: Respuesta final de la directora.
        llamadas: Llamadas registradas (con "herramienta" y "error").
        limite_alcanzado: Si el ciclo alcanzó el límite.

    Returns:
        Lista de {"dato", "esperado", "obtenido", "coincide"}.

    Example:
        >>> e = {"sala_tripulante": "Bodega", "pasos_alienigena_tripulante": 15}
        >>> [d["coincide"] for d in comparar("C1", e, "Está en Bodega, a 15 pasos.", [], False)]
        [True, True]
    """
    def dato(nombre: str, valor: Any, coincide: bool) -> dict:
        return {"dato": nombre, "esperado": valor,
                "obtenido": "mencionado" if coincide else "no mencionado", "coincide": coincide}

    def numero(nombre: str, valor: float) -> dict:
        return dato(nombre, valor, _dice_numero(respuesta, valor))

    def nombre(nombre_dato: str, valor: str) -> dict:
        return dato(nombre_dato, valor, _dice_nombre(respuesta, valor))

    if caso_id == "C1":
        return [nombre("sala del tripulante", esperado["sala_tripulante"]),
                numero("pasos del alienígena al tripulante", esperado["pasos_alienigena_tripulante"])]
    if caso_id == "C2":
        negacion = re.search(r"\bno\b", respuesta.lower()) is not None
        return [dato("lo ve", "no" if not esperado["ve"] else "sí",
                     negacion if not esperado["ve"] else not negacion)]
    if caso_id == "C3":
        return [nombre("sala destino", esperado["sala"]), numero("confianza", esperado["confianza"])]
    if caso_id == "C4":
        afirma = re.search(r"\bs[ií]\b", respuesta.lower()) is not None
        return [nombre("sala de la pista", esperado["sala_pista"]),
                numero("pistas restantes", esperado["pistas_restantes"]),
                numero("pasos antes", esperado["pasos_antes"]),
                numero("pasos después", esperado["pasos_despues"]),
                dato("se acercó", "sí" if esperado["se_acerco"] else "no",
                     afirma if esperado["se_acerco"] else not afirma)]
    if caso_id == "C5":
        sin_ruta = not any(ll["herramienta"] == "ruta_mas_corta" and not ll["error"]
                           for ll in llamadas)
        salas = re.findall(r"Salas válidas: (.*?)\.", esperado["error"])[0].split(", ")
        return [dato("dice que la sala no existe", "no existe", _dice_nombre(respuesta, "no existe")),
                dato("lista las 8 salas válidas", "8 salas",
                     all(_dice_nombre(respuesta, s) for s in salas)),
                dato("no calcula una ruta", "ninguna ruta calculada", sin_ruta)]
    if caso_id == "C6":
        datos = [dato("alcanza el límite", True, limite_alcanzado),
                 dato("dice que alcanzó el límite", "límite", _dice_nombre(respuesta, "límite"))]
        texto = normalizar_nombre(respuesta.replace("*", ""))
        for sala, pasos in esperado["pasos_por_sala"].items():
            # El número tiene que venir poco después del nombre y seguido de "paso"; así una
            # frase como "las otras 3 salas (Bodega, ...)" no cuenta como distancia.
            encontrado = re.search(rf"{re.escape(normalizar_nombre(sala))}\W{{0,6}}(\d+) ?pasos?\b", texto)
            if encontrado:  # solo se compara lo que la respuesta informa; el resto lo cortó el límite
                obtenido = int(encontrado.group(1))
                datos.append({"dato": f"pasos a {sala}", "esperado": pasos,
                              "obtenido": obtenido, "coincide": obtenido == pasos})
        return datos
    raise ValueError(f"Caso sin comparación definida: {caso_id}.")


def sugerir_valoracion(caso: dict, comparacion: list[dict], llamadas: list[dict]) -> str:
    """Valoración sugerida a partir de la comparación: correcto, parcial o incorrecto, con motivo.

    Args:
        caso: El caso, con sus herramientas_esperadas.
        comparacion: Resultado de comparar.
        llamadas: Llamadas registradas.

    Returns:
        Texto como "correcto: ..." o "parcial: ...".

    Example:
        >>> sugerir_valoracion({"herramientas_esperadas": ["ve_tripulante"]},
        ...                    [{"dato": "lo ve", "coincide": True}], [{"herramienta": "ve_tripulante"}])
        'correcto: coinciden los 1 datos esperados; usó ve_tripulante.'
    """
    fallan = [d["dato"] for d in comparacion if not d["coincide"]]
    usadas = list(dict.fromkeys(ll["herramienta"] for ll in llamadas))
    texto_usadas = f"usó {', '.join(usadas)}." if usadas else "no usó herramientas."
    if not fallan:
        return f"correcto: coinciden los {len(comparacion)} datos esperados; {texto_usadas}"
    veredicto = "incorrecto" if len(fallan) == len(comparacion) else "parcial"
    return f"{veredicto}: no coincide {', '.join(fallan)}; {texto_usadas}"


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
        ClaveFaltanteError: Si no se pasó cliente y falta la clave del proveedor.
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
        esperado = calcular_esperado(caso["id"], semilla)
        llamadas = [{"herramienta": r.herramienta, "argumentos": r.argumentos,
                     "resultado": r.resultado, "segundos": round(r.segundos, 4),
                     "error": r.error} for r in resultado.registro]
        comparacion = comparar(caso["id"], esperado, resultado.respuesta, llamadas,
                               resultado.limite_alcanzado)
        resultados.append({
            **caso,
            "semilla_caso": semilla_caso,
            "resultado_esperado": esperado,
            "respuesta": resultado.respuesta,
            "llamadas": llamadas,
            "numero_llamadas": resultado.llamadas,
            "limite_alcanzado": resultado.limite_alcanzado,
            "latencia_segundos": round(latencia, 3),
            "comparacion": comparacion,
            "valoracion_sugerida": sugerir_valoracion(caso, comparacion, llamadas),
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


def recomparar(ruta_json: str | Path) -> tuple[Path, Path]:
    """Recalcula la comparación y la valoración sugerida de una evidencia ya guardada.

    No vuelve a llamar al modelo: usa las respuestas y llamadas del JSON. Sirve cuando se
    corrige la comparación automática sin querer repetir la corrida.

    Args:
        ruta_json: JSON escrito por ejecutar_casos.

    Returns:
        Rutas del JSON y del Markdown reescritos.
    """
    ruta_json = Path(ruta_json)
    informe = json.loads(ruta_json.read_text(encoding="utf-8"))
    for c in informe["casos"]:
        c["comparacion"] = comparar(c["id"], c["resultado_esperado"], c["respuesta"],
                                    c["llamadas"], c["limite_alcanzado"])
        c["valoracion_sugerida"] = sugerir_valoracion(c, c["comparacion"], c["llamadas"])
    ruta_json.write_text(json.dumps(informe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ruta_md = ruta_json.with_suffix(".md")
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
        "| Caso | Categoría | Llamadas | Límite alcanzado | Latencia (s) | Comparación automática "
        "| Valoración sugerida | Correcto |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for c in informe["casos"]:
        bien = sum(d["coincide"] for d in c["comparacion"])
        lineas.append(f"| {c['id']} | {c['categoria']} | {c['numero_llamadas']} | "
                      f"{'sí' if c['limite_alcanzado'] else 'no'} | {c['latencia_segundos']} | "
                      f"{bien} de {len(c['comparacion'])} | "
                      f"{c['valoracion_sugerida'].split(':')[0]} | |")
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
            "**Comparación automática:**", "",
            "| Dato | Esperado | Obtenido | Coincide |", "|---|---|---|---|",
            *[f"| {d['dato']} | {d['esperado']} | {d['obtenido']} | {'sí' if d['coincide'] else 'no'} |"
              for d in c["comparacion"]],
            "", f"**Valoración sugerida:** {c['valoracion_sugerida']}", "",
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
    parser.add_argument("--recomparar", metavar="ARCHIVO_JSON",
                        help="Recalcula la comparación de una evidencia guardada, sin el modelo.")
    args = parser.parse_args(argv)
    if args.recomparar:
        ruta_json, ruta_md = recomparar(args.recomparar)
        print(f"Comparación recalculada en {ruta_json} y {ruta_md}")
        return 0
    try:
        ruta_json, ruta_md = ejecutar_casos(semilla=args.semilla, salida=args.salida)
    except ClaveFaltanteError as exc:
        print(f"No se pueden correr los casos.\n{exc}", file=sys.stderr)
        return CODIGO_SIN_CLAVE
    print(f"Resultados en {ruta_json} y {ruta_md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
