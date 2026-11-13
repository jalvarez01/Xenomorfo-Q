"""Pruebas del ejecutor de casos con un cliente falso, sin red (apoyo a T21).

Tareas relacionadas: T21 (ejecución de casos), T11 (directora), T17 (pruebas sin API).
"""
from __future__ import annotations

import json

import pytest

from director import llm
from director.llm import ConfigLLM
from director.partida import Partida
from director.prompt import PROMPT_VERSION
from experiments import casos
from experiments.casos import CASOS, calcular_esperado, ejecutar_casos
from tests.test_directora import ClienteFalso, pide, texto

# Valor de clave falso para comprobar que nunca llega a los archivos. No tiene la forma
# de una clave real, así el escaneo de claves del repositorio no lo confunde.
CLAVE_FALSA = "clave-secreta-de-prueba-0123456789"


@pytest.fixture(autouse=True)
def entorno(monkeypatch):
    """Define una clave falsa en el entorno y desactiva la carga de .env."""
    monkeypatch.setattr(llm, "_cargar_dotenv", lambda: None)
    for nombre in (llm.VAR_PROVEEDOR, *llm.VARIABLES_CLAVE, llm.VAR_MODELO, llm.VAR_URL_BASE):
        monkeypatch.delenv(nombre, raising=False)
    monkeypatch.setenv(llm.VAR_CLAVE, CLAVE_FALSA)


def guion() -> list:
    """Respuestas falsas para los 6 casos: C1 pide dos herramientas y C5 una con error."""
    return [
        pide("c1", "estado_partida", {}),
        pide("c2", "ruta_mas_corta", {"origen": "alienigena", "destino": "tripulante"}),
        texto("Bodega, a 15 pasos."),
        texto("No lo ve."),
        texto("Va a Bodega."),
        texto("Hecho."),
        pide("c3", "ruta_mas_corta", {"origen": "Enfermería", "destino": "Hangar"}),
        texto("La Enfermería no existe."),
        texto("Distancias."),
    ]


def test_seis_casos_definidos():
    """Hay 6 casos con id, categoría, pregunta y herramientas esperadas; solo C3 se prepara."""
    assert [c["id"] for c in CASOS] == ["C1", "C2", "C3", "C4", "C5", "C6"]
    for caso in CASOS:
        assert {"id", "categoria", "pregunta", "herramientas_esperadas"} <= set(caso)
        assert set(caso) - {"id", "categoria", "pregunta", "herramientas_esperadas"} <= {"preparacion"}
    assert [c["id"] for c in CASOS if "preparacion" in c] == ["C3"]


def test_preparacion_de_c3_es_la_de_la_busqueda():
    """La preparación guardada en C3 es la primera que encuentra buscar_preparacion."""
    c3 = next(c for c in CASOS if c["id"] == "C3")
    assert casos.buscar_preparacion() == c3["preparacion"] == {"semilla": 0, "ticks": 11}


def test_c3_ya_no_es_trivial():
    """Después de la preparación, C3 predice otra sala con confianza de al menos 0.5."""
    esperado = calcular_esperado("C3")
    assert esperado["ticks_analizados"] == 10
    assert esperado["confianza"] >= casos.CONFIANZA_MIN_C3
    assert esperado["sala"] != esperado["sala_actual_tripulante"]
    assert (esperado["sala"], esperado["sala_actual_tripulante"]) == ("Hangar", "Corredor B")


def test_preparar_partida_avanza_en_tramos():
    """preparar_partida avanza más de 20 ticks en tramos y no hace nada con 0."""
    partida = Partida(semilla=0)
    assert casos.preparar_partida(partida, 0) is None and partida.env.tick == 0
    resultado = casos.preparar_partida(partida, 25)
    assert partida.env.tick == 25 and resultado["capturado"] is False


def test_esperados_coinciden_con_las_herramientas():
    """Los valores esperados de la semilla 42 son los de las herramientas sin modelo."""
    assert calcular_esperado("C1") == {"sala_tripulante": "Bodega", "pasos_alienigena_tripulante": 15}
    assert calcular_esperado("C2") == {"ve": False, "distancia_casillas": 15}
    assert calcular_esperado("C4")["se_acerco"] is True
    assert "no existe" in calcular_esperado("C5")["error"]
    c6 = calcular_esperado("C6")
    assert len(c6["pasos_por_sala"]) == 8 and c6["limite_alcanzado"] is True
    with pytest.raises(ValueError, match="Caso desconocido"):
        calcular_esperado("C9")


def test_escribe_json_y_markdown_con_todos_los_campos(tmp_path):
    """El ejecutor escribe JSON y Markdown con todos los campos y deja vacía la valoración."""
    ruta_json, ruta_md = ejecutar_casos(salida=tmp_path, cliente=ClienteFalso(guion()),
                                        config=ConfigLLM())
    assert ruta_json.exists() and ruta_md.exists()
    assert f"prompt{PROMPT_VERSION}" in ruta_json.name and "semilla42" in ruta_json.name
    informe = json.loads(ruta_json.read_text(encoding="utf-8"))
    assert set(informe) == {"fecha", "prompt_version", "modelo", "temperatura", "semilla",
                            "limite", "casos"}
    assert informe["modelo"] == ConfigLLM().modelo and informe["semilla"] == 42
    campos = {"id", "categoria", "pregunta", "herramientas_esperadas", "semilla_caso", "resultado_esperado",
              "respuesta", "llamadas", "numero_llamadas", "limite_alcanzado",
              "latencia_segundos", "valoracion", "correcto"}
    for caso in informe["casos"]:
        assert set(caso) - {"preparacion"} == campos
        assert caso["valoracion"] == "" and caso["correcto"] is None
    c3 = informe["casos"][2]
    assert c3["preparacion"] == {"semilla": 0, "ticks": 11} and c3["semilla_caso"] == 0
    assert informe["casos"][0]["semilla_caso"] == 42
    c1 = informe["casos"][0]
    assert [ll["herramienta"] for ll in c1["llamadas"]] == ["estado_partida", "ruta_mas_corta"]
    assert json.loads(c1["llamadas"][1]["resultado"])["pasos"] == 15
    assert informe["casos"][4]["llamadas"][0]["error"] is True
    md = ruta_md.read_text(encoding="utf-8")
    for caso in CASOS:
        assert f"## {caso['id']}" in md and caso["pregunta"] in md
    assert "**Valoración:** (pendiente)" in md
    assert "preparada avanzando 11 ticks" in md


def test_la_clave_nunca_aparece(tmp_path):
    """Ni la clave ni su nombre de variable aparecen en los archivos."""
    for ruta in ejecutar_casos(salida=tmp_path, cliente=ClienteFalso(guion()), config=ConfigLLM()):
        contenido = ruta.read_text(encoding="utf-8")
        assert CLAVE_FALSA not in contenido
        for variable in llm.VARIABLES_CLAVE:
            assert variable not in contenido


def test_comando_sin_clave(monkeypatch, tmp_path, capsys):
    """Sin la clave del proveedor el comando sale con código 2, sin escribir archivos."""
    monkeypatch.delenv(llm.VAR_CLAVE)
    assert casos.main(["--salida", str(tmp_path)]) == casos.CODIGO_SIN_CLAVE
    assert llm.VAR_CLAVE in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == []


def test_la_directora_pregunta_sobre_la_partida_preparada(tmp_path):
    """En C3 la directora ve el mismo estado preparado que el valor esperado."""
    guion_c3 = [pide("p1", "predecir_destino", {}), texto("Va al Hangar.")]
    caso = next(c for c in CASOS if c["id"] == "C3")
    ruta_json, _ = ejecutar_casos(salida=tmp_path, cliente=ClienteFalso(guion_c3),
                                  config=ConfigLLM(), casos=[caso])
    c3 = json.loads(ruta_json.read_text(encoding="utf-8"))["casos"][0]
    obtenido = json.loads(c3["llamadas"][0]["resultado"])
    assert obtenido["sala"] == c3["resultado_esperado"]["sala"] == "Hangar"
    assert obtenido["ticks_analizados"] == 10


def test_comando_con_cliente_falso(monkeypatch, tmp_path, capsys):
    """El comando corre los casos e imprime dónde quedaron los archivos."""
    cliente = ClienteFalso(guion())
    monkeypatch.setattr("director.directora.crear_cliente", lambda config: cliente)
    assert casos.main(["--semilla", "42", "--salida", str(tmp_path)]) == 0
    assert "Resultados en" in capsys.readouterr().out
    assert len(list(tmp_path.glob("casos_*.json"))) == 1
