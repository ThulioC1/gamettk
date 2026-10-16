"""Roda toda a suite de testes.

    python3 tests/run_all.py            # tudo
    python3 tests/run_all.py duelo pipa  # so alguns
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent

SUITE = [
    ("config", "test_config.py"),
    ("gifts", "test_gifts.py"),
    ("corrida", "test_corrida.py"),
    ("duelo", "test_duelo.py"),
    ("pipa", "test_pipa.py"),
    ("token", "test_token.py"),
    ("multijogo", "test_multijogo.py"),
    ("interativo", "test_interativo.py"),
    ("simulador", "test_simulador.py"),
    ("referencia", "test_referencia.py"),
]


def roda_render() -> int:
    """Renderers sao JavaScript: rodam em node, se ele existir."""
    node = shutil.which("node")
    if not node:
        print("\n== render (pulado: node nao instalado) ==")
        return 0
    print(f"\n{'=' * 60}\n== render\n{'=' * 60}")
    return subprocess.run([node, str(TESTS_DIR / "render_check.mjs")]).returncode


def main() -> int:
    wanted = set(sys.argv[1:])
    selected = [(name, path) for name, path in SUITE if not wanted or name in wanted]

    results = []
    for name, script in selected:
        print(f"\n{'=' * 60}\n== {name}  ({script})\n{'=' * 60}")
        started = time.monotonic()
        done = subprocess.run([sys.executable, str(TESTS_DIR / script)], cwd=str(TESTS_DIR))
        results.append((name, done.returncode, time.monotonic() - started))

    if not wanted:
        results.append(("render", roda_render(), 0.0))

    print(f"\n{'=' * 60}\nRESUMO\n{'=' * 60}")
    for name, code, seconds in results:
        print(f"  {'PASS' if code == 0 else 'FAIL'}  {name:<12} {seconds:5.1f}s")
    failed = [name for name, code, _ in results if code != 0]
    print("\n" + ("TUDO VERDE" if not failed else f"FALHARAM: {', '.join(failed)}"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
