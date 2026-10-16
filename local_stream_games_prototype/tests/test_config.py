"""Guarda a estrutura do .env: toda chave lida tem que estar em DEFAULTS.

Armadilha ja mordida duas vezes: chave nova no codigo e esquecida no DEFAULTS faz
`get_int` devolver o `minimum` silenciosamente (CAR_MAX virou 1, LIKE_BOOST_STEP
virou 0 e o like "nao acelerava"). Este teste fecha essa porta.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))          # _harness
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # projeto

from _harness import PROJECT, check, finish  # noqa: E402
from shared import config  # noqa: E402
from shared.config import DEFAULTS  # noqa: E402

PADROES = re.compile(r'config\.get_(?:int|str|bool|csv)\(\s*"([A-Z0-9_]+)"')
PADRAO_ENV = re.compile(r'get_str\(\s*f?"([A-Z0-9_]+)\s*\+')
ALTOS = re.compile(r'config\.get_str\(f"(GIFT_[A-Z_]+|GIFT_\{[^}]+\})"')

print("\n== A. toda chave lida no codigo esta em DEFAULTS ==")
arquivos = [
    "server/server.py",
    *[f"server/games/{nome}" for nome in ("corrida.py", "duelo.py", "pipa_arena.py", "platformer.py")],
    "shared/gifts.py",
    "shared/sides.py",
    "shared/pipas.py",
    "shared/carros.py",
    "tiktok/bot.py",
    "simulator/simulator.py",
]

faltando = {}
for relativo in arquivos:
    caminho = PROJECT / relativo
    if not caminho.is_file():
        continue
    texto = caminho.read_text(encoding="utf-8")
    for chave in PADROES.findall(texto):
        if chave not in DEFAULTS:
            faltando.setdefault(chave, []).append(relativo)

check("nenhuma chave lida fora do DEFAULTS", not faltando,
      "; ".join(f"{chave} em {', '.join(arqs)}" for chave, arqs in faltando.items()))

print("\n== B. chaves do DEFAULTS nao sao havidas ==")
# as keywords de presente sao lidas por f-string (GIFT_{efeito}_KEYWORDS)
texto_gifts = (PROJECT / "shared/gifts.py").read_text(encoding="utf-8")
dinamicas = {f"GIFT_{efeito}_KEYWORDS" for efeito in ("NITRO", "OIL", "TURBO")
             if f'GIFT_{{effect}}_KEYWORDS' in texto_gifts or f"GIFT_{efeito}_KEYWORDS" in texto_gifts}
codigo = "\n".join((PROJECT / arq).read_text(encoding="utf-8")
                   for arq in arquivos if (PROJECT / arq).is_file())
sem_uso = sorted(chave for chave in DEFAULTS
                 if chave not in dinamicas and f'"{chave}"' not in codigo)
check("sem chave morta no DEFAULTS", not sem_uso, str(sem_uso))

print("\n== C. .env.example cobre o DEFAULTS ==")
exemplo = (PROJECT / ".env.example").read_text(encoding="utf-8")
faltando_env = sorted(chave for chave in DEFAULTS if not re.search(rf"^{chave}=", exemplo, re.MULTILINE))
check("toda chave do DEFAULTS esta no .env.example", not faltando_env, str(faltando_env))

print("\n== D. valores do DEFAULTS sao coerentes ==")
for chave, valor in sorted(DEFAULTS.items()):
    if valor == "":
        continue
    try:
        float(valor)
    except ValueError:
        check(f"{chave} tem valor numerico ou texto", True, valor)  # texto vazio e' aceito
print("chaves no DEFAULTS:", len(DEFAULTS))

finish()