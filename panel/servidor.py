"""Servidor HTTP local del panel, solo con la biblioteca estándar.

Sirve la página (panel/estatico/index.html) y una API JSON. Escucha solo en 127.0.0.1: en
local es una ayuda visual y en línea (D18) Caddy es el único que escucha en la red y le pasa
las peticiones. La clave del modelo nunca sale del servidor: no está en ninguna respuesta ni
en ningún registro.

Cada visitante tiene su propia partida, identificada por una cookie aleatoria (HttpOnly,
SameSite=Lax y Secure cuando Caddy avisa que la petición llegó por HTTPS). El chat tiene
cupos de preguntas por sesión y por hora; pasado un cupo responde 429 con un aviso y lo
demás sigue funcionando (panel/sesiones.py).

Rutas:
    GET  /              la página.
    GET  /salud         {"ok": true}, para comprobar que el servicio está vivo.
    GET  /api/mapa      datos fijos del mapa.
    GET  /api/estado    estado actual.
    POST /api/paso      un tick con el bot (modo observar).
    POST /api/mover     {"direccion"}: un tick moviendo al tripulante (modo "Tú").
    POST /api/reiniciar {"semilla", "nivel"}: partida nueva; sin nivel conserva el actual.
    POST /api/preguntar {"pregunta"}: pregunta a la directora sobre la misma partida.

Contenido principal:
    crear_servidor: arma el ThreadingHTTPServer con sus sesiones y cupos.
    HOST: dirección en la que escucha.

Tareas relacionadas: T24 (demostración), D16, D18.
"""
from __future__ import annotations

import json
from http import HTTPStatus
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from panel.sesion import Sesion, validar_pregunta
from panel.sesiones import (NOMBRE_COOKIE, AlmacenFijo, AlmacenSesiones, Entrada,
                            LimitePreguntas)

# Solo la máquina local: en línea, Caddy recibe las peticiones de la red y las reenvía aquí.
HOST = "127.0.0.1"
# Página del panel; se lee de disco en cada petición para poder editarla sin reiniciar.
PAGINA = Path(__file__).resolve().parent / "estatico" / "index.html"
# Tamaño máximo del cuerpo de una petición, en bytes.
MAX_CUERPO = 4096
# Únicas direcciones cuyo X-Forwarded-Proto se cree: el proxy corre en la misma máquina.
PROXIES_CONFIABLES = ("127.0.0.1",)


class _Manejador(BaseHTTPRequestHandler):
    """Atiende la página y la API JSON. Las sesiones y los cupos se asignan al crear el servidor."""

    almacen: AlmacenSesiones | AlmacenFijo
    limite: LimitePreguntas

    def log_message(self, formato: str, *args) -> None:
        """No registra peticiones en la terminal: el chat no debe quedar en ningún registro."""

    # ------------------------------------------------------------------ GET
    def do_GET(self) -> None:  # noqa: N802 - nombre fijo de http.server
        """Página, salud, mapa o estado."""
        self._cookie_nueva: str | None = None
        # Se enruta solo por la ruta: la página acepta parámetros como ?modo=tu.
        ruta = urlsplit(self.path).path
        if ruta == "/salud":
            self._json(HTTPStatus.OK, {"ok": True})
        elif ruta in ("/", "/index.html"):
            # La sesión se crea al cargar la página, así las peticiones siguientes ya
            # llevan la cookie y no crean sesiones de más.
            self._entrada()
            self._enviar(HTTPStatus.OK, PAGINA.read_bytes(), "text/html; charset=utf-8")
        elif ruta == "/api/mapa":
            self._json(HTTPStatus.OK, self._entrada().sesion.mapa())
        elif ruta == "/api/estado":
            self._json(HTTPStatus.OK, self._entrada().sesion.estado())
        else:
            self._json(HTTPStatus.NOT_FOUND, {"error": "Ruta desconocida."})

    # ----------------------------------------------------------------- POST
    def do_POST(self) -> None:  # noqa: N802 - nombre fijo de http.server
        """Paso, movimiento manual, reinicio o pregunta."""
        self._cookie_nueva = None
        ruta = urlsplit(self.path).path
        if ruta not in ("/api/paso", "/api/mover", "/api/reiniciar", "/api/preguntar"):
            self._json(HTTPStatus.NOT_FOUND, {"error": "Ruta desconocida."})
            return
        entrada = self._entrada()
        sesion = entrada.sesion
        try:
            datos = self._leer_json()
            if ruta == "/api/paso":
                respuesta = sesion.paso()
            elif ruta == "/api/mover":
                respuesta = sesion.mover(str(datos.get("direccion", "")))
            elif ruta == "/api/reiniciar":
                nivel = datos.get("nivel")
                respuesta = sesion.reiniciar(datos.get("semilla", 42),
                                             None if nivel is None else str(nivel))
            else:
                pregunta = validar_pregunta(datos.get("pregunta", ""))
                aviso = self.limite.reservar(entrada)
                if aviso is not None:
                    self._json(HTTPStatus.TOO_MANY_REQUESTS,
                               {"error": aviso, "estado": sesion.estado()})
                    return
                respuesta = sesion.preguntar(pregunta)
        except ValueError as exc:
            # Errores esperables (partida terminada, dirección, semilla o pregunta inválida):
            # el mensaje es nuestro y no lleva datos sensibles.
            self._json(HTTPStatus.CONFLICT, {"error": str(exc), "estado": sesion.estado()})
            return
        self._json(HTTPStatus.OK, respuesta)

    # ------------------------------------------------------------- internos
    def _entrada(self) -> Entrada:
        """Sesión del visitante según su cookie; si es nueva, la cookie se envía con la respuesta."""
        token, entrada, nueva = self.almacen.obtener(self._token_cookie())
        if nueva and token is not None:
            self._cookie_nueva = token
        return entrada

    def _token_cookie(self) -> str | None:
        """Valor de la cookie de sesión, o None si no llegó o no se puede leer."""
        cookies = SimpleCookie()
        try:
            cookies.load(self.headers.get("Cookie", ""))
        except CookieError:
            return None
        morsel = cookies.get(NOMBRE_COOKIE)
        return None if morsel is None else morsel.value

    def _por_https(self) -> bool:
        """Si la petición llegó por HTTPS según el proxy local (Caddy)."""
        return (self.client_address[0] in PROXIES_CONFIABLES
                and self.headers.get("X-Forwarded-Proto", "").lower() == "https")

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
        if getattr(self, "_cookie_nueva", None):
            atributos = "Path=/; HttpOnly; SameSite=Lax" + ("; Secure" if self._por_https() else "")
            self.send_header("Set-Cookie", f"{NOMBRE_COOKIE}={self._cookie_nueva}; {atributos}")
        self.end_headers()
        self.wfile.write(cuerpo)


def crear_servidor(sesiones: Sesion | AlmacenSesiones | AlmacenFijo, puerto: int = 8000,
                   limite: LimitePreguntas | None = None) -> ThreadingHTTPServer:
    """Crea el servidor del panel, escuchando solo en 127.0.0.1.

    Args:
        sesiones: Un AlmacenSesiones (una partida por visitante, lo que usa python -m panel)
            o una Sesion, que entonces comparten todos los visitantes.
        puerto: Puerto local; 0 elige uno libre (útil en las pruebas).
        limite: Cupos del chat. None los lee de XQ_PANEL_MAX_SESION y XQ_PANEL_MAX_HORA.

    Returns:
        El servidor, listo para serve_forever().

    Raises:
        OSError: Si el puerto está ocupado.
        ValueError: Si una variable de cupo no es un entero mayor o igual a 0.
    """
    almacen = AlmacenFijo(sesiones) if isinstance(sesiones, Sesion) else sesiones
    limite = LimitePreguntas.desde_entorno() if limite is None else limite
    manejador = type("Manejador", (_Manejador,), {"almacen": almacen, "limite": limite})
    return ThreadingHTTPServer((HOST, puerto), manejador)
