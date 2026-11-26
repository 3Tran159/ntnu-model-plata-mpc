"""Analyse the Godø overset PID baseline -> 70_godo_case/OVERSET_BASELINE.json"""
import csv, json, math, pathlib
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1] / "70_godo_case"
TE, U, REL = 1.9368, 12.3467, 1.9368


def load(run):
    R = {}
    p = ROOT / "overset_runs" / run / "history.csv"
    if not p.exists():
        return None
    for r in csv.DictReader(open(p)):
        try:
            R[round(float(r["time_s"]), 6)] = r
        except Exception:
            pass
    t = np.array(sorted(R))
    cols = list(next(iter(R.values())).keys())
    d = {"t": t}
    for c in cols:
        if c in ("time_s", "mode"):
            continue
        try:
            d[c] = np.array([float(R[x][c]) if R[x][c] not in ("", None) else np.nan for x in t])
        except Exception:
            pass
    return d


def harm(t, y, w):
    A = np.c_[np.ones_like(t), np.cos(w * t), np.sin(w * t)]
    c, *_ = np.linalg.lstsq(A, y, rcond=None)
    return c[0], math.hypot(c[1], c[2]), math.atan2(-c[2], c[1])


def hf(t, y, f0):
    m = t > REL + 0.25
    yy = y[m] - np.convolve(y[m], np.ones(50) / 50, "same")
    f = np.fft.rfftfreq(m.sum(), 1e-3); A = np.abs(np.fft.rfft(yy)) * 2 / m.sum()
    return float(A[(f > f0 - 5) & (f < f0 + 5)].max())


def analyse(run):
    d = load(run)
    if d is None:
        return {"status": "missing"}
    t = d["t"]; out = {"t_last_s": float(t[-1]), "n": int(len(t))}
    nper = int(math.floor((t[-1] - REL) / TE + 2e-3))
    nper = min(nper, 4)
    out["hf_100Hz_amp"] = {k: hf(t, d[k], 100) for k in ("AF_Fx", "GODO_Fy_fluid", "GODO_M_pivot") if k in d}
    out["hf_200Hz_amp"] = {k: hf(t, d[k], 200) for k in ("AF_Fx", "GODO_Fy_fluid") if k in d}
    if nper < 1:
        out["status"] = "too short"; return out
    t1 = t[-1]; t0 = t1 - nper * TE; m = t > t0; tt = t[m]; w = 2 * math.pi / TE
    out.update({"status": "ok", "periods": nper, "window_s": [float(t0), float(t1)]})
    _, ea, eph = harm(tt, d["GODO_eta_at_LE"][m], w)
    S = {}
    for k in ("z_m", "theta_deg", "GODO_lift_over_weight", "AF_CL", "AF_CD", "AF_Fx", "P_drag_W", "P_act_W", "GODO_M_pivot", "v_m_s"):
        y = d[k][m]; mu, a, ph = harm(tt, y, w)
        S[k] = {"mean": float(np.nanmean(y)), "min": float(np.nanmin(y)), "max": float(np.nanmax(y)), "h1_amp": a,
                "h1_phase_vs_eta_LE_deg": math.degrees((ph - eph + math.pi) % (2 * math.pi) - math.pi)}
    S["P_total_W"] = {"mean": float(np.nanmean(d["P_drag_W"][m] + d["P_act_W"][m]))}
    acc = np.gradient(d["v_m_s"][m], tt)
    S["zddot_m_s2"] = {"rms": float(np.sqrt(np.mean(acc ** 2))), "max_abs": float(np.abs(acc).max()), "max_abs_over_g": float(np.abs(acc).max() / 9.81)}
    S["theta_rate_deg_s"] = {"max_abs": float(np.nanmax(np.abs(d["theta_rate_deg_s"][m])))}
    S["eta_LE_h1_amp_m"] = ea
    S["eta_up_h1_amp_m"] = harm(tt, d["GODO_eta_upstream_quarter_lambda"][m], w)[1]
    S["interfaceCFL_max"] = float(np.nanmax(d["GODO_interfaceCFL"][m]))
    S["s_per_step_median"] = float(np.nanmedian(d["solver_s"][m]))
    S["limits_ok"] = bool(np.nanmax(np.abs(d["z_m"][m])) < 0.75 and np.nanmax(np.abs(d["theta_deg"][m])) <= 7.5 + 1e-6)
    out["stats"] = S
    return out


res = {r: analyse(r) for r in ("OVS_PID_BASE2", "OVS_PID_BASE", "OVS_PID_PRBS1", "OVS_PID_SINE_A2")}
(ROOT / "OVERSET_BASELINE.json").write_text(json.dumps(res, indent=1))
print(json.dumps(res, indent=1))
