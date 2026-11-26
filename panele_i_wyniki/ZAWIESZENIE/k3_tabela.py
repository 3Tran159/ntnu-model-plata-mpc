"""k3_tabela.py - wypisuje pelna tabele z K3_WIDMO\\K3_WIDMO.json (po k3_widmo.py summary) i liczbe przebiegow z dobiciem zawieszenia / wynurzeniem; tylko odczyt."""
import json, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent; D = HERE / (sys.argv[1] if len(sys.argv) > 1 else "K3_WIDMO")     # K3_WIDMO albo K3_WIENER
J = json.loads((D / "K3_WIDMO.json").read_text(encoding="utf-8"))
rows = [json.loads(p.read_text()) for p in (D / "wyniki").glob("*.json")]
print("P_calm", J["P_calm_90_W"])
for k, v in J["wyniki"].items():
    c, s = k.split("|"); R = [r for r in rows if r["case"] == c and r["sea"] == s and "error" not in r]
    bott = sum(r["bottomed"] for r in R); subneg = sum(r["sub_min"] < 0 for r in R); sub1c = sum(r["sub_min"] < 0.312 for r in R)
    pa = v["P_act_W_strip"]; pa = f"{pa[0]:.2f}-{pa[1]:.2f}" if pa else "-"
    print(f"{k:34s} n{v['n']} br {v['dP_brutto_pct']:+6.1f} net {v['dP_net_pct']:+6.1f} gen {v['P_gen_el_W_per_m'] or 0:6.0f} W/m act {pa} W/pasek "
          f"acc {v['acc_rms']:.3f} wk {v['acc_wk']:.3f} MSI {v['MSI']:.1f} a110 {v['acc_1_10']:.2f} pk {v['acc_peak']:.2f} sub {v['sub_min']:+.2f} "
          f"<1c% {np.mean([r['t_below_1c_pct'] for r in R]):.2f} skok {v['stroke']:.2f} dobicie {bott}/5 wynurz {subneg}/5 <1c {sub1c}/5 rate {v['rate_rms_deg_s'] or 0:.1f} werr {v['w_est_err_rel'] or 0:.3f}")
for k in ("PID1_sztywny", "K0_85", "K1_miekkie_f0.2_s0.5", "K0_50+K1_f0.2"):
    for s in ("S1", "S2", "S3", "S4"):
        v = J["odniesienie_koordynatora"].get(f"{k}|{s}")
        if v: print(f"KOORD {k}|{s}: dP {v['dP_pct']:+.1f} acc {v['acc_rms']:.3f} MSI {v['MSI']:.1f} sub {v['sub_min']:+.2f} <1c {v['below_1c_pct']:.2f}")
