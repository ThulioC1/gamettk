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

# --- likes: quanto mais a pessoa curte, mais o carro acelera (com teto) ---
LIKE_BOOST_STEP = config.get_int("LIKE_BOOST_STEP", minimum=0) / 100.0  # px/frame por curtida
LIKE_BOOST_FRAMES = config.get_int("LIKE_BOOST_FRAMES", minimum=5)
LIKE_SPEED_CAP = config.get_int("LIKE_SPEED_CAP", minimum=1) / 10.0      # teto do impulso
LIKE_BOOST_DECAY = config.get_int("LIKE_BOOST_DECAY", minimum=900) / 100000.0  # decai por frame
LIKE_FRAMES_PER_LIKE = config.get_int("LIKE_FRAMES_PER_LIKE", minimum=1)

# --- os dois carros de casa: sempre na pista, mesmo com a live vazia ---
RIVAL_NAMES = (config.get_str("RIVAL_1_NAME") or "Vitinmilgrau",
               config.get_str("RIVAL_2_NAME") or "Narutobebado")
RIVAL_VEHICLES = (config.get_str("RIVAL_1_VEHICLE") or "g8",
                  config.get_str("RIVAL_2_VEHICLE") or "xre300")
RIVAL_SPEED = config.get_int("RIVAL_SPEED", minimum=1) / 100.0  # fator deles na corrida

MAX_BOOST = TURBO_BOOST * 8
MAX_BOOST_FRAMES = BOOST_FRAMES * 4
MAX_OIL_SLICKS = 4
OIL_LIFETIME = 1200

#: px/frame -> km/h (velocidade de referencia: 4.5 px/frame = ~180 km/h)
KMH_FACTOR = config.get_int("KMH_FACTOR", minimum=1)
KMH_MAX = config.get_int("KMH_MAX", minimum=60)  # teto do mostrador

PHASE_WAITING = "esperando"
PHASE_COUNTDOWN = "countdown"
PHASE_RACING = "racing"
PHASE_OVER = "over"


def _kmh(px_por_frame: float) -> int:
    """Converte px/frame em km/h, com teto (nada de 1300 km/h na placa)."""
    return int(min(KMH_MAX, round(abs(px_por_frame) * KMH_FACTOR)))


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class Car:
    """Um carro da pista: dono, veiculo, posicao, faixa e velocidade."""

    __slots__ = ("user", "name", "number", "lane", "color", "dark", "vehicle", "vehicle_name",
                 "is_moto", "dist", "speed", "boost", "boost_left", "like_boost", "spin_left",
                 "points", "likes", "fixed", "finished_at", "entry_dist", "place")

    def __init__(self, user: str, number: int, lane: int, veiculo: carro_lib.Veiculo,
                 fixed: bool = False) -> None:
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
        self.boost = 0.0            # impulso de comentario/presente (temporario)
        self.boost_left = 0
        self.like_boost = 0.0       # impulso das curtidas (cresce e decai devagar)
        self.spin_left = 0
        self.points = 0
        self.likes = 0
        self.fixed = fixed            # carro de casa: nunca sai da pista
        self.finished_at: Optional[int] = None
        self.entry_dist = 0.0   # de onde o carro partiu no frame da chegada
        self.place = 0

    def kmh(self) -> int:
        """Velocidade mostrada na placa, com teto."""
        return _kmh(self.speed)

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
            "fixed": self.fixed,
            "dist": round(self.dist, 1),
            "speed": round(self.speed, 2),
            "kmh": self.kmh(),
            "boost": round(self.boost, 2),
            "likeBoost": round(self.like_boost, 2),
            "likeKmh": _kmh(self.like_boost),
            "spinning": self.spin_left > 0,
            "points": self.points,
            "likes": self.likes,
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
        self.phase = PHASE_WAITING
        self.countdown = COUNTDOWN_SECONDS * 60
        self.pending: Optional[Dict[str, Any]] = None
        self.random = random.Random(1234)  # partida reproduzivel em teste
        self._cria_carros_de_casa()

    def _cria_carros_de_casa(self) -> None:
        """Dois carros fixos, para a pista nunca ficar vazia.

        Sem ninguem na live eles correm sozinhos: quem chegar tem adversario.
        """
        for indice, nome in enumerate(RIVAL_NAMES):
            veiculo = (self.catalogo.by_id(RIVAL_VEHICLES[indice % len(RIVAL_VEHICLES)])
                       or self.catalogo.veiculos[indice % len(self.catalogo.veiculos)])
            car = Car(user=nome, number=99 - indice, lane=indice, veiculo=veiculo, fixed=True)
            car.dist = -(indice * GRID_COLUMN_GAP + 30)
            self.cars.append(car)

    # ------------------------------------------------------------------ reset
    def reset(self) -> None:
        self.oils.clear()
        self.restart_in = 0
        self.winner = None
        self.last_joiner = None
        self.phase = PHASE_WAITING
        self.countdown = COUNTDOWN_SECONDS * 60
        self.pending = None
        for index, car in enumerate(self.cars):
            car.dist = -self._grid_offset(index)
            car.speed = 0.0
            car.boost = 0.0
            car.boost_left = 0
            car.like_boost = 0.0
            car.spin_left = 0
            car.likes = 0
            car.finished_at = None
            car.place = 0

    @staticmethod
    def _grid_offset(index: int) -> float:
        """Posicao no grid de largada: 8 colunas x N faixas, atras da linha."""
        row = index // GRID_COLUMNS
        column = index % GRID_COLUMNS
        return row * GRID_ROW_GAP + column * GRID_COLUMN_GAP + 30.0

    def _dispara_largada(self) -> None:
        """O primeiro viewer acorda a corrida: antes disso fica em 'esperando'."""
        if self.phase == PHASE_WAITING:
            self.phase = PHASE_COUNTDOWN
            self.countdown = COUNTDOWN_SECONDS * 60
            self.pending = {"kind": "countdown", "message": "CHEGOU ALGUÉM! LARGADA EM 00:10"}

    # ----------------------------------------------------------------- entradas
    def handle_event(self, event: Dict[str, Any]) -> List[Dict[str, Any]]:
        kind = event.get("event")
        user = str(event.get("user") or "anon")[:24]
        notices: List[Dict[str, Any]] = []

        if kind in {"comment", "gift", "follow", "share"}:
            self._dispara_largada()

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

    def _car_do_usuario(self, user: str) -> Optional[Car]:
        """Como `_car_of`, mas ignora os carros de casa (viewers nunca os assume)."""
        for car in self.cars:
            if car.user == user and not car.fixed:
                return car
        return None

    def _add_car(self, user: str, veiculo: carro_lib.Veiculo) -> Car:
        index = len(self.cars)
        lane = index % LANES
        car = Car(user=user, number=index % 99 + 1, lane=lane, veiculo=veiculo)
        car.dist = -self._grid_offset(index)
        self.cars.append(car)

        # pista cheia: sai quem esta mais atras, mas NUNCA um carro de casa
        if len(self.cars) > MAX_CARS:
            variaveis = [car for car in self.cars if not car.fixed]
            if len(variaveis) > 1:
                self.cars.remove(min(variaveis, key=lambda car: car.dist))

        self.last_joiner = user
        return car
    def _on_comment(self, user: str, text: str) -> List[Dict[str, Any]]:
        # `_car_do_usuario` ignora os carros de casa: um viewer que se chamar
        # "Vitinmilgrau" ganha o carro DELE, sem tomar o carro fixo da pista.
        car = self._car_do_usuario(user)
        joined = car is None

        trocou = False
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
                trocou = True

        car.points += POINT_PER_COMMENT
        car.boost = max(car.boost, COMMENT_BOOST)
        car.boost_left = max(car.boost_left, BOOST_FRAMES // 3)

        notices: List[Dict[str, Any]] = []
        if joined:
            notices.append({
                "kind": "join", "user": user, "vehicle": car.vehicle_name, "color": car.color,
                "message": f"{user} ENTROU COM {car.vehicle_name.upper()}",
            })
        elif trocou:
            notices.append({"kind": "vehicle", "user": user, "vehicle": car.vehicle_name,
                            "message": f"{user} TROCOU PARA {car.vehicle_name.upper()}"})
        elif car.boost > COMMENT_BOOST:
            notices.append({"kind": "comment", "user": user, "message": f"{user} ACELEROU!"})
        return [notice for notice in notices if notice.get("message")]

    def _on_gift(self, user: str, gift_name: Any, count: int, event_coins: int) -> List[Dict[str, Any]]:
        gift_info = gift_lib.describe(str(gift_name) if gift_name else None, event_coins)
        effect = str(gift_info["effect"])
        multiplier = int(gift_info["multiplier"]) * self.clamp(count, 1, 3)

        car = self._car_do_usuario(user)
        if car is None:
            car = self._add_car(user, carro_lib.random_veiculo(self.catalogo, self.random))
        car.points += 10 * multiplier

        notice = {
            "kind": "gift", "user": user, "gift": gift_name, "effect": effect,
            "emoji": gift_info["emoji"], "coins": gift_info["coins"], "tier": gift_info["tier"],
            "message": f"{gift_info['label']} ({gift_info['tier']})",
        }

        if effect == gift_lib.OIL:
            manchas = min(multiplier, MAX_OIL_SLICKS)
            for index in range(manchas):
                self.oils.append({
                    "dist": max(car.dist - 70 - index * 45, -140),
                    "owner": user,
                    "life": OIL_LIFETIME,
                })
            notice["effect_text"] = f"{manchas} mancha(s) de oleo na pista"
            notice["message"] = (f"{gift_info['emoji']} OLEO ({gift_info['tier']})"
                                 f" -> {manchas} manchas na pista")
            return [notice]

        base_boost = TURBO_BOOST if effect == gift_lib.TURBO else NITRO_BOOST
        antes = car.boost
        impulso = min(max(car.boost, base_boost * multiplier), MAX_BOOST)
        car.boost = impulso
        car.boost_left = min(max(car.boost_left, BOOST_FRAMES + (multiplier - 1) * 20), MAX_BOOST_FRAMES)
        if effect == gift_lib.TURBO:
            car.dist += 60 * multiplier  # ultrapassagem: ganha posicao na hora

        ganho = _kmh(impulso - antes)
        extra = f" e +{60 * multiplier} px de posicao" if effect == gift_lib.TURBO else ""
        if ganho <= 0:
            # ja estava no teto de nitro: melhor dizer isso do que "+0 km/h"
            notice["effect_text"] = "no limite de nitro"
            notice["message"] = (f"{gift_info['label']} ({gift_info['tier']}) -> ja esta no nitro maximo"
                                 + (f" e +{60 * multiplier} px de posicao" if effect == gift_lib.TURBO else ""))
            return [notice]

        notice["effect_text"] = f"+{ganho} km/h"
        notice["message"] = (f"{gift_info['emoji']} {gift_info['label']} ({gift_info['tier']})"
                             f" -> +{ganho} km/h{extra}"
                             f" (ponta: {_kmh(car.speed + car.like_boost + car.boost)} km/h)")
        return [notice]

    def _on_like(self, user: str, count: int) -> List[Dict[str, Any]]:
        """Curtida acelera de forma acumulada: 10 likes > 3 likes > 1 like."""
        car = self._car_do_usuario(user)
        if car is None:
            return []

        car.likes += count
        car.points += count

        # o impulso das curtidas e ADITIVO (soma ao de comentario/presente) para
        # a diferenca aparecer na tela desde a primeira curtida
        antes = car.like_boost
        car.like_boost = min(LIKE_SPEED_CAP, car.like_boost + count * LIKE_BOOST_STEP)
        frames = LIKE_BOOST_FRAMES + min(LIKE_FRAMES_PER_LIKE * car.likes, LIKE_FRAMES_PER_LIKE * 40)
        car.boost_left = max(car.boost_left, frames)
        ganho = _kmh(car.like_boost - antes)

        return [{"kind": "like", "user": user, "count": count, "likes": car.likes,
                 "effect": f"+{ganho} km/h",
                 "message": (f"{user} CURTIU ({car.likes} likes) → +{ganho} km/h "
                             f"(ponta: {_kmh(car.speed + car.like_boost)} km/h)")}]

    # ------------------------------------------------------------------ update
    def update(self) -> List[Dict[str, Any]]:
        super().update()
        events: List[Dict[str, Any]] = []

        # ---- largada: contagem regressiva, ninguem anda
        if self.phase == PHASE_WAITING:
            return events + self._drain()

        if self.phase == PHASE_COUNTDOWN:
            if self.cars:
                self.countdown -= 1
                if self.countdown <= 0:
                    self.phase = PHASE_RACING
                    self.countdown = 0
                    events.append({"kind": "go", "message": "VALENDO!"})
            return events + self._drain()

        if self.phase == PHASE_OVER:
            self.restart_in -= 1
            if self.restart_in <= 0:
                self.reset()
                events.append({"kind": "restart", "message": "NOVA CORRIDA!"})
            return events + self._drain()

        # ---- corrida
        for oil in self.oils:
            oil["life"] -= 1
        self.oils = [oil for oil in self.oils if oil["life"] > 0]

        for car in self.cars:
            if car.like_boost > 0:  # decai devagar: a curtida vale a corrida toda
                car.like_boost = max(0.0, car.like_boost * LIKE_BOOST_DECAY)

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
                if car.fixed:  # os carros de casa correm na medida, sem nitro da live
                    fator *= RIVAL_SPEED
                car.speed = (BASE_SPEED + car.boost + car.like_boost) * fator

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
                car.entry_dist = previous      # de onde ele saiu no frame
                finished.append(car)

        if finished:
            # Desempate: no mesmo frame vale quem estava MAIS A FRENTE ao entrar
            # no frame (entry_dist). Pela ordem da lista o vencedor seria sempre o
            # primeiro carro criado - hoje, os dois carros de casa.
            champion = min(finished, key=lambda car: (car.finished_at or 0, -car.entry_dist, -car.speed))
            for colocacao, car in enumerate(sorted(
                    finished, key=lambda car: (car.finished_at or 0, -car.entry_dist, -car.speed)), start=1):
                car.place = colocacao

            self.phase = PHASE_OVER
            self.winner = {
                "user": champion.name,
                "vehicle": champion.vehicle_name,
                "kmh": champion.kmh(),
                "points": champion.points,
                "likes": champion.likes,
                "fixed": champion.fixed,
                "time": round(self.tick / 60.0, 1),
            }
            self.restart_in = RESTART_DELAY_FRAMES
            events.append({"kind": "winner", "user": champion.name, "side": None,
                           "message": f"{champion.name.upper()} VENCEU COM {champion.vehicle_name.upper()}!"})

        return events + self._drain()

    def _drain(self) -> List[Dict[str, Any]]:
        """Entrega (e limpa) o evento acumulado desde o ultimo frame."""
        if not self.pending:
            return []
        evento, self.pending = self.pending, None
        return [evento]

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
            "waitingFor": self.phase == PHASE_WAITING,
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
