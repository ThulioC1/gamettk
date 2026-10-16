"""Interface que todo jogo do launcher implementa.

O servidor (HTTP + WebSocket), o bot do TikTok e o simulador falam com o jogo
sempre por estes 4 metodos. Nada aqui sabe o que e uma live ou um Canvas: e so
o contrato entre o nucleo e o modulo de jogo.

Eventos que chegam em `handle_event`:

    {"event": "comment", "user": "nick", "text": "pula!"}
    {"event": "gift",    "user": "nick", "gift": "Rose", "count": 3, "value": 1}
    {"event": "like",    "user": "nick", "count": 5}
    {"event": "follow",  "user": "nick"}
    {"event": "command", "command": "JUMP", "user": "local"}   # teclado / simulador
"""
from __future__ import annotations

from typing import Any, Dict, List


class GameBase:
    """Jogo base: guarda o estado, responde a eventos e produz snapshots."""

    #: identificador usado na URL (?game=corrida) e no log do servidor
    type: str = "base"

    #: titulo mostrado no HUD do navegador
    title: str = "Jogo"

    #: instrucao curta para a live ("comenta pra entrar")
    call_to_action: str = ""

    def __init__(self) -> None:
        self.tick = 0
        self.events_sent = 0

    # ------------------------------------------------------------- entrada
    def handle_event(self, event: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Processa um evento da live. Retorna avisos para o HUD."""
        return []

    # ------------------------------------------------------------- update
    def update(self) -> List[Dict[str, Any]]:
        """Avanca um frame. Retorna eventos como 'winner', 'coin', 'join'."""
        self.tick += 1
        return []

    # --------------------------------------------------------- serializacao
    def snapshot(self) -> Dict[str, Any]:
        """Estado consumido pelo renderer do navegador."""
        return {"tick": self.tick}

    def describe(self) -> Dict[str, Any]:
        """Metadados que o client precisa antes do primeiro snapshot."""
        return {
            "type": self.type,
            "title": self.title,
            "callToAction": self.call_to_action,
        }

    # ------------------------------------------------------------- utilidade
    def reset(self) -> None:
        """Zera a partida (mantendo configuracao e elenco, quando fizer sentido)."""

    @staticmethod
    def clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))
