"""Comando del panel visual: python -m panel [--semilla 42] [--puerto 8000] [--abrir].

Levanta el servidor local (solo 127.0.0.1), imprime la URL y, con --abrir, abre el
navegador. Sin clave del modelo el panel funciona igual (mapa, observar y jugar); el chat
muestra el mismo mensaje de configuración que python -m director.

Contenido principal:
    main: interpreta los argumentos y corre el servidor hasta Ctrl+C.

Tareas relacionadas: T24 (demostración), D16.
"""
from __future__ import annotations

import argparse
import sys
import webbrowser

from director.partida import SEMILLA_POR_DEFECTO
from panel.servidor import HOST, crear_servidor
from panel.sesion import Sesion

# Puerto por defecto del panel.
PUERTO_POR_DEFECTO = 8000


def main(argv: list[str] | None = None) -> int:
    """Corre el panel.

    Args:
        argv: Argumentos sin el nombre del programa. None usa sys.argv.

    Returns:
        0 al cerrar con Ctrl+C; 1 si el puerto está ocupado.
    """
    parser = argparse.ArgumentParser(prog="python -m panel",
                                     description="Panel visual local de Xenomorfo-Q.")
    parser.add_argument("--semilla", type=int, default=SEMILLA_POR_DEFECTO,
                        help="Semilla de la partida inicial (por defecto 42).")
    parser.add_argument("--puerto", type=int, default=PUERTO_POR_DEFECTO,
                        help="Puerto local (por defecto 8000).")
    parser.add_argument("--abrir", action="store_true", help="Abre el navegador al iniciar.")
    args = parser.parse_args(argv)
    try:
        servidor = crear_servidor(Sesion(semilla=args.semilla), args.puerto)
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
