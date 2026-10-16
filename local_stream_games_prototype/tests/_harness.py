"""Apoio comum aos testes: porta livre e servidor em background.

Uso:
    from _harness import PORT, check, run_server
"""
from __future__ import annotations

import contextlib
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterator, List, Optional

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))


def free_port() -> str:
    """Porta livre agora (evita conflito com outro processo da maquina)."""
    with contextlib.closing(socket.socket()) as sock:
        sock.bind(("127.0.0.1", 0))
        return str(sock.getsockname()[1])


PORT = free_port()

failures: List[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    """Registra e imprime o resultado de uma verificacao."""
    print(("  OK  " if condition else " FAIL ") + name + (f" -> {detail}" if detail else ""))
    if not condition:
        failures.append(name)


def finish() -> None:
    """Fecha o teste: imprime o veredito e sai com codigo apropriado."""
    print("\n" + ("TODOS OS TESTES PASSARAM" if not failures else f"FALHAS: {failures}"))
    sys.exit(1 if failures else 0)


@contextlib.contextmanager
def run_server(*args: str, env_extra: Optional[dict] = None, wait: float = 2.5) -> Iterator[subprocess.Popen]:
    """Sobe `server/server.py` com porta livre e garante o encerramento."""
    env = {**dict(__import__("os").environ), "PORT": PORT, **(env_extra or {})}
    process = subprocess.Popen(
        [sys.executable, "server/server.py", *args],
        cwd=str(PROJECT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    time.sleep(wait)
    try:
        yield process
    finally:
        process.terminate()
        with contextlib.suppress(subprocess.TimeoutExpired):
            process.wait(timeout=6)


def server_log(process: subprocess.Popen) -> str:
    """Le a saida do servidor (use dentro do with, apos terminate)."""
    with contextlib.suppress(subprocess.TimeoutExpired):
        return process.communicate(timeout=6)[0] or ""
    return ""
