"""Testes do nucleo + jogo da corrida (suite do launcher)."""

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

from server.games import GAMES, build  # noqa: E402
from shared import gifts as gift_lib  # noqa: E402

print("\n== A. classificacao de presentes ==")
for name, expected in [
    ("Rose", gift_lib.NITRO), ("Rosa", gift_lib.NITRO), ("heart", gift_lib.NITRO),
    ("Galaxy", gift_lib.TURBO), ("universo", gift_lib.TURBO), ("TikTok", gift_lib.TURBO),
    ("Oil", gift_lib.OIL), ("Banana", gift_lib.OIL), ("oleo", gift_lib.OIL),
    ("Presente Desconhecido 999", gift_lib.NITRO), ("", gift_lib.NITRO), (None, gift_lib.NITRO),
]:
    got = gift_lib.classify(name)
    check(f"classify({name!r}) == {expected}", got == expected, f"got={got}")

print("\n== B. Corrida: regras do jogo ==")
race = build("corrida")
check("tipo do jogo", race.type == "corrida")

notices = race.handle_event({"event": "comment", "user": "ana", "text": "oi"})
check("primeiro comentario cria carro", len(race.cars) == 1 and notices[0]["kind"] == "join")
check("carro do dono registrado", race.cars[0].user == "ana")

for i in range(5):
    race.handle_event({"event": "comment", "user": f"user{i}", "text": "oi"})
check("cada viewer novo cria um carro", len(race.cars) == 6)

before = race.cars[0].boost
race.handle_event({"event": "comment", "user": "ana", "text": "vai"})
check("comentar de novo acelera o proprio carro", race.cars[0].boost > 0 and race.cars[0].boost >= before)
check("comentar de novo nao cria carro", len(race.cars) == 6)

race.handle_event({"event": "gift", "user": "ana", "gift": "Galaxy", "count": 3})
check("presente turbo da impulso", race.cars[0].boost > 0 and race.cars[0].points > 0)

race.cars[0].dist = 400
race.handle_event({"event": "gift", "user": "ana", "gift": "Oil", "count": 1})
check("oleio deixa mancha na pista", len(race.oils) == 1 and race.oils[0]["dist"] < 400)

race.reset()
check("reset limpa oleo e zera distancias", not race.oils and all(car.dist == 0 for car in race.cars))
check("reset preserva o elenco", len(race.cars) == 6)

print("\n== C. Corrida: quem chega primeiro vence ==")
race.reset()
race.cars[0].dist = race.snapshot()["trackLength"] - 1
winner = []
for _ in range(10):
    winner = [e for e in race.update() if e["kind"] == "winner"]
    if winner:
        break
check("vitoria detectada", bool(winner), winner[0]["message"] if winner else "ninguem chegou")
check("colocacao do campeao = 1", race.cars[0].place == 1 and race.cars[0].finished_at is not None)

restarted = []
for _ in range(600):
    restarted = [e for e in race.update() if e["kind"] == "restart"]
    if restarted:
        break
check("corrida reinicia sozinha", bool(restarted))
check("todos voltam ao inicio", all(car.dist == 0 for car in race.cars))

print("\n== D. derrapagem no oleo ==")
race.reset()
race.cars[0].dist = 100
race.handle_event({"event": "gift", "user": "ana", "gift": "Oil"})
race.cars[0].dist = race.oils[0]["dist"]
spill = [e for e in race.update() if e["kind"] == "spill"]
check("carro derrapa e trava", bool(spill) and race.cars[0].spin_left > 0)
check("mancha consumida no derrape", len(race.oils) == 0)

print("\n== E. teto de carros ==")
race = build("corrida")
for i in range(race.describe()["maxCars"] + 12):
    race.handle_event({"event": "comment", "user": f"u{i}", "text": "oi"})
check("pista nunca passa do limite", len(race.cars) <= race.describe()["maxCars"], f"{len(race.cars)} carros")

print("\n== F. platformer continua funcionando ==")
plat = build("platformer")
plat.handle_event({"event": "command", "command": "MOVE_RIGHT"})
for _ in range(60):
    plat.update()
check("platformer andou", plat.player_x > 100, f"x={plat.player_x:.0f}")
check("platformer ignora evento de live", plat.handle_event({"event": "comment", "text": "oi"}) == [])
check("games registrados", set(GAMES) == {"corrida", "duelo", "pipa", "platformer"}, str(sorted(GAMES)))

print("\n== G. servidor: HTTP, /games e WebSocket ==")
env = {**os.environ, "PORT": PORT}
server = subprocess.Popen(
    [sys.executable, "server/server.py"], cwd=str(PROJECT), env=env,
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
)
time.sleep(2.5)

async def ws_flow():
    import websockets

    result = {"welcome": None, "events": [], "notices": [], "cars": 0, "oil": 0, "spill": False, "status": None}
    async with websockets.connect(f"ws://127.0.0.1:{PORT}") as ws:
        hello = json.loads(await asyncio.wait_for(ws.recv(), 5))
        result["welcome"] = hello.get("game", {}).get("type")

        for user in ["ana", "br", "carla", "duda"]:
            await ws.send(json.dumps({"type": "event", "event": "comment", "source": "tiktok",
                                     "user": user, "text": "oi live"}))
        await ws.send(json.dumps({"type": "event", "event": "gift", "source": "tiktok",
                                 "user": "ana", "gift": "Galaxy", "count": 2}))
        await ws.send(json.dumps({"type": "event", "event": "gift", "source": "tiktok",
                                 "user": "ana", "gift": "Oil", "count": 1}))
        await ws.send(json.dumps({"type": "event", "event": "comando_invalido", "source": "tiktok", "user": "x"}))

        deadline = time.time() + 6
        while time.time() < deadline:
            try:
                payload = json.loads(await asyncio.wait_for(ws.recv(), 3))
            except asyncio.TimeoutError:
                break
            kind = payload.get("type")
            if kind == "state":
                result["cars"] = len(payload["state"]["cars"])
                result["oil"] = max(result["oil"], len(payload["state"]["oils"]))
                if result["cars"] >= 4 and (result["oil"] >= 1 or result["spill"]):
                    break
            elif kind == "event":
                result["events"].append(payload["event"]["event"])
                result["notices"] += payload.get("notices", [])
            elif kind == "game_event":
                if payload.get("kind") == "spill":
                    result["spill"] = True
            elif kind == "status":
                result["status"] = payload
    return result

try:
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=5) as resp:
        html = resp.read().decode()
    check("HTTP serve o launcher", "<canvas" in html and "type=\"module\"" in html)
except Exception as err:  # noqa: BLE001
    check("HTTP serve o launcher", False, str(err))

try:
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/games", timeout=5) as resp:
        games = json.loads(resp.read().decode())
    check("/games lista os jogos", {g["type"] for g in games["games"]} == {"corrida", "duelo", "pipa", "platformer"}, str(sorted(g["type"] for g in games["games"])))
except Exception as err:  # noqa: BLE001
    check("/games lista os jogos", False, str(err))

try:
    for asset in ("client.js", "style.css", "renderers/corrida.js", "renderers/platformer.js"):
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/{asset}", timeout=5) as resp:
            body = resp.read().decode()
        check(f"servido: {asset}", len(body) > 50)
except Exception as err:  # noqa: BLE001
    check("assets do client", False, str(err))

try:
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/../server/server.py", timeout=5) as resp:
        check("path traversal bloqueado", False, "vazou conteudo")
except urllib.error.HTTPError as err:
    check("path traversal bloqueado", err.code == 404, f"HTTP {err.code}")

try:
    result = asyncio.run(ws_flow())
    check("welcome traz o jogo", result["welcome"] == "corrida", str(result["welcome"]))
    check("4 comentarios criam 4 carros", result["cars"] >= 4, f"{result['cars']} carros")
    check("presente de oleo agiu no jogo (mancha ou derrape)", result["oil"] >= 1 or result["spill"],
          f"manchas={result['oil']} derrape={result['spill']}")
    check("evento invalido foi ignorado", "comando_invalido" not in result["events"])
    check("avisos voltaram para o HUD", any(n.get("message") for n in result["notices"]),
          "; ".join(str(n.get("message")) for n in result["notices"][:3]))
except Exception as err:  # noqa: BLE001
    check("fluxo WebSocket", False, repr(err))
finally:
    server.terminate()
    try:
        log = server.communicate(timeout=6)[0]
    except subprocess.TimeoutExpired:
        server.kill()
        log = server.communicate()[0]

print("\n--- log do servidor ---")
print((log or "").strip()[-1200:])
finish()
