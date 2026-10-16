"""Platformer de demonstracao: o teclado/simador envia comandos diretos.

Serve como segundo modulo do launcher - e o mais simples de todos: mostra que
o nucleo (servidor + bot + HUD) nao depende do jogo instalado.
"""
from __future__ import annotations

import random
from typing import Any, Dict, List, Tuple

from server.base import GameBase
from shared import commands as cmd

WORLD_WIDTH = 960
WORLD_HEIGHT = 540

GRAVITY = 0.62
MOVE_SPEED = 5.4
JUMP_VELOCITY = -13.4
MAX_FALL_SPEED = 15.0

PLAYER_WIDTH = 28
PLAYER_HEIGHT = 40
SPAWN_X = 60.0
SPAWN_Y = 420.0

#: (x, y, largura, altura) em pixels do canvas.
PLATFORMS: Tuple[Tuple[float, float, float, float], ...] = (
    (0.0, 500.0, WORLD_WIDTH, 40.0),
    (150.0, 410.0, 160.0, 16.0),
    (370.0, 330.0, 160.0, 16.0),
    (610.0, 250.0, 170.0, 16.0),
    (790.0, 380.0, 170.0, 16.0),
)

COIN_SPOTS: Tuple[Tuple[float, float], ...] = (
    (210.0, 378.0), (300.0, 378.0), (430.0, 298.0),
    (520.0, 298.0), (660.0, 218.0), (770.0, 218.0), (840.0, 348.0),
)

COIN_RADIUS = 9.0
GOAL_X, GOAL_Y, GOAL_WIDTH, GOAL_HEIGHT = 900.0, 460.0, 16.0, 40.0
COIN_SCORE = 10
GOAL_SCORE = 100


class Platformer(GameBase):
    type = "platformer"
    title = "Platformer"
    call_to_action = "Use o teclado, os botoes ou o simulador (pula / esquerda / direita)."

    def __init__(self) -> None:
        super().__init__()
        self.random = random.Random(7)
        self.reset(full=True)

    def reset(self, full: bool = False) -> None:
        self.player_x = SPAWN_X
        self.player_y = SPAWN_Y
        self.velocity_x = 0.0
        self.velocity_y = 0.0
        self.facing_right = True
        self.on_ground = False
        self.score = 0
        self.won = False
        self.direction = 0
        self.coins: List[Dict[str, Any]] = [{"x": x, "y": y, "collected": False} for x, y in COIN_SPOTS]

    # ----------------------------------------------------------------- entrada
    def handle_event(self, event: Dict[str, Any]) -> List[Dict[str, Any]]:
        if event.get("event") != "command":
            return []
        command = str(event.get("command", "")).strip().upper()
        if command not in cmd.COMMANDS:
            return []
        self.apply_command(command)
        return [{"kind": "command", "command": command, "user": event.get("user", "")}]

    def apply_command(self, command: str) -> bool:
        if command in cmd.DIRECTION_COMMANDS:
            self.direction = {cmd.MOVE_LEFT: -1, cmd.MOVE_RIGHT: 1, cmd.STOP: 0}[command]
            return True
        if command == cmd.JUMP:
            if self.on_ground and not self.won:
                self.velocity_y = JUMP_VELOCITY
                self.on_ground = False
            return True
        if command == cmd.RESET:
            self.reset()
            return True
        return False

    # ------------------------------------------------------------------ update
    def update(self) -> List[Dict[str, Any]]:
        super().update()
        events: List[Dict[str, Any]] = []

        if not self.won:
            target = MOVE_SPEED * self.direction
            self.velocity_x += (target - self.velocity_x) * 0.35
            if abs(self.velocity_x) < 0.05:
                self.velocity_x = 0.0
            self.facing_right = self.direction >= 0

            self.velocity_y = min(self.velocity_y + GRAVITY, MAX_FALL_SPEED)
            previous_bottom = self.player_y + PLAYER_HEIGHT

            self.player_x += self.velocity_x
            self.player_x = self.clamp(self.player_x, 0.0, WORLD_WIDTH - PLAYER_WIDTH)
            self.player_y += self.velocity_y

            self.on_ground = False
            for platform_x, platform_y, platform_w, _ in PLATFORMS:
                overlaps_x = (self.player_x + PLAYER_WIDTH > platform_x
                              and self.player_x < platform_x + platform_w)
                crossed = previous_bottom <= platform_y and self.player_y + PLAYER_HEIGHT >= platform_y
                if overlaps_x and crossed and self.velocity_y >= 0:
                    self.player_y = platform_y - PLAYER_HEIGHT
                    self.velocity_y = 0.0
                    self.on_ground = True

            events.extend(self._check_pickups())
        else:
            self.velocity_x = 0.0

        if self.player_y > WORLD_HEIGHT + 60:
            events.append({"kind": "death", "message": "CAIU! REINICIANDO"})
            self.reset()

        return events

    def _check_pickups(self) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        center_x = self.player_x + PLAYER_WIDTH / 2
        center_y = self.player_y + PLAYER_HEIGHT / 2

        for coin in self.coins:
            if coin["collected"]:
                continue
            if (abs(coin["x"] - center_x) <= COIN_RADIUS + PLAYER_WIDTH / 2
                    and abs(coin["y"] - center_y) <= COIN_RADIUS + PLAYER_HEIGHT / 2):
                coin["collected"] = True
                self.score += COIN_SCORE
                events.append({"kind": "coin", "score": self.score, "message": "MOEDA +%d" % COIN_SCORE})

        if (self.player_x + PLAYER_WIDTH >= GOAL_X
                and self.player_y + PLAYER_HEIGHT > GOAL_Y - GOAL_HEIGHT):
            self.won = True
            self.score += GOAL_SCORE
            events.append({"kind": "goal", "score": self.score, "message": "CHEGADA! +%d" % GOAL_SCORE})

        return events

    # -------------------------------------------------------------- serializacao
    def snapshot(self) -> Dict[str, Any]:
        return {
            "tick": self.tick,
            "world": {"width": WORLD_WIDTH, "height": WORLD_HEIGHT},
            "player": {
                "x": round(self.player_x, 2),
                "y": round(self.player_y, 2),
                "vx": round(self.velocity_x, 2),
                "vy": round(self.velocity_y, 2),
                "facingRight": self.facing_right,
                "onGround": self.on_ground,
            },
            "platforms": [list(platform) for platform in PLATFORMS],
            "coins": [{"x": c["x"], "y": c["y"], "collected": c["collected"]} for c in self.coins],
            "goal": {"x": GOAL_X, "y": GOAL_Y, "width": GOAL_WIDTH, "height": GOAL_HEIGHT},
            "coinRadius": COIN_RADIUS,
            "playerSize": [PLAYER_WIDTH, PLAYER_HEIGHT],
            "score": self.score,
            "won": self.won,
        }

    def describe(self) -> Dict[str, Any]:
        info = super().describe()
        info["commands"] = list(cmd.COMMANDS)
        return info


def random_walk_command(previous: str) -> str:
    """Usado pelo simulador automatico para gerar uma jogada plausivel."""
    choices = [cmd.MOVE_LEFT, cmd.MOVE_RIGHT, cmd.JUMP, cmd.STOP]
    if previous not in choices:
        previous = cmd.STOP
    return random.choice(choices)  # type: ignore[return-value]
