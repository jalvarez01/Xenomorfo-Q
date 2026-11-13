"""Comando del panel visual: python -m panel [--semilla 42] [--puerto 8000] [--abrir].

Levanta el servidor local (siempre en 127.0.0.1), imprime la URL y, con --abrir, abre el
navegador. Cada visitante tiene su propia partida (cookie de sesión) y el chat tiene cupos
de preguntas (XQ_PANEL_MAX_SESION y XQ_PANEL_MAX_HORA). Sin clave del modelo el panel
funciona igual (mapa, observar y jugar); el chat muestra el mismo mensaje de configuración
que python -m director.

El puerto sale de --puerto, si no de la variable PORT y si no es 8000. No hay opción para
escuchar en otra dirección: en línea, Caddy es el único que escucha en la red (D18).

Contenido principal:
    main: interpreta los argumentos y corre el servidor hasta Ctrl+C.
    leer_argumentos: argumentos del comando, con el puerto por defecto tomado de PORT.

Tareas relacionadas: T24 (demostración), D16, D18.
"""
from __future__ import annotations

import argparse
import os
import sys
import webbrowser
from typing import Mapping

from director.partida import SEMILLA_POR_DEFECTO
from panel.servidor import HOST, crear_servidor
from panel.sesion import Sesion
from panel.sesiones import AlmacenSesiones, LimitePreguntas

# Puerto por defecto del panel si no hay --puerto ni PORT.
PUERTO_POR_DEFECTO = 8000
# Variable de entorno con el puerto (convención de los servicios de despliegue).
VAR_PUERTO = "PORT"


def leer_argumentos(argv: list[str] | None = None,
                    entorno: Mapping[str, str] | None = None) -> argparse.Namespace:
    """Argumentos del comando; el puerto por defecto sale de PORT si está definida.

    Args:
        argv: Argumentos sin el nombre del programa. None usa sys.argv.
        entorno: Variables de entorno; None usa os.environ.

    Returns:
        Namespace con semilla, puerto y abrir.

    Example:
        >>> leer_argumentos([], {"PORT": "9000"}).puerto, leer_argumentos(["--puerto", "1"], {"PORT": "9000"}).puerto
        (9000, 1)
    """
    entorno = os.environ if entorno is None else entorno
    parser = argparse.ArgumentParser(prog="python -m panel",
                                     description="Panel visual local de Xenomorfo-Q.")
    parser.add_argument("--semilla", type=int, default=SEMILLA_POR_DEFECTO,
                        help="Semilla de cada partida nueva (por defecto 42).")
    parser.add_argument("--puerto", type=int, default=None,
                        help="Puerto local (por defecto PORT o 8000).")
    parser.add_argument("--abrir", action="store_true", help="Abre el navegador al iniciar.")
    args = parser.parse_args(argv)
    if args.puerto is None:
        valor = entorno.get(VAR_PUERTO, "").strip()
        if valor and not valor.isdigit():
            parser.error(f"{VAR_PUERTO} debe ser un número de puerto; se recibió {valor!r}.")
        args.puerto = int(valor) if valor else PUERTO_POR_DEFECTO
    return args


def main(argv: list[str] | None = None) -> int:
    """Corre el panel.

    Args:
        argv: Argumentos sin el nombre del programa. None usa sys.argv.

    Returns:
        0 al cerrar con Ctrl+C; 1 si el puerto está ocupado o un cupo es inválido.
    """
    args = leer_argumentos(argv)
    try:
        limite = LimitePreguntas.desde_entorno()
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    almacen = AlmacenSesiones(lambda: Sesion(semilla=args.semilla))
    try:
        servidor = crear_servidor(almacen, args.puerto, limite)
    except OSError as exc:
        print(f"No se pudo abrir el puerto {args.puerto}: {exc.strerror}. Prueba con --puerto.",
              file=sys.stderr)
        return 1
    url = f"http://{HOST}:{servidor.server_port}/"
    # flush: el aviso tiene que verse aunque la salida vaya a un archivo o a otro proceso.
    print(f"Panel de Xenomorfo-Q en {url} (Ctrl+C para cerrar)", flush=True)
    if args.abrir:
        webbrowser.open(url)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        servidor.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
