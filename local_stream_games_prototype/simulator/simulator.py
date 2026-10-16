"""Simulador de live: gera comentarios e presentes como se fossem de uma live real.

Existe para testar o jogo inteiro sem depender de live nenhuma (e sem gastar
requisicao do sign-server do TikTok).

    python3 simulator/simulator.py --auto      # simula uma live inteira sozinho
    python3 simulator/simulator.py             # console: digite comandos/ações
"""
from __future__ import annotations

import asyncio
import json
import logging
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import websockets  # type: ignore

from shared import commands as cmd  # noqa: E402
from shared import config  # noqa: E402
from shared import gifts as gift_lib  # noqa: E402

LOGGER = logging.getLogger("simulator")

SERVER_URL = f"ws://127.0.0.1:{config.get_int('PORT', minimum=1)}"
RECONNECT_DELAY = 3.0
TOKEN = config.get_str("GAME_TOKEN")
CONTROL_URL = f"{SERVER_URL}/?token={TOKEN}" if TOKEN else SERVER_URL
SOURCE = "simulator"

FAKE_USERS = [
    "ana.live", "br.com", "carla_", "duda.exe", "elisao", "fef_", "gabi", "heitor",
    "isa.ods", "juju", "kaue", "lel", "mari", "nando", "olivia", "pedrao", "queila",
    "rafa", "sarah", "tobin", "ursula", "vitor", "wendel", "yasmin",
]

FAKE_COMMENTS = [
    "pula", "VAI!", "corrida", "tô chegando", "kkkkk", "vai com tudo", "valeu",
    "vamos que vamos", "esse jogo é bom", "left", "direita", "bora", "🚀🚀",
    "primeira vez aqui", "oi live", "quem tá ganhando?",
    # metade cita o carro: exercita a escolha de veiculo
    "tenho um gol", "vou de moto biz", "solta a pcx", "chegou a opala",
    "xre 300 na pista", "pilotando o g8",
]

FAKE_GIFTS = ["Rose", "Heart", "Galaxy", "TikTok", "Rosa", "Love", "Draco", "Banana"]

AUTO_EVENT_INTERVAL = 0.35
AUTO_COMMENT_RATIO = 0.75  # 75% comentarios, o resto presentes/likes

# Semente da live ficticia: sem ela cada `--auto` joga diferente e o teste fica
# instavel. Troque com: python3 simulator/simulator.py --auto --seed 7
AUTO_SEED = 4242


def _seed_do_argumento(default: int) -> int:
    argv = sys.argv
    for index, item in enumerate(argv):
        if item == "--seed" and index + 1 < len(argv):
            try:
                return int(argv[index + 1])
            except ValueError:
                return default
        if item.startswith("--seed="):
            try:
                return int(item.split("=", 1)[1])
            except ValueError:
                return default
    return default


rng = random.Random(_seed_do_argumento(AUTO_SEED))


async def send(websocket, payload: dict) -> None:
    await websocket.send(json.dumps({"type": "event", "source": SOURCE, "user": "sim", **payload},
                                    ensure_ascii=False))


async def report_status(websocket, connected: bool, note: str = "") -> None:
    await websocket.send(json.dumps({
        "type": "source_status", "source": SOURCE, "connected": connected,
        "username": "simulador", "note": note, "viewers": rng.randint(20, 400),
    }))


async def eco(websocket, stop: asyncio.Event) -> None:
    """Leitor unico do socket: mostra no console o que o jogo respondeu.

    Sem isso o REPL manda evento e nao da retorno nenhum — da a impressao de que
    "nao aconteceu nada". O `state` chega 30x/s e e descartado de proposito.
    """
    try:
        async for raw in websocket:
            if stop.is_set():
                return
            try:
                payload = json.loads(raw)
            except (TypeError, json.JSONDecodeError):
                continue
            if payload.get("type") == "event":
                for notice in payload.get("notices") or []:
                    if notice.get("message"):
                        print(f"  >> {notice['message']}", flush=True)
            elif payload.get("type") == "game_event" and payload.get("message"):
                print(f"  >> {payload['message']}", flush=True)
    except (websockets.exceptions.WebSocketException, asyncio.CancelledError):
        return


def veiculo_pedido(texto: str):
    """'gol', 'XRE 300' -> veiculo do catalogo; None se nao for veiculo."""
    try:
        from shared import carros as carro_lib
    except ImportError:
        return None
    return carro_lib.from_text(texto, carro_lib.load())


async def auto_mode(websocket, stop: asyncio.Event) -> None:
    """Gera uma live fictícia: viewers comentando, mandando presentes e likes."""
    rng.seed(_seed_do_argumento(AUTO_SEED))  # mesma live ficticia toda vez
    viewers = rng.sample(FAKE_USERS, k=min(len(FAKE_USERS), rng.randint(4, 12)))
    LOGGER.info("modo automatico: %d viewers simulados (Ctrl+C para sair)", len(viewers))

    await report_status(websocket, True, "modo automatico")
    eco_task = asyncio.create_task(eco(websocket, stop))
    try:
        while not stop.is_set():
            user = rng.choice(viewers)
            roll = rng.random()
            if roll < 0.05:
                await send(websocket, {"event": "follow", "user": user})
            elif roll < AUTO_COMMENT_RATIO:
                text = rng.choice(FAKE_COMMENTS)
                await send(websocket, {"event": "comment", "user": user, "text": text})
            elif roll < 0.95:
                gift = rng.choice(FAKE_GIFTS)
                count = rng.choice([1, 1, 1, 2, 5])
                await send(websocket, {"event": "gift", "user": user, "gift": gift, "count": count})
            else:
                await send(websocket, {"event": "like", "user": user, "count": rng.randint(1, 30)})
            await asyncio.sleep(AUTO_EVENT_INTERVAL * rng.random())
    finally:
        eco_task.cancel()
        await report_status(websocket, False, "modo automatico desligado")


HELP = """
comandos:
  comento <texto>   simula um comentário      (ex: comento vou ganhar)
  carro <nome>      escolhe/troca o carro     (ex: carro gol, carro xre 300)
  presente <nome>   simula um presente        (ex: presente Galaxy)
  like              simula likes
  follow            simula um follow
  auto              liga/desliga a live simulada
  jogo <MOVE_LEFT|MOVE_RIGHT|JUMP|STOP|RESET>   comando direto (platformer)
  help / quit

Atalho: escrever so o nome do carro (gol, fusca, pcx, xre 300...) ja escolhe.
O que o jogo responder aparece logo abaixo com ">>".
"""


async def read_line(prompt: str) -> str:
    """Le uma linha do teclado sem travar o event loop.

    `loop.run_in_executor` devolve um Future, e `asyncio.create_task` so aceita
    coroutine — por isso o wrapper (o erro aparece so no modo interativo).
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, input, prompt)


async def interactive_mode(websocket, stop: asyncio.Event) -> bool:
    """REPL simples para disparar evento por evento.

    Devolve False quando o usuario pediu para sair (quit, Ctrl+D, Ctrl+C).
    """
    await report_status(websocket, True, "console")
    print(HELP)

    eco_task = asyncio.create_task(eco(websocket, stop))
    stop_task = asyncio.create_task(stop.wait())
    try:
        while not stop.is_set():
            line_task = asyncio.create_task(read_line("evento> "))
            done, _ = await asyncio.wait({line_task, stop_task}, return_when=asyncio.FIRST_COMPLETED)
            if line_task not in done:
                line_task.cancel()
                return False

            try:
                raw = (line_task.result() or "").strip()
            except (EOFError, KeyboardInterrupt):  # stdin fechou (pipe, Ctrl+D)
                print("\nate mais!")
                return False
            if not raw:
                continue

            action, _, argument = raw.partition(" ")
            action = cmd.normalize(action)

            if action in {"quit", "exit", "sair"}:
                return False
            if action in {"help", "ajuda"}:
                print(HELP)
                continue
            if action == "auto":
                await auto_mode(websocket, stop)
                continue
            if action == "comento":
                await send(websocket, {"event": "comment", "user": "voce", "text": argument.strip()[:80]})
                print(f"  >> comentario enviado: {argument.strip()!r}", flush=True)
                continue
            if action == "carro":
                nome = argument.strip()[:40]
                if not nome:
                    print("uso: carro <nome>  (ex: carro gol)")
                    continue
                veiculo = veiculo_pedido(nome)
                await send(websocket, {"event": "comment", "user": "voce", "text": nome})
                print(f"  >> pedindo {veiculo.name if veiculo else nome!r}"
                      f"{'' if veiculo else ' (nao achei no catalogo)'}", flush=True)
                continue
            if action == "presente":
                await send(websocket, {"event": "gift", "user": "voce",
                                       "gift": argument.strip()[:40] or "Rose", "count": 1})
                print(f"  >> presente enviado: {argument.strip()!r}")
                continue
            if action == "like":
                await send(websocket, {"event": "like", "user": "voce", "count": 10})
                print("  >> like enviado", flush=True)
                continue
            if action == "follow":
                await send(websocket, {"event": "follow", "user": "voce"})
                print("  >> follow enviado", flush=True)
                continue
            if action == "jogo":
                command = argument.strip().upper()
                if command in cmd.COMMANDS:
                    await send(websocket, {"event": "command", "command": command, "user": "console"})
                    print(f"  >> comando enviado: {command}", flush=True)
                else:
                    print(f"comando invalido: {command!r}. use: {', '.join(cmd.COMMANDS)}")
                continue

            if raw.upper() in cmd.COMMANDS:
                await send(websocket, {"event": "command", "command": raw.upper(), "user": "console"})
                print(f"  >> comando enviado: {raw.upper()}", flush=True)
                continue

            # atalho: nome de carro solto ("gol", "XRE 300", "moto biz")
            veiculo = veiculo_pedido(raw)
            if veiculo is not None:
                await send(websocket, {"event": "comment", "user": "voce", "text": raw})
                print(f"  >> pedindo {veiculo.name}", flush=True)
                continue

            print("nao entendi. digite 'help'.")
    finally:
        stop_task.cancel()
        eco_task.cancel()

    return not stop.is_set()


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    stop = asyncio.Event()

    while not stop.is_set():
        try:
            async with websockets.connect(CONTROL_URL) as websocket:
                if "--auto" in sys.argv:
                    await auto_mode(websocket, stop)
                    return
                # interativo: so volta a conectar se o usuario nao tiver saido
                if not await interactive_mode(websocket, stop):
                    LOGGER.info("simulador encerrado")
                    return
        except (OSError, websockets.exceptions.WebSocketException) as err:
            LOGGER.error("nao consegui falar com %s (%s)", SERVER_URL, err)
            await asyncio.sleep(RECONNECT_DELAY)
        except KeyboardInterrupt:
            return

    LOGGER.info("simulador encerrado")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nate mais!")
