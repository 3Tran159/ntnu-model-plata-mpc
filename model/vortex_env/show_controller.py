"""show_controller.py - jak wyglada wytrenowany sterownik TD3_GODO vs PID1 (Godo), w modelu wirowym (bazowym).
Zapisuje SHOW_CONTROLLER.json: przebiegi czasowe z 2 ostatnich okresow (fala przy LE, z, kat, opor plata)
oraz mape polityki: kat [deg] w funkcji fazy fali i wysokosci z (v = 0)."""
import json, sys, importlib
from pathlib import Path
import numpy as np, torch
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
import godo_vortex_env as G
from godo_vortex_env import GodoVortexEnv, pid_policy, rollout, OBS_SCALE
torch.set_num_threads(1)
env = GodoVortexEnv(random_phase=False)
out = dict(D_cw_W=env.D_cw * G.U, TH_MAX_DEG=G.TH_MAX_DEG)

def dump(rows):
    print("keys:", list(rows[0].keys()))
    h = rows[-2 * 194:][::2]
    keys = [k for k in ("t", "z", "theta_deg", "P_drag_W", "eta_LE", "eta", "sub", "acc") if k in rows[0]]
    return {k: [round(float(r[k]), 4) for r in h] for k in keys}

act, st = pid_policy(2.01, 0.196); G.TH_REF_DEG = 3.22
R, rows, term = rollout(env, act, 0.0, st); out["PID1"] = dump(rows); out["PID1"]["term"] = bool(term)

sys.argv = ["x", "td3", "TD3_GODO"]; import train_rl; importlib.reload(train_rl)
ag = train_rl.Agent(); ag.actor.load_state_dict(torch.load(HERE / "runs" / "TD3_GODO" / "best_actor.pt", weights_only=False))
R, rows, term = rollout(env, lambda e, o: ag.act(o, True), 0.0); out["TD3"] = dump(rows); out["TD3"]["term"] = bool(term)

p = env.plant; ph = np.linspace(0, 2 * np.pi, 37); zz = np.linspace(-0.75, 0.75, 31)
P, Zg = np.meshgrid(ph, zz); eta = p.a * np.cos(P); w = p.a * 2 * np.pi / 5.0 * np.sin(P)
trim = 3.22 / G.TH_MAX_DEG
O = np.stack([Zg, 0 * Zg, eta, w, 0 * Zg + trim], -1).reshape(-1, 5) / OBS_SCALE
with torch.no_grad():
    A = ag.actor(torch.as_tensor(O, dtype=torch.float32)).numpy().reshape(Zg.shape) * G.TH_MAX_DEG
out["map"] = dict(phase_deg=np.degrees(ph).round(1).tolist(), z=zz.round(3).tolist(), theta_deg=A.round(2).tolist(), wave_amp_m=float(p.a))
n = sum(x.numel() for x in ag.actor.parameters()); out["n_weights"] = int(n)
(HERE / "SHOW_CONTROLLER.json").write_text(json.dumps(out), encoding="utf-8")
print("ok, weights:", n, "PID1 term", out["PID1"]["term"], "TD3 term", out["TD3"]["term"])
