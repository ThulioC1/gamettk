"""Teste do GAME_TOKEN: sem token nao entra evento de live."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))          # _harness
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # projeto

from _harness import PORT, PROJECT, check, finish  # noqa: E402

import asyncio
import json
import os
import subprocess
import time
import urllib.request

TOKEN = "segredo-de-teste-123"

env = {**os.environ, "PORT": PORT, "GAME_TOKEN": TOKEN}
server = subprocess.Popen([sys.executable, "server/server.py", "--game", "corrida"], cwd=str(PROJECT), env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
time.sleep(2.5)

async def try_send(url, label):
    """Envia 1 comentario + 1 presente e diz quantos carros apareceram."""

    import websockets

    cars = 0
    try:
        async with websockets.connect(url) as ws:
            await asyncio.wait_for(ws.recv(), 5)  # welcome
            await ws.send(json.dumps({"type": "event", "event": "comment", "source": "tiktok", "user": "x", "text": "oi"}))
            await ws.send(json.dumps({"type": "event", "event": "gift", "source": "tiktok", "user": "x",
                                      "gift": "Universo TikTok", "count": 1, "value": 44999}))
            await ws.send(json.dumps({"type": "source_status", "source": "tiktok", "connected": True,
                                      "username": "fake"}))
            deadline = time.time() + 2.5
            while time.time() < deadline:
                try:
                    payload = json.loads(await asyncio.wait_for(ws.recv(), 2))
                except asyncio.TimeoutError:
                    break
                if payload.get("type") == "state":
                    cars = max(cars, len(payload["state"]["cars"]))
    except Exception as err:  # noqa: BLE001
        return label, f"erro: {err!r}"
    return label, cars

async def main():
    base = f"ws://127.0.0.1:{PORT}"
    sem = await try_send(base, "sem token")
    errado = await try_send(f"{base}/?token=chute", "token errado")
    certo = await try_send(f"{base}/?token={TOKEN}", "token certo")
    return sem, errado, certo

resultado = asyncio.run(main())
check("conexao sem token NAO injeta evento", resultado[0][1] == 0, str(resultado[0]))
check("token errado NAO injeta evento", resultado[1][1] == 0, str(resultado[1]))
check("token certo injeta evento", resultado[2][1] >= 1, str(resultado[2]))

# o navegador (viewer, sem token) ainda precisa receber o estado
async def viewer_recebe():
    import websockets

    async with websockets.connect(f"ws://127.0.0.1:{PORT}") as ws:
        hello = json.loads(await asyncio.wait_for(ws.recv(), 5))
        for _ in range(40):
            payload = json.loads(await asyncio.wait_for(ws.recv(), 3))
            if payload.get("type") == "state":
                return True, hello["game"]["type"]
    return False, None

ok, tipo = asyncio.run(viewer_recebe())
check("viewer sem token continua vendo o jogo", ok, f"jogo={tipo}")

server.terminate()
try:
    log = server.communicate(timeout=6)[0]
except subprocess.TimeoutExpired:
    server.kill()
    log = server.communicate()[0]

protegido = "sem GAME_TOKEN" in log
check("servidor registrou a tentativa sem token", protegido, "log tem o aviso" if protegido else "sem aviso no log")

print("\n--- ultimas linhas do servidor ---")
print("\n".join((log or "").splitlines()[-5:]))
finish()
