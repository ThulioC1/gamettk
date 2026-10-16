/* Renderer do Platformer: mundo fixo, jogador com interpolacao. */

const scope = { pops: [], particles: [], flash: 0 };
const display = { x: 60, y: 420 };

export function create() {
  return {
    width: 960,
    height: 540,
    keyboard: true,
    controls: `
      <button class="btn" data-command="MOVE_LEFT">◀ esquerda</button>
      <button class="btn" data-command="JUMP">▲ pular</button>
      <button class="btn" data-command="MOVE_RIGHT">direita ▶</button>
      <button class="btn ghost" data-command="STOP">■ parar</button>
      <button class="btn ghost" data-command="RESET">↺ reset</button>`,

    hud(state) {
      if (!state) return { score: "", meta: "" };
      return {
        score: `PONTOS <b>${state.score}</b>`,
        meta: state.won ? "chegada! clique para recomeçar" : "colete as moedas e chegue na bandeira",
      };
    },

    onGameEvent(payload) {
      if (payload.message) {
        scope.pops.push({
          text: payload.message,
          life: 1,
          color: payload.kind === "death" ? "#f87171" : "#fbbf24",
        });
      }
      const origin = payload.kind === "death" ? [display.x, Math.min(display.y, 470)] : [display.x + 14, display.y];
      const amount = payload.kind === "goal" ? 40 : 14;
      burst(origin[0], origin[1], payload.kind === "death" ? "#f87171" : "#fbbf24", amount);
      if (payload.kind === "goal") scope.flash = 1;
    },

    draw(context, state, meta, view) {
      drawBackground(context);

      if (!state) {
        drawWaiting(context);
        return;
      }

      display.x += (state.player.x - display.x) * 0.45;
      display.y += (state.player.y - display.y) * 0.45;

      const [pw, ph] = state.playerSize;
      const [px, py] = state.world ? [state.world.width, state.world.height] : [960, 540];

      for (const [x, y, w, h] of state.platforms) {
        context.fillStyle = x === 0 ? "#0e2b49" : "#10405c";
        context.fillRect(x, y, w, h);
        context.fillStyle = "rgba(34, 211, 238, .55)";
        context.fillRect(x, y, w, 2);
      }

      for (const coin of state.coins) {
        if (coin.collected) continue;
        const squash = Math.abs(Math.cos(view.time * 2.5 + coin.x));
        context.save();
        context.translate(coin.x, coin.y);
        context.scale(0.35 + squash * 0.65, 1);
        context.fillStyle = "#fbbf24";
        context.beginPath();
        context.arc(0, 0, state.coinRadius, 0, Math.PI * 2);
        context.fill();
        context.fillStyle = "#fde68a";
        context.beginPath();
        context.arc(-2.5, -2.5, state.coinRadius * 0.38, 0, Math.PI * 2);
        context.fill();
        context.restore();
      }

      const goal = state.goal;
      context.fillStyle = "#cbd5e1";
      context.fillRect(goal.x, goal.y, 3, goal.height);
      context.fillStyle = "#ec4899";
      context.beginPath();
      context.moveTo(goal.x + 3, goal.y + 2);
      context.lineTo(goal.x + 34, goal.y + 8 + Math.sin(view.time * 3) * 3);
      context.lineTo(goal.x + 3, goal.y + 16);
      context.closePath();
      context.fill();

      drawPlayer(context, state.player, pw, ph, view.time);

      if (state.won) {
        context.fillStyle = "rgba(4, 10, 20, .6)";
        context.fillRect(0, 0, px, py);
        context.fillStyle = "#fde68a";
        context.font = "900 38px system-ui, sans-serif";
        context.textAlign = "center";
        context.fillText("VOCÊ CHEGOU!", px / 2, py / 2);
        context.fillStyle = "#94a3b8";
        context.font = "600 15px system-ui, sans-serif";
        context.fillText("clique para jogar de novo", px / 2, py / 2 + 26);
      }

      drawEffects(context, view.delta);
    },
  };
}

function drawBackground(context) {
  const sky = context.createLinearGradient(0, 0, 0, 540);
  sky.addColorStop(0, "#0a1830");
  sky.addColorStop(0.6, "#0c2444");
  sky.addColorStop(1, "#071021");
  context.fillStyle = sky;
  context.fillRect(0, 0, 960, 540);

  context.fillStyle = "rgba(34, 211, 238, .3)";
  for (let i = 0; i < 42; i += 1) {
    context.fillRect((i * 137) % 960, (i * 83) % 300, 2, 2);
  }
}

function drawWaiting(context) {
  context.fillStyle = "rgba(8, 15, 30, .55)";
  context.fillRect(0, 0, 960, 540);
  context.fillStyle = "#e2e8f0";
  context.font = "700 22px system-ui, sans-serif";
  context.textAlign = "center";
  context.fillText("aguardando o servidor enviar o estado…", 480, 270);
}

function drawPlayer(context, player, pw, ph, time) {
  context.save();
  context.translate(display.x + pw / 2, display.y);
  context.scale(player.facingRight ? 1 : -1, 1);
  context.translate(0, player.onGround ? 0 : Math.sin(time * 12) * 1.5);

  context.fillStyle = "#22d3ee";
  context.shadowColor = "rgba(34, 211, 238, .65)";
  context.shadowBlur = 14;
  context.beginPath();
  context.roundRect(-pw / 2, -ph, pw, ph, 8);
  context.fill();
  context.shadowBlur = 0;

  context.fillStyle = "#08324a";
  context.beginPath();
  context.arc(4, -ph + 13, 2.6, 0, Math.PI * 2);
  context.arc(-5, -ph + 13, 2.6, 0, Math.PI * 2);
  context.fill();

  context.strokeStyle = "#08324a";
  context.lineWidth = 2;
  context.beginPath();
  context.moveTo(-4, -ph + 24);
  context.lineTo(4, -ph + 24);
  context.stroke();
  context.restore();
}

function burst(x, y, color, amount) {
  for (let i = 0; i < amount; i += 1) {
    const angle = Math.random() * Math.PI * 2;
    const speed = 1 + Math.random() * 4;
    scope.particles.push({ x, y, vx: Math.cos(angle) * speed, vy: Math.sin(angle) * speed - 1, life: 1, color });
  }
}

function drawEffects(context, delta) {
  scope.pops = scope.pops.filter((pop) => (pop.life -= 0.012) > 0);
  context.textAlign = "center";
  context.font = "800 24px system-ui, sans-serif";
  scope.pops.forEach((pop) => {
    context.globalAlpha = Math.max(0, Math.min(1, pop.life));
    context.fillStyle = pop.color;
    context.fillText(pop.text, 480, 140);
  });

  scope.particles = scope.particles.filter((particle) => {
    particle.x += particle.vx;
    particle.y += particle.vy;
    particle.vy += 0.12;
    particle.life -= 0.02;
    return particle.life > 0;
  });
  scope.particles.forEach((particle) => {
    context.globalAlpha = Math.max(0, particle.life);
    context.fillStyle = particle.color;
    context.fillRect(particle.x, particle.y, 3, 3);
  });
  context.globalAlpha = 1;
}
