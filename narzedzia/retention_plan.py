"""retention_plan.py - PLAN porzadkowania (tylko odczyt, nic nie usuwa ani nie przenosi).

Zasady recyrkulacji plikow .sim w kazdym folderze przebiegu:
  ZOSTAJE: plik startowy/SETUP (GODO_SETUP_*, *_SETUP_*), END_* (koniec), FINAL*, najnowszy CP_* (do wznowienia),
           wszystkie male pliki (csv, json, log, png, java, py, txt) - to sa wyniki i historia.
  DO KOSZA: starsze CP_* (gdy jest nowszy CP albo END), *.sim~ (kopie zapasowe STAR), *.simh starsze niz najnowszy w folderze,
           duplikaty pliku SETUP w wielu folderach (zostaje pierwszy, reszta = odsylacz).
  NIE RUSZA: aktywne przebiegi (folder zmieniony w ostatnich 3 h lub z dzialajacym procesem), overset_runs (zasada briefu),
             .venv, 00_source, 05_literature.
Wynik: RETENTION_PLAN.csv + RETENTION_PLAN.txt (podsumowanie w GB) w 00_START.
"""
import csv, os, re, sys, time, hashlib
from pathlib import Path
from collections import defaultdict

ROOT = Path(r"T:\NTNU_GODO_CONTROL_20261109")
OUT = ROOT / "00_START"
SKIP_TOP = {".venv", "00_START", "01_BRIEF_I_ZRODLA", "02_LITERATURA", "99_DO_UPORZADKOWANIA", "00_source", "05_literature", "10_macros", "20_supervisor", "30_runs", "40_analysis", "50_learning", "60_dashboard", "70_godo_case"}
PROTECT_PARTS = {"overset_runs"}          # brief: nie zmieniac plikow w overset_runs
ACTIVE_H = 3.0
now = time.time()


def is_active(d: Path):
    try:
        newest = max((f.stat().st_mtime for f in d.iterdir() if f.is_file()), default=0)
    except Exception:
        return True
    return (now - newest) < ACTIVE_H * 3600


def main():
    OUT.mkdir(exist_ok=True)
    rows = []
    setup_seen = {}
    by_dir = defaultdict(list)
    for top in ROOT.iterdir():
        if not top.is_dir() or top.name in SKIP_TOP:
            continue
        for f in top.rglob("*"):
            if f.is_file() and f.suffix.lower() in (".sim", ".simh", ".sim~"):
                by_dir[f.parent].append(f)
    for d, files in sorted(by_dir.items()):
        protect = any(p in d.parts for p in PROTECT_PARTS)
        active = is_active(d)
        cps = sorted([f for f in files if re.match(r"CP_\d+", f.name)], key=lambda f: f.stat().st_mtime)
        ends = [f for f in files if f.name.startswith(("END", "FINAL"))]
        simh = sorted([f for f in files if f.suffix.lower() == ".simh"], key=lambda f: f.stat().st_mtime)
        for f in files:
            gb = f.stat().st_size / 1e9
            act, why = "ZOSTAJE", ""
            if f.suffix.lower() == ".sim~":
                act, why = "DO_KOSZA", "kopia zapasowa STAR (.sim~)"
            elif f in cps[:-1]:
                act, why = "DO_KOSZA", "starszy checkpoint (jest nowszy %s)" % cps[-1].name
            elif cps and f == cps[-1] and ends and max(e.stat().st_mtime for e in ends) >= f.stat().st_mtime:
                act, why = "DO_KOSZA", "ostatni checkpoint, ale jest END/FINAL"
            elif f in ends and f != max(ends, key=lambda e: e.stat().st_mtime):
                act, why = "DO_KOSZA", "starszy END (zostaje najnowszy %s)" % max(ends, key=lambda e: e.stat().st_mtime).name
            elif f in simh[:-1]:
                act, why = "DO_KOSZA", "starsza historia .simh"
            elif "SETUP" in f.name.upper():
                key = (f.name, f.stat().st_size)
                if key in setup_seen:
                    act, why = "DO_KOSZA", "duplikat SETUP (zostaje %s)" % setup_seen[key]
                else:
                    setup_seen[key] = str(f.relative_to(ROOT))
            if act == "DO_KOSZA" and protect:
                act, why = "CHRONIONE", why + " | overset_runs - nie ruszam bez zgody"
            if act == "DO_KOSZA" and active:
                act, why = "AKTYWNE", why + " | folder zmieniany < %.0f h" % ACTIVE_H
            rows.append(dict(akcja=act, GB=round(gb, 3), plik=str(f.relative_to(ROOT)), powod=why,
                             data=time.strftime("%Y-%m-%d %H:%M", time.localtime(f.stat().st_mtime))))
    with open(OUT / "RETENTION_PLAN.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["akcja", "GB", "plik", "powod", "data"], delimiter=";")
        w.writeheader(); w.writerows(sorted(rows, key=lambda r: (r["akcja"], r["plik"])))
    tot = defaultdict(float); n = defaultdict(int)
    for r in rows:
        tot[r["akcja"]] += r["GB"]; n[r["akcja"]] += 1
    top_dirs = defaultdict(float)
    for r in rows:
        if r["akcja"] == "DO_KOSZA":
            top_dirs[str(Path(r["plik"]).parent)] += r["GB"]
    lines = ["PLAN RECYRKULACJI .sim  (%s)  - nic nie zostalo usuniete" % time.strftime("%Y-%m-%d %H:%M")]
    for k in ("ZOSTAJE", "DO_KOSZA", "CHRONIONE", "AKTYWNE"):
        lines.append("  %-10s %4d plikow  %7.2f GB" % (k, n[k], tot[k]))
    lines.append("Najwiecej do odzyskania:")
    for d, gb in sorted(top_dirs.items(), key=lambda x: -x[1])[:25]:
        lines.append("  %6.2f GB  %s" % (gb, d))
    (OUT / "RETENTION_PLAN.txt").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()

