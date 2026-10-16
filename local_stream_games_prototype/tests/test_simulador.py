"""Simulador --auto contra o servidor: a live ficticia tem que gerar uma corrida."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))          # _harness
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # projeto

from _harness import PORT, PROJECT, check, finish  # noqa: E402

import asyncio
import json
import os
import subprocess
import time
import urllib.request

env = {**os.environ, "PORT": PORT}
server = subprocess.Popen([sys.executable, "server/server.py"], cwd=str(PROJECT), env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
time.sleep(2.5)

sim = subprocess.Popen([sys.executable, "simulator/simulator.py", "--auto"], cwd=str(PROJECT), env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

async def observe(seconds):
    import websockets

    seen = {"cars": 0, "maxSpeed": 0, "oils": 0, "joins": 0, "gifts": 0, "likes": 0, "tiktok": None, "states": 0}
    async with websockets.connect(f"ws://127.0.0.1:{PORT}") as ws:
        deadline = time.time() + seconds
        while time.time() < deadline:
            try:
                payload = json.loads(await asyncio.wait_for(ws.recv(), 3))
            except asyncio.TimeoutError:
                break
            if payload.get("type") == "state":
                state = payload["state"]
                seen["states"] += 1
                seen["cars"] = max(seen["cars"], len(state["cars"]))
                seen["oils"] = max(seen["oils"], len(state["oils"]))
                seen["maxSpeed"] = max([seen["maxSpeed"]] + [c["speed"] for c in state["cars"]])
            elif payload.get("type") == "event":
                kind = payload["event"]["event"]
                seen[kind + "s" if kind in ("like", "gift") else "joins"] = seen.get(
                    kind + "s" if kind in ("like", "gift") else "joins", 0) + 1
            elif payload.get("type") == "status":
                tiktok = (payload.get("sources") or {}).get("simulator") or {}
                if tiktok.get("connected"):
                    seen["tiktok"] = tiktok
    return seen

result = asyncio.run(observe(12))
sim.terminate()
try:
    sim_log = sim.communicate(timeout=6)[0]
except subprocess.TimeoutExpired:
    sim.kill()
    sim_log = sim.communicate()[0]

try:
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=5) as resp:
        health = json.loads(resp.read().decode())
    check("servidor vivo", health["ok"] and health["game"] == "corrida", json.dumps(health))
except Exception as err:  # noqa: BLE001
    check("servidor vivo", False, str(err))

check("simulador rodou sem erro", "Traceback" not in (sim_log or ""), (sim_log or "")[-200:] if "Traceback" in (sim_log or "") else "")
check("live ficticia criou varios carros", result["cars"] >= 3, f"{result['cars']} carros")
check("presentes chegaram (nitro/oleo)", result["gifts"] >= 1, f"{result['gifts']} presentes")
check("efeito de nitro acelerou alguem", result["maxSpeed"] > 4.5, f"velocidade max={result['maxSpeed']}")
check("HUD recebeu o status do simulador", bool(result["tiktok"]),
      json.dumps(result["tiktok"], ensure_ascii=False) if result["tiktok"] else "sem status")
check("estado continuou chegando", result["states"] > 100, f"{result['states']} snapshots")

server.terminate()
try:
    log = server.communicate(timeout=6)[0]
except subprocess.TimeoutExpired:
    server.kill()
    log = server.communicate()[0]

errors = [line for line in (log or "").splitlines() if "ERROR" in line or "Traceback" in line]
print("\n--- ultimas linhas do servidor ---")
print("\n".join((log or "").splitlines()[-8:]))
print("\n--- erros no servidor ---")
print("\n".join(errors) if errors else "(nenhum)")
finish()
