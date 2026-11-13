"""Entorno mínimo de la estación (versión 0, tarea T07).

Es la simulación que consultan y operan las herramientas del agente directora: la
partida (posiciones, salas, captura) vive aquí y las herramientas la leen o la hacen
avanzar.

Interfaz tipo Gym, descrita en docs/contratos.md:
    obs = env.reset(semilla)
    obs, recompensa, terminado, info = env.step(accion)

El tensor de observación y la recompensa se conservan del diseño inicial porque no
estorban y mantienen la interfaz estable, pero el agente no los usa (decisión D8 en
docs/decisiones.md).

Versión 0: movimiento, captura y visión del alienígena (T08, sim/percepcion.py), con
direccion_alien, campo_vision e info["ve_tripulante"]. Las rutas con A* (T09) están en
sim/rutas.py y el avance con eventos (T10) en sim/avance.py; ninguno cambia esta interfaz.

Contenido principal:
    EstacionEnv: el entorno, con el alienígena movido por quien llama a step() y un
        tripulante movido por un bot provisional.
    Constantes de acciones y recompensas.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from .mapa import DIRS, Mapa
from .percepcion import ALCANCE_VISION, campo_de_vision

# Mapa que se usa cuando no se pasa ninguno. Se resuelve desde la ubicación del paquete
# para que funcione sin importar el directorio de trabajo.
MAPA_POR_DEFECTO = Path(__file__).resolve().parent.parent / "data" / "mapas" / "vela9.txt"

# Acciones del alienígena: 0 arriba, 1 derecha, 2 abajo, 3 izquierda, 4 revisar casillero
N_ACCIONES = 5
# Recompensas en puntos: R_CAPTURA al atrapar al tripulante, R_PASO en cada tick
# (empuja a capturar rápido) y R_CASILLERO_VACIO como castigo adicional por revisar
# un casillero sin nadie.
R_CAPTURA, R_PASO, R_CASILLERO_VACIO = 100.0, -1.0, -5.0
# Dirección (dx, dy) en la que mira el alienígena al empezar: hacia abajo (y crece hacia abajo).
DIRECCION_INICIAL = (0, 1)


class EstacionEnv:
    """Entorno de caza en la estación con interfaz tipo Gym.

    Quien llama a step() controla al alienígena; en el diseño actual será el
    alienígena por reglas (T18). El tripulante se mueve después de cada acción con un
    bot provisional. Hay captura cuando la distancia Manhattan entre ambos es
    1 o menos.

    Args:
        mapa: Un Mapa ya construido o la ruta a un archivo de mapa.
        max_ticks: Ticks máximos por episodio antes de cortarlo sin captura.
        distancia_inicial: Distancia Manhattan mínima entre alienígena y tripulante al
            iniciar, en casillas.
        semilla: Semilla del generador aleatorio. None usa una semilla del sistema.
        alcance_vision: Alcance de la visión del alienígena, en casillas. Por defecto
            ALCANCE_VISION (7.5), el de siempre; el panel lo sube en los niveles difíciles
            (D19).

    Raises:
        ValueError: Si el mapa no es válido o alcance_vision no es mayor que 0.
        FileNotFoundError: Si se pasa una ruta que no existe.

    Attributes:
        mapa: Mapa de la estación.
        rng: Generador aleatorio; controla posiciones iniciales y el bot.
        alien: Posición (x, y) del alienígena.
        tripulante: Posición (x, y) del tripulante.
        tick: Ticks transcurridos en el episodio actual.
        trayectoria: Posiciones del tripulante en el episodio, incluida la inicial.
        direccion_alien: Hacia dónde mira el alienígena, como (dx, dy) de DIRS. Es
            (0, 1) al empezar, cambia con las acciones 0 a 3 (aunque choque) y no cambia
            con la acción 4.
        campo_vision: Matriz booleana (alto, ancho) con las casillas que ve el
            alienígena (sim/percepcion.py, T08). Se recalcula en reset() y en cada tick.
        alcance_vision: Alcance de la visión con el que se calcula campo_vision.

    Example:
        >>> env = EstacionEnv()
        >>> obs = env.reset(42)
        >>> obs.shape
        (4, 15, 24)
    """

    def __init__(self, mapa: Mapa | str | Path = MAPA_POR_DEFECTO, max_ticks: int = 300,
                 distancia_inicial: int = 10, semilla: int | None = None,
                 alcance_vision: float = ALCANCE_VISION):
        if alcance_vision <= 0:
            raise ValueError(f"alcance_vision debe ser mayor que 0; se recibió {alcance_vision}.")
        self.alcance_vision = alcance_vision
        self.mapa = mapa if isinstance(mapa, Mapa) else Mapa.desde_archivo(mapa)
        self.max_ticks = max_ticks
        self.distancia_inicial = distancia_inicial
        self.rng = np.random.default_rng(semilla)
        self.alien = self.tripulante = (0, 0)
        self.tick = 0
        self.trayectoria: list[tuple[int, int]] = []
        self.direccion_alien: tuple[int, int] = DIRECCION_INICIAL
        self.campo_vision = np.zeros((self.mapa.alto, self.mapa.ancho), dtype=bool)

    # ------------------------------------------------------------------ API
    def reset(self, semilla: int | None = None) -> np.ndarray:
        """Inicia un episodio nuevo.

        Ubica al alienígena en una casilla transitable al azar y al tripulante a por lo
        menos distancia_inicial casillas de él.

        Args:
            semilla: Si se pasa, reinicia el generador aleatorio para que el episodio
                sea reproducible. Si es None, continúa con el generador actual.

        Returns:
            Observación inicial de forma (4, alto, ancho) y tipo float32.
        """
        if semilla is not None:
            self.rng = np.random.default_rng(semilla)
        libres = self.mapa.transitables
        self.alien = libres[self.rng.integers(len(libres))]
        # Si el mapa es muy pequeño y ninguna casilla cumple la distancia, se acepta
        # cualquiera para no dejar el episodio sin tripulante.
        lejos = [c for c in libres if _manhattan(c, self.alien) >= self.distancia_inicial] or libres
        self.tripulante = lejos[self.rng.integers(len(lejos))]
        self.tick = 0
        self.trayectoria = [self.tripulante]
        self.direccion_alien = DIRECCION_INICIAL
        self.campo_vision = self._calcular_vision()
        return self._observacion()

    def step(self, accion: int,
             accion_tripulante: int | None = None) -> tuple[np.ndarray, float, bool, dict]:
        """Avanza un tick: mueve al alienígena, luego al tripulante, y revisa captura.

        Args:
            accion: 0 arriba, 1 derecha, 2 abajo, 3 izquierda, 4 revisar casillero.
            accion_tripulante: Movimiento manual del tripulante (0 arriba, 1 derecha, 2
                abajo, 3 izquierda, 4 quieto), para el modo de juego del panel. None usa el
                bot de siempre; así, sin control manual, el generador aleatorio se consume
                igual que antes y las partidas con semilla no cambian.

        Returns:
            Tupla (obs, recompensa, terminado, info):
                obs: Observación (4, alto, ancho) float32.
                recompensa: R_PASO más R_CAPTURA si hubo captura y R_CASILLERO_VACIO
                    si la acción fue 4.
                terminado: True si hubo captura o se llegó a max_ticks.
                info: Diccionario con 'tick', 'capturado', 'distancia_real' y
                    've_tripulante' (si el tripulante está en campo_vision al final
                    del tick).

        Raises:
            ValueError: Si la acción o la acción del tripulante está fuera de 0 a 4.

        Example:
            >>> env = EstacionEnv()
            >>> _ = env.reset(42)
            >>> env.step(1)[1:]
            (-1.0, False, {'tick': 1, 'capturado': False, 'distancia_real': 10, 've_tripulante': False})
        """
        if not 0 <= accion < N_ACCIONES:
            raise ValueError(f"Acción fuera de rango: {accion}")
        if accion_tripulante is not None and not 0 <= accion_tripulante < N_ACCIONES:
            raise ValueError(f"Acción del tripulante fuera de rango: {accion_tripulante}")
        self.tick += 1
        recompensa = R_PASO
        # Mira hacia donde intentó moverse, aunque choque: así se gira sin avanzar.
        if accion < 4:
            self.direccion_alien = DIRS[accion]

        if accion < 4:
            self.alien = self._mover(self.alien, accion)
        else:
            recompensa += R_CASILLERO_VACIO  # Los casilleros todavía no esconden a nadie

        # Se revisa la captura antes y después de mover al tripulante: si el alienígena
        # llega a su lado, el tripulante no alcanza a escapar en ese mismo tick.
        capturado = self._captura()
        if not capturado:
            if accion_tripulante is None:
                self.tripulante = self._paso_tripulante()
            else:
                self.tripulante = self._paso_manual(accion_tripulante)
            self.trayectoria.append(self.tripulante)
            capturado = self._captura()

        # El alienígena ya no se mueve en este tick, así que su campo de visión es final.
        self.campo_vision = self._calcular_vision()
        ve = bool(self.campo_vision[self.tripulante[1], self.tripulante[0]])

        if capturado:
            recompensa += R_CAPTURA
        terminado = capturado or self.tick >= self.max_ticks
        info = {"tick": self.tick, "capturado": capturado,
                "distancia_real": _manhattan(self.alien, self.tripulante),
                "ve_tripulante": ve}
        return self._observacion(), recompensa, terminado, info

    def paso_extra_alien(self, accion: int) -> dict:
        """Un paso más del alienígena dentro del tick actual (persecución rápida, D19).

        Usa las mismas reglas de movimiento que step(): gira hacia donde intenta ir, no
        atraviesa paredes y revisa la captura antes y después de moverse. No avanza el
        tick, no mueve al tripulante y no usa el generador aleatorio.

        Args:
            accion: 0 arriba, 1 derecha, 2 abajo, 3 izquierda o 4 quieto.

        Returns:
            {'tick', 'capturado', 'distancia_real', 've_tripulante'}, como el info de step().

        Raises:
            ValueError: Si la acción está fuera de 0 a 4.

        Example:
            >>> env = EstacionEnv()
            >>> _ = env.reset(42)
            >>> env.alien
            (1, 2)
            >>> env.paso_extra_alien(1)  # a la derecha hay pared: solo gira
            {'tick': 0, 'capturado': False, 'distancia_real': 11, 've_tripulante': False}
            >>> env.alien, env.direccion_alien
            ((1, 2), (1, 0))
        """
        if not 0 <= accion < N_ACCIONES:
            raise ValueError(f"Acción fuera de rango: {accion}")
        # Si ya lo alcanzó, no hace falta moverse: la captura queda como está.
        if not self._captura() and accion < 4:
            self.direccion_alien = DIRS[accion]
            self.alien = self._mover(self.alien, accion)
            self.campo_vision = self._calcular_vision()
        return {"tick": self.tick, "capturado": self._captura(),
                "distancia_real": _manhattan(self.alien, self.tripulante),
                "ve_tripulante": bool(self.campo_vision[self.tripulante[1], self.tripulante[0]])}

    # ------------------------------------------------------------- internos
    def _calcular_vision(self) -> np.ndarray:
        """Campo de visión del alienígena con el alcance de este entorno."""
        return campo_de_vision(self.mapa, self.alien, self.direccion_alien, self.alcance_vision)

    def _mover(self, pos: tuple[int, int], accion: int) -> tuple[int, int]:
        """Aplica una acción de movimiento; si choca, se queda en el sitio."""
        dx, dy = DIRS[accion]
        nueva = (pos[0] + dx, pos[1] + dy)
        return nueva if self.mapa.es_transitable(*nueva) else pos

    def _paso_tripulante(self) -> tuple[int, int]:
        """Bot provisional: se aleja del alienígena si está cerca; si no, camina al azar."""
        # Quedarse quieto es una opción válida; así nunca se queda sin movimientos.
        opciones = self.mapa.vecinos(*self.tripulante) + [self.tripulante]
        opciones = [c for c in opciones if c != self.alien]
        # 6 casillas es el radio en el que el bot "nota" al alienígena y huye.
        if _manhattan(self.tripulante, self.alien) <= 6:
            mejor = max(_manhattan(c, self.alien) for c in opciones)
            opciones = [c for c in opciones if _manhattan(c, self.alien) == mejor]
        return opciones[self.rng.integers(len(opciones))]

    def _paso_manual(self, accion: int) -> tuple[int, int]:
        """Movimiento manual del tripulante: avanza si la casilla es transitable y no es la
        del alienígena; si no, se queda. No usa el generador aleatorio."""
        if accion == 4:
            return self.tripulante
        nueva = self._mover(self.tripulante, accion)
        return self.tripulante if nueva == self.alien else nueva

    def _captura(self) -> bool:
        """True si el alienígena está en la misma casilla o en una contigua."""
        return _manhattan(self.alien, self.tripulante) <= 1

    def _observacion(self) -> np.ndarray:
        """Tensor (4, alto, ancho): paredes, creencia, alien, pista.
        Se conserva del diseño inicial con creencia uniforme y pista vacía; el agente no
        lo usa (D8)."""
        obs = np.zeros((4, self.mapa.alto, self.mapa.ancho), dtype=np.float32)
        obs[0] = self.mapa.paredes
        # 0.5 distingue los casilleros de las paredes sin abrir una capa adicional.
        obs[0][self.mapa.casilleros] = 0.5
        libres = ~self.mapa.paredes & ~self.mapa.casilleros
        obs[1][libres] = 1.0 / libres.sum()
        obs[2][self.alien[1], self.alien[0]] = 1.0
        return obs


def _manhattan(a: tuple[int, int], b: tuple[int, int]) -> int:
    """Distancia Manhattan entre dos casillas (x, y), en casillas."""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])
