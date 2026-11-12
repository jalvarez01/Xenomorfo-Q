"""Pruebas del comando python -m director con un cliente falso, sin red (T11).

Tareas relacionadas: T11 (directora y comando), T17 (pruebas sin API).
"""
from __future__ import annotations

import json

import pytest

from director import __main__ as cli
from director import directora, llm
from tests.test_directora import ClienteFalso, pide, texto


@pytest.fixture(autouse=True)
def sin_clave(monkeypatch):
    """Aísla las pruebas de la clave real y de cualquier .env local."""
    monkeypatch.setattr(llm, "_cargar_dotenv", lambda: None)
    monkeypatch.delenv(llm.VAR_CLAVE, raising=False)


def usar_cliente(monkeypatch, guion: list) -> ClienteFalso:
    """Hace que la directora use un cliente falso en vez del real."""
    cliente = ClienteFalso(guion)
    monkeypatch.setattr(directora, "crear_cliente", lambda config: cliente)
    return cliente


def test_pregunta_con_registro(monkeypatch, capsys):
    """Con --registro imprime la respuesta, el registro y el número de llamadas."""
    usar_cliente(monkeypatch, [pide("c1", "estado_partida", {}), texto("Está en Bodega.")])
    codigo = cli.main(["¿En qué sala está el tripulante?", "--registro"])
    salida = capsys.readouterr().out
    assert codigo == 0
    assert salida.startswith("Está en Bodega.\n")
    assert "1. estado_partida({})" in salida
    assert "Llamadas: 1. Límite alcanzado: no." in salida


def test_pregunta_sin_registro(monkeypatch, capsys):
    """Sin --registro solo imprime la respuesta."""
    usar_cliente(monkeypatch, [texto("Hola.")])
    assert cli.main(["Hola", "--semilla", "7", "--limite", "3"]) == 0
    assert capsys.readouterr().out == "Hola.\n"


def test_sin_clave_codigo_2(capsys):
    """Sin NVIDIA_API_KEY sale con código 2 y un mensaje que apunta a .env.example, sin traza."""
    assert cli.main(["¿Dónde está el tripulante?"]) == cli.CODIGO_SIN_CLAVE == 2
    error = capsys.readouterr().err
    assert "NVIDIA_API_KEY" in error and ".env.example" in error
    assert "Traceback" not in error


def test_modo_interactivo(monkeypatch, capsys):
    """En modo interactivo 'estado' no usa el modelo, una pregunta sí y 'salir' termina."""
    cliente = usar_cliente(monkeypatch, [texto("Respuesta.")])
    entradas = iter(["estado", "", "¿Qué pasa?", "salir", "nunca se lee"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(entradas))
    assert cli.main([]) == 0
    salida = capsys.readouterr().out
    inicio = salida.index("{")
    estado = json.loads(salida[inicio:salida.index("\n}", inicio) + 2])
    assert estado["tick"] == 0 and estado["tripulante"]["sala"] == "Bodega"
    assert "Respuesta." in salida
    assert len(cliente.llamadas) == 1


def test_modo_interactivo_termina_con_fin_de_entrada(monkeypatch):
    """Si se cierra la entrada (Ctrl+D), el modo interactivo termina sin error."""
    usar_cliente(monkeypatch, [])

    def fin(prompt=""):
        raise EOFError

    monkeypatch.setattr("builtins.input", fin)
    assert cli.main([]) == 0
