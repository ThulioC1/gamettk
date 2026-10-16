/* Renderer da Corrida na Live.
 *
 * Formato de referencia (modelos/2.jpeg):
 *   - contagem regressiva "LARGADA EM 00:10" com todo mundo parado a 0 km/h;
 *   - grid de largada com carros empilhados em faixas;
 *   - placa em cada carro: numero, nome do viewer e velocidade em km/h;
 *   - paineis a esquerda com o catalogo (carros e motos);
 *   - banner central com o que acabou de acontecer ("CURTIU A LIVE", "+15 curtidas").
 *
 * O estado vem do servidor (server/games/corrida.py); aqui so existe desenho.
 */
const WIDTH = 960;
const HEIGHT = 540;
const ROAD_TOP = 210;
const LANE_H = 66;          // altura de uma faixa (faixas empilhadas)
const PPM = 0.16;           // px de tela por px de pista
const CATALOG_W = 168;      // painel de catalogo a esquerda

const scope = { banner: null, pops: [], players: [] };

export function create() {
  const cache = { buildings: [], clouds: [] };

  return {
    width: WIDTH,
    height: HEIGHT,
    keyboard: false,
    controls: "",

    hud(state, meta) {
      if (!state) return { score: "", meta: "" };
      const leader = state.cars[0];
      const faltam = leader ? Math.max(0, Math.round(state.trackLength - leader.dist)) : 0;
      const fase = state.phase === "countdown"
        ? `larga em ${state.countdown}s`
        : state.phase === "over"
          ? "corrida encerrada"
          : `faltam ${faltam} px`;
      return {
        score: `CARROS <b>${state.cars.length}</b>`,
        meta: leader ? `lider: <b>${escapeHtml(leader.name)}</b> · ${fase}` : `aguardando a live… · ${fase}`,
      };
    },

    onEvent(event, notices) {
      for (const notice of notices) {
        if (notice.message) pushBanner(notice.message, notice);
      }
    },

    onGameEvent(payload) {
      if (payload.kind === "go") {
        pushBanner("VALENDO!", { color: "#fbbf24" });
      } else if (payload.kind === "winner") {
        pushBanner(payload.message, { color: "#22d3ee", confete: true });
      } else if (payload.kind === "restart") {
        pushBanner(payload.message, { color: "#e2e8f0" });
      } else if (payload.kind === "spill") {
        pushBanner(payload.message, { color: "#f87171" });
      }
    },

    draw(context, state, meta, view) {
      drawCidade(context, view.time, cache);

      if (!state) {
        drawWaiting(context);
        return;
      }

      const lanes = state.lanes || 5;
      const camera = cameraOf(state);
      const toScreen = (dist) => dist * PPM - camera;

      drawPista(context, camera, lanes, toScreen, state.trackLength);
      drawCatalogo(context, meta, state);

      if (state.phase === "countdown") {
        drawCountdown(context, state.countdown);
      }

      for (const oil of state.oils) {
        drawOil(context, toScreen(oil.dist), laneY(2, lanes));
      }

      // desenha de tras para frente: a faixa de baixo cobre a de cima
      for (const car of state.cars.slice().sort((a, b) => b.lane - a.lane)) {
        drawCar(context, car, toScreen(car.dist), laneY(car.lane, lanes), view.time);
      }

      drawPlacar(context, state);
      drawBanner(context, view.delta);
    },
  };
}

function laneY(lane, lanes) {
  return ROAD_TOP + 40 + lane * LANE_H;
}

function cameraOf(state) {
  const leader = state.cars.reduce((best, car) => (car.dist > (best ? best.dist : -Infinity) ? car : best), null);
  // Segue o lider desde o primeiro frame; sem o clamp os carros da largada
  // (dist negativa) ficam fora da tela e a pista parece vazia.
  return leader ? leader.dist * PPM - WIDTH * 0.35 : 0;
}

// ------------------------------------------------------------------ cenarios
function drawCidade(context, time, cache) {
  const sky = context.createLinearGradient(0, 0, 0, HEIGHT);
  sky.addColorStop(0, "#1b3b6f");
  sky.addColorStop(0.35, "#2f6ea8");
  sky.addColorStop(0.62, "#7db6dd");
  sky.addColorStop(1, "#cfe6f5");
  context.fillStyle = sky;
  context.fillRect(0, 0, WIDTH, HEIGHT);

  context.fillStyle = "rgba(253, 224, 71, .9)";
  context.beginPath();
  context.arc(830, 78, 34, 0, Math.PI * 2);
  context.fill();

  if (!cache.buildings.length) {
    cache.buildings = Array.from({ length: 16 }, (_, i) => ({
      x: i * 70,
      w: 44 + ((i * 13) % 26),
      h: 50 + ((i * 31) % 70),
      cor: ["#274b7a", "#31578c", "#3d6399", "#8a5a44"][i % 4],
    }));
  }
  cache.buildings.forEach((b, i) => {
    context.fillStyle = b.cor;
    context.fillRect(b.x - (time * 6) % 1120, HEIGHT * 0.42 - b.h, b.w, b.h + 40);
    context.fillStyle = "rgba(253, 224, 71, .35)";
    for (let j = 0; j < 3; j += 1) {
      context.fillRect(b.x - (time * 6) % 1120 + 8, HEIGHT * 0.42 - b.h + 12 + j * 16, 9, 9);
    }
  });

  if (!cache.clouds.length) {
    cache.clouds = Array.from({ length: 5 }, (_, i) => ({ x: i * 230, y: 40 + i * 26, s: 0.7 + (i % 3) * 0.3 }));
  }
  cache.clouds.forEach((cloud) => {
    const x = ((cloud.x + time * 5) % (WIDTH + 240)) - 120;
    drawCloud(context, x, cloud.y, cloud.s);
  });
}

function drawCloud(context, x, y, scale) {
  context.save();
  context.translate(x, y);
  context.scale(scale, scale);
  context.fillStyle = "rgba(255, 255, 255, .75)";
  [[0, 0, 24], [22, 6, 17], [-20, 7, 15]].forEach(([cx, cy, r]) => {
    context.beginPath();
    context.arc(cx, cy, r, 0, Math.PI * 2);
    context.fill();
  });
  context.restore();
}

function drawPista(context, camera, lanes, toScreen, trackLength) {
  const bottom = laneY(lanes - 1, lanes) + 46;
  context.fillStyle = "#2b2f36";
  context.fillRect(0, ROAD_TOP, WIDTH, bottom - ROAD_TOP);

  // faixas (o asfalto de cada faixa e um pouco mais claro)
  for (let lane = 0; lane < lanes; lane += 1) {
    const y = laneY(lane, lanes);
    context.fillStyle = lane % 2 === 0 ? "#343941" : "#2f343b";
    context.fillRect(0, y - 26, WIDTH, 52);
  }

  // linhas brancas da pista, com movimento
  const spacing = 150;
  const offset = -(camera * PPM * 0.6) % spacing;
  context.fillStyle = "rgba(241, 245, 249, .5)";
  for (let lane = 0; lane <= lanes; lane += 1) {
    const y = laneY(lane, lanes) - 26;
    for (let x = offset - spacing; x < WIDTH + spacing; x += spacing) {
      context.fillRect(x + 20, y, 70, 4);
    }
  }

  // faixa amarela do meio
  context.fillStyle = "rgba(250, 204, 21, .85)";
  context.fillRect(0, ROAD_TOP - 4, WIDTH, 4);

  drawLargada(context, toScreen(0));
  drawChegada(context, toScreen(trackLength));
}

function drawLargada(context, x) {
  if (x < -40 || x > WIDTH + 40) return;
  context.save();
  for (let row = 0; row < 12; row += 1) {
    for (let col = 0; col < 2; col += 1) {
      context.fillStyle = (row + col) % 2 === 0 ? "#0f172a" : "#f8fafc";
      context.fillRect(x + col * 8, ROAD_TOP + row * 26, 8, 26);
    }
  }
  context.restore();
}

function drawChegada(context, x) {
  if (x < -80 || x > WIDTH + 80) return;
  const height = laneY(4, 5) - ROAD_TOP + 46;
  const squares = 14;
  for (let row = 0; row < 10; row += 1) {
    for (let col = 0; col < squares; col += 1) {
      context.fillStyle = (row + col) % 2 === 0 ? "#0f172a" : "#f8fafc";
      context.fillRect(x - 56 + col * 8, ROAD_TOP + row * (height / 10), 8, height / 10);
    }
  }
  context.fillStyle = "#facc15";
  context.font = "800 15px system-ui, sans-serif";
  context.textAlign = "center";
  context.fillText("CHEGADA", x - 28, ROAD_TOP - 10);
}

// ------------------------------------------------------------------ catalogo
function drawCatalogo(context, meta, state) {
  const catalog = (meta && meta.catalog) || { cars: [], motos: [] };
  const panels = [
    { title: "CARROS DISPONÍVEIS", itens: catalog.cars },
    { title: "MOTOS", itens: catalog.motos },
  ];

  let y = 84;
  panels.forEach((panel) => {
    if (!panel.itens.length) return;
    const altura = 26 + panel.itens.length * 22;
    context.fillStyle = "rgba(4, 12, 22, .78)";
    context.beginPath();
    context.roundRect(14, y, CATALOG_W, altura, 10);
    context.fill();

    context.fillStyle = "#facc15";
    context.font = "800 13px system-ui, sans-serif";
    context.textAlign = "left";
    context.fillText(panel.title, 26, y + 20);

    panel.itens.forEach((item, i) => {
      const linha = y + 40 + i * 22;
      const emPista = state.cars.some((car) => car.vehicle === item.id);
      context.fillStyle = item.color;
      context.beginPath();
      context.roundRect(26, linha - 8, 14, 10, 3);
      context.fill();
      context.fillStyle = emPista ? "#e2e8f0" : "#94a3b8";
      context.font = `${emPista ? 700 : 500} 13px system-ui, sans-serif`;
      context.fillText(item.name, 48, linha);
    });

    y += altura + 12;
  });
}

function drawCountdown(context, segundos) {
  const texto = `LARGADA EM 00:${String(Math.max(0, Math.ceil(segundos))).padStart(2, "0")}`;
  context.fillStyle = "rgba(4, 12, 22, .72)";
  context.beginPath();
  context.roundRect(WIDTH / 2 - 210, 118, 420, 56, 12);
  context.fill();
  context.strokeStyle = "rgba(250, 204, 21, .5)";
  context.lineWidth = 2;
  context.stroke();

  context.fillStyle = "#facc15";
  context.font = "900 34px system-ui, sans-serif";
  context.textAlign = "center";
  context.fillText(texto, WIDTH / 2, 158);
}

// ------------------------------------------------------------------ carro
function drawCar(context, car, x, y, time) {
  if (x < -180 || x > WIDTH + 180) return;

  const bodyW = car.isMoto ? 54 : 84;
  const bodyH = car.isMoto ? 22 : 34;
  const spinner = car.spinning;
  const tilt = spinner ? Math.sin(time * 18) * 0.22 : 0;

  context.save();
  context.translate(x, y + (spinner ? Math.sin(time * 24) * 3 : 0));
  context.rotate(tilt);

  // sombra
  context.fillStyle = "rgba(0, 0, 0, .38)";
  context.beginPath();
  context.ellipse(0, bodyH / 2 + 5, bodyW / 2, 6, 0, 0, Math.PI * 2);
  context.fill();

  if (car.isMoto) {
    // moto: rider + roda
    context.fillStyle = "#0b1220";
    context.beginPath();
    context.arc(20, bodyH / 2 - 4, 11, 0, Math.PI * 2);
    context.fill();
    context.beginPath();
    context.arc(-20, bodyH / 2 - 4, 11, 0, Math.PI * 2);
    context.fill();
    context.fillStyle = car.color;
    context.beginPath();
    context.roundRect(-26, -bodyH / 2, 52, bodyH - 4, 7);
    context.fill();
    context.fillStyle = "#111827";
    context.beginPath();
    context.arc(-4, -bodyH / 2 - 6, 8, 0, Math.PI * 2);
    context.fill();
    context.fillStyle = car.dark;
    context.beginPath();
    context.roundRect(-14, -bodyH / 2 - 2, 16, 14, 5);
    context.fill();
  } else {
    // carro
    context.fillStyle = "#0b1220";
    [24, -20].forEach((offset) => {
      context.beginPath();
      context.arc(offset, bodyH / 2 - 4, 11, 0, Math.PI * 2);
      context.fill();
      context.fillStyle = "#64748b";
      context.beginPath();
      context.arc(offset, bodyH / 2 - 4, 4, 0, Math.PI * 2);
      context.fill();
      context.fillStyle = "#0b1220";
    });

    context.fillStyle = car.color;
    context.beginPath();
    context.roundRect(-bodyW / 2, -bodyH / 2, bodyW, bodyH, 9);
    context.fill();
    context.fillStyle = "rgba(255, 255, 255, .22)";
    context.beginPath();
    context.roundRect(-bodyW / 2, -bodyH / 2, bodyW, 7, 5);
    context.fill();
    context.fillStyle = "rgba(15, 23, 42, .85)";
    context.beginPath();
    context.roundRect(-10, -bodyH / 2 - 10, 34, 15, 6);
    context.fill();
  }

  if (car.boost > 0) {
    context.fillStyle = "rgba(251, 191, 36, .9)";
    context.beginPath();
    context.moveTo(bodyW / 2 - 6, -5);
    context.lineTo(bodyW / 2 + 24 + Math.sin(time * 30) * 6, 0);
    context.lineTo(bodyW / 2 - 6, 5);
    context.closePath();
    context.fill();
  }

  drawPlaca(context, car, time);
  context.restore();
}

/* Placa do piloto: numero + nome + km/h (o que a referencia mostra em cada carro). */
function drawPlaca(context, car, time) {
  const nome = truncate(car.name, 12);
  const kmh = `${car.kmh} km/h`;

  context.font = "700 13px system-ui, sans-serif";
  const largura = Math.max(96, context.measureText(nome).width + 78);
  const altura = 30;
  const x0 = -largura / 2;
  const y0 = -34;

  context.fillStyle = "rgba(4, 12, 22, .82)";
  context.beginPath();
  context.roundRect(x0, y0, largura, altura, 7);
  context.fill();

  // barrinha com a cor do veiculo
  context.fillStyle = car.color;
  context.fillRect(x0 + 4, y0 + 6, 4, altura - 12);

  // numero da colocacao
  context.fillStyle = "#1f9d55";
  context.beginPath();
  context.arc(x0 + 20, y0 + altura / 2, 12, 0, Math.PI * 2);
  context.fill();
  context.fillStyle = "#ffffff";
  context.font = "800 13px system-ui, sans-serif";
  context.textAlign = "center";
  context.textBaseline = "middle";
  context.fillText(String(car.place || car.number), x0 + 20, y0 + altura / 2 + 1);

  context.fillStyle = "#e2e8f0";
  context.textAlign = "left";
  context.font = "700 13px system-ui, sans-serif";
  context.fillText(nome, x0 + 38, y0 + 11);

  context.fillStyle = car.kmh > 0 ? "#facc15" : "#64748b";
  context.font = "700 12px system-ui, sans-serif";
  context.fillText(kmh, x0 + 38, y0 + 24);

  context.textBaseline = "alphabetic";
}

function drawPlacar(context, state) {
  const top = state.cars.slice(0, 5);
  if (!top.length) return;
  const x = WIDTH - CATALOG_W - 8;

  context.fillStyle = "rgba(4, 12, 22, .78)";
  context.beginPath();
  context.roundRect(x, 84, CATALOG_W, 26 + top.length * 22, 10);
  context.fill();

  context.fillStyle = "#facc15";
  context.font = "800 13px system-ui, sans-serif";
  context.textAlign = "left";
  context.fillText("LIDERANÇA", x + 12, 104);

  top.forEach((car, i) => {
    const y = 124 + i * 22;
    context.fillStyle = car.color;
    context.beginPath();
    context.roundRect(x + 12, y - 8, 14, 10, 3);
    context.fill();
    context.fillStyle = "#e2e8f0";
    context.font = "600 13px system-ui, sans-serif";
    context.fillText(`${i + 1}. ${truncate(car.name, 11)}`, x + 32, y);
    context.textAlign = "right";
    context.fillStyle = "#facc15";
    context.fillText(`${car.kmh}`, x + CATALOG_W - 12, y);
    context.textAlign = "left";
  });
}

// ------------------------------------------------------------------ banner
function pushBanner(text, opts = {}) {
  scope.banner = { text, color: opts.color || "#e2e8f0", life: 1, confete: opts.confete };
  scope.pops = scope.pops.slice(-4);
}

function drawBanner(context, delta) {
  if (!scope.banner) return;
  scope.banner.life -= 0.008;
  if (scope.banner.life <= 0) {
    scope.banner = null;
    return;
  }

  context.fillStyle = "rgba(4, 12, 22, .82)";
  context.beginPath();
  context.roundRect(WIDTH / 2 - 230, ROAD_TOP - 6, 460, 44, 10);
  context.fill();
  context.fillStyle = scope.banner.color;
  context.font = "800 20px system-ui, sans-serif";
  context.textAlign = "center";
  context.fillText(scope.banner.text, WIDTH / 2, ROAD_TOP + 23);
}

function drawOil(context, x, y) {
  if (x < -60 || x > WIDTH + 60) return;
  context.save();
  context.globalAlpha = 0.85;
  context.fillStyle = "#0b1220";
  context.beginPath();
  context.ellipse(x, y + 12, 34, 11, 0, 0, Math.PI * 2);
  context.fill();
  context.fillStyle = "rgba(56, 189, 248, .3)";
  context.beginPath();
  context.ellipse(x - 6, y + 9, 12, 4, 0, 0, Math.PI * 2);
  context.fill();
  context.restore();
}

function drawWaiting(context) {
  context.fillStyle = "rgba(4, 12, 22, .6)";
  context.fillRect(0, 0, WIDTH, HEIGHT);
  context.textAlign = "center";
  context.fillStyle = "#e2e8f0";
  context.font = "700 22px system-ui, sans-serif";
  context.fillText("aguardando alguém comentar na live…", WIDTH / 2, 300);
  context.fillStyle = "#94a3b8";
  context.font = "500 15px system-ui, sans-serif";
  context.fillText("o primeiro comentário escolhe o carro e entra no grid", WIDTH / 2, 328);
}

function truncate(text, size) {
  return text.length > size ? `${text.slice(0, size - 1)}…` : text;
}

function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[char]);
}