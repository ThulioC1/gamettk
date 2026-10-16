"""Pipa Arena - cada comentario vira uma pipa no ceu; presente corta linha do rival.

Mecanica:
  - comentar solta uma pipa que sobe e ficaPairando no ceu;
  - cada presente corta linhas de pipas adversarias (as mais altas primeiro),
    e quem estava segurando o ceu com mais pipas sofre mais;
  - pipa sobe com a quantidade de pessoas segurando o ceu no momento
    (mais pipas no ar = mais "corrente"), e desce quando a limpao acontece;
    - quem junta a propria pipa no chao marca pontos e solta uma nova;
  - ao encher o ceu, a partida reinicia.

`kite.y` e a ALTURA da pipa acima do chao (0 = juntada no chao). Quem segura
o ceu e quem tem mais altura: mais pipas = mais "corrente" = mais altura.
"""
from __future__ import annotations

import random
from typing import Any, Dict, List

from server.base import GameBase
from shared import gifts as gift_lib
from shared import pipas as pipa_lib


WORLD_WIDTH = 960
GROUND_Y = 520.0          # onde a pipa e "junada" (chao)
SPAWN_X_MIN = 70.0
SPAWN_X_MAX = 890.0
RELEASE_HEIGHT = 6.0      # a pipa solta logo acima do chao
MAX_ALTITUDE = 400.0      # teto do ceu (altura acima do chao)
SINK_SPEED = 1.2          # queda de uma pipa por frame quando ninguem mais segura
FULL_SKY_FRAMES = 30      # frames com o ceu cheio antes de trocar de rodada
MAX_CUTS = 10             # teto de linhas cortadas por presente (Universo = 40)


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class Kite:
    """Uma pipa no ceu: dono, posicao, altura e se ainda esta presa."""

    __slots__ = ("id", "user", "color", "x", "target_x", "y", "anchored", "points", "cut_count")

    def __init__(self, kite_id: int, user: str, color: str, x: float, y: float) -> None:
        self.id = kite_id
        self.user = user
        self.color = color
        self.x = x
        self.target_x = x
        self.y = y
        self.anchored = False
        self.points = 0
        self.cut_count = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user": self.user,
            "color": self.color,
            "x": round(self.x, 1),
            "y": round(self.y, 1),
            "anchored": self.anchored,
            "points": self.points,
            "cuts": self.cut_count,
        }


class PipaArena(GameBase):
    type = "pipa"
    title = "Pipa Arena"
    call_to_action = "Cada comentario solta uma pipa. Presentes cortam as linhas dos rivais!"

    def __init__(self) -> None:
        super().__init__()
        self.arena = pipa_lib.load()
        self.title = self.arena.title
        self.kites: List[Kite] = []
        self.fallen: List[Dict[str, Any]] = []   # destrocos de linha cortada
        self.next_id = 1
        self.total_flights = 0
        self.best_height = 0.0
        self.random = random.Random(99)
        self.restart_in = 0

    # ------------------------------------------------------------------ estado
    def reset(self) -> None:
        self.kites.clear()
        self.fallen.clear()
        self.total_flights = 0
        self.best_height = 0.0
        self.restart_in = 0

    @property
    def ceiling_load(self) -> int:
        """Quantas pessoas estao segurando o ceu agora (pipas no ar)."""
        return len(self.kites)

    # ----------------------------------------------------------------- entrada
    def handle_event(self, event: Dict[str, Any]) -> List[Dict[str, Any]]:
        kind = event.get("event")
        user = str(event.get("user") or "anon")[:24]

        if kind == "comment":
            return [self._launch(user)]
        if kind == "gift":
            return self._cut(user, event.get("gift"), _as_int(event.get("count"), 1),
                              _as_int(event.get("value"), 0))
        if kind == "like":
            return []
        if kind in {"follow", "share"}:
            return [self._launch(user)]
        return []

    def _launch(self, user: str) -> Dict[str, Any]:
        """Solta uma pipa nova no ceu."""
        x = round(self.random.uniform(SPAWN_X_MIN, SPAWN_X_MAX), 1)
        kite = Kite(
            kite_id=self.next_id,
            user=user[:16],
            color=pipa_lib.color_for(self.next_id),
            x=x,
            y=RELEASE_HEIGHT,
        )
        self.next_id += 1
        self.total_flights += 1
        self.kites.append(kite)

        # ceu cheio: quem estava mais alto perde o lugar
        while len(self.kites) > self.arena.max_kites:
            victim = max(self.kites, key=lambda item: item.y)
            self.kites.remove(victim)
            self._drop(victim)

        return {"kind": "launch", "user": user, "color": kite.color, "message": f"{user} SOLTOU UMA PIPA"}

    def _cut(self, user: str, gift_name: Any, count: int, coins: int) -> List[Dict[str, Any]]:
        """Presente corta linhas: as pipas mais altas primeiro."""
        gift_info = gift_lib.describe(str(gift_name) if gift_name else None, coins)
        effect = str(gift_info["effect"])
        spec = self.arena.gifts.get(effect, {})
        multiplier = int(gift_info["multiplier"]) * max(1, min(count, 3))
        cuts = self.clamp(max(1, spec.get("cuts", 1)) * multiplier, 1, MAX_CUTS)

        victim_lines: List[str] = []
        for kite in sorted(self.kites, key=lambda item: item.y, reverse=True):
            if kite.user == user or len(victim_lines) >= self.arena.rival_rivals:
                continue
            victim_lines.append(kite.user[:16])

        cut = 0
        for line in victim_lines:
            same_line = [k for k in self.kites if k.user == line]
            for _ in range(cuts):
                if not same_line:
                    break
                victim = max(same_line, key=lambda item: item.y)
                same_line.remove(victim)
                self.kites.remove(victim)
                victim.cut_count += 1
                cut += 1

        message = spec.get("message") or f"CORTOU {cut} LINHA(S)!"
        if cut == 0:
            message = "NINGUEM PARA CORTAR"
        elif gift_info["coins"]:
            message = f"{message} ({gift_info['tier']}, {gift_info['coins']} moedas)"
        return [{"kind": "cut", "user": user, "cuts": cut, "lines": victim_lines,
                 "coins": gift_info["coins"], "tier": gift_info["tier"], "message": message}]

    def _drop(self, kite: Kite) -> None:
        """A pipa cai: vira destroco e some do ceu."""
        self.fallen.append({
            "x": kite.x, "y": kite.y, "vx": self.random.uniform(-1.5, 1.5),
            "vy": -1.0, "color": kite.color, "user": kite.user, "life": 1,
        })

    # ------------------------------------------------------------------ update
    def update(self) -> List[Dict[str, Any]]:
        super().update()
        events: List[Dict[str, Any]] = []

        # Quanto mais gente segura o ceu, mais corrente de ar: com poucas pipas
        # ninguem aguenta e elas caem. Por isso cortar linhas derruba o rival.
        rise = self.arena.kite_speed * max(1, self.ceiling_load)
        net = rise - SINK_SPEED

        for kite in list(self.kites):
            kite.y = self.clamp(kite.y + net, 0.0, MAX_ALTITUDE)
            kite.x += (kite.target_x - kite.x) * 0.04

            if kite.y <= 0:  # juntou a pipa no chao
                kite.anchored = True
                kite.points += 10
                self.kites.remove(kite)
                events.append({"kind": "land", "user": kite.user, "color": kite.color,
                                "points": kite.points, "message": f"{kite.user} JUNTOU A PIPA (+10)"})

        survivors: List[Dict[str, Any]] = []
        for piece in self.fallen:
            piece["vy"] += 0.25
            piece["life"] -= 0.01
            if piece["life"] > 0:
                survivors.append(piece)
        self.fallen = survivors

        self.best_height = max([self.best_height] + [kite.y for kite in self.kites])

        if len(self.kites) >= self.arena.max_kites:
            self.restart_in += 1
            if self.restart_in >= FULL_SKY_FRAMES:
                self.reset()
                events.append({"kind": "restart", "message": "CEU LIMPO! OUTRA RODADA!"})

        return events

    # -------------------------------------------------------------- serializacao
    def snapshot(self) -> Dict[str, Any]:
        holders = sorted(self.kites, key=lambda item: item.y)
        return {
            "tick": self.tick,
            "title": self.arena.title,
            "world": {"width": WORLD_WIDTH, "groundY": GROUND_Y, "maxAltitude": MAX_ALTITUDE},
            "kites": [kite.to_dict() for kite in holders],
            "fallen": self.fallen,
            "leaders": [
                {"user": item.user, "points": item.points, "y": round(item.y, 1)}
                for item in sorted(holders, key=lambda item: item.y, reverse=True)[:5]
            ],
            "load": self.ceiling_load,
            "maxKites": self.arena.max_kites,
            "totalFlights": self.total_flights,
            "bestHeight": round(self.best_height, 1),
            "restartIn": self.restart_in,
        }

    def describe(self) -> Dict[str, Any]:
        info = super().describe()
        info.update({
            "title": self.arena.title,
            "callToAction": self.call_to_action,
            "maxKites": self.arena.max_kites,
            "giftEffects": {effect: dict(spec) for effect, spec in self.arena.gifts.items()},
        })
        return info
