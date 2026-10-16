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


def carro_de(race, user: str):
    """Carro de um viewer (os carros de casa ficam no inicio da lista)."""
    for car in race.cars:
        if car.user == user and not car.fixed:
            return car
    return None


def larga(race) -> None:
    """Avanca ate a largada (a corrida comeca com contagem regressiva)."""
    for _ in range(3000):
        race.update()
        if race.phase != "countdown":
            race.update()   # o frame do "VALENDO!" ainda nao moveu ninguem
            return

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
check("primeiro comentario cria carro",
      len([c for c in race.cars if not c.fixed]) == 1 and notices[0]["kind"] == "join")
check("carro do dono registrado", carro_de(race, "ana").user == "ana")

for i in range(5):
    race.handle_event({"event": "comment", "user": f"user{i}", "text": "oi"})
check("cada viewer novo cria um carro",
      len([c for c in race.cars if not c.fixed]) == 6, str(len(race.cars)))

ana = carro_de(race, "ana")
before = ana.boost
race.handle_event({"event": "comment", "user": "ana", "text": "vai"})
ana = carro_de(race, "ana")
check("comentar de novo acelera o proprio carro", ana.boost > 0 and ana.boost >= before)
check("comentar de novo nao cria carro", len([c for c in race.cars if not c.fixed]) == 6)

race.handle_event({"event": "gift", "user": "ana", "gift": "Galaxy", "count": 3})
check("presente turbo da impulso", carro_de(race, "ana").boost > 0 and carro_de(race, "ana").points > 0)

race.cars[0].dist = 400
race.handle_event({"event": "gift", "user": "ana", "gift": "Oil", "count": 1})
check("oleio deixa mancha na pista", len(race.oils) == 1 and race.oils[0]["dist"] < 400)

race.reset()
check("reset limpa oleo e zera distancias", not race.oils and all(car.dist < 0 for car in race.cars),
      f"{[round(c.dist) for c in race.cars[:3]]}")
check("reset preserva o elenco", len([c for c in race.cars if not c.fixed]) == 6)
check("reset volta para a contagem", race.phase == "countdown" and race.snapshot()["countdown"] > 0,
      f"{race.phase} {race.snapshot()['countdown']}s")
larga(race)

print("\n== B2. largada: contagem, grid, faixas e veiculos ==")
race = build("corrida")
race.handle_event({"event": "comment", "user": "ana", "text": "tenho um gol"})
race.handle_event({"event": "comment", "user": "br", "text": "vou de moto biz"})
race.handle_event({"event": "comment", "user": "carla", "text": "oi"})
check("veiculo escolhido pela palavra", carro_de(race, "ana").vehicle_name == "Gol",
      carro_de(race, "ana").vehicle_name)
check("moto escolhida pela palavra", carro_de(race, "br").vehicle_name == "Biz",
      carro_de(race, "br").vehicle_name)
check("quem nao pediu carro ganhou um sorteado", carro_de(race, "carla").vehicle_name != "",
      carro_de(race, "carla").vehicle_name)
check("catalogo no describe tem carros e motos",
      len(race.describe()["catalog"]["cars"]) > 5 and len(race.describe()["catalog"]["motos"]) >= 3,
      f"{len(race.describe()['catalog']['cars'])} carros / {len(race.describe()['catalog']['motos'])} motos")

lanes = [car.lane for car in race.cars]
check("carros ficam em faixas diferentes", len(set(lanes)) == len(lanes), str(lanes))
check("grid de largada atras da linha", all(car.dist < 0 for car in race.cars),
      str([round(c.dist) for c in race.cars]))
check("todas as distancias do grid sao distintas", len({car.dist for car in race.cars}) == len(race.cars))

parado = [car.dist for car in race.cars]
for _ in range(120):
    race.update()
check("ninguem anda durante a contagem", [car.dist for car in race.cars] == parado)
check("contagem aparece no snapshot", race.snapshot()["countdown"] > 0, str(race.snapshot()["countdown"]))

valendo = []
for _ in range(3000):
    if race.phase != "countdown":
        break
    valendo += [e for e in race.update() if e["kind"] == "go"]
race.update()   # primeiro frame de corrida: velocidades sao calculadas aqui
check("largou e avisou", bool(valendo), valendo[0]["message"] if valendo else "sem evento 'go'")
check("agora todo mundo tem velocidade", any(car.kmh() > 0 for car in race.cars),
      str([car.kmh() for car in race.cars]))
check("km/h vai no snapshot", all("kmh" in car.to_dict() for car in race.cars))

print("\n== C. Corrida: quem chega primeiro vence ==")
race.reset()
larga(race)
race.cars[0].dist = race.snapshot()["trackLength"] - 1  # primeiro carro: um dos de casa
winner = []
for _ in range(10):
    winner = [e for e in race.update() if e["kind"] == "winner"]
    if winner:
        break
check("vitoria detectada", bool(winner), winner[0]["message"] if winner else "ninguem chegou")
check("colocacao do campeao = 1", race.cars[0].place == 1 and race.cars[0].finished_at is not None)

restarted = []
for _ in range(900):
    restarted = [e for e in race.update() if e["kind"] == "restart"]
    if restarted:
        break
check("corrida reinicia sozinha", bool(restarted))
check("todos voltam ao grid", all(car.dist < 0 for car in race.cars) and race.phase == "countdown",
      f"{race.phase} {[round(c.dist) for c in race.cars[:3]]}")

print("\n== D. derrapagem no oleo ==")
race.reset()
larga(race)
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

print("\n== H. like acelera progressivamente ==")
race = build("corrida")
larga(race)
race.handle_event({"event": "comment", "user": "ana", "text": "oi"})
race.cars = [car for car in race.cars if not car.fixed]  # mede so o carro da ana
ana = race.cars[0]

velocidades = []
for curtidas in (1, 5, 20, 60):
    race.handle_event({"event": "like", "user": "ana", "count": curtidas})
    race.update()
    velocidades.append(ana.kmh())

check("likes somam no contador", ana.likes == 86, str(ana.likes))
check("1 like < 5 likes < 20 likes < 60 likes", velocidades == sorted(velocidades) and len(set(velocidades)) >= 3,
      str(velocidades))
check("o ultimo like e bem mais rapido", velocidades[-1] >= velocidades[0] * 1.4, str(velocidades))
check("impulso dos likes some do snapshot",
      "likeBoost" in ana.to_dict() and "likes" in ana.to_dict(), str(ana.to_dict().get("likeKmh")))

aviso = race.handle_event({"event": "like", "user": "ana", "count": 3})[0]
check("aviso do like diz o efeito em km/h", "km/h" in aviso["message"] and "likes" in aviso["message"],
      aviso["message"])

print("\n== I. dois carros de casa, sempre na pista ==")
race = build("corrida")
nomes = [car.user for car in race.cars if car.fixed]
check("os dois carros fixos existem", nomes == ["Vitinmilgrau", "Narutobebado"], str(nomes))
check("eles tem veiculo proprio", all(car.vehicle for car in race.cars if car.fixed),
      str([(car.user, car.vehicle) for car in race.cars if car.fixed]))
check("um deles e moto", any(car.is_moto for car in race.cars if car.fixed))

for i in range(race.describe()["maxCars"] + 20):
    race.handle_event({"event": "comment", "user": f"cheio{i}", "text": "oi"})
check("carros fixos sobrevivem a pista cheia",
      [car.user for car in race.cars if car.fixed] == ["Vitinmilgrau", "Narutobebado"],
      str([car.user for car in race.cars if car.fixed]))
check("carros fixos nao somem apos o reset",
      len([car for car in race.reset() or race.cars if car.fixed]) == 2)

race.reset()
larga(race)
tem_algum = False
for _ in range(400):
    race.update()
    if any(car.dist > 50 for car in race.cars if car.fixed):
        tem_algum = True
        break
check("eles correm sozinhos com a live vazia", tem_algum,
      str([(car.user, round(car.dist)) for car in race.cars if car.fixed]))

# viewer nunca assume o carro de casa
race.handle_event({"event": "comment", "user": "Vitinmilgrau", "text": "oi"})
check("viewer com o mesmo nome ganha o proprio carro",
      len([car for car in race.cars if car.user == "Vitinmilgrau"]) == 2,
      str([car.user for car in race.cars]))

print("\n== J. vencedor com detalhe no fim da partida ==")
race.reset()
larga(race)
race.cars = [car for car in race.cars if car.fixed]
for car in race.cars:
    car.dist = race.snapshot()["trackLength"] - 1
vitoria = [e for e in race.update() if e["kind"] == "winner"]
snap = race.snapshot()
check("fase vira 'over'", snap["phase"] == "over", snap["phase"])
check("snapshot tem o vencedor", bool(snap["winner"]), str(snap["winner"]))
check("vencedor tem veiculo, km/h, pontos e likes",
      all(k in snap["winner"] for k in ("user", "vehicle", "kmh", "points", "likes")), str(snap["winner"]))
check("evento de vitoria cita o veiculo", "VENCEU COM" in (vitoria[0]["message"] if vitoria else ""),
      vitoria[0]["message"] if vitoria else "sem evento")

print("\n== K. banner diz o efeito de cada presente ==")
race = build("corrida")
race.handle_event({"event": "comment", "user": "ana", "text": "oi"})
n_roda = [car for car in race.cars if car.user == "ana"][0].number
gift = race.handle_event({"event": "gift", "user": "ana", "gift": "Galaxy", "count": 1})[0]
check("presente avisa o efeito em km/h", "km/h" in gift["message"], gift["message"])
check("presente traz campo effect_text", bool(gift.get("effect_text")), str(gift.get("effect_text")))
oleo = race.handle_event({"event": "gift", "user": "ana", "gift": "Chuva de Dinheiro", "count": 1})[0]
check("oleo avisa as manchas", "mancha" in oleo["message"].lower(), oleo["message"])

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
