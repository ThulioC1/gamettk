"""Duelo de Torres - duas torres, dois lados, o chat decide quem sobe mais rapido.

Regras:
  - comentar pela 1a vez coloca a pessoa num lado (pela palavra que escreveu,
    senao pelo lado que estiver mais baixo);
  - cada comentario vira 1 bloco na torre da pessoa;
  - presentes valem varios blocos (NITRO/TURBO) ou derrubam bloco do rival (OIL);
  - bloco mal posicionado escorrega e cai, e o excesso deBlocks fora do lugar
    inclina a torre ate ela desabar;
  - quem chegar na altura alvo primeiro vence, e a partida reinicia.
"""
from __future__ import annotations

import random
from typing import Any, Dict, List, Optional

from server.base import GameBase
from shared import gifts as gift_lib
from shared import sides as sides_lib

TOWER_WIDTH = 320.0
BLOCK_WIDTH = 250.0
BASE_Y = 512.0            # base das torres no canvas 960x540
SLIDE_LIMIT = 42.0        # deslocamento maximo antes do bloco escorregar
BLOCK_JITTER = 14.0       # quanto o bloco "anda" de um nivel para o outro
LEAN_DECAY = 0.0055       # quanto a inclinacao se recupera por frame
LEAN_PER_OFFSET = 0.16    # inclinacao por bloco deslocado
LEAN_COLLAPSE = 1.0       # a partir daqui a torre desaba
COLLAPSE_BLOCKS = 4       # quanto cai quando desaba
MAX_GIFT_BLOCKS = 16      # teto de blocos por presente (Universo TikTok = 40, corta em 16)
MAX_SABOTAGE_BLOCKS = 12  # teto de blocos derrubados do rival por presente
RESTART_DELAY_FRAMES = 420


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class Tower:
    """Uma torre: pilha de blocos, inclinacao e quem a sustenta."""

    def __init__(self, side: sides_lib.Side) -> None:
        self.side = side
        self.blocks: List[Dict[str, Any]] = []
        self.lean = 0.0
        self.drop_offset = 0.0   # deslocamento do proximo bloco
        self.supporter = ""
        self.won = False

    @property
    def height(self) -> int:
        return len(self.blocks)

    def top_y(self, block_height: int) -> float:
        return BASE_Y - len(self.blocks) * block_height

    def reset(self) -> None:
        self.blocks.clear()
        self.lean = 0.0
        self.drop_offset = 0.0
        self.supporter = ""
        self.won = False


class Duelo(GameBase):
    type = "duelo"
    call_to_action = "Comente 'lula' ou 'flavio' para escolher seu lado. Cada comentario ergue 1 bloco!"

    def __init__(self) -> None:
        super().__init__()
        self.duel = sides_lib.load()
        self.title = self.duel.title
        self.towers = [Tower(side) for side in self.duel.sides]
        self.supporter_of: Dict[str, str] = {}   # user -> side id
        self.restart_in = 0
        self.winner: Optional[str] = None
        self.pending_event: Optional[Dict[str, Any]] = None
        self.random = random.Random(4242)        # partida reproduzivel em teste

    # ------------------------------------------------------------------ estado
    def _tower(self, side_id: str) -> Optional[Tower]:
        return next((tower for tower in self.towers if tower.side.id == side_id), None)

    def _lowest_tower(self) -> Tower:
        """Escolhe o lado mais fraco para balancear quem nao escreveu palavra."""
        return min(self.towers, key=lambda tower: tower.height)

    def reset(self) -> None:
        for tower in self.towers:
            tower.reset()
        self.restart_in = 0
        self.winner = None

    # ----------------------------------------------------------------- entrada
    def handle_event(self, event: Dict[str, Any]) -> List[Dict[str, Any]]:
        kind = event.get("event")
        user = str(event.get("user") or "anon")[:24]
        if self.winner is not None:
            return []

        if kind == "comment":
            return self._on_comment(user, str(event.get("text", ""))[:80])
        if kind == "gift":
            return self._on_gift(user, event.get("gift"),
                                 _as_int(event.get("count"), 1), _as_int(event.get("value"), 0))
        if kind in {"follow", "share"}:
            return self._on_comment(user, "")
        if kind == "like":
            return []
        return []

    def _pick_side(self, user: str, text: str) -> tuple[Tower, bool]:
        """Define o lado da pessoa. Devolve (torre, trocou_de_lado?)."""
        asked = sides_lib.side_from_text(text, self.duel)
        current_id = self.supporter_of.get(user)

        if asked is not None:
            switched = current_id is not None and current_id != asked.id
            self.supporter_of[user] = asked.id
            return self._tower(asked.id) or self._lowest_tower(), switched

        if current_id is not None:
            return self._tower(current_id) or self._lowest_tower(), False

        # entrou sem dizer o lado: vai para o mais baixo, para a disputa ficar pareada
        tower = self._lowest_tower() if self.random.random() < 0.65 else self.random.choice(self.towers)
        self.supporter_of[user] = tower.side.id
        return tower, False

    def _on_comment(self, user: str, text: str) -> List[Dict[str, Any]]:
        tower, switched = self._pick_side(user, text)
        notices: List[Dict[str, Any]] = [
            {"kind": "side", "side": tower.side.id, "user": user,
             "message": f"{user} -> {tower.side.label()}"}
        ]

        placed, fallen = self._stack(tower, user, blocks=1)
        if placed:
            notices.append({
                "kind": "block", "side": tower.side.id, "blocks": placed, "user": user,
                "height": tower.height, "message": f"{tower.side.party or tower.side.name.upper()} +{placed}",
            })
        else:
            notices.append({"kind": "slide", "side": tower.side.id, "user": user,
                            "message": f"{user} ESCORREGA!"})

        if switched:
            notices.append({"kind": "switch", "side": tower.side.id, "user": user,
                            "message": f"{user} TROCOU DE LADO"})
        return notices

    def _on_gift(self, user: str, gift_name: Any, count: int, coins: int) -> List[Dict[str, Any]]:
        gift_info = gift_lib.describe(str(gift_name) if gift_name else None, coins)
        effect = str(gift_info["effect"])
        multiplier = int(gift_info["multiplier"]) * self.clamp(count, 1, 3)
        spec = self.duel.gifts.get(effect, {})
        tower, _ = self._pick_side(user, "")

        notice = {
            "kind": "gift", "side": tower.side.id, "user": user,
            "coins": gift_info["coins"], "tier": gift_info["tier"],
        }

        if "sabotage" in spec:  # OIL: derruba blocos do adversario
            rival = next((other for other in self.towers if other.side.id != tower.side.id), None)
            dropped = 0
            if rival is not None:
                dropped = min(len(rival.blocks),
                              self.clamp(spec["sabotage"] * multiplier, 1, MAX_SABOTAGE_BLOCKS))
                for block in rival.blocks[-dropped:]:
                    block["dropped"] = True
                if dropped:
                    del rival.blocks[-dropped:]
                rival.lean = min(LEAN_COLLAPSE, rival.lean + 0.1 * dropped)
            notice.update({
                "kind": "sabotage",
                "side": rival.side.id if rival else tower.side.id,
                "blocks": dropped,
                "message": f"{spec.get('message', 'SABOTAGEM')} -{dropped}",
            })
            return [notice]

        blocks = self.clamp(spec.get("blocks", 1) * multiplier, 1, MAX_GIFT_BLOCKS)
        placed, _ = self._stack(tower, user, blocks=blocks)
        message = spec.get("message") or f"+{blocks} BLOCOS"
        if placed != blocks:  # parte dos blocos escorregou
            message = f"{message} ({placed} firmes)"
        notice.update({
            "blocks": placed, "height": tower.height,
            "message": f"{tower.side.party or tower.side.name.upper()} {message}",
        })
        return [notice]

    # ----------------------------------------------------------------- pilha
    def _stack(self, tower: Tower, user: str, blocks: int) -> tuple[int, int]:
        """Empilha blocos; devolve (colocados, escorregados)."""
        placed = 0
        fallen = 0

        for _ in range(max(0, blocks)):
            offset = tower.drop_offset + self.random.uniform(-BLOCK_JITTER, BLOCK_JITTER)
            offset = self.clamp(offset, -SLIDE_LIMIT, SLIDE_LIMIT)

            if abs(offset) >= SLIDE_LIMIT - 1.5:  # no limite: o bloco escorrega
                tower.drop_offset = 0.0
                tower.lean = min(LEAN_COLLAPSE, tower.lean + LEAN_PER_OFFSET * 2)
                fallen += 1
                continue

            tower.blocks.append({
                "offset": round(offset, 1),
                "by": user[:16],
                "at": self.tick,
                "dropped": False,
            })
            tower.supporter = user[:16]
            tower.drop_offset = offset
            tower.lean = min(LEAN_COLLAPSE, tower.lean + abs(offset) / SLIDE_LIMIT * LEAN_PER_OFFSET)
            placed += 1

        if tower.height >= self.duel.target_blocks:
            self._declare_winner(tower)
        elif tower.lean >= LEAN_COLLAPSE:
            self._collapse(tower)
        return placed, fallen

    def _collapse(self, tower: Tower) -> None:
        """A torre desaba: cai a ponta e a inclinacao volta pela metade."""
        falling = min(COLLAPSE_BLOCKS, tower.height)
        for block in tower.blocks[-falling:]:
            block["dropped"] = True
        if falling:
            del tower.blocks[-falling:]
        tower.lean = LEAN_COLLAPSE * 0.45
        tower.drop_offset = 0.0
        self.pending_event = {"kind": "collapse", "side": tower.side.id, "blocks": falling,
                              "message": f"{tower.side.name.upper()} DESABOU!"}

    def _declare_winner(self, tower: Tower) -> None:
        tower.won = True
        tower.lean = 0.0
        self.winner = tower.side.id
        self.restart_in = RESTART_DELAY_FRAMES
        self.pending_event = {
            "kind": "winner",
            "side": tower.side.id,
            "blocks": tower.height,
            "message": f"{tower.side.name.upper()} VENCEU O DUELO!",
        }

    # ------------------------------------------------------------------ update
    def update(self) -> List[Dict[str, Any]]:
        super().update()
        events: List[Dict[str, Any]] = []

        # A vitoria pode ter vindo de um comando entre dois frames: sempre
        # despacha o que estiver pendente, mesmo com o duelo ja encerrado.
        if self.winner is not None:
            events += self._drain()
            self.restart_in -= 1
            if self.restart_in <= 0:
                self.reset()
                events.append({"kind": "restart", "message": "NOVO DUELO!"})
            return events

        for tower in self.towers:
            # checa o desabamento antes de aliviar: lean chega em LEAN_COLLAPSE
            # por acumulo de blocos tortos, e a recuperacao nunca deve mascará-lo.
            if tower.lean >= LEAN_COLLAPSE:
                self._collapse(tower)
            else:
                tower.lean = max(0.0, tower.lean - LEAN_DECAY)

        return events + self._drain()

    def _drain(self) -> List[Dict[str, Any]]:
        """Entrega (e limpa) o evento acumulado desde o ultimo frame."""
        if not self.pending_event:
            return []
        event, self.pending_event = self.pending_event, None
        return [event]

    # -------------------------------------------------------------- serializacao
    def snapshot(self) -> Dict[str, Any]:
        block_height = self.duel.block_height
        return {
            "tick": self.tick,
            "title": self.duel.title,
            "targetBlocks": self.duel.target_blocks,
            "blockHeight": block_height,
            "towerWidth": TOWER_WIDTH,
            "blockWidth": BLOCK_WIDTH,
            "baseY": BASE_Y,
            "towers": [
                {
                    "side": tower.side.to_dict(),
                    "blocks": tower.blocks,
                    "height": tower.height,
                    "lean": round(tower.lean, 3),
                    "supporter": tower.supporter,
                    "won": tower.won,
                    "supporters": sum(1 for side_id in self.supporter_of.values() if side_id == tower.side.id),
                }
                for tower in self.towers
            ],
            "winner": self.winner,
            "restartIn": self.restart_in,
        }

    def describe(self) -> Dict[str, Any]:
        info = super().describe()
        info.update({
            "title": self.duel.title,
            "callToAction": self.call_to_action,
            "targetBlocks": self.duel.target_blocks,
            "sides": [side.to_dict() for side in self.duel.sides],
            "giftEffects": {effect: dict(spec) for effect, spec in self.duel.gifts.items()},
        })
        return info
