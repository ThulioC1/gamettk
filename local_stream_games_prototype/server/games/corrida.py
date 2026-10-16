"""Corrida na Live - "quem comenta entra na pista; presentes viram nitro e óleo".

Cada pessoa que comenta pela primeira vez ganha um carro. Comentar de novo ou
mandar presente acelera o carro da pessoa. Nao existe direcao: o carro dirige
sozinho, a live inteira disputa a corrida.
"""
from __future__ import annotations

import random
from typing import Any, Dict, List, Optional

from server.base import GameBase
from shared import config
from shared import gifts as gift_lib

# ------------------------------------------------------------------ tuning
TRACK_LENGTH = config.get_int("TRACK_LENGTH", minimum=200)          # px de pista
BASE_SPEED = config.get_int("CAR_BASE_SPEED", minimum=1) / 10.0     # px por frame
MAX_CARS = config.get_int("CAR_MAX", minimum=1)
COMMENT_BOOST = config.get_int("COMMENT_BOOST", minimum=0) / 10.0   # px/frame por comentario
NITRO_BOOST = config.get_int("NITRO_BOOST", minimum=0) / 10.0
TURBO_BOOST = config.get_int("TURBO_BOOST", minimum=0) / 10.0
BOOST_FRAMES = config.get_int("BOOST_FRAMES", minimum=5)
SPIN_FRAMES = config.get_int("SPIN_FRAMES", minimum=5)
RESTART_DELAY_FRAMES = config.get_int("RESTART_DELAY_FRAMES", minimum=30)
POINT_PER_COMMENT = config.get_int("POINT_PER_COMMENT", minimum=0)

CAR_COLORS = ["#22d3ee", "#3b82f6", "#ec4899", "#fbbf24", "#a78bfa", "#34d399", "#f97316", "#f43f5e"]
CAR_NAMES = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

# Tetos: presente caro aumenta o efeito, mas nao quebra a corrida.
MAX_BOOST = TURBO_BOOST * 8
MAX_BOOST_FRAMES = BOOST_FRAMES * 4
MAX_OIL_SLICKS = 4
OIL_LIFETIME = 1200


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class Car:
    """Um carro da pista: dono, posicao, velocidade e efeitos temporarios."""

    __slots__ = ("user", "name", "number", "color", "dist", "speed", "boost",
                 "boost_left", "spin_left", "points", "finished_at", "place")

    def __init__(self, user: str, name: str, number: int, color: str) -> None:
        self.user = user
        self.name = name
        self.number = number
        self.color = color
        self.dist = 0.0
        self.speed = 0.0
        self.boost = 0.0
        self.boost_left = 0
        self.spin_left = 0
        self.points = 0
        self.finished_at: Optional[int] = None
        self.place = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user": self.user,
            "name": self.name,
            "number": self.number,
            "color": self.color,
            "dist": round(self.dist, 1),
            "speed": round(self.speed, 2),
            "boost": round(self.boost, 2),
            "spinning": self.spin_left > 0,
            "points": self.points,
            "place": self.place,
            "finished": self.finished_at is not None,
        }


class Corrida(GameBase):
    type = "corrida"
    title = "Corrida na Live"
    call_to_action = "Comente qualquer coisa pra entrar na pista. Manda presente pra acelerar!"

    def __init__(self) -> None:
        super().__init__()
        self.cars: List[Car] = []
        self.oils: List[Dict[str, Any]] = []
        self.restart_in = 0
        self.winner: Optional[Dict[str, Any]] = None
        self.last_joiner: Optional[str] = None
        self.finished_count = 0
        self.random = random.Random(1234)  # partida reproduzivel em teste

    # ------------------------------------------------------------------ reset
    def reset(self) -> None:
        self.oils.clear()
        self.restart_in = 0
        self.winner = None
        self.last_joiner = None
        self.finished_count = 0
        for car in self.cars:
            car.dist = 0.0
            car.speed = 0.0
            car.boost = 0.0
            car.boost_left = 0
            car.spin_left = 0
            car.finished_at = None
            car.place = 0

    # ----------------------------------------------------------------- entrada
    def handle_event(self, event: Dict[str, Any]) -> List[Dict[str, Any]]:
        kind = event.get("event")
        user = str(event.get("user") or "anon")[:24]
        notices: List[Dict[str, Any]] = []

        if kind == "comment":
            notices.extend(self._on_comment(user, str(event.get("text", ""))[:60]))
        elif kind == "gift":
            notices.extend(self._on_gift(user, event.get("gift"), _as_int(event.get("count"), 1),
                                         _as_int(event.get("value"), 0)))
        elif kind == "follow":
            notices.extend(self._on_comment(user, "follow"))
        elif kind == "like":
            notices.extend(self._on_like(user, int(event.get("count", 1) or 1)))
        # 'command' e especifico do platformer: aqui nao faz nada

        return notices

    def _car_of(self, user: str) -> Optional[Car]:
        for car in self.cars:
            if car.user == user:
                return car
        return None

    def _add_car(self, user: str) -> Car:
        number = len(self.cars) % len(CAR_NAMES) + 1
        color = CAR_COLORS[len(self.cars) % len(CAR_COLORS)]
        car = Car(user=user, name=user, number=number, color=color)
        # quem entra depois comeca um pouco atras: a pista nunca fica vazia no inicio
        car.dist = -self.random.uniform(0, 60)
        self.cars.append(car)

        # pista cheia: sai quem esta mais atras (o novo nunca e expulso)
        if len(self.cars) > MAX_CARS:
            oldest = self.cars[1:]
            self.cars.remove(min(oldest, key=lambda car: car.dist))

        self.last_joiner = user
        return car

    def _on_comment(self, user: str, text: str) -> List[Dict[str, Any]]:
        car = self._car_of(user)
        joined = car is None
        if car is None:
            car = self._add_car(user)

        car.points += POINT_PER_COMMENT
        car.boost = max(car.boost, COMMENT_BOOST)
        car.boost_left = max(car.boost_left, BOOST_FRAMES // 3)

        return [
            {
                "kind": "join" if joined else "comment",
                "user": user,
                "text": text,
                "message": f"{user} ENTROU NA PISTA!" if joined else None,
            }
        ]

    def _on_gift(self, user: str, gift_name: Any, count: int, event_coins: int) -> List[Dict[str, Any]]:
        gift_info = gift_lib.describe(str(gift_name) if gift_name else None, event_coins)
        effect = str(gift_info["effect"])
        multiplier = int(gift_info["multiplier"]) * self.clamp(count, 1, 3)
        car = self._car_of(user) or self._add_car(user)
        car.points += 10 * multiplier

        notice = {
            "kind": "gift", "user": user, "gift": gift_name, "effect": effect,
            "coins": gift_info["coins"], "tier": gift_info["tier"],
            "message": f"{gift_info['label']} ({gift_info['tier']})",
        }

        if effect == gift_lib.OIL:
            # um presente caro derruba mais faixa de oleo na pista
            for index in range(min(multiplier, MAX_OIL_SLICKS)):
                self.oils.append({
                    "dist": max(car.dist - 70 - index * 45, -140),
                    "owner": user,
                    "life": OIL_LIFETIME,
                })
            return [notice]

        base_boost = TURBO_BOOST if effect == gift_lib.TURBO else NITRO_BOOST
        car.boost = min(max(car.boost, base_boost * multiplier), MAX_BOOST)
        car.boost_left = min(max(car.boost_left, BOOST_FRAMES + (multiplier - 1) * 20), MAX_BOOST_FRAMES)
        if effect == gift_lib.TURBO:
            car.dist += 60 * multiplier  # ultrapassagem: ganha posicao na hora
        return [notice]

    def _on_like(self, user: str, count: int) -> List[Dict[str, Any]]:
        car = self._car_of(user)
        if car is None:
            return []
        car.points += count
        return []

    # ------------------------------------------------------------------ update
    def update(self) -> List[Dict[str, Any]]:
        super().update()
        events: List[Dict[str, Any]] = []

        if self.winner is not None:
            self.restart_in -= 1
            if self.restart_in <= 0:
                self.reset()
                events.append({"kind": "restart", "message": "NOVA CORRIDA!"})
            return events

        for oil in self.oils:
            oil["life"] -= 1
        self.oils = [oil for oil in self.oils if oil["life"] > 0]

        finished: List[Car] = []

        for car in self.cars:
            if car.boost_left > 0:
                car.boost_left -= 1
                if car.boost_left == 0:
                    car.boost = 0.0

            if car.spin_left > 0:
                car.spin_left -= 1
                car.speed = 0.0
            else:
                car.speed = BASE_SPEED + car.boost

            previous = car.dist
            car.dist += car.speed

            # derrapou no oleo?
            for oil in self.oils:
                if abs(oil["dist"] - previous) <= 40 and abs(car.dist - oil["dist"]) < 40:
                    car.spin_left = SPIN_FRAMES
                    car.boost = 0.0
                    car.boost_left = 0
                    self.oils.remove(oil)
                    events.append({"kind": "spill", "user": car.name, "message": f"{car.name} DERRAPOU!"})
                    break

            if car.dist >= TRACK_LENGTH and car.finished_at is None:
                car.finished_at = self.tick
                finished.append(car)

        if finished:
            for car in sorted(finished, key=lambda car: car.finished_at or 0):
                self.finished_count += 1
                car.place = self.finished_count
            champion = min(finished, key=lambda car: car.finished_at or 0)
            self.winner = {
                "user": champion.name,
                "place": champion.place,
                "points": champion.points,
            }
            self.restart_in = RESTART_DELAY_FRAMES
            events.append({"kind": "winner", "user": champion.name, "message": f"{champion.name} VENCEU!"})

        return events

    # -------------------------------------------------------------- serializacao
    def snapshot(self) -> Dict[str, Any]:
        ordered = sorted(self.cars, key=lambda car: car.dist, reverse=True)
        for index, car in enumerate(ordered, start=1):
            if not car.finished_at:
                car.place = index
        return {
            "tick": self.tick,
            "trackLength": TRACK_LENGTH,
            "cars": [car.to_dict() for car in ordered],
            "oils": [{"dist": round(oil["dist"], 1)} for oil in self.oils],
            "winner": self.winner,
            "restartIn": self.restart_in,
            "lastJoiner": self.last_joiner,
            "baseSpeed": BASE_SPEED,
        }

    def describe(self) -> Dict[str, Any]:
        info = super().describe()
        info.update({
            "maxCars": MAX_CARS,
            "effects": gift_lib.EFFECT_LABELS,
            "pointPerComment": POINT_PER_COMMENT,
        })
        return info
