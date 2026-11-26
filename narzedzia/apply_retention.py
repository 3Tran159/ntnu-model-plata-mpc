"""apply_retention.py - wykonuje plan z 00_START/RETENTION_PLAN.csv: pliki DO_KOSZA PRZENOSI (nie kasuje)
do 99_DO_UPORZADKOWANIA/_DO_USUNIECIA/<ta sama sciezka>. Ten sam dysk -> natychmiast, odwracalne.
Dziennik: 00_START/MIGRACJA.csv (stara sciezka -> nowa, GB, data). Pomija pliki zmienione w ostatnich 3 h."""
import csv, shutil, time
from pathlib import Path
ROOT = Path(r"T:\NTNU_GODO_CONTROL_20261109")
Q = ROOT / "99_DO_UPORZADKOWANIA" / "_DO_USUNIECIA"
plan = list(csv.DictReader(open(ROOT / "00_START" / "RETENTION_PLAN.csv", encoding="utf-8-sig"), delimiter=";"))
logp = ROOT / "00_START" / "MIGRACJA.csv"; new = not logp.exists()
tot = 0.0; n = 0
with open(logp, "a", newline="", encoding="utf-8-sig") as fh:
    w = csv.writer(fh, delimiter=";")
    if new: w.writerow(["data", "akcja", "stara", "nowa", "GB", "powod"])
    for r in plan:
        if r["akcja"] != "DO_KOSZA": continue
        src = ROOT / r["plik"]
        if not src.exists() or time.time() - src.stat().st_mtime < 3 * 3600: continue
        dst = Q / r["plik"]; dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        w.writerow([time.strftime("%Y-%m-%d %H:%M"), "do_kwarantanny", r["plik"], str(dst.relative_to(ROOT)), r["GB"], r["powod"]])
        tot += float(r["GB"]); n += 1
print("przeniesiono %d plikow, %.2f GB -> %s" % (n, tot, Q))
