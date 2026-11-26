"""Wave phase reference for the first-harmonic map test (same convention as wave_phase_map_analysis.py).

eta(-3 m, t) = m + c cos(w t) + s sin(w t)  ->  Z = c - i s,  eta ~ |Z| cos(w t + arg Z)
incident wave phase phi(t) = w t + theta0 (crest at 0), theta0 = arg Z ; flap = A cos(phi + phase_off).
Window and period as in WAVE_PHASE_TO_FLAP_REPORT.json fixed_gate.
"""
import csv, json, math
import numpy as np
from pathlib import Path

F = Path(r"F:\ntnu\flap_control\exploration_lab\MINI_POC_2D_20261103\mini_vof_20261103\COMEBACK_20261104\runs\PHASE_MAP_WAVE_FIXED_20261106_105755\gauges.csv")
REP = Path(r"F:\ntnu\flap_control\exploration_lab\MINI_POC_2D_20261103\mini_vof_20261103\COMEBACK_20261104\RESUME_0422200_GPU_CHECK_20261105\WAVE_PHASE_TO_FLAP_REPORT.json")
r = json.loads(REP.read_text())
T = r["period_s"]; t0, t1 = r["fixed_gate"]["window_s"]
w = 2 * math.pi / T
rows = [(float(a["time_s"]), float(a["eta_actual_m"])) for a in csv.DictReader(F.open()) if abs(float(a["x_m"]) + 3) < 1e-7]
t, y = np.array([x for x in rows if t0 <= x[0] < t1]).T
out = {"period_s": T, "omega_rad_s": w, "window_s": [t0, t1], "n": int(len(t))}
for name, ww in (("map_period", w), ("native_period", 2 * math.pi / 0.45555302324319264)):
    A = np.column_stack((np.ones_like(t), np.cos(ww * t), np.sin(ww * t)))
    m, c, s = np.linalg.lstsq(A, y, rcond=None)[0]
    res = y - A @ np.array([m, c, s])
    out[name] = {"omega": ww, "theta0_rad": math.atan2(-s, c), "amp_m": math.hypot(c, s), "mean_m": m,
                 "resid_rms_m": float(np.sqrt(np.mean(res ** 2)))}
# per-cycle phase stability with the map period
ph = []
k = 0
while t0 + (k + 1) * T <= t1 + 1e-9:
    m_ = (t >= t0 + k * T) & (t < t0 + (k + 1) * T)
    A = np.column_stack((np.ones(m_.sum()), np.cos(w * t[m_]), np.sin(w * t[m_])))
    _, c, s = np.linalg.lstsq(A, y[m_], rcond=None)[0]
    ph.append(math.degrees(math.atan2(-s, c)))
    k += 1
out["per_cycle_theta0_deg"] = ph
out["map_amp_deg"] = r["flap_amplitude_deg"]; out["map_phase_off_deg"] = r["phase_offset_deg"]
Path(r"T:\NTNU_GODO_CONTROL_20261109\40_analysis\MAP_PHASE_REFERENCE.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
