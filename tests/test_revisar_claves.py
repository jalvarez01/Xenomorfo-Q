"""Pruebas del hook pre-commit que bloquea claves de API (scripts/revisar_claves.sh).

Cada prueba crea un repositorio git temporal con el hook instalado. Los valores con forma
de clave se arman en tiempo de ejecución, así ningún archivo del repositorio contiene uno.

Tareas relacionadas: guía de desarrollo (claves de API).
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parent.parent / "scripts" / "revisar_claves.sh"

pytestmark = pytest.mark.skipif(shutil.which("git") is None or shutil.which("sh") is None,
                                reason="hace falta git y sh")


def falsa_nvidia() -> str:
    """Valor falso con la forma de una clave de NVIDIA, armado en tiempo de ejecución."""
    return "nv" + "api-" + "Prueba" * 6


def falsa_openai() -> str:
    """Valor falso con la forma de una clave de OpenAI, armado en tiempo de ejecución."""
    return "s" + "k-" + "x1" * 15


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    """Corre git en el repositorio temporal, con el hook del repositorio y sin config global."""
    return subprocess.run(["git", "-c", "core.hooksPath=.git/hooks", *args], cwd=repo,
                          capture_output=True, text=True,
                          env={"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
                               "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1",
                               "HOME": str(repo)})


@pytest.fixture
def repo(tmp_path) -> Path:
    """Repositorio git vacío con el hook instalado como pre-commit."""
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.name", "Prueba")
    git(tmp_path, "config", "user.email", "prueba@example.com")
    destino = tmp_path / ".git" / "hooks" / "pre-commit"
    shutil.copy(HOOK, destino)
    destino.chmod(0o755)
    (tmp_path / "LEEME.txt").write_text("hola\n", encoding="utf-8")
    git(tmp_path, "add", "LEEME.txt")
    assert git(tmp_path, "commit", "-q", "-m", "inicio").returncode == 0
    return tmp_path


@pytest.mark.parametrize("valor", [falsa_nvidia, falsa_openai])
def test_bloquea_un_valor_con_forma_de_clave(repo, valor):
    """Un archivo que agrega algo con forma de clave bloquea el commit y se nombra sin mostrar el valor."""
    secreto = valor()
    (repo / ".env.example").write_text(f"CLAVE={secreto}\n", encoding="utf-8")
    git(repo, "add", ".env.example")
    r = git(repo, "commit", "-q", "-m", "agrega plantilla")
    assert r.returncode != 0
    assert ".env.example" in r.stderr and "Commit bloqueado" in r.stderr
    assert secreto not in r.stdout + r.stderr
    assert git(repo, "rev-list", "--count", "HEAD").stdout.strip() == "1"


def test_deja_pasar_cambios_sin_claves(repo):
    """Una plantilla con la clave vacía y texto normal se puede commitear."""
    (repo / ".env.example").write_text("OPENAI_API_KEY=\nXQ_MODELO=\n", encoding="utf-8")
    git(repo, "add", ".env.example")
    assert git(repo, "commit", "-q", "-m", "agrega plantilla vacia").returncode == 0


def test_solo_revisa_lo_agregado(repo):
    """Borrar una línea con forma de clave no bloquea: solo cuentan las líneas agregadas."""
    (repo / "viejo.txt").write_text(f"{falsa_nvidia()}\n", encoding="utf-8")
    git(repo, "add", "viejo.txt")
    assert git(repo, "commit", "-q", "--no-verify", "-m", "estado previo").returncode == 0
    (repo / "viejo.txt").write_text("limpio\n", encoding="utf-8")
    git(repo, "add", "viejo.txt")
    assert git(repo, "commit", "-q", "-m", "limpia").returncode == 0


def test_el_patron_no_se_detecta_a_si_mismo():
    """El script contiene el patrón, pero no algo con forma de clave."""
    import re
    texto = HOOK.read_text(encoding="utf-8")
    assert "nvapi-[A-Za-z0-9]" in texto
    assert re.search(r"nvapi-[A-Za-z0-9]|sk-[A-Za-z0-9]{20,}", texto) is None
