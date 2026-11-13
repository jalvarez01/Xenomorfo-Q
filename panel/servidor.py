"""Servidor HTTP local del panel, solo con la biblioteca estándar.

Sirve la página (panel/estatico/index.html) y una API JSON sobre una Sesion. Escucha solo
en 127.0.0.1: el panel es una ayuda visual local, no un servicio. La clave del modelo
nunca sale del servidor: no está en ninguna respuesta ni en ningún registro.

Rutas:
    GET  /              la página.
    GET  /api/mapa      datos fijos del mapa.
    GET  /api/estado    estado actual.
    POST /api/paso      un tick con el bot (modo observar).
    POST /api/mover     {"direccion"}: un tick moviendo al tripulante (modo "Tú").
    POST /api/reiniciar {"semilla"}: partida nueva.
    POST /api/preguntar {"pregunta"}: pregunta a la directora sobre la misma partida.

Contenido principal:
    crear_servidor: arma el ThreadingHTTPServer con su Sesion.
    HOST: dirección en la que escucha.

Tareas relacionadas: T24 (demostración), D16.
"""
from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from panel.sesion import Sesion

# Solo la máquina local: así nadie más en la red ve la partida ni usa el modelo.
HOST = "127.0.0.1"
# Página del panel; se lee de disco en cada petición para poder editarla sin reiniciar.
PAGINA = Path(__file__).resolve().parent / "estatico" / "index.html"
# Tamaño máximo del cuerpo de una petición, en bytes.
MAX_CUERPO = 4096


class _Manejador(BaseHTTPRequestHandler):
    """Atiende la página y la API JSON. La sesión se asigna al crear el servidor."""

    sesion: Sesion

    def log_message(self, formato: str, *args) -> None:
        """No registra peticiones en la terminal: el chat no debe quedar en ningún registro."""

    # ------------------------------------------------------------------ GET
    def do_GET(self) -> None:  # noqa: N802 - nombre fijo de http.server
        """Página, mapa o estado."""
        if self.path in ("/", "/index.html"):
            self._enviar(HTTPStatus.OK, PAGINA.read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/mapa":
            self._json(HTTPStatus.OK, self.sesion.mapa())
        elif self.path == "/api/estado":
            self._json(HTTPStatus.OK, self.sesion.estado())
        else:
            self._json(HTTPStatus.NOT_FOUND, {"error": "Ruta desconocida."})

    # ----------------------------------------------------------------- POST
    def do_POST(self) -> None:  # noqa: N802 - nombre fijo de http.server
        """Paso, movimiento manual, reinicio o pregunta."""
        try:
            datos = self._leer_json()
            if self.path == "/api/paso":
                respuesta = self.sesion.paso()
            elif self.path == "/api/mover":
                respuesta = self.sesion.mover(str(datos.get("direccion", "")))
            elif self.path == "/api/reiniciar":
                respuesta = self.sesion.reiniciar(datos.get("semilla", 42))
            elif self.path == "/api/preguntar":
                respuesta = self.sesion.preguntar(datos.get("pregunta", ""))
            else:
                self._json(HTTPStatus.NOT_FOUND, {"error": "Ruta desconocida."})
                return
        except ValueError as exc:
            # Errores esperables (partida terminada, dirección o semilla inválida): el
            # mensaje es nuestro y no lleva datos sensibles.
            self._json(HTTPStatus.CONFLICT, {"error": str(exc), "estado": self.sesion.estado()})
            return
        self._json(HTTPStatus.OK, respuesta)

    # ------------------------------------------------------------- internos
    def _leer_json(self) -> dict:
        """Cuerpo de la petición como diccionario; vacío si no hay cuerpo.

        Raises:
            ValueError: Si el cuerpo es muy grande o no es un objeto JSON.
        """
        largo = int(self.headers.get("Content-Length") or 0)
        if largo > MAX_CUERPO:
            raise ValueError("El cuerpo de la petición es demasiado grande.")
        if largo == 0:
            return {}
        try:
            datos = json.loads(self.rfile.read(largo).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ValueError("El cuerpo de la petición no es JSON válido.") from None
        if not isinstance(datos, dict):
            raise ValueError("El cuerpo de la petición debe ser un objeto JSON.")
        return datos

    def _json(self, estado: HTTPStatus, datos: dict) -> None:
        """Responde un diccionario como JSON."""
        cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
        self._enviar(estado, cuerpo, "application/json; charset=utf-8")

    def _enviar(self, estado: HTTPStatus, cuerpo: bytes, tipo: str) -> None:
        """Envía la respuesta sin caché, para que el navegador siempre vea el estado actual."""
        self.send_response(estado)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(cuerpo)


def crear_servidor(sesion: Sesion, puerto: int = 8000) -> ThreadingHTTPServer:
    """Crea el servidor del panel sobre una sesión, escuchando solo en 127.0.0.1.

    Args:
        sesion: Sesión con la partida y la directora.
        puerto: Puerto local; 0 elige uno libre (útil en las pruebas).

    Returns:
        El servidor, listo para serve_forever().

    Raises:
        OSError: Si el puerto está ocupado.
    """
    manejador = type("Manejador", (_Manejador,), {"sesion": sesion})
    return ThreadingHTTPServer((HOST, puerto), manejador)
