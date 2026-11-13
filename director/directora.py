"""La directora: une la partida, las herramientas, los esquemas, el prompt y el modelo (T11).

Es el punto de entrada para preguntarle al agente. Cada pregunta es independiente (no se
guarda historial de conversación con el modelo), pero la partida sí persiste entre
preguntas: si una pregunta da una pista o avanza la simulación, la siguiente ve ese
estado.

El cliente del modelo se crea solo cuando se hace la primera pregunta, así importar el
módulo, crear la directora o correr las pruebas no necesita la clave.

Contenido principal:
    Directora: preguntar(pregunta) -> ResultadoAgente y reiniciar(semilla).

Tareas relacionadas: T11 (herramientas y directora), T13 (esquemas), T14 (cliente del
LLM), T15 (ciclo del agente), T16 (prompt de sistema).
"""
from __future__ import annotations

from typing import Any

from director.agente import LIMITE_POR_DEFECTO, ResultadoAgente, ejecutar_agente
from director.esquemas import construir_esquemas, validar_correspondencia
from director.herramientas import crear_herramientas
from director.llm import ConfigLLM, cargar_config, crear_cliente
from director.partida import MAX_TICKS_POR_DEFECTO, SEMILLA_POR_DEFECTO, Partida
from director.prompt import construir_prompt_sistema


class Directora:
    """Agente directora sobre una partida de la estación.

    Args:
        semilla: Semilla de la partida.
        cliente: Objeto con chat.completions.create(**kwargs). None crea el cliente real
            de NVIDIA NIM en la primera pregunta.
        config: Configuración del modelo. None la lee del entorno con cargar_config().
        limite: Máximo de herramientas ejecutadas por pregunta.
        max_ticks: Ticks máximos de la partida.

    Raises:
        ValueError: Si las herramientas no coinciden con sus esquemas.

    Attributes:
        partida: Partida actual; su estado persiste entre preguntas.
        herramientas: Diccionario nombre -> función ligado a la partida.
        esquemas: Esquemas de las herramientas para el modelo.
        prompt: Prompt de sistema.
        config: Modelo, URL base y temperatura.
        limite: Máximo de herramientas por pregunta.

    Example:
        >>> d = Directora(semilla=42, config=ConfigLLM())
        >>> d.herramientas["estado_partida"]()["tripulante"]["sala"]
        'Bodega'
        >>> resultado = d.preguntar("¿En qué sala está el tripulante?")  # doctest: +SKIP
    """

    def __init__(self, semilla: int = SEMILLA_POR_DEFECTO, cliente: Any = None,
                 config: ConfigLLM | None = None, limite: int = LIMITE_POR_DEFECTO,
                 max_ticks: int = MAX_TICKS_POR_DEFECTO):
        self.limite = limite
        self.max_ticks = max_ticks
        self.config = config if config is not None else cargar_config()
        self._cliente = cliente
        self.reiniciar(semilla)

    def preguntar(self, pregunta: str) -> ResultadoAgente:
        """Responde una pregunta en español usando las herramientas sobre la partida.

        Args:
            pregunta: Pregunta del usuario.

        Returns:
            ResultadoAgente con la respuesta, el registro de llamadas y si se alcanzó el
            límite.

        Raises:
            ClaveFaltanteError: Si no se pasó cliente y falta la clave del proveedor.
        """
        if self._cliente is None:
            self._cliente = crear_cliente(self.config)
        return ejecutar_agente(pregunta, self.herramientas, self.esquemas, self._cliente,
                               self.config.modelo, self.prompt, limite=self.limite,
                               temperatura=self.config.temperatura)

    def reiniciar(self, semilla: int | None = None) -> None:
        """Empieza una partida nueva y vuelve a ligar las herramientas a ella.

        Args:
            semilla: Semilla de la nueva partida. None repite la semilla actual.

        Raises:
            ValueError: Si las herramientas no coinciden con sus esquemas.
        """
        if semilla is None:
            semilla = self.partida.semilla
        self.partida = Partida(semilla=semilla, max_ticks=self.max_ticks)
        self.herramientas = crear_herramientas(self.partida)
        nombres = self.partida.env.mapa.nombres_salas
        self.esquemas = construir_esquemas(nombres)
        # Si una función y su esquema no coinciden, el modelo pediría argumentos que la
        # función rechaza: mejor fallar al crear la directora que a mitad de una pregunta.
        problemas = validar_correspondencia(self.esquemas, self.herramientas)
        if problemas:
            raise ValueError("Las herramientas no coinciden con sus esquemas: "
                             + " ".join(problemas))
        self.prompt = construir_prompt_sistema(nombres, self.limite)
