"""Pruebas del panel visual: sesión, servidor HTTP local y control manual del tripulante (D16).

El servidor corre en un hilo sobre 127.0.0.1 con un puerto libre; el modelo es un cliente
falso, sin red.

Contenido principal:
    servidor: fixture con el panel corriendo y una función para pedirle rutas.
    huella_partida, huella_step: resumen de partidas con semilla, para comprobar que el
        control manual opcional no cambió nada cuando no se usa.

Tareas relacionadas: T24 (demostración), D16.
"""
from __future__ import annotations

import hashlib
import json
import threading
import urllib.error
import urllib.request

import pytest

from alien.reglas import AlienReglas
from director import llm
from director.llm import ConfigLLM
from panel.servidor import HOST, crear_servidor
from panel.sesion import Sesion, objetivo_alien
from sim import EstacionEnv
from sim.avance import Avance
from tests.test_directora import ClienteFalso, pide, texto

# Valor de clave falso para comprobar que nunca sale en una respuesta. No tiene la forma de
# una clave real, así el escaneo de claves del repositorio no lo confunde.
CLAVE_FALSA = "clave-secreta-del-panel-0123456789"

# Huellas tomadas con el código ANTES de agregar el control manual (commit 0bc8757 de
# development): partidas completas con AlienReglas y 200 pasos con acciones fijas.
HUELLAS_PARTIDA = {
    42: "f7678f6f96fdb09fe2eabd79c197ff691035052cb90f71356af368270c4b2e86",
    0: "0049ca1977b481ca21fabd27f66d49f1ed971b47a34b3d902f62824d0ce8ebaa",
    7: "705a49589df3cce62d46526491a600a6c9702fff289139ae31db66fe041a92ad",
}
HUELLA_STEP_42 = "eb4548c5d252a94c26f9d5cd8b5ac59bfbeb61e2b7d4302e3bd87314498ba7d2"


@pytest.fixture(autouse=True)
def entorno(monkeypatch):
    """Define una clave falsa y desactiva la carga de .env, para no depender del equipo."""
    monkeypatch.setattr(llm, "_cargar_dotenv", lambda: None)
    for nombre in (llm.VAR_PROVEEDOR, *llm.VARIABLES_CLAVE, llm.VAR_MODELO, llm.VAR_URL_BASE):
        monkeypatch.delenv(nombre, raising=False)
    monkeypatch.setenv(llm.VAR_CLAVE, CLAVE_FALSA)


def levantar(sesion: Sesion):
    """Arranca el panel en un hilo y devuelve (pedir, servidor); pedir(ruta, datos) -> (código, cuerpo)."""
    servidor = crear_servidor(sesion, puerto=0)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    base = f"http://{HOST}:{servidor.server_port}"
    cuerpos: list[str] = []

    def pedir(ruta: str, datos: dict | None = None, crudo: bytes | None = None):
        cuerpo = crudo if crudo is not None else (None if datos is None else json.dumps(datos).encode())
        req = urllib.request.Request(base + ruta, data=cuerpo, method="GET" if cuerpo is None else "POST",
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                codigo, texto_resp = r.status, r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            codigo, texto_resp = e.code, e.read().decode("utf-8")
        cuerpos.append(texto_resp)
        return codigo, (json.loads(texto_resp) if texto_resp.startswith("{") else texto_resp)

    pedir.cuerpos = cuerpos
    return pedir, servidor


@pytest.fixture
def servidor():
    """Panel con semilla 42 y un cliente falso que pide dar_pista, luego avanzar 5 ticks y responde."""
    cliente = ClienteFalso([
        pide("c1", "dar_pista", {"sala": "bodega"}),
        pide("c2", "avanzar_simulacion", {"ticks": 5}),
        texto("Le di una pista hacia Bodega y avancé 5 ticks."),
    ])
    pedir, srv = levantar(Sesion(semilla=42, cliente=cliente, config=ConfigLLM()))
    yield pedir
    srv.shutdown()
    srv.server_close()
    for cuerpo in pedir.cuerpos:
        assert CLAVE_FALSA not in cuerpo


# --- Rutas --------------------------------------------------------------------------------


def test_pagina_sin_recursos_externos(servidor):
    """GET / sirve la página, que no carga nada de internet."""
    codigo, pagina = servidor("/")
    assert codigo == 200 and "<canvas id=\"map\"" in pagina
    assert "http://" not in pagina and "https://" not in pagina


def test_pagina_con_parametros(servidor):
    """La página también se sirve con parámetros, como ?modo=tu para abrir en modo de juego."""
    codigo, pagina = servidor("/?modo=tu")
    assert codigo == 200 and "<canvas id=\"map\"" in pagina


def test_mapa(servidor):
    """GET /api/mapa da las filas de vela9, las 8 salas y una etiqueta por sala."""
    codigo, mapa = servidor("/api/mapa")
    assert codigo == 200 and (mapa["ancho"], mapa["alto"]) == (24, 15)
    assert len(mapa["etiquetas"]) == 8 and mapa["etiquetas"][0] == {"nombre": "Médico", "x": 1, "y": 1}
    assert mapa["salas"][1][1] == 0 and mapa["salas"][3][7] == -1


def test_estado_inicial(servidor):
    """GET /api/estado da las posiciones, salas y datos reales de la partida 42."""
    env = EstacionEnv()
    env.reset(42)
    codigo, e = servidor("/api/estado")
    assert codigo == 200
    assert (e["tripulante"]["x"], e["tripulante"]["y"]) == env.tripulante
    assert (e["alien"]["x"], e["alien"]["y"]) == env.alien
    assert (e["tripulante"]["sala"], e["alien"]["sala"]) == ("Bodega", "Médico")
    assert e["distancia"] == 15 and e["ve"] is False and e["pistas_restantes"] == 3
    assert [[x, y] for y, x in zip(*env.campo_vision.nonzero())] == e["vision"]
    assert e["ruta"][0] == [e["alien"]["x"], e["alien"]["y"]]


def test_paso_avanza_como_la_herramienta(servidor):
    """POST /api/paso avanza un tick igual que avanzar_simulacion(1) en la misma semilla."""
    from director.herramientas import crear_herramientas
    from director.partida import Partida
    partida = Partida(42)
    crear_herramientas(partida)["avanzar_simulacion"](3)
    for _ in range(3):
        codigo, e = servidor("/api/paso", {})
    assert codigo == 200 and e["tick"] == 3
    assert (e["alien"]["x"], e["alien"]["y"]) == partida.env.alien
    assert (e["tripulante"]["x"], e["tripulante"]["y"]) == partida.env.tripulante


def test_reiniciar(servidor):
    """POST /api/reiniciar empieza otra partida con la semilla pedida y vacía el chat."""
    servidor("/api/paso", {})
    codigo, e = servidor("/api/reiniciar", {"semilla": 7})
    env = EstacionEnv()
    env.reset(7)
    assert codigo == 200 and e["semilla"] == 7 and e["tick"] == 0 and e["chat"] == []
    assert (e["tripulante"]["x"], e["tripulante"]["y"]) == env.tripulante


def test_mover_y_errores(servidor):
    """POST /api/mover mueve al tripulante; una dirección o un cuerpo inválidos dan 409."""
    codigo, e = servidor("/api/mover", {"direccion": "izquierda"})
    assert codigo == 200 and e["tick"] == 1 and (e["tripulante"]["x"], e["tripulante"]["y"]) == (1, 12)
    codigo, e = servidor("/api/mover", {"direccion": "volar"})
    assert codigo == 409 and "Dirección desconocida" in e["error"]
    codigo, e = servidor("/api/paso", crudo=b"{no es json")
    assert codigo == 409 and "JSON" in e["error"]
    codigo, _ = servidor("/api/nada", {})
    assert codigo == 404


def test_preguntar_usa_la_misma_partida(servidor):
    """POST /api/preguntar devuelve llamadas y respuesta, y el mapa refleja la pista y el avance."""
    codigo, r = servidor("/api/preguntar", {"pregunta": "Dale una pista hacia bodega y avanza 5 ticks."})
    assert codigo == 200 and r["respuesta"].startswith("Le di una pista")
    assert [c["herramienta"] for c in r["llamadas"]] == ["dar_pista", "avanzar_simulacion"]
    assert r["llamadas"][0]["resultado"] == '{"sala": "Bodega", "pistas_restantes": 2}'
    assert r["limite_alcanzado"] is False and r["numero_llamadas"] == 2
    e = r["estado"]
    assert e["tick"] == 5 and e["pistas_restantes"] == 2
    assert len(e["chat"]) == 1
    assert any(x["tipo"] == "agente" and x["texto"].startswith("dar_pista") for x in e["registro"])
    _, despues = servidor("/api/estado")
    assert despues["tick"] == 5 and despues["chat"][0]["pregunta"].startswith("Dale una pista")


def test_preguntar_vacia(servidor):
    """Una pregunta vacía da 409 sin llamar al modelo."""
    codigo, r = servidor("/api/preguntar", {"pregunta": "   "})
    assert codigo == 409 and "vacía" in r["error"]


# --- Clave ----------------------------------------------------------------------------------


def test_sin_clave_el_panel_funciona_y_el_chat_explica(monkeypatch):
    """Sin clave el mapa y los pasos funcionan, y preguntar da el mensaje del comando sin valores."""
    monkeypatch.delenv(llm.VAR_CLAVE)
    pedir, srv = levantar(Sesion(semilla=42))
    try:
        assert pedir("/api/paso", {})[0] == 200
        codigo, r = pedir("/api/preguntar", {"pregunta": "¿Dónde está el tripulante?"})
        assert codigo == 200 and r["error"].startswith("No se puede consultar el modelo.")
        assert llm.VAR_CLAVE in r["error"] and ".env.example" in r["error"]
        assert r["estado"]["chat"] == []
    finally:
        srv.shutdown()
        srv.server_close()


def test_error_del_modelo_no_muestra_su_texto(monkeypatch):
    """Si el modelo falla, la respuesta solo nombra el error, nunca su texto (puede traer la clave)."""
    class Falla(Exception):
        status_code = 401

    def lanzar(**kwargs):
        raise Falla(f"Clave incorrecta: {CLAVE_FALSA}")

    cliente = ClienteFalso([])
    cliente.chat.completions.create = lanzar
    pedir, srv = levantar(Sesion(semilla=42, cliente=cliente, config=ConfigLLM()))
    try:
        codigo, r = pedir("/api/preguntar", {"pregunta": "Hola"})
        assert codigo == 200 and r["error"] == "El modelo no respondió: Falla (código 401)."
        assert all(CLAVE_FALSA not in c for c in pedir.cuerpos)
    finally:
        srv.shutdown()
        srv.server_close()


def test_solo_escucha_en_localhost():
    """El servidor se liga a 127.0.0.1, no a todas las interfaces."""
    srv = crear_servidor(Sesion(semilla=42), puerto=0)
    try:
        assert srv.server_address[0] == "127.0.0.1"
    finally:
        srv.server_close()


# --- Control manual del tripulante ----------------------------------------------------------


def test_mover_contra_pared_no_avanza():
    """El tripulante no atraviesa paredes: contra una pared se queda, aunque el tick avance."""
    s = Sesion(semilla=42)
    s.directora.partida.env.tripulante = (1, 12)
    e = s.mover("izquierda")  # (0, 12) es pared
    assert (e["tripulante"]["x"], e["tripulante"]["y"]) == (1, 12) and e["tick"] == 1


def test_mover_no_entra_a_la_casilla_del_alien():
    """La regla manual no deja entrar a la casilla del alienígena (en step la captura llega antes)."""
    env = EstacionEnv()
    env.reset(42)
    env.alien, env.tripulante = (4, 12), (3, 12)
    assert env._paso_manual(1) == (3, 12)
    assert env._paso_manual(3) == (2, 12)


def test_paso_manual_no_usa_el_azar():
    """Un paso manual lejos del alienígena mueve al tripulante sin consumir el generador aleatorio."""
    env = EstacionEnv()
    env.reset(42)
    env.alien, env.tripulante = (20, 3), (3, 12)
    estado_rng = env.rng.bit_generator.state
    _, _, _, info = env.step(4, accion_tripulante=1)
    assert env.tripulante == (4, 12) and not info["capturado"]
    assert env.rng.bit_generator.state == estado_rng


def test_accion_del_tripulante_invalida():
    """Una acción manual fuera de 0 a 4 da ValueError."""
    env = EstacionEnv()
    env.reset(42)
    with pytest.raises(ValueError, match="tripulante"):
        env.step(1, accion_tripulante=7)


# --- Determinismo -----------------------------------------------------------------------------


def huella_partida(semilla: int) -> str:
    """Hash de una partida completa con AlienReglas: trayectoria, alien final, tick y estado del azar."""
    env = EstacionEnv()
    env.reset(semilla)
    avance = Avance(env, AlienReglas(env))
    while env.tick < env.max_ticks:
        if avance.avanzar(20)["capturado"]:
            break
    datos = [list(c) for c in env.trayectoria] + [list(env.alien), env.tick, int(env.rng.integers(1 << 30))]
    return hashlib.sha256(json.dumps(datos).encode()).hexdigest()


def huella_step(semilla: int) -> str:
    """Hash de 200 pasos de env.step con acciones fijas, sin control manual."""
    env = EstacionEnv()
    env.reset(semilla)
    datos = []
    for i in range(200):
        _, r, fin, info = env.step([0, 1, 2, 3, 4][i % 5])
        datos.append([list(env.alien), list(env.tripulante), r, fin, info["ve_tripulante"]])
        if fin:
            env.reset()
    return hashlib.sha256(json.dumps(datos).encode()).hexdigest()


@pytest.mark.parametrize("semilla", sorted(HUELLAS_PARTIDA))
def test_sin_control_manual_las_partidas_no_cambian(semilla):
    """Con el control manual opcional sin usar, cada partida con semilla es idéntica a la de antes."""
    assert huella_partida(semilla) == HUELLAS_PARTIDA[semilla]


def test_sin_control_manual_step_no_cambia():
    """env.step sin acción del tripulante da la misma secuencia que antes con la semilla 42."""
    assert huella_step(42) == HUELLA_STEP_42


def test_objetivo_alien_no_modifica_el_alien():
    """Leer el objetivo para dibujar la ruta no cambia el estado del alienígena ni la partida."""
    s = Sesion(semilla=42)
    alien = s.directora.partida.alien
    antes = (alien.estado, alien.ultima_vista, alien.pista, alien._objetivo, set(alien._visitadas))
    objetivo_alien(alien)
    s.estado()
    assert antes == (alien.estado, alien.ultima_vista, alien.pista, alien._objetivo, set(alien._visitadas))


# --- Rama del árbol del alienígena (etiqueta del mapa y panel de reglas) ---------------------


def _sesion_con(alien, tripulante, direccion, ultima_vista=None, pista=None) -> Sesion:
    """Sesión de vela9 con el alienígena y el tripulante en casillas elegidas."""
    from sim.percepcion import campo_de_vision
    s = Sesion(semilla=42)
    env, a = s.directora.partida.env, s.directora.partida.alien
    env.alien, env.tripulante, env.direccion_alien = alien, tripulante, direccion
    env.campo_vision = campo_de_vision(env.mapa, env.alien, env.direccion_alien)
    a.ultima_vista, a.pista = ultima_vista, pista
    return s


@pytest.mark.parametrize("caso, esperado", [
    ({"alien": (10, 3), "tripulante": (12, 3), "direccion": (1, 0)}, "persigue"),
    ({"alien": (10, 3), "tripulante": (2, 12), "direccion": (1, 0), "ultima_vista": (13, 3)}, "ultima_casilla"),
    ({"alien": (10, 3), "tripulante": (2, 12), "direccion": (1, 0), "pista": 5}, "pista"),
    ({"alien": (10, 3), "tripulante": (2, 12), "direccion": (1, 0)}, "patrulla"),
    # Si ya llegó a la última casilla vista y no lo ve, esa rama no aplica.
    ({"alien": (10, 3), "tripulante": (2, 12), "direccion": (1, 0), "ultima_vista": (10, 3)}, "patrulla"),
])
def test_rama_del_alien(caso, esperado):
    """La rama sigue el orden del árbol: lo ve, última casilla vista, pista, patrulla."""
    from panel.sesion import RAMAS, rama_alien
    s = _sesion_con(**caso)
    rama, objetivo = rama_alien(s.directora.partida.alien)
    e = s.estado()
    assert rama == esperado == e["alien"]["rama"]
    assert e["alien"]["rama_texto"] == RAMAS[esperado]
    assert e["ruta"][-1] == list(objetivo)  # la ruta dibujada va al objetivo de esa misma rama


def test_la_pagina_usa_un_solo_campo_para_la_rama():
    """La etiqueta del mapa y el panel de reglas leen rama, no el estado interno del alienígena."""
    from panel.servidor import PAGINA
    from panel.sesion import RAMAS
    pagina = PAGINA.read_text(encoding="utf-8")
    assert "E.alien.rama_texto" in pagina and "RAMAS.indexOf(E.alien.rama)" in pagina
    assert "E.alien.estado" not in pagina
    assert f"const RAMAS = {json.dumps(list(RAMAS))};" in pagina
