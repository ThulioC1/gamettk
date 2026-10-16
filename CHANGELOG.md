# CHANGELOG

Append-only. **Mais recente no topo.** Uma entrada por sessão.
Detalhe de arquitetura e regras de bolso: `AGENTS.md`.

---

## 2026-10-16 — modo interativo do simulador quebrado (achado pelo usuário no Kali)

**O quê**
- `simulator/simulator.py`: `asyncio.create_task(loop.run_in_executor(None,
  input, ...))` → `TypeError: a coroutine was expected, got <Future>`.
  Agora existe `async def read_line()` como wrapper, e EOF/Ctrl+D encerram limpo.
- `quit` não saía: o `main()` reconectava em laço infinito e re-imprimia o help
  (pior que o traceback, porque fica parecendo travado). `interactive_mode` agora
  devolve `False` para "usuário quer sair".
- Implementado `jogo <COMANDO>` no REPL: estava no `help` desde o começo mas nunca
  existiu no código (doc mentindo sobre código).
- Novo teste `tests/test_interativo.py`, no `run_all`.

**Por quê**
O usuário rodou no Kali (Python 3.14) e o simulador morreu no primeiro comando. Os
testes passavam porque só cobriam `--auto`: **modo interativo, flags de CLI e
`help` nunca foram exercitados**. Dois bugs de Once misses de primeira linha
moravam exatamente ali.

**Arquivos tocados**
`simulator/simulator.py`, `tests/test_interativo.py`, `tests/run_all.py`,
`AGENTS.md`.

**Como verifiquei**
`python3 tests/run_all.py` → 7 suítes verdes (o teste novo alimenta o simulador
por stdin e confere que comentário/presente/like/follow/comando chegam no
servidor e que o processo sai com código 0).

**Lição registrada no AGENTS.md**
`run_in_executor` devolve Future, `create_task` quer coroutine; e caminho de
teste só conta se o teste o exercitar.

---

## 2026-10-16 — memória de IA + testes no repositório

**O quê**
- Criado `AGENTS.md` na raiz: contrato para qualquer IA ler antes de mexer
  (ler → rodar suíte → registrar no changelog → respeitar escopo), mapa da
  arquitetura, regras não negociáveis e as 9 armadilhas já mordidas nesta sessão.
- Criado `CHANGELOG.md` (este arquivo) com o histórico da sessão anterior.
- Testes movidos de pasta temporária para dentro do projeto, em `tests/`,
  com `tests/_harness.py` (porta livre por teste, `check()`, `finish()`,
  `run_server()`) e `tests/run_all.py` para rodar tudo (`python3 tests/run_all.py`).
- Corrigido `.gitignore` e `README.md` para refletir o layout novo.

**Por quê**
A regra "sempre rode os testes antes de dizer que está pronto" era inútil: os
scripts viviam em `%TEMP%`, que morre com a sessão. Sem os testes no repo, uma IA
nova não tem como verificar nada e a memória de sessão vira a única fonte de
verdade — exatamente o que o `AGENTS.md` tenta substituir.

**Como verifiquei**
`python3 tests/run_all.py` → gifts/corrida/duelo/pipa/token/simulador, todos PASS,
zero erro no log do servidor.

**Armadilha nova que entrou na lista**
Escrever arquivo com acento por script externo (via PowerShell/Python) corrompe o
encoding — use escape (`"Fl\u00e1vio"`) e leia de volta para conferir.

---

## 2026-10-16 — Duelo de Torres, Pipa Arena, presentes por valor, GAME_TOKEN

**O quê**
- `server/games/duelo.py` + `client/renderers/duelo.js`: Duelo de Torres
  **Lula (PT) × Flávio Bolsonaro (PL)**, 1 bloco por comentário, presentes
  empilham ou sabotam, torre desaba quando inclina demais, 32 blocos para vencer.
- `server/games/pipa_arena.py` + `client/renderers/pipa_arena.js`: Pipa Arena —
  cada comentário solta uma pipa; presente corta linhas de pipas rivais; quanto
  mais pipas no céu, mais altitude.
- Núcleo agnóstico ao jogo: `server/base.py::GameBase`, registro em
  `server/games/__init__.py`, seletor de jogo no launcher e `?game=<nome>`.
- Personalização por dados: `config/duel.json` (lados, partido, cor, palavras,
  meta, valores) e `config/pipa.json`, com `DUEL_CONFIG`/`PIPA_CONFIG` no `.env`.
- `shared/gifts.py` reescrito com a tabela real de presentes brasileiros: efeito
  por **nome** (Rosa→NITRO, Chuva de Dinheiro→ÓLEO, Universo TikTok→TURBO) e
  potência por **valor em moedas** (`gift.diamond_count`, faixas ×1 a ×8).
- `GAME_TOKEN`: eventos de live (comentário/presente) exigem token quando
  configurado. Sem token, quem assiste só assiste. Antes, qualquer WebSocket
  aberto injetava eventos.
- Bot agora manda o valor em moedas e ignora o meio do streak de presente.
- Deploy: `deploy/install.sh` + duas units systemd (`streamgames-server`,
  `streamgames-bot`) e seção de implantação no README (local, VPS, HTTPS).

**Por quê**
O pedido era "duelo personalizado Lula x Flávio" e depois Pipa Arena. O núcleo
precisava virar agnóstico para que cada jogo novo custasse um arquivo de regra +
um renderer. A tabela de presentes do usuário mostrou que o mapeamento antigo
estava errado: todo presente brasileiro caía no fallback, então um Universo TikTok
de ~R$ 1.350 valia o mesmo que uma Rosa de R$ 0,06.

**Arquivos tocados**
`server/base.py`, `server/server.py`, `server/games/{__init__,corrida,duelo,pipa_arena,platformer}.py`,
`client/{index.html,client.js,style.css,renderers/*.js}`,
`shared/{config,commands,gifts,sides,pipas}.py`,
`config/{duel,pipa}.json`, `tiktok/bot.py`, `simulator/simulator.py`,
`deploy/*`, `README.md`, `.env.example`, `.gitignore`.

**Como verifiquei**
Suíte completa (corrida, duelo, pipa, presentes, token, simulador `--auto`) com
todas as verificações verdes e sem erro no log do servidor. Cada correção abaixo
foi achada por teste, não por leitura.

**Bugs corrigidos que merecem memória**
- `update()` do duelo retornava antes de despachar o evento de vitória: o
  vencedor nunca era anunciado.
- Largura da torre (320) vs. do bloco (250) deixava só 10 px de folga: quase todo
  bloco "escorregava" e as torres nunca subiam.
- Presentes grandes (Galaxy ×2 = 16 blocos) zeravam o duelo em duas pessoas;
  teto de 8 por presente → 16.
- Pipa nascia a 120 px de altura (`skyHeight`): uma pipa sozinha "subia".
- "chuva de dinheiro" estava na lista de NITRO e de OIL; NITRO vencia por ordem
  de leitura do dicionário.
- Aviso de sabotagem do duelo perdeu `kind: "sabotage"`, quebrando os destroços
  no renderer.
- `del lista[-n:] if cond else None` e atribuição em comprehension: erro de
  sintaxe que derrubou a importação do módulo inteiro.
- `ServerConnection.respond()` não aceita `headers=` nesta versão do `websockets`.
- `process_request` servia HTML no handshake do WebSocket (o upgrade falhava com
  `InvalidStatus`).