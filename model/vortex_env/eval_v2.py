"""eval_v2.py - ocena regulatorow na modelu v2 (biegunowa CD(CL) z URANS + opor wspornikow), fala regularna, 4 fazy.
Opor podawany: sam plat (porownywalny z URANS) i plat + wsporniki (to, co widzi nagroda), wzgledem wody spokojnej PID2.
Wynik: EVAL_V2.json.  Wszystko "w modelu wirowym"."""
import json, sys, pickle
from pathlib import Path
import numpy as np, torch
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
import godo_vortex_env as G
from godo_vortex_env import GodoVortexEnv, pid_policy, rollout, C
torch.set_num_threads(1)
env = GodoVortexEnv(random_phase=False)
PH = (0.0, np.pi / 2, np.pi, 1.5 * np.pi)
out = dict(D_cw_W=env.D_cw * G.U, D_cw_tot_W=env.D_cw_tot * G.U, wyniki={})


def summ(name, runs):
    res = []
    for rows, term in runs:
        if term: res.append(dict(term=True, t=len(rows) * 0.01)); continue
        h = rows[-776:]; a = lambda k: np.array([x[k] for x in h])
        res.append(dict(term=False, P_plat=float(a("P_drag_W").mean()), P_tot=float(a("P_tot_W").mean()), z=[float(a("z").min()), float(a("z").max())],
                        sub_min_c=float(a("sub").min() / C), acc=float(np.sqrt((a("acc") ** 2).mean())), th=[float(a("theta_deg").min()), float(a("theta_deg").max())]))
    ok = [r for r in res if not r["term"]]
    s = dict(przezyl=f"{len(ok)}/{len(res)}")
    if ok:
        s.update(P_plat=np.mean([r["P_plat"] for r in ok]), P_tot=np.mean([r["P_tot"] for r in ok]), z=[min(r["z"][0] for r in ok), max(r["z"][1] for r in ok)],
                 sub_min_c=min(r["sub_min_c"] for r in ok), acc=np.mean([r["acc"] for r in ok]), th=[min(r["th"][0] for r in ok), max(r["th"][1] for r in ok)])
        s["plat_vs_calm_pct"] = 100 * (s["P_plat"] / out["D_cw_W"] - 1); s["tot_vs_calm_pct"] = 100 * (s["P_tot"] / out["D_cw_tot_W"] - 1)
    out["wyniki"][name] = s
    print(f"{name:22s} przezyl {s['przezyl']}" + (f" | plat {s['P_plat']:.1f} W ({s['plat_vs_calm_pct']:+.0f}%) | z wspornikami {s['P_tot']:.1f} W ({s['tot_vs_calm_pct']:+.0f}%) | z {s['z'][0]:.2f}..{s['z'][1]:.2f} | zanurz. min {s['sub_min_c']:.2f}c | z̈ {s['acc']:.2f} | kat {s['th'][0]:.1f}..{s['th'][1]:.1f}" if ok else ""), flush=True)
    (HERE / "EVAL_V2.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")


for name, kp, ki, tr in [("PID1 Godø", 2.01, 0.196, 3.22), ("PID2 Godø", 6.63, 1.18, 3.22), ("BASE2 (Kp 10)", 10, 2, 3.5), ("PID3 Godø", 22.3, 7.25, 3.22)]:
    G.TH_REF_DEG = tr; runs = []
    for ph in PH:
        act, st = pid_policy(kp, ki); R, rows, term = rollout(env, act, ph, st); runs.append((rows, term))
    G.TH_REF_DEG = 3.22; summ(name, runs)

import importlib
for tag, alg in (("TD3_GODO", "td3"), ("SAC_B", "sac"), ("SAC_C", "sac"), ("TD3_C", "td3")):
    f = HERE / "runs" / tag / "best_actor.pt"
    if not f.exists(): continue
    sys.argv = ["x", alg, tag]; import train_rl; importlib.reload(train_rl)
    ag = train_rl.Agent(); ag.actor.load_state_dict(torch.load(f, weights_only=False))
    runs = [rollout(env, lambda e, o: ag.act(o, True), ph)[1:] for ph in PH]
    summ(f"{tag} (nagroda {'v2' if tag.endswith('_C') else 'v1'})", runs)
