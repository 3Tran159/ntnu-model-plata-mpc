"""kalibracja_u.py - koordynator 14.11.2026 (zgoda Julka 11:05). Model B z przeskalowana pozioma predkoscia fali (u -> ku*u) albo z cd_wave 0,0016.
Punkty URANS (fala regularna H 1,5 m, T 5 s, ostatnie 3 okresy): PID1/2/3 przy 100 % (-19,2 / -3,4 / +49,0 %), K0 85 % przy 90 % (-4,3 %).
Nie zmienia faltinsen_plant.py - skalowanie przez opakowanie metody gust() w tym procesie. Uzycie: worker K N | summary"""
import json, sys, time
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
import ablacja as A
Z, FP, W = A.Z, A.FP, A.W
RES = HERE / "wyniki_kal"; RES.mkdir(exist_ok=True)
_g = Z.FaltinsenPlant.gust
KU = {"k": 1.0}
def gust_scaled(self, x, t):
    u, w = _g(self, x, t); return KU["k"] * u, w
Z.FaltinsenPlant.gust = gust_scaled
PIDS = {"PID1": (2.01, 0.196), "PID2": (6.63, 1.18), "PID3": (22.3, 7.25)}
URANS = {"PID1_100": -19.2, "PID2_100": -3.4, "PID3_100": 49.0, "K0_85_90": -4.3}
CASES = [("PID1_100", "PID1", 1.0, 0.0), ("PID2_100", "PID2", 1.0, 0.0), ("PID3_100", "PID3", 1.0, 0.0), ("K0_85_90", "PID1", 0.9, 0.85)]
VARS = [("ku1.0", 1.0, 0.0), ("ku0.4", 0.4, 0.0), ("ku0.5", 0.5, 0.0), ("ku0.6", 0.6, 0.0), ("cdw", 1.0, 0.0016)]
JOBS = [(v, c) for v in VARS for c in CASES]


def one(var, case):
    name, ku, cdw = var; cname, pid, load, gain = case; KU["k"] = ku; W.PID1 = PIDS[pid]
    A.VAR["kal"] = dict(slope=1.0, wave_u=True, cd_wave=cdw)
    r = A.regular("kal", load, gain); A.VAR["kal"] = dict(slope=1.0, wave_u=True)      # woda spokojna bez cd_wave (jak URANS CALM)
    r["P_calm"], r["trim"] = A.calm("kal", load); r["dP_pct"] = 100 * (r["P_W"] / r["P_calm"] - 1); r["urans"] = URANS[cname]
    return r


def worker(k, n):
    try:
        import psutil; p = psutil.Process(); p.cpu_affinity([18 + k]); p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    except Exception as e: print("affinity", e)
    for j, (v, c) in enumerate(JOBS):
        if j % n != k: continue
        f = RES / f"{v[0]}__{c[0]}.json"
        if f.exists(): continue
        try: r = one(v, c)
        except Exception as e: r = dict(error=repr(e))
        f.write_text(json.dumps(r), encoding="utf-8")


def summary():
    out = {}
    for f in sorted(RES.glob("*.json")):
        r = json.loads(f.read_text(encoding="utf-8")); out[f.stem] = {k: round(r[k], 2) for k in ("dP_pct", "urans", "acc_rms") if k in r}
        if "error" in r: out[f.stem]["err"] = r["error"]
    (HERE / "KALIBRACJA_U.json").write_text(json.dumps(out, indent=1), encoding="utf-8"); print(json.dumps(out))


if __name__ == "__main__":
    if sys.argv[1] == "worker": worker(int(sys.argv[2]), int(sys.argv[3]))
    else: summary()
