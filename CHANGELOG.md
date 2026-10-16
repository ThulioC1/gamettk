# CHANGELOG

Append-only. **Mais recente no topo.** Uma entrada por sessão.
Detalhe de arquitetura e regras de bolso: `AGENTS.md`.

---

## 2026-10-16 — Corrida na Live no formato da referência (modelos/2.jpeg)

**O quê**
- **Contagem regressiva**: a corrida começa em `LARGADA EM 00:10`, com todo mundo
  parado a 0 km/h, e o evento `go` dispara o "VALENDO!".
- **Grid de largada e faixas**: os carros entram empilhados (`GRID_COLUMNS`,
  `GRID_COLUMN_GAP`, `GRID_ROW_GAP`, `CAR_LANES`) em vez de todos em `dist≈0`.
- **Placa por carro** no formato da referência: número da colocação, nome do
  viewer e velocidade em **km/h** (`KMH_FACTOR`).
- **Catálogo de veículos**: `config/carros.json` + `shared/carros.py` com Gol,
  Uno, Chevette, Fusca, Opala, Kombi, Celta, Palio, Yaris, Corolla, G8 e as motos
  160, Biz, PCX, Pop 100, S1000, XRE 300 — cada um com cor e velocidade. O
  viewer pede o carro no comentário ("tenho um gol", "vou de moto biz") ou ganha
  um sorteado; pode trocar a qualquer momento.
- Renderer reescrito: cidade em parallax, pista com faixas, painéis
  "CARROS DISPONÍVEIS"/"MOTOS" à esquerda, liderança à direita, banner central de
  evento, linha de largada e chegada, moto desenhada diferente de carro.
- Fases explícitas no snapshot: `countdown` / `racing` / `over`.
- `like` passou a dar um empurrão (antes só pontuava).
- `tests/_harness.py`: espera a porta ficar pronta em vez de dormir tempo fixo
  (a suite ficou instável quando o teste anterior ainda soltava a porta).

**Por quê**
O usuário mandou a imagem da Corrida real e pediu "é assim que quero o game". O
que existia era uma pista com um blob colorido; faltava a linguagem visual do
produto: largada contada, grid, faixas, placa com km/h e o catálogo de carros.

**Arquivos tocados**
`config/carros.json` (novo), `shared/carros.py` (novo),
`server/games/corrida.py` (reescrito), `client/renderers/corrida.js` (reescrito),
`shared/config.py`, `.env.example`, `README.md`, `tests/{test_corrida,_harness,render_check.mjs}`.

**Como verifiquei**
`python3 tests/run_all.py` → 9 suítes verdes. O `render_check.mjs` confere na
tela: ≥3 carros no grid (`x=[286,302,319,336]`), 4 faixas distintas
(`y=[448,379,316,250]`), o texto `LARGADA EM 00:10` e as placas com `180 km/h`.
O `test_corrida.py` ganhou a seção B2 (contagem, grid, faixas, veículo por
palavra, km/h) e um helper `larga()` — sem ele os testes rodavam dentro da
contagem e nada se movia.

---

## 2026-10-16 — carros invisíveis, troca de jogo de verdade, suíte de render

**O quê**
- **Corrida na Live: os carros não apareciam.** Duas causas independentes:
  1. `corrida.js` chamava `drawPops(context, view.delta)` numa função declarada
     `drawPops(context, scope, delta)` — o `scope` recebia um número e
     `scope.pops.filter(...)` estourava **a todo frame**, congelando o canvas
     (era o erro que o usuário viu na tela).
  2. A câmera usava `Math.max(0, ...)`: ficava travada em 0 até o líder passar
     336 px, então todo carro atrás da largada ficava fora da tela.
- Largada em grid (8 por fila), carros maiores (58→78 px), placa com o nome do
  piloto, linha de largada e marcadores de distância a cada 1000 px — para o
  movimento ficar legível na transmissão.
- **Multijogo no servidor**: os quatro jogos agora rodam ao mesmo tempo, cada
  tela assiste o que escolheu (`?game=` na URL) e troca em tempo real com
  `{"type":"watch","game":"..."}`, sem recarregar a página. Antes o servidor rodava
  um jogo só e o seletor não fazia nada (era o "só muda os pixels").
- `share` passou a entrar na pista na Corrida (só `follow` era tratado).
- `?game=nao_existe` derrubava a conexão com 1011 (KeyError) — agora cai no padrão.
- Novo `tests/render_check.mjs`: roda cada renderer fora do navegador contra um
  estado real, e prova que a Corrida desenha ≥3 carros na tela e que a posição
  deles muda com a distância.
- `tests/test_multijogo.py`: welcome por jogo, roteamento de estado, evento indo
  para o jogo certo, troca em tempo real, jogo inválido, follow/share.
- Testes de duelo e pipa passaram a pedir `?game=` na URL.

**Por quê**
O usuário entrou com a imagem da tela vazia e com o 1011 no terminal. O
`render_check.mjs` nasceu porque **renderer quebrado não aparece em teste de
back-end**: o Pythonrespondia 200, o WebSocket funcionava, e mesmo assim a tela
fazia nada. Segundo a regra do `AGENTS.md`, o caminho que quebrou ganhou teste.

**Arquivos tocados**
`client/renderers/corrida.js`, `client/client.js`, `server/server.py`,
`server/games/corrida.py`, `tests/{render_check.mjs,test_multijogo.py,run_all.py,
test_duelo.py,test_pipa.py}`.

**Como verifiquei**
`python3 tests/run_all.py` → 9 suítes verdes (incluindo `render`, que roda em
node). `tests/render_check.mjs` confere x=[293,307,322,336] na largada e
posições diferentes quando os carros avançam.

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