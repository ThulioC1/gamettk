"""Bot do TikTok: le a live e repassa cada evento para o servidor do jogo.

Fluxo:  live -> (TikTokLive) -> evento -> cooldown/rate limit -> WebSocket -> jogo

A leitura do TikTok roda em uma thread separada (a lib usa o proprio event loop)
e coloca tudo numa fila thread-safe. O laco asyncio deste arquivo so cuida da
conexao com o servidor do jogo.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import pathlib
import queue
import sys
import threading
import time
from typing import Any, Dict, Optional

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import websockets  # type: ignore

from shared import config  # noqa: E402
from shared import gifts as gift_lib  # noqa: E402

LOGGER = logging.getLogger("tiktok-bot")

SOURCE = "tiktok"
RECONNECT_DELAY = 3.0

#: fila entre a thread do TikTok e o laco asyncio
inbox: "queue.Queue[Dict[str, Any]]" = queue.Queue()

#: ultimo evento aceito por usuario (cooldown por pessoa)
last_seen: Dict[str, float] = {}

#: relogio deslizante de eventos aceitos (teto global)
recent: list[float] = []


# --------------------------------------------------------------- rate limiting
def accepted(user: str) -> tuple[bool, str]:
    """Aplica cooldown por viewer e teto global de eventos."""
    now = time.monotonic()
    cooldown_s = config.get_int("COMMAND_COOLDOWN_MS", minimum=0) / 1000
    limit_per_min = config.get_int("COMMAND_RATE_LIMIT_PER_MIN", minimum=0)

    if now - last_seen.get(user, 0.0) < cooldown_s:
        return False, "cooldown"

    recent[:] = [stamp for stamp in recent if now - stamp < 60.0]
    if limit_per_min and len(recent) >= limit_per_min:
        return False, "limite por minuto"

    # live longa acumula viewer novo; limpa quem ja saiu do cooldown
    if len(last_seen) > 5000:
        for name in [name for name, seen in last_seen.items() if now - seen > max(cooldown_s * 4, 60.0)]:
            del last_seen[name]

    last_seen[user] = now
    recent.append(now)
    return True, "ok"


# ------------------------------------------------------------------ listeners
def build_tiktok_client(username: str) -> Any:
    """Cria o cliente da lib e registra os listeners."""
    from TikTokLive import TikTokLiveClient
    from TikTokLive.client.logger import LogLevel
    from TikTokLive.client.web.web_settings import WebDefaults
    from TikTokLive.events import (
        CommentEvent,
        ConnectEvent,
        DisconnectEvent,
        FollowEvent,
        GiftEvent,
        LikeEvent,
        LiveEndEvent,
        RoomUserSeqEvent,
        ShareEvent,
    )

    sign_key = config.get_str("EULER_API_KEY")
    if sign_key:
        WebDefaults.tiktok_sign_api_key = sign_key

    client = TikTokLiveClient(unique_id=username)
    client.logger.setLevel(LogLevel.INFO.value)

    def nickname(event) -> str:
        user = getattr(event, "user", None)
        if user is None:
            return "anon"
        return (getattr(user, "nickname", "") or getattr(user, "unique_id", "") or "anon")[:24]

    def guard(func):
        """Listener nunca pode derrubar a conexao do TikTok."""
        def wrapper(event) -> None:
            try:
                func(event)
            except Exception:  # noqa: BLE001
                LOGGER.exception("erro tratando %s", type(event).__name__)
        return wrapper

    def on_comment(event) -> None:
        text = getattr(event, "comment", "") or ""
        if not text.strip():
            return
        inbox.put({"event": "comment", "user": nickname(event), "text": text[:80]})

    def on_gift(event) -> None:
        # streak: so o evento final conta (repeat_end == 1). Durante o streak o
        # proprio TikTokLive marca `value` como None para nao contar em dobro.
        if getattr(event, "streaking", False):
            return
        details = getattr(event, "gift", None)
        if details is None:
            return
        inbox.put({
            "event": "gift",
            "user": nickname(event),
            "gift": getattr(details, "name", "") or "presente",
            "count": int(getattr(event, "repeat_count", 1) or 1),
            # moedas do presente (gift.diamond_count: Rosa=1, Universo TikTok=44999)
            "value": int(getattr(details, "diamond_count", 0) or 0),
        })

    def on_like(event) -> None:
        inbox.put({
            "event": "like",
            "user": nickname(event),
            "count": int(getattr(event, "count", 1) or 1),
        })

    def on_follow(event) -> None:
        inbox.put({"event": "follow", "user": nickname(event)})

    def on_share(event) -> None:
        inbox.put({"event": "share", "user": nickname(event)})

    def on_room_user(event) -> None:
        inbox.put({"viewers": int(getattr(event, "total_user", 0) or 0)})

    def on_connect(event) -> None:
        inbox.put({"status": True, "room_id": getattr(event, "room_id", None)})

    def on_disconnect(event) -> None:
        inbox.put({"status": False, "note": "conexao caiu"})

    def on_live_end(event) -> None:
        inbox.put({"status": False, "note": "criador encerrou a live"})

    for event_class, handler in (
        (CommentEvent, on_comment),
        (GiftEvent, on_gift),
        (LikeEvent, on_like),
        (FollowEvent, on_follow),
        (ShareEvent, on_share),
        (RoomUserSeqEvent, on_room_user),
        (ConnectEvent, on_connect),
        (DisconnectEvent, on_disconnect),
        (LiveEndEvent, on_live_end),
    ):
        client.add_listener(event_class, guard(handler))

    return client


def run_tiktok_thread(username: str) -> None:
    """Thread que mantem a conexao com a live (a lib bloqueia aqui)."""
    from TikTokLive.client.errors import UserNotFoundError, UserOfflineError

    while True:
        client = build_tiktok_client(username)
        try:
            client.run()  # bloqueia ate a live acabar
            LOGGER.info("conexao com a live encerrada; tentando dnv em 5s")
        except UserOfflineError:
            LOGGER.warning("@%s nao esta ao vivo agora. tentando dnv em 30s", username)
            time.sleep(30)
        except UserNotFoundError:
            LOGGER.error("@%s nao existe ou nao tem live. verifique o username", username)
            return
        except Exception:  # noqa: BLE001
            LOGGER.exception("falha inesperada na conexao com o TikTok")
            time.sleep(15)
        else:
            time.sleep(5)


# ------------------------------------------------------------------ game link
async def pump_events(websocket: Any, username: str) -> None:
    """Transfere os eventos da live para o servidor do jogo."""
    reported = False
    viewers: Optional[int] = None
    room_id: Optional[int] = None

    async def report(connected: bool, note: str = "") -> None:
        await websocket.send(json.dumps({
            "type": "source_status",
            "source": SOURCE,
            "connected": connected,
            "username": username,
            "note": note,
            "viewers": viewers,
            "room_id": room_id,
        }))

    await report(False, "conectando na live")

    while True:
        try:
            item = inbox.get_nowait()
        except queue.Empty:
            await asyncio.sleep(0.05)
            continue

        if "viewers" in item:
            viewers = item["viewers"]
            if reported:
                await report(True)
            continue

        if "status" in item:
            reported = item["status"]
            room_id = item.get("room_id")
            await report(reported, item.get("note", ""))
            LOGGER.info("live conectada" if reported else "live desconectada")
            continue

        user = item.get("user", "anon")
        ok, reason = accepted(user)
        if not ok:
            LOGGER.debug("descartado (%s): %s de %s", reason, item["event"], user)
            continue

        payload = {"type": "event", "source": SOURCE, **item}
        await websocket.send(json.dumps(payload, ensure_ascii=False))

        effect = ""
        if item["event"] == "gift":
            effect = f" [{gift_lib.classify(item.get('gift'))}]"
        LOGGER.info("%-22s %-7s %s%s", user, item["event"], str(item.get("text", item.get("gift", "")))[:40], effect)


async def run_game_link(username: str) -> None:
    """Mantem o WebSocket com o servidor do jogo vivo, com reconexao."""
    base = f"ws://127.0.0.1:{config.get_int('PORT', minimum=1)}"
    token = config.get_str("GAME_TOKEN")
    url = f"{base}/?token={token}" if token else base

    while True:
        try:
            async with websockets.connect(url, max_size=1 << 20) as websocket:
                LOGGER.info("ligado ao servidor do jogo em %s", base)
                await pump_events(websocket, username)
        except asyncio.CancelledError:
            raise
        except (OSError, websockets.exceptions.WebSocketException) as err:
            LOGGER.error("conexao com o servidor do jogo falhou (%s). tentando dnv em %.0fs", err, RECONNECT_DELAY)
            await asyncio.sleep(RECONNECT_DELAY)


# ----------------------------------------------------------------------- main
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bot que joga com o chat da live do TikTok.")
    parser.add_argument("--username", help="usuario do criador da live (padrao: TIKTOK_USERNAME do .env)")
    parser.add_argument("--port", type=int, help="porta do servidor do jogo (padrao: PORT do .env)")
    parser.add_argument("--list", action="store_true", help="apenas mostra a configuracao e sai")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")

    username = (args.username or config.get_str("TIKTOK_USERNAME")).lstrip("@")
    if args.port:
        os.environ["PORT"] = str(args.port)

    if args.list:
        print(f"usuario:   {username or '(nao configurado)'}")
        print(f"sign key:  {'configurada' if config.get_str('EULER_API_KEY') else 'AUSENTE'}")
        print(f"servidor:  ws://127.0.0.1:{config.get_int('PORT', minimum=1)}")
        print(f"cooldown:  {config.get_int('COMMAND_COOLDOWN_MS')} ms por viewer")
        print(f"teto:      {config.get_int('COMMAND_RATE_LIMIT_PER_MIN')} eventos/min")
        print("presentes:")
        for effect in gift_lib.EFFECT_LABELS:
            keywords = config.get_str(f"GIFT_{effect}_KEYWORDS") or gift_lib.DEFAULT_KEYWORDS[effect]
            print(f"  {effect:<7} {gift_lib.EFFECT_LABELS[effect]:<20} <- {keywords}")
        return

    if not username:
        LOGGER.error("informe o criador da live: --username fulano  ou  TIKTOK_USERNAME=fulano no .env")
        return

    if not config.get_str("EULER_API_KEY"):
        LOGGER.warning(
            "EULER_API_KEY vazia. A lib usa o sign-server comunitario da Euler Stream com poucas "
            "requisicoes por minuto - se falhar, cadastre uma key gratuita em https://www.eulerstream.com"
        )

    threading.Thread(target=run_tiktok_thread, args=(username,), daemon=True, name="tiktok").start()
    try:
        asyncio.run(run_game_link(username))
    except KeyboardInterrupt:
        LOGGER.info("bot encerrado")


if __name__ == "__main__":
    main()
