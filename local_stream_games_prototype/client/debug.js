/* Pagina de debug: mostra os eventos crus que chegam da live.
 *
 * Serve para responder "o bot esta funcionando?" sem ficar caçando log:
 * se aparecer evento aqui, o problema e no jogo; se nao aparecer, e no bot.
 */
(() => {
  "use strict";

  const el = {
    resumo: document.getElementById("resumo"),
    connection: document.getElementById("connection"),
    fontes: document.getElementById("fontes"),
    presentes: document.getElementById("presentes"),
    eventos: document.getElementById("eventos"),
    limpar: document.getElementById("limpar"),
  };

  const contadores = { comentario: 0, presente: 0, like: 0, follow: 0, share: 0 };
  const nomesPresente = new Map();
  const MAX = 120;

  let socket = null;
  let espera = 500;

  function conectar() {
    const protocolo = location.protocol === "https:" ? "wss" : "ws";
    socket = new WebSocket(`${protocolo}://${location.host}/`);

    socket.addEventListener("open", () => {
      espera = 500;
      el.connection.textContent = "conectado";
      el.connection.className = "status online";
      atualizaResumo();
    });

    socket.addEventListener("close", () => {
      el.connection.textContent = "desconectado - reconectando…";
      el.connection.className = "status offline";
      setTimeout(conectar, espera);
      espera = Math.min(espera * 1.8, 8000);
    });

    socket.addEventListener("message", (event) => {
      let payload;
      try {
        payload = JSON.parse(event.data);
      } catch (err) {
        return;
      }
      trata(payload);
    });
  }

  function trata(payload) {
    if (payload.type === "status") {
      for (const [nome, info] of Object.entries(payload.sources || {})) {
        el.fontes.innerHTML += "";
      }
      desenhaFontes(payload.sources || {});
      return;
    }
    if (payload.type === "event") {
      conta(payload.event);
      linha(
        payload.event.event,
        `${payload.event.user}${payload.event.text ? `: ${payload.event.text}` : ""}` +
        `${payload.event.gift ? ` [${payload.event.gift}]` : ""}`,
        payload.event.source,
      );
      return;
    }
    if (payload.type === "game_event") {
      linha("jogo", payload.message || payload.kind, "server");
    }
  }

  function conta(evento) {
    const chave = { comment: "comentario", gift: "presente", like: "like", follow: "follow", share: "share" }[evento.event];
    if (!chave) return;
    contadores[chave] = (contadores[chave] || 0) + 1;
    if (evento.event === "gift" && evento.gift) {
      nomesPresente.set(evento.gift, (nomesPresente.get(evento.gift) || 0) + 1);
      desenhaPresentes();
    }
    atualizaResumo();
  }

  function atualizaResumo() {
    el.resumo.textContent =
      `${contadores.comentario} comentário(s) · ${contadores.presente} presente(s) · ` +
      `${contadores.like} like(s) · ${contadores.follow} follow(s) · ${contadores.share} share(s)`;
  }

  function desenhaFontes(sources) {
    el.fontes.innerHTML = Object.entries(sources)
      .map(([nome, info]) => {
        const on = info.connected;
        return `<div class="fonte ${on ? "on" : "off"}">
            <b>${nome}</b>
            <span>${on ? `conectado${info.username ? ` como @${info.username}` : ""}` : info.note || "desconectado"}</span>
            ${info.viewers ? `<span>${info.viewers} viewers</span>` : ""}
          </div>`;
      })
      .join("");
  }

  function desenhaPresentes() {
    if (!nomesPresente.size) return;
    const itens = [...nomesPresente.entries()].sort((a, b) => b[1] - a[1]);
    el.presentes.innerHTML = itens
      .map(([nome, total]) => `<code>${escapeHtml(nome)} <b>x${total}</b></code>`)
      .join("");
  }

  function linha(tipo, texto, origem) {
    const div = document.createElement("div");
    div.className = `ev ev-${tipo}`;
    div.innerHTML = `<b>${tipo}</b><span>${escapeHtml(texto || "")}</span><i>${escapeHtml(origem || "")}</i>`;
    el.eventos.prepend(div);
    while (el.eventos.childElementCount > MAX) el.eventos.lastElementChild.remove();
  }

  function escapeHtml(text) {
    return String(text).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  el.limpar.addEventListener("click", () => {
    el.eventos.innerHTML = "";
    el.presentes.textContent = "nenhum ainda";
    nomesPresente.clear();
    for (const chave of Object.keys(contadores)) contadores[chave] = 0;
    atualizaResumo();
  });

  conectar();
})();