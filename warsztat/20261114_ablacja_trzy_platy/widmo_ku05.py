"""widmo_ku05.py - koordynator 14.11.2026: koncepcje z widmo_s1s4.py w modelu B z u x 0,5 (kalibracja oporu, krok3-ablacja-modelu.md).
8 koncepcji x S1-S4 x 2 realizacje (ziarna 0, 1) x 660 s (60 s odrzucone). Rdzenie 18-23. Uzycie: worker K N | summary"""
import json, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
import kalibracja_u as KAL
A, W, Z = KAL.A, KAL.W, KAL.Z
RES = HERE / "wyniki_widmo_ku05"; RES.mkdir(exist_ok=True)
KAL.KU["k"] = 0.5
JOBS = [(c, s, sd) for c in W.CASES for s in ("S1", "S2", "S3", "S4") for sd in (0, 1)]


def worker(k, n):
    try:
        import psutil; p = psutil.Process(); p.cpu_affinity([18 + k]); p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    except Exception as e: print("affinity", e)
    W.T_SIM = 660.0
    for j, (c, s, sd) in enumerate(JOBS):
        if j % n != k: continue
        f = RES / f"{c}__{s}__{sd}.json"
        if f.exists(): continue
        try:
            Z.VB.clear(); Z.VB.update(slope=1.0, wave_u=True); r = W.run(c, s, sd)
            r["P_calm"], _ = A.calm("B", 0.9); r["dP_pct"] = 100 * (r["P_W"] / r["P_calm"] - 1)
        except Exception as e: r = dict(error=repr(e))
        f.write_text(json.dumps(r), encoding="utf-8")


def summary():
    rows = [json.loads(f.read_text(encoding="utf-8")) for f in RES.glob("*.json")]
    out = {}
    for c in W.CASES:
        for s in ("S1", "S2", "S3", "S4"):
            R = [r for r in rows if r.get("case") == c and r.get("sea") == s]
            if R: out[f"{c}|{s}"] = dict(n=len(R), dP=round(float(np.mean([r["dP_pct"] for r in R])), 2), acc=round(float(np.mean([r["acc_rms"] for r in R])), 3),
                                         sub_min=round(min(r["sub_min"] for r in R), 2))
    (HERE / "WIDMO_KU05.json").write_text(json.dumps(out, indent=1), encoding="utf-8"); print(json.dumps(out))


if __name__ == "__main__":
    if sys.argv[1] == "worker": worker(int(sys.argv[2]), int(sys.argv[3]))
    else: summary()
