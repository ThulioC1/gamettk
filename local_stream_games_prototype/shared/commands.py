"""Comandos do jogo e traducao de texto (chat) -> comando.

Usado tanto pelo bot do TikTok quanto pelo simulador de console,
para que as duas entradas falem exatamente o mesmo idioma.
"""
from __future__ import annotations

import unicodedata
from typing import Dict, Iterable, Mapping, Optional

MOVE_LEFT = "MOVE_LEFT"
MOVE_RIGHT = "MOVE_RIGHT"
STOP = "STOP"
JUMP = "JUMP"
RESET = "RESET"

#: Comandos aceitos pelo servidor, na ordem de prioridade de execucao.
COMMANDS: tuple[str, ...] = (MOVE_LEFT, MOVE_RIGHT, STOP, JUMP, RESET)

#: Comandos que alteram a direcao horizontal (o ultimo recebido prevalece).
DIRECTION_COMMANDS = frozenset({MOVE_LEFT, MOVE_RIGHT, STOP})

#: Palavras -> comando. PT-BR e EN juntos, porque a live pode misturar idiomas.
DEFAULT_KEYWORDS: Dict[str, str] = {
    "pula": JUMP,
    "pular": JUMP,
    "pulou": JUMP,
    "salta": JUMP,
    "jump": JUMP,
    "esquerda": MOVE_LEFT,
    "esq": MOVE_LEFT,
    "left": MOVE_LEFT,
    "a": MOVE_LEFT,
    "direita": MOVE_RIGHT,
    "dir": MOVE_RIGHT,
    "right": MOVE_RIGHT,
    "d": MOVE_RIGHT,
    "para": STOP,
    "parar": STOP,
    "pare": STOP,
    "stop": STOP,
    "solta": STOP,
    "larga": STOP,
    "reset": RESET,
    "reinicia": RESET,
    "recomeca": RESET,
}

#: Palavras especificas do simulador de console (linha de comando direta).
SIMULATOR_KEYWORDS: Dict[str, str] = {
    **DEFAULT_KEYWORDS,
    "left": MOVE_LEFT,
    "right": MOVE_RIGHT,
    "up": JUMP,
    "space": JUMP,
    "w": JUMP,
    "s": STOP,
    "help": "HELP",
    "auto": "AUTO",
    "quit": "QUIT",
    "exit": "QUIT",
}


#: Comprimento minimo para casar por subtexto. Abbreviations curtas ("esq", "dir")
#: so funcionam quando vem como palavra inteira - senao "boa noite" casaria "a".
MIN_SUBSTRING_LENGTH = 4


def strip_accents(text: str) -> str:
    """Remove acentos: 'pulo' e 'pulo' viram iguais para a busca."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def normalize(text: str) -> str:
    """Minusculas, sem acento e sem pontuacao, para comparar com as palavras."""
    cleaned = strip_accents(text.lower())
    return "".join(char if char.isalnum() or char.isspace() else " " for char in cleaned).strip()


def parse_keywords(raw: Iterable[str]) -> Dict[str, str]:
    """Aceita 'pula:JUMP' e tambem 'pula' (cai no dicionario padrao)."""
    table: Dict[str, str] = {}
    for entry in raw:
        keyword, _, command = entry.partition(":")
        keyword = normalize(keyword)
        if not keyword:
            continue
        if command:
            resolved = command.strip().upper()
            table[keyword] = resolved if resolved in COMMANDS else DEFAULT_KEYWORDS.get(keyword, STOP)
        else:
            default = DEFAULT_KEYWORDS.get(keyword)
            if default:
                table[keyword] = default
    return table


def parse_command(
    text: str,
    keywords: Optional[Mapping[str, str]] = None,
    *,
    match_substring: bool = True,
) -> Optional[str]:
    """Traduz um texto livre ('VAI PRA ESQUERDA!!') em um comando do jogo.

    Prioriza a palavra inteira; se nao houver, aceita subtexto ('esquerda' em
    'vai pra esquerda!!'). Retorna None quando nada bate.
    """
    table = dict(keywords) if keywords is not None else dict(DEFAULT_KEYWORDS)
    normalized = normalize(text)
    if not normalized:
        return None

    tokens = normalized.split()
    # Palavra exata tem prioridade sobre subtexto.
    for token in tokens:
        if token in table:
            return table[token]
    if not match_substring:
        return None

    # Palavras mais longas primeiro, para nao perder 'direita' para 'dir'.
    for keyword in sorted(table, key=len, reverse=True):
        if len(keyword) < MIN_SUBSTRING_LENGTH:
            continue
        if keyword in normalized:
            return table[keyword]
    return None


def describe_commands() -> str:
    """Texto de ajuda do simulador."""
    grouped: Dict[str, list[str]] = {}
    for word, command in SIMULATOR_KEYWORDS.items():
        if command in COMMANDS:
            grouped.setdefault(command, []).append(word)

    lines = ["Comandos aceitos:"]
    for command in COMMANDS:
        words = ", ".join(sorted(grouped.get(command, [])))
        lines.append(f"  {command:<11} -> {words}")
    lines.append("  auto        -> liga/desliga o envio automatico de comandos")
    lines.append("  help        -> mostra esta ajuda")
    lines.append("  quit        -> encerra o simulador")
    return "\n".join(lines)
