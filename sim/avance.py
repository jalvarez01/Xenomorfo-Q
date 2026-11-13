"""Avance de la simulación varios ticks con registro de eventos (T10).

Base de la herramienta avanzar_simulacion del agente: avanza la partida de 1 a 20 ticks
y devuelve una lista de eventos en texto para que el agente pueda resumir lo ocurrido.

Quién mueve al alienígena no se decide aquí: se pasa una "política", una función que
recibe el entorno y devuelve la acción del alienígena (0 a 4). Así este módulo no
depende del alienígena por reglas (T18), que se conecta después sin cambiar nada.

Eventos que se registran:
    - El tripulante o el alienígena entra a una sala distinta de la última en que estuvo.
    - El alienígena empieza a ver al tripulante o lo pierde de vista, según
      info["ve_tripulante"], que el entorno informa desde la visión (T08). Si un entorno
      no lo informa, no se registran.
    - Eventos propios de la política, si tiene un método tomar_eventos(). El alienígena
      por reglas (alien/reglas.py) informa así cuándo llega a la sala de una pista.
    - Eventos de la función tras_tick, si se pasa una (el panel la usa para su pista
      automática, D19).
    - Captura del tripulante.
    - Fin de la partida por tiempo (max_ticks).

Si la política tiene un método accion_extra() que devuelve una acción, Avance la aplica
en el mismo tick con env.paso_extra_alien() (persecución rápida de los niveles del
panel, D19). Por defecto ninguna de las dos cosas está activa.

Contenido principal:
    Avance: avanza un EstacionEnv y guarda el historial de eventos de la partida.
    TOPE_TICKS: máximo de ticks por llamada.

Tareas relacionadas: T10 (este módulo), T11 (la herramienta avanzar_simulacion),
T08 (visión), T18 (alienígena por reglas), T19 (pistas).
"""
from __future__ import annotations

from collections.abc import Callable

from .env import EstacionEnv
from .mapa import SIN_SALA

# Máximo de ticks que se pueden avanzar en una sola llamada (pestaña 'Contratos').
TOPE_TICKS = 20

# Función que recibe el entorno y devuelve la acción del alienígena (0 a 4).
PoliticaAlien = Callable[[EstacionEnv], int]
# Función opcional que se llama al final de cada tick sin captura, con el entorno y el
# info del tick; devuelve eventos en texto (sin el prefijo del tick).
TrasTick = Callable[[EstacionEnv, dict], list[str]]


class Avance:
    """Avanza una partida y registra lo que pasa en cada tick.

    Se crea uno por partida, después de env.reset(), porque recuerda la última sala de
    cada personaje y si el alienígena estaba viendo al tripulante.

    Args:
        env: Entorno ya iniciado con reset().
        politica: Función que recibe el entorno y devuelve la acción del alienígena.
        tras_tick: Función opcional que se llama al final de cada tick sin captura y
            devuelve eventos propios. None, el valor por defecto, no hace nada.

    Attributes:
        env: Entorno que se avanza.
        politica: Política del alienígena.
        tras_tick: La función de fin de tick, o None. Se puede asignar después de crear
            el Avance.
        historial: Todos los eventos de la partida, en orden, de todas las llamadas.

    Example:
        >>> def siempre_derecha(env):
        ...     return 1
        >>> env = EstacionEnv()
        >>> _ = env.reset(42)
        >>> avance = Avance(env, siempre_derecha)
        >>> avance.avanzar(3)
        {'tick': 3, 'ticks_avanzados': 3, 'eventos': [], 'capturado': False}
    """

    def __init__(self, env: EstacionEnv, politica: PoliticaAlien,
                 tras_tick: TrasTick | None = None):
        self.env = env
        self.politica = politica
        self.tras_tick = tras_tick
        self.historial: list[str] = []
        self._sala_tripulante = env.mapa.sala(env.tripulante[0], env.tripulante[1])
        self._sala_alien = env.mapa.sala(env.alien[0], env.alien[1])
        # Al empezar la partida se asume que el alienígena no ve al tripulante.
        self._ve = False

    def avanzar(self, ticks: int, accion_tripulante: int | None = None) -> dict:
        """Avanza la partida hasta ticks ticks, o menos si termina antes.

        Args:
            ticks: Ticks a avanzar, de 1 a TOPE_TICKS.
            accion_tripulante: Movimiento manual del tripulante en cada tick (ver
                EstacionEnv.step); None deja al bot, como siempre.

        Returns:
            Diccionario serializable a JSON con:
                tick: Tick de la partida al terminar.
                ticks_avanzados: Ticks que avanzó (menos que ticks si la partida terminó).
                eventos: Eventos de esta llamada, en texto, por ejemplo
                    "tick 12: el tripulante entró a Laboratorio".
                capturado: True si el tripulante fue capturado.

        Raises:
            ValueError: Si ticks no es un entero entre 1 y TOPE_TICKS, o si la partida
                ya terminó.
        """
        # bool es un tipo de int en Python; se rechaza para que True no cuente como 1.
        if not isinstance(ticks, int) or isinstance(ticks, bool):
            raise ValueError(f"ticks debe ser un número entero, no {ticks!r}.")
        if ticks < 1 or ticks > TOPE_TICKS:
            raise ValueError(f"ticks debe estar entre 1 y {TOPE_TICKS}, no {ticks}.")
        if self._capturado():
            raise ValueError("La partida ya terminó: el tripulante fue capturado.")
        if self.env.tick >= self.env.max_ticks:
            raise ValueError(
                f"La partida ya terminó: se alcanzó el máximo de {self.env.max_ticks} ticks.")

        eventos = []
        avanzados = 0
        capturado = False
        for _ in range(ticks):
            accion = self.politica(self.env)
            # Solo se pasa si hay control manual, así los entornos de prueba con step(accion)
            # siguen funcionando y el bot se usa exactamente como antes.
            if accion_tripulante is None:
                _, _, terminado, info = self.env.step(accion)
            else:
                _, _, terminado, info = self.env.step(accion, accion_tripulante)
            avanzados += 1
            tick = info["tick"]

            # Paso extra de persecución (D19): solo si la política lo ofrece y le toca. Una
            # función simple o AlienReglas sin paso_extra_cada nunca lo da.
            accion_extra = getattr(self.politica, "accion_extra", None)
            if accion_extra is not None and not info["capturado"]:
                extra = accion_extra()
                if extra is not None:
                    info = {**info, **self.env.paso_extra_alien(extra)}

            sala = self.env.mapa.sala(self.env.tripulante[0], self.env.tripulante[1])
            # En una puerta la sala es SIN_SALA: se ignora y se recuerda la anterior.
            if sala != SIN_SALA and sala != self._sala_tripulante:
                eventos.append(f"tick {tick}: el tripulante entró a {self._nombre(sala)}")
                self._sala_tripulante = sala

            sala = self.env.mapa.sala(self.env.alien[0], self.env.alien[1])
            if sala != SIN_SALA and sala != self._sala_alien:
                eventos.append(f"tick {tick}: el alienígena entró a {self._nombre(sala)}")
                self._sala_alien = sala

            # Un entorno sin visión no trae ve_tripulante; en ese caso no hay eventos de vista.
            if "ve_tripulante" in info:
                ve = bool(info["ve_tripulante"])
                if ve and not self._ve:
                    eventos.append(f"tick {tick}: el alienígena vio al tripulante")
                if not ve and self._ve:
                    eventos.append(f"tick {tick}: el alienígena perdió de vista al tripulante")
                self._ve = ve

            # La política puede tener eventos propios, como la llegada a la sala de una
            # pista (AlienReglas, T19). Una función simple no tiene tomar_eventos: se salta.
            tomar_eventos = getattr(self.politica, "tomar_eventos", None)
            if tomar_eventos is not None:
                for texto in tomar_eventos():
                    eventos.append(f"tick {tick}: {texto}")

            if self.tras_tick is not None and not info["capturado"]:
                for texto in self.tras_tick(self.env, info):
                    eventos.append(f"tick {tick}: {texto}")

            if info["capturado"]:
                capturado = True
                eventos.append(f"tick {tick}: el alienígena capturó al tripulante")
                break
            if terminado:
                eventos.append(
                    f"tick {tick}: se acabó el tiempo de la partida ({self.env.max_ticks} ticks)")
                break

        self.historial.extend(eventos)
        return {
            "tick": self.env.tick,
            "ticks_avanzados": avanzados,
            "eventos": eventos,
            "capturado": capturado,
        }

    def _capturado(self) -> bool:
        """True si el alienígena está en la casilla del tripulante o en una contigua.

        Es la misma regla de captura del entorno (distancia Manhattan de 1 o menos).
        """
        dx = abs(self.env.alien[0] - self.env.tripulante[0])
        dy = abs(self.env.alien[1] - self.env.tripulante[1])
        return dx + dy <= 1

    def _nombre(self, sala: int) -> str:
        """Nombre de la sala a partir de su índice."""
        return self.env.mapa.nombres_salas[sala]
