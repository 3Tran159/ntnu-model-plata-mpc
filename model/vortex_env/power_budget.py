"""Bilans mocy w modelu wirowym (faza 0, ostatnie 4 okresy): opor, moc na wale obrotu (moment c/4 NIEZWALIDOWANY), moc w nurzaniu.
Porownanie z URANS BASE2 (P_act = 0,26 W/pasek)."""
import sys, json, pickle
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
import godo_vortex_env as G
from godo_vortex_env import GodoVortexEnv, pid_policy, rollout
import mpc_linear as M
from vortex_plant import MASS, SPAN

env = GodoVortexEnv(random_phase=False)
out = {}


def summ(name, rows):
    h = rows[-776:]; a = lambda k: np.array([x[k] for x in h])
    acc, z = a("acc"), a("z")
    out[name] = dict(P_drag_W=float(a("P_drag_W").mean()), P_shaft_mean_W=float(a("P_shaft").mean()), P_act_pos_W=float(a("P_act").mean()),
                     P_drag_calm_W=float(env.D_cw * G.U))
    print(f"{name:12s} opor {out[name]['P_drag_W']:7.1f} W | wal obrotu: srednia {out[name]['P_shaft_mean_W']:+.2f} W, tylko dodatnia {out[name]['P_act_pos_W']:.2f} W | woda spokojna {out[name]['P_drag_calm_W']:.1f} W", flush=True)


G.TH_REF_DEG = 3.5; act, st = pid_policy(10, 2); summ("BASE2", rollout(env, act, 0.0, st)[1]); G.TH_REF_DEG = 3.22
act, st = pid_policy(); summ("PID2", rollout(env, act, 0.0, st)[1])
M.W_Z = 2.0; mdl = pickle.loads((HERE / "MPC_ID_MODEL.pkl").read_bytes()); mpc = M.LinMPC(mdl, ome=env.plant.ome)
summ("MPC", M.mpc_episode(env, mpc, 0.0)[1])
(HERE / "POWER_BUDGET.json").write_text(json.dumps(out, indent=1))
