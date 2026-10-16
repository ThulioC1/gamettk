"""Política de reconexão com espera exponencial e jitter.

Ideia adaptada do `tiktokReconnectPolicy.js` do tiktok-live-games: esperar
sempre o mesmo tempo martela o serviço (e cria o `1011 keepalive ping timeout`
que aparecia no terminal). Aqui a espera cresce até um teto, ganha um sorteio
para dessincronizar várias tentativas, e para sozinha depois de N tentativas.

    politica = PoliticaReconexao(base_s=2.0, teto_s=60.0, tentativas=8)
    if politica.pode_tentar():
        await asyncio.sleep(politica.proxima_espera())
    else:
        ... desistir de vez
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Optional, Tuple  # noqa: F401


@dataclass
class PoliticaReconexao:
    """Espera crescente com teto, jitter e contador de tentativas."""

    base_s: float = 2.0
    teto_s: float = 60.0
    tentativas: int = 8
    jitter: float = 0.3                # 0.3 = ate +-30% da espera
    rng: random.Random = field(default_factory=random.Random)

    tentativa: int = 0
    _tentativas_em: list[float] = field(default_factory=list)

    # ------------------------------------------------------------- decisoes
    def pode_tentar(self) -> bool:
        return self.tentativa < self.tentativas

    def registra_falha(self) -> None:
        self.tentativa += 1

    def registra_sucesso(self) -> None:
        """Conexao de pe: zera a contagem (volta a 2 s se cair de novo)."""
        self.tentativa = 0

    def proxima_espera(self) -> float:
        """Quanto esperar (em segundos) antes da proxima tentativa."""
        base = min(self.base_s * (2 ** max(self.tentativa - 1, 0)), self.teto_s)
        desvio = base * self.jitter * (self.rng.random() * 2 - 1)
        return max(0.5, round(base + desvio, 2))

    # ------------------------------------------------------------- historico
    def tentativas_recentes(self, janela_s: float = 120.0) -> int:
        agora = time.monotonic()
        self._tentativas_em[:] = [t for t in self._tentativas_em if agora - t < janela_s]
        return len(self._tentativas_em)

    def registra_tentativa(self) -> None:
        self._tentativas_em.append(time.monotonic())

    def desiste(self) -> bool:
        """Verdadeiro se esgotou as tentativas (o chamador avisa e para)."""
        return self.tentativa >= self.tentativas

    def resumo(self) -> str:
        return (f"{self.tentativa}/{self.tentativas} tentativas, "
                f"proxima espera {self.proxima_espera():.1f}s")


def politica_do_env() -> PoliticaReconexao:
    """Le os parametros do .env (com padroes quando nao vierem)."""
    from shared import config

    return PoliticaReconexao(
        base_s=config.get_int("RECONNECT_BASE_S", minimum=1) or 2,
        teto_s=config.get_int("RECONNECT_MAX_S", minimum=5) or 60,
        tentativas=config.get_int("RECONNECT_ATTEMPTS", minimum=1) or 8,
    )


__all__ = ["PoliticaReconexao", "politica_do_env"]
