"""Configuración del modelo de lenguaje y creación del cliente compatible con OpenAI.

La directora usa un LLM de un proveedor con API compatible con OpenAI: OpenAI (por
defecto) o NVIDIA NIM (alternativa gratuita). Este módulo lee la configuración desde
variables de entorno, opcionalmente desde un archivo .env local, y crea el cliente. La
clave nunca se guarda en el repositorio ni se imprime. Decisión D15 en
docs/decisiones.md.

Variables de entorno:
    XQ_PROVEEDOR: "openai" (por defecto) o "nvidia".
    OPENAI_API_KEY: clave de OpenAI. Obligatoria solo para crear el cliente real con
        el proveedor "openai".
    NVIDIA_API_KEY: clave de NVIDIA NIM. Obligatoria solo con el proveedor "nvidia".
    XQ_MODELO: nombre del modelo. Por defecto, el del proveedor (PROVEEDORES).
    XQ_URL_BASE: URL base del backend. Por defecto, la del proveedor.
    XQ_TEMPERATURA: temperatura de muestreo. Por defecto 0.

Contenido principal:
    Proveedor, PROVEEDORES: datos de cada proveedor (variable de la clave, URL y modelo).
    ConfigLLM: proveedor, modelo, URL base y temperatura.
    cargar_config: arma un ConfigLLM a partir del entorno.
    crear_cliente: crea un openai.OpenAI con la clave del proveedor elegido.
    ClaveFaltanteError: error cuando falta la clave del proveedor.

Tareas relacionadas: T14 (configuración del LLM), T15 (ciclo del agente), T17 (pruebas).
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import openai

# Nombres de las variables de entorno que lee este módulo.
VAR_PROVEEDOR = "XQ_PROVEEDOR"
VAR_CLAVE_OPENAI = "OPENAI_API_KEY"
VAR_CLAVE_NVIDIA = "NVIDIA_API_KEY"
VAR_MODELO = "XQ_MODELO"
VAR_URL_BASE = "XQ_URL_BASE"
VAR_TEMPERATURA = "XQ_TEMPERATURA"
# Variables con claves: las pruebas las limpian todas para no depender del equipo.
VARIABLES_CLAVE = (VAR_CLAVE_OPENAI, VAR_CLAVE_NVIDIA)
# Temperatura de muestreo (adimensional). 0 hace que los casos de prueba sean repetibles.
TEMPERATURA_POR_DEFECTO = 0.0


@dataclass(frozen=True)
class Proveedor:
    """Datos fijos de un proveedor de modelos.

    Attributes:
        var_clave: Variable de entorno con la clave.
        url_base: URL base de la API; None usa la de la biblioteca openai.
        modelo: Modelo por defecto.
    """

    var_clave: str
    url_base: str | None
    modelo: str


PROVEEDORES = {
    # Proveedor principal (D15): gpt-5.4-nano fue el más barato que pasó las pruebas de
    # herramientas, de llamada de cierre y del caso C1, con menos de 4 s por pregunta.
    "openai": Proveedor(VAR_CLAVE_OPENAI, None, "gpt-5.4-nano"),
    # Alternativa gratuita (D15): meta/llama-3.3-70b-instruct llegó al fin de su vida el
    # 2026-08-26; openai/gpt-oss-20b fue el único candidato que pasó las pruebas, pero
    # tardó unos 4 minutos por pregunta. Se puede cambiar con XQ_MODELO.
    "nvidia": Proveedor(VAR_CLAVE_NVIDIA, "https://integrate.api.nvidia.com/v1",
                        "openai/gpt-oss-20b"),
}
# Proveedor que se usa si XQ_PROVEEDOR no está definido.
PROVEEDOR_POR_DEFECTO = "openai"
# Variable de la clave del proveedor por defecto. Se conserva por compatibilidad.
VAR_CLAVE = PROVEEDORES[PROVEEDOR_POR_DEFECTO].var_clave


class ClaveFaltanteError(RuntimeError):
    """Se lanza cuando falta la clave del proveedor elegido al crear el cliente real."""


@dataclass(frozen=True)
class ConfigLLM:
    """Parámetros del modelo de lenguaje. No incluye la clave a propósito.

    La clave se lee solo al crear el cliente, así un ConfigLLM se puede imprimir o
    registrar en el notebook sin exponerla. Un modelo vacío o una URL base vacía toman
    el valor por defecto del proveedor.

    Attributes:
        modelo: Nombre del modelo en el backend.
        url_base: URL base del backend compatible con OpenAI; None usa la de OpenAI.
        temperatura: Temperatura de muestreo.
        proveedor: "openai" o "nvidia".

    Raises:
        ValueError: Si el proveedor no es uno de PROVEEDORES.

    Example:
        >>> ConfigLLM().modelo, ConfigLLM().url_base
        ('gpt-5.4-nano', None)
        >>> ConfigLLM(proveedor="nvidia").url_base
        'https://integrate.api.nvidia.com/v1'
        >>> ConfigLLM(temperatura=0.5).temperatura
        0.5
    """

    modelo: str = ""
    url_base: str | None = ""
    temperatura: float = TEMPERATURA_POR_DEFECTO
    proveedor: str = PROVEEDOR_POR_DEFECTO

    def __post_init__(self) -> None:
        if self.proveedor not in PROVEEDORES:
            raise ValueError(f"Proveedor desconocido: {self.proveedor!r}. Usa uno de: "
                             f"{', '.join(PROVEEDORES)}.")
        datos = PROVEEDORES[self.proveedor]
        # La clase es inmutable: los valores por defecto se fijan con object.__setattr__.
        if not self.modelo:
            object.__setattr__(self, "modelo", datos.modelo)
        if self.url_base == "":
            object.__setattr__(self, "url_base", datos.url_base)


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

    Las variables vacías se tratan como ausentes y toman el valor por defecto del
    proveedor.

    Returns:
        Un ConfigLLM con los valores del entorno o los valores por defecto.

    Raises:
        ValueError: Si XQ_TEMPERATURA no es un número o XQ_PROVEEDOR no es válido.

    Example:
        >>> config = cargar_config()
        >>> isinstance(config.temperatura, float)
        True
    """
    _cargar_dotenv()
    proveedor = os.environ.get(VAR_PROVEEDOR, "").strip().lower() or PROVEEDOR_POR_DEFECTO
    if proveedor not in PROVEEDORES:
        raise ValueError(f"{VAR_PROVEEDOR} debe ser uno de: {', '.join(PROVEEDORES)}; "
                         f"se recibió {proveedor!r}.")
    modelo = os.environ.get(VAR_MODELO, "").strip()
    url_base = os.environ.get(VAR_URL_BASE, "").strip()
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
    return ConfigLLM(modelo=modelo, url_base=url_base, temperatura=temperatura,
                     proveedor=proveedor)


def crear_cliente(config: ConfigLLM | None = None) -> openai.OpenAI:
    """Crea el cliente compatible con OpenAI con la clave del proveedor elegido.

    Crear el cliente no hace ninguna llamada de red; la primera llamada ocurre al usar
    cliente.chat.completions.create.

    Args:
        config: Configuración a usar. Si es None, se lee con cargar_config().

    Returns:
        Un openai.OpenAI apuntando a config.url_base (o a OpenAI si es None).

    Raises:
        ClaveFaltanteError: Si la variable de la clave del proveedor no está definida o
            está vacía.

    Example:
        >>> cliente = crear_cliente(cargar_config())  # doctest: +SKIP
    """
    _cargar_dotenv()
    if config is None:
        config = cargar_config()
    var_clave = PROVEEDORES[config.proveedor].var_clave
    clave = os.environ.get(var_clave, "").strip()
    if not clave:
        # El mensaje nunca incluye valores: solo el nombre de la variable y cómo definirla.
        otros = ", ".join(p for p in PROVEEDORES if p != config.proveedor)
        raise ClaveFaltanteError(
            f"Falta la variable de entorno {var_clave} (proveedor {config.proveedor}). "
            f"Defínela de una de estas formas:\n"
            f"  - Localmente: copia .env.example a .env en la raíz del repositorio y "
            f"escribe la clave después de {var_clave}=.\n"
            f"  - En Colab: agrégala en Secretos (icono de llave) con el nombre {var_clave} "
            f"y cárgala en os.environ antes de crear el cliente.\n"
            f"Para usar otro proveedor ({otros}), cambia {VAR_PROVEEDOR} en .env.\n"
            f"La clave nunca se sube al repositorio: .env está en .gitignore."
        )
    return openai.OpenAI(api_key=clave, base_url=config.url_base)
