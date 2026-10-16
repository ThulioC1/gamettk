# Stream Games Interativos (protótipo local)

Launcher de jogos que a **live do TikTok joga junto com a plateia**.
Cada comentário, presente, like ou follow vira um evento; o jogo decide o que
fazer com ele e o navegador só desenha o resultado.

| Jogo | Regra |
|---|---|
| **Corrida na Live** (`corrida`) | quem comenta entra na pista; presentes viram nitro, óleo e ultrapassagem |
| **Duelo de Torres** (`duelo`) | Lula × Flávio Bolsonaro: cada comentário ergue 1 bloco do seu lado |
| **Pipa Arena** (`pipa`) | cada comentário solta uma pipa no céu; presente corta a linha do rival |
| **Platformer** (`platformer`) | demo com comandos diretos (teclado/simulador) |

```
live do TikTok
      │  comentário / presente / like / follow
      ▼
tiktok/bot.py        TikTokLive + cooldown por viewer + teto global
      │  WebSocket (JSON)
      ▼
server/server.py     HTTP (client) + WebSocket (eventos), loop de 60 Hz
      │  delega cada evento
      ▼
server/games/*.py    regra do jogo (corrida, duelo, pipa_arena, platformer)
      │  snapshot ~30x/s
      ▼
client/              Canvas no navegador (OBS: fonte de navegador)
```

O servidor é o dono do estado. Nada de posição inventada pelo client: chat,
simulador e teclado passam pelo mesmo caminho.

---

## 1. Requisitos (Kali Linux)

- Python 3.10+ (`python3 --version`) — o Kali já traz
- `python3-venv`, para não mexer no Python do sistema:

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip
```

## 2. Instalação

```bash
cd local_stream_games_prototype
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## 3. Configuração (.env)

```ini
PORT=8080            # HTTP + WebSocket
GAME=corrida         # jogo inicial: corrida | duelo | pipa | platformer

TIKTOK_USERNAME=seu_usuario    # quem está ao vivo (sem @)
EULER_API_KEY=                 # chave gratuita: https://www.eulerstream.com

COMMAND_COOLDOWN_MS=350        # evento mínimo por viewer
COMMAND_RATE_LIMIT_PER_MIN=180 # teto da live inteira (0 = sem teto)
```

Sobre a `EULER_API_KEY`: o TikTok não assina o WebSocket da live, e a biblioteca
usa um servidor de assinatura de terceiros (Euler Stream). Sem chave funciona com
limite baixo de requisições; a conta gratuita aumenta o limite.

Tuning da corrida (todas opcionais, com padrão em `.env.example`):
`TRACK_LENGTH`, `CAR_BASE_SPEED`, `COMMENT_BOOST`, `NITRO_BOOST`, `TURBO_BOOST`,
`BOOST_FRAMES`, `SPIN_FRAMES`, `CAR_MAX`, `POINT_PER_COMMENT`.

Mapa de presentes → efeitos (seção 6):
`GIFT_NITRO_KEYWORDS`, `GIFT_OIL_KEYWORDS`, `GIFT_TURBO_KEYWORDS`.

## 4. Rodando

### 4.1 Sem TikTok (para testar)

```bash
python3 server/server.py                     # http://localhost:8080
python3 simulator/simulator.py --auto        # outra terminal: live fictícia
```

O simulador `--auto` cria viewers fictícios comentando, mandando presentes e
likes — é o jeito mais rápido de ver a pista se enchendo.

Modo console, evento por evento (cada comando responde com `>>` do jogo):

```
evento> carro gol          # escolhe/troca o carro
evento> gol                # atalho: só o nome do carro já escolhe
evento> comento vou ganhar
evento> presente Galaxy    # presente com nome e valor em moedas
evento> like
evento> follow
evento> auto               # liga/desliga a live simulada
evento> help / quit
```

### 4.2 Com a live do TikTok

```bash
# terminal 1
python3 server/server.py

# terminal 2
source .venv/bin/activate
python3 tiktok/bot.py --username seu_usuario
```

Confira a configuração antes de abrir a live:

```bash
python3 tiktok/bot.py --list
```

O HUD mostra `TikTok: @voce ao vivo` quando a conexão está boa. Se o criador não
estiver ao vivo, o bot avisa e tenta de novo a cada 30 s.

### 4.3 Escolhendo o jogo

```bash
python3 server/server.py --game duelo       # sobe direto no Duelo de Torres
```

No navegador, o seletor no topo troca sem reiniciar o servidor, ou por URL:
<http://localhost:8080/?game=pipa>.

### 4.4 Rodando os testes

```bash
cd local_stream_games_prototype

python3 tests/run_all.py              # suíte inteira (~90 s)
python3 tests/run_all.py corrida      # só um jogo
python3 tests/run_all.py config render

node tests/render_check.mjs           # só os renderers (precisa de node)
```

Cada teste imprime `OK`/`FAIL` por verificação e termina com `TUDO VERDE` ou
`FALHAS: [...]`. Para testar um trecho só:

```bash
python3 tests/test_corrida.py   # regra da corrida
python3 tests/test_config.py    # .env: chave faltando no DEFAULTS
python3 tests/test_interativo.py  # console do simulador (envia comandos de verdade)
```

Os testes sobem o servidor sozinhos em uma porta livre (não briga com o servidor
que você está usando no 8080) e o `render_check` roda os renderers fora do
navegador, com um canvas falso.

## 5. As regras de cada jogo

### 5.1 Corrida na Live

Formato de referência em `modelos/2.jpeg`: contagem regressiva, grid de largada,
carros empilhados em faixas, placa com número/nome/velocidade e catálogo de veículos.

| Evento da live | O que acontece |
|---|---|
| comentário (viewer novo) | entra no grid, no carro que a pessoa pediu ou num sorteado |
| comentário com o nome do carro ("tenho um gol", "vou de moto biz") | troca o veículo na hora |
| comentário (quem já tem carro) | acelera o próprio carro |
| like | pontua e dá um empurrão |
| follow / share | entra na pista como se fosse comentário |
| presente NITRO | impulso temporário |
| presente ÓLEO | mancha na pista; quem passa derrapa |
| presente ULTRAPASSAGEM | impulso forte + ganha posição na hora |
| primeiro a cruzar a chegada | vence, e a próxima corrida começa com contagem |

Antes de começar aparece **LARGADA EM 00:10** (`COUNTDOWN_SECONDS`) com todo mundo
parado a 0 km/h. **Acima de cada carro** fica a placa com a colocação (círculo),
o nome do dono e a velocidade em km/h (`KMH_FACTOR` converte px/frame em km/h,
com teto em `KMH_MAX`).

**Like acelera o carro progressivamente.** O impulso das curtidas é *aditivo* ao
de comentário/presente e cresce com o total de likes da pessoa, até o teto:

| likes acumulados | efeito |
|---|---|
| 1 | +2 km/h |
| 5 | +12 km/h |
| 20 | +48 km/h |
| 60+ | no teto (`LIKE_SPEED_CAP`) |

Ajuste com `LIKE_BOOST_STEP` (quanto cada curtida rende), `LIKE_SPEED_CAP` (teto) e
`LIKE_BOOST_DECAY` (o quanto o impulso decai durante a corrida).

**Dois carros de casa** ficam sempre na pista, mesmo com a live vazia:
**Vitinmilgrau** (G8) e **Narutobebado** (XRE 300). Eles correm sozinhos
(`RIVAL_SPEED`), nunca saem da pista quando ela enche e podem ganhar — é o
adversário para quem chegar. Renomeie em `RIVAL_1_NAME`/`RIVAL_2_NAME` e troque o
veículo em `RIVAL_1_VEHICLE`/`RIVAL_2_VEHICLE`.

**Banner de efeito.** Cada presente e cada like dizem na tela o que causaram:
`ROSA (comum) -> +120 km/h (ponta: 320 km/h)`, `CHUVA DE DINHEIRO -> 2 manchas na
pista`, `fef_ CURTIU (14 likes) -> +24 km/h (ponta: 348 km/h)`, `KAROL DERRAPOU!`.

**Fim de partida**: cartela do vencedor com nome, veículo, km/h, pontos, likes e
contagem para a próxima corrida.

Catálogo em [`config/carros.json`](config/carros.json): Gol, Uno, Chevette, Fusca,
Opala, Kombi, Celta, Palio, Yaris, Corolla, G8 e as motos 160, Biz, PCX, Pop 100,
S1000, XRE 300 — cada um com cor e velocidade própria. Para trocar o catálogo:
`CARROS_CONFIG=/caminho/meus_carros.json` no `.env`.

### 5.2 Duelo de Torres (Lula × Flávio Bolsonaro)

| Evento da live | O que acontece |
|---|---|
| comentário com `lula`, `pt`, `vermelho` | vai (ou volta) para a torre vermelha |
| comentário com `flavio`, `bolsonaro`, `pl`, `azul` | vai para a torre azul |
| comentário sem palabra de lado | entra no lado **mais baixo**, para a disputa ficar pareada |
| presente NITRO / ULTRAPASSAGEM | +2 / +5 blocos (teto de 8 por presente) |
| presente ÓLEO | derruba 2 blocos do **rival** |
| bloco torto demais | escorrega; se a torre inclinar demais, ela **desaba** |
| primeiro a chegar em 32 blocos | vence o duelo; novo duel em ~7 s |

**Personalização**: o confronto inteiro está em [`config/duel.json`](config/duel.json).
Trocar de duelo = editar um arquivo (nomes, partido, cor, palavra-chave, meta de
blocos, valor de cada presente). Não precisa mexer em código. Para apontar para
outro arquivo: `DUEL_CONFIG=/caminho/meu_duelo.json` no `.env`.

```json
{
  "title": "Duelo de Torres",
  "targetBlocks": 32,
  "blockHeight": 12,
  "sides": [
    { "id": "esquerda", "name": "Lula", "party": "PT",
      "color": "#e11d48", "keywords": ["lula", "pt", "esquerda", "vermelho"] },
    { "id": "direita", "name": "Flávio Bolsonaro", "party": "PL",
      "color": "#2563eb", "keywords": ["flavio", "bolsonaro", "pl", "direita", "azul"] }
  ],
  "gifts": { "NITRO": {"blocks": 2}, "TURBO": {"blocks": 5}, "OIL": {"sabotage": 2} }
}
```

As palavras são comparadas sem acento (`flávio` = `flavio`) e funcionam dentro
de frases maiores ("sou do PT com PT"). Quem não escrever o nome do lado entra
no lado mais baixo, para a disputa não nascer desequilibrada.

### 5.3 Pipa Arena

| Evento da live | O que acontece |
|---|---|
| comentário | solta uma pipa nova no céu, com a cor e o nome de quem soltou |
| presente NITRO / ULTRAPASSAGEM / ÓLEO | corta 1 / 2 / 3 linhas de pipas adversárias |
| linhas cortadas | a pipa cai e vira destroço |
| pouca gente no céu | as pipas restantes descem (ninguém segura o vento) |
| muita gente no céu | as pipas sobem: quanto mais pipas, mais altitude |
| juntar a pipa no chão | +10 pontos para quem era dono |
| céu cheio (26 pipas) | rodada limpa e recomeça |

Quem segura mais pipas no alto sofre mais com o presente do rival — é o
incentivo para atacar antes de encher o céu.

### Contra spam

Cada viewer só age a cada `COMMAND_COOLDOWN_MS`, e a live inteira tem teto de
eventos por minuto. Com 200 pessoas digitando, o jogo não trava — só alguém da
fila consegue o comando.

## 6. Presentes: categoria e potência

O efeito do presente vem de **duas camadas**:

1. **nome** → categoria (NITRO / ÓLEO / ULTRAPASSAGEM), comparando sem acento e
   aceitando frase inteira ("Chuva de Dinheiro", "Bola de Espelhos");
2. **valor em moedas** (`gift.diamond_count`, enviado pelo bot) → multiplicador
   de potência, porque nome muda por região e não pode ser a única fonte.

| Faixa (moedas) | Presentes | Multiplicador |
|---|---|---|
| 1 – 19 | Rosa, GG, Casquinha de Sorvete, Panda | ×1 |
| 20 – 199 | Perfume, Eu Te Amo, Confete, Óculos de sol | ×2 |
| 200 – 999 | Chuva de Dinheiro | ×3 |
| 1.000 – 4.999 | Bola de Espelhos (Galáxia), Sereia | ×4 |
| 5.000 – 14.999 | Avião | ×6 |
| 15.000 + | Planeta, Voo Diamante, Leão, Universo TikTok | ×8 |

Nomes (BR) mapeados hoje:

- **NITRO** (empurra o jogador): rosa, gg, casquinha, sorvete, panda, perfume,
  eu te amo, confete, óculos de sol
- **ÓLEO** (ataca o rival): chuva de dinheiro, chuva, dinheiro
- **ULTRAPASSAGEM** (impulso máximo): galáxia, bola de espelhos, sereia, avião,
  planeta, voo diamante, leão, universo tiktok

Aliases em inglês/espanhol continuam funcionando (rose, heart, galaxy, universe,
oil…), porque o nome do presente muda conforme o país do criador.

Presente sem nome conhecido e sem valor → **NITRO ×1** (nunca é jogado fora).
Os valores acima valem para qualquer jogo; o que cada categoria faz está na
seção de cada jogo. Para trocar o nome que dispara a sabotagem, edite
`GIFT_OIL_KEYWORDS` no `.env`.

## 7. Estrutura

```
local_stream_games_prototype/
├── server/
│   ├── server.py        # HTTP (client) + WebSocket, loop de 60 Hz, rate limit
│   ├── base.py          # contrato GameBase (handle_event / update / snapshot)
│   └── games/
│       ├── corrida.py   # Corrida na Live
│       ├── duelo.py     # Duelo de Torres (torres configuráveis)
│       ├── pipa_arena.py# Pipa Arena
│       └── platformer.py# demo com comandos diretos
├── config/
│   ├── duel.json        # personalização do duelo (nomes, cores, palavras, meta)
│   ├── pipa.json        # personalização da arena (teto de pipas, cortes, ...)
│   └── carros.json      # catálogo da corrida (Gol, Uno, motos...)
├── shared/
│   ├── config.py        # leitura do .env
│   ├── commands.py      # comandos de texto (usados pelo platformer)
│   ├── gifts.py         # presente -> efeito (NITRO / OIL / TURBO)
│   ├── sides.py         # lados e palavras do duelo
│   ├── pipas.py         # regras da arena
│   └── carros.py        # catálogo de veículos
├── deploy/
│   ├── install.sh       # instalador Kali (venv + .env + systemd)
│   ├── streamgames-server.service
│   └── streamgames-bot.service
├── client/
│   ├── index.html       # launcher (seletor de jogo)
│   ├── client.js        # WebSocket, HUD, roteia para o renderer do jogo
│   ├── style.css
│   └── renderers/
│       ├── corrida.js   # pista, parallax, câmera no líder
│       ├── duelo.js     # torres, avatares, desabamento, confete
│       ├── pipa_arena.js# céu, pipas, linhas e destroços
│       └── platformer.js
├── tiktok/bot.py        # live -> eventos (thread do TikTok + asyncio do servidor)
├── simulator/simulator.py
├── tests/               # suíte (python3 tests/run_all.py)
├── requirements.txt
└── .env.example
```

### Adicionar um jogo novo

1. Crie `server/games/meu_jogo.py` herdando de `server.base.GameBase`.
2. Implemente `handle_event`, `update`, `snapshot` e `describe`.
3. Registre em `server/games/__init__.py` (`GAMES`).
4. Crie `client/renderers/meu_jogo.js` exportando `create(ctx)`.

Não é preciso mexer no servidor, no bot nem no simulador.

## 8. Protocolo (WebSocket, JSON)

Cliente/simulador/bot → servidor:

```json
{"type": "event", "event": "comment", "user": "nick", "text": "vai!"}
{"type": "event", "event": "gift",    "user": "nick", "gift": "Universo TikTok", "count": 1, "value": 44999}
{"type": "event", "event": "like",    "user": "nick", "count": 5}
{"type": "event", "event": "command", "command": "JUMP"}
{"type": "source_status", "source": "tiktok", "connected": true, "viewers": 142}
```

`value` = moedas do presente (`gift.diamond_count`), que é o que define a
potência (seção 6). O bot já preenche esse campo; o simulador pode mandar 0.

Servidor → clients:

```json
{"type": "welcome", "game": {"type": "corrida", "title": "Corrida na Live", ...}}
{"type": "state", "game": "corrida", "state": {"cars": [...], "oils": [...], "trackLength": 5000}}
{"type": "event", "event": {...}, "notices": [{"message": "nick ENTROU NA PISTA!"}]}
{"type": "game_event", "kind": "winner", "message": "nick VENCEU!"}
{"type": "status", "clients": 1, "sources": {...}}
```

`GET /games` devolve os jogos disponíveis; `GET /health`, `{ok, game, clients, tick}`.

## 9. Colocando na transmissão (OBS)

- Fonte de navegador apontando para `http://localhost:8080`.
- Ou o navegador em tela cheia num segundo monitor.
- `/?game=duelo` fixa o jogo; o seletor no topo troca sem recarregar o servidor.
- Dica: no OBS use 1920×1080 e deixe o canvas escalado — os textos do HUD já
  foram feitos para leitura à distância.

## 10. Implantação

### 10.1 Na máquina que transmite (Kali, tudo local)

O caminho curto é o instalador, que faz venv, `.env`, token e systemd:

```bash
cd local_stream_games_prototype
bash deploy/install.sh seu_usuario_tiktok
```

Isso deixa dois serviços:

| Serviço | Faz |
|---|---|
| `streamgames-server` | HTTP + WebSocket em `:8080` (sempre no ar, reinicia sozinho) |
| `streamgames-bot` | lê a live e envia eventos (reinicia se cair) |

Comandos do dia a dia:

```bash
systemctl status streamgames-server streamgames-bot   # estado
journalctl -u streamgames-bot -f                      # log da live (cada comando aparece)
sudo systemctl restart streamgames-server             # reiniciar o jogo
curl -s localhost:8080/health                         # {ok, game, clients, tick}
```

Depois é só apontar o OBS: **Fonte de navegador** → `http://localhost:8080/`.

### 10.2 Numa VPS (o jogo roda 24 h, sua máquina só transmite)

O bot e o servidor rodam no servidor; o OBS aponta para o IP público.

```bash
# no VPS (Ubuntu/Debian/Kali), dentro do projeto
bash deploy/install.sh seu_usuario_tiktok
sudo ufw allow 8080/tcp          # ou apenas para o seu IP: sudo ufw allow from SEU_IP to any port 8080
curl -s localhost:8080/health    # conferindo
```

No OBS: `http://SEU_IP:8080/?game=corrida`.

Notas de VPS:

- **Defina `GAME_TOKEN` com certeza.** Sem ele, qualquer pessoa que abrir a URL
  injeta comentários e presentes falsos no seu placar. O `install.sh` já gera um.
  Para trocar: edite `.env` e reinicie os dois serviços.
- O token só é exigido para **enviar** eventos. Quem assiste (OBS, chat da sua
  audiência abrindo o link) não precisa dele.
- O estado fica na memória do processo: reiniciar zera a partida em andamento
  (os carros/torres/pipas voltam ao zero).
- Delay da VPS até o OBS: como o estado chega 30x/s, alguns ms de latência não
  muda nada; o problema seria só jitter de rede.

### 10.3 HTTPS / domínio (opcional)

Some engines de live não carregam `http://` em fonte de navegador, e o
`wss://` evita aviso de conteúdo misto. O caminho curto é um túnel ou um proxy
com TLS:

```bash
# opcao A: caddy (renova certificado sozinho)
sudo apt install -y caddy
# /etc/caddy/Caddyfile
# seu-dominio.com {
#     reverse_proxy 127.0.0.1:8080
# }

# opcao B: cloudflared (sem abrir porta no firewall)
cloudflared tunnel --url http://localhost:8080
```

Nos dois casos, o OBS usa `https://seu-dominio.com/`. O WebSocket passa a
`wss://` automaticamente porque o mesmo host serve as duas coisas.

### 10.4 O que o servidor **não** faz (e você vai querer)

- **Não manda nada pro TikTok.** Ele só lê. Para o bot postar na live, a lib
  exige cookies da sua conta e uma API key paga — dá pra adicionar, mas é um
  risco de banimento da sua própria conta.
- **Não guarda ranking entre lives.** O placar morre quando o processo reinicia.
- **Não é multi-sessão.** Uma partida por servidor; para dois jogos ao mesmo
  tempo, rode duas instâncias em portas diferentes.

## 11. Problemas comuns

| Sintoma | Causa provável |
|---|---|
| `externally-managed-environment` | esqueceu do venv: `source .venv/bin/activate` |
| `Address already in use` | já tem servidor na 8080: mude `PORT` no `.env` |
| bot avisa `nao esta ao vivo` | o criador ainda não abriu a live; tenta de novo a cada 30 s |
| erro de assinatura do TikTok | falta `EULER_API_KEY` (ou o limite free estourou) |
| eventos da live não chegam (em VPS) | faltou `GAME_TOKEN` no `.env` do bot/servidor (veja 10.2) |
| os presentes não viram efeito | nome do presente fora das keywords: `python3 tiktok/bot.py --list` |
| nobody entra na pista | o bot está conectado mas o cooldown está altíssimo, ou o `user` está vazio |

## 12. Limites conhecidos

- A leitura do chat do TikTok é **não-oficial** (reverse engineering): o TikTok pode
  mudar o protocolo e quebrar a biblioteca sem aviso.
- Chave gratuita da Euler Stream tem limite de requisições; live grande pede o plano pago.
- Estado único em memória: uma sessão, sem ranking entre lives nem persistência.
- Sem regra de anti-cheat: o cooldown é por viewer conhecido, não por conta.
