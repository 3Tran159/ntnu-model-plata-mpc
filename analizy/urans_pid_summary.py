"""urans_pid_summary.py - URANS overset: ostatnie 3 okresy spotkania (Te 1.9368 s), moc oporu vs woda spokojna 61.1 W/pasek."""
import csv, json, sys
import numpy as np
from pathlib import Path
O = Path(r"T:\NTNU_GODO_CONTROL_20261109\70_godo_case\overset_runs")
TE, DCW = 1.9368, 61.0999
out = {}
for run in ["OVS_PID_BASE2", "OVS_PID1_GODO", "OVS_PID3_GODO", "OVS_PID_SINE_A2", "OVS_PID_PRBS1"]:
    f = O / run / "history.csv"
    if not f.exists(): continue
    R = list(csv.DictReader(open(f)))
    c = lambda k: np.array([float(r[k]) for r in R])
    t = c("time_s"); m = t >= t[-1] - 3 * TE
    P = c("P_drag_W")[m]; z = c("z_m")[m]; v = c("v_m_s")[m]; th = c("theta_deg")[m]; tt = t[m]
    acc = np.gradient(v, tt)
    Pa = c("P_act_W")[m]
    out[run] = dict(P_drag_W=round(P.mean(), 1), vs_calm_pct=round(100 * (P.mean() / DCW - 1), 1),
                    z_min_m=round(z.min(), 3), z_max_m=round(z.max(), 3), acc_rms=round(float(np.sqrt(np.mean((acc - acc.mean()) ** 2))), 2),
                    theta_deg=[round(th.min(), 2), round(th.max(), 2)], P_act_mean_W=round(Pa.mean(), 2), t_end=round(t[-1], 3))
    print(run, out[run])
json.dump(out, open(Path(__file__).with_name("URANS_PID_SUMMARY.json"), "w"), indent=1)
