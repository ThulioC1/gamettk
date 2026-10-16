"""Roda toda a suite de testes.

    python3 tests/run_all.py            # tudo
    python3 tests/run_all.py duelo pipa  # so alguns
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent

SUITE = [
    ("gifts", "test_gifts.py"),
    ("corrida", "test_corrida.py"),
    ("duelo", "test_duelo.py"),
    ("pipa", "test_pipa.py"),
    ("token", "test_token.py"),
    ("interativo", "test_interativo.py"),
    ("simulador", "test_simulador.py"),
]


def main() -> int:
    wanted = set(sys.argv[1:])
    selected = [(name, path) for name, path in SUITE if not wanted or name in wanted]

    results = []
    for name, script in selected:
        print(f"\n{'=' * 60}\n== {name}  ({script})\n{'=' * 60}")
        started = time.monotonic()
        done = subprocess.run([sys.executable, str(TESTS_DIR / script)], cwd=str(TESTS_DIR))
        results.append((name, done.returncode, time.monotonic() - started))

    print(f"\n{'=' * 60}\nRESUMO\n{'=' * 60}")
    for name, code, seconds in results:
        print(f"  {'PASS' if code == 0 else 'FAIL'}  {name:<12} {seconds:5.1f}s")
    failed = [name for name, code, _ in results if code != 0]
    print("\n" + ("TUDO VERDE" if not failed else f"FALHARAM: {', '.join(failed)}"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
