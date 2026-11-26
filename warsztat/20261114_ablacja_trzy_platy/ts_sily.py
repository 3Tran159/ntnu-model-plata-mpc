# Przebiegi czasowe sil na trzech wspornikach (z interakcja), do wykresu "lift w czasie na wspornik".
import sys, json, inspect
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
import trzy_platy_interakcja as TI
src = inspect.getsource(TI.simulate).replace("    return dict(v=v", "    TS.append(a)\n    return dict(v=v")
ns = dict(vars(TI)); ns["TS"] = TS = []; exec(src, ns); sim = ns["simulate"]


def job(a):
    v, sea = a; TS.clear(); r = sim(v, "int", 15.0, sea, 0, 130.0, 10.0); A = TS[0]
    t, L, P, th = A[:, 0], A[:, 1:4], A[:, 4:7], A[:, 7:10]
    L0 = TI.FP.MASS * TI.G_ - TI.BUOY
    s = slice(None, None, 5)                                           # 20 Hz
    return dict(v=v, sea=sea, L0=L0, P_mean=r["P_mean"], acc_heave=r["acc_heave"], acc_bow=r["acc_bow"],
                L_std_pct=[float(100 * L[:, j].std() / L0) for j in range(3)], L_max_pct=[float(100 * (L[:, j].max() / L0 - 1)) for j in range(3)],
                L_min_pct=[float(100 * (L[:, j].min() / L0 - 1)) for j in range(3)], F_sum_std_pct=float(100 * (L.sum(1)).std() / (3 * L0)),
                ts=dict(t=np.round(t[s], 2).tolist(), L=[np.round(L[s, j] / L0, 4).tolist() for j in range(3)], th=[np.round(th[s, j], 3).tolist() for j in range(3)]))


if __name__ == "__main__":
    from multiprocessing import Pool
    J = [("G1_lim30", "S1"), ("K0", "S1"), ("G1_lim30", "S2"), ("K0", "S2")]
    with Pool(4) as p: R = p.map(job, J)
    (HERE / "TS_SILY.json").write_text(json.dumps(R))
    for r in R: print(r["v"], r["sea"], {k: (np.round(r[k], 1).tolist() if isinstance(r[k], list) else round(r[k], 3)) for k in ("L_std_pct", "L_max_pct", "L_min_pct", "F_sum_std_pct", "acc_heave", "acc_bow")})
