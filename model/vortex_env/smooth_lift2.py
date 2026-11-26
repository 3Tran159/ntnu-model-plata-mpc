"""smooth_lift.py - 13.11 rano, pytanie Julka: czy "gladki" wodolot (wygladzone piki sily nosnej) wygrywa na oporze?
Sterownik "stala sila nosna": kat = trym - (w_wody_na_glebokosci - v_plata)/U  (kasuje zmiane kata natarcia od fali i nurzania)
+ wolny PID1 Godo na wysokosc. Porownanie z PID1, PID3, TD3_GODO w modelu wirowym (bazowym), ta sama fala, 4 fazy.
Wynik: SMOOTH_LIFT.json.  Wszystko "w modelu wirowym"."""
import json, sys, math
from pathlib import Path
import numpy as np, torch
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
import godo_vortex_env as G
from godo_vortex_env import GodoVortexEnv, pid_policy, rollout
from vortex_plant import DEPTH
torch.set_num_threads(1)
env = GodoVortexEnv(random_phase=False); p = env.plant; PH = (0.0, np.pi / 2, np.pi, 1.5 * np.pi)


VW = 1.0
def smooth(gain):
    act_pid, st = pid_policy(2.01, 0.196)
    def act(e, o=None):
        a_pid = act_pid(e, o)[0] * G.TH_MAX_DEG
        w = p.w_surface() * math.exp(-p.k * DEPTH)            # pionowa predkosc wody na glebokosci plata (fala liniowa)
        corr = math.degrees((w - VW * p.v) / G.U) * gain           # zmiana kata natarcia od fali i nurzania
        return np.array([np.clip((a_pid - corr) / G.TH_MAX_DEG, -1, 1)])
    return act, st


def summ(runs):
    out = []
    for R, rows, term in runs:
        if term: out.append(dict(term=True)); continue
        h = rows[-776:]; a = lambda k: np.array([x[k] for x in h])
        out.append(dict(term=False, plat=100 * (a("D").mean() / env.D_cw - 1), acc=float(np.sqrt((a("acc") ** 2).mean())),
                        CL_std=float(a("CL").std()), CL_mean=float(a("CL").mean()), z_p2p=float(np.ptp(a("z"))), th=[float(a("theta_deg").min()), float(a("theta_deg").max())]))
    ok = [r for r in out if not r["term"]]
    return dict(przezyl=f"{len(ok)}/{len(out)}", **({k: float(np.mean([r[k] for r in ok])) for k in ("plat", "acc", "CL_std", "CL_mean", "z_p2p")} if ok else {}),
                th=[min(r["th"][0] for r in ok), max(r["th"][1] for r in ok)] if ok else None)


res = {}
G.TH_REF_DEG = 3.22
for name, kp, ki in (("PID1 Godo", 2.01, 0.196), ("PID3 Godo", 22.3, 7.25)):
    runs = []
    for ph in PH:
        act, st = pid_policy(kp, ki); runs.append(rollout(env, act, ph, st))
    res[name] = summ(runs)
for g in (0.5, 1.0):
    runs = []
    for ph in PH:
        act, st = smooth(g); runs.append(rollout(env, act, ph, st))
    res[f"gladka sila nosna (kasowanie {int(100*g)} %)"] = summ(runs)
sys.argv = ["x", "td3", "TD3_GODO"]; import train_rl
ag = train_rl.Agent(); ag.actor.load_state_dict(torch.load(HERE / "runs" / "TD3_GODO" / "best_actor.pt", weights_only=False))
res["TD3_GODO"] = summ([rollout(env, lambda e, o: ag.act(o, True), ph) for ph in PH])
(HERE / "SMOOTH_LIFT.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
for k, v in res.items():
    print(f"{k:38s} {v['przezyl']} plat {v.get('plat', float('nan')):+6.1f} %  z'' {v.get('acc', float('nan')):.2f}  CL {v.get('CL_mean', 0):.2f}+-{v.get('CL_std', 0):.3f}  z p2p {v.get('z_p2p', 0):.2f}  kat {v.get('th')}", flush=True)


# 13.11 08:25: tylko fala (bez kasowania tlumienia nurzania), rozne wzmocnienia
for g in (0.5, 1.0, 1.5):
    VW = 0.0; runs = []
    for ph in PH:
        act, st = smooth(g); runs.append(rollout(env, act, ph, st))
    v = summ(runs); res[f"tylko fala {int(100*g)} %"] = v
    print(f"tylko fala {int(100*g)} %: {v['przezyl']} plat {v.get('plat', float('nan')):+6.1f} %  z'' {v.get('acc', float('nan')):.2f}  CL std {v.get('CL_std', 0):.3f}  z p2p {v.get('z_p2p', 0):.2f}  kat {v.get('th')}", flush=True)
(HERE / "SMOOTH_LIFT.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")

