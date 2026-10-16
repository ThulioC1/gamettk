# AGENTS.md — instruções para qualquer IA que mexer neste repositório

> **Leia este arquivo ANTES de alterar qualquer coisa.** Ele existe para que uma
> IA em sessão nova (ou outra IA) não precise redescobrir o projeto, não repita
> bugs já resolvidos e não quebre as decisões de quem maintaina.
>
> **Toda alteração tem de ser registrada em `CHANGELOG.md`** (seção nova no
> topo). Se você não registrou, seu trabalho está incompleto.

---

## 0. Contrato (leia e respeite)

1. **Leia `AGENTS.md` (este arquivo) e `CHANGELOG.md` antes de editar.**
2. **Rode a suíte antes e depois**: `python3 tests/run_all.py`. Não diga que está
   pronto com teste vermelho.
3. **Registre a mudança** no topo de `CHANGELOG.md`: o que, por quê, arquivos
   tocados, como verificou.
4. **Não mude de escopo.** Se o pedido é "adicione um jogo", não refatore o
   servidor; se o pedido é "mude X", não mexa em Y. Mudança de escopo não pedida
   é como regressão entra.
5. **Se algo estiver errado neste arquivo** (desatualizado, mentindo), corrija o
   arquivo junto com a mudança e diga isso no changelog.
6. **Nada de segredo no repositório.** `EULER_API_KEY` e `GAME_TOKEN` vão no
   `.env`, que está no `.gitignore`.

## 1. O que é este projeto

Launcher de jogos que a **live do TikTok joga com a plateia**: cada comentário,
presente, like ou follow vira um evento; o jogo decide o efeito; o navegador só
desenha. Tudo local, sem serviço pago.

- Projeto: `local_stream_games_prototype/` (Python 3.10+, asyncio, sem framework web)
- Bugro de dados: TikTok é **API não-oficial** (reverse engineering). Pode
  quebrar sem aviso — se a lib mudar, o problema provavelmente está na lib.
- Ambiente de produção: **Kali Linux**, em máquina própria ou VPS. Desenvolvimento
  acontece em Windows. **Código tem que rodar nos dois**: nada de caminho com
  `\`, nada de dependência de sistema específico.
- Comentários e mensagens de log em **português do Brasil**, sem acento quando
  forem identificadores/código (o console do Python é cp1252 em Windows e quebrou
  testes mais de uma vez).

## 2. Arquitetura em 6 linhas

```
live → tiktok/bot.py (TikTokLive em thread) → WebSocket JSON
     → server/server.py (HTTP + WS, loop 60 Hz) → server/games/<jogo>.py (regra)
     → client/renderers/<jogo>.js (Canvas)
```

- **O servidor é dono do estado.** O client nunca inventa posição; ele desenha o
  snapshot e envia eventos.
- **Contrato de jogo**: `server/base.py::GameBase` com `handle_event`, `update`,
  `snapshot`, `describe`. Um jogo novo é **um arquivo em `server/games/` + um
  renderer em `client/renderers/`**, sem tocar em servidor, bot nem simulador.
- **Jogos**: `corrida` (Corrida na Live), `duelo` (Lula × Flávio Bolsonaro),
  `pipa` (Pipa Arena), `platformer` (demo).
- **Personalização por dados**: `config/duel.json` e `config/pipa.json` descrevem
  confronto/arena sem tocar em código; `shared/sides.py` e `shared/pipas.py`
  carregam e validam.
- **Segurança**: `GAME_TOKEN` protege o envio de eventos (comentário/presente).
  Sem token, quem assiste não envia nada.
- **Deploy**: `deploy/install.sh` sobe `streamgames-server` e `streamgames-bot`
  no systemd.

## 3. Comandos que importam

```bash
# suíte completa (porta livre por teste, ~90 s)
python3 tests/run_all.py
python3 tests/run_all.py duelo      # só um arquivo
python3 tests/run_all.py corrida render   # só alguns

# jogo local sem TikTok (dois terminais)
python3 server/server.py --game duelo      # http://localhost:8080
python3 simulator/simulator.py --auto      # live fictícia

# live real
python3 tiktok/bot.py --username fulano     # le o .env
python3 tiktok/bot.py --list                # confere config sem conectar

# deploy (Kali)
bash deploy/install.sh fulano
curl -s localhost:8080/health
```

## 4. Regras que não se negociam

| Regra | Porquê |
|---|---|
| Comentário/presente só chega ao jogo por `handle_event` | quem valida é o servidor, não o client |
| Eventos de live exigem `GAME_TOKEN` quando configurado | sem isso, qualquer visitor injeta eventos falsos |
| `shared/config.py::DEFAULTS` lista **toda** chave usada | chave fora da lista cai no `minimum` do `get_int` (bug real: `CAR_MAX` virou 1) |
| Todo jogo devolve snapshot **serializável em JSON** (só tipos simples) | vai cru pelo WebSocket a 30 Hz |
| Client só desenha o snapshot; não simula física | latência de interpolação é ok, inconsistência não |
| Limite de potência em presente (boost, blocos, cortes) | presente de 45.000 moedas zerava a partida |
| Velocidade mostrada tem teto (`KMH_MAX`) | sem isso a placa exibia 1300 km/h num turbo |
| Cooldown por viewer + teto por minuto, em `bot.py` | 200 pessoas na live não podem travar o jogo |
| Teste novo vai em `tests/`, com `check()` do `_harness` | Assertion ad-hoc em arquivo temporário morre com a sessão |
| Toda chave de `.env` em `shared/config.py::DEFAULTS` e no `.env.example` | `tests/test_config.py` falha se faltar uma (já pegou `CAR_MAX` e `LIKE_BOOST_STEP`) |

## 5. Armadilhas já mordidas (não repita)

1. **`ServerConnection.respond()` não aceita `headers=`.** A assinatura é
   `respond(status, text)`. Para trocar header: pegue a resposta e use
   `del response.headers["Content-Type"]` antes de atribuir, senão duplica.
2. **`process_request` não pode servir HTML no handshake.** Se você não checar
   `Upgrade: websocket` e retornar `None`, o handshake responde 200 com HTML e o
   WebSocket falha com `InvalidStatus`.
3. **Atribuição em comprehension é erro de sintaxe**:
   `[x for x in y if (x["life"] -= 0.01) > 0]` → não compila. Use laço.
4. **`del lista[-n:] if cond else None`** também não compila.
5. **Palavra-chave curta casando por subtexto.** `a`/`d` faziam "boa noite"
   virar comando. Hoje o mínimo é `MIN_SUBSTRING_LENGTH = 4`.
6. **Presente não pode estar em duas categorias.** `DEFAULT_KEYWORDS` é lida na
   ordem e o primeiro vence: "chuva de dinheiro" em NITRO e em OIL = NITRO.
7. **Arquivo com acento + escrita por script externo** vira lixo de encoding
   (`FlÃ¡vio`). Use escapes (`"Fl\u00e1vio"`) em script que reescreve arquivo.
8. **Seed aleatório nos jogos** (`random.Random(seed)`) para teste ser
   reprodutível.
9. **Apresentação não é estado.** `snapshot()` não manda campo que só existe para
   desenhar bonito.
10. **`asyncio.create_task()` não aceita Future.** `loop.run_in_executor()`
    devolve Future; embrulhe em `async def` antes de criar a task (bug do modo
    interativo do simulador, que só aparecia digitando no terminal).
11. **REPL com reconexão precisa sinalizar "saiu".** Sem isso, `quit` reconecta e
    re-imprime o help em laço infinito (foi o segundo bug do mesmo trecho).
12. **Caminho de teste só é testado se o teste o exercitar.** Modo interativo,
    flags de CLI e `help` não entram em suíte sozinhos: `tests/test_interativo.py`
    alimenta o simulador por stdin justamente para cobrir isso. Ao mexer em
    entrada do usuário, escreva o teste na mesma hora.
13. **Renderer quebrado não aparece em teste de back-end.** O servidor pode
    responder 200, o WebSocket mandar estado e a tela continuar vazia. Rode
    `node tests/render_check.mjs` (ou `python3 tests/run_all.py`, que já chama)
    sempre que mexer em `client/renderers/`. Cuidado com assinatura x chamada:
    `drawPops(context, scope, delta)` chamada como `drawPops(context, view.delta)`
    quebrou a Corrida inteira.
14. **Argumento e posição da chamada precisam bater.** No Python, sigilo em
    keyword; em JS, o nome importa igual. Erro desses só aparece em runtime.
15. **Script que reescreve arquivo apaga indentação.** Vários `IndentationError`
    vieram de patch por string.replace; depois de mexer, rode `py -c "import
    server.games.<modulo>"` antes da suíte. O erro aparece longe da causa.
16. **Teste que fala com servidor velho passa errado.** Se a execução anterior
    morreu antes do `terminate`, o processo órfão fica ouvindo na porta e o teste
    mede o estado antigo (verde ou vermelho, sempre errado). `run_server()` agora
    recusa subir em porta ocupada — se ele reclamar, mate o processo. No Windows:
    `Get-CimInstance Win32_Process -Filter "Name like 'python%'"` e veja se há
    `server/server.py` vivo.
17. **`game_event` chega antes do primeiro `state`.** O `event` é empurrado na hora,
    mas o snapshot só sai a cada `BROADCAST_EVERY_TICKS` (2). Cliente que faz
    `break` ao ver o `winner` nunca leu um estado — foi o que zerou `torres subiram`
    no `test_duelo` (`[0, 0]`).
18. **`reset()` não zera mais a corrida.** A fase `esperando` resolve quem aciona a
    largada; `reset()` devolve as pessoas para a plateia. Teste que contava carros na
    pista depois do `reset()` tem que usar a fase, não o `reset()`.

## 6. Multijogo (desde 2026-10-16)

O servidor roda **todos** os jogos em paralelo; cada conexão assiste um:

- `?game=<tipo>` na URL define o jogo inicial (é o que o OBS usa).
- `{"type":"watch","game":"<tipo>"}` troca em tempo real, sem recarregar.
- Eventos vão para o jogo que **quem enviou** está assistindo (o bot conecta com
  `?game=` do `.env`, então a live dirige o jogo configurado).
- Cada estado é transmitido só para quem assiste aquele jogo — por isso o
  broadcast recebe o `game_type` como filtro.
- `GameBase` continua igual; `--game` só define o **padrão** do launcher.

## 7. Ao adicionar um jogo (checklist)

- [ ] `server/games/meu_jogo.py` herdando `GameBase`; `type` único em minúsculas.
- [ ] Registrar em `server/games/__init__.py` (`GAMES`).
- [ ] `client/renderers/meu_jogo.js` com `export function create()` retornando
      `{width, height, keyboard, controls, hud, draw, onEvent?, onGameEvent?}`.
- [ ] Adicionar o renderer em `client/client.js::RENDERERS`.
- [ ] `describe()` com `title` e `callToAction` (vão para o HUD).
- [ ] Teste em `tests/test_meu_jogo.py` cobrindo: evento vira efeito, estado
      serializa, vitória/reset.
- [ ] `python3 tests/run_all.py` verde.
- [ ] Entrada no `CHANGELOG.md` e no `README.md` (tabela de jogos + regras).

## 8. State of the art (não é verdade pra sempre)

- WebSocket: `websockets>=14`, API `websockets.asyncio.server`.
- Presente: campo de moedas é `gift.diamond_count`; nome é `gift.name`; streak
  deve ser ignorado enquanto `event.streaking` for verdadeiro.
- Presente→efeito tem três camadas: **nome** (categoria), **moedas** (potência,
  faixas em `shared/gifts.py::VALUE_TIERS`) e **catálogo** — quando a lib não manda
  o valor, `shared/gifts.py::coins_conhecidas` procura o nome em
  `config/presentes.json` (29 presentes, com emoji). Presente desconhecido = NITRO ×1.
- Login no TikTok não é usado (só leitura). Não introduza sem o usuário pedir:
  risco de banimento da conta dele.

## 8.1 Referência externa (desde 2026-10-16)

`https://github.com/vamnguyen/tiktok-live-games.git` foi avaliado e **parcialmente
adotado** (backoff+jitter, catálogo de presentes, fase `esperando`, `/debug`).
O que **não** foi adotado, e por quê:

- O jogo dele roda **no navegador** (`race-engine.js`); cada viewer simula o seu.
  Aqui o servidor é dono do estado e o client só desenha — senão a tela do OBS e a
  de quem assiste divergem, e ninguém consegue dirigir a partida.
- `cors: "*"` e envio de evento sem token: qualquer visitor injeta evento falso.
  Aqui é `GAME_TOKEN` (armadilha/regras acima).
- Sem cooldown por viewer nem teto por minuto: 200 pessoas na live travam o jogo.
- Zero testes. `tests/test_referencia.py` fixa o que foi pego de lá **e** o motivo
  de não pegar o resto, para a próxima IA não "voltar" para a arquitetura antiga.

## 9. Registro de mudanças

`CHANGELOG.md` é append-only, mais recente no topo, com uma entrada por sessão.
Leia as últimas antes de mexer: elas dizem o que já foi tentado e por que.
