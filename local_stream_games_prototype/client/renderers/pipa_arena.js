/* Renderer da Pipa Arena: ceu azul, pipas subindo e linhas sendo cortadas.
 *
 * O estado vem do servidor (server/games/pipa_arena.py). `kite.y` e a altura
 * acima do chao: aqui vira posicao na tela (y = groundY - altura).
 */
const WIDTH = 960;
const HEIGHT = 540;
const TAIL = 54;

const scope = { cuts: [], banner: null, confetti: [] };

export function create() {
  return {
    width: WIDTH,
    height: HEIGHT,
    keyboard: false,
    controls: "",

    hud(state) {
      if (!state) return { score: "", meta: "" };
      const leader = state.leaders[0];
      return {
        score: `PIPAS NO CEU <b>${state.load}/${state.maxKites}</b>`,
        meta: leader
          ? `mais alta: <b>${leader.user}</b> · ${state.totalFlights} pipas soltas`
          : "nenhuma pipa no ar — comente para soltar a sua",
      };
    },

    onEvent(event, notices) {
      for (const notice of notices) {
        if (notice.kind !== "cut" || !notice.message) continue;
        scope.cuts.push({ life: 1, text: notice.message });
      }
    },

    onGameEvent(payload) {
      if (payload.kind === "restart") {
        scope.banner = { text: payload.message, sub: "o ceu voltou a ficar limpo", life: 0.8 };
      }
      if (payload.kind === "land") {
        for (let i = 0; i < 12; i += 1) {
          scope.confetti.push({
            x: 480 + (Math.random() - 0.5) * 600,
            y: 120,
            vx: (Math.random() - 0.5) * 3,
            vy: 1 + Math.random() * 3,
            color: payload.color || "#fbbf24",
            size: 3 + Math.random() * 3,
            life: 1,
          });
        }
      }
    },

    draw(context, state, meta, view) {
      drawSky(context, view.time);

      if (!state) {
        drawWaiting(context);
        return;
      }

      const groundY = state.world.groundY;

      // linhas primeiro (ficam atras das pipas)
      for (const kite of state.kites) {
        drawString(context, kite, groundY, view.time);
      }

      for (const piece of state.fallen) {
        drawFallingPiece(context, piece);
      }

      for (const kite of state.kites.slice().reverse()) {
        drawKite(context, kite, groundY, view.time);
      }

      drawGround(context, groundY);
      drawLeaders(context, state);
      drawCuts(context, view);
      drawConfetti(context);
      drawBanner(context);
    },
  };
}

// ------------------------------------------------------------------ cenarios
function drawSky(context, time) {
  const sky = context.createLinearGradient(0, 0, 0, HEIGHT);
  sky.addColorStop(0, "#38bdf8");
  sky.addColorStop(0.55, "#7dd3fc");
  sky.addColorStop(1, "#e0f2fe");
  context.fillStyle = sky;
  context.fillRect(0, 0, WIDTH, HEIGHT);

  // sol com halo
  context.fillStyle = "rgba(255, 255, 255, .35)";
  context.beginPath();
  context.arc(120, 90, 46, 0, Math.PI * 2);
  context.fill();
  context.fillStyle = "rgba(253, 224, 71, .95)";
  context.beginPath();
  context.arc(120, 90, 30, 0, Math.PI * 2);
  context.fill();

  // nuvens em parallax
  for (let i = 0; i < 6; i += 1) {
    const x = ((i * 220 + time * 8) % (WIDTH + 240)) - 120;
    const y = 60 + ((i * 71) % 220);
    drawCloud(context, x, y, 0.7 + (i % 3) * 0.25);
  }
}

function drawCloud(context, x, y, scale) {
  context.save();
  context.translate(x, y);
  context.scale(scale, scale);
  context.fillStyle = "rgba(255, 255, 255, .9)";
  [[0, 0, 24], [24, 6, 18], [-22, 7, 16], [8, -10, 16]].forEach(([cx, cy, r]) => {
    context.beginPath();
    context.arc(cx, cy, r, 0, Math.PI * 2);
    context.fill();
  });
  context.fillRect(-22, 0, 46, 16);
  context.restore();
}

function drawGround(context, groundY) {
  context.fillStyle = "#86efac";
  context.fillRect(0, groundY, WIDTH, HEIGHT - groundY);
  context.fillStyle = "#4ade80";
  context.fillRect(0, groundY, WIDTH, 4);
  context.fillStyle = "rgba(22, 101, 52, .18)";
  for (let i = 0; i < 26; i += 1) {
    context.fillRect((i * 73) % WIDTH, groundY + 10 + ((i * 29) % 40), 14, 3);
  }
}

function drawString(context, kite, groundY, time) {
  const x = kite.x + Math.sin(time * 1.4 + kite.id) * 3;
  context.strokeStyle = "rgba(30, 41, 59, .35)";
  context.lineWidth = 1;
  context.beginPath();
  context.moveTo(x, groundY);
  // catenaria simples: a linha cai de lado com o vento
  context.quadraticCurveTo(x + (kite.x - x) * 1.6, (groundY + kite.y) / 2, x, kite.y);
  context.stroke();
}

function drawKite(context, kite, groundY, time) {
  const x = kite.x + Math.sin(time * 1.4 + kite.id) * 3;
  const y = groundY - kite.y;
  const tilt = Math.sin(time * 2 + kite.id) * 0.12;

  context.save();
  context.translate(x, y);
  context.rotate(tilt);

  // rabo com bandeirinhas
  context.strokeStyle = "rgba(30, 41, 59, .5)";
  context.lineWidth = 1;
  context.beginPath();
  context.moveTo(0, 10);
  context.quadraticCurveTo(6, 26, -4, TAIL);
  context.stroke();

  // corpo da pipa (losango)
  const size = 17;
  context.fillStyle = kite.color;
  context.beginPath();
  context.moveTo(0, -size * 1.2);
  context.lineTo(size, 0);
  context.lineTo(0, size * 1.2);
  context.lineTo(-size, 0);
  context.closePath();
  context.fill();

  // costura central
  context.strokeStyle = "rgba(255, 255, 255, .75)";
  context.lineWidth = 1.5;
  context.beginPath();
  context.moveTo(0, -size * 1.2);
  context.lineTo(0, size * 1.2);
  context.moveTo(-size, 0);
  context.lineTo(size, 0);
  context.stroke();

  // nome do dono (para a live saber de quem e a pipa)
  context.fillStyle = "rgba(15, 23, 42, .8)";
  context.font = "700 10px system-ui, sans-serif";
  context.textAlign = "center";
  context.fillText(kite.user, 0, size * 1.2 + 12);

  context.restore();
}

function drawFallingPiece(context, piece) {
  const y = (piece.y ?? 0) + 0; // snapshot ja traz altura
  context.save();
  context.globalAlpha = Math.max(0, piece.life);
  context.translate(piece.x, 520 - y + (1 - piece.life) * 120);
  context.rotate((1 - piece.life) * 6);
  context.fillStyle = piece.color;
  context.beginPath();
  context.moveTo(0, -10);
  context.lineTo(8, 0);
  context.lineTo(0, 10);
  context.lineTo(-8, 0);
  context.closePath();
  context.fill();
  context.restore();
  context.globalAlpha = 1;
}

function drawLeaders(context, state) {
  const leaders = state.leaders || [];
  if (!leaders.length) return;

  context.save();
  context.fillStyle = "rgba(255, 255, 255, .78)";
  context.beginPath();
  context.roundRect(14, 14, 196, 24 + leaders.length * 19, 10);
  context.fill();

  context.textAlign = "left";
  context.textBaseline = "middle";
  context.fillStyle = "#0f172a";
  context.font = "800 12px system-ui, sans-serif";
  context.fillText("MAIS ALTAS", 26, 30);
  leaders.forEach((leader, index) => {
    const y = 50 + index * 19;
    context.fillStyle = "#334155";
    context.font = "600 12px system-ui, sans-serif";
    context.fillText(`${index + 1}. ${leader.user}`, 26, y);
    context.textAlign = "right";
    context.fillStyle = "#0369a1";
    context.fillText(`${Math.round(leader.y)} px`, 198, y);
    context.textAlign = "left";
  });
  context.restore();
}

function drawCuts(context, view) {
  scope.cuts = scope.cuts.filter((cut) => (cut.life -= 0.015) > 0);
  context.textAlign = "center";
  context.font = "800 24px system-ui, sans-serif";
  scope.cuts.forEach((cut, index) => {
    context.globalAlpha = Math.max(0, Math.min(1, cut.life));
    context.fillStyle = "#e11d48";
    context.fillText(cut.text, WIDTH / 2, 120 + index * 30);
  });
  context.globalAlpha = 1;
}

function drawConfetti(context) {
  scope.confetti = scope.confetti.filter((piece) => {
    piece.x += piece.vx;
    piece.y += piece.vy;
    piece.life -= 0.01;
    return piece.life > 0 && piece.y < HEIGHT;
  });
  scope.confetti.forEach((piece) => {
    context.globalAlpha = Math.max(0, piece.life);
    context.fillStyle = piece.color;
    context.fillRect(piece.x, piece.y, piece.size, piece.size);
  });
  context.globalAlpha = 1;
}

function drawBanner(context) {
  if (!scope.banner || scope.banner.life <= 0) return;
  scope.banner.life -= 0.006;
  context.fillStyle = "rgba(255, 255, 255, .85)";
  context.beginPath();
  context.roundRect(WIDTH / 2 - 250, 200, 500, 76, 14);
  context.fill();
  context.fillStyle = "#0369a1";
  context.font = "900 26px system-ui, sans-serif";
  context.textAlign = "center";
  context.fillText(scope.banner.text, WIDTH / 2, 240);
  if (scope.banner.sub) {
    context.fillStyle = "#64748b";
    context.font = "600 13px system-ui, sans-serif";
    context.fillText(scope.banner.sub, WIDTH / 2, 262);
  }
}

function drawWaiting(context) {
  context.fillStyle = "rgba(255, 255, 255, .5)";
  context.fillRect(0, 0, WIDTH, HEIGHT);
  context.textAlign = "center";
  context.fillStyle = "#0f172a";
  context.font = "700 22px system-ui, sans-serif";
  context.fillText("o ceu esta vazio — o primeiro comentario solta a primeira pipa", WIDTH / 2, 280);
}
