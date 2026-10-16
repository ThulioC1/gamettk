/* Roda cada renderer fora do navegador, contra um estado real do servidor.
 *
 * Sem isso, um erro no renderer so aparece na tela (canvas congelado / vazio) e
 * ninguem descobre o por que. Aqui o erro estoura no console.
 *
 *   node tests/render_check.mjs
 */
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);

// ---------------------------------------------------------------- mock de canvas
const stats = { fillRect: 0, fillText: 0, roundRect: 0, arc: 0, stroke: 0, save: 0 };

/* ---------------------------------------------------------------- posicoes
 * Guardamos onde cada desenho foi colocado, para provar que os carros CAEM NA
 * TELA (o bug do usuario era um canvas que ficava com a pista vazia). */
const posicoes = [];
function mockContext() {
  const noop = () => {};
  const ctx = {
    canvas: { width: 960, height: 540 },
    globalAlpha: 1,
    fillStyle: "#000",
    strokeStyle: "#000",
    lineWidth: 1,
    font: "",
    textAlign: "left",
    textBaseline: "top",
    save: () => { stats.save += 1; },
    restore: noop,
    translate: (x, y) => { posicoes.push({ tipo: "translate", x, y }); },
    rotate: noop,
    scale: noop,
    beginPath: noop,
    closePath: noop,
    moveTo: noop,
    lineTo: noop,
    arc: (x, y) => { posicoes.push({ tipo: "arc", x, y }); },
    ellipse: (x, y) => { posicoes.push({ tipo: "arc", x, y }); },
    quadraticCurveTo: noop,
    rect: noop,
    roundRect: (...a) => { stats.roundRect += 1; posicoes.push({ tipo: "roundRect", x: a[0], y: a[1] }); },
    fill: noop,
    stroke: () => { stats.stroke += 1; },
    setTransform: noop,
    clearRect: noop,
    setLineDash: noop,
    getLineDash: () => [],
    clip: noop,
    fillRect: (...a) => { stats.fillRect += 1; ctx.lastFill = a; },
    fillText: (text, ...a) => { stats.fillText += 1; ctx.lastText = text; },
    strokeText: noop,
    createLinearGradient: () => ({ addColorStop: noop }),
    measureText: () => ({ width: 40 }),
  };
  return ctx;
}

// ---------------------------------------------------------------- estados reais
// Mesmo formato que GameBase.snapshot() devolve (ver server/games/*.py).
const ESTADOS = {
  corrida: {
    phase: "racing",
    countdown: 0,
    trackLength: 5000,
    lanes: 5,
    baseSpeed: 4.5,
    kmhFactor: 40,
    winner: null,
    lastJoiner: "ana",
    restartIn: 0,
    oils: [{ dist: 220 }, { dist: 640 }],
    cars: [
      { user: "ana", name: "ana", number: 1, lane: 0, vehicle: "gol", vehicleName: "Gol", isMoto: false, color: "#1f9d55", dark: "#0f6b3a", dist: 1400, speed: 4.5, kmh: 180, boost: 0, spinning: false, points: 12, place: 1, finished: false },
      { user: "br", name: "br.com", number: 2, lane: 1, vehicle: "pcx", vehicleName: "PCX", isMoto: true, color: "#3b82f6", dark: "#1e3a8a", dist: 900, speed: 11, kmh: 440, boost: 6, spinning: false, points: 8, place: 2, finished: false },
      { user: "carla", name: "carla_", number: 3, lane: 2, vehicle: "fusca", vehicleName: "Fusca", isMoto: false, color: "#ef4444", dark: "#991b1b", dist: 180, speed: 0, kmh: 0, boost: 0, spinning: true, points: 3, place: 3, finished: false },
      { user: "duda", name: "duda.exe", number: 4, lane: 3, vehicle: "g8", vehicleName: "G8", isMoto: false, color: "#fbbf24", dark: "#b45309", dist: 4600, speed: 4.5, kmh: 180, boost: 0, spinning: false, points: 30, place: 1, finished: true },
    ],
  },
  duelo: {
    title: "Duelo de Torres",
    targetBlocks: 32,
    blockHeight: 12,
    towerWidth: 320,
    blockWidth: 250,
    baseY: 512,
    winner: null,
    restartIn: 0,
    towers: [
      {
        side: { id: "esquerda", name: "Lula", party: "PT", color: "#e11d48", dark: "#881337", tagline: "", keywords: [] },
        blocks: Array.from({ length: 9 }, (_, i) => ({ offset: i * 2, by: "ana", at: i, dropped: false })),
        height: 9, lean: 0.2, supporter: "ana", won: false, supporters: 3,
      },
      {
        side: { id: "direita", name: "Flávio Bolsonaro", party: "PL", color: "#2563eb", dark: "#1e3a8a", tagline: "", keywords: [] },
        blocks: Array.from({ length: 5 }, (_, i) => ({ offset: -i, by: "br", at: i, dropped: false })),
        height: 5, lean: 0.1, supporter: "br", won: false, supporters: 2,
      },
    ],
  },
  pipa: {
    title: "Pipa Arena",
    world: { width: 960, groundY: 520, maxAltitude: 400 },
    kites: [
      { id: 1, user: "ana", color: "#f43f5e", x: 200, y: 260, anchored: false, points: 0, cuts: 0 },
      { id: 2, user: "br", color: "#3b82f6", x: 640, y: 120, anchored: false, points: 10, cuts: 0 },
      { id: 3, user: "carla", color: "#fbbf24", x: 420, y: 30, anchored: false, points: 0, cuts: 1 },
    ],
    fallen: [{ x: 300, y: 200, vx: 1, vy: 2, color: "#22d3ee", user: "duda", life: 0.5 }],
    leaders: [{ user: "carla", points: 0, y: 30 }],
    load: 3,
    maxKites: 26,
    totalFlights: 7,
    bestHeight: 260,
    restartIn: 0,
  },
  platformer: {
    world: { width: 960, height: 540 },
    player: { x: 120, y: 460, vx: 5, vy: 0, facingRight: true, onGround: true },
    platforms: [[0, 500, 960, 40], [150, 410, 160, 16]],
    coins: [{ x: 200, y: 380, collected: false }, { x: 300, y: 380, collected: true }],
    goal: { x: 900, y: 460, width: 16, height: 40 },
    coinRadius: 9,
    playerSize: [28, 40],
    score: 20,
    won: false,
  },
};

const MODULOS = {
  corrida: "../client/renderers/corrida.js",
  duelo: "../client/renderers/duelo.js",
  pipa: "../client/renderers/pipa_arena.js",
  platformer: "../client/renderers/platformer.js",
};

// O que o servidor manda em `welcome.game` (describe()): o renderer usa o catalogo.
const META = {
  type: "corrida",
  title: "Corrida na Live",
  catalog: {
    cars: [
      { id: "gol", name: "Gol", type: "carro", color: "#1f9d55", dark: "#0f6b3a", speed: 1 },
      { id: "uno", name: "Uno", type: "carro", color: "#e2e8f0", dark: "#94a3b8", speed: 0.94 },
      { id: "fusca", name: "Fusca", type: "carro", color: "#ef4444", dark: "#991b1b", speed: 0.92 },
    ],
    motos: [
      { id: "m160", name: "160", type: "moto", color: "#ef4444", dark: "#991b1b", speed: 1.04 },
      { id: "xre300", name: "XRE 300", type: "moto", color: "#84cc16", dark: "#3f6212", speed: 1.12 },
    ],
  },
};

let falhas = 0;
function check(nome, ok, detalhe = "") {
  console.log((ok ? "  OK  " : " FAIL ") + nome + (detalhe ? ` -> ${detalhe}` : ""));
  if (!ok) falhas += 1;
}

for (const [tipo, caminho] of Object.entries(MODULOS)) {
  let mod;
  try {
    mod = await import(new URL(caminho, import.meta.url));
  } catch (err) {
    check(`${tipo}: importa`, false, err.message);
    continue;
  }

  const ctx = mockContext();
  let renderer;
  try {
    renderer = mod.create(ctx, { canvas: ctx.canvas, els: {} });
  } catch (err) {
    check(`${tipo}: create()`, false, err.message);
    continue;
  }

  // 1. desenha com estado vazio (o que o usuario ve antes de alguem comentar)
  try {
    renderer.draw(ctx, null, {}, { time: 0, delta: 1 });
    check(`${tipo}: desenha sem estado (tela inicial)`, true);
  } catch (err) {
    check(`${tipo}: desenha sem estado`, false, err.message);
  }

  // 2. desenha com estado real, em 3 instantes
  try {
    for (const t of [0, 1.7, 9.3]) {
      renderer.draw(ctx, ESTADOS[tipo], { type: tipo, title: tipo }, { time: t, delta: 1 });
    }
    check(`${tipo}: desenha com estado`, true, `${stats.fillRect} fillRect, ${stats.fillText} textos`);
  } catch (err) {
    check(`${tipo}: desenha com estado`, false, `${err.message}`);
    continue;
  }

  // 3. hud nao pode explodir nem devolver NaN
  try {
    const hud = renderer.hud(ESTADOS[tipo], { title: tipo }) || {};
    const texto = `${hud.score || ""} ${hud.meta || ""}`;
    check(`${tipo}: hud ok`, !texto.includes("NaN") && !texto.includes("undefined"), texto.trim().slice(0, 70));
  } catch (err) {
    check(`${tipo}: hud`, false, err.message);
  }

  // 4. eventos nao podem explodir (quem quebrou a tela antes foi um onEvent)
  try {
    if (typeof renderer.onEvent === "function") {
      renderer.onEvent({ event: "gift", user: "x" }, [{ kind: "cut", message: "CORTOU 1 LINHA!", cuts: 1, side: "a", blocks: 2 }]);
    }
    renderer.onGameEvent({ kind: "winner", message: "VENCEU!", side: "a", user: "x", blocks: 3 });
    renderer.onGameEvent({ kind: "collapse", message: "DESABOU!", side: "a", blocks: 4 });
    renderer.onGameEvent({ kind: "land", message: "JUNTOU!", user: "x", color: "#fff" });
    renderer.onGameEvent({ kind: "restart", message: "NOVO!" });
    check(`${tipo}: eventos nao quebram`, true);
  } catch (err) {
    check(`${tipo}: eventos`, false, err.message);
  }

  // 5. o renderer precisa desenhar ALGO quando ha estado (tela vazia = bug)
  try {
    const antes = stats.fillRect;
    renderer.draw(ctx, ESTADOS[tipo], { type: tipo, title: tipo }, { time: 4.2, delta: 1 });
    const desenhou = stats.fillRect > antes;
    check(`${tipo}: desenhou pixels com estado`, desenhou, `${stats.fillRect - antes} fillRect`);
  } catch (err) {
    check(`${tipo}: desenhou pixels com estado`, false, err.message);
  }
}

// ------------------------------------------------- corrida: carros na tela e movimento
console.log("\n== corrida: os carros aparecem e andam ==");

{
  const { create } = await import(new URL(MODULOS.corrida, import.meta.url));

  const posicoesDeCarros = (estado) => {
    posicoes.length = 0;
    const ctx = mockContext();
    const r = create(ctx);
    r.draw(ctx, estado, META, { time: 2.0, delta: 1 });
    // cada carro faz translate(x, laneY) antes de desenhar o corpo
    return posicoes.filter((p) => p.tipo === "translate" && p.y >= 200).map((p) => Math.round(p.x));
  };

  const largada = {
    ...ESTADOS.corrida,
    phase: "countdown",
    countdown: 10,
    cars: ESTADOS.corrida.cars.map((c, i) => ({ ...c, dist: -30 - i * 105, kmh: 0, speed: 0 })),
  };
  const xs = posicoesDeCarros(largada);
  const naTela = xs.filter((x) => x >= 0 && x <= 960);
  check("pelo menos 3 carros caem na tela na largada", naTela.length >= 3, `x=[${xs}]`);

  const andando = posicoesDeCarros(ESTADOS.corrida);
  check("posicao dos carros muda com a distancia", JSON.stringify(xs) !== JSON.stringify(andando),
    `largada=[${xs}] vs corrida=[${andando}]`);
  check("nenhum carro nasce fora da pista (x >= -20)", xs.every((x) => x >= -20), `x=[${xs}]`);

  // faixas: no grid de largada cada carro tem que sair numa linha diferente
  posicoes.length = 0;
  create(mockContext()).draw(mockContext(), largada, META, { time: 1, delta: 1 });
  const linhas = [...new Set(posicoes.filter((p) => p.tipo === "translate" && p.y >= 200).map((p) => Math.round(p.y)))];
  check("carros ficam empilhados em faixas", linhas.length >= 4, `y=[${linhas}]`);

  // a contagem regressiva precisa aparecer na tela
  posicoes.length = 0;
  let textos = [];
  const ctxCount = {
    ...mockContext(),
    fillText: (t, x, y) => { textos.push({ t, x, y }); },
  };
  create(ctxCount).draw(ctxCount, largada, META, { time: 1, delta: 1 });
  check("mostra 'LARGADA EM 00:10'", textos.some((t) => String(t.t).includes("LARGADA EM 00:10")),
    textos.filter((t) => String(t.t).includes("LARGADA")).map((t) => t.t).join("|"));

  // a placa de cada carro mostra km/h
  posicoes.length = 0;
  textos = [];
  const ctxPlaca = { ...mockContext(), fillText: (t) => { textos.push(String(t)); } };
  create(ctxPlaca).draw(ctxPlaca, ESTADOS.corrida, META, { time: 1, delta: 1 });
  check("placa mostra km/h", textos.some((t) => /km\/h/.test(t)), textos.filter((t) => /km/.test(t)).slice(0, 3).join("|"));

  // o catalogo (painel esquerdo) precisa estar no describe do jogo
  check("catalogo tem carros e motos", META.catalog.cars.length > 0 && META.catalog.motos.length > 0,
    `${META.catalog.cars.length} carros, ${META.catalog.motos.length} motos`);
}

// ------------------------------------------------- resumo
console.log("\n" + (falhas === 0 ? "TODOS OS RENDERERS OK" : `FALHAS: ${falhas}`));
process.exit(falhas === 0 ? 0 : 1);