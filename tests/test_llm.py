"""Pruebas de la configuración del LLM, sin llamadas de red ni claves reales.

Cada prueba desactiva la carga de .env para que un archivo real del equipo no cambie el
resultado, y limpia las variables con monkeypatch.

Tareas relacionadas: T17 (pruebas sin API), T14 (configuración del LLM).
"""
from __future__ import annotations

import pytest

from director import llm

VARIABLES = (llm.VAR_CLAVE, llm.VAR_CLAVE_OPENAI, llm.VAR_PROVEEDOR,
             llm.VAR_MODELO, llm.VAR_URL_BASE, llm.VAR_TEMPERATURA)


@pytest.fixture(autouse=True)
def entorno_limpio(monkeypatch):
    """Aísla cada prueba del entorno y de cualquier .env local."""
    monkeypatch.setattr(llm, "_cargar_dotenv", lambda: None)
    for nombre in VARIABLES:
        monkeypatch.delenv(nombre, raising=False)


def test_valores_por_defecto():
    """Sin variables, la configuración toma los valores por defecto."""
    config = llm.cargar_config()
    assert config == llm.ConfigLLM()
    assert config.modelo == "meta/llama-3.3-70b-instruct"
    assert config.url_base == "https://integrate.api.nvidia.com/v1"
    assert config.temperatura == 0.0


def test_variables_cambian_la_configuracion(monkeypatch):
    """XQ_MODELO, XQ_URL_BASE y XQ_TEMPERATURA se reflejan en ConfigLLM."""
    monkeypatch.setenv(llm.VAR_MODELO, "otro/modelo")
    monkeypatch.setenv(llm.VAR_URL_BASE, "http://localhost:8000/v1")
    monkeypatch.setenv(llm.VAR_TEMPERATURA, "0.7")
    config = llm.cargar_config()
    assert config.modelo == "otro/modelo"
    assert config.url_base == "http://localhost:8000/v1"
    assert config.temperatura == 0.7


def test_temperatura_invalida(monkeypatch):
    """Una temperatura que no es número lanza ValueError con el nombre de la variable."""
    monkeypatch.setenv(llm.VAR_TEMPERATURA, "tibia")
    with pytest.raises(ValueError, match=llm.VAR_TEMPERATURA):
        llm.cargar_config()


def test_sin_clave_lanza_error_claro():
    """Sin NVIDIA_API_KEY, crear_cliente lanza ClaveFaltanteError nombrando la variable."""
    with pytest.raises(llm.ClaveFaltanteError) as info:
        llm.crear_cliente(llm.ConfigLLM())
    mensaje = str(info.value)
    assert "NVIDIA_API_KEY" in mensaje
    assert ".env" in mensaje
    assert "Colab" in mensaje


def test_clave_vacia_cuenta_como_faltante(monkeypatch):
    """Una NVIDIA_API_KEY vacía o con espacios se trata como ausente."""
    monkeypatch.setenv(llm.VAR_CLAVE, "   ")
    with pytest.raises(llm.ClaveFaltanteError):
        llm.crear_cliente()


def test_crear_cliente_usa_la_url_base(monkeypatch):
    """Con clave, el cliente apunta a la URL base configurada (sin llamadas de red)."""
    monkeypatch.setenv(llm.VAR_CLAVE, "clave-ficticia-de-prueba")
    cliente = llm.crear_cliente(llm.ConfigLLM(url_base="http://localhost:9/v1"))
    assert str(cliente.base_url).rstrip("/") == "http://localhost:9/v1"


def test_openai_configura_modelo_url_y_clave_correctos(monkeypatch):
    monkeypatch.setenv(llm.VAR_PROVEEDOR, "openai")
    monkeypatch.setenv(llm.VAR_CLAVE_OPENAI, "clave-openai-ficticia")
    monkeypatch.setenv(llm.VAR_CLAVE, "clave-nvidia-ficticia")
    config = llm.cargar_config()
    assert config.proveedor == "openai"
    assert config.modelo == "gpt-5.4-nano"
    assert config.url_base == "https://api.openai.com/v1"
    cliente = llm.crear_cliente(config)
    assert cliente.api_key == "clave-openai-ficticia"
    assert str(cliente.base_url).rstrip("/") == config.url_base


def test_openai_no_usa_clave_nvidia(monkeypatch):
    monkeypatch.setenv(llm.VAR_PROVEEDOR, "openai")
    monkeypatch.setenv(llm.VAR_CLAVE, "clave-nvidia-ficticia")
    with pytest.raises(llm.ClaveFaltanteError, match="OPENAI_API_KEY"):
        llm.crear_cliente()


def test_proveedor_invalido_no_se_ignora(monkeypatch):
    monkeypatch.setenv(llm.VAR_PROVEEDOR, "otro")
    with pytest.raises(ValueError, match="XQ_PROVEEDOR"):
        llm.cargar_config()
