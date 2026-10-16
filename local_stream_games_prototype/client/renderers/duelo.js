/* Renderer do Duelo de Torres: duas torres, cada bloco com a cor do partido.
 *
 * O estado vem do servidor (server/games/duelo.py). Quem apena desenha: pilha de
 * blocos, avatares no topo, destrocos caindo quando a torre desaba e confete
 * quando alguem vence.
 */
const WIDTH = 960;
const HEIGHT = 540;

const scope = { debris: [], confetti: [], banner: null, flash: {}, feed: [] };

export function create() {
  return {
    width: WIDTH,
    height: HEIGHT,
    keyboard: false,
    controls: "",

    hud(state) {
      if (!state) return { score: "", meta: "" };
      const [a, b] = state.towers;
      return {
        score: `${a.side.party || a.side.name} <b>${a.height}</b> &nbsp;×&nbsp; ${b.side.party || b.side.name} <b>${b.height}</b>`,
        meta: `meta: ${state.targetBlocks} blocos para vencer · ${a.supporters + b.supporters} pessoas na disputa`,
      };
    },

    onEvent(event, notices) {
      for (const notice of notices) {
        if (!notice.message) continue;
        if (notice.kind === "slide") {
          spawnDebris(notice.side, 1);
        } else if (notice.kind === "sabotage") {
          scope.flash[notice.side] = 1;
          spawnDebris(notice.side, notice.blocks || 2);
        } else if (notice.kind === "collapse") {
          scope.flash[notice.side] = 1;
        }
      }
    },

    onGameEvent(payload) {
      if (payload.kind === "collapse") {
        spawnDebris(payload.side, payload.blocks || 4);
        scope.banner = { text: payload.message, sub: "a torre cedeu!", life: 1, color: "#f87171" };
      } else if (payload.kind === "restart") {
        scope.debris = [];
        scope.banner = { text: payload.message, sub: "todo mundo de volta ao zero", life: 0.8, color: "#e2e8f0" };
      } else if (payload.kind === "winner") {
        const tower = findTower(payload.side);
        scope.banner = {
          text: payload.message,
          sub: "novo duelo em instantes",
          life: 1,
          color: tower ? tower.side.color : "#fbbf24",
        };
        burstConfetti(tower ? tower.side.color : "#fbbf24");
      }
    },

    draw(context, state, meta, view) {
      lastState = state;
      drawStage(context);

      if (!state) {
        drawWaiting(context);
        return;
      }

      const [left, right] = state.towers;
      drawHeader(context, state);
      drawTower(context, left, view.time, "left");
      drawTower(context, right, view.time, "right");
      drawCenter(context, state);
      drawDebris(context, view.delta);
      drawConfetti(context, view.delta);
      drawBanner(context, view.delta);
    },
  };
}

let lastState = null;

// ------------------------------------------------------------------ cenarios
function drawStage(context) {
  const bg = context.createLinearGradient(0, 0, 0, HEIGHT);
  bg.addColorStop(0, "#0b1220");
  bg.addColorStop(1, "#111c30");
  context.fillStyle = bg;
  context.fillRect(0, 0, WIDTH, HEIGHT);

  // holofotes
  context.fillStyle = "rgba(59, 130, 246, .07)";
  context.beginPath();
  context.moveTo(240, 0);
  context.lineTo(80, 520);
  context.lineTo(400, 520);
  context.closePath();
  context.fill();
  context.fillStyle = "rgba(225, 29, 72, .07)";
  context.beginPath();
  context.moveTo(720, 0);
  context.lineTo(560, 520);
  context.lineTo(880, 520);
  context.closePath();
  context.fill();

  // chao
  context.fillStyle = "#0a1526";
  context.fillRect(0, 512, WIDTH, HEIGHT - 512);
  context.fillStyle = "rgba(148, 163, 184, .35)";
  context.fillRect(0, 512, WIDTH, 2);
}

function drawHeader(context, state) {
  const [left, right] = state.towers;
  const target = state.targetBlocks;

  // barra de progresso de cada lado
  [[left, 60], [right, WIDTH - 60]].forEach(([tower, x], index) => {
    const width = 200;
    const barX = index === 0 ? x - width : x;
    context.fillStyle = "rgba(148, 163, 184, .18)";
    context.beginPath();
    context.roundRect(barX, 66, width, 10, 5);
    context.fill();
    context.fillStyle = tower.side.color;
    context.beginPath();
    context.roundRect(barX, 66, Math.max(10, width * Math.min(1, tower.height / target)), 10, 5);
    context.fill();

    context.textAlign = index === 0 ? "left" : "right";
    context.fillStyle = "#e2e8f0";
    context.font = "800 20px system-ui, sans-serif";
    context.fillText(tower.side.name.toUpperCase(), index === 0 ? barX : barX + width, 56);
    context.fillStyle = tower.side.color;
    context.font = "700 12px system-ui, sans-serif";
    context.fillText(tower.side.party || tower.side.tagline, index === 0 ? barX : barX + width, 92);
  });

  // placar central
  context.textAlign = "center";
  context.fillStyle = "#f8fafc";
  context.font = "900 30px system-ui, sans-serif";
  context.fillText(`${left.height}`, WIDTH / 2 - 34, 66);
  context.fillText(`${right.height}`, WIDTH / 2 + 34, 66);
  context.fillStyle = "#64748b";
  context.font = "800 18px system-ui, sans-serif";
  context.fillText("VS", WIDTH / 2, 64);
  context.fillStyle = "#475569";
  context.font = "600 11px system-ui, sans-serif";
  context.fillText(`meta ${target}`, WIDTH / 2, 84);
}

function drawCenter(context, state) {
  const y = BASE(state);
  context.strokeStyle = "rgba(148, 163, 184, .25)";
  context.lineWidth = 2;
  context.setLineDash([6, 8]);
  context.beginPath();
  context.moveTo(WIDTH / 2, 100);
  context.lineTo(WIDTH / 2, y);
  context.stroke();
  context.setLineDash([]);
}

function BASE(state) {
  return state.baseY || 512;
}

function drawTower(context, tower, time, side) {
  const state = lastState;
  const baseY = BASE(state);
  const blockHeight = state.blockHeight;
  const width = state.towerWidth;
  const blockWidth = state.blockWidth;
  const centerX = side === "left" ? 240 : WIDTH - 240;

  const lean = Math.sin(time * 2) * tower.lean * 6;

  context.save();
  context.translate(centerX, baseY);

  // base/pedestal
  context.fillStyle = tower.side.dark;
  context.beginPath();
  context.roundRect(-width / 2 - 10, -14, width + 20, 18, 6);
  context.fill();

  // pilha de blocos
  tower.blocks.forEach((block, index) => {
    const y = -(index + 1) * blockHeight;
    const wobble = Math.sin(time * 1.6 + index * 0.4) * tower.lean * 3;
    const shift = block.offset + lean * ((tower.blocks.length - index) / 10) + wobble;

    context.fillStyle = tower.side.color;
    context.fillRect(shift - blockWidth / 2, y, blockWidth, blockHeight - 2);
    context.fillStyle = "rgba(255, 255, 255, .18)";
    context.fillRect(shift - blockWidth / 2, y, blockWidth, 3);
    context.fillStyle = tower.side.dark;
    context.fillRect(shift - blockWidth / 2, y + blockHeight - 4, blockWidth, 2);

    // nome de quem levantou este bloco (no topo da pilha)
    if (index >= tower.blocks.length - 3 && block.by) {
      context.fillStyle = "rgba(255, 255, 255, .78)";
      context.font = "700 10px system-ui, sans-serif";
      context.textAlign = "center";
      context.fillText(block.by, shift, y + blockHeight - 6);
    }
  });

  // avatar em cima da torre
  const topY = -tower.blocks.length * blockHeight;
  drawAvatar(context, tower, topY, time, lean);

  // aviso de inclinacao
  if (tower.lean > 0.6) {
    context.fillStyle = `rgba(248, 113, 113, ${Math.min(0.9, (tower.lean - 0.6) * 2.5)})`;
    context.font = "800 12px system-ui, sans-serif";
    context.textAlign = "center";
    context.fillText("TREMENDO!", 0, topY - 66);
  }

  context.restore();

  // flash vermelho quando desaba/sabotado
  if (scope.flash[tower.side.id] > 0) {
    scope.flash[tower.side.id] -= 0.03;
    context.fillStyle = `rgba(248, 113, 113, ${Math.max(scope.flash[tower.side.id], 0) * 0.25})`;
    context.fillRect(centerX - width / 2 - 20, 100, width + 40, baseY - 100);
  }
}

function drawAvatar(context, tower, topY, time, lean) {
  const color = tower.side.color;
  const wobble = Math.sin(time * 3) * (tower.won ? 3 : 1);

  context.save();
  context.translate(lean, topY - 34 + wobble);

  // corpo
  context.fillStyle = tower.side.dark;
  context.beginPath();
  context.roundRect(-26, 16, 52, 40, 12);
  context.fill();
  // camisa
  context.fillStyle = "#f8fafc";
  context.beginPath();
  context.moveTo(-8, 16);
  context.lineTo(8, 16);
  context.lineTo(4, 40);
  context.lineTo(-4, 40);
  context.closePath();
  context.fill();
  // cabeca
  context.fillStyle = "#fcd9b6";
  context.beginPath();
  context.arc(0, 0, 17, 0, Math.PI * 2);
  context.fill();
  // cabelo
  context.fillStyle = "#1f2937";
  context.beginPath();
  context.arc(0, -3, 17, Math.PI * 1.05, Math.PI * 1.95);
  context.fill();
  // olhos
  context.fillStyle = "#111827";
  context.beginPath();
  context.arc(-5, 2, 2, 0, Math.PI * 2);
  context.arc(5, 2, 2, 0, Math.PI * 2);
  context.fill();

  // "VENCEU" sobre o campeao
  if (tower.won) {
    context.fillStyle = "#fbbf24";
    context.font = "900 16px system-ui, sans-serif";
    context.textAlign = "center";
    context.fillText("CAMPEÃO!", 0, -26);
  }

  context.restore();
}

// ------------------------------------------------------------------ efeitos
function findTower(sideId) {
  if (!lastState || !lastState.towers) return null;
  return lastState.towers.find((tower) => tower.side.id === sideId) || null;
}

function towerCenterX(tower) {
  return tower && tower.side.id === lastState.towers[0].side.id ? 240 : WIDTH - 240;
}

function spawnDebris(sideId, count) {
  const state = lastState;
  const tower = findTower(sideId);
  if (!state || !tower) return;

  const centerX = towerCenterX(tower);
  const total = Math.max(1, Math.min(count, 6));

  for (let i = 0; i < total; i += 1) {
    const block = tower.blocks[tower.blocks.length - 1 - i] || { offset: 0 };
    scope.debris.push({
      x: centerX + block.offset,
      y: (state.baseY || 512) - tower.blocks.length * state.blockHeight + i * state.blockHeight,
      vx: (Math.random() - 0.5) * 6,
      vy: -3 - Math.random() * 4,
      rot: 0,
      spin: (Math.random() - 0.5) * 0.3,
      color: tower.side.color,
      w: state.blockWidth * 0.7,
      h: state.blockHeight - 2,
      life: 1,
    });
  }
}

function burstConfetti(color) {
  for (let i = 0; i < 90; i += 1) {
    scope.confetti.push({
      x: WIDTH / 2 + (Math.random() - 0.5) * 420,
      y: 120 + Math.random() * 120,
      vx: (Math.random() - 0.5) * 8,
      vy: Math.random() * 5 + 2,
      color: Math.random() < 0.5 ? color : "#fbbf24",
      size: 4 + Math.random() * 4,
      rot: Math.random() * Math.PI,
      spin: (Math.random() - 0.5) * 0.4,
      life: 1,
    });
  }
}

function drawDebris(context, delta) {
  scope.debris = scope.debris.filter((piece) => {
    piece.x += piece.vx;
    piece.y += piece.vy;
    piece.vy += 0.45;
    piece.rot += piece.spin;
    piece.life -= 0.012;
    return piece.life > 0 && piece.y < HEIGHT + 80;
  });

  scope.debris.forEach((piece) => {
    context.save();
    context.globalAlpha = Math.max(0, piece.life);
    context.translate(piece.x, piece.y);
    context.rotate(piece.rot);
    context.fillStyle = piece.color;
    context.fillRect(-piece.w / 2, -piece.h / 2, piece.w, piece.h);
    context.restore();
  });
  context.globalAlpha = 1;
}

function drawConfetti(context) {
  scope.confetti = scope.confetti.filter((piece) => {
    piece.x += piece.vx;
    piece.y += piece.vy;
    piece.rot += piece.spin;
    piece.life -= 0.006;
    return piece.life > 0 && piece.y < HEIGHT + 20;
  });
  scope.confetti.forEach((piece) => {
    context.save();
    context.globalAlpha = Math.max(0, piece.life);
    context.translate(piece.x, piece.y);
    context.rotate(piece.rot);
    context.fillStyle = piece.color;
    context.fillRect(-piece.size / 2, -piece.size / 2, piece.size, piece.size);
    context.restore();
  });
  context.globalAlpha = 1;
}

function drawBanner(context) {
  if (!scope.banner || scope.banner.life <= 0) return;
  scope.banner.life -= 0.006;
  context.textAlign = "center";
  context.fillStyle = "rgba(8, 14, 26, .82)";
  context.beginPath();
  context.roundRect(WIDTH / 2 - 300, 236, 600, 92, 14);
  context.fill();
  context.fillStyle = scope.banner.color;
  context.font = "900 34px system-ui, sans-serif";
  context.fillText(scope.banner.text, WIDTH / 2, 282);
  if (scope.banner.sub) {
    context.fillStyle = "#94a3b8";
    context.font = "600 14px system-ui, sans-serif";
    context.fillText(scope.banner.sub, WIDTH / 2, 306);
  }
}

function drawWaiting(context) {
  context.fillStyle = "rgba(8, 14, 26, .6)";
  context.fillRect(0, 0, WIDTH, HEIGHT);
  context.textAlign = "center";
  context.fillStyle = "#e2e8f0";
  context.font = "700 22px system-ui, sans-serif";
  context.fillText("aguardando a live escolher um lado…", WIDTH / 2, 280);
  context.fillStyle = "#94a3b8";
  context.font = "500 15px system-ui, sans-serif";
  context.fillText("comente o nome do seu lado para começar", WIDTH / 2, 308);
}
