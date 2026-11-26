"""mpc_strut.py - MPC liniowy (mpc_linear.py) a opor wspornikow. 12.11 18:20, pytanie Julka "ile MPC ze wspornikiem".
Wariant A: MPC jak dotad (nie wie o wspornikach), ocena z oporem wspornikow (338 N/m zanurzenia z CFD).
Wariant B: MPC z oporem wspornikow w koszcie: D_strut ~ k * (eta + DEPTH - z) -> czlon liniowy -k * sum z_k.
Uzycie: python mpc_strut.py A|B W_Z [W_DU].  Wynik: MPC_STRUT_<wariant>_WZ<..>.json.  Wszystko "w modelu wirowym" (bazowym)."""
import json, sys, pickle, time
from pathlib import Path
import numpy as np
from scipy.optimize import minimize
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
import mpc_linear as ML
from godo_vortex_env import GodoVortexEnv

VAR = sys.argv[1]; ML.W_Z = float(sys.argv[2]); ML.W_DU = float(sys.argv[3]) if len(sys.argv) > 3 else 2000.0
env = GodoVortexEnv(random_phase=False)          # strut=True: D_tot = D + strut_k * max(sub, 0)
K = env.strut_k if VAR == "B" else 0.0


class StrutMPC(ML.LinMPC):
    def solve(s, x_s, th_h, v_h, z, v, t, beta, u_last):
        phis = -s.ome * (t + s.dt * np.arange(ML.H)) + beta
        f0, z0 = s.sim(x_s, th_h, v_h, z, v, np.zeros(ML.H), phis)
        M, p = s.m["M"], s.m["p"]; Fm = s.Fu.transpose(1, 0, 2)
        g = np.einsum("kjf,f->j", Fm, p) + 2 * np.einsum("kjf,fg,kg->j", Fm, M, f0) + 2 * ML.W_Z * s.Zu @ z0
        g = g - K * s.Zu.sum(axis=1)               # opor wspornikow: plat nizej (z mniejsze) = wiecej zanurzonego wspornika
        Hs = 2 * np.einsum("kjf,fg,kig->ji", Fm, M, Fm) + 2 * ML.W_Z * s.Zu @ s.Zu.T
        Dm = (np.eye(s.nb) - np.eye(s.nb, k=-1)); Hs += 2 * ML.W_DU * Dm.T @ Dm
        e0 = np.zeros(s.nb); e0[0] = u_last; g += -2 * ML.W_DU * Dm.T @ e0
        w, V = np.linalg.eigh(0.5 * (Hs + Hs.T)); w = np.maximum(w, 1e-3 * w.max()); Hs = (V * w) @ V.T
        x0 = np.full(s.nb, u_last) if s.Uprev is None else np.r_[s.Uprev[1:], s.Uprev[-1]]
        eta = s.amp * np.cos(phis); zmax = np.minimum(eta + ML.DEPTH - 2 * ML.C, 0.6); zmin = -0.6; ZT = s.Zu.T

        def fun(x):
            zz = z0 + ZT @ x; e1 = np.maximum(0, zz - zmax); e2 = np.maximum(0, zmin - zz)
            return 0.5 * x @ Hs @ x + g @ x + ML.W_S * (e1 @ e1 + e2 @ e2), Hs @ x + g + 2 * ML.W_S * ZT.T @ (e1 - e2)
        res = minimize(fun, x0, jac=True, method="L-BFGS-B", bounds=[(-ML.THM, ML.THM)] * s.nb)
        s.Uprev = res.x
        return res.x[0]


mdl = pickle.loads((HERE / "MPC_ID_MODEL.pkl").read_bytes())
mpc = StrutMPC(mdl, ome=env.plant.ome)
out = dict(wariant=VAR, W_Z=ML.W_Z, W_DU=ML.W_DU, strut_k_N_per_m=env.strut_k, D_cw_W=env.D_cw * 12.35, D_cw_tot_W=env.D_cw_tot * 12.35, fazy=[])
for ph in (0.0, np.pi / 2, np.pi, 1.5 * np.pi):
    R, rows, term = ML.mpc_episode(env, mpc, ph)
    if ph == 0.0 and VAR == "A" and ML.W_Z == 2.0:   # epizod do panelu "Efekty sterowania" (stary MPC_EP_phase0.json liczony starym modelem oporu CD = const)
        src = HERE / "MPC_EP_phase0.json"
        if src.exists() and not (HERE / "MPC_EP_phase0_v1_cdconst.json").exists(): src.replace(HERE / "MPC_EP_phase0_v1_cdconst.json")
        (HERE / "MPC_EP_phase0.json").write_text(json.dumps(dict(term=bool(term), rows=[{k: float(v) for k, v in r.items()} for r in rows])))
    n = len(rows); h = slice(max(0, n - 4 * 194), n); a = lambda k: np.array([x[k] for x in rows])[h]
    r = dict(term=bool(term), plat_pct=100 * (a("D").mean() / env.D_cw - 1), tot_pct=100 * (a("D_tot").mean() / env.D_cw_tot - 1),
             z=[float(a("z").min()), float(a("z").max())], acc=float(np.sqrt((a("acc") ** 2).mean())), th=[float(a("theta_deg").min()), float(a("theta_deg").max())])
    out["fazy"].append(r); print(VAR, ML.W_Z, f"{ph:.2f}", {k: (round(v, 2) if isinstance(v, float) else v) for k, v in r.items()}, flush=True)
ok = [r for r in out["fazy"] if not r["term"]]
if ok: out["srednio"] = dict(przezyl=f"{len(ok)}/4", plat_pct=float(np.mean([r["plat_pct"] for r in ok])), tot_pct=float(np.mean([r["tot_pct"] for r in ok])),
                             z_min=min(r["z"][0] for r in ok), acc=float(np.mean([r["acc"] for r in ok])))
(HERE / f"MPC_STRUT_{VAR}_WZ{ML.W_Z:g}.json").write_text(json.dumps(out, indent=1))
print("SREDNIO", VAR, ML.W_Z, out.get("srednio"), flush=True)
