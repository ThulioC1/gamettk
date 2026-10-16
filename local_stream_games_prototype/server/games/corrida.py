"""Corrida na Live - "quem comenta entra na pista; presentes viram nitro e óleo".

Como a da plataforma: contagem regressiva, grid de largada, carros em faixas,
placa com numero/nome/km/h e um catalogo (Gol, Uno, Fusca, motos).

  - comentar pela 1a vez coloca a pessoa na pista, no carro que ela pediu
    ("tenho um gol") ou num sorteado;
  - comentar de novo ou_presentar acelera o carro da pessoa;
  - nitro = impulso, turbo = impulso + posicao, oleo = derrapa quem passar;
  - o primeiro a cruzar a chegada vence e a corrida recomeca com contagem.
"""
from __future__ import annotations

import random
from typing import Any, Dict, List, Optional

from server.base import GameBase
from shared import carros as carro_lib
from shared import config
from shared import gifts as gift_lib

# ------------------------------------------------------------------ tuning
TRACK_LENGTH = config.get_int("TRACK_LENGTH", minimum=0) or 5000
BASE_SPEED = config.get_int("CAR_BASE_SPEED", minimum=1) / 10.0   # px por frame
MAX_CARS = config.get_int("CAR_MAX", minimum=1)
COMMENT_BOOST = config.get_int("COMMENT_BOOST", minimum=0) / 10.0
NITRO_BOOST = config.get_int("NITRO_BOOST", minimum=0) / 10.0
TURBO_BOOST = config.get_int("TURBO_BOOST", minimum=0) / 10.0
BOOST_FRAMES = config.get_int("BOOST_FRAMES", minimum=5)
SPIN_FRAMES = config.get_int("SPIN_FRAMES", minimum=5)
RESTART_DELAY_FRAMES = config.get_int("RESTART_DELAY_FRAMES", minimum=30)
POINT_PER_COMMENT = config.get_int("POINT_PER_COMMENT", minimum=0)

COUNTDOWN_SECONDS = config.get_int("COUNTDOWN_SECONDS", minimum=0) or 10
GRID_COLUMNS = config.get_int("GRID_COLUMNS", minimum=2)
GRID_COLUMN_GAP = config.get_int("GRID_COLUMN_GAP", minimum=40)
GRID_ROW_GAP = config.get_int("GRID_ROW_GAP", minimum=80)
LANES = config.get_int("CAR_LANES", minimum=1)

MAX_BOOST = TURBO_BOOST * 8
MAX_BOOST_FRAMES = BOOST_FRAMES * 4
MAX_OIL_SLICKS = 4
OIL_LIFETIME = 1200

#: px/frame -> km/h (velocidade de referencia: 4.5 px/frame = ~180 km/h)
KMH_FACTOR = config.get_int("KMH_FACTOR", minimum=1)

PHASE_COUNTDOWN = "countdown"
PHASE_RACING = "racing"
PHASE_OVER = "over"


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class Car:
    """Um carro da pista: dono, veiculo, posicao, faixa e velocidade."""

    __slots__ = ("user", "name", "number", "lane", "color", "dark", "vehicle", "vehicle_name",
                 "is_moto", "dist", "speed", "boost", "boost_left", "spin_left", "points",
                 "finished_at", "place")

    def __init__(self, user: str, number: int, lane: int, veiculo: carro_lib.Veiculo) -> None:
        self.user = user
        self.name = user
        self.number = number
        self.lane = lane
        self.vehicle = veiculo.id
        self.vehicle_name = veiculo.name
        self.is_moto = veiculo.type == "moto"
        self.color = veiculo.color
        self.dark = veiculo.dark
        self.dist = 0.0
        self.speed = 0.0
        self.boost = 0.0
        self.boost_left = 0
        self.spin_left = 0
        self.points = 0
        self.finished_at: Optional[int] = None
        self.place = 0

    def kmh(self) -> int:
        return int(round(abs(self.speed) * KMH_FACTOR))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user": self.user,
            "name": self.name,
            "number": self.number,
            "lane": self.lane,
            "vehicle": self.vehicle,
            "vehicleName": self.vehicle_name,
            "isMoto": self.is_moto,
            "color": self.color,
            "dark": self.dark,
            "dist": round(self.dist, 1),
            "speed": round(self.speed, 2),
            "kmh": self.kmh(),
            "boost": round(self.boost, 2),
            "spinning": self.spin_left > 0,
            "points": self.points,
            "place": self.place,
            "finished": self.finished_at is not None,
        }


class Corrida(GameBase):
    type = "corrida"
    call_to_action = ("Comente pra entrar na pista (ou escreva o carro: \"gol\", \"moto biz\"). "
                      "Presente acelera!")

    def __init__(self) -> None:
        super().__init__()
        self.catalogo = carro_lib.load()
        self.title = self.catalogo.title
        self.cars: List[Car] = []
        self.oils: List[Dict[str, Any]] = []
        self.restart_in = 0
        self.winner: Optional[Dict[str, Any]] = None
        self.last_joiner: Optional[str] = None
        self.phase = PHASE_COUNTDOWN
        self.countdown = COUNTDOWN_SECONDS * 60
        self.random = random.Random(1234)  # partida reproduzivel em teste

    # ------------------------------------------------------------------ reset
    def reset(self) -> None:
        self.oils.clear()
        self.restart_in = 0
        self.winner = None
        self.last_joiner = None
        self.phase = PHASE_COUNTDOWN
        self.countdown = COUNTDOWN_SECONDS * 60
        for index, car in enumerate(self.cars):
            car.dist = -self._grid_offset(index)
            car.speed = 0.0
            car.boost = 0.0
            car.boost_left = 0
            car.spin_left = 0
            car.finished_at = None
            car.place = 0

    @staticmethod
    def _grid_offset(index: int) -> float:
        """Posicao no grid de largada: 8 colunas x N faixas, atras da linha."""
        row = index // GRID_COLUMNS
        column = index % GRID_COLUMNS
        return row * GRID_ROW_GAP + column * GRID_COLUMN_GAP + 30.0

    # ----------------------------------------------------------------- entradas
    def handle_event(self, event: Dict[str, Any]) -> List[Dict[str, Any]]:
        kind = event.get("event")
        user = str(event.get("user") or "anon")[:24]
        notices: List[Dict[str, Any]] = []

        if kind == "comment":
            notices.extend(self._on_comment(user, str(event.get("text", ""))[:60]))
        elif kind == "gift":
            notices.extend(self._on_gift(user, event.get("gift"), _as_int(event.get("count"), 1),
                                         _as_int(event.get("value"), 0)))
        elif kind in {"follow", "share"}:
            # seguir e compartilhar alimentam a pista como um comentário
            notices.extend(self._on_comment(user, kind))
        elif kind == "like":
            notices.extend(self._on_like(user, _as_int(event.get("count"), 1)))
        # 'command' e especifico do platformer: aqui nao faz nada

        return notices

    def _car_of(self, user: str) -> Optional[Car]:
        for car in self.cars:
            if car.user == user:
                return car
        return None

    def _add_car(self, user: str, veiculo: carro_lib.Veiculo) -> Car:
        index = len(self.cars)
        lane = index % LANES
        car = Car(user=user, number=index % 99 + 1, lane=lane, veiculo=veiculo)
        car.dist = -self._grid_offset(index)
        self.cars.append(car)

        # pista cheia: sai quem esta mais atras (o novo nunca e expulso)
        if len(self.cars) > MAX_CARS:
            self.cars.remove(min(self.cars[1:], key=lambda car: car.dist))

        self.last_joiner = user
        return car

    def _on_comment(self, user: str, text: str) -> List[Dict[str, Any]]:
        car = self._car_of(user)
        joined = car is None

        if car is None:
            pedido = carro_lib.from_text(text, self.catalogo)
            veiculo = pedido or carro_lib.random_veiculo(self.catalogo, self.random)
            car = self._add_car(user, veiculo)
        else:
            pedido = carro_lib.from_text(text, self.catalogo)
            if pedido and pedido.id != car.vehicle:  # "agora vai de moto"
                car.vehicle = pedido.id
                car.vehicle_name = pedido.name
                car.is_moto = pedido.type == "moto"
                car.color = pedido.color
                car.dark = pedido.dark

        car.points += POINT_PER_COMMENT
        car.boost = max(car.boost, COMMENT_BOOST)
        car.boost_left = max(car.boost_left, BOOST_FRAMES // 3)

        notices: List[Dict[str, Any]] = []
        if joined:
            notices.append({
                "kind": "join", "user": user, "vehicle": car.vehicle_name, "color": car.color,
                "message": f"{user} ENTROU COM {car.vehicle_name.upper()}",
            })
        else:
            notices.append({"kind": "comment", "user": user,
                            "message": f"{user} ACELEROU!" if car.boost > COMMENT_BOOST else None})
        return [notice for notice in notices if notice.get("message")]

    def _on_gift(self, user: str, gift_name: Any, count: int, event_coins: int) -> List[Dict[str, Any]]:
        gift_info = gift_lib.describe(str(gift_name) if gift_name else None, event_coins)
        effect = str(gift_info["effect"])
        multiplier = int(gift_info["multiplier"]) * self.clamp(count, 1, 3)

        car = self._car_of(user)
        if car is None:
            car = self._add_car(user, carro_lib.random_veiculo(self.catalogo, self.random))
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
        # curtida tambem ajuda: empurra um pouco quem ja esta na pista
        car.boost = max(car.boost, COMMENT_BOOST / 2)
        car.boost_left = max(car.boost_left, BOOST_FRAMES // 4)
        return [{"kind": "like", "user": user, "count": count, "message": f"{user} CURTIU (+{count})"}]

    # ------------------------------------------------------------------ update
    def update(self) -> List[Dict[str, Any]]:
        super().update()
        events: List[Dict[str, Any]] = []

        # ---- largada: contagem regressiva, ninguem anda
        if self.phase == PHASE_COUNTDOWN:
            if self.cars:
                self.countdown -= 1
                if self.countdown <= 0:
                    self.phase = PHASE_RACING
                    self.countdown = 0
                    events.append({"kind": "go", "message": "VALENDO!"})
            return events

        if self.phase == PHASE_OVER:
            self.restart_in -= 1
            if self.restart_in <= 0:
                self.reset()
                events.append({"kind": "restart", "message": "NOVA CORRIDA!"})
            return events

        # ---- corrida
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
                veiculo = self.catalogo.by_id(car.vehicle)
                fator = veiculo.speed if veiculo else 1.0
                car.speed = (BASE_SPEED + car.boost) * fator

            previous = car.dist
            car.dist += car.speed

            for oil in list(self.oils):  # derrapou no oleo?
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
            champion = min(finished, key=lambda car: car.finished_at or 0)
            self.phase = PHASE_OVER
            self.winner = {"user": champion.name, "points": champion.points,
                           "vehicle": champion.vehicle_name, "kmh": champion.kmh()}
            self.restart_in = RESTART_DELAY_FRAMES
            events.append({"kind": "winner", "user": champion.name, "side": None,
                           "message": f"{champion.name} VENCEU!"})

        return events

    # -------------------------------------------------------------- serializacao
    def snapshot(self) -> Dict[str, Any]:
        ordered = sorted(self.cars, key=lambda car: car.dist, reverse=True)
        for index, car in enumerate(ordered, start=1):
            if not car.finished_at:
                car.place = index
        return {
            "tick": self.tick,
            "phase": self.phase,
            "countdown": max(0, -(-self.countdown // 60)) if self.phase == PHASE_COUNTDOWN else 0,
            "trackLength": TRACK_LENGTH,
            "lanes": LANES,
            "cars": [car.to_dict() for car in ordered],
            "oils": [{"dist": round(oil["dist"], 1)} for oil in self.oils],
            "winner": self.winner,
            "restartIn": self.restart_in,
            "lastJoiner": self.last_joiner,
            "baseSpeed": BASE_SPEED,
            "kmhFactor": KMH_FACTOR,
        }

    def describe(self) -> Dict[str, Any]:
        info = super().describe()
        info.update({
            "title": self.title,
            "callToAction": self.call_to_action,
            "maxCars": MAX_CARS,
            "lanes": LANES,
            "countdownSeconds": COUNTDOWN_SECONDS,
            "effects": gift_lib.EFFECT_LABELS,
            "pointPerComment": POINT_PER_COMMENT,
            "catalog": {
                "cars": [v.to_dict() for v in self.catalogo.cars()],
                "motos": [v.to_dict() for v in self.catalogo.motos()],
            },
        })
        return info