"""Una partida por visitante y límites de costo del chat del panel.

En local hay un solo visitante y todo se comporta como antes. En línea (D18) cada navegador
recibe una cookie aleatoria y su propia Sesion, así dos visitantes nunca mueven la misma
partida. Las sesiones viven en memoria: como máximo MAX_SESIONES, se descartan tras
INACTIVIDAD_SEGUNDOS sin uso y, si el almacén está lleno, se descarta la usada hace más
tiempo (LRU).

El chat llama al modelo, que cuesta dinero, así que tiene dos cupos: preguntas por sesión y
preguntas por hora en todo el servidor. Pasado un cupo, el chat responde con un aviso y el
mapa, el modo observar y el modo "Tú" siguen funcionando.

Contenido principal:
    AlmacenSesiones: sesiones por cookie, con caducidad y descarte LRU; seguro para hilos.
    AlmacenFijo: una sola Sesion para todos (la usan las pruebas y crear_servidor(Sesion)).
    Entrada: una sesión con su último uso y sus preguntas.
    LimitePreguntas: cupos de preguntas por sesión y por hora.
    leer_limite: lee un cupo de una variable de entorno.
    token_valido: si un texto tiene la forma de un token de sesión.

Tareas relacionadas: T24 (demostración), D16, D18.
"""
from __future__ import annotations

import os
import re
import secrets
import threading
import time
from collections import OrderedDict, deque
from dataclasses import dataclass
from typing import Callable, Mapping

from panel.sesion import Sesion

# Nombre de la cookie con el token de la sesión.
NOMBRE_COOKIE = "xq_sesion"
# Sesiones vivas como máximo; cada una es una partida en memoria.
MAX_SESIONES = 30
# Tiempo sin peticiones tras el que una sesión se descarta, en segundos.
INACTIVIDAD_SEGUNDOS = 30 * 60
# Bytes aleatorios del token; secrets.token_urlsafe(32) da 43 caracteres.
BYTES_TOKEN = 32
# Forma de un token válido; cualquier otro valor de la cookie se ignora.
_PATRON_TOKEN = re.compile(r"[A-Za-z0-9_-]{43}")

# Variables de entorno de los cupos del chat; 0 desactiva el cupo.
VAR_MAX_SESION = "XQ_PANEL_MAX_SESION"
VAR_MAX_HORA = "XQ_PANEL_MAX_HORA"
MAX_SESION_POR_DEFECTO = 20
MAX_HORA_POR_DEFECTO = 60
# Ventana del cupo por hora, en segundos.
VENTANA_HORA = 3600


def token_valido(token: str | None) -> bool:
    """Si el texto tiene la forma de un token de sesión.

    Example:
        >>> token_valido("a" * 43), token_valido("corto"), token_valido(None)
        (True, False, False)
    """
    return token is not None and _PATRON_TOKEN.fullmatch(token) is not None


def leer_limite(nombre: str, por_defecto: int, entorno: Mapping[str, str] | None = None) -> int:
    """Lee un cupo de una variable de entorno.

    Args:
        nombre: Nombre de la variable.
        por_defecto: Valor si la variable no existe o está vacía.
        entorno: Variables a usar; None usa os.environ.

    Returns:
        El cupo; 0 significa sin cupo.

    Raises:
        ValueError: Si el valor no es un entero mayor o igual a 0.

    Example:
        >>> leer_limite("X", 20, {}), leer_limite("X", 20, {"X": "5"}), leer_limite("X", 20, {"X": ""})
        (20, 5, 20)
    """
    valor = (os.environ if entorno is None else entorno).get(nombre, "").strip()
    if not valor:
        return por_defecto
    if not valor.isdigit():
        raise ValueError(f"{nombre} debe ser un entero mayor o igual a 0; se recibió {valor!r}.")
    return int(valor)


@dataclass
class Entrada:
    """Una sesión del almacén.

    Attributes:
        sesion: La partida y la directora de este visitante.
        ultimo_uso: Momento de la última petición, según el reloj del almacén.
        preguntas: Preguntas al modelo hechas en esta sesión (no se reinicia con la partida).
    """

    sesion: Sesion
    ultimo_uso: float
    preguntas: int = 0


class AlmacenSesiones:
    """Sesiones por token de cookie, con caducidad por inactividad y descarte LRU.

    Args:
        fabrica: Crea la Sesion de un visitante nuevo.
        max_sesiones: Sesiones vivas como máximo.
        inactividad: Segundos sin uso tras los que una sesión se descarta.
        reloj: Función que da el tiempo en segundos (las pruebas pasan uno falso).

    Example:
        >>> almacen = AlmacenSesiones(lambda: Sesion(semilla=42), max_sesiones=2)
        >>> token, entrada, nueva = almacen.obtener(None)
        >>> nueva, almacen.obtener(token)[2], len(almacen)
        (True, False, 1)
    """

    def __init__(self, fabrica: Callable[[], Sesion], max_sesiones: int = MAX_SESIONES,
                 inactividad: float = INACTIVIDAD_SEGUNDOS,
                 reloj: Callable[[], float] = time.monotonic):
        if max_sesiones < 1:
            raise ValueError("max_sesiones debe ser al menos 1.")
        self._fabrica = fabrica
        self._max = max_sesiones
        self._inactividad = inactividad
        self._reloj = reloj
        # Orden de uso: la primera es la usada hace más tiempo.
        self._sesiones: OrderedDict[str, Entrada] = OrderedDict()
        self._candado = threading.Lock()

    def __len__(self) -> int:
        with self._candado:
            return len(self._sesiones)

    def obtener(self, token: str | None) -> tuple[str | None, Entrada, bool]:
        """Sesión del token, o una nueva si el token no existe, caducó o no es válido.

        Args:
            token: Valor de la cookie, o None si no llegó.

        Returns:
            (token, entrada, nueva). Si nueva es True, hay que enviar la cookie con el token.
        """
        ahora = self._reloj()
        with self._candado:
            self._descartar_caducadas(ahora)
            if token_valido(token) and token in self._sesiones:
                entrada = self._sesiones[token]
                entrada.ultimo_uso = ahora
                self._sesiones.move_to_end(token)
                return token, entrada, False
            while len(self._sesiones) >= self._max:
                self._sesiones.popitem(last=False)
            nuevo = secrets.token_urlsafe(BYTES_TOKEN)
            entrada = Entrada(self._fabrica(), ahora)
            self._sesiones[nuevo] = entrada
            return nuevo, entrada, True

    def _descartar_caducadas(self, ahora: float) -> None:
        """Quita las sesiones sin uso durante más de la inactividad permitida."""
        while self._sesiones:
            token, entrada = next(iter(self._sesiones.items()))
            if ahora - entrada.ultimo_uso <= self._inactividad:
                break
            del self._sesiones[token]


class AlmacenFijo:
    """Una sola Sesion para todos los visitantes, sin cookie.

    Lo usa crear_servidor cuando recibe una Sesion: las pruebas y quien quiera compartir una
    partida fija.

    Args:
        sesion: La sesión compartida.
    """

    def __init__(self, sesion: Sesion):
        self._entrada = Entrada(sesion, 0.0)

    def __len__(self) -> int:
        return 1

    def obtener(self, token: str | None) -> tuple[str | None, Entrada, bool]:
        """Siempre la misma sesión; nunca pide enviar una cookie."""
        return None, self._entrada, False


class LimitePreguntas:
    """Cupos del chat: preguntas por sesión y preguntas por hora en todo el servidor.

    Args:
        max_sesion: Preguntas por sesión; 0 sin cupo.
        max_hora: Preguntas en la última hora en todo el servidor; 0 sin cupo.
        reloj: Función que da el tiempo en segundos (las pruebas pasan uno falso).

    Example:
        >>> limite = LimitePreguntas(max_sesion=1, max_hora=0)
        >>> entrada = Entrada(Sesion(semilla=42), 0.0)
        >>> limite.reservar(entrada) is None, limite.reservar(entrada) is None
        (True, False)
    """

    def __init__(self, max_sesion: int = MAX_SESION_POR_DEFECTO,
                 max_hora: int = MAX_HORA_POR_DEFECTO,
                 reloj: Callable[[], float] = time.monotonic):
        self.max_sesion = max_sesion
        self.max_hora = max_hora
        self._reloj = reloj
        self._ultima_hora: deque[float] = deque()
        self._candado = threading.Lock()

    @classmethod
    def desde_entorno(cls, entorno: Mapping[str, str] | None = None) -> "LimitePreguntas":
        """Cupos de XQ_PANEL_MAX_SESION y XQ_PANEL_MAX_HORA (20 y 60 si no están).

        Raises:
            ValueError: Si alguna variable no es un entero mayor o igual a 0.
        """
        return cls(leer_limite(VAR_MAX_SESION, MAX_SESION_POR_DEFECTO, entorno),
                   leer_limite(VAR_MAX_HORA, MAX_HORA_POR_DEFECTO, entorno))

    def reservar(self, entrada: Entrada) -> str | None:
        """Cuenta una pregunta si cabe en los dos cupos.

        Args:
            entrada: La sesión que pregunta.

        Returns:
            None si la pregunta cabe (y queda contada), o el aviso en español si no cabe.
        """
        ahora = self._reloj()
        with self._candado:
            while self._ultima_hora and ahora - self._ultima_hora[0] >= VENTANA_HORA:
                self._ultima_hora.popleft()
            if self.max_sesion and entrada.preguntas >= self.max_sesion:
                return (f"Llegaste al máximo de {self.max_sesion} preguntas a la directora en esta "
                        "sesión. El mapa, el modo observar y el modo Tú siguen funcionando.")
            if self.max_hora and len(self._ultima_hora) >= self.max_hora:
                return (f"El panel llegó al máximo de {self.max_hora} preguntas a la directora en "
                        "la última hora. Intenta más tarde; el mapa, el modo observar y el modo "
                        "Tú siguen funcionando.")
            entrada.preguntas += 1
            self._ultima_hora.append(ahora)
            return None
