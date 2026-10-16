"""Testes do Duelo de Torres (suite do launcher)."""

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

from shared import sides as sides_lib  # noqa: E402

print("\n== A. configuracao do duelo (personalizacao) ==")

duel_cfg = sides_lib.load()

check("dois lados configurados", len(duel_cfg.sides) == 2, ", ".join(s.label() for s in duel_cfg.sides))

check("lado esquerdo e Lula/PT", duel_cfg.sides[0].name == "Lula" and duel_cfg.sides[0].party == "PT")

check("lado direito e Flavio/PL", duel_cfg.sides[1].name == "Fl\u00e1vio Bolsonaro" and duel_cfg.sides[1].party == "PL")

check("cores distintas", duel_cfg.sides[0].color != duel_cfg.sides[1].color)

check("meta de 32 blocos", duel_cfg.target_blocks == 32)

for text, expected in [

    ("lula", "esquerda"), ("LULA!", "esquerda"), ("sou do pt", "esquerda"),

    ("vermelho", "esquerda"), ("flavio", "direita"), ("bolsonaro", "direita"),

    ("direita", "direita"), ("azul", "direita"), ("OlÃ¡ pessoal", None), ("", None),

]:

    side = sides_lib.side_from_text(text, duel_cfg)

    got = side.id if side else None

    check(f"side_from_text({text!r}) == {expected}", got == expected, f"got={got}")

print("\n== B. escolha de lado e pilha ==")

game = build("duelo")

notices = game.handle_event({"event": "comment", "user": "ana", "text": "lula"})

tower = game.towers[0]

check("comentario escolheu o lado", tower.height == 1, f"altura={tower.height}")

check("aviso de lado enviado", any(n["kind"] == "side" for n in notices))

game.handle_event({"event": "comment", "user": "br", "text": "flavio"})

check("segundo viewer foi para o outro lado", game.towers[1].height == 1)

game.handle_event({"event": "comment", "user": "ana", "text": "vamo"})

check("comentar de novo empilha no mesmo lado", game.towers[0].height == 2 and game.towers[1].height == 1)

before = game.towers[0].height

game.handle_event({"event": "comment", "user": "ana", "text": "flavio agora"})

check("palavra de outro lado troca o jogador", game.supporter_of["ana"] == "direita", game.supporter_of["ana"])

check("torre antiga permanece", game.towers[0].height == before)

total_before = sum(t.height for t in game.towers)

newcomer = [f"u{i}" for i in range(12)]

for user in newcomer:

    game.handle_event({"event": "comment", "user": user, "text": "oi"})

check("quem nao escreve lado vai para o mais baixo (ou aleatorio)",

      sum(t.height for t in game.towers) == total_before + 12, f"{[t.height for t in game.towers]}")

check("todos os lados sao validos", all(game.supporter_of[u] in {"esquerda", "direita"} for u in newcomer))

print("\n== C. presentes ==")

game.reset()

game.supporter_of.clear()

game.handle_event({"event": "comment", "user": "ana", "text": "lula"})

base = game.towers[0].height

game.handle_event({"event": "gift", "user": "ana", "gift": "Galaxy", "count": 1})

check("presente grande levanta varios blocos", game.towers[0].height >= base + 2, f"{base} -> {game.towers[0].height}")

before_rose = game.towers[0].height

game.handle_event({"event": "gift", "user": "ana", "gift": "Rose", "count": 2})

check("presente pequeno Ã—2 levanta 4", game.towers[0].height - before_rose == 4,

      f"{before_rose} -> {game.towers[0].height}")

game.handle_event({"event": "gift", "user": "ana", "gift": "Galaxy", "count": 99})

check("presente gigante e limitado (teto de 16)", game.towers[0].height - before_rose <= 16 + 4,

      f"altura={game.towers[0].height}")

rival_before = game.towers[1].height

game.handle_event({"event": "comment", "user": "br", "text": "flavio"})

rival_before = game.towers[1].height

out = game.handle_event({"event": "gift", "user": "ana", "gift": "Oil", "count": 1})

check("presente de oleo derruba bloco do rival", game.towers[1].height < rival_before,

      f"{rival_before} -> {game.towers[1].height}")

check("aviso de sabotagem com quantidade", any(n.get("kind") == "sabotage" and n.get("blocks", 0) > 0 for n in out))

print("\n== D. queda e desabamento ==")

game = build("duelo")

for i in range(80):

    game.handle_event({"event": "comment", "user": f"z{i}", "text": "lula"})

heights = [t.height for t in game.towers]

leans = [t.lean for t in game.towers]

check("torre grew ou desabou", max(heights) >= 20 or any(l > 0 for l in leans), f"{heights} lean={leans}")

check("nenhum lado passa da meta antes de vencer", max(heights) <= game.duel.target_blocks, str(heights))

game = build("duelo")

# forca desabamento: torre cheia de blocos tortos (limite de inclinacao)

tower = game.towers[0]

tower.lean = 1.0

events = game.update()

check("desabou no limite de inclinacao", any(e["kind"] == "collapse" for e in events), str(events[:1]))

check("torre perdeu blocos", tower.height == 0, f"altura={tower.height}")

print("\n== E. vitoria e reinicio ==")

game = build("duelo")

game.handle_event({"event": "comment", "user": "ana", "text": "lula"})

seen_events = []

for _ in range(60):

    seen_events += game.update()

    if game.winner:

        break

    game.handle_event({"event": "gift", "user": "ana", "gift": "Galaxy", "count": 1})

check("atingiu a meta e declarou vencedor", game.winner == "esquerda", str(game.winner))

win_events = [e for e in seen_events if e["kind"] == "winner"]

check("evento de vitoria emitido", bool(win_events), win_events[0]["message"] if win_events else str(seen_events[-1:]))

blocked = game.handle_event({"event": "comment", "user": "br", "text": "flavio"})

check("nada entra no jogo enquanto o duelo acaba", blocked == [])

restarted = False

for _ in range(600):

    if any(e["kind"] == "restart" for e in game.update()):

        restarted = True

        break

check("duelo reinicia sozinho", restarted)

check("torres voltam a zero", all(t.height == 0 for t in game.towers))

print("\n== F. snapshot e serializacao ==")

snap = build("duelo").snapshot()

check("snapshot traz duas torres", len(snap["towers"]) == 2)

check("snapshot traz identidade dos lados", {"name", "party", "color"} <= set(snap["towers"][0]["side"]))

check("snapshot serializa em JSON", isinstance(json.dumps(snap, ensure_ascii=False), str))

describe = build("duelo").describe()

check("describe traz o titulo customizado", describe["title"] == "Duelo de Torres", describe["title"])

check("describe lista os lados", len(describe["sides"]) == 2)

check("duelo registrado no launcher", "duelo" in GAMES, str(sorted(GAMES)))

print("\n== G. servidor servindo o duelo ==")

env = {**os.environ, "PORT": PORT}

server = subprocess.Popen([sys.executable, "server/server.py", "--game", "duelo"], cwd=str(PROJECT), env=env,

                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

time.sleep(2.5)

async def ws_flow():

    import websockets

    result = {"welcome": None, "sides": {}, "maxHeights": [0, 0], "events": [], "winner": False}

    async with websockets.connect(f"ws://127.0.0.1:{PORT}/?game=duelo") as ws:

        hello = json.loads(await asyncio.wait_for(ws.recv(), 5))

        result["welcome"] = hello.get("game", {}).get("type")

        result["sides"] = {s["id"]: s["name"] for s in hello.get("game", {}).get("sides", [])}

        users = ["lula_1", "pt_2", "flavio_3", "bolso_4", "neutro_5", "pt_6"]

        for user in users:

            await ws.send(json.dumps({"type": "event", "event": "comment", "source": "tiktok",

                                     "user": user, "text": "lula" if "pt" in user or "lula" in user else "flavio"}))

            await ws.send(json.dumps({"type": "event", "event": "gift", "source": "tiktok",

                                     "user": user, "gift": "Galaxy", "count": 2}))

        deadline = time.time() + 6

        while time.time() < deadline:

            try:

                payload = json.loads(await asyncio.wait_for(ws.recv(), 3))

            except asyncio.TimeoutError:

                break

            if payload.get("type") == "state":

                heights = [t["height"] for t in payload["state"]["towers"]]

                result["maxHeights"] = [max(result["maxHeights"][i], heights[i]) for i in (0, 1)]

            elif payload.get("type") == "game_event":

                result["events"].append(payload.get("kind"))

                if payload.get("kind") == "winner":

                    result["winner"] = True

                    break

    return result

try:

    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/renderers/duelo.js", timeout=5) as resp:

        check("renderer do duelo servido", len(resp.read()) > 1000)

except Exception as err:  # noqa: BLE001

    check("renderer do duelo servido", False, str(err))

try:

    result = asyncio.run(ws_flow())

    check("welcome diz que e o duelo", result["welcome"] == "duelo", str(result["welcome"]))

    check("lados personalizados chegam ao client", result["sides"] == {"esquerda": "Lula", "direita": "Fl\u00e1vio Bolsonaro"},

          json.dumps(result["sides"], ensure_ascii=False))

    check("torres subiram com os eventos", max(result["maxHeights"]) >= 3, str(result["maxHeights"]))

except Exception as err:  # noqa: BLE001

    check("fluxo WebSocket do duelo", False, repr(err))

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
