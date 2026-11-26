"""dryf_calm.py - koordynator 14.11 (T2): czy dryf oporu URANS w wodzie spokojnej to narastanie fali od plata?
Dopasowanie P(t) = P_inf - C/sqrt(t) (asymptotyka narastania oporu falowego po starcie) i liniowe, okno t >= 2 s, srednie 0,25 s."""
import csv, json
from pathlib import Path
import numpy as np
RUNS = Path(r"T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR\overset_runs"); out = {}
for tag in ("OVS_CALM_PID2", "OVS_CALM_Z-0.3", "OVS_CALM_Z-0.6", "OVS_CALM_90"):
    rd = csv.reader(open(RUNS / tag / "history.csv")); h = next(rd); R = {}
    for r in rd:
        if len(r) == len(h): R[r[0]] = (float(r[0]), float(r[h.index("P_drag_W")]))
    A = np.array(sorted(R.values())); t, P = A[:, 0], A[:, 1]
    edges = np.arange(2.0, t[-1] + 1e-9, 0.25); tm, Pm = [], []
    for a, b in zip(edges[:-1], edges[1:]):
        m = (t >= a) & (t < b)
        if m.any(): tm.append((a + b) / 2); Pm.append(P[m].mean())
    tm, Pm = np.array(tm), np.array(Pm)
    X = np.c_[np.ones_like(tm), -1 / np.sqrt(tm)]; c, res, *_ = np.linalg.lstsq(X, Pm, rcond=None)
    lin = np.polyfit(tm, Pm, 1)
    out[tag] = dict(t_end=round(float(t[-1]), 2), P_last1s=round(float(P[t > t[-1] - 1].mean()), 2), P_inf=round(float(c[0]), 2), C=round(float(c[1]), 2),
                    fit_rms=round(float(np.sqrt(np.mean((X @ c - Pm) ** 2))), 3), slope_W_per_s=round(float(lin[0]), 3),
                    P_2_4=round(float(Pm[(tm >= 2) & (tm < 4)].mean()), 2), P_4_6=round(float(Pm[(tm >= 4) & (tm < 6)].mean()), 2) if t[-1] > 5 else None,
                    P_6_8=round(float(Pm[(tm >= 6)].mean()), 2) if t[-1] > 7 else None)
print(json.dumps(out))
