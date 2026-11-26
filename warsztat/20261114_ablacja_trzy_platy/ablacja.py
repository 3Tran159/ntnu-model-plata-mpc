"""ablacja.py - koordynator 14.11.2026 (prosba Julka 10:47): model Faltinsena B wobec "samych wirow" (wiry zwiazane + splywajace).
Warianty: B (pelny), bez_u (bez poziomej predkosci wody), bez_pow (bez powierzchni swobodnej: obraz, 6.144, opor falowy), wiry (bez obu).
Kazdy wariant ma wlasna wode spokojna (odniesienie) i wlasny trym. Wszystko w modelu.
Uzycie: python ablacja.py worker K N  |  python ablacja.py summary"""
import json, sys, time
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent; sys.path.insert(0, str(Path(r"T:\NTNU_GODO_CONTROL_20261109\60_PANELE_I_WYNIKI") / "WIDMO_S1S4")); sys.path.insert(0, str(Path(r"T:\NTNU_GODO_CONTROL_20261109\60_PANELE_I_WYNIKI") / "ZAWIESZENIE"))
import zaw90 as Z
import widmo_s1s4 as W
FP, U, G, BUOY = Z.FP, Z.U, Z.G, Z.BUOY
RES = HERE / "wyniki"; RES.mkdir(exist_ok=True)
VAR = {"B": dict(slope=1.0, wave_u=True), "bez_u": dict(slope=1.0, wave_u=False),
       "bez_pow": dict(slope=1.0, wave_u=True, free_surface=False), "wiry": dict(slope=1.0, wave_u=False, free_surface=False)}
TE = 1.9368


def calm(var, load):
    FP.MASS = load * Z.MASS100; P = Z.FaltinsenPlant(wave_amp=0.0, **VAR[var])
    cl_eq = (FP.MASS * G - BUOY) / P.q; trim = FP.TH_REF_DEG + float(np.degrees((cl_eq - FP.CL_REF) / (P.slope * P.dcl)))
    P.reset(theta_deg=trim); P.cmd = np.radians(trim)
    Pw = [P.step(free_heave=False)["P_drag_W_strip"] for _ in range(20000)]
    return float(np.mean(Pw[10000:])), trim


def regular(var, load, gain):
    FP.MASS = load * Z.MASS100; P = Z.FaltinsenPlant(wave_amp=0.733, **VAR[var])
    cl_eq = (FP.MASS * G - BUOY) / P.q; trim = FP.TH_REF_DEG + float(np.degrees((cl_eq - FP.CL_REF) / (P.slope * P.dcl)))
    P.reset(theta_deg=trim); ie = 0.0; n = int(round(30.0 / P.dt)); rec = []
    for i in range(n):
        free = P.t >= TE
        if i % P.tick == 0:
            cmd = trim
            if free: ie = float(np.clip(ie + (-P.z) * P.tick * P.dt, -1, 1)); cmd = trim + W.PID1[0] * (-P.z) + W.PID1[1] * ie
            if gain: cmd -= gain * float(np.degrees(float(np.mean(P.gust(P.F.xc, P.t)[1])) / U))
            P.cmd = np.radians(float(np.clip(cmd, -7.5, 7.5)))
        r = P.step(free_heave=free)
        if i % 10 == 9: rec.append((r["t"], (r["L"] + BUOY) / FP.MASS - G, r["P_drag_W_strip"]))
    a = np.array(rec); b = a[a[:, 0] > 30.0 - 3 * TE]
    return dict(P_W=float(b[:, 2].mean()), acc_rms=float(b[:, 1].std()))


JOBS = []
for v in VAR:
    JOBS += [("reg", v, "PID1_100", 1.0, 0.0), ("reg", v, "PID1_90", 0.9, 0.0), ("reg", v, "K0_85_90", 0.9, 0.85)]
    for s in ("S1", "S4"):
        for c in ("PID1_sztywny", "K0_85"): JOBS.append(("widmo", v, c, s, 0))


def worker(k, n):
    try:
        import psutil; p = psutil.Process(); p.cpu_affinity([18 + k]); p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    except Exception as e: print("affinity", e)
    W.T_SIM = 660.0
    for j, job in enumerate(JOBS):
        if j % n != k: continue
        f = RES / ("__".join(map(str, job)) + ".json")
        if f.exists(): continue
        t0 = time.time()
        try:
            if job[0] == "reg":
                _, v, name, load, gain = job; r = regular(v, load, gain); r["P_calm"], r["trim"] = calm(v, load)
            else:
                _, v, c, s, seed = job; Z.VB.clear(); Z.VB.update(VAR[v]); r = W.run(c, s, seed); r["P_calm"], r["trim"] = calm(v, 0.9)
        except Exception as e:
            r = dict(error=repr(e), P_W=float("nan"), P_calm=1.0, acc_rms=float("nan"), trim=float("nan"))
        r.update(job=list(job), wall=time.time() - t0); r["dP_pct"] = 100 * (r["P_W"] / r["P_calm"] - 1)
        f.write_text(json.dumps(r), encoding="utf-8")


def summary():
    rows = [json.loads(f.read_text(encoding="utf-8")) for f in sorted(RES.glob("*.json"))]
    out = {"__".join(map(str, r["job"])): dict(dP=round(r["dP_pct"], 2), acc=round(r["acc_rms"], 3), P_calm=round(r["P_calm"], 2), trim=round(r["trim"], 3),
           sub_min=round(r.get("sub_min", 0), 2), err=r.get("error", "")) for r in rows}
    (HERE / "ABLACJA.json").write_text(json.dumps(out, indent=1), encoding="utf-8"); print(json.dumps(out))


if __name__ == "__main__":
    if sys.argv[1] == "worker": worker(int(sys.argv[2]), int(sys.argv[3]))
    else: summary()
