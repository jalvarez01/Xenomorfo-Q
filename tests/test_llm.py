"""Pruebas de la configuración del LLM, sin llamadas de red ni claves reales.

Cada prueba desactiva la carga de .env para que un archivo real del equipo no cambie el
resultado, y limpia las variables con monkeypatch.

Tareas relacionadas: T17 (pruebas sin API), T14 (configuración del LLM), D15 (proveedor
configurable).
"""
from __future__ import annotations

import pytest

from director import llm

VARIABLES = (llm.VAR_PROVEEDOR, *llm.VARIABLES_CLAVE, llm.VAR_MODELO, llm.VAR_URL_BASE,
             llm.VAR_TEMPERATURA)


@pytest.fixture(autouse=True)
def entorno_limpio(monkeypatch):
    """Aísla cada prueba del entorno y de cualquier .env local."""
    monkeypatch.setattr(llm, "_cargar_dotenv", lambda: None)
    for nombre in VARIABLES:
        monkeypatch.delenv(nombre, raising=False)


def test_valores_por_defecto():
    """Sin variables, el proveedor es OpenAI con su modelo por defecto y temperatura 0."""
    config = llm.cargar_config()
    assert config == llm.ConfigLLM()
    assert config.proveedor == "openai"
    assert config.modelo == llm.PROVEEDORES["openai"].modelo == "gpt-5.4-nano"
    assert config.url_base is None
    assert config.temperatura == 0.0
    assert llm.VAR_CLAVE == "OPENAI_API_KEY"


def test_proveedor_nvidia(monkeypatch):
    """Con XQ_PROVEEDOR=nvidia se usan la URL y el modelo de NVIDIA NIM."""
    monkeypatch.setenv(llm.VAR_PROVEEDOR, " NVIDIA ")
    config = llm.cargar_config()
    assert config.proveedor == "nvidia"
    assert config.url_base == "https://integrate.api.nvidia.com/v1"
    assert config.modelo == llm.PROVEEDORES["nvidia"].modelo


def test_proveedor_desconocido(monkeypatch):
    """Un proveedor que no existe lanza ValueError con los válidos."""
    monkeypatch.setenv(llm.VAR_PROVEEDOR, "otro")
    with pytest.raises(ValueError, match="openai, nvidia"):
        llm.cargar_config()
    with pytest.raises(ValueError, match="Proveedor desconocido"):
        llm.ConfigLLM(proveedor="otro")


def test_variables_cambian_la_configuracion(monkeypatch):
    """XQ_MODELO, XQ_URL_BASE y XQ_TEMPERATURA se reflejan en ConfigLLM."""
    monkeypatch.setenv(llm.VAR_MODELO, "otro/modelo")
    monkeypatch.setenv(llm.VAR_URL_BASE, "http://localhost:8000/v1")
    monkeypatch.setenv(llm.VAR_TEMPERATURA, "0.7")
    config = llm.cargar_config()
    assert config.modelo == "otro/modelo"
    assert config.url_base == "http://localhost:8000/v1"
    assert config.temperatura == 0.7


def test_variables_vacias_toman_los_valores_del_proveedor(monkeypatch):
    """XQ_MODELO y XQ_URL_BASE vacíos toman los valores por defecto del proveedor."""
    monkeypatch.setenv(llm.VAR_MODELO, "")
    monkeypatch.setenv(llm.VAR_URL_BASE, "  ")
    config = llm.cargar_config()
    assert (config.modelo, config.url_base) == ("gpt-5.4-nano", None)


def test_temperatura_invalida(monkeypatch):
    """Una temperatura que no es número lanza ValueError con el nombre de la variable."""
    monkeypatch.setenv(llm.VAR_TEMPERATURA, "tibia")
    with pytest.raises(ValueError, match=llm.VAR_TEMPERATURA):
        llm.cargar_config()


@pytest.mark.parametrize("proveedor, variable", [("openai", "OPENAI_API_KEY"),
                                                 ("nvidia", "NVIDIA_API_KEY")])
def test_sin_clave_nombra_la_variable_del_proveedor(proveedor, variable):
    """Sin la clave del proveedor, el error nombra su variable, .env.example y Colab."""
    with pytest.raises(llm.ClaveFaltanteError) as info:
        llm.crear_cliente(llm.ConfigLLM(proveedor=proveedor))
    mensaje = str(info.value)
    assert variable in mensaje and f"proveedor {proveedor}" in mensaje
    assert ".env.example" in mensaje and "Colab" in mensaje and "XQ_PROVEEDOR" in mensaje


def test_la_clave_de_otro_proveedor_no_sirve(monkeypatch):
    """Con OpenAI elegido, tener solo NVIDIA_API_KEY no basta."""
    monkeypatch.setenv(llm.VAR_CLAVE_NVIDIA, "clave-ficticia-de-prueba")
    with pytest.raises(llm.ClaveFaltanteError, match="OPENAI_API_KEY"):
        llm.crear_cliente(llm.ConfigLLM(proveedor="openai"))


def test_clave_vacia_cuenta_como_faltante(monkeypatch):
    """Una clave vacía o con espacios se trata como ausente."""
    monkeypatch.setenv(llm.VAR_CLAVE, "   ")
    with pytest.raises(llm.ClaveFaltanteError):
        llm.crear_cliente()


def test_el_mensaje_nunca_incluye_la_clave(monkeypatch):
    """Si falta la clave de un proveedor, el mensaje no muestra la de otro."""
    monkeypatch.setenv(llm.VAR_CLAVE_OPENAI, "clave-ficticia-que-no-debe-salir")
    with pytest.raises(llm.ClaveFaltanteError) as info:
        llm.crear_cliente(llm.ConfigLLM(proveedor="nvidia"))
    assert "clave-ficticia-que-no-debe-salir" not in str(info.value)


def test_crear_cliente_usa_la_url_base(monkeypatch):
    """Con clave, el cliente apunta a la URL base configurada (sin llamadas de red)."""
    monkeypatch.setenv(llm.VAR_CLAVE, "clave-ficticia-de-prueba")
    cliente = llm.crear_cliente(llm.ConfigLLM(url_base="http://localhost:9/v1"))
    assert str(cliente.base_url).rstrip("/") == "http://localhost:9/v1"


def test_crear_cliente_nvidia(monkeypatch):
    """Con el proveedor nvidia y su clave, el cliente apunta a NVIDIA NIM."""
    monkeypatch.setenv(llm.VAR_CLAVE_NVIDIA, "clave-ficticia-de-prueba")
    cliente = llm.crear_cliente(llm.ConfigLLM(proveedor="nvidia"))
    assert "integrate.api.nvidia.com" in str(cliente.base_url)
