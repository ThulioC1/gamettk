"""Presentes do TikTok -> categoria (efeito) e potencia.

Tres fontes, em ordem:

1. **valor em moedas** que veio do evento (`gift.diamond_count`) — confiavel;
2. **catálogo** (`config/presentes.json`): nome -> moedas + emoji. Serve de
   reserva quando a lib nao manda o valor, e da o emoji do banner;
3. piso: presente desconhecido = nitro x1 (nunca e jogado fora).

O catalogo junta os nomes da live brasileira (Rosa, Chuva de Dinheiro, Universo
TikTok) com os globais (Galaxy, Swan, Fireworks), porque o TikTok renomeia por
pais/idioma.
"""
from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

from shared import config

NITRO = "NITRO"
OIL = "OIL"
TURBO = "TURBO"
POINTS = "POINTS"

DEFAULT_PATH = config.PROJECT_ROOT / "config" / "presentes.json"

EFFECT_LABELS: Dict[str, str] = {
    NITRO: "NITRO!",
    OIL: "ÓLEO!",
    TURBO: "ULTRAPASSAGEM!",
    POINTS: "+PONTOS",
}

#: fallback por palavras-chave, quando o nome nao esta no catalogo.
#: O catalogo manda: estas so entram se o presente for desconhecido.
DEFAULT_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    NITRO: ("rosa", "gg", "casquinha", "sorvete", "panda", "perfume", "eu te amo", "te amo",
            "confete", "oculos de sol", "oculos", "rose", "heart", "love", "gift"),
    OIL: ("chuva de dinheiro", "chuva", "dinheiro", "oil", "oleo", "banana", "slippery"),
    TURBO: ("galaxia", "bola de espelhos", "espelhos", "sereia", "aviao", "planeta",
            "voo diamante", "diamante", "leao", "mini leao", "universo tiktok", "universo",
            "galaxy", "universe", "crown", "rocket", "dragon", "draco", "legend", "tiktok"),
}

#: categorias padrao (usadas quando o catalogo nao traz o efeito)
DEFAULT_EFFECT_BY_VALUE = (
    (19, NITRO), (199, NITRO), (999, OIL), (4999, TURBO),
    (14999, TURBO), (None, TURBO),
)


@dataclass(frozen=True)
class Presente:
    """Um presente do catalogo: nome, moedas, emoji e efeito."""

    name: str
    coins: int
    emoji: str
    effect: str
    aliases: Tuple[str, ...]


@dataclass(frozen=True)
class CatalogoPresentes:
    gifts: List[Presente]
    tiers: Tuple[Tuple[str, Optional[int], int], ...]   # (id, maxCoins, multiplier)

    def por_nome(self, nome: str) -> Optional[Presente]:
        alvo = _normalize(nome)
        if not alvo:
            return None
        for presente in self.gifts:
            if _normalize(presente.name) == alvo:
                return presente
            if alvo in {_normalize(alias) for alias in presente.aliases}:
                return presente
        return None

    def por_nome_parcial(self, nome: str) -> Optional[Presente]:
        """Igual `por_nome`, mas aceitando subtexto ('universo' em 'universo tiktok')."""
        alvo = _normalize(nome)
        if not alvo:
            return None
        for presente in sorted(self.gifts, key=lambda item: len(item.name), reverse=True):
            if len(alvo) >= 4 and _normalize(presente.name) in alvo:
                return presente
            for alias in presente.aliases:
                if len(alias) >= 4 and alias in alvo:
                    return presente
        return None


def _normalize(texto: str) -> str:
    from shared.commands import normalize

    return normalize(texto)


@lru_cache(maxsize=4)
def load(path: str | None = None) -> CatalogoPresentes:
    """Le `config/presentes.json`; arquivo ausente = catalogo vazio (so o piso)."""
    alvo = pathlib.Path(path) if path else pathlib.Path(config.get_str("PRESENTES_CONFIG") or DEFAULT_PATH)

    dados: Dict[str, object] = {}
    if alvo.is_file():
        try:
            dados = json.loads(alvo.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as err:
            print(f"[presentes] JSON invalido em {alvo} ({err}); usando piso")

    gifts: List[Presente] = []
    for bruto in dados.get("gifts", []) or []:
        nome = _normalize(str(bruto.get("name", "")))
        if not nome:
            continue
        aliases = tuple(_normalize(str(a)) for a in (bruto.get("aliases") or []) if _normalize(str(a)))
        gifts.append(Presente(
            name=nome,
            coins=int(bruto.get("coins", 0) or 0),
            emoji=str(bruto.get("emoji", ""))[:4],
            effect=str(bruto.get("effect", NITRO)).upper(),
            aliases=aliases,
        ))

    tiers: List[Tuple[str, Optional[int], int]] = []
    for bruto in dados.get("tiers", []) or []:
        maximo = bruto.get("maxCoins")
        tiers.append((
            str(bruto.get("id", "x"))[:12],
            None if maximo is None else int(maximo),
            int(bruto.get("multiplier", 1)),
        ))
    if not tiers:
        tiers = [("x", 19, 1), ("x", 199, 2), ("x", 999, 3),
                 ("x", 4999, 4), ("x", 14999, 6), ("x", None, 8)]

    return CatalogoPresentes(gifts=gifts, tiers=tuple(tiers))


def coins_conhecidas(gift_name: Optional[str]) -> int:
    """Valor em moedas pelo nome, quando a lib nao mandou (0 = nao sei)."""
    if not gift_name:
        return 0
    catalogo = load()
    presente = catalogo.por_nome(gift_name) or catalogo.por_nome_parcial(gift_name)
    return presente.coins if presente else 0


def emoji_de(gift_name: Optional[str]) -> str:
    if not gift_name:
        return "🎁"
    catalogo = load()
    presente = catalogo.por_nome(gift_name) or catalogo.por_nome_parcial(gift_name)
    return (presente.emoji if presente and presente.emoji else "🎁")


def classify(gift_name: Optional[str]) -> str:
    """Categoria pelo nome: primeiro o catalogo, depois as palavras-chave do .env."""
    if not gift_name:
        return NITRO

    catalogo = load()
    presente = catalogo.por_nome(gift_name)
    if presente:
        return presente.effect
    parcial = catalogo.por_nome_parcial(gift_name)
    if parcial:
        return parcial.effect

    from_env = _keywords_do_env()
    normalizado = _normalize(gift_name)
    if normalizado in from_env:
        return from_env[normalizado]
    for palavra, efeito in sorted(from_env.items(), key=lambda item: len(item[0]), reverse=True):
        if len(palavra) >= 4 and palavra in normalizado:
            return efeito
    return NITRO


def _keywords_do_env() -> Dict[str, str]:
    """GIFT_*_KEYWORDS do .env (ou os defaults), indice palavra -> efeito."""
    indice: Dict[str, str] = {}
    for efeito, entradas in DEFAULT_KEYWORDS.items():
        bruto = config.get_str(f"GIFT_{efeito}_KEYWORDS")
        if not bruto:
            bruto = ", ".join(entradas)
        for palavra in bruto.split(","):
            limpa = _normalize(palavra)
            if limpa:
                indice.setdefault(limpa, efeito)
    return indice


def magnitude(diamond_count: Optional[int] = None, gift_name: Optional[str] = None) -> int:
    """Multiplicador pela faixa de valor; usa o catalogo quando o valor nao veio."""
    moedas: Optional[int]
    try:
        moedas = int(diamond_count) if diamond_count is not None else None
    except (TypeError, ValueError):
        moedas = None

    if not moedas:
        moedas = coins_conhecidas(gift_name) or None
    if not moedas:
        return 1

    for _id, maximo, multiplicador in load().tiers:
        if maximo is None or moedas <= maximo:
            return multiplicador
    return 1


def tier_label(diamond_count: Optional[int] = None, gift_name: Optional[str] = None) -> str:
    """Rotulo curto da faixa: 'comum x1', 'lendario x8'."""
    multiplicador = magnitude(diamond_count, gift_name)
    for identificador, _maximo, valor in load().tiers:
        if valor == multiplicador:
            return f"{identificador} x{valor}"
    return f"x{multiplicador}"


def describe(gift_name: Optional[str], diamond_count: Optional[int] = None) -> Dict[str, object]:
    """Tudo que um jogo precisa saber sobre um presente, em uma chamada."""
    efeito = classify(gift_name)
    moedas = int(diamond_count or 0) or coins_conhecidas(gift_name)
    return {
        "name": (gift_name or "")[:40],
        "emoji": emoji_de(gift_name),
        "effect": efeito,
        "label": EFFECT_LABELS.get(efeito, efeito),
        "coins": moedas,
        "multiplier": magnitude(diamond_count, gift_name),
        "tier": tier_label(diamond_count, gift_name),
    }


#: mantido por compatibilidade com quem importa daqui
VALUE_TIERS = tuple((maximo, valor) for _id, maximo, valor in load().tiers)

__all__ = [
    "NITRO", "OIL", "TURBO", "POINTS", "EFFECT_LABELS", "Presente", "CatalogoPresentes",
    "load", "classify", "magnitude", "tier_label", "describe", "coins_conhecidas", "emoji_de",
]
