"""Servidor do launcher: HTTP (client) + WebSocket (eventos) na mesma porta.

O servidor nao sabe qual jogo esta rodando. Ele entrega todo evento que chega
(da live, do simulador ou do teclado) ao modulo de jogo escolhido e reenvia o
estado para todos os navegadores conectados.
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import logging
import mimetypes
import pathlib
import secrets
import signal
import sys
import time
from http import HTTPStatus
from typing import Any, Dict, Optional, Set

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from websockets.asyncio.server import ServerConnection, serve  # type: ignore
from websockets.exceptions import ConnectionClosed  # type: ignore

from server.base import GameBase  # noqa: E402
from server.games import DEFAULT_GAME, GAMES, build  # noqa: E402
from shared import config  # noqa: E402

LOGGER = logging.getLogger("server")

CLIENT_DIR = (config.PROJECT_ROOT / "client").resolve()

TICK_RATE = 60
BROADCAST_EVERY_TICKS = 2          # ~30 snapshots/s por client
MAX_EVENTS_PER_SECOND = 60         # trava de seguranca contra spam

EVENT_TYPES = frozenset({"comment", "gift", "like", "follow", "share", "command"})

#: eventos que mudam o placar. Precisam de GAME_TOKEN configurado: sem isso,
#: qualquer pessoa com um WebSocket aberto injeta comentarios e presentes falsos.
CONTROLLED_EVENTS = frozenset({"comment", "gift", "like", "follow", "share"})

clients: Set[Any] = set()

#: todos os jogos rodam ao mesmo tempo, cada um com seu proprio estado.
#: Quem assiste escolhe qual quer ver (`?game=` na URL ou `watch` em tempo real);
#: quem manda eventos (bot/simulador) manda para o jogo que ele assiste.
games: Dict[str, GameBase] = {name: build(name) for name in GAMES}
default_game: str = (config.get_str("GAME") or DEFAULT_GAME).lower()
if default_game not in games:
    default_game = DEFAULT_GAME

#: web socket -> tipo do jogo que ele assiste
watching: Dict[Any, str] = {}

source_status: Dict[str, Dict[str, Any]] = {
    "tiktok": {"connected": False, "username": "", "note": "bot do TikTok offline"},
    "simulator": {"connected": False, "note": "simulador offline"},
}

_events_window: list[float] = []


def subscribers(game_type: str) -> Set[Any]:
    return {client for client, watched in watching.items() if watched == game_type}


# --------------------------------------------------------------------- utils
def _allow_event() -> bool:
    """Janela deslizante de 1 s com o teto de eventos globais."""
    now = time.monotonic()
    _events_window[:] = [stamp for stamp in _events_window if now - stamp < 1.0]
    if len(_events_window) >= MAX_EVENTS_PER_SECOND:
        return False
    _events_window.append(now)
    return True


async def broadcast(payload: Dict[str, Any], game_type: Optional[str] = None) -> None:
    """Envia o JSON para todos, ou so para quem assiste um jogo especifico."""
    if game_type is None:
        targets = list(clients)
    else:
        targets = list(subscribers(game_type))
    if not targets:
        return
    message = json.dumps(payload)
    await asyncio.gather(*(client.send(message) for client in targets), return_exceptions=True)


async def broadcast_status() -> None:
    await broadcast({
        "type": "status",
        "clients": len(clients),
        "sources": source_status,
        "games": [
            {"type": name, "watchers": len(subscribers(name)), "tick": games[name].tick}
            for name in sorted(games)
        ],
    })


# ----------------------------------------------------------------- eventos
async def handle_event(payload: Dict[str, Any], source: str, websocket: Any = None) -> None:
    """Valida, entrega ao jogo que a conexao assiste e avisa os clients."""
    event_type = str(payload.get("event", "")).strip().lower()
    if event_type not in EVENT_TYPES:
        LOGGER.debug("evento ignorado (tipo desconhecido): %r", event_type)
        return
    if event_type in CONTROLLED_EVENTS and not _is_authorized(websocket):
        LOGGER.warning("evento %s de %s descartado: conexao sem GAME_TOKEN", event_type, source)
        return
    if not _allow_event():
        LOGGER.warning("teto de eventos atingido; %s de %s descartado", event_type, source)
        return

    game_type = watching.get(websocket, default_game)
    game = games[game_type]

    event = {
        "event": event_type,
        "user": str(payload.get("user", "") or "anon")[:24],
        "text": str(payload.get("text", ""))[:80],
        "gift": str(payload.get("gift", ""))[:40],
        "count": _as_int(payload.get("count"), 1),
        "value": _as_int(payload.get("value"), 0),
        "command": str(payload.get("command", ""))[:16].upper(),
        "source": source,
        "at": int(time.time() * 1000) % 100_000_000,
    }

    notices = game.handle_event(event)

    await broadcast({"type": "event", "game": game_type, "event": event, "notices": notices}, game_type)
    for notice in notices:
        if notice.get("message"):
            LOGGER.info("[%s] %s", game_type, notice["message"])


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------- websocket
async def handler(websocket: ServerConnection) -> None:
    clients.add(websocket)
    peer = getattr(websocket, "remote_address", None)
    requested = _game_from_path(getattr(websocket, "streamgames_path", "") or "")
    game_type = requested if requested in games else default_game
    if requested and requested not in games:
        LOGGER.warning("jogo '%s' pedido na URL nao existe; usando '%s'", requested, default_game)
    watching[websocket] = game_type
    LOGGER.info("client conectado: %s assistindo '%s' (total %d)", peer, game_type, len(clients))

    await websocket.send(json.dumps({"type": "welcome", "game": games[game_type].describe(),
                                    "tickRate": TICK_RATE, "games": sorted(games)}))
    await broadcast_status()

    try:
        async for raw in websocket:
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", errors="ignore")
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                LOGGER.debug("payload invalido ignorado: %r", raw[:120])
                continue
            if not isinstance(payload, dict):
                continue

            message_type = payload.get("type")

            if message_type == "event":
                await handle_event(payload, str(payload.get("source", "unknown"))[:16], websocket)
            elif message_type == "watch":
                # troca de jogo em tempo real, sem recarregar a pagina
                wanted = str(payload.get("game", "")).strip().lower()
                if wanted in games:
                    watching[websocket] = wanted
                    await websocket.send(json.dumps({"type": "game", "game": games[wanted].describe(),
                                                    "tickRate": TICK_RATE}))
                    LOGGER.info("client %s agora assiste '%s'", peer, wanted)
                    await broadcast_status()
                else:
                    await websocket.send(json.dumps({"type": "error", "message": f"jogo desconhecido: {wanted}"}))
            elif message_type == "source_status":
                if not _is_authorized(websocket):
                    LOGGER.warning("source_status ignorado: sem GAME_TOKEN")
                    continue
                source = str(payload.get("source", "unknown"))[:16]
                source_status[source] = {
                    "connected": bool(payload.get("connected")),
                    "username": str(payload.get("username", ""))[:40],
                    "note": str(payload.get("note", ""))[:60],
                    "viewers": payload.get("viewers"),
                    "likes": payload.get("likes"),
                }
                await broadcast_status()
            elif message_type == "ping":
                await websocket.send(json.dumps({"type": "pong"}))
    except ConnectionClosed:
        pass
    except Exception:  # noqa: BLE001 - um client ruim nao derruba o servidor
        LOGGER.exception("erro no handler do client %s", peer)
    finally:
        clients.discard(websocket)
        watching.pop(websocket, None)
        LOGGER.info("client desconectado: %s (total %d)", peer, len(clients))
        await broadcast_status()


# --------------------------------------------------------------------- HTTP
def _safe_client_path(url_path: str) -> pathlib.Path | None:
    """Resolve o caminho pedido dentro de client/, bloqueando path traversal."""
    relative = url_path.split("?", 1)[0].split("#", 1)[0].lstrip("/")
    if relative in {"", "index.html"}:
        relative = "index.html"
    candidate = (CLIENT_DIR / relative).resolve()
    if candidate != CLIENT_DIR and CLIENT_DIR not in candidate.parents:
        return None
    return candidate if candidate.is_file() else None


def _token_from_path(url_path: str) -> str:
    """Le ?token=... da URL (o bot/simulador abrem a conexao com ele)."""
    query = url_path.split("?", 1)[1] if "?" in url_path else ""
    for part in query.split("&"):
        key, _, value = part.partition("=")
        if key == "token":
            return value
    return ""


def _is_authorized(websocket: Any) -> bool:
    """So quem mandou o token certo envia eventos da live.

    Sem GAME_TOKEN configurado (dev local) todo mundo pode: e' o padrao.
    """
    token = config.get_str("GAME_TOKEN")
    if not token:
        return True
    return bool(getattr(websocket, "streamgames_token_ok", False))


def _game_from_path(url_path: str) -> str:
    """Le ?game=... da URL de conexao."""
    query = url_path.split("?", 1)[1] if "?" in url_path else ""
    for part in query.split("&"):
        key, _, value = part.partition("=")
        if key == "game":
            return value.strip().lower()
    return ""


async def process_request(connection: ServerConnection, request: Any) -> Any:
    """Serve o client do jogo na mesma porta do WebSocket."""
    path = getattr(request, "path", "/")
    base_path = path.split("?", 1)[0]

    try:
        upgrade = request.headers.get("Upgrade", "").lower()
    except Exception:  # noqa: BLE001 - header ausente em requisicao malformada
        upgrade = ""
    if upgrade == "websocket":
        expected = config.get_str("GAME_TOKEN")
        # guarda a URL na conexao: e' de onde sai o ?game= e o ?token=
        setattr(connection, "streamgames_path", path)
        setattr(connection, "streamgames_token_ok",
                bool(expected) and secrets.compare_digest(_token_from_path(path), expected))
        return None

    if base_path == "/health":
        return connection.respond(HTTPStatus.OK, json.dumps({
            "ok": True,
            "game": default_game,
            "clients": len(clients),
            "tick": games[default_game].tick,
            "games": {name: {"watchers": len(subscribers(name)), "tick": games[name].tick}
                      for name in sorted(games)},
        }))

    if base_path == "/games":
        return connection.respond(HTTPStatus.OK, json.dumps(
            {"default": DEFAULT_GAME, "games": [GAMES[name]().describe() for name in GAMES]},
            ensure_ascii=False,
        ))

    target = _safe_client_path(path)
    if target is None:
        return connection.respond(HTTPStatus.NOT_FOUND, "Nao encontrado")

    content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
    response = connection.respond(HTTPStatus.OK, target.read_text(encoding="utf-8"))
    del response.headers["Content-Type"]
    response.headers["Content-Type"] = f"{content_type}; charset=utf-8"
    response.headers["Cache-Control"] = "no-store"
    return response


# ---------------------------------------------------------------- game loop
async def game_loop() -> None:
    """Loop fixo de 60 Hz para TODOS os jogos; cada um so transmite a quem assiste."""
    interval = 1 / TICK_RATE
    loop = asyncio.get_running_loop()
    deadline = loop.time()

    while True:
        deadline += interval
        for game_type, game in games.items():
            for event in game.update():
                await broadcast({"type": "game_event", "game": game_type, **event}, game_type)

            if game.tick % BROADCAST_EVERY_TICKS == 0:
                await broadcast({"type": "state", "game": game_type, "state": game.snapshot()}, game_type)

        await asyncio.sleep(max(0.0, deadline - loop.time()))


async def heartbeat() -> None:
    while True:
        await asyncio.sleep(15)
        await broadcast_status()


# --------------------------------------------------------------------- main
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launcher de jogos controlados pela live do TikTok.")
    parser.add_argument("--game", default=config.get_str("GAME") or DEFAULT_GAME,
                        help=f"jogo inicial: {', '.join(sorted(GAMES))} (padrao: {DEFAULT_GAME})")
    parser.add_argument("--port", type=int, help="porta HTTP/WebSocket (padrao: PORT do .env)")
    return parser.parse_args()


async def serve_forever(game_name: str, port: int) -> None:
    """Sobe o servidor. Todos os jogos ficam disponiveis; `game_name` e so o padrao."""
    loop_task = asyncio.create_task(game_loop())
    status_task = asyncio.create_task(heartbeat())

    LOGGER.info("jogos disponiveis: %s", ", ".join(sorted(games)))
    LOGGER.info("padrao: %s - %s", default_game, games[default_game].title)
    LOGGER.info("call to action: %s", games[default_game].call_to_action)
    LOGGER.info("http://localhost:%d/?game=%s", port, default_game)
    if game_name and game_name != default_game and game_name in games:
        LOGGER.warning("--game %s so define o jogo PADRAO (os outros seguem disponiveis)", game_name)

    stop = asyncio.get_running_loop().create_future()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError, AttributeError):
            loop.add_signal_handler(sig, lambda: stop.done() or stop.set_result(None))

    async with serve(handler, host="0.0.0.0", port=port,
                    process_request=process_request, ping_interval=20, ping_timeout=20):
        await stop

    LOGGER.info("encerrando...")
    for task in (loop_task, status_task):
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
                        datefmt="%H:%M:%S")

    game_name = (args.game or DEFAULT_GAME).strip().lower()
    if game_name not in GAMES:
        LOGGER.warning("jogo '%s' inexistente; usando '%s'. disponiveis: %s",
                       game_name, DEFAULT_GAME, ", ".join(sorted(GAMES)))
        game_name = DEFAULT_GAME

    port = args.port or config.get_int("PORT", minimum=1)
    try:
        asyncio.run(serve_forever(game_name, port))
    except KeyboardInterrupt:
        LOGGER.info("interrompido pelo usuario")


if __name__ == "__main__":
    main()
