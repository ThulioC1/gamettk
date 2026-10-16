"""Modulo compartilhado: leitura de configuracao (.env / ambiente)."""
from __future__ import annotations

import os
import pathlib
from typing import Dict, Iterable

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent

# Valores padrao usados quando a variavel nao existe no ambiente/.env
DEFAULTS: Dict[str, str] = {
    "PORT": "8080",
    "GAME": "corrida",
    # Senha do controlador: sem ela, quem nao for o bot pode injetar eventos.
    "GAME_TOKEN": "",
    "TIKTOK_USERNAME": "",
    "EULER_API_KEY": "",
    "COMMAND_COOLDOWN_MS": "350",
    "COMMAND_RATE_LIMIT_PER_MIN": "180",
    # Corrida na Live
    "TRACK_LENGTH": "5000",
    "CAR_BASE_SPEED": "45",
    "COMMENT_BOOST": "18",
    "NITRO_BOOST": "60",
    "TURBO_BOOST": "110",
    "BOOST_FRAMES": "90",
    "SPIN_FRAMES": "70",
    "RESTART_DELAY_FRAMES": "420",
    "POINT_PER_COMMENT": "1",
    "CAR_MAX": "40",
    # Presentes -> efeitos (vazio = usar shared.gifts.DEFAULT_KEYWORDS)
    "GIFT_NITRO_KEYWORDS": "",
    "GIFT_OIL_KEYWORDS": "",
    "GIFT_TURBO_KEYWORDS": "",
}


def load_dotenv(path: pathlib.Path | None = None) -> None:
    """Carrega KEY=VALOR do .env no os.environ sem sobrescrever o que ja existe."""
    env_path = path or (PROJECT_ROOT / ".env")
    if not env_path.is_file():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        os.environ.setdefault(key, value)


def get_str(key: str) -> str:
    load_dotenv()
    return os.environ.get(key, DEFAULTS.get(key, "")).strip()


def get_int(key: str, minimum: int | None = None) -> int:
    raw = get_str(key) or "0"
    try:
        value = int(raw)
    except ValueError:
        value = int(DEFAULTS.get(key, "0"))
    if minimum is not None and value < minimum:
        return minimum
    return value


def get_bool(key: str, default: bool = False) -> bool:
    raw = get_str(key).lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "y", "sim", "on"}


def get_csv(key: str) -> list[str]:
    raw = get_str(key)
    return [item.strip() for item in raw.split(",") if item.strip()]


def missing_keys(required: Iterable[str]) -> list[str]:
    """Retorna as chaves obrigatorias que estao vazias (para mensagens de erro)."""
    return [key for key in required if not get_str(key)]
