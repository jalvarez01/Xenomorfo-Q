"""Comando para preguntarle a la directora desde la terminal (T11).

Uso:
    python -m director "¿En qué sala está el tripulante?" [--semilla 42] [--limite 6] [--registro]
    python -m director            (modo interactivo: "salir" termina, "estado" muestra
                                   estado_partida sin usar el modelo)

Si falta la clave del proveedor (OPENAI_API_KEY o NVIDIA_API_KEY, según XQ_PROVEEDOR), muestra
cómo configurarla y termina con código 2, sin traza.

Contenido principal:
    main: interpreta los argumentos y devuelve el código de salida.
    CODIGO_SIN_CLAVE: código de salida cuando falta la clave.

Tareas relacionadas: T11 (directora), T14 (configuración del LLM), T24 (demostración).
"""
from __future__ import annotations

import argparse
import json
import sys

from director.agente import LIMITE_POR_DEFECTO, formatear_registro
from director.directora import Directora
from director.llm import ClaveFaltanteError
from director.partida import SEMILLA_POR_DEFECTO

# Código de salida cuando falta la clave; distinto de 1 para distinguirlo de otros errores.
CODIGO_SIN_CLAVE = 2
# Palabras del modo interactivo.
SALIR, ESTADO = "salir", "estado"


def main(argv: list[str] | None = None) -> int:
    """Ejecuta el comando.

    Args:
        argv: Argumentos sin el nombre del programa. None usa sys.argv.

    Returns:
        0 si todo salió bien, CODIGO_SIN_CLAVE si falta la clave.
    """
    parser = argparse.ArgumentParser(
        prog="python -m director",
        description="Pregúntale a la directora sobre una partida simulada de Vela-9.")
    parser.add_argument("pregunta", nargs="?", help="Pregunta en español. Sin pregunta, "
                        "abre el modo interactivo.")
    parser.add_argument("--semilla", type=int, default=SEMILLA_POR_DEFECTO,
                        help="Semilla de la partida (por defecto 42).")
    parser.add_argument("--limite", type=int, default=LIMITE_POR_DEFECTO,
                        help="Máximo de llamadas a herramientas por pregunta (por defecto 6).")
    parser.add_argument("--registro", action="store_true",
                        help="Muestra también las llamadas a herramientas.")
    args = parser.parse_args(argv)

    directora = Directora(semilla=args.semilla, limite=args.limite)
    try:
        if args.pregunta is not None:
            _responder(directora, args.pregunta, args.registro)
        else:
            _interactivo(directora, args.registro)
    except ClaveFaltanteError as exc:
        print(f"No se puede consultar el modelo.\n{exc}", file=sys.stderr)
        return CODIGO_SIN_CLAVE
    return 0


def _responder(directora: Directora, pregunta: str, registro: bool) -> None:
    """Hace una pregunta e imprime la respuesta y, si se pide, el registro."""
    resultado = directora.preguntar(pregunta)
    print(resultado.respuesta)
    if registro:
        print()
        print(formatear_registro(resultado.registro))
        print(f"Llamadas: {resultado.llamadas}. Límite alcanzado: "
              f"{'sí' if resultado.limite_alcanzado else 'no'}.")


def _interactivo(directora: Directora, registro: bool) -> None:
    """Bucle de preguntas hasta 'salir' o fin de la entrada."""
    print(f"Directora de Vela-9, partida con semilla {directora.partida.semilla}. "
          f"Escribe '{SALIR}' para terminar o '{ESTADO}' para ver el estado sin el modelo.")
    while True:
        try:
            linea = input("> ").strip()
        except EOFError:
            print()
            return
        if not linea:
            continue
        if linea.lower() == SALIR:
            return
        if linea.lower() == ESTADO:
            print(json.dumps(directora.herramientas["estado_partida"](), ensure_ascii=False,
                             indent=2))
            continue
        _responder(directora, linea, registro)


if __name__ == "__main__":
    sys.exit(main())
