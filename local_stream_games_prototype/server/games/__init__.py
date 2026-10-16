"""Modulos de jogo do launcher.

Cada modulo implementa `server.base.GameBase` e e escolhido pelo servidor com
`python3 server/server.py --game <nome>` ou `?game=<nome>` no navegador.
"""
from __future__ import annotations

from typing import Dict, Type

from server.base import GameBase
from server.games.corrida import Corrida
from server.games.duelo import Duelo
from server.games.pipa_arena import PipaArena
from server.games.platformer import Platformer

#: nome usado na URL -> classe do jogo
GAMES: Dict[str, Type[GameBase]] = {
    Corrida.type: Corrida,
    Duelo.type: Duelo,
    PipaArena.type: PipaArena,
    Platformer.type: Platformer,
}

DEFAULT_GAME = Corrida.type


def build(name: str | None = None) -> GameBase:
    """Instancia o jogo pedido; cai no padrao se o nome nao existir."""
    game_class = GAMES.get((name or DEFAULT_GAME).strip().lower(), GAMES[DEFAULT_GAME])
    return game_class()


__all__ = ["GAMES", "DEFAULT_GAME", "build", "Corrida", "Duelo", "PipaArena", "Platformer", "GameBase"]
