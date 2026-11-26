"""20.11 22:10: skladowe fali nieregularnej S1 (Hs 1,5 m, Tp 5 s, JONSWAP 3,3) - TA SAMA realizacja co w modelu (mpc_komfort.plant("S1", 100) = seed 0 serii cel_widmo).
Obciecie do pasma, ktore domena overset przenosi (okres 2-7,5 s): reszta energii < 1 %. Zapis: S1_SKLADOWE.json (a [m], w0 [rad/s], k [1/m], eps [rad], T [s], lambda [m])."""
import sys, json, numpy as np
sys.path.insert(0, r"T:\NTNU_GODO_CONTROL_20261109\95_WARSZTAT_KOORDYNATOR\warsztat\20261117_mpc_komfort")
import os; os.environ["MPC_W_A"] = "1"
import mpc_komfort as MK
p, trim = MK.plant("S1", 100); I = p.irr
a, w, k, eps = I["a"], I["w"], I["k"], I["eps"]; T = 2 * np.pi / w; lam = 2 * np.pi / k
keep = (T >= 2.0) & (T <= 7.5)
E = (a ** 2 / 2); out = dict(Hs_pelne=float(4 * np.sqrt(E.sum())), Hs_obciete=float(4 * np.sqrt(E[keep].sum())), udzial_energii=float(E[keep].sum() / E.sum()), n=int(keep.sum()), trim_deg=float(trim),
           skladowe=[dict(a=float(a[i]), w0=float(w[i]), k=float(k[i]), eps=float(eps[i]), T=float(T[i]), lam=float(lam[i])) for i in np.where(keep)[0]])
open(r"T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR\overset\WAVE_S1\S1_SKLADOWE.json", "w").write(json.dumps(out, indent=1))
print({k_: v for k_, v in out.items() if k_ != "skladowe"}, "T", round(T[keep].min(), 2), round(T[keep].max(), 2), "a max", round(a.max(), 3))
