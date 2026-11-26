import json
from pathlib import Path
H = Path(__file__).parent; PF, PS = 57.06, 12.35 * 85.5 * 0.02 * 1.09
for s in ("S1", "S2", "S3", "S4"):
    for rule, d in (("2c", "wyniki_act57_wa3"), ("1.5c", "wyniki_act57_wa3_sub1.5"), ("1c", "wyniki_act57_wa3_sub1")):
        f = H / d / f"{s}__s0.json"
        if not f.exists(): print(s, rule, "BRAK"); continue
        r = json.loads(f.read_text())
        if "error" in r: print(s, rule, "BLAD", r["error"]); continue
        print(f"| {s} | {rule} | {100*((r['P_foil_W']+r['P_strut_W'])/(PF+PS)-1):+.1f} | {100*(r['P_foil_W']/PF-1):+.1f} | {r['acc_rms']:.2f} | {r['sub_min']:.2f} | {r['t_below_1c_pct']:.2f} |")
