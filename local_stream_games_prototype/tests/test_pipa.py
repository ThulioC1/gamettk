"""Testes da Pipa Arena (suite do launcher)."""

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
from shared import pipas as pipa_lib  # noqa: E402

print("\n== A. configuracao da arena ==")
arena = pipa_lib.load()
check("titulo correto", arena.title == "Pipa Arena")
check("teto de pipas = 26", arena.max_kites == 26, str(arena.max_kites))
check("tres efeitos de presente", set(arena.gifts) == {"NITRO", "TURBO", "OIL"})
check("cores de pipa disponiveis", len(pipa_lib.PALETTE) >= 6)

print("\n== B. comentario solta pipa ==")
game = build("pipa")
check("tipo do jogo", game.type == "pipa")
notices = game.handle_event({"event": "comment", "user": "ana", "text": "oi"})
check("primeiro comentario solta pipa", len(game.kites) == 1)
check("aviso de pipa solta", notices[0]["kind"] == "launch" and "SOLTOU" in notices[0]["message"])
check("pipa com dono e cor", game.kites[0].user == "ana" and game.kites[0].color.startswith("#"))

for i in range(6):
    game.handle_event({"event": "comment", "user": f"u{i}", "text": "oi"})
check("cada comentario vira uma pipa", len(game.kites) == 7, str(len(game.kites)))
check("todas com dono diferente", len({k.user for k in game.kites}) == 7)

print("\n== C. altura sobe com mais gente no ceu ==")
game = build("pipa")
game.handle_event({"event": "comment", "user": "sozinho", "text": "oi"})
for _ in range(90):
    game.update()
single_height = game.kites[0].y if game.kites else 0

game = build("pipa")
for i in range(6):
    game.handle_event({"event": "comment", "user": f"u{i}", "text": "oi"})
for _ in range(90):
    game.update()
crowd_height = max([k.y for k in game.kites] or [0])
check("pipa sozinha nao sobe muito", single_height < 20, f"{single_height:.1f} px")
check("com many pipas o ceu sobe", crowd_height > single_height + 20,
      f"sozinho={single_height:.1f} multidao={crowd_height:.1f}")
check("altura tem teto", crowd_height <= 400.5, f"{crowd_height:.1f}")

print("\n== D. presente corta linha do rival ==")
game = build("pipa")
for i in range(6):
    game.handle_event({"event": "comment", "user": f"u{i}", "text": "oi"})
before = len(game.kites)
own_before = len([k for k in game.kites if k.user == "u0"])
out = game.handle_event({"event": "gift", "user": "u0", "gift": "Galaxy", "count": 1})
check("presente tirou pipas do ar", len(game.kites) < before, f"{before} -> {len(game.kites)}")
check("nunca corta a propria linha",
      len([k for k in game.kites if k.user == "u0"]) == own_before, f"{own_before} -> propreas")
check("mensagem de corte com quantidade", any(n.get("kind") == "cut" and n.get("cuts", 0) > 0 for n in out),
      str([n.get("message") for n in out]))

solo = build("pipa")
solo.handle_event({"event": "comment", "user": "u0", "text": "oi"})
out = solo.handle_event({"event": "gift", "user": "u0", "gift": "Galaxy", "count": 1})
check("sem rival nao corta ninguem", len(solo.kites) == 1 and out[0]["cuts"] == 0, out[0]["message"])

print("\n== E. juntar a pipa no chao ==")
game = build("pipa")
game.handle_event({"event": "comment", "user": "ana", "text": "oi"})
landed = []
for _ in range(400):
    landed += [e for e in game.update() if e["kind"] == "land"]
    if landed:
        break
check("pipa solitaria cai e marca pontos", bool(landed), landed[0]["message"] if landed else "nunca caiu")
check("pontos somados", landed[0]["points"] == 10, str(landed[0]["points"]))
check("pipa saiu do ceu apos juntar", len(game.kites) == 0)

print("\n== F. ceu cheio reinicia ==")
game = build("pipa")
for i in range(game.arena.max_kites + 6):
    game.handle_event({"event": "comment", "user": f"u{i}", "text": "oi"})
check("ceu respeita o teto", len(game.kites) <= game.arena.max_kites, str(len(game.kites)))
check("excedente virou destroco", len(game.fallen) > 0, f"{len(game.fallen)} caindo")
restarted = []
for _ in range(120):
    restarted += [e for e in game.update() if e["kind"] == "restart"]
    if restarted:
        break
check("ceu cheio limpa a rodada", bool(restarted), restarted[0]["message"] if restarted else "nao reiniciou")
check("tudo limpo apos reiniciar", not game.kites and not game.fallen)

print("\n== G. serializacao e launcher ==")
game = build("pipa")
game.handle_event({"event": "comment", "user": "ana", "text": "oi"})
snap = game.snapshot()
check("snapshot tem pipas e mundo", {"kites", "world", "load", "maxKites"} <= set(snap))
check("altura vai no snapshot", "y" in snap["kites"][0])
check("snapshot serializa", isinstance(json.dumps(snap, ensure_ascii=False), str))
check("describe traz efeitos", "giftEffects" in build("pipa").describe())
check("pipa registrada no launcher", "pipa" in GAMES, str(sorted(GAMES)))
check("quatro jogos no total", len(GAMES) == 4, str(sorted(GAMES)))

print("\n== H. servidor servindo a pipa arena ==")
env = {**os.environ, "PORT": PORT}
server = subprocess.Popen([sys.executable, "server/server.py", "--game", "pipa"], cwd=str(PROJECT), env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
time.sleep(2.5)

async def ws_flow():
    import websockets

    result = {"welcome": None, "maxLoad": 0, "launches": 0, "cuts": 0, "states": 0, "alts": []}
    async with websockets.connect(f"ws://127.0.0.1:{PORT}/?game=pipa") as ws:
        hello = json.loads(await asyncio.wait_for(ws.recv(), 5))
        result["welcome"] = hello.get("game", {}).get("type")

        for i in range(14):
            await ws.send(json.dumps({"type": "event", "event": "comment", "source": "tiktok",
                                     "user": f"viewer{i}", "text": "oi live"}))
            if i % 4 == 3:
                await ws.send(json.dumps({"type": "event", "event": "gift", "source": "tiktok",
                                         "user": f"viewer{i}", "gift": "Galaxy", "count": 1}))

        deadline = time.time() + 6
        while time.time() < deadline:
            try:
                payload = json.loads(await asyncio.wait_for(ws.recv(), 3))
            except asyncio.TimeoutError:
                break
            kind = payload.get("type")
            if kind == "state":
                result["states"] += 1
                result["maxLoad"] = max(result["maxLoad"], payload["state"]["load"])
                result["alts"] = [k["y"] for k in payload["state"]["kites"]][:1]
            elif kind == "event":
                for notice in payload.get("notices", []):
                    if notice.get("kind") == "launch":
                        result["launches"] += 1
                    elif notice.get("kind") == "cut" and notice.get("cuts"):
                        result["cuts"] += 1
    return result

try:
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/renderers/pipa_arena.js", timeout=5) as resp:
        check("renderer da pipa servido", len(resp.read()) > 1000)
except Exception as err:  # noqa: BLE001
    check("renderer da pipa servido", False, str(err))

try:
    result = asyncio.run(ws_flow())
    check("welcome diz que e a pipa", result["welcome"] == "pipa", str(result["welcome"]))
    check("14 comentarios viraram pipas", result["launches"] >= 10, f"{result['launches']} pipas")
    check("ceu encheu", result["maxLoad"] >= 6, f"max={result['maxLoad']}")
    check("presente cortou linha", result["cuts"] >= 1, f"{result['cuts']} cortes")
    check("estado continuou chegando", result["states"] > 30, f"{result['states']} snapshots")
except Exception as err:  # noqa: BLE001
    check("fluxo WebSocket da pipa", False, repr(err))
finally:
    server.terminate()
    try:
        log = server.communicate(timeout=6)[0]
    except subprocess.TimeoutExpired:
        server.kill()
        log = server.communicate()[0]

errors = [line for line in (log or "").splitlines() if "ERROR" in line or "Traceback" in line]
print("\n--- ultimas linhas do servidor ---")
print("\n".join((log or "").splitlines()[-6:]))
finish()
