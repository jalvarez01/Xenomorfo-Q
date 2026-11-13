"""Estado de una sesión del panel: la partida que se ve en el mapa y la directora que la consulta.

La sesión envuelve una Directora: el mapa, los pasos del modo observar, los movimientos del
modo "Tú" y las preguntas del chat usan la MISMA partida (directora.partida). Todo lo que
devuelve sale del código de la simulación y del agente; la sesión no simula nada por su
cuenta.

Niveles de dificultad (D19), solo en el panel: normal (todo por defecto, la partida de
siempre), dificil (visión de 10 casillas y un paso extra al perseguir cada 3 ticks) y
pesadilla (dificil más una pista automática hacia la sala real del tripulante tras 25
ticks sin verlo, como máximo 3 por partida, aparte de las 3 de la directora).

Ninguna respuesta incluye la clave del modelo ni el texto de errores de la API (que puede
repetir parte de la clave): solo el nombre del error.

Contenido principal:
    Sesion: mapa, estado, paso, mover, preguntar y reiniciar.
    Nivel, NIVELES, NIVEL_POR_DEFECTO: los niveles de dificultad.
    PistaAutomatica: la pista automática del nivel pesadilla.
    validar_pregunta: limpia una pregunta y rechaza las vacías o demasiado largas.
    rama_alien: rama activa del árbol del alienígena y su casilla objetivo, sin modificarlo.
    objetivo_alien: solo la casilla objetivo (para dibujar la ruta).
    RAMAS: nombre visible de cada rama del árbol.
    DIRECCIONES: nombre de cada dirección y su acción (0 a 3).

Tareas relacionadas: T24 (demostración), T11 (directora), T18 y T19 (alienígena), D16.
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from typing import Any

from alien.reglas import PISTAS_POR_PARTIDA, AlienReglas
from director.directora import Directora
from director.llm import ClaveFaltanteError, ConfigLLM
from director.partida import SEMILLA_POR_DEFECTO
from director.partida import Partida
from sim.env import EstacionEnv
from sim.mapa import DIRS, SIN_SALA
from sim.percepcion import ALCANCE_VISION
from sim.rutas import ruta

# Acción del entorno para cada dirección que manda el navegador (el orden de DIRS).
DIRECCIONES = {"arriba": 0, "derecha": 1, "abajo": 2, "izquierda": 3, "quieto": 4}
# Nombre de la dirección del alienígena, para los instrumentos.
NOMBRES_DIRECCION = dict(zip(DIRS, ("arriba", "derecha", "abajo", "izquierda")))
# Ramas del árbol de AlienReglas, en orden de prioridad, con su nombre visible. La etiqueta
# del mapa y el panel de reglas usan esta misma clave, así nunca se contradicen.
RAMAS = {"persigue": "Persigue", "ultima_casilla": "Última casilla vista",
         "pista": "Va a la pista", "patrulla": "Patrulla"}
# Largo del rastro del tripulante que se dibuja, en casillas.
LARGO_RASTRO = 12
# Entradas del registro que se envían al navegador (las más recientes).
LARGO_REGISTRO = 40
# Largo máximo del resultado de una herramienta en el chat, en caracteres.
LARGO_RESULTADO = 160
# Largo máximo de una pregunta, en caracteres; protege el servidor de cuerpos enormes.
LARGO_PREGUNTA = 500


@dataclass(frozen=True)
class Nivel:
    """Un nivel de dificultad del panel (D19).

    Attributes:
        nombre: Nombre visible.
        alcance_vision: Alcance de la visión del alienígena, en casillas.
        paso_extra_cada: Paso extra al perseguir cada tantos ticks, o None.
        pista_auto_ticks: Ticks sin ver al tripulante tras los que llega una pista
            automática, o None si el nivel no la tiene.
        pista_auto_max: Pistas automáticas por partida.
    """

    nombre: str
    alcance_vision: float = ALCANCE_VISION
    paso_extra_cada: int | None = None
    pista_auto_ticks: int | None = None
    pista_auto_max: int = 0

    def opciones_partida(self) -> dict:
        """Parámetros de Partida que cambian; vacío en normal, así la partida es la de siempre."""
        opciones = {}
        if self.alcance_vision != ALCANCE_VISION:
            opciones["alcance_vision"] = self.alcance_vision
        if self.paso_extra_cada is not None:
            opciones["paso_extra_cada"] = self.paso_extra_cada
        return opciones


# Niveles del panel, en el orden del selector. normal es la partida de siempre.
NIVELES = {
    "normal": Nivel("Normal"),
    "dificil": Nivel("Difícil", alcance_vision=10, paso_extra_cada=3),
    "pesadilla": Nivel("Pesadilla", alcance_vision=10, paso_extra_cada=3,
                       pista_auto_ticks=25, pista_auto_max=3),
}
NIVEL_POR_DEFECTO = "normal"


class PistaAutomatica:
    """Pista automática del nivel pesadilla: una regla del panel, no de la directora.

    Se engancha como Avance.tras_tick, así cuenta cada tick, también los que avanza la
    directora con avanzar_simulacion. Si el alienígena pasa ticks_sin_ver ticks seguidos
    sin ver al tripulante, le da una pista hacia la sala real del tripulante con
    AlienReglas.dar_pista(sala, contar=False): no gasta las pistas de la directora y
    lleva su propio presupuesto.

    Args:
        partida: La partida (para la sala del tripulante y el alienígena).
        ticks_sin_ver: Ticks seguidos sin verlo antes de dar la pista.
        maximo: Pistas automáticas por partida.

    Attributes:
        restantes: Pistas automáticas que quedan.
        sin_ver: Ticks seguidos sin ver al tripulante.
    """

    def __init__(self, partida: Partida, ticks_sin_ver: int, maximo: int):
        self.partida = partida
        self.ticks_sin_ver = ticks_sin_ver
        self.restantes = maximo
        self.sin_ver = 0

    def __call__(self, env: EstacionEnv, info: dict) -> list[str]:
        """Cuenta el tick y, si toca, da la pista; devuelve el evento para el registro."""
        if info.get("ve_tripulante"):
            self.sin_ver = 0
            return []
        self.sin_ver += 1
        if self.sin_ver < self.ticks_sin_ver or self.restantes == 0:
            return []
        sala = self.partida.ultima_sala_tripulante()
        if sala == SIN_SALA:
            return []
        nombre = self.partida.alien.dar_pista(env.mapa.nombres_salas[sala], contar=False)["sala"]
        self.restantes -= 1
        self.sin_ver = 0
        return [f"directora automática: pista hacia {nombre}"]


def rama_alien(alien: AlienReglas) -> tuple[str, tuple[int, int]]:
    """Rama del árbol que el alienígena va a seguir y su casilla objetivo, sin modificarlo.

    Repite el orden de AlienReglas.decidir (lo ve, última casilla vista, pista, patrulla)
    sin llamar a decidir, que cambia su estado. La etiqueta del mapa, el panel de reglas y
    la ruta dibujada salen de este mismo cálculo.

    Args:
        alien: El alienígena de la partida.

    Returns:
        (rama, objetivo): una clave de RAMAS y la casilla (x, y) a la que va.

    Example:
        >>> s = Sesion(semilla=42)
        >>> rama_alien(s.directora.partida.alien)[0]
        'patrulla'
    """
    env = alien.env
    x, y = env.tripulante
    if env.campo_vision[y, x]:
        return "persigue", env.tripulante
    if alien.ultima_vista is not None and env.alien != alien.ultima_vista:
        return "ultima_casilla", alien.ultima_vista
    if alien.pista is not None:
        return "pista", alien.centros[alien.pista]
    # _objetivo es el centro de patrulla actual; solo se lee para mostrarlo.
    return "patrulla", alien.centros[alien._objetivo]


def objetivo_alien(alien: AlienReglas) -> tuple[int, int]:
    """Casilla hacia la que va el alienígena (la de rama_alien)."""
    return rama_alien(alien)[1]


def validar_pregunta(pregunta: object) -> str:
    """Pregunta sin espacios sobrantes en los extremos, lista para la directora.

    Args:
        pregunta: Texto que mandó el navegador.

    Returns:
        La pregunta limpia.

    Raises:
        ValueError: Si la pregunta está vacía o supera LARGO_PREGUNTA caracteres.

    Example:
        >>> validar_pregunta("  ¿Dónde está?  ")
        '¿Dónde está?'
    """
    pregunta = str(pregunta).strip()
    if not pregunta:
        raise ValueError("La pregunta está vacía.")
    if len(pregunta) > LARGO_PREGUNTA:
        raise ValueError(f"La pregunta supera los {LARGO_PREGUNTA} caracteres.")
    return pregunta


def _una_linea(texto: str) -> str:
    """Resultado de herramienta en una línea y recortado, para el chat."""
    texto = " ".join(str(texto).split())
    return texto if len(texto) <= LARGO_RESULTADO else texto[:LARGO_RESULTADO - 3] + "..."


class Sesion:
    """Partida del panel con su directora; segura para varios hilos del servidor.

    Args:
        semilla: Semilla de la partida inicial.
        cliente: Cliente del modelo (las pruebas pasan uno falso). None crea el real en la
            primera pregunta, con la clave del entorno.
        config: Configuración del modelo. None la lee del entorno.
        nivel: Clave de NIVELES; por defecto "normal", la partida de siempre.

    Attributes:
        directora: La directora; directora.partida es la partida que se ve.
        nivel: Clave del nivel actual.
        pista_auto: La PistaAutomatica de la partida, o None si el nivel no la tiene.
        chat: Preguntas hechas en esta partida, con respuesta y llamadas.
        registro: Eventos del avance y llamadas del agente, en orden.

    Example:
        >>> s = Sesion(semilla=42)
        >>> e = s.estado()
        >>> e["tick"], e["tripulante"]["sala"], e["alien"]["sala"]
        (0, 'Bodega', 'Médico')
    """

    def __init__(self, semilla: int = SEMILLA_POR_DEFECTO, cliente: Any = None,
                 config: ConfigLLM | None = None, nivel: str = NIVEL_POR_DEFECTO):
        # Un solo candado: el navegador puede pedir un paso mientras el chat espera al
        # modelo, y la partida no se puede modificar desde dos hilos a la vez.
        self._candado = threading.RLock()
        self._cliente = cliente
        self._config = config
        self.nivel = NIVEL_POR_DEFECTO
        self.reiniciar(semilla, nivel)

    # ------------------------------------------------------------------ API
    def reiniciar(self, semilla: int = SEMILLA_POR_DEFECTO, nivel: str | None = None) -> dict:
        """Empieza una partida nueva y vacía el chat y el registro.

        Args:
            semilla: Semilla de la partida.
            nivel: Clave de NIVELES. None conserva el nivel actual.

        Returns:
            El estado de la partida nueva.

        Raises:
            ValueError: Si la semilla no es un entero o el nivel no existe.
        """
        if not isinstance(semilla, int) or isinstance(semilla, bool):
            raise ValueError("La semilla debe ser un número entero.")
        if nivel is not None and nivel not in NIVELES:
            raise ValueError(f"Nivel desconocido: {nivel!r}. Usa uno de: {', '.join(NIVELES)}.")
        with self._candado:
            if nivel is not None:
                self.nivel = nivel
            datos = NIVELES[self.nivel]
            self.directora = Directora(semilla=semilla, cliente=self._cliente, config=self._config,
                                       opciones_partida=datos.opciones_partida())
            self.pista_auto = None
            if datos.pista_auto_ticks is not None:
                self.pista_auto = PistaAutomatica(self.directora.partida, datos.pista_auto_ticks,
                                                  datos.pista_auto_max)
                self.directora.partida.avance.tras_tick = self.pista_auto
            self.chat: list[dict] = []
            self.registro: list[dict] = []
            self._eventos_vistos = 0
            texto = f"partida nueva con semilla {semilla}"
            if self.nivel != NIVEL_POR_DEFECTO:
                texto += f", nivel {datos.nombre.lower()}"
            self._anotar("sistema", texto)
            return self.estado()

    def mapa(self) -> dict:
        """Datos fijos del mapa para dibujarlo: filas, salas y su posición de etiqueta.

        Returns:
            {"ancho", "alto", "filas", "salas", "nombres_salas", "etiquetas"}, donde salas
            es la matriz de índices de sala (-1 en paredes y puertas).
        """
        with self._candado:
            mapa = self.directora.partida.env.mapa
            etiquetas = []
            for indice, nombre in enumerate(mapa.nombres_salas):
                celdas = [(x, y) for x, y in mapa.transitables if mapa.sala(x, y) == indice]
                x, y = min(celdas, key=lambda c: (c[1], c[0]))
                etiquetas.append({"nombre": nombre, "x": x, "y": y})
            return {"ancho": mapa.ancho, "alto": mapa.alto, "filas": list(mapa.filas),
                    "salas": mapa.salas.tolist(), "nombres_salas": list(mapa.nombres_salas),
                    "etiquetas": etiquetas}

    def estado(self) -> dict:
        """Estado actual de la partida, tal como lo calculan la simulación y el alienígena.

        Returns:
            Diccionario serializable a JSON con posiciones, salas, visión, ruta prevista,
            pistas, captura, registro y chat.
        """
        with self._candado:
            partida = self.directora.partida
            env, alien = partida.env, partida.alien
            camino = ruta(env.mapa, env.alien, env.tripulante)
            capturado = env._captura()
            rama, objetivo = rama_alien(alien)
            ruta_prevista = ruta(env.mapa, env.alien, objetivo) or [env.alien]
            # nonzero() da enteros de numpy; JSON necesita int de Python.
            vision = [[int(x), int(y)] for y, x in zip(*env.campo_vision.nonzero())]
            return {
                "semilla": partida.semilla,
                "tick": env.tick,
                "max_ticks": env.max_ticks,
                "capturado": capturado,
                "terminado": capturado or env.tick >= env.max_ticks,
                "tripulante": {"x": env.tripulante[0], "y": env.tripulante[1],
                               "sala": partida.nombre_sala(partida.ultima_sala_tripulante())},
                "alien": {"x": env.alien[0], "y": env.alien[1],
                          "sala": partida.nombre_sala(partida.ultima_sala_alien()),
                          "direccion": NOMBRES_DIRECCION[env.direccion_alien],
                          "dx": env.direccion_alien[0], "dy": env.direccion_alien[1],
                          "rama": rama, "rama_texto": RAMAS[rama]},
                "ve": bool(env.campo_vision[env.tripulante[1], env.tripulante[0]]),
                "distancia": None if camino is None else len(camino) - 1,
                "pistas_restantes": alien.pistas_restantes,
                "pistas_max": PISTAS_POR_PARTIDA,
                "nivel": self.nivel,
                "nivel_texto": NIVELES[self.nivel].nombre,
                "niveles": {clave: n.nombre for clave, n in NIVELES.items()},
                "alcance_vision": env.alcance_vision,
                "pistas_auto_restantes": 0 if self.pista_auto is None else self.pista_auto.restantes,
                "pistas_auto_max": NIVELES[self.nivel].pista_auto_max,
                "pista_activa": alien.pista_activa,
                "vision": vision,
                "ruta": [list(c) for c in ruta_prevista],
                "rastro": [list(c) for c in env.trayectoria[-LARGO_RASTRO:]],
                "modelo": self.directora.config.modelo,
                "proveedor": self.directora.config.proveedor,
                "registro": self.registro[-LARGO_REGISTRO:],
                "chat": self.chat,
            }

    def paso(self) -> dict:
        """Avanza un tick con el bot del tripulante y el alienígena por reglas (modo observar).

        Returns:
            El estado después del tick.

        Raises:
            ValueError: Si la partida ya terminó.
        """
        with self._candado:
            self.directora.partida.avanzar(1)
            self._sincronizar_eventos()
            return self.estado()

    def mover(self, direccion: str) -> dict:
        """Avanza un tick moviendo al tripulante a mano (modo "Tú").

        El alienígena decide igual que siempre; el tripulante va en la dirección pedida si
        la casilla es transitable y no es la del alienígena (si no, se queda).

        Args:
            direccion: "arriba", "derecha", "abajo", "izquierda" o "quieto".

        Returns:
            El estado después del tick.

        Raises:
            ValueError: Si la dirección no existe o la partida ya terminó.
        """
        if direccion not in DIRECCIONES:
            raise ValueError(f"Dirección desconocida: {direccion!r}. Usa una de: "
                             f"{', '.join(DIRECCIONES)}.")
        with self._candado:
            self.directora.partida.avanzar(1, DIRECCIONES[direccion])
            self._sincronizar_eventos()
            return self.estado()

    def preguntar(self, pregunta: str) -> dict:
        """Hace una pregunta a la directora sobre la partida que se ve en el mapa.

        Args:
            pregunta: Pregunta en español.

        Returns:
            {"respuesta", "llamadas", "numero_llamadas", "limite_alcanzado", "estado"}, o
            {"error", "estado"} si falta la clave o el modelo no respondió.

        Raises:
            ValueError: Si la pregunta está vacía o es demasiado larga.
        """
        pregunta = validar_pregunta(pregunta)
        with self._candado:
            try:
                resultado = self.directora.preguntar(pregunta)
            except ClaveFaltanteError as exc:
                # El mismo mensaje del comando: nombra la variable y .env.example, sin valores.
                return {"error": f"No se puede consultar el modelo.\n{exc}", "estado": self.estado()}
            except Exception as exc:  # noqa: BLE001 - el texto de la API puede repetir parte de la clave
                codigo = getattr(exc, "status_code", None)
                detalle = type(exc).__name__ + (f" (código {codigo})" if codigo else "")
                return {"error": f"El modelo no respondió: {detalle}.", "estado": self.estado()}
            llamadas = [{"herramienta": r.herramienta, "argumentos": r.argumentos,
                         "resultado": _una_linea(r.resultado), "error": r.error}
                        for r in resultado.registro]
            for llamada in llamadas:
                argumentos = json.dumps(llamada["argumentos"], ensure_ascii=False)
                self._anotar("agente", f"{llamada['herramienta']}({argumentos}) -> {llamada['resultado']}")
            self._sincronizar_eventos()
            entrada = {"pregunta": pregunta, "respuesta": resultado.respuesta, "llamadas": llamadas,
                       "numero_llamadas": resultado.llamadas,
                       "limite_alcanzado": resultado.limite_alcanzado,
                       "tick": self.directora.partida.env.tick}
            self.chat.append(entrada)
            return {**entrada, "estado": self.estado()}

    # ------------------------------------------------------------- internos
    def _anotar(self, tipo: str, texto: str) -> None:
        """Agrega una entrada al registro con el tick actual."""
        self.registro.append({"tick": self.directora.partida.env.tick, "tipo": tipo, "texto": texto})

    def _sincronizar_eventos(self) -> None:
        """Pasa al registro los eventos nuevos de Avance (pasos, juego o herramientas)."""
        historial = self.directora.partida.avance.historial
        for evento in historial[self._eventos_vistos:]:
            self._anotar("evento", evento)
        self._eventos_vistos = len(historial)
