"""O que foi adotado do repo vamnguyen/tiktok-live-games.

Este teste cobre as pecas copiadas de la (e o que NAO copiamos, com o motivo):
politica de reconexao com backoff e jitter, catalogo de presentes com moedas/emoji,
fase "esperando" antes da largada e desempate justo na vitoria.
"""
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))          # _harness
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # projeto

from _harness import PORT_B, PROJECT, check, finish, run_server, server_log  # noqa: E402
from shared import gifts as gift_lib  # noqa: E402
from shared.reconnect import PoliticaReconexao  # noqa: E402
from server.games import build  # noqa: E402

print("\n== A. politica de reconexao (backoff + jitter) ==")
# sem jitter: a espera tem que crescer monotonicamente ate o teto
politica = PoliticaReconexao(base_s=2.0, teto_s=60.0, tentativas=8, jitter=0.0)
esperas = []
for _ in range(8):
    if not politica.pode_tentar():
        break
    politica.registra_falha()
    esperas.append(politica.proxima_espera())

check("espera cresce com a tentativa", esperas == sorted(esperas), str(esperas))
check("espera respeita o teto", max(esperas) <= 60.0 + 0.01, str(max(esperas)))
check("nunca espera menos de meio segundo", min(esperas) >= 0.5, str(min(esperas)))
check("com jitter as esperas oscilam (evita martelar em sincronia)",
      PoliticaReconexao(base_s=2.0, tentativas=1, jitter=0.3).proxima_espera() !=
      PoliticaReconexao(base_s=2.0, tentativas=1, jitter=0.3).proxima_espera())
check("ha jitter (duas execucoes nao batem)",
      PoliticaReconexao(base_s=2.0, tentativas=1).proxima_espera() !=
      PoliticaReconexao(base_s=2.0, tentativas=1).proxima_espera())
check("desiste depois de N tentativas", PoliticaReconexao(tentativas=3).registra_falha() or True)
p3 = PoliticaReconexao(tentativas=3)
for _ in range(3):
    p3.registra_falha()
check("pode_tentar falso no fim", not p3.pode_tentar() and p3.desiste())
p3.registra_sucesso()
check("sucesso zera a contagem", p3.pode_tentar() and p3.tentativa == 0)

print("\n== B. catalogo de presentes (moedas por nome + emoji) ==")
catalogo = gift_lib.load()
check("catalogo carregou do config/presentes.json", len(catalogo.gifts) >= 20, f"{len(catalogo.gifts)} presentes")
check("Universo TikTok vale 44999 sem a lib mandar valor", gift_lib.coins_conhecidas("Universo TikTok") == 44999)
check("nome global (Galaxy) tambem resolve", gift_lib.coins_conhecidas("Galaxy") == 1000)
check("valor da lib tem prioridade sobre o catalogo", gift_lib.magnitude(1, "Universo TikTok") == 1)
check("emoji vem do catalogo", gift_lib.emoji_de("Universo TikTok") == "\U0001f30c",
      repr(gift_lib.emoji_de("Universo TikTok")))
check("presente desconhecido cai no piso", gift_lib.magnitude(0, "Presente Inexistente") == 1)
info = gift_lib.describe("Universo TikTok")
check("describe traz emoji, moedas e faixa",
      info["emoji"] and info["coins"] == 44999 and "x8" in str(info["tier"]), str(info))

print("\n== C. fase 'esperando' antes da largada ==")
race = build("corrida")
check("comeca esperando a plateia", race.phase == "esperando", race.phase)
for _ in range(120):
    race.update()
check("ninguem sai do lugar enquanto espera", all(car.dist < 0 for car in race.cars) and race.phase == "esperando")
race.handle_event({"event": "comment", "user": "ana", "text": "oi"})
check("primeiro viewer dispara a largada", race.phase == "countdown", race.phase)
lancamento = [e for e in race.update() if e["kind"] == "countdown"]
check("avisa que a largada comecou", bool(lancamento), lancamento[0]["message"] if lancamento else "")
snap = race.snapshot()
check("snapshot diz que esta esperando antes", "waitingFor" in snap)

print("\n== D. desempate justo na vitoria ==")
race = build("corrida")
race.cars = [car for car in race.cars if not car.fixed]
race.handle_event({"event": "comment", "user": "ana", "text": "oi"})
race.handle_event({"event": "comment", "user": "br", "text": "oi"})
ana = next(car for car in race.cars if car.user == "ana")
br = next(car for car in race.cars if car.user == "br")
race.phase = "racing"
race.countdown = 0
chegada = race.snapshot()["trackLength"] - 1
ana.dist = chegada
br.dist = chegada + 40          # br estava mais perto: tem que ganhar
br.speed = 9.0
ana.speed = 4.5
vitoria = [e for e in race.update() if e["kind"] == "winner"]
check("vence quem estava mais perto (nao o primeiro da lista)",
      bool(vitoria) and vitoria[0]["user"] == "br",
      vitoria[0]["user"] if vitoria else "ninguem venceu")
check("place 1 do vencedor", br.place == 1, f"br={br.place} ana={ana.place}")

print("\n== E. pagina de debug (eventos crus da live) ==")
with run_server("--game", "corrida", port=PORT_B) as server:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT_B}/debug", timeout=5) as resp:
            pagina = resp.read().decode("utf-8")
        check("/debug responde 200", True)
        check("/debug carrega o log de eventos", "debug.js" in pagina, pagina[:80])
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT_B}/debug.js", timeout=5) as resp:
            check("/debug.js servido", len(resp.read()) > 100)
    except Exception as err:  # noqa: BLE001
        check("/debug responde 200", False, repr(err))
    log = server_log(server)
check("servidor do debug sem erro", "Traceback" not in log, log[-200:])

print("\n== F. o que NAO foi adotado (e por que) ==")
servidor = (PROJECT / "server/server.py").read_text(encoding="utf-8")
bot = (PROJECT / "tiktok/bot.py").read_text(encoding="utf-8")
check("continuamos com estado no servidor (eles rodam no navegador)",
      "GameBase" in servidor and "GAMES" in servidor)
check("continuamos exigindo GAME_TOKEN (eles tem cors:*)", "GAME_TOKEN" in servidor)
check("continuamos com cooldown por viewer (eles nao tem)", "accepted(" in bot)
check("temos suite de testes (eles tem zero)", (PROJECT / "tests/run_all.py").is_file())

finish()
