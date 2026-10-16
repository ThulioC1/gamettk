/* Renderer da Corrida na Live: pista de lado, camera segue o lider.
 *
 * O estado vem do servidor (server/games/corrida.py): cada carro tem distancia
 * em px na pista. Aqui so existe perspectiva, parallax e desenho.
 */

const WIDTH = 960;
const HEIGHT = 540;
const ROAD_Y = 430;       // topo da pista
const ROAD_H = 110;
const PPM = 0.16;         // px da tela por px de pista (zoom da camera)

const scope = { pops: [], banner: null };

export function create(ctx) {
  const cache = { clouds: [] };

  return {
    width: WIDTH,
    height: HEIGHT,
    keyboard: false,
    controls: "",

    hud(state) {
      if (!state) return { score: "", meta: "" };
      const leader = state.cars[0];
      const leaderText = leader
        ? `lider: <b>${escapeHtml(leader.name)}</b>`
        : "aguardando a live comentar…";
      return {
        score: `CARROS <b>${state.cars.length}</b>`,
        meta: `${leaderText} · faltam ${Math.max(0, Math.round(state.trackLength - (leader ? leader.dist : 0)))} px`,
      };
    },

    onEvent(event, notices) {
      const notice = notices.find((item) => item.message);
      if (!notice) return;
      scope.pops.push({ text: notice.message, life: 1, color: "#fbbf24" });
    },

    onGameEvent(payload) {
      if (payload.kind === "winner") {
        scope.banner = { text: payload.message, sub: "nova corrida em instantes", life: 1 };
      } else if (payload.kind === "restart") {
        scope.banner = { text: payload.message, sub: "", life: 0.7 };
      } else if (payload.kind === "spill") {
        scope.pops.push({ text: payload.message, life: 1, color: "#f87171" });
      }
    },

    draw(context, state, meta, view) {
      drawSky(context, view.time, cache);

      if (!state) {
        drawWaiting(context);
        return;
      }

      const leader = state.cars.reduce((best, car) => (car.dist > (best ? best.dist : -Infinity) ? car : best), null);
      const camera = leader ? Math.max(0, leader.dist * PPM - WIDTH * 0.35) : 0;
      const toScreen = (dist) => dist * PPM - camera;

      drawRoad(context, camera, view.time);
      drawFinishLine(context, toScreen(state.trackLength));

      for (const oil of state.oils) {
        drawOil(context, toScreen(oil.dist));
      }

      for (const car of state.cars.slice().reverse()) {
        drawCar(context, car, toScreen(car.dist), view.time);
      }

      drawStandings(context, state);
      drawPops(context, view.delta);
    },
  };
}

  // ------------------------------------------------------------------ cenarios
  function drawSky(context, time, cache) {
    const sky = context.createLinearGradient(0, 0, 0, HEIGHT);
    sky.addColorStop(0, "#1d4ed8");
    sky.addColorStop(0.45, "#60a5fa");
    sky.addColorStop(1, "#bfdbfe");
    context.fillStyle = sky;
    context.fillRect(0, 0, WIDTH, HEIGHT);

    // sol
    context.fillStyle = "rgba(253, 224, 71, .85)";
    context.beginPath();
    context.arc(820, 90, 42, 0, Math.PI * 2);
    context.fill();

    if (!cache.clouds.length) {
      cache.clouds = Array.from({ length: 7 }, (_, i) => ({
        x: (i * 190) % (WIDTH + 200),
        y: 40 + ((i * 57) % 130),
        scale: 0.6 + ((i * 13) % 10) / 10,
      }));
    }
    cache.clouds.forEach((cloud) => {
      const x = (cloud.x + time * 6 * cloud.scale) % (WIDTH + 220) - 110;
      drawCloud(context, x, cloud.y, cloud.scale);
    });
  }

  function drawCloud(context, x, y, scale) {
    context.save();
    context.translate(x, y);
    context.scale(scale, scale);
    context.fillStyle = "rgba(255, 255, 255, .88)";
    [[0, 0, 26], [26, 6, 20], [-24, 7, 18], [8, -12, 18]].forEach(([cx, cy, r]) => {
      context.beginPath();
      context.arc(cx, cy, r, 0, Math.PI * 2);
      context.fill();
    });
    context.fillRect(-24, 0, 52, 18);
    context.restore();
  }

  function drawRoad(context, camera, time) {
    // gramado
    context.fillStyle = "#166534";
    context.fillRect(0, ROAD_Y - 70, WIDTH, ROAD_H + 70);

    // faixa de asfalto
    context.fillStyle = "#1f2937";
    context.fillRect(0, ROAD_Y, WIDTH, ROAD_H);
    context.fillStyle = "#111827";
    context.fillRect(0, ROAD_Y + ROAD_H - 14, WIDTH, 14);

    // faixas tracejadas (movem com a camera)
    context.fillStyle = "rgba(248, 250, 252, .75)";
    const spacing = 90;
    const offset = -(camera * PPM) % spacing;
    for (let x = offset - spacing; x < WIDTH + spacing; x += spacing) {
      context.fillRect(x + 24, ROAD_Y + ROAD_H / 2 - 3, 44, 6);
    }

    // guarda-corpo
    context.fillStyle = "#e2e8f0";
    const railOffset = -(camera * PPM) % 60;
    for (let x = railOffset - 60; x < WIDTH + 60; x += 60) {
      context.fillRect(x, ROAD_Y - 16, 44, 12);
    }
    context.fillStyle = "#94a3b8";
    context.fillRect(0, ROAD_Y - 18, WIDTH, 4);
  }

  function drawFinishLine(context, x) {
    if (x < -80 || x > WIDTH + 80) return;
    context.fillStyle = "#f8fafc";
    context.fillRect(x - 4, ROAD_Y - 30, 8, ROAD_H + 30);
    const squares = 12;
    for (let row = 0; row < 4; row += 1) {
      for (let col = 0; col < squares; col += 1) {
        context.fillStyle = (row + col) % 2 === 0 ? "#0f172a" : "#f8fafc";
        context.fillRect(x - 60 + col * 10, ROAD_Y - 30 + row * ((ROAD_H + 30) / 4), 10, (ROAD_H + 30) / 4);
      }
    }
    context.fillStyle = "#0f172a";
    context.font = "800 16px system-ui, sans-serif";
    context.textAlign = "center";
    context.fillText("CHEGADA", x - 30, ROAD_Y - 40);
  }

  function drawOil(context, x) {
    if (x < -60 || x > WIDTH + 60) return;
    context.save();
    context.globalAlpha = 0.85;
    context.fillStyle = "#0b1220";
    context.beginPath();
    context.ellipse(x, ROAD_Y + ROAD_H * 0.62, 34, 12, 0, 0, Math.PI * 2);
    context.fill();
    context.fillStyle = "rgba(56, 189, 248, .35)";
    context.beginPath();
    context.ellipse(x - 6, ROAD_Y + ROAD_H * 0.58, 12, 4, 0, 0, Math.PI * 2);
    context.fill();
    context.restore();
  }

  function drawCar(context, car, x, time) {
    if (x < -120 || x > WIDTH + 120) return;

    const bodyW = 58;
    const bodyH = 26;
    const y = ROAD_Y + 44;
    const bob = car.spinning ? Math.sin(time * 26) * 4 : 0;
    const tilt = car.spinning ? Math.sin(time * 18) * 0.25 : 0;

    context.save();
    context.translate(x, y + bob);
    context.rotate(tilt);

    // sombra
    context.fillStyle = "rgba(0, 0, 0, .3)";
    context.beginPath();
    context.ellipse(0, bodyH / 2 + 4, bodyW / 2, 5, 0, 0, Math.PI * 2);
    context.fill();

    // rodas
    context.fillStyle = "#0b1220";
    [14, -14].forEach((offset) => {
      context.beginPath();
      context.arc(offset, bodyH / 2 - 2, 8, 0, Math.PI * 2);
      context.fill();
    });

    // corpo
    context.fillStyle = car.color;
    context.beginPath();
    context.roundRect(-bodyW / 2, -bodyH / 2, bodyW, bodyH, 8);
    context.fill();

    // cabine
    context.fillStyle = "rgba(15, 23, 42, .82)";
    context.beginPath();
    context.roundRect(-4, -bodyH / 2 - 8, 22, 12, 5);
    context.fill();

    // farol aceso quando turbando
    if (car.boost > 0) {
      context.fillStyle = "#fbbf24";
      context.beginPath();
      context.moveTo(bodyW / 2 - 4, -4);
      context.lineTo(bodyW / 2 + 16 + Math.sin(time * 30) * 5, 0);
      context.lineTo(bodyW / 2 - 4, 4);
      context.closePath();
      context.fill();
    }

    // numero
    context.fillStyle = "rgba(15, 23, 42, .85)";
    context.beginPath();
    context.arc(-bodyW / 2 + 12, 0, 9, 0, Math.PI * 2);
    context.fill();
    context.fillStyle = "#f8fafc";
    context.font = "800 11px system-ui, sans-serif";
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.fillText(String(car.number), -bodyW / 2 + 12, 1);

    // nome do piloto
    context.fillStyle = "#0f172a";
    context.font = "700 11px system-ui, sans-serif";
    context.fillText(truncate(car.name, 12), 0, -bodyH / 2 - 22);

    context.restore();
  }

  function drawStandings(context, state) {
    const top = state.cars.slice(0, 5);
    if (!top.length) return;

    context.save();
    context.fillStyle = "rgba(15, 23, 42, .62)";
    context.beginPath();
    context.roundRect(WIDTH - 176, 56, 164, 22 + top.length * 20, 10);
    context.fill();

    context.textAlign = "left";
    context.textBaseline = "middle";
    top.forEach((car, index) => {
      const y = 76 + index * 20;
      context.fillStyle = car.color;
      context.beginPath();
      context.roundRect(WIDTH - 168, y - 7, 14, 14, 4);
      context.fill();
      context.fillStyle = "#f8fafc";
      context.font = "700 12px system-ui, sans-serif";
      context.fillText(`${index + 1}. ${truncate(car.name, 11)}`, WIDTH - 146, y);
    });
    context.restore();
  }

  function drawPops(context, scope, delta) {
    scope.pops = scope.pops.filter((pop) => (pop.life -= 0.008) > 0);
    context.textAlign = "center";
    context.font = "800 26px system-ui, sans-serif";
    scope.pops.forEach((pop, index) => {
      context.globalAlpha = Math.min(1, pop.life);
      context.fillStyle = pop.color;
      context.fillText(pop.text, WIDTH / 2, 150 + index * 34);
    });
    context.globalAlpha = 1;

    if (scope.banner && scope.banner.life > 0) {
      scope.banner.life -= 0.004 * (delta || 1);
      context.fillStyle = "rgba(15, 23, 42, .78)";
      context.fillRect(0, 210, WIDTH, 110);
      context.fillStyle = "#fde68a";
      context.font = "900 40px system-ui, sans-serif";
      context.fillText(scope.banner.text, WIDTH / 2, 268);
      if (scope.banner.sub) {
        context.fillStyle = "#94a3b8";
        context.font = "600 16px system-ui, sans-serif";
        context.fillText(scope.banner.sub, WIDTH / 2, 296);
      }
    }
  }

  function drawWaiting(context) {
    context.fillStyle = "rgba(8, 15, 30, .55)";
    context.fillRect(0, 0, WIDTH, HEIGHT);
    context.fillStyle = "#e2e8f0";
    context.font = "700 24px system-ui, sans-serif";
    context.textAlign = "center";
    context.fillText("aguardando alguém comentar na live…", WIDTH / 2, HEIGHT / 2 - 10);
    context.fillStyle = "#94a3b8";
    context.font = "500 15px system-ui, sans-serif";
    context.fillText("o primeiro comentário cria o primeiro carro", WIDTH / 2, HEIGHT / 2 + 18);
  }

  function truncate(text, size) {
    return text.length > size ? `${text.slice(0, size - 1)}…` : text;
  }

  function escapeHtml(text) {
    return String(text).replace(/[&<>"']/g, (char) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[char]);
  }
