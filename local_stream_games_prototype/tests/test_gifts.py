"""Testes do mapeamento de presentes (tabela BR) e do efeito por valor."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))          # _harness
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # projeto

from _harness import PORT, PROJECT, check, finish  # noqa: E402

from shared import gifts as gift_lib  # noqa: E402
from server.games import build  # noqa: E402

# (nome, moedas, categoria esperada) — tabela real da live brasileira
TABLE = [
    ("Rosa", 1, gift_lib.NITRO),
    ("GG", 1, gift_lib.NITRO),
    ("Casquinha de Sorvete", 1, gift_lib.NITRO),
    ("Panda", 5, gift_lib.NITRO),
    ("Perfume", 20, gift_lib.NITRO),
    ("Eu Te Amo", 49, gift_lib.NITRO),
    ("Confete", 100, gift_lib.NITRO),
    ("Óculos de sol", 199, gift_lib.NITRO),
    ("Chuva de Dinheiro", 500, gift_lib.OIL),
    ("Bola de Espelhos", 1000, gift_lib.TURBO),
    ("Galáxia", 1000, gift_lib.TURBO),
    ("Sereia", 2988, gift_lib.TURBO),
    ("Avião", 6000, gift_lib.TURBO),
    ("Planeta", 15000, gift_lib.TURBO),
    ("Voo Diamante", 18000, gift_lib.TURBO),
    ("Leão", 29999, gift_lib.TURBO),
    ("Mini Leão", 29999, gift_lib.TURBO),
    ("Universo TikTok", 44999, gift_lib.TURBO),
]

print("\n== 1. nome -> categoria (nomes reais BR) ==")
for name, coins, expected in TABLE:
    got = gift_lib.classify(name)
    check(f"{name} ({coins}) -> {expected}", got == expected, f"got={got}")

print("\n== 2. acento e casing ==")
for variant in ["ROSA", "rosa", "rosA", "universo tiktok", "UNIVERSO TIKTOK", "aviao", "avião", "Avião"]:
    got = gift_lib.classify(variant)
    check(f"classify({variant!r})", got in (gift_lib.NITRO, gift_lib.OIL, gift_lib.TURBO), got)

print("\n== 3. valor em moedas -> multiplicador ==")
for coins, expected in [(1, 1), (5, 1), (20, 2), (199, 2), (500, 3), (1000, 4), (2988, 4),
                        (6000, 6), (15000, 8), (44999, 8), (0, 1), (None, 1)]:
    got = gift_lib.magnitude(coins)
    check(f"{coins} moedas -> x{expected}", got == expected, f"got={got}")

print("\n== 4. presente caro tem que valer mais que o barato ==")
corrida = build("corrida")

def boost_for(name, coins):
    game = build("corrida")
    game.handle_event({"event": "comment", "user": "ana", "text": "oi"})
    game.handle_event({"event": "gift", "user": "ana", "gift": name, "value": coins, "count": 1})
    # cars[0] e um dos fixos (Vitinmilgrau/Narutobebado); o da ana vem depois
    ana = next(car for car in game.cars if car.user == "ana")
    return ana.boost

rosa, universo = boost_for("Rosa", 1), boost_for("Universo TikTok", 44999)
galaxia = boost_for("Galáxia", 1000)
check("Universo TikTok impulsiona muito mais que Rosa", universo > rosa * 4, f"{universo} vs {rosa}")
check("Galáxia fica entre os dois", rosa < galaxia < universo, f"{rosa} < {galaxia} < {universo}")
check("impulso tem teto (nao quebra a corrida)", universo <= 88, str(universo))

print("\n== 5. duelo: presente caro levanta mais blocos ==")
def blocks_for(name, coins):
    game = build("duelo")
    game.handle_event({"event": "comment", "user": "ana", "text": "lula"})
    before = game.towers[0].height
    game.handle_event({"event": "gift", "user": "ana", "gift": name, "value": coins, "count": 1})
    return game.towers[0].height - before

rosa_b, universo_b = blocks_for("Rosa", 1), blocks_for("Universo TikTok", 44999)
check("Universo levanta bem mais que Rosa", universo_b > rosa_b * 2, f"{universo_b} vs {rosa_b}")
check("blocos por presente tem teto (16)", universo_b <= 16, str(universo_b))

print("\n== 6. pipa: presente caro corta mais linhas ==")
def cuts_for(name, coins):
    game = build("pipa")
    # 3 pipas por viewer: assim da pra ver a diferenca de quantas linhas caem
    for i in range(8):
        for _ in range(3):
            game.handle_event({"event": "comment", "user": f"u{i}", "text": "oi"})
    out = game.handle_event({"event": "gift", "user": "u0", "gift": name, "value": coins, "count": 1})
    return out[0]["cuts"]

rosa_c, universo_c = cuts_for("Rosa", 1), cuts_for("Universo TikTok", 44999)
check("Universo corta mais que Rosa", universo_c > rosa_c, f"{universo_c} vs {rosa_c}")
check("cortes tem teto (10)", universo_c <= 10, str(universo_c))

print("\n== 7. presente desconhecido nao some (piso = nitro x1) ==")
info = gift_lib.describe("Presente Que Nao Existe 9999", 0)
check("categoria piso", info["effect"] == gift_lib.NITRO, str(info["effect"]))
check("multiplicador piso", info["multiplier"] == 1, str(info["multiplier"]))
check("describe traz moedas e faixa", info["coins"] == 0 and "x1" in str(info["tier"]), str(info))
rich = gift_lib.describe("Universo TikTok", 44999)
check("describe do Universo", rich["multiplier"] == 8 and "lendario" in str(rich["tier"]), str(rich))

finish()
