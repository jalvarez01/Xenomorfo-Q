"""Alienígena por reglas que reacciona a las pistas de la directora (T18, T19).

En cada tick decide su acción con un árbol simple, en este orden:

1. Si ve al tripulante, lo persigue por el camino más corto (A*).
2. Si lo perdió de vista, va a la última casilla donde lo vio. Si llega y no lo ve,
   deja de buscarlo ahí.
3. Si tiene una pista vigente, va al centro de esa sala. Al llegar, la pista se cumple.
4. Si no, patrulla: recorre los centros de las salas, siempre hacia el más cercano que
   no haya visitado en la vuelta actual.

Opcional (D19, niveles del panel): con paso_extra_cada=N, cada N ticks en los que está
persiguiendo da un paso más (accion_extra, que Avance aplica con env.paso_extra_alien).
Por defecto no hay paso extra y el comportamiento es el de siempre.

El alienígena no hace trampa: solo usa la posición del tripulante cuando lo está viendo
(env.campo_vision). Quien conoce la posición real es la directora, que puede ayudarlo
con una pista: una sala, nunca una casilla (D2 adaptada en D8). Hay 3 pistas por partida.

Se usa como política de Avance (sim/avance.py): Avance(env, AlienReglas(env)).

Contenido principal:
    AlienReglas: el alienígena; decide la acción de cada tick y recibe las pistas.
    centro_de_sala: casilla transitable más cercana al centro de una sala.
    PISTAS_POR_PARTIDA, PERSIGUE, PISTA, PATRULLA: presupuesto y estados.

Tareas relacionadas: T18 (reglas), T19 (pistas con presupuesto), T10 (evento de llegada
a la sala de la pista en Avance), T11 (herramienta dar_pista).
"""
from __future__ import annotations

from sim.env import EstacionEnv
from sim.mapa import DIRS, SIN_SALA, Mapa
from sim.rutas import ruta

# Pistas que la directora puede dar en una partida (pestaña 'Contratos').
PISTAS_POR_PARTIDA = 3
# La acción 4 (revisar casillero) no mueve al alienígena: se usa para quedarse quieto.
QUIETO = 4
# Estados del árbol, para que el agente y las pruebas sepan qué está haciendo.
PERSIGUE = "persigue"
PISTA = "va a la pista"
PATRULLA = "patrulla"


class AlienReglas:
    """Alienígena controlado por reglas, con presupuesto de pistas.

    Se crea uno por partida, después de env.reset(), porque recuerda dónde vio al
    tripulante, la pista vigente y las salas que ya patrulló.

    Args:
        env: Entorno ya iniciado con reset(). El mapa debe tener salas.
        paso_extra_cada: Si es un entero N >= 1, en los ticks múltiplos de N en los que
            persigue da un paso extra (accion_extra). None, el valor por defecto, no da
            pasos extra.

    Raises:
        ValueError: Si el mapa no tiene salas o paso_extra_cada no es None ni >= 1.

    Attributes:
        env: Entorno de la partida.
        estado: PERSIGUE, PISTA o PATRULLA, según la última decisión.
        pistas_restantes: Pistas que quedan en la partida.
        pista: Índice de la sala de la pista vigente, o None.
        ultima_vista: Última casilla donde vio al tripulante, o None si ya la revisó.
        centros: Centro de cada sala, en orden de índice.
        paso_extra_cada: Cada cuántos ticks da un paso extra al perseguir, o None.

    Example:
        >>> from sim.avance import Avance
        >>> env = EstacionEnv()
        >>> _ = env.reset(42)
        >>> alien = AlienReglas(env)
        >>> alien.dar_pista("Bodega")
        {'sala': 'Bodega', 'pistas_restantes': 2}
        >>> r = Avance(env, alien).avanzar(20)
        >>> alien.estado
        'persigue'
    """

    def __init__(self, env: EstacionEnv, paso_extra_cada: int | None = None):
        if env.mapa.n_salas == 0:
            raise ValueError("El mapa no tiene salas; el alienígena por reglas las necesita.")
        if paso_extra_cada is not None and (not isinstance(paso_extra_cada, int)
                                            or isinstance(paso_extra_cada, bool)
                                            or paso_extra_cada < 1):
            raise ValueError(f"paso_extra_cada debe ser None o un entero >= 1; "
                             f"se recibió {paso_extra_cada!r}.")
        self.env = env
        self.paso_extra_cada = paso_extra_cada
        self.estado = PATRULLA
        self.pistas_restantes = PISTAS_POR_PARTIDA
        self.pista: int | None = None
        self.ultima_vista: tuple[int, int] | None = None
        self.centros = []
        for sala in range(env.mapa.n_salas):
            self.centros.append(centro_de_sala(env.mapa, sala))
        # Patrulla: empieza por el centro de su propia sala (la 0 si arranca en una puerta).
        sala_inicial = env.mapa.sala(env.alien[0], env.alien[1])
        if sala_inicial == SIN_SALA:
            sala_inicial = 0
        self._objetivo = sala_inicial
        self._visitadas: set[int] = set()
        self._eventos: list[str] = []

    @property
    def pista_activa(self) -> str | None:
        """Nombre de la sala de la pista vigente, o None si no hay pista."""
        if self.pista is None:
            return None
        return self.env.mapa.nombres_salas[self.pista]

    def __call__(self, env: EstacionEnv) -> int:
        """Permite usar el alienígena como política de Avance: decide la acción del tick.

        Args:
            env: El entorno de la partida (el mismo que se pasó al crearlo).

        Returns:
            Acción de 0 a 4.
        """
        return self.decidir()

    def decidir(self) -> int:
        """Elige la acción de este tick con el árbol de reglas.

        Returns:
            Acción de 0 a 4 (0 arriba, 1 derecha, 2 abajo, 3 izquierda, 4 quieto).
        """
        alien = self.env.alien
        tripulante = self.env.tripulante

        # 1. Lo ve: lo persigue y recuerda dónde está.
        if self.env.campo_vision[tripulante[1], tripulante[0]]:
            self.estado = PERSIGUE
            self.ultima_vista = tripulante
            return self._paso_hacia(tripulante)

        # 2. Lo perdió de vista: va a la última casilla donde lo vio.
        if self.ultima_vista is not None:
            if alien == self.ultima_vista:
                self.ultima_vista = None  # llegó y no está: deja de buscarlo ahí
            else:
                self.estado = PERSIGUE
                return self._paso_hacia(self.ultima_vista)

        # 3. Pista vigente: va al centro de esa sala.
        if self.pista is not None:
            centro = self.centros[self.pista]
            if alien == centro:
                self._cumplir_pista()
            else:
                self.estado = PISTA
                accion, siguiente = self._paso_y_casilla(centro)
                if siguiente == centro:
                    self._cumplir_pista()  # llega en este tick
                return accion

        # 4. Patrulla.
        self.estado = PATRULLA
        if alien == self.centros[self._objetivo]:
            self._visitadas.add(self._objetivo)
            self._objetivo = self._siguiente_patrulla()
        return self._paso_hacia(self.centros[self._objetivo])

    def accion_extra(self) -> int | None:
        """Acción del paso extra de este tick, o None si no le toca (D19).

        Le toca solo si paso_extra_cada está definido, el tick es múltiplo de él y en
        este tick decidió perseguir. El destino es el mismo de la rama de persecución:
        el tripulante si lo ve ahora, o la última casilla donde lo vio. Avance lo llama
        después de env.step() y aplica la acción con env.paso_extra_alien(), que usa las
        mismas reglas de movimiento y de captura. No usa el generador aleatorio.

        Returns:
            Acción de 0 a 3, o None si no hay paso extra.

        Example:
            >>> env = EstacionEnv()
            >>> _ = env.reset(42)
            >>> AlienReglas(env).accion_extra() is None
            True
        """
        if (self.paso_extra_cada is None or self.estado != PERSIGUE
                or self.env.tick == 0 or self.env.tick % self.paso_extra_cada):
            return None
        tripulante = self.env.tripulante
        if self.env.campo_vision[tripulante[1], tripulante[0]]:
            self.ultima_vista = tripulante
            destino = tripulante
        elif self.ultima_vista is not None and self.env.alien != self.ultima_vista:
            destino = self.ultima_vista
        else:
            return None
        accion, _ = self._paso_y_casilla(destino)
        return None if accion == QUIETO else accion

    def dar_pista(self, sala: str, contar: bool = True) -> dict:
        """Recibe una pista de la directora: la sala donde buscar al tripulante (T19).

        La pista no mueve al alienígena: queda vigente y la sigue en los próximos ticks,
        salvo que vea al tripulante, que tiene prioridad. Una pista nueva reemplaza a la
        anterior.

        Args:
            sala: Nombre de la sala, sin importar mayúsculas ni espacios al inicio o final.
            contar: True (por defecto) gasta una de las pistas de la directora. False no
                la gasta ni la exige: lo usa la pista automática del panel (D19), que
                lleva su propio presupuesto.

        Returns:
            Diccionario serializable a JSON con:
                sala: Nombre de la sala, como está en el mapa.
                pistas_restantes: Pistas que quedan en la partida.

        Raises:
            ValueError: Si no quedan pistas (solo con contar=True) o la sala no existe
                (el mensaje lista las salas válidas). En ninguno de los dos casos se gasta
                una pista.
        """
        if not contar:
            self.pista = self._indice_sala(sala)
            return {"sala": self.env.mapa.nombres_salas[self.pista],
                    "pistas_restantes": self.pistas_restantes}
        if self.pistas_restantes == 0:
            raise ValueError(
                f"No quedan pistas: ya se usaron las {PISTAS_POR_PARTIDA} de la partida.")
        indice = self._indice_sala(sala)
        self.pista = indice
        self.pistas_restantes -= 1
        return {"sala": self.env.mapa.nombres_salas[indice],
                "pistas_restantes": self.pistas_restantes}

    def tomar_eventos(self) -> list[str]:
        """Devuelve los eventos del alienígena desde la última llamada y los borra.

        Avance los llama en cada tick para agregarlos a su registro, por ejemplo
        "el alienígena llegó a Bodega, la sala de la pista".

        Returns:
            Lista de eventos en texto, sin el prefijo del tick.
        """
        eventos = self._eventos
        self._eventos = []
        return eventos

    # ------------------------------------------------------------- internos
    def _paso_hacia(self, destino: tuple[int, int]) -> int:
        """Acción del primer paso del camino más corto hacia destino."""
        accion, _ = self._paso_y_casilla(destino)
        return accion

    def _paso_y_casilla(self, destino: tuple[int, int]) -> tuple[int, tuple[int, int]]:
        """Acción del primer paso hacia destino y la casilla a la que llega.

        Si ya está en destino o no hay camino, se queda quieto.
        """
        alien = self.env.alien
        camino = ruta(self.env.mapa, alien, destino)
        if camino is None or len(camino) < 2:
            return QUIETO, alien
        siguiente = camino[1]
        paso = (siguiente[0] - alien[0], siguiente[1] - alien[1])
        # DIRS está en el mismo orden que las acciones 0 a 3.
        return DIRS.index(paso), siguiente

    def _cumplir_pista(self) -> None:
        """Marca la pista como cumplida y deja el evento para Avance."""
        nombre = self.env.mapa.nombres_salas[self.pista]
        self._eventos.append(f"el alienígena llegó a {nombre}, la sala de la pista")
        # La patrulla sigue desde la sala de la pista, como si la hubiera visitado.
        self._visitadas.add(self.pista)
        self._objetivo = self.pista
        self.pista = None

    def _siguiente_patrulla(self) -> int:
        """Sala sin visitar en esta vuelta cuyo centro está más cerca; si ya visitó todas,
        empieza otra vuelta. En un empate gana la de menor índice."""
        if len(self._visitadas) == len(self.centros):
            self._visitadas = {self._objetivo}
        mejor = None
        mejor_pasos = None
        for sala in range(len(self.centros)):
            if sala in self._visitadas:
                continue
            camino = ruta(self.env.mapa, self.env.alien, self.centros[sala])
            if camino is None:
                continue  # sala inalcanzable desde aquí
            pasos = len(camino) - 1
            if mejor is None or pasos < mejor_pasos:
                mejor = sala
                mejor_pasos = pasos
        if mejor is None:
            return self._objetivo  # no hay otra sala alcanzable: se queda en la suya
        return mejor

    def _indice_sala(self, sala: str) -> int:
        """Índice de la sala por su nombre, sin importar mayúsculas ni espacios.

        Raises:
            ValueError: Si no hay ninguna sala con ese nombre.
        """
        buscado = str(sala).strip().casefold()
        nombres = self.env.mapa.nombres_salas
        for indice in range(len(nombres)):
            if nombres[indice].casefold() == buscado:
                return indice
        raise ValueError(f"La sala '{sala}' no existe. Salas válidas: {', '.join(nombres)}.")


def centro_de_sala(mapa: Mapa, sala: int) -> tuple[int, int]:
    """Casilla transitable de la sala más cercana a su centro geométrico.

    El centro geométrico es el promedio de las casillas transitables de la sala. Si hay
    empate, gana la primera en orden de fila y columna.

    Args:
        mapa: Mapa con salas.
        sala: Índice de la sala.

    Returns:
        Casilla (x, y) transitable de la sala.

    Example:
        >>> m = Mapa(["#######", "#..+..#", "#######"],
        ...          filas_salas=["#######", "#00+11#", "#######"], nombres_salas=["A", "B"])
        >>> centro_de_sala(m, 0), centro_de_sala(m, 1)
        ((1, 1), (4, 1))
    """
    casillas = []
    for x, y in mapa.transitables:
        if mapa.sala(x, y) == sala:
            casillas.append((x, y))
    cx = sum(x for x, _ in casillas) / len(casillas)
    cy = sum(y for _, y in casillas) / len(casillas)
    mejor = casillas[0]
    mejor_distancia = (mejor[0] - cx) ** 2 + (mejor[1] - cy) ** 2
    for x, y in casillas:
        distancia = (x - cx) ** 2 + (y - cy) ** 2
        if distancia < mejor_distancia:
            mejor = (x, y)
            mejor_distancia = distancia
    return mejor
