"""Pruebas del panel en línea (D18): sesiones por visitante, cupos del chat, /salud y deploy/.

No usan red ni la API real: el servidor corre en 127.0.0.1 con un puerto libre y el modelo
es un cliente falso. Los relojes de las sesiones y los cupos son falsos para probar la
caducidad y la ventana de una hora sin esperar.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from director import llm
from director.llm import ConfigLLM
from panel.__main__ import leer_argumentos
from panel.servidor import HOST, crear_servidor
from panel.sesion import Sesion
from panel.sesiones import (NOMBRE_COOKIE, AlmacenSesiones, Entrada, LimitePreguntas,
                            leer_limite, token_valido)
from tests.test_directora import ClienteFalso, pide, texto

RAIZ = Path(__file__).resolve().parent.parent
DEPLOY = RAIZ / "deploy"
# Valor con forma de clave; nunca debe aparecer en una respuesta ni en la terminal.
CLAVE_FALSA = "clave-falsa-de-prueba-panel-en-linea"


class Reloj:
    """Reloj falso: devuelve self.t y se adelanta a mano."""

    def __init__(self):
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


@pytest.fixture(autouse=True)
def entorno(monkeypatch):
    """Clave falsa, sin .env del equipo y sin cupos del entorno."""
    monkeypatch.setattr(llm, "_cargar_dotenv", lambda: None)
    for nombre in (llm.VAR_PROVEEDOR, *llm.VARIABLES_CLAVE, llm.VAR_MODELO, llm.VAR_URL_BASE,
                   "XQ_PANEL_MAX_SESION", "XQ_PANEL_MAX_HORA", "PORT"):
        monkeypatch.delenv(nombre, raising=False)
    monkeypatch.setenv(llm.VAR_CLAVE, CLAVE_FALSA)


def cliente_que_responde(n: int) -> ClienteFalso:
    """Cliente falso con n respuestas de texto, sin herramientas."""
    return ClienteFalso([texto(f"Respuesta {i}.") for i in range(n)])


class Panel:
    """Servidor del panel en un hilo, con un pedidor que guarda cuerpos y cabeceras."""

    def __init__(self, sesiones, limite: LimitePreguntas | None = None):
        self.servidor = crear_servidor(sesiones, puerto=0, limite=limite)
        threading.Thread(target=self.servidor.serve_forever, daemon=True).start()
        self.base = f"http://{HOST}:{self.servidor.server_port}"
        self.cuerpos: list[str] = []
        self.cabeceras: list[str] = []

    def pedir(self, ruta: str, datos: dict | None = None, cookie: str | None = None,
              cabeceras: dict | None = None):
        """(código, cuerpo como dict o texto, Set-Cookie o None)."""
        h = {"Content-Type": "application/json", **(cabeceras or {})}
        if cookie:
            h["Cookie"] = f"{NOMBRE_COOKIE}={cookie}"
        cuerpo = None if datos is None else json.dumps(datos).encode()
        req = urllib.request.Request(self.base + ruta, data=cuerpo, headers=h,
                                     method="GET" if cuerpo is None else "POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                codigo, texto_resp, galleta = r.status, r.read().decode(), r.headers.get("Set-Cookie")
                self.cabeceras.append(str(r.headers))
        except urllib.error.HTTPError as e:
            codigo, texto_resp, galleta = e.code, e.read().decode(), e.headers.get("Set-Cookie")
            self.cabeceras.append(str(e.headers))
        self.cuerpos.append(texto_resp)
        valor = json.loads(texto_resp) if texto_resp.startswith("{") else texto_resp
        return codigo, valor, galleta

    def cerrar(self):
        self.servidor.shutdown()
        self.servidor.server_close()
        for texto_visto in self.cuerpos + self.cabeceras:
            assert CLAVE_FALSA not in texto_visto


def token_de(set_cookie: str) -> str:
    """Token de una cabecera Set-Cookie."""
    return set_cookie.split(";")[0].split("=", 1)[1]


@pytest.fixture
def panel():
    """Panel con una partida por visitante y cupos amplios; cada sesión tiene su cliente falso."""
    p = Panel(AlmacenSesiones(lambda: Sesion(semilla=42, cliente=cliente_que_responde(30),
                                             config=ConfigLLM())),
              LimitePreguntas(max_sesion=0, max_hora=0))
    yield p
    p.cerrar()


# --- Sesiones por visitante -------------------------------------------------------------


def test_la_pagina_entrega_una_cookie_segura(panel):
    """GET / crea la sesión y manda una cookie HttpOnly y SameSite=Lax, sin Secure en HTTP."""
    codigo, _, galleta = panel.pedir("/")
    assert codigo == 200 and galleta is not None
    assert galleta.startswith(f"{NOMBRE_COOKIE}=")
    assert "HttpOnly" in galleta and "SameSite=Lax" in galleta and "Path=/" in galleta
    assert "Secure" not in galleta
    assert token_valido(token_de(galleta))
    # Con la cookie ya no se manda otra.
    assert panel.pedir("/api/estado", cookie=token_de(galleta))[2] is None


def test_cookie_secure_detras_de_caddy(panel):
    """Con X-Forwarded-Proto: https desde 127.0.0.1 (Caddy) la cookie lleva Secure."""
    _, _, galleta = panel.pedir("/", cabeceras={"X-Forwarded-Proto": "https"})
    assert "Secure" in galleta


def test_cada_visitante_tiene_su_partida(panel):
    """Lo que hace un visitante no cambia la partida del otro."""
    a = token_de(panel.pedir("/")[2])
    b = token_de(panel.pedir("/")[2])
    assert a != b
    for _ in range(3):
        panel.pedir("/api/paso", {}, cookie=a)
    assert panel.pedir("/api/estado", cookie=a)[1]["tick"] == 3
    assert panel.pedir("/api/estado", cookie=b)[1]["tick"] == 0
    panel.pedir("/api/preguntar", {"pregunta": "¿Dónde está?"}, cookie=a)
    assert len(panel.pedir("/api/estado", cookie=a)[1]["chat"]) == 1
    assert panel.pedir("/api/estado", cookie=b)[1]["chat"] == []


def test_cookie_desconocida_da_una_sesion_nueva(panel):
    """Un token inventado o mal formado no da acceso a nada: crea una sesión nueva."""
    for falso in ("x" * 43, "corto", "a;b"):
        codigo, estado, galleta = panel.pedir("/api/estado", cookie=falso)
        assert codigo == 200 and estado["tick"] == 0
        assert galleta is not None and token_de(galleta) != falso


def test_sesion_caduca_por_inactividad():
    """Tras 30 minutos sin uso la sesión se descarta; antes sigue viva."""
    reloj = Reloj()
    almacen = AlmacenSesiones(lambda: Sesion(semilla=42), reloj=reloj)
    token, entrada, _ = almacen.obtener(None)
    reloj.t += 29 * 60
    assert almacen.obtener(token)[1] is entrada
    reloj.t += 30 * 60 + 1
    nuevo, otra, nueva = almacen.obtener(token)
    assert nueva and nuevo != token and otra is not entrada
    assert len(almacen) == 1


def test_descarte_lru_al_llenarse():
    """Con el almacén lleno se descarta la sesión usada hace más tiempo."""
    reloj = Reloj()
    almacen = AlmacenSesiones(lambda: Sesion(semilla=42), max_sesiones=3, reloj=reloj)
    a, b, c = (almacen.obtener(None)[0] for _ in range(3))
    reloj.t += 1
    almacen.obtener(a)  # a pasa a ser la más reciente; b es la más vieja.
    d = almacen.obtener(None)[0]
    assert len(almacen) == 3
    assert not almacen.obtener(a)[2] and not almacen.obtener(c)[2] and not almacen.obtener(d)[2]
    assert almacen.obtener(b)[2]  # b fue descartada: vuelve como sesión nueva.


def test_maximo_por_defecto_es_30():
    """Sin argumentos el almacén guarda como máximo 30 sesiones."""
    almacen = AlmacenSesiones(lambda: Sesion(semilla=42))
    for _ in range(35):
        almacen.obtener(None)
    assert len(almacen) == 30


def test_almacen_seguro_para_hilos():
    """Muchos hilos creando y usando sesiones a la vez no rompen el máximo ni fallan."""
    almacen = AlmacenSesiones(lambda: Sesion(semilla=42), max_sesiones=5)
    errores: list[BaseException] = []

    def trabajar():
        try:
            token = almacen.obtener(None)[0]
            for _ in range(5):
                token = almacen.obtener(token)[0]
        except BaseException as exc:  # noqa: BLE001 - se reporta abajo
            errores.append(exc)

    hilos = [threading.Thread(target=trabajar) for _ in range(20)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert not errores and len(almacen) <= 5


# --- Cupos del chat ----------------------------------------------------------------------


def test_cupo_por_sesion_responde_429_y_lo_demas_sigue():
    """Pasado el cupo de la sesión: 429 con aviso en español; paso, mover y mapa siguen."""
    p = Panel(AlmacenSesiones(lambda: Sesion(semilla=42, cliente=cliente_que_responde(5),
                                             config=ConfigLLM())),
              LimitePreguntas(max_sesion=2, max_hora=0))
    try:
        a = token_de(p.pedir("/")[2])
        for _ in range(2):
            assert p.pedir("/api/preguntar", {"pregunta": "¿Dónde está?"}, cookie=a)[0] == 200
        codigo, cuerpo, _ = p.pedir("/api/preguntar", {"pregunta": "¿Y ahora?"}, cookie=a)
        assert codigo == 429
        assert "máximo de 2 preguntas" in cuerpo["error"] and "siguen funcionando" in cuerpo["error"]
        assert cuerpo["estado"]["tick"] == 0
        assert p.pedir("/api/paso", {}, cookie=a)[0] == 200
        assert p.pedir("/api/mover", {"direccion": "arriba"}, cookie=a)[0] == 200
        assert p.pedir("/api/mapa", cookie=a)[0] == 200
        # Reiniciar la partida no reinicia el cupo.
        p.pedir("/api/reiniciar", {"semilla": 7}, cookie=a)
        assert p.pedir("/api/preguntar", {"pregunta": "¿Y ahora?"}, cookie=a)[0] == 429
        # Otro visitante tiene su propio cupo.
        b = token_de(p.pedir("/")[2])
        assert p.pedir("/api/preguntar", {"pregunta": "¿Dónde está?"}, cookie=b)[0] == 200
    finally:
        p.cerrar()


def test_cupo_por_hora_de_todo_el_servidor():
    """El cupo por hora cuenta las preguntas de todos los visitantes y se libera a la hora."""
    reloj = Reloj()
    limite = LimitePreguntas(max_sesion=0, max_hora=3, reloj=reloj)
    entradas = [Entrada(Sesion(semilla=42), 0.0) for _ in range(4)]
    assert [limite.reservar(e) for e in entradas[:3]] == [None, None, None]
    aviso = limite.reservar(entradas[3])
    assert aviso is not None and "última hora" in aviso
    reloj.t += 3599
    assert limite.reservar(entradas[3]) is not None
    reloj.t += 1
    assert limite.reservar(entradas[3]) is None


def test_cupo_por_hora_en_el_servidor():
    """El 429 del cupo por hora llega al navegador con el estado de la partida."""
    p = Panel(AlmacenSesiones(lambda: Sesion(semilla=42, cliente=cliente_que_responde(5),
                                             config=ConfigLLM())),
              LimitePreguntas(max_sesion=0, max_hora=1))
    try:
        a = token_de(p.pedir("/")[2])
        b = token_de(p.pedir("/")[2])
        assert p.pedir("/api/preguntar", {"pregunta": "Hola"}, cookie=a)[0] == 200
        codigo, cuerpo, _ = p.pedir("/api/preguntar", {"pregunta": "Hola"}, cookie=b)
        assert codigo == 429 and "última hora" in cuerpo["error"] and "estado" in cuerpo
    finally:
        p.cerrar()


def test_pregunta_vacia_no_gasta_cupo():
    """Una pregunta inválida responde 409 y no cuenta para el cupo."""
    p = Panel(AlmacenSesiones(lambda: Sesion(semilla=42, cliente=cliente_que_responde(2),
                                             config=ConfigLLM())),
              LimitePreguntas(max_sesion=1, max_hora=0))
    try:
        a = token_de(p.pedir("/")[2])
        assert p.pedir("/api/preguntar", {"pregunta": "   "}, cookie=a)[0] == 409
        assert p.pedir("/api/preguntar", {"pregunta": "x" * 501}, cookie=a)[0] == 409
        assert p.pedir("/api/preguntar", {"pregunta": "Hola"}, cookie=a)[0] == 200
    finally:
        p.cerrar()


def test_cupos_desde_el_entorno(monkeypatch):
    """XQ_PANEL_MAX_SESION y XQ_PANEL_MAX_HORA; 20 y 60 por defecto; 0 desactiva."""
    assert (LimitePreguntas.desde_entorno().max_sesion, LimitePreguntas.desde_entorno().max_hora) == (20, 60)
    monkeypatch.setenv("XQ_PANEL_MAX_SESION", "5")
    monkeypatch.setenv("XQ_PANEL_MAX_HORA", "0")
    limite = LimitePreguntas.desde_entorno()
    assert (limite.max_sesion, limite.max_hora) == (5, 0)
    entrada = Entrada(Sesion(semilla=42), 0.0)
    assert all(limite.reservar(entrada) is None for _ in range(5))
    with pytest.raises(ValueError, match="XQ_PANEL_MAX_HORA"):
        leer_limite("XQ_PANEL_MAX_HORA", 60, {"XQ_PANEL_MAX_HORA": "-1"})
    with pytest.raises(ValueError):
        leer_limite("X", 60, {"X": "muchas"})


# --- /salud, puerto y registros ---------------------------------------------------------


def test_salud(panel):
    """GET /salud responde {"ok": true} sin crear sesión."""
    codigo, cuerpo, galleta = panel.pedir("/salud")
    assert codigo == 200 and cuerpo == {"ok": True} and galleta is None


def test_puerto_desde_port():
    """--puerto gana; si no está, PORT; si no, 8000. PORT inválido es un error."""
    assert leer_argumentos([], {}).puerto == 8000
    assert leer_argumentos([], {"PORT": "8123"}).puerto == 8123
    assert leer_argumentos(["--puerto", "9000"], {"PORT": "8123"}).puerto == 9000
    with pytest.raises(SystemExit):
        leer_argumentos([], {"PORT": "ochenta"})


def test_sin_opcion_para_cambiar_la_direccion():
    """El comando no tiene --host: el panel siempre escucha en 127.0.0.1."""
    with pytest.raises(SystemExit):
        leer_argumentos(["--host", "0.0.0.0"], {})
    srv = crear_servidor(AlmacenSesiones(lambda: Sesion(semilla=42)), puerto=0)
    try:
        assert srv.server_address[0] == "127.0.0.1"
    finally:
        srv.server_close()


def test_ni_respuestas_ni_terminal_muestran_la_clave(capfd):
    """Con un error del modelo que repite la clave, nada de lo que sale la muestra."""

    def lanzar(**_):
        raise RuntimeError(f"Clave inválida: {CLAVE_FALSA}")

    def cliente_que_falla() -> ClienteFalso:
        cliente = ClienteFalso([])
        cliente.chat.completions.create = lanzar
        return cliente

    p = Panel(AlmacenSesiones(lambda: Sesion(semilla=42, cliente=cliente_que_falla(),
                                             config=ConfigLLM())),
              LimitePreguntas(max_sesion=1, max_hora=0))
    try:
        a = token_de(p.pedir("/")[2])
        codigo, cuerpo, _ = p.pedir("/api/preguntar", {"pregunta": "Hola"}, cookie=a)
        assert codigo == 200 and "RuntimeError" in cuerpo["error"]
        assert p.pedir("/api/preguntar", {"pregunta": "Hola"}, cookie=a)[0] == 429
        p.pedir("/api/estado", cookie=a)
        p.pedir("/salud")
        p.pedir("/no-existe")
    finally:
        p.cerrar()  # Revisa cuerpos y cabeceras.
    salida = capfd.readouterr()
    assert CLAVE_FALSA not in salida.out and CLAVE_FALSA not in salida.err


# --- deploy/ -----------------------------------------------------------------------------


def test_unidad_systemd():
    """La unidad corre como xq, desde /opt/xenomorfo-q, con su archivo de variables."""
    unidad = (DEPLOY / "xenomorfo-q.service").read_text(encoding="utf-8")
    for linea in ("User=xq", "WorkingDirectory=/opt/xenomorfo-q",
                  "EnvironmentFile=/etc/xenomorfo-q.env",
                  "ExecStart=/opt/xenomorfo-q/.venv/bin/python -m panel --puerto 8000",
                  "Restart=always"):
        assert linea in unidad.splitlines()


def test_caddyfile_plantilla():
    """Usuario y contraseña en todo salvo /salud, proxy a 127.0.0.1:8000 y cabeceras."""
    caddy = (DEPLOY / "Caddyfile.plantilla").read_text(encoding="utf-8")
    sin_comentarios = "\n".join(l for l in caddy.splitlines() if not l.lstrip().startswith("#"))
    assert "{$XQ_DOMINIO} {" in sin_comentarios
    assert "@protegido not path /salud" in sin_comentarios
    assert "basic_auth @protegido" in sin_comentarios
    assert "{$XQ_USUARIO} {$XQ_HASH}" in sin_comentarios
    assert "reverse_proxy 127.0.0.1:8000" in sin_comentarios
    for cabecera in ("Strict-Transport-Security", "X-Content-Type-Options", "X-Frame-Options",
                     "Referrer-Policy", "Content-Security-Policy"):
        assert cabecera in sin_comentarios


def test_plantilla_de_variables_vacia():
    """La plantilla de /etc/xenomorfo-q.env no trae valores."""
    for linea in (DEPLOY / "xenomorfo-q.env.plantilla").read_text(encoding="utf-8").splitlines():
        if linea and not linea.startswith("#"):
            assert linea.endswith("="), linea


def test_instalar_guarda_solo_el_hash():
    """El script lee la contraseña sin mostrarla y la pasa por la entrada estándar."""
    script = (DEPLOY / "instalar.sh").read_text(encoding="utf-8")
    assert "read -r -s" in script and "| caddy hash-password" in script
    assert "--plaintext" not in script
    assert "install -m 600 -o root -g" in script
    assert "cat $ARCHIVO_ENV" not in script and 'cat "$ARCHIVO_ENV"' not in script


@pytest.mark.parametrize("script", ["instalar.sh", "actualizar.sh"])
def test_scripts_bash_validos(script):
    """Sintaxis de bash y, si está instalado, shellcheck sin avisos."""
    ruta = DEPLOY / script
    assert subprocess.run(["bash", "-n", str(ruta)], capture_output=True).returncode == 0
    if shutil.which("shellcheck") is None:
        pytest.skip("shellcheck no está instalado")
    resultado = subprocess.run(["shellcheck", str(ruta)], capture_output=True, text=True)
    assert resultado.returncode == 0, resultado.stdout
