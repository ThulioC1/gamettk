"""Catalogo de veiculos da Corrida na Live, lido de `config/carros.json`.

Gol, Uno, Fusca, Kombi e as motos sao os nomes que a plateia reconhece; cada um
tem cor e velocidade propria. O viewer escolhe escribiendo o nome no comentario
("tenho um gol", "moto biz") ou ganha um sorteado.

    CARROS_CONFIG=/caminho/meus_carros.json   # opcional
"""
from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

from shared import config
from shared.commands import normalize

DEFAULT_PATH = config.PROJECT_ROOT / "config" / "carros.json"

#: usado se o JSON faltar ou vier quebrado
FALLBACK: Tuple[Dict[str, Any], ...] = (
    {"id": "gol", "name": "Gol", "type": "carro", "color": "#1f9d55", "dark": "#0f6b3a", "speed": 1.0, "keywords": ["gol"]},
    {"id": "uno", "name": "Uno", "type": "carro", "color": "#e2e8f0", "dark": "#94a3b8", "speed": 0.94, "keywords": ["uno"]},
    {"id": "moto", "name": "160", "type": "moto", "color": "#ef4444", "dark": "#991b1b", "speed": 1.04, "keywords": ["moto"]},
)


@dataclass(frozen=True)
class Veiculo:
    id: str
    name: str
    type: str          # "carro" | "moto"
    color: str
    dark: str
    speed: float       # multiplicador de velocidade
    keywords: Tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "name": self.name, "type": self.type,
                "color": self.color, "dark": self.dark, "speed": self.speed}


@dataclass(frozen=True)
class Catalogo:
    title: str
    veiculos: List[Veiculo]

    def by_id(self, veiculo_id: str) -> Optional[Veiculo]:
        return next((v for v in self.veiculos if v.id == veiculo_id), None)

    def cars(self) -> List[Veiculo]:
        return [v for v in self.veiculos if v.type == "carro"]

    def motos(self) -> List[Veiculo]:
        return [v for v in self.veiculos if v.type == "moto"]


def _color(value: Any, fallback: str) -> str:
    text = str(value or fallback).strip()
    if not text.startswith("#") or len(text) not in (4, 7):
        return fallback
    return text


def _build(raw: Dict[str, Any], index: int) -> Veiculo:
    base = FALLBACK[index % len(FALLBACK)]
    palavras = raw.get("keywords") or base["keywords"]
    keywords = tuple(sorted({normalize(str(palavra)) for palavra in palavras if normalize(str(palavra))}))
    try:
        speed = float(raw.get("speed", base["speed"]))
    except (TypeError, ValueError):
        speed = base["speed"]
    return Veiculo(
        id=str(raw.get("id") or base["id"])[:20],
        name=str(raw.get("name") or base["name"])[:16],
        type="moto" if str(raw.get("type", base["type"])).lower() == "moto" else "carro",
        color=_color(raw.get("color"), base["color"]),
        dark=_color(raw.get("dark"), base["dark"]),
        speed=min(1.5, max(0.7, speed)),
        keywords=keywords,
    )


@lru_cache(maxsize=4)
def load(path: str | None = None) -> Catalogo:
    """Le e valida o catalogo; em qualquer problema usa o fallback."""
    target = pathlib.Path(path) if path else pathlib.Path(config.get_str("CARROS_CONFIG") or DEFAULT_PATH)

    data: Dict[str, Any] = {}
    if target.is_file():
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as err:
            print(f"[corrida] JSON invalido em {target} ({err}); usando fallback")

    veiculos = [_build(raw, index) for index, raw in enumerate(data.get("cars") or [])]
    if not veiculos:
        veiculos = [_build(raw, index) for index, raw in enumerate(FALLBACK)]

    return Catalogo(title=str(data.get("title") or "Corrida na Live")[:40], veiculos=veiculos)


def from_text(text: str, catalogo: Optional[Catalogo] = None) -> Optional[Veiculo]:
    """Acha o veiculo que a pessoa pediu no comentario."""
    catalogo = catalogo or load()
    normalized = normalize(text)
    if not normalized:
        return None

    for token in normalized.split():
        for veiculo in catalogo.veiculos:
            if token in veiculo.keywords:
                return veiculo

    for veiculo in catalogo.veiculos:  # subtexto, palavra mais longa primeiro
        for keyword in sorted(veiculo.keywords, key=len, reverse=True):
            if len(keyword) >= 4 and keyword in normalized:
                return veiculo
    return None


def random_veiculo(catalogo: Catalogo, rng) -> Veiculo:
    return catalogo.veiculos[rng.randrange(len(catalogo.veiculos))]


__all__ = ["Veiculo", "Catalogo", "load", "from_text", "random_veiculo"]