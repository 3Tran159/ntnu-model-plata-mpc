"""Ile daje uklad czujnikow fali przed platem: R2 estymaty pionowej predkosci wody w c/4 (wf) teraz i 0,25-1,5 s naprzod.
JONSWAP Hs 1,5 m, Tp 5 s; liniowy estymator (ridge) z 1 s historii kazdego czujnika; dopasowanie na 6 realizacjach, test na innej."""
import json, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
import mpc_irr as M

CONF = {"sonda 0 m": [0.0], "1,5 m": [0.0, 1.5], "3 m": [0.0, 3.0], "1,5 + 3 m": [0.0, 1.5, 3.0], "6 m": [0.0, 6.0], "1,5 + 3 + 6 m": [0.0, 1.5, 3.0, 6.0], "10 m": [0.0, 10.0]}
D_ALL = sorted({d for v in CONF.values() for d in v})
TAUS = (0, 25, 50, 100, 150)
data = {s: M.wave_series(s, 400.0 if s < 300 else 200.0, D_ALL) for s in list(range(200, 206)) + [300]}
out = {}
for name, ds in CONF.items():
    M.MODES[name] = ds
    X, Y = [], []
    for s in range(200, 206):
        wf, et = data[s]
        for k in range(5 * M.NH, len(wf) - 160, 7):
            X.append(M.regs({d: et[d][k - 5 * M.NH + 1:k + 1] for d in ds}, name)); Y.append([wf[k + t] for t in TAUS])
    X = np.array(X); lam = 1e-3 * np.trace(X.T @ X) / X.shape[1]
    B = np.linalg.solve(X.T @ X + lam * np.eye(X.shape[1]), X.T @ np.array(Y))
    wf, et = data[300]; Xt, Yt = [], []
    for k in range(5 * M.NH, len(wf) - 160, 11):
        Xt.append(M.regs({d: et[d][k - 5 * M.NH + 1:k + 1] for d in ds}, name)); Yt.append([wf[k + t] for t in TAUS])
    P = np.array(Xt) @ B; Yt = np.array(Yt)
    out[name] = {f"{t*0.01:.2f} s": round(float(1 - np.var(Yt[:, i] - P[:, i]) / np.var(Yt[:, i])), 3) for i, t in enumerate(TAUS)}
    print(f"{name:14s} " + "  ".join(f"{k}: {v:.3f}" for k, v in out[name].items()), flush=True)
(HERE / "PRED_SENSORS.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
