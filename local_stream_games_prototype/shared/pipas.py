"""Regras da Pipa Arena, lidas de `config/pipa.json`.

Cada comentário solta uma pipa no céu; cada presente corta linhas de pipa
rivais. Quem une a propria pipa no chao mantem pontos; quem voa mais alto
(ponto por altura) e quem tem mais pipas no ar disputa a lideranca.

    PIPA_CONFIG=/caminho/minha_pipa.json   # opcional
"""
from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Dict, List, Tuple

from shared import config

DEFAULT_PATH = config.PROJECT_ROOT / "config" / "pipa.json"

FALLBACK: Dict[str, Any] = {
    "title": "Pipa Arena",
    "maxKites": 26,
    "kiteSpeed": 0.45,
    "stringPull": 1.2,
    "rivalRivals": 2,
    "gifts": {"NITRO": {"cuts": 1}, "TURBO": {"cuts": 2}, "OIL": {"cuts": 3}},
}


#: cores de pipa, escolhidas por indice (% len)
PALETTE: Tuple[str, ...] = (
    "#f43f5e", "#f97316", "#fbbf24", "#22d3ee",
    "#3b82f6", "#a78bfa", "#34d399", "#e879f9",
)


@dataclass(frozen=True)
class ArenaConfig:
    title: str
    max_kites: int
    kite_speed: float
    string_pull: float
    rival_rivals: int
    gifts: Dict[str, Dict[str, int]]


@lru_cache(maxsize=4)
def load(path: str | None = None) -> ArenaConfig:
    """Le e valida o JSON da arena; em qualquer problema usa o fallback."""
    target = pathlib.Path(path) if path else pathlib.Path(config.get_str("PIPA_CONFIG") or DEFAULT_PATH)

    data: Dict[str, Any] = dict(FALLBACK)
    if target.is_file():
        try:
            data.update(json.loads(target.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError) as err:
            print(f"[pipa] JSON invalido em {target} ({err}); usando padroes")

    gifts: Dict[str, Dict[str, int]] = {}
    for effect, spec in (data.get("gifts") or {}).items():
        if isinstance(spec, dict):
            gifts[effect] = {
                key: int(value) for key, value in spec.items()
                if isinstance(value, (int, float))
            }

    return ArenaConfig(
        title=str(data.get("title") or FALLBACK["title"])[:40],
        max_kites=max(4, int(data.get("maxKites") or FALLBACK["maxKites"])),
        kite_speed=float(data.get("kiteSpeed") or FALLBACK["kiteSpeed"]),
        string_pull=float(data.get("stringPull") or FALLBACK["stringPull"]),
        rival_rivals=max(1, int(data.get("rivalRivals") or FALLBACK["rivalRivals"])),
        gifts=gifts or dict(FALLBACK["gifts"]),
    )


def color_for(index: int) -> str:
    return PALETTE[index % len(PALETTE)]


__all__ = ["ArenaConfig", "PALETTE", "color_for", "load"]
