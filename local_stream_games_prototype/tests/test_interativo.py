"""Regressao do modo interativo do simulador (stdin via pipe).

O bug que motivou este teste so aparecia digitando no terminal:
`asyncio.create_task(loop.run_in_executor(...))` -> Future nao e coroutine.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))          # _harness
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # projeto

from _harness import PORT, PROJECT, check, finish, run_server, server_log  # noqa: E402
import asyncio  # noqa: E402
import json  # noqa: E402
import subprocess  # noqa: E402

LINHAS = "comento vou ganhar\npresente Galaxy\nlike\nfollow\njogo JUMP\nMOVE_LEFT\nquit\n"


def observe(seconds: float) -> list:
    """Conecta como viewer e coleta os eventos que o simulador mandar."""
    import websockets

    async def run():
        vistos = []
        async with websockets.connect(f"ws://127.0.0.1:{PORT}") as ws:
            await asyncio.wait_for(ws.recv(), 5)
            deadline = asyncio.get_event_loop().time() + seconds
            while asyncio.get_event_loop().time() < deadline:
                try:
                    payload = json.loads(await asyncio.wait_for(ws.recv(), 2))
                except asyncio.TimeoutError:
                    break
                if payload.get("type") == "event":
                    vistos.append((payload["event"]["event"], payload["event"].get("gift", "")))
        return vistos

    return asyncio.run(run())


with run_server("--game", "corrida") as server:
    async def pipeline():
        return await asyncio.to_thread(observe, 8.0)

    async def dispara():
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "simulator/simulator.py",
            cwd=str(PROJECT),
            env={**dict(__import__("os").environ), "PORT": PORT},
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        saida, _ = await asyncio.wait_for(proc.communicate(LINHAS.encode()), 20)
        return proc.returncode, saida.decode(errors="replace")

    async def main():
        observador = asyncio.create_task(pipeline())
        await asyncio.sleep(0.5)
        codigo, saida = await dispara()
        eventos = await asyncio.wait_for(observador, 15)
        return codigo, saida, eventos

    codigo, saida, eventos = asyncio.run(main())

print("\n== modo interativo do simulador ==")
check("nao Raising TypeError", "TypeError" not in saida, saida.strip().splitlines()[-1] if "TypeError" in saida else "")
check("sem traceback", "Traceback" not in saida)
check("terminou com codigo 0", codigo == 0, f"codigo={codigo}")
check("mostrou o prompt 'evento>'", "evento>" in saida)
check("aceitou 'quit'", codigo == 0)

tipos = [tipo for tipo, _ in eventos]
for esperado in ("comment", "gift", "like", "follow", "command"):
    check(f"evento '{esperado}' chegou ao servidor", esperado in tipos, str(tipos))

comandos = [e for e in eventos if e[0] == "command"]
check("'jogo JUMP' virou comando JUMP", len(comandos) >= 2, f"{len(comandos)} comandos")
presentes = [g for tipo, g in eventos if tipo == "gift"]
check("'presente Galaxy' mandou o nome do presente", "Galaxy" in presentes, str(presentes))

finish()