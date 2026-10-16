# Este repositório é o Stream Games Interativos (protótipo local).

Leia **antes de mexer em qualquer coisa**:

- [`AGENTS.md`](AGENTS.md) — contrato para IAs: arquitetura, regras que não se
  negociam, armadilhas já mordidas e como testar.
- [`CHANGELOG.md`](CHANGELOG.md) — histórico append-only. Toda alteração tem uma
  entrada nova no topo.
- [`local_stream_games_prototype/README.md`](local_stream_games_prototype/README.md)
  — documentação para humanos: como rodar, regras de cada jogo, deploy.

## Mapa rápido

```
local_stream_games_prototype/   # o projeto
  server/     núcleo agnóstico ao jogo + módulos em server/games/
  client/     launcher no navegador + renderers por jogo
  tiktok/     bot que lê a live e vira evento
  simulator/  live fictícia para testar sem TikTok
  shared/     config, palavras de comando, presentes, lados da arena
  config/     JSON de personalização (duelo, pipa)
  deploy/     instalador systemd para Kali
  tests/      suíte (python3 tests/run_all.py)
  AGENTS.md   contrato de leitura + regras (este diretório)
  CHANGELOG.md
```

## Comandos

```bash
cd local_stream_games_prototype
python3 tests/run_all.py                     # suíte (~50 s)
python3 server/server.py --game duelo        # http://localhost:8080
python3 simulator/simulator.py --auto        # live fictícia
bash deploy/install.sh seu_usuario           # systemd (Kali)
```

Ambiente de produção é **Kali Linux**; o desenvolvimento acontece em Windows.
Código precisa rodar nos dois: sem caminho com `\`, sem dependência de SO.