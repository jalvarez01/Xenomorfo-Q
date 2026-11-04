"""Predicción de la sala hacia la que se dirige el tripulante (heurística de T12).

Base de la herramienta predecir_destino del agente. Mira los últimos ticks de la
trayectoria del tripulante y elige la sala a la que más se acercó, medido en pasos
caminando por el mapa (no en línea recta, porque las paredes obligan a rodear).

Contenido principal:
    PredictorDestino: precalcula la distancia de cada casilla a cada sala y predice el
        destino a partir de una trayectoria.
    VENTANA_TICKS: ticks que se miran hacia atrás.

Tareas relacionadas: T12 (esta heurística), T11 (la herramienta que la expone al
agente), T31 (opcional: reemplazarla por un árbol de decisión entrenado).
"""
from __future__ import annotations

from sim.mapa import SIN_SALA, Mapa

# Ticks que se miran hacia atrás. 10 ticks son 11 posiciones (la inicial más 10 pasos).
VENTANA_TICKS = 10


class PredictorDestino:
    """Predice la sala destino del tripulante con una heurística de acercamiento.

    Para cada sala, con d0 la distancia al inicio de la ventana y d1 al final (en pasos):

    - acercamiento = d0 - d1: cuántos pasos se acercó.
    - puntaje = acercamiento * (acercamiento / d0): el acercamiento ponderado por la
      fracción del camino que recorrió. Sin esa fracción, al caminar hacia el este
      siempre ganaría la sala más lejana del este, aunque el tripulante ya hubiera
      llegado a una más cercana.

    El destino es la sala de mayor puntaje entre las que se acercó. La confianza es
    acercamiento / ticks: qué tan directo caminó hacia esa sala (1.0 si cada tick lo
    acercó un paso; baja si se quedó quieto o dio vueltas).

    Args:
        mapa: Mapa con salas (n_salas > 0).
        ventana: Ticks que se miran hacia atrás.

    Raises:
        ValueError: Si el mapa no tiene salas o la ventana es menor que 1.

    Attributes:
        distancias: Una entrada por sala; cada una es un diccionario
            {casilla (x, y): pasos hasta la sala}. Se calcula una sola vez aquí.

    Example:
        >>> m = Mapa(["#######", "#..+..#", "#######"],
        ...          filas_salas=["#######", "#00+11#", "#######"],
        ...          nombres_salas=["A", "B"])
        >>> PredictorDestino(m).predecir([(1, 1), (2, 1)])
        {'sala': 'B', 'confianza': 1.0, 'acercamiento_casillas': 1, 'ticks_analizados': 1}
    """

    def __init__(self, mapa: Mapa, ventana: int = VENTANA_TICKS):
        if mapa.n_salas == 0:
            raise ValueError("El mapa no tiene salas; predecir_destino las necesita.")
        if ventana < 1:
            raise ValueError(f"La ventana debe ser de al menos 1 tick, no {ventana}.")
        self.mapa = mapa
        self.ventana = ventana
        self.distancias = []
        for sala in range(mapa.n_salas):
            self.distancias.append(_distancias_a_sala(mapa, sala))

    def distancia(self, casilla: tuple[int, int], sala: int) -> int | None:
        """Pasos caminando desde una casilla hasta la sala.

        Args:
            casilla: Posición (x, y).
            sala: Índice de la sala, de 0 a n_salas - 1.

        Returns:
            Número de pasos (0 si la casilla ya está en la sala), o None si desde esa
            casilla no se llega a la sala.
        """
        return self.distancias[sala].get(casilla)

    def predecir(self, trayectoria: list[tuple[int, int]]) -> dict:
        """Predice la sala hacia la que se dirige el tripulante.

        Solo se usan las últimas ventana + 1 posiciones. Si no se acercó a ninguna sala
        (quieto, o solo se alejó), se devuelve la última sala en la que estuvo dentro de
        la ventana con confianza 0, porque no hay señal de que vaya a otra parte.

        Args:
            trayectoria: Posiciones (x, y) del tripulante, de la más antigua a la más
                reciente, como EstacionEnv.trayectoria.

        Returns:
            Diccionario serializable a JSON con:
                sala: Nombre de la sala estimada, o None si en toda la ventana estuvo en
                    puertas.
                confianza: Entre 0 y 1, con dos decimales.
                acercamiento_casillas: Pasos que se acercó a la sala estimada.
                ticks_analizados: Ticks usados (menos que ventana si la partida es corta).

        Raises:
            ValueError: Si la trayectoria está vacía o tiene una casilla no transitable.

        Example:
            >>> m = Mapa(["#######", "#..+..#", "#######"],
            ...          filas_salas=["#######", "#00+11#", "#######"],
            ...          nombres_salas=["A", "B"])
            >>> PredictorDestino(m).predecir([(5, 1), (5, 1)])
            {'sala': 'B', 'confianza': 0.0, 'acercamiento_casillas': 0, 'ticks_analizados': 1}
        """
        if len(trayectoria) == 0:
            raise ValueError("La trayectoria está vacía: no hay posiciones del tripulante.")
        # Las últimas ventana + 1 posiciones; si la partida es más corta, todas.
        ventana = trayectoria[-(self.ventana + 1):]
        for x, y in ventana:
            if not self.mapa.es_transitable(x, y):
                raise ValueError(f"La casilla {(x, y)} de la trayectoria no es transitable.")

        inicio = ventana[0]
        fin = ventana[-1]
        ticks = len(ventana) - 1

        mejor_sala = None
        mejor_puntaje = 0.0
        mejor_acercamiento = 0
        for sala in range(self.mapa.n_salas):
            d0 = self.distancia(inicio, sala)
            d1 = self.distancia(fin, sala)
            if d0 is None or d1 is None:
                continue  # no se llega a esa sala desde aquí
            acercamiento = d0 - d1
            if acercamiento <= 0:
                continue  # no se acercó a esta sala
            # acercamiento > 0 implica d0 > 0, así que la división es segura.
            puntaje = acercamiento * acercamiento / d0
            if mejor_sala is None or puntaje > mejor_puntaje:
                es_mejor = True
            elif puntaje == mejor_puntaje:
                # Empate: gana la sala más cercana al final. Si siguen empatadas, se
                # queda la primera, la de menor índice.
                es_mejor = d1 < self.distancia(fin, mejor_sala)
            else:
                es_mejor = False
            if es_mejor:
                mejor_sala = sala
                mejor_puntaje = puntaje
                mejor_acercamiento = acercamiento

        if mejor_sala is None:
            sala = _ultima_sala(self.mapa, ventana)
            confianza = 0.0
        else:
            sala = mejor_sala
            confianza = mejor_acercamiento / ticks

        if sala == SIN_SALA:
            nombre = None
        else:
            nombre = self.mapa.nombres_salas[sala]
        return {
            "sala": nombre,
            "confianza": round(confianza, 2),
            "acercamiento_casillas": mejor_acercamiento,
            "ticks_analizados": ticks,
        }


def _distancias_a_sala(mapa: Mapa, sala: int) -> dict[tuple[int, int], int]:
    """Pasos desde cada casilla transitable hasta la casilla más cercana de la sala.

    Funciona como una ola: empieza con las casillas de la sala (0 pasos) y en cada vuelta
    avanza un paso hacia las vecinas que todavía no tienen distancia. Es una búsqueda en
    anchura (BFS); en una cuadrícula donde todos los pasos cuestan 1 da la misma
    distancia que A*.

    Returns:
        Diccionario {(x, y): pasos}. Las casillas a las que no se llega no aparecen.
    """
    distancias = {}
    for x, y in mapa.transitables:
        if mapa.sala(x, y) == sala:
            distancias[(x, y)] = 0

    frontera = list(distancias)  # casillas alcanzadas en la última vuelta
    pasos = 0
    while len(frontera) > 0:
        pasos += 1
        siguiente = []
        for x, y in frontera:
            for vecina in mapa.vecinos(x, y):
                if vecina not in distancias:
                    distancias[vecina] = pasos
                    siguiente.append(vecina)
        frontera = siguiente
    return distancias


def _ultima_sala(mapa: Mapa, ventana: list[tuple[int, int]]) -> int:
    """Última sala de la ventana, saltando puertas; SIN_SALA si solo hubo puertas."""
    for x, y in reversed(ventana):
        if mapa.sala(x, y) != SIN_SALA:
            return mapa.sala(x, y)
    return SIN_SALA
