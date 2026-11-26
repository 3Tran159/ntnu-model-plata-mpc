"""robust_test.py - krok 8: odpornosc polityki w modelu wirowym v2 (fala regularna, 4 fazy na wariant).
Zaburzenia: CL x0,85 / x1,15, opor x0,8 / x1,2, fala x0,9 / x1,1, opoznienie obserwacji 1 takt (10 ms).
usage: python robust_test.py TAG [td3|sac]   ->  runs/TAG/ROBUST.json"""
import sys, json
from pathlib import Path
import numpy as np, torch
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
from godo_vortex_env import GodoVortexEnv, rollout, C, U
torch.set_num_threads(1)
tag = sys.argv[1]; alg = sys.argv[2] if len(sys.argv) > 2 else ("sac" if "SAC" in tag else "td3")
sys.argv = ["x", alg, tag]; import train_rl
ag = train_rl.Agent(); ag.actor.load_state_dict(torch.load(HERE / "runs" / tag / "best_actor.pt", weights_only=False))
CASES = {"nominal": {}, "CL x0.85": dict(cl_scale=0.85), "CL x1.15": dict(cl_scale=1.15), "opor x0.8": dict(cd_scale=0.8), "opor x1.2": dict(cd_scale=1.2),
         "fala x0.9": dict(wave_scale=0.9), "fala x1.1": dict(wave_scale=1.1), "opoznienie 1 takt": dict(obs_delay=1)}
out = {}
for name, kw in CASES.items():
    env = GodoVortexEnv(random_phase=False, **kw); res = []
    for ph in (0.0, np.pi / 2, np.pi, 1.5 * np.pi):
        R, rows, term = rollout(env, lambda e, o: ag.act(o, True), ph)
        if term: res.append(dict(term=True, t=len(rows) * 0.01)); continue
        h = rows[-776:]; a = lambda k: np.array([x[k] for x in h])
        res.append(dict(term=False, tot_pct=100 * (a("D_tot").mean() / env.D_cw_tot - 1), plat_pct=100 * (a("D").mean() / env.D_cw - 1),
                        sub_min_c=float(a("sub").min() / C), z_min=float(a("z").min()), acc=float(np.sqrt((a("acc") ** 2).mean()))))
    ok = [r for r in res if not r["term"]]
    out[name] = dict(przezyl=f"{len(ok)}/4", tot_pct=round(np.mean([r["tot_pct"] for r in ok]), 1) if ok else None,
                     plat_pct=round(np.mean([r["plat_pct"] for r in ok]), 1) if ok else None, z_min=round(min(r["z_min"] for r in ok), 2) if ok else None,
                     sub_min_c=round(min(r["sub_min_c"] for r in ok), 2) if ok else None, acc=round(np.mean([r["acc"] for r in ok]), 2) if ok else None)
    print(f"{tag} {name:18s}: {out[name]}", flush=True)
(HERE / "runs" / tag / "ROBUST.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
