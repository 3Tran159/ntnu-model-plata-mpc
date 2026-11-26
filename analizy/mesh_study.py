"""GodÃƒÂ¸-case mesh / time-step study. Usage: python mesh_study.py  -> 70_godo_case/MESH_STUDY.json"""
import json, math, pathlib
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
NIGHT = ROOT / "70_godo_case" / "night"
TE = 1.9368
VARS = {"COARSE": (1.41421356, 1e-3), "MEDIUM": (1.0, 1e-3), "FINE": (0.70710678, 1e-3), "MEDIUM_DT05": (1.0, 5e-4)}
for extra in ("FINE_DT0707", "COARSE_CPU"):
    if (NIGHT / extra).exists():
        VARS[extra] = None


def load(v):
    p = NIGHT / v / "history.csv"
    if not p.exists():
        return None
    lines = p.read_text().splitlines()
    hdr = lines[0].split(",")
    rows = {}
    for ln in lines[1:]:
        if ln.startswith("time_s"):
            continue
        f = ln.split(",")
        if len(f) != len(hdr):
            continue
        try:
            vals = [float(x) for x in f]
        except ValueError:
            continue
        rows[round(vals[0], 7)] = vals  # dedupe: last write wins (restart overlaps)
    t = np.array(sorted(rows))
    a = np.array([rows[k] for k in t])
    return {h: a[:, i] for i, h in enumerate(hdr)}


def harm(t, y, w):
    A = np.c_[np.ones_like(t), np.cos(w * t), np.sin(w * t)]
    c, *_ = np.linalg.lstsq(A, y, rcond=None)
    return c[0], math.hypot(c[1], c[2]), math.atan2(-c[2], c[1])  # y ~ m + a cos(wt + ph)


def analyse(v):
    d = load(v)
    if d is None:
        return {"status": "missing"}
    t = d["time_s"]
    out = {"t_last_s": float(t[-1]), "n_steps": int(len(t))}
    t1 = t[-1]
    nper = int(math.floor((t1 - 2 * TE) / TE + 2e-3))
    if nper < 1:
        out["status"] = "incomplete (less than 3 periods)"
        return out
    nper = min(nper, 4)
    t0 = t1 - nper * TE
    m = t > t0
    w = 2 * math.pi / TE
    tt = t[m]
    res = {"status": "ok" if nper == 4 else "partial", "periods_used": nper, "window_s": [float(t0), float(t1)]}
    eta = d["GODO_eta_upstream_quarter_lambda"][m]
    _, ea, eph = harm(tt, eta, w)
    res["eta_up_h1_amp_m"] = ea
    for k, key in (("CL", "AF_CL"), ("CD", "AF_CD"), ("Fx", "AF_Fx"), ("Mh", "AF_Mh")):
        y = d[key][m]
        mu, a, ph = harm(tt, y, w)
        cyc = [float(np.mean(y[(tt > t0 + i * TE) & (tt <= t0 + (i + 1) * TE)])) for i in range(nper)]
        res[k] = {"mean": float(np.mean(y)), "h1_amp": a, "h1_phase_vs_eta_deg": math.degrees((ph - eph + math.pi) % (2 * math.pi) - math.pi),
                  "cycle_means": cyc, "cycle_spread_pct": float(100 * (max(cyc) - min(cyc)) / abs(np.mean(y))) if nper > 1 else None}
    res["interfaceCFL_max"] = float(np.nanmax(d["GODO_interfaceCFL"][m]))
    res["yplus"] = {"mean": float(np.nanmean(d["GODO_yplus_mean"][m])), "max": float(np.nanmax(d["GODO_yplus_max"][m])),
                    "frac_30_70_mean": float(np.nanmean(d["GODO_yplus_frac_30_70"][m]))}
    res["s_per_step_median"] = float(np.median(d["solver_s"][m]))
    out.update(res)
    return out


def gci(f1, f2, f3, r=math.sqrt(2)):
    """Celik 2008, f1 fine, f3 coarse, constant r."""
    e21, e32 = f2 - f1, f3 - f2
    if e21 == 0 or e32 == 0:
        return {"note": "zero difference"}
    s = e32 / e21
    if s < 0:
        return {"convergence": "oscillatory", "e21": e21, "e32": e32}
    p = abs(math.log(abs(e32 / e21))) / math.log(r)
    ext = (r ** p * f1 - f2) / (r ** p - 1)
    ea = abs((f1 - f2) / f1)
    return {"convergence": "monotonic", "p": p, "f_ext": ext, "ea21_pct": 100 * ea, "GCI_fine_pct": 100 * 1.25 * ea / (r ** p - 1)}


R = {v: analyse(v) for v in VARS}
cmp = {}
mo, dt = R.get("MEDIUM", {}), R.get("MEDIUM_DT05", {})
if mo.get("status") in ("ok", "partial") and dt.get("status") in ("ok", "partial"):
    cmp["dt_effect_MEDIUM_1ms_vs_0p5ms"] = {k: {"pct": 100 * (dt[k]["mean"] - mo[k]["mean"]) / abs(dt[k]["mean"])} for k in ("CD", "Fx", "CL")}
    cmp["dt_effect_MEDIUM_1ms_vs_0p5ms"]["CL_h1_amp_pct"] = 100 * (mo["CL"]["h1_amp"] - dt["CL"]["h1_amp"]) / dt["CL"]["h1_amp"]
    cmp["dt_effect_MEDIUM_1ms_vs_0p5ms"]["CL_h1_phase_diff_deg"] = mo["CL"]["h1_phase_vs_eta_deg"] - dt["CL"]["h1_phase_vs_eta_deg"]
coarse = "COARSE_CPU" if R.get("COARSE_CPU", {}).get("status") in ("ok", "partial") else "COARSE"
fine = "FINE_DT0707" if R.get("FINE_DT0707", {}).get("status") in ("ok", "partial") else "FINE"
if all(R.get(v, {}).get("status") in ("ok", "partial") for v in (fine, "MEDIUM", coarse)):
    cmp["GCI_spatial"] = {"fine_variant": fine, "coarse_variant": coarse}
    for k in ("CD", "CL", "Mh"):
        cmp["GCI_spatial"][k + "_mean"] = gci(R[fine][k]["mean"], R["MEDIUM"][k]["mean"], R[coarse][k]["mean"])
        cmp["GCI_spatial"][k + "_h1_amp"] = gci(R[fine][k]["h1_amp"], R["MEDIUM"][k]["h1_amp"], R[coarse][k]["h1_amp"])
    cmp["GCI_spatial"]["dCD_fine_vs_medium_rel_CDcw_pct"] = 100 * (R[fine]["CD"]["mean"] - R["MEDIUM"]["CD"]["mean"]) / 0.0134
cmp["godo_appB_reference"] = "doubling resolution changed drag by 0.87 %"
CD_CW_REF = 0.0134   # calm-water-like CD of the fixed foil before the wave arrives (t ~ 0.04 s), used as a non-vanishing scale
if "dt_effect_MEDIUM_1ms_vs_0p5ms" in cmp:
    cmp["dt_effect_MEDIUM_1ms_vs_0p5ms"]["dCD_rel_to_CDcw_pct"] = 100 * (mo["CD"]["mean"] - dt["CD"]["mean"]) / CD_CW_REF
cmp["notes"] = ["mean CD in waves is close to zero (wave-induced thrust almost cancels viscous drag), so %% of mean CD is ill-conditioned;"
                " differences are also given relative to CD_cw_ref = %.4f" % CD_CW_REF,
                "cycle means still drift slowly (Fx +0.013 N per period, about 0.2 % of CD_cw per period)",
                "COARSE and FINE of the night failed (intermittent client NPE + orphan GPU clients; FINE hit CFL>0.95 at dt 1 ms);"
                " rerun 10 Nov: COARSE dt 1 ms, FINE_DT0707 dt 0.707 ms (same Courant number as MEDIUM)"]
OUT = {"Te_s": TE, "variants": R, "comparisons": cmp}
(ROOT / "70_godo_case" / "MESH_STUDY.json").write_text(json.dumps(OUT, indent=1))
print(json.dumps(OUT, indent=1))
