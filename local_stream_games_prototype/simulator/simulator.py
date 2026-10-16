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
]

FAKE_GIFTS = ["Rose", "Heart", "Galaxy", "TikTok", "Rosa", "Love", "Draco", "Banana"]

AUTO_EVENT_INTERVAL = 0.35
AUTO_COMMENT_RATIO = 0.75  # 75% comentarios, o resto presentes/likes


async def send(websocket, payload: dict) -> None:
    await websocket.send(json.dumps({"type": "event", "source": SOURCE, "user": "sim", **payload},
                                    ensure_ascii=False))


async def report_status(websocket, connected: bool, note: str = "") -> None:
    await websocket.send(json.dumps({
        "type": "source_status", "source": SOURCE, "connected": connected,
        "username": "simulador", "note": note, "viewers": random.randint(20, 400),
    }))


async def auto_mode(websocket, stop: asyncio.Event) -> None:
    """Gera uma live fictícia: viewers comentando, mandando presentes e likes."""
    viewers = random.sample(FAKE_USERS, k=min(len(FAKE_USERS), random.randint(4, 12)))
    LOGGER.info("modo automatico: %d viewers simulados (Ctrl+C para sair)", len(viewers))

    await report_status(websocket, True, "modo automatico")
    try:
        while not stop.is_set():
            user = random.choice(viewers)
            roll = random.random()
            if roll < 0.05:
                await send(websocket, {"event": "follow", "user": user})
                LOGGER.info("follow de %s", user)
            elif roll < AUTO_COMMENT_RATIO:
                text = random.choice(FAKE_COMMENTS)
                await send(websocket, {"event": "comment", "user": user, "text": text})
            elif roll < 0.95:
                gift = random.choice(FAKE_GIFTS)
                count = random.choice([1, 1, 1, 2, 5])
                await send(websocket, {"event": "gift", "user": user, "gift": gift, "count": count})
                LOGGER.info("presente %s x%d de %s -> %s", gift, count, user, gift_lib.classify(gift))
            else:
                await send(websocket, {"event": "like", "user": user, "count": random.randint(1, 30)})
            await asyncio.sleep(AUTO_EVENT_INTERVAL * random.random())
    finally:
        await report_status(websocket, False, "modo automatico desligado")


HELP = """
comandos:
  comento <texto>   simula um comentário      (ex: comento vou ganhar)
  presente <nome>   simula um presente        (ex: presente Galaxy)
  like              simula likes
  follow            simula um follow
  auto              liga/desliga a live simulada
  jogo <MOVE_LEFT|MOVE_RIGHT|JUMP|STOP|RESET>   comando direto (platformer)
  help / quit
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
                continue
            if action == "presente":
                await send(websocket, {"event": "gift", "user": "voce",
                                       "gift": argument.strip()[:40] or "Rose", "count": 1})
                continue
            if action == "like":
                await send(websocket, {"event": "like", "user": "voce", "count": 10})
                continue
            if action == "follow":
                await send(websocket, {"event": "follow", "user": "voce"})
                continue
            if action == "jogo":
                command = argument.strip().upper()
                if command in cmd.COMMANDS:
                    await send(websocket, {"event": "command", "command": command, "user": "console"})
                else:
                    print(f"comando invalido: {command!r}. use: {', '.join(cmd.COMMANDS)}")
                continue

            if raw.upper() in cmd.COMMANDS:
                await send(websocket, {"event": "command", "command": raw.upper(), "user": "console"})
                continue

            print("nao entendi. digite 'help'.")
    finally:
        stop_task.cancel()

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
