/* Cliente do launcher: roteia o estado para o renderer do jogo ativo.
 *
 * O navegador nao decide nada: desenha o snapshot mais recente e envia eventos
 * (comando de teclado, botao) para o servidor. Se a conexao cair, o canvas
 * congela com aviso em vez de inventar movimento.
 */
(() => {
  "use strict";

  const RENDERERS = {
    corrida: () => import("./renderers/corrida.js"),
    duelo: () => import("./renderers/duelo.js"),
    pipa: () => import("./renderers/pipa_arena.js"),
    platformer: () => import("./renderers/platformer.js"),
  };

  const canvas = document.getElementById("game");
  const ctx = canvas.getContext("2d");

  const el = {
    connection: document.getElementById("connection"),
    title: document.getElementById("gameTitle"),
    cta: document.getElementById("callToAction"),
    score: document.getElementById("score"),
    meta: document.getElementById("gameMeta"),
    lastEvent: document.getElementById("lastEvent"),
    tiktokStatus: document.getElementById("tiktokStatus"),
    viewers: document.getElementById("viewers"),
    feed: document.getElementById("feed"),
    gameSelect: document.getElementById("gameSelect"),
    controls: document.getElementById("controls"),
    hud: document.getElementById("hud"),
  };

  // ------------------------------------------------------------------ estado
  const params = new URLSearchParams(location.search);
  let socket = null;
  let connected = false;
  let reconnectDelay = 500;

  let gameType = params.get("game") || "corrida";
  let meta = null;
  let state = null;
  let renderer = null;   // { draw(ctx, state, meta, view), onEvent?(notice), controls }
  let feedItems = [];

  const dpr = Math.min(window.devicePixelRatio || 1, 2);

  function fitCanvas(width, height) {
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.aspectRatio = `${width} / ${height}`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  fitCanvas(960, 540);

  // ------------------------------------------------------------- envio de evento
  function sendEvent(payload) {
    if (!socket || socket.readyState !== WebSocket.OPEN) return false;
    socket.send(JSON.stringify({ type: "event", source: "keyboard", user: "local", ...payload }));
    return true;
  }

  function sendCommand(command) {
    return sendEvent({ event: "command", command });
  }

  // -------------------------------------------------------------- websocket
  function connect() {
    const protocol = location.protocol === "https:" ? "wss" : "ws";
    socket = new WebSocket(`${protocol}://${location.host}`);

    socket.addEventListener("open", () => {
      connected = true;
      reconnectDelay = 500;
      setConnection("conectado ao servidor", "online");
    });

    socket.addEventListener("close", () => {
      connected = false;
      setConnection("desconectado - tentando reconectar…", "offline");
      setTimeout(connect, reconnectDelay);
      reconnectDelay = Math.min(reconnectDelay * 1.7, 8000);
    });

    socket.addEventListener("error", () => socket.close());

    socket.addEventListener("message", (event) => {
      let payload;
      try {
        payload = JSON.parse(event.data);
      } catch (err) {
        return;
      }
      handle(payload);
    });
  }

  async function handle(payload) {
    switch (payload.type) {
      case "welcome":
        meta = payload.game;
        await loadRenderer(meta.type);
        break;

      case "state":
        state = payload.state;
        updateHud();
        break;

      case "event":
        onEvent(payload.event, payload.notices || []);
        break;

      case "game_event":
        onGameEvent(payload);
        break;

      case "status":
        el.viewers.textContent = `${payload.clients} tela(s)`;
        renderTiktokStatus(payload.sources && payload.sources.tiktok);
        break;

      default:
        break;
    }
  }

  async function loadRenderer(type) {
    const loader = RENDERERS[type] || RENDERERS.corrida;
    const module = await loader();
    renderer = module.create(ctx, { canvas, els: el });
    gameType = type;

    el.title.textContent = meta.title;
    el.cta.textContent = meta.callToAction || "";
    el.controls.innerHTML = renderer.controls || "";
    el.controls.querySelectorAll("[data-command]").forEach((button) => {
      button.addEventListener("click", () => sendCommand(button.dataset.command));
    });
    fitCanvas(renderer.width || 960, renderer.height || 540);
  }

  // ---------------------------------------------------------------- hud
  function setConnection(text, className) {
    el.connection.textContent = text;
    el.connection.className = `status ${className}`;
  }

  function renderTiktokStatus(tiktok) {
    if (!tiktok || !tiktok.connected) {
      el.tiktokStatus.textContent = "TikTok: desconectado";
      el.tiktokStatus.classList.remove("live");
      return;
    }
    const viewers = tiktok.viewers ? ` · ${tiktok.viewers} viewers` : "";
    el.tiktokStatus.textContent = `TikTok: @${tiktok.username || "?"} ao vivo${viewers}`;
    el.tiktokStatus.classList.add("live");
  }

  function updateHud() {
    if (renderer && renderer.hud) {
      const hud = renderer.hud(state, meta);
      el.score.innerHTML = hud.score || "";
      el.meta.innerHTML = hud.meta || "";
    }
  }

  const LABELS = {
    comment: "COMENTOU",
    gift: "PRESENTE",
    like: "LIKES",
    follow: "SEGUIU",
    command: "COMANDO",
    share: "COMPARTILHOU",
  };

  function onEvent(event, notices) {
    if (event.source === "keyboard") return;

    const label = LABELS[event.event] || event.event;
    let detail = event.text || "";
    if (event.event === "gift") detail = `${event.gift || "presente"}${event.count > 1 ? ` x${event.count}` : ""}`;

    el.lastEvent.textContent = `${event.user} · ${label}${detail ? ` · ${detail}` : ""}`;
    pushFeed(event.user, label, detail);

    const effect = notices.find((notice) => notice.message);
    if (effect) pushFeed(event.user, "efeito", effect.message);

    if (renderer && renderer.onEvent) renderer.onEvent(event, notices);
  }

  function onGameEvent(payload) {
    if (payload.message) el.lastEvent.textContent = payload.message;
    if (renderer && renderer.onGameEvent) renderer.onGameEvent(payload);
  }

  function pushFeed(user, label, detail) {
    const item = document.createElement("div");
    item.className = "feed-item";
    item.innerHTML = `<span class="who">${escapeHtml(user)}</span> <span class="what">${escapeHtml(label)}</span>${
      detail ? ` <span class="detail">${escapeHtml(detail)}</span>` : ""
    }`;
    el.feed.prepend(item);
    while (el.feed.childElementCount > 8) el.feed.lastElementChild.remove();
    setTimeout(() => item.classList.add("fading"), 6000);
    setTimeout(() => item.remove(), 6500);
  }

  function escapeHtml(text) {
    return String(text).replace(/[&<>"']/g, (char) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[char]);
  }

  // ------------------------------------------------------------ controles
  const KEY_COMMANDS = {
    ArrowLeft: "MOVE_LEFT", a: "MOVE_LEFT", A: "MOVE_LEFT",
    ArrowRight: "MOVE_RIGHT", d: "MOVE_RIGHT", D: "MOVE_RIGHT",
    ArrowUp: "JUMP", w: "JUMP", W: "JUMP", " ": "JUMP",
    ArrowDown: "STOP", s: "STOP", S: "STOP",
    r: "RESET", R: "RESET",
  };

  window.addEventListener("keydown", (event) => {
    const command = KEY_COMMANDS[event.key];
    if (!command || !renderer || !renderer.keyboard) return;
    event.preventDefault();
    sendCommand(command);
  });

  el.gameSelect.addEventListener("change", () => {
    const url = new URL(location.href);
    url.searchParams.set("game", el.gameSelect.value);
    location.href = url.toString();
  });

  // ---------------------------------------------------------------- render
  let lastTime = performance.now();

  function loop(now) {
    const delta = Math.min((now - lastTime) / 16.67, 4); // frames de 60 Hz
    lastTime = now;
    const time = now / 1000;

    if (renderer && renderer.draw) {
      renderer.draw(ctx, state, meta, { time, delta });
    }
    if (!connected) drawOffline();

    requestAnimationFrame(loop);
  }

  function drawOffline() {
    const width = canvas.width / dpr;
    const height = canvas.height / dpr;
    ctx.fillStyle = "rgba(4, 10, 20, .6)";
    ctx.fillRect(0, 0, width, height);
    ctx.fillStyle = "#f87171";
    ctx.font = "700 22px system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("SEM CONEXÃO COM O SERVIDOR", width / 2, height / 2);
  }

  // ------------------------------------------------------------------ start
  fetch("/games")
    .then((response) => response.json())
    .then((data) => {
      el.gameSelect.innerHTML = (data.games || [])
        .map((game) => `<option value="${game.type}">${game.title}</option>`)
        .join("");
      if (!params.get("game") && data.default) el.gameSelect.value = data.default;
    })
    .catch(() => { /* servidor pode estar subindo; o select fica vazio */ });

  requestAnimationFrame(loop);
  connect();
})();
