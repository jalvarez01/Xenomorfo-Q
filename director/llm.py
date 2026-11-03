"""Configuración del modelo de lenguaje y creación del cliente compatible con OpenAI.

La directora usa un LLM servido por NVIDIA (o cualquier backend compatible con la API de
OpenAI). Este módulo lee la configuración desde variables de entorno, opcionalmente desde
un archivo .env local, y crea el cliente. La clave nunca se guarda en el repositorio.

Variables de entorno:
    NVIDIA_API_KEY: clave de la API. Obligatoria solo para crear el cliente real.
    XQ_MODELO: nombre del modelo. Por defecto "meta/llama-3.3-70b-instruct".
    XQ_URL_BASE: URL base del backend. Por defecto "https://integrate.api.nvidia.com/v1".
    XQ_TEMPERATURA: temperatura de muestreo. Por defecto 0.

Contenido principal:
    ConfigLLM: modelo, URL base y temperatura.
    cargar_config: arma un ConfigLLM a partir del entorno.
    crear_cliente: crea un openai.OpenAI con la clave del entorno.
    ClaveFaltanteError: error cuando falta NVIDIA_API_KEY.

Tareas relacionadas: T14 (configuración del LLM), T15 (ciclo del agente), T17 (pruebas).
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import openai

# Nombres de las variables de entorno que lee este módulo.
VAR_CLAVE = "NVIDIA_API_KEY"
VAR_MODELO = "XQ_MODELO"
VAR_URL_BASE = "XQ_URL_BASE"
VAR_TEMPERATURA = "XQ_TEMPERATURA"

# Modelo por defecto en el catálogo de NVIDIA; sigue bien instrucciones y llamadas a herramientas.
MODELO_POR_DEFECTO = "meta/llama-3.3-70b-instruct"
# Endpoint de NVIDIA compatible con la API de OpenAI.
URL_BASE_POR_DEFECTO = "https://integrate.api.nvidia.com/v1"
# Temperatura de muestreo (adimensional). 0 hace que los casos de prueba sean repetibles.
TEMPERATURA_POR_DEFECTO = 0.0


class ClaveFaltanteError(RuntimeError):
    """Se lanza cuando falta la variable NVIDIA_API_KEY al crear el cliente real."""


@dataclass(frozen=True)
class ConfigLLM:
    """Parámetros del modelo de lenguaje. No incluye la clave a propósito.

    La clave se lee solo al crear el cliente, así un ConfigLLM se puede imprimir o
    registrar en el notebook sin exponerla.

    Attributes:
        modelo: Nombre del modelo en el backend.
        url_base: URL base del backend compatible con OpenAI.
        temperatura: Temperatura de muestreo.

    Example:
        >>> ConfigLLM().modelo
        'meta/llama-3.3-70b-instruct'
        >>> ConfigLLM(temperatura=0.5).temperatura
        0.5
    """

    modelo: str = MODELO_POR_DEFECTO
    url_base: str = URL_BASE_POR_DEFECTO
    temperatura: float = TEMPERATURA_POR_DEFECTO


def _cargar_dotenv() -> None:
    """Carga un archivo .env local si python-dotenv está instalado.

    Las variables ya definidas en el entorno tienen prioridad (override=False), para que
    los secretos de Colab o del sistema no queden pisados por un .env viejo.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        # python-dotenv es opcional: en Colab las variables llegan por otra vía.
        return
    load_dotenv(override=False)


def cargar_config() -> ConfigLLM:
    """Lee la configuración del LLM desde el entorno (y desde .env, si existe).

    Las variables vacías se tratan como ausentes y toman el valor por defecto.

    Returns:
        Un ConfigLLM con los valores del entorno o los valores por defecto.

    Raises:
        ValueError: Si XQ_TEMPERATURA no es un número.

    Example:
        >>> config = cargar_config()
        >>> isinstance(config.temperatura, float)
        True
    """
    _cargar_dotenv()
    modelo = os.environ.get(VAR_MODELO, "").strip() or MODELO_POR_DEFECTO
    url_base = os.environ.get(VAR_URL_BASE, "").strip() or URL_BASE_POR_DEFECTO
    texto_temperatura = os.environ.get(VAR_TEMPERATURA, "").strip()
    if texto_temperatura:
        try:
            temperatura = float(texto_temperatura)
        except ValueError:
            raise ValueError(
                f"{VAR_TEMPERATURA} debe ser un número, por ejemplo 0 o 0.2; "
                f"se recibió {texto_temperatura!r}."
            ) from None
    else:
        temperatura = TEMPERATURA_POR_DEFECTO
    return ConfigLLM(modelo=modelo, url_base=url_base, temperatura=temperatura)


def crear_cliente(config: ConfigLLM | None = None) -> openai.OpenAI:
    """Crea el cliente compatible con OpenAI usando la clave de NVIDIA_API_KEY.

    Crear el cliente no hace ninguna llamada de red; la primera llamada ocurre al usar
    cliente.chat.completions.create.

    Args:
        config: Configuración a usar. Si es None, se lee con cargar_config().

    Returns:
        Un openai.OpenAI apuntando a config.url_base.

    Raises:
        ClaveFaltanteError: Si NVIDIA_API_KEY no está definida o está vacía.

    Example:
        >>> cliente = crear_cliente(cargar_config())  # doctest: +SKIP
    """
    _cargar_dotenv()
    if config is None:
        config = cargar_config()
    clave = os.environ.get(VAR_CLAVE, "").strip()
    if not clave:
        # El mensaje nunca incluye valores: solo el nombre de la variable y cómo definirla.
        raise ClaveFaltanteError(
            f"Falta la variable de entorno {VAR_CLAVE}. Defínela de una de estas formas:\n"
            f"  - Localmente: copia .env.example a .env en la raíz del repositorio y "
            f"escribe la clave después de {VAR_CLAVE}=.\n"
            f"  - En Colab: agrégala en Secretos (icono de llave) con el nombre {VAR_CLAVE} "
            f"y cárgala en os.environ antes de crear el cliente.\n"
            f"La clave nunca se sube al repositorio: .env está en .gitignore."
        )
    return openai.OpenAI(api_key=clave, base_url=config.url_base)
