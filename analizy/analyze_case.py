"""Metrics for a Godo-control case (history.csv written by GodoControl.java).

usage: python analyze_case.py <case_dir> [t_from t_to]   -> prints and writes METRICS.json
Window defaults to the last full encounter period(s) available (T_e = 0.45555302324319264 s).
Definitions (no hidden normalisation):
  CL, CD   : AF_CL / AF_CD as reported by the sim (buoyancy-corrected, 3855.6 N/ coefficient basis of the sim)
  Fx       : AF_Fx [N] (drag-direction sign as in the sim; mean power U*Fx, U = 18 m/s)
  hinge power demand (no recovery) = max(0, -Mh * d(delta)/dt)  [W]  -- SIGN CONVENTION STILL TO BE
             CONFIRMED against Mh axis/delta direction (reported both ways below)
"""
import sys, json, math
from pathlib import Path
import numpy as np

TE = 0.45555302324319264
U = 18.0


def load(case):
    arr = np.genfromtxt(Path(case) / "history.csv", delimiter=",", names=True)
    return arr


def harmonic(t, x, T=TE):
    w = 2 * math.pi / T
    a = 2 * np.mean(x * np.cos(w * t))
    b = 2 * np.mean(x * np.sin(w * t))
    return math.hypot(a, b), math.degrees(math.atan2(b, a))


def window_stats(h, t0, t1):
    m = (h["time_s"] >= t0 - 1e-9) & (h["time_s"] <= t1 + 1e-9)
    t = h["time_s"][m]
    out = {"t0": float(t[0]), "t1": float(t[-1]), "n": int(m.sum())}
    for k in ("CL", "CD", "Fx_N", "Fz_N", "Mh_Nm", "pFlapAbsMin_Pa", "cmd_deg", "meas_deg"):
        x = h[k][m]
        amp, ph = harmonic(t, x - x.mean())
        out[k] = {"mean": float(x.mean()), "rms": float(np.sqrt(np.mean((x - x.mean()) ** 2))),
                  "min": float(x.min()), "max": float(x.max()), "h1_amp": amp, "h1_phase_deg": ph}
    dt = float(np.mean(np.diff(t)))
    ddot = np.gradient(h["meas_deg"][m], dt) * math.pi / 180.0  # rad/s
    p = -h["Mh_Nm"][m] * ddot
    out["hinge_power_W"] = {"mean_net": float(p.mean()), "demand_no_recovery_mean": float(np.maximum(0, p).mean()),
                            "demand_other_sign_mean": float(np.maximum(0, -p).mean()),
                            "max_rate_deg_s": float(np.max(np.abs(ddot)) * 180 / math.pi)}
    out["U_times_mean_Fx_W"] = U * out["Fx_N"]["mean"]
    return out


def main():
    case = Path(sys.argv[1])
    h = load(case)
    t_end = float(h["time_s"][-1])
    t0 = float(sys.argv[2]) if len(sys.argv) > 2 else max(float(h["time_s"][0]), t_end - TE * math.floor((t_end - h["time_s"][0]) / TE))
    t1 = float(sys.argv[3]) if len(sys.argv) > 3 else t_end
    res = window_stats(h, t0, t1)
    res["case"] = str(case)
    (case / "METRICS.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
