"""Restart optymalizacji po bledzie ugiecia profilu w petli G2 (gorny plat mial odwrocone ugiecie -> ujemna sila nosna).
Nic nie kasuje: wadliwe przypadki przemianowane na *_BLAD_KAMBER, stary CSV -> OPT_WYNIKI_BLAD_KAMBER.csv."""
import json, time
from pathlib import Path
H = Path(__file__).parent
bad = ["OPT_10", "OPT_11", "OPT_12", "P3D_AR4_g2_h04", "P3D_AR8_g2_h04", "P3D_AR8_g2_h10"]
for b in bad:
    if (H / b).exists(): (H / b).rename(H / f"{b}_BLAD_KAMBER")
for b in ["P3D_g2_h04"] + [f"OPT_{k:02d}" for k in range(32)]:          # nieudane siatki (rc 15 od zabijania procesow) - czysty start
    d = H / b
    if d.exists() and not (d / "PETLA_SETUP.sim").exists(): d.rename(H / f"{b}_NIEUDANA_{time.strftime('%H%M')}")
if (H / "OPT_WYNIKI.csv").exists():
    import csv
    rows = list(csv.DictReader(open(H / "OPT_WYNIKI.csv", encoding="utf-8")))
    (H / "OPT_WYNIKI.csv").rename(H / "OPT_WYNIKI_BLAD_KAMBER.csv")
    ok = [r for r in rows if r["name"] not in bad]                      # pojedyncze platy sa poprawne
    with open(H / "OPT_WYNIKI.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(ok)
st = json.loads((H / "P3D_STATUS.json").read_text())
for k in list(st):
    if k in bad or k.startswith("OPT_") or k == "P3D_g2_h04": st.pop(k)
(H / "P3D_STATUS.json").write_text(json.dumps(st, indent=1))
plan = json.loads((H / "OPT_PLAN.json").read_text())
names = [p["name"] for p in plan]
for n, ar in (("P3D_AR8_g2_h04", 8), ("P3D_AR4_g2_h04", 4)):
    if n not in names: plan.insert(5, dict(name=n, ar=ar, gap=0.4, stag=0))
(H / "OPT_PLAN.json").write_text(json.dumps(plan, indent=1)); print("ok", len(plan))
