"""Unattended watcher: waits for cases to finish, then writes gate/comparison JSON files.

 - INT_SCRIPTED vs INT_FIXED  -> INTEGRATION_GATE.json  (sign, tracking, lag, time continuity, guards)
 - PI_* vs FIXED_REF          -> COMPARISON_<pi_case>.json (same start state, same window)
Run detached:  python watch_and_analyze.py
"""
import json, math, sys, time
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
from analyze_case import load, window_stats, TE

RUNS = Path(r"T:\NTNU_GODO_CONTROL_20261109\30_runs")
VAPOR = 2339.214766776897


def newest(prefix):
    c = sorted([p for p in RUNS.glob(prefix + "_2*") if p.is_dir()])
    return c[-1] if c else None


def done(p):
    return p is not None and ((p / "FC_RESULT.json").exists() or (p / "ERROR.json").exists())


def integration_gate(sc, fx):
    a, b = load(sc), load(fx)
    n = min(len(a["time_s"]), len(b["time_s"]))
    t = a["time_s"][:n]
    g = {"cases": [str(sc), str(fx)], "steps_compared": int(n)}
    g["time_continuity_max_dev_s"] = float(np.max(np.abs(np.diff(a["time_s"]) - 5e-4)))
    g["time_continuity_pass"] = g["time_continuity_max_dev_s"] < 1e-8
    g["tracking_max_abs_cmd_minus_meas_deg"] = float(np.max(np.abs(a["cmd_deg"] - a["meas_deg"])))
    # lag cmd -> meas by cross-correlation of derivatives (steps)
    dc, dm = np.gradient(a["cmd_deg"]), np.gradient(a["meas_deg"])
    best = min(range(-6, 7), key=lambda k: np.sum((np.roll(dc, k) - dm) ** 2))
    g["cmd_to_meas_lag_steps"] = int(-best) if False else int(best)
    dCL = a["CL"][:n] - b["CL"][:n]
    dCD = a["CD"][:n] - b["CD"][:n]
    d = a["meas_deg"][:n]
    hold = np.where((np.abs(a["cmd_deg"][:n] - np.round(a["cmd_deg"][:n], 6)) < 1e-9) & (np.abs(a["cmd_deg"][:n]) > 0.9))[0]
    if len(hold) > 20:
        g["dCL_per_deg_on_hold"] = float(np.mean(dCL[hold] / d[hold]))
        g["dCD_per_deg_on_hold"] = float(np.mean(dCD[hold] / d[hold]))
    g["sign_positive_delta_gives_positive_dCL"] = bool(np.corrcoef(d, dCL)[0, 1] > 0.5)
    g["pFlapAbsMin_min_Pa"] = float(np.min(a["pFlapAbsMin_Pa"]))
    g["pFlapAbsMin_above_vapor"] = g["pFlapAbsMin_min_Pa"] > VAPOR
    g["interfaceCFL_max"] = float(np.max(a["interfaceCFL"]))
    g["interfaceCFL_pass"] = g["interfaceCFL_max"] < 0.9
    g["CL_first_step"] = float(a["CL"][0])
    g["fixed_vs_scripted_CL_first_step_diff"] = float(a["CL"][0] - b["CL"][0])
    g["PASS"] = bool(g["time_continuity_pass"] and g["tracking_max_abs_cmd_minus_meas_deg"] < 0.05
                     and g["sign_positive_delta_gives_positive_dCL"] and g["interfaceCFL_pass"])
    return g


def comparison(pi, fx):
    a, b = load(pi), load(fx)
    n = min(len(a["time_s"]), len(b["time_s"]))
    t = a["time_s"][:n]
    t1 = float(t[-1]); k = math.floor((t1 - float(t[0])) / TE)
    out = {"pi_case": str(pi), "fixed_case": str(fx), "window_periods": k}
    if k >= 1:
        t0 = t1 - k * TE
        wa, wb = window_stats(a, t0, t1), window_stats(b, t0, t1)
        out["PI"], out["FIXED"] = wa, wb
        out["delta_vs_FIXED"] = {
            "CL_mean": wa["CL"]["mean"] - wb["CL"]["mean"],
            "CD_mean_rel_pct": 100 * (wa["CD"]["mean"] / wb["CD"]["mean"] - 1),
            "Fx_mean_rel_pct": 100 * (wa["Fx_N"]["mean"] / wb["Fx_N"]["mean"] - 1),
            "CL_rms_ratio": wa["CL"]["rms"] / wb["CL"]["rms"]}
    return out


def main():
    while True:
        sc, fx = newest("INT_SCRIPTED"), newest("INT_FIXED")
        if done(sc) and done(fx) and not (RUNS / "INTEGRATION_GATE.json").exists():
            try:
                (RUNS / "INTEGRATION_GATE.json").write_text(json.dumps(integration_gate(sc, fx), indent=1))
            except Exception as e:
                (RUNS / "INTEGRATION_GATE.json").write_text(json.dumps({"error": repr(e)}))
        pi, fr = newest("PI_KP08"), newest("FIXED_REF")
        if done(pi) and done(fr) and not (RUNS / "COMPARISON_PI_KP08.json").exists():
            try:
                (RUNS / "COMPARISON_PI_KP08.json").write_text(json.dumps(comparison(pi, fr), indent=1))
            except Exception as e:
                (RUNS / "COMPARISON_PI_KP08.json").write_text(json.dumps({"error": repr(e)}))
        if (RUNS / "INTEGRATION_GATE.json").exists() and (RUNS / "COMPARISON_PI_KP08.json").exists():
            break
        time.sleep(60)


if __name__ == "__main__":
    main()
