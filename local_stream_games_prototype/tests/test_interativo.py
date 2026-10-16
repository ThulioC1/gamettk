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

LINHAS = ("comento vou ganhar\npresente Galaxy\nlike\nfollow\njogo JUMP\nMOVE_LEFT\n"
          "carro gol\ngol\ncarro xre 300\nXRE 300\ncarro naoexiste\nquit\n")


def observe(seconds: float) -> list:
    """Conecta como viewer e coleta os eventos que o simulador mandar."""
    import websockets

    async def run():
        vistos = []
        async with websockets.connect(f"ws://127.0.0.1:{PORT}/?game=corrida") as ws:
            await asyncio.wait_for(ws.recv(), 5)
            deadline = asyncio.get_event_loop().time() + seconds
            while asyncio.get_event_loop().time() < deadline:
                try:
                    payload = json.loads(await asyncio.wait_for(ws.recv(), 2))
                except asyncio.TimeoutError:
                    break
                if payload.get("type") == "state":
                    vistos.append(("estado", payload["state"]))
                elif payload.get("type") == "event":
                    evento = payload["event"]
                    vistos.append((evento["event"], evento.get("text", ""),
                                   [n.get("message") for n in payload.get("notices") or [] if n.get("message")]))
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
check("carro inexistente avisa", "nao achei no catalogo" in saida)
check("nao respondeu 'nao entendi' para nome de carro", "nao entendi" not in saida,
      [l for l in saida.splitlines() if "nao entendi" in l][:2])

comentarios = [e for e in eventos if e[0] == "comment"]
textos = [e[1] for e in comentarios]
check("'carro gol' e o atalho 'gol' viraram comentario", "gol" in textos, str(textos))
check("'carro xre 300' e o atalho 'XRE 300' viraram comentario",
      any("xre 300" in t.lower() for t in textos), str(textos))

avisos = [m for e in comentarios for m in e[2]]
check("jogo respondeu que entrou com o carro", any("ENTROU COM" in m for m in avisos), str(avisos[:2]))
check("jogo confirmou a troca de carro", any("TROCOU PARA" in m for m in avisos), str(avisos[:4]))

tipos = [e[0] for e in eventos]
for esperado in ("comment", "gift", "like", "follow", "command"):
    check(f"evento '{esperado}' chegou ao servidor", esperado in tipos, str(sorted(set(tipos))))

comandos = [e for e in eventos if e[0] == "command"]
check("'jogo JUMP' virou comando JUMP", len(comandos) >= 2, f"{len(comandos)} comandos")

# o console precisa devolver resposta: sem isso da a impressao de que nao aconteceu nada
check("console ecoa o que enviou", "comentario enviado" in saida)
check("console mostra a resposta do jogo (>>)", ">>" in saida)

estado_final = [e for e in eventos if e[0] == "estado"]
carros = estado_final[-1][1]["cars"] if estado_final else []
check("o carro do console entrou na pista", any(c["user"] == "voce" for c in carros),
      str([(c["user"], c["vehicle"]) for c in carros]))
check("veiculo final e o XRE 300", any(c["user"] == "voce" and c["vehicle"] == "xre300" for c in carros),
      str([(c["user"], c["vehicle"]) for c in carros]))
check("carro tem faixa e placa com km/h",
      all("lane" in c and "kmh" in c for c in carros), str(carros[0].keys() if carros else []))

finish()