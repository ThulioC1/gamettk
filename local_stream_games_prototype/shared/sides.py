"""Lados e regras do Duelo de Torres, lidos de `config/duel.json`.

O confronto (nomes, partido, cor, palavra-chave que coloca a pessoa de um lado)
e os efeitos de presente ficam em um JSON: trocar o duelo e' editar um arquivo,
nao mexer no codigo.

    DUEL_CONFIG=/caminho/meu_duelo.json   # opcional, para outro confronto
"""
from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Dict, List, Optional

from shared import config
from shared.commands import normalize

DEFAULT_PATH = config.PROJECT_ROOT / "config" / "duel.json"

FALLBACK: Dict[str, Any] = {
    "title": "Duelo de Torres",
    "targetBlocks": 20,
    "blockHeight": 18,
    "sides": [
        {"id": "esquerda", "name": "LULA", "party": "PT", "color": "#e11d48", "dark": "#881337", "keywords": ["lula", "pt"]},
        {"id": "direita", "name": "RIVAL", "party": "", "color": "#2563eb", "dark": "#1e3a8a", "keywords": ["rival"]},
    ],
    "gifts": {
        "NITRO": {"blocks": 3, "message": "+3 BLOCOS"},
        "TURBO": {"blocks": 8, "message": "+8 BLOCOS"},
        "OIL": {"sabotage": 2, "message": "DERRUBADA!"},
    },
}


@dataclass(frozen=True)
class Side:
    """Um lado do duelo: identidade visual + palavras que levam ate ele."""

    id: str
    name: str
    party: str
    color: str
    dark: str
    tagline: str = ""
    keywords: frozenset[str] = field(default_factory=frozenset)

    def label(self) -> str:
        return f"{self.name} ({self.party})" if self.party else self.name

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "party": self.party,
            "color": self.color,
            "dark": self.dark,
            "tagline": self.tagline,
            "keywords": sorted(self.keywords),
        }


@dataclass(frozen=True)
class DuelConfig:
    title: str
    target_blocks: int
    block_height: int
    sides: List[Side]
    gifts: Dict[str, Dict[str, int]]


def _build_side(raw: Dict[str, Any], index: int) -> Side:
    """Normaliza uma entrada do JSON (palavras sem acento, cores com #)."""
    base = FALLBACK["sides"][index % 2]
    keywords = raw.get("keywords") or base["keywords"]
    normalized = {normalize(str(word)) for word in keywords}
    normalized.discard("")
    return Side(
        id=str(raw.get("id") or base["id"])[:16],
        name=str(raw.get("name") or base["name"])[:24],
        party=str(raw.get("party") or "")[:8],
        color=_color(raw.get("color"), base["color"]),
        dark=_color(raw.get("dark"), base["dark"]),
        tagline=str(raw.get("tagline") or "")[:40],
        keywords=frozenset(normalized),
    )


def _color(value: Any, fallback: str) -> str:
    text = str(value or fallback).strip()
    if not text.startswith("#") or len(text) not in (4, 7):
        return fallback
    return text


@lru_cache(maxsize=4)
def load(path: Optional[str] = None) -> DuelConfig:
    """Le e valida o JSON do duelo; em qualquer problema usa o fallback."""
    target = pathlib.Path(path) if path else pathlib.Path(config.get_str("DUEL_CONFIG") or DEFAULT_PATH)

    data: Dict[str, Any] = dict(FALLBACK)
    if target.is_file():
        try:
            data.update(json.loads(target.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError) as err:
            print(f"[duelo] JSON invalido em {target} ({err}); usando padroes")

    sides = [_build_side(raw, index) for index, raw in enumerate(data.get("sides", []))]
    if len(sides) < 2:
        sides = [_build_side(raw, index) for index, raw in enumerate(FALLBACK["sides"])]

    gifts: Dict[str, Dict[str, int]] = {}
    for effect, spec in (data.get("gifts") or {}).items():
        if isinstance(spec, dict):
            gifts[effect] = {key: int(value) for key, value in spec.items() if isinstance(value, (int, float))}

    return DuelConfig(
        title=str(data.get("title") or FALLBACK["title"])[:40],
        target_blocks=max(3, int(data.get("targetBlocks") or FALLBACK["targetBlocks"])),
        block_height=max(8, int(data.get("blockHeight") or FALLBACK["blockHeight"])),
        sides=sides[:2],
        gifts=gifts or dict(FALLBACK["gifts"]),
    )


def side_from_text(text: str, duel: Optional[DuelConfig] = None) -> Optional[Side]:
    """Descobre qual lado a pessoa pediu ao escrever no chat."""
    duel = duel or load()
    normalized = normalize(text)
    if not normalized:
        return None

    for token in normalized.split():
        for side in duel.sides:
            if token in side.keywords:
                return side

    for side in duel.sides:  # depois, por subtexto (palavra mais longa primeiro)
        for keyword in sorted(side.keywords, key=len, reverse=True):
            if len(keyword) >= 4 and keyword in normalized:
                return side
    return None
