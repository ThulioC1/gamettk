"""Presentes do TikTok -> efeito no jogo.

Duas camadas:

1. **nome** -> categoria (NITRO / OIL / TURBO), com os nomes reais que aparecem
   na live brasileira (Rosa, Galaxia, Sereia, Universo TikTok...);
2. **valor em moedas** (`gift.diamond_count`) -> multiplicador, porque nome muda
   a cada live/regiao e nao pode ser a unica fonte de verdade. Um Universo
   TikTok (44.999) tem que valer muito mais que um Rosa (1).

Presente sem nome conhecido e sem valor cai no piso: nitro x1.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from shared import config

NITRO = "NITRO"
OIL = "OIL"
TURBO = "TURBO"
POINTS = "POINTS"

#: efeito -> rotulo curto do HUD
EFFECT_LABELS: Dict[str, str] = {
    NITRO: "NITRO!",
    OIL: "ÓLEO!",
    TURBO: "ULTRAPASSAGEM!",
    POINTS: "+PONTOS",
}

#: palavras dos nomes reais de presente (BR) + aliases de outras regioes.
# Cuidado: uma palavra so pode estar em uma categoria (NITRO vem primeiro, entao
# duplicar em OIL/TURBO faria a primeira vencer).
DEFAULT_KEYWORDS: Dict[str, str] = {
    # comuns e medios: empurram o jogador
    NITRO: (
        # Brasil
        "rosa, gg, casquinha, sorvete, panda, perfume, eu te amo, te amo, "
        "confete, oculos de sol, oculos",
        # outros paises
        "rose, heart, love, gift",
    ),
    # agressao contra o rival
    OIL: (
        # Brasil
        "chuva de dinheiro, chuva, dinheiro",
        # outros paises
        "oil, oleo, banana, slippery",
    ),
    # grandes: impulso maximo
    TURBO: (
        # Brasil
        "galaxia, bola de espelhos, espelhos, sereia, aviao, planeta, "
        "voo diamante, diamante, leao, mini leao, universo tiktok, "
        "universo, tiktok universe",
        # outros paises
        "galaxy, universe, crown, rocket, dragon, draco, legend, tiktok",
    ),
}

#: (minimo de moedas, maximo, multiplicador). Base na tabela de presentes BR.
VALUE_TIERS: Tuple[Tuple[int, Optional[int], int], ...] = (
    (0, 19, 1),          # Rosa, GG, Casquinha, Panda
    (20, 199, 2),        # Perfume, Eu Te Amo, Confete, Oculos de sol
    (200, 999, 3),       # Chuva de Dinheiro
    (1000, 4999, 4),     # Galaxia, Sereia
    (5000, 14999, 6),    # Aviao, Planeta
    (15000, None, 8),    # Voo Diamante, Leao, Universo TikTok
)

#: nome da faixa, para o HUD
TIER_LABELS: Dict[int, str] = {
    1: "comum",
    2: "medio",
    3: "grande",
    4: "lenda",
    6: "lenda+",
    8: "lendario",
}


def _table() -> Dict[str, str]:
    """Monta o indice palavra-chave -> categoria a partir do .env."""
    index: Dict[str, str] = {}
    for effect, entries in DEFAULT_KEYWORDS.items():
        override = config.get_str(f"GIFT_{effect}_KEYWORDS")
        raw = override or ", ".join(entries)
        for word in raw.split(","):
            word = _normalize(word)
            if word:
                index.setdefault(word, effect)
    return index


def _normalize(text: str) -> str:
    from shared.commands import normalize

    return normalize(text)


def classify(gift_name: Optional[str]) -> str:
    """Descobre a categoria pelo nome do presente."""
    if not gift_name:
        return NITRO

    normalized = _normalize(gift_name)
    if not normalized:
        return NITRO

    index = _table()
    if normalized in index:  # nome exato ("rosa") antes de subtexto
        return index[normalized]

    for word, effect in sorted(index.items(), key=lambda item: len(item[0]), reverse=True):
        if len(word) >= 4 and word in normalized:
            return effect
    return NITRO


def magnitude(diamond_count: Optional[int]) -> int:
    """Multiplicador pela faixa de valor do presente."""
    try:
        coins = int(diamond_count or 0)
    except (TypeError, ValueError):
        return 1

    for low, high, multiplier in VALUE_TIERS:
        if coins >= low and (high is None or coins <= high):
            return multiplier
    return 1


def tier_label(diamond_count: Optional[int]) -> str:
    return TIER_LABELS.get(magnitude(diamond_count), "comum")


def describe(gift_name: Optional[str], diamond_count: Optional[int] = None) -> Dict[str, object]:
    """Tudo que um jogo precisa saber sobre um presente, em uma chamada."""
    effect = classify(gift_name)
    return {
        "name": (gift_name or "")[:40],
        "effect": effect,
        "label": EFFECT_LABELS.get(effect, effect),
        "coins": int(diamond_count or 0),
        "multiplier": magnitude(diamond_count),
        "tier": tier_label(diamond_count),
    }


def preset_table() -> List[Tuple[str, int]]:
    """Referencia rapida da tabela BR usada no .env e no README."""
    return [
        ("Rosa / GG / Casquinha de Sorvete", 1),
        ("Panda", 5),
        ("Perfume", 20),
        ("Eu Te Amo", 49),
        ("Confete", 100),
        ("Oculos de sol", 199),
        ("Chuva de Dinheiro", 500),
        ("Bola de Espelhos (Galaxia)", 1000),
        ("Sereia", 2988),
        ("Aviao", 6000),
        ("Planeta", 15000),
        ("Voo Diamante", 18000),
        ("Leao / Mini Leao", 29999),
        ("Universo TikTok", 44999),
    ]


__all__ = [
    "NITRO", "OIL", "TURBO", "POINTS",
    "EFFECT_LABELS", "DEFAULT_KEYWORDS", "VALUE_TIERS", "TIER_LABELS",
    "classify", "magnitude", "tier_label", "describe", "preset_table",
]
