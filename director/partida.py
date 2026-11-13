"""Una partida de la estación con todo lo que consultan las herramientas (T11).

Reúne el entorno, el alienígena por reglas, el avance con eventos y el predictor de
destino de una misma partida. Las herramientas del agente (director/herramientas.py)
leen y modifican siempre esta partida, así que su estado se conserva entre preguntas.

Contenido principal:
    Partida: entorno, alienígena, avance y predictor de una partida, con la última sala
        conocida de cada personaje.

Tareas relacionadas: T11 (herramientas), T10 (avance), T12 (predecir_destino), T18 y
T19 (alienígena por reglas y pistas).
"""
from __future__ import annotations

from alien.reglas import AlienReglas
from director.prediccion import PredictorDestino
from sim.avance import Avance
from sim.env import MAPA_POR_DEFECTO, EstacionEnv
from sim.mapa import DIRS, SIN_SALA, Mapa

# Semilla por defecto: la misma de los ejemplos de docs/, para que los resultados se
# puedan comparar con lo documentado.
SEMILLA_POR_DEFECTO = 42
# Ticks máximos de una partida antes de terminar sin captura.
MAX_TICKS_POR_DEFECTO = 300


class Partida:
    """Una partida: entorno, alienígena por reglas, avance y predictor de destino.

    Args:
        semilla: Semilla de env.reset(); la misma semilla da la misma partida.
        max_ticks: Ticks máximos de la partida.
        mapa: Mapa con salas o ruta a un archivo de mapa. None usa vela9.

    Raises:
        ValueError: Si el mapa no tiene salas.

    Attributes:
        env: Entorno de la partida, ya iniciado.
        alien: AlienReglas; también es la política del avance y guarda las pistas.
        avance: Avance que mueve la partida y registra eventos.
        predictor: PredictorDestino del mapa (precalcula distancias una sola vez).
        semilla: Semilla con la que se inició.

    Example:
        >>> p = Partida()
        >>> p.env.alien, p.env.tripulante
        ((1, 2), (2, 12))
        >>> p.nombre_sala(p.ultima_sala_tripulante()), p.nombre_sala(p.ultima_sala_alien())
        ('Bodega', 'Médico')
    """

    def __init__(self, semilla: int = SEMILLA_POR_DEFECTO,
                 max_ticks: int = MAX_TICKS_POR_DEFECTO, mapa: Mapa | str | None = None):
        self.semilla = semilla
        self.env = EstacionEnv(mapa if mapa is not None else MAPA_POR_DEFECTO,
                               max_ticks=max_ticks)
        if self.env.mapa.n_salas == 0:
            raise ValueError("El mapa no tiene salas; las herramientas las necesitan.")
        self.env.reset(semilla)
        self.alien = AlienReglas(self.env)
        self.avance = Avance(self.env, self.alien)
        self.predictor = PredictorDestino(self.env.mapa)
        self._sala_alien = SIN_SALA
        self._registrar_sala_alien()

    def avanzar(self, ticks: int, accion_tripulante: int | None = None) -> dict:
        """Avanza la partida con el alienígena por reglas y actualiza su última sala.

        Args:
            ticks: Ticks a avanzar, de 1 a 20.
            accion_tripulante: Movimiento manual del tripulante (panel, modo de juego);
                None deja al bot. Las herramientas del agente nunca lo usan.

        Returns:
            El resultado de Avance.avanzar: {tick, ticks_avanzados, eventos, capturado}.

        Raises:
            ValueError: Si ticks no es válido o la partida ya terminó.
        """
        resultado = self.avance.avanzar(ticks, accion_tripulante)
        self._registrar_sala_alien()
        return resultado

    def ultima_sala_tripulante(self) -> int:
        """Índice de la última sala en la que estuvo el tripulante.

        Recorre env.trayectoria hacia atrás hasta la primera casilla con sala, así una
        puerta informa la sala de la que viene.

        Returns:
            Índice de sala, o SIN_SALA si en toda la partida solo estuvo en puertas.
        """
        mapa = self.env.mapa
        for x, y in reversed(self.env.trayectoria):
            if mapa.sala(x, y) != SIN_SALA:
                return mapa.sala(x, y)
        return SIN_SALA

    def ultima_sala_alien(self) -> int:
        """Índice de la sala del alienígena, o la última en la que estuvo si está en una puerta.

        En una puerta mira la casilla de atrás (la opuesta a direccion_alien), que es de
        donde viene. Si esa casilla tampoco tiene sala, usa la última sala registrada
        después de cada avance.

        Returns:
            Índice de sala, o SIN_SALA si nunca estuvo en una sala.
        """
        mapa = self.env.mapa
        x, y = self.env.alien
        if mapa.sala(x, y) != SIN_SALA:
            return mapa.sala(x, y)
        dx, dy = self.env.direccion_alien
        if mapa.sala(x - dx, y - dy) != SIN_SALA:
            return mapa.sala(x - dx, y - dy)
        return self._sala_alien

    def nombre_sala(self, indice: int) -> str | None:
        """Nombre de una sala por su índice; None para SIN_SALA."""
        return None if indice == SIN_SALA else self.env.mapa.nombres_salas[indice]

    def _registrar_sala_alien(self) -> None:
        """Guarda la sala actual del alienígena para cuando quede en una puerta.

        Al empezar en una puerta, sin casilla de atrás con sala, usa la primera vecina
        con sala en el orden de DIRS, para que siempre haya una sala que informar.
        """
        sala = self.ultima_sala_alien()
        if sala == SIN_SALA:
            x, y = self.env.alien
            for dx, dy in DIRS:
                if self.env.mapa.sala(x + dx, y + dy) != SIN_SALA:
                    sala = self.env.mapa.sala(x + dx, y + dy)
                    break
        if sala != SIN_SALA:
            self._sala_alien = sala
