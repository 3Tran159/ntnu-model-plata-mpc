"""FIXED_LONG vs MAP_FF vs MAP_FF180: same start state, same window (last 3 encounter periods), per-cycle repeatability.
Writes 30_runs/COMPARE_MAP3.json and prints a table.
Power per 0.02 m span: drag U*Fx; actuator demand max(0, -Mh * d(delta)/dt) (sign checked: Mh about -z, delta + = TE down).
"""
import json, math, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
from analyze_case import load, harmonic, TE

RUNS = Path(r"T:\NTNU_GODO_CONTROL_20261109\30_runs")
U = 18.0
cases = {n: sorted(RUNS.glob(n + "_2026*"))[-1] for n in ("FIXED_LONG", "MAP_FF", "MAP_FF180")}
H = {n: load(p) for n, p in cases.items()}
t_end = min(float(h["time_s"][-1]) for h in H.values())
t0 = t_end - 3 * TE
out = {"window_s": [t0, t_end], "cases": {k: str(v) for k, v in cases.items()}}


def stats(h):
    m = (h["time_s"] > t0 + 1e-9) & (h["time_s"] <= t_end + 1e-9)
    t = h["time_s"][m]
    dt = np.mean(np.diff(t))
    ddot = np.gradient(np.radians(h["meas_deg"][m]), dt)
    p_act = np.maximum(0, -h["Mh_Nm"][m] * ddot)
    r = {"CL_mean": h["CL"][m].mean(), "CD_mean": h["CD"][m].mean(), "Fx_mean_N": h["Fx_N"][m].mean(),
         "P_drag_W": U * h["Fx_N"][m].mean(), "P_act_W": p_act.mean(),
         "P_total_W": U * h["Fx_N"][m].mean() + p_act.mean(),
         "delta_amp_deg": 0.5 * (h["meas_deg"][m].max() - h["meas_deg"][m].min()),
         "pFlap_min_Pa": h["pFlapAbsMin_Pa"][m].min()}
    w = 2 * math.pi / TE
    for k in ("CL", "CD", "eta_m3_m"):
        x = h[k][m] - h[k][m].mean()
        z = 2 * np.mean(x * np.exp(-1j * w * t))
        r[k + "_h1_amp"], r[k + "_h1_phase_deg"] = abs(z), math.degrees(np.angle(z))
    r["CL_phase_minus_eta_deg"] = ((r["CL_h1_phase_deg"] - r["eta_m3_m_h1_phase_deg"] + 180) % 360) - 180
    cyc = []
    for i in range(3):
        mm = (h["time_s"] > t0 + i * TE + 1e-9) & (h["time_s"] <= t0 + (i + 1) * TE + 1e-9)
        cyc.append([h["CL"][mm].mean(), h["CD"][mm].mean()])
    cyc = np.array(cyc)
    r["cycle_CD"] = cyc[:, 1].tolist(); r["cycle_CL"] = cyc[:, 0].tolist()
    r["CD_cycle_spread_pct"] = 100 * (cyc[:, 1].max() - cyc[:, 1].min()) / cyc[:, 1].mean()
    return r


S = {n: stats(h) for n, h in H.items()}
F = S["FIXED_LONG"]
for n, r in S.items():
    r["dCD_vs_FIXED_pct"] = 100 * (r["CD_mean"] / F["CD_mean"] - 1)
    r["dCL_vs_FIXED_pct"] = 100 * (r["CL_mean"] / F["CL_mean"] - 1)
    r["dP_total_vs_FIXED_pct"] = 100 * (r["P_total_W"] / F["P_total_W"] - 1)
    # paired per-cycle CD differences (same wave cycles) -> significance vs cycle-to-cycle scatter
    d = np.array(r["cycle_CD"]) - np.array(F["cycle_CD"])
    r["dCD_paired_cycles_pct"] = (100 * d / np.array(F["cycle_CD"])).tolist()
out["results"] = S
(RUNS / "COMPARE_MAP3.json").write_text(json.dumps(out, indent=1, default=float))
keys = ["CL_mean", "dCL_vs_FIXED_pct", "CD_mean", "dCD_vs_FIXED_pct", "dCD_paired_cycles_pct", "CD_cycle_spread_pct",
        "P_drag_W", "P_act_W", "P_total_W", "dP_total_vs_FIXED_pct", "delta_amp_deg", "CL_h1_amp", "CL_phase_minus_eta_deg",
        "pFlap_min_Pa"]
print("window", t0, t_end)
for k in keys:
    print("%-24s" % k, "  ".join(("%s" % (np.round(S[n][k], 5) if not isinstance(S[n][k], list) else np.round(S[n][k], 3))).ljust(26) for n in S))
