"""Cada tela assiste o jogo que escolheu, e o evento vai para o jogo certo.

Cobre o que quebrou: o seletor de jogo nao trocava nada porque o servidor rodava
um jogo so, e o client desenhava sempre o estado do servidor.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))          # _harness
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # projeto

from _harness import PORT, PROJECT, check, finish, run_server, server_log  # noqa: E402
import asyncio  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import subprocess  # noqa: E402
import urllib.request  # noqa: E402


async def client(qs="", comandos=None, segundos=4.0):
    """Abre uma conexao e coleta tudo que chegar."""
    import websockets

    async with websockets.connect(f"ws://127.0.0.1:{PORT}/{qs}") as ws:
        primeiro = json.loads(await asyncio.wait_for(ws.recv(), 5))
        for mensagem in comandos or []:
            await ws.send(json.dumps(mensagem))
        estados, eventos = [], []
        deadline = asyncio.get_running_loop().time() + segundos
        while asyncio.get_running_loop().time() < deadline:
            try:
                payload = json.loads(await asyncio.wait_for(ws.recv(), 2))
            except asyncio.TimeoutError:
                break
            if payload.get("type") == "state":
                estados.append(payload)
            elif payload.get("type") == "event":
                eventos.append(payload)
        return primeiro, estados, eventos


with run_server() as server:
    async def cenario_duas_telas():
        # tela 1 assiste corrida, tela 2 assiste duelo
        t1, e1, v1 = await client("?game=corrida")
        t2, e2, v2 = await client("?game=duelo")
        return t1, t2, e1, e2, v1 + v2

    t_corrida, t_duelo, estados_corrida, estados_duelo, eventos_corrida = asyncio.run(cenario_duas_telas())

    print("\n== 1. o welcome entrega o jogo pedido ==")
    check("welcome corrida", t_corrida["game"]["type"] == "corrida", str(t_corrida["game"]["type"]))
    check("welcome duelo", t_duelo["game"]["type"] == "duelo", str(t_duelo["game"]["type"]))
    check("lista de jogos no welcome", len(t_corrida.get("games", [])) >= 4, str(t_corrida.get("games")))

    print("\n== 2. cada tela so recebe o estado do seu jogo ==")
    tipos_corrida = {s["game"] for s in estados_corrida}
    tipos_duelo = {s["game"] for s in estados_duelo}
    check("tela da corrida so recebe 'corrida'", tipos_corrida == {"corrida"}, str(tipos_corrida))
    check("tela do duelo so recebe 'duelo'", tipos_duelo == {"duelo"}, str(tipos_duelo))
    check("estado da corrida tem carros", bool(estados_corrida and "cars" in estados_corrida[-1]["state"]))
    check("estado do duelo tem torres", bool(estados_duelo and "towers" in estados_duelo[-1]["state"]))

    print("\n== 3. evento vai para o jogo de quem mandou ==")

    async def evento_no_duelo():
        await client("?game=duelo", comandos=[
            {"type": "event", "event": "comment", "source": "tiktok", "user": "lula_1", "text": "lula"},
        ], segundos=2.5)
        _, _, nada = await client("?game=corrida", segundos=2.0)

    asyncio.run(evento_no_duelo())

    async def confere_torres():
        _, estados, _ = await client("?game=duelo", segundos=2.0)
        return estados[-1]["state"]["towers"] if estados else []

    torres = asyncio.run(confere_torres())
    check("comentario criou bloco no duelo", sum(t["height"] for t in torres) >= 1,
          str([t["height"] for t in torres]))

    print("\n== 4. troca de jogo em tempo real ==")

    async def troca():
        t, estados, _ = await client("?game=corrida", comandos=[
            {"type": "watch", "game": "pipa"},
        ], segundos=3.0)
        return t, estados

    t_inicial, estados_troca = asyncio.run(troca())
    tipos_depois = {s["game"] for s in estados_troca}
    check("welcome continua corrida", t_inicial["game"]["type"] == "corrida")
    check("depois do watch chega estado da pipa", "pipa" in tipos_depois, str(tipos_depois))

    print("\n== 5. jogo inexistente ==")

    async def invalido():
        _, estados, _ = await client("?game=nao_existe", comandos=[
            {"type": "watch", "game": "tampouco_existe"},
        ], segundos=2.0)
        return estados

    estados_invalido = asyncio.run(invalido())
    tipos_invalido = {s["game"] for s in estados_invalido}
    check("cai no jogo padrao quando o nome nao existe", tipos_invalido == {"corrida"}, str(tipos_invalido))

    print("\n== 6. follow / share criam carro ==")

    async def follow_e_share():
        await client("?game=corrida", comandos=[
            {"type": "event", "event": "follow", "source": "tiktok", "user": "quem_seguiu"},
            {"type": "event", "event": "share", "source": "tiktok", "user": "quem_compartilhou"},
        ], segundos=2.5)

    asyncio.run(follow_e_share())

    async def carros():
        _, estados, _ = await client("?game=corrida", segundos=2.0)
        return estados[-1]["state"]["cars"] if estados else []

    lista = asyncio.run(carros())
    nomes = {c["user"] for c in lista}
    check("follow virou carro", "quem_seguiu" in nomes, str(sorted(nomes)))
    check("share virou carro", "quem_compartilhou" in nomes, str(sorted(nomes)))

    print("\n== 7. /health com todos os jogos ==")
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=5) as resp:
        health = json.loads(resp.read().decode())
    check("health lista os 4 jogos", set(health.get("games", {})) == {"corrida", "duelo", "pipa", "platformer"},
          str(sorted(health.get("games", {}))))
    check("health mantem as chaves antigas", all(k in health for k in ("ok", "game", "clients", "tick")))

    log = server_log(server)

erros = [l for l in log.splitlines() if "ERROR" in l or "Traceback" in l]
check("servidor sem erro", not erros, "; ".join(erros[:2]))
print("\n--- ultimas linhas do servidor ---")
print("\n".join(log.splitlines()[-5:]))

finish()