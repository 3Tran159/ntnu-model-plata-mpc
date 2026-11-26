"""strut_chain.py - kolejka: wspornik w wodzie spokojnej, h = 1.09, 0.7, 1.5 m.
Dla kazdego h: (1) BuildStrutCalm (CPU, rdzen P 23) -> STRUT_SETUP_h*.sim, (2) RunStrut na GPU (gospodarz na rdzeniu 23).
Wznowienie: uruchom ponownie - gotowe (RUN_RESULT DONE) pomija, przerwane wznawia z ostatniego CP_*.sim.
Log: strut_chain.log.  Zatrzymanie: plik STOP w folderze h* (RunStrut zapisze CP i wyjdzie).
"""
import sys, json, time, re
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "20_supervisor"))
import starrun

SRC = HERE.parent / "night" / "MEDIUM" / "GODO_SETUP_B1.0.sim"
CPUS = (23,)
HS = [float(x) for x in (sys.argv[1].split(",") if len(sys.argv) > 1 else ["1.09", "0.7", "1.5"])]


def log(m):
    with open(HERE / "strut_chain.log", "a", encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + m + "\n")


def status(d):
    try:
        return json.loads((d / "RUN_RESULT.json").read_text()).get("status")
    except Exception:
        return None


template = (HERE / "h1.09" / "control.properties").read_text()
for h in HS:
    d = HERE / ("h%g" % h if h != 1.09 else "h1.09")
    d.mkdir(exist_ok=True)
    if status(d) == "DONE":
        log("h=%g juz DONE" % h); continue
    if not (d / "control.properties").exists():
        (d / "control.properties").write_text(re.sub(r"(?m)^h_m=.*$", "h_m=%g" % h, template))
    setup = sorted(d.glob("STRUT_SETUP_h*.sim"))
    if not setup:
        log("h=%g setup start" % h)
        r = starrun.launch(SRC, HERE / "BuildStrutCalm.java", d, cpus=CPUS, timeout_s=5400)
        setup = sorted(d.glob("STRUT_SETUP_h*.sim"))
        log("h=%g setup koniec rc=%s, plik=%s" % (h, r.get("returncode"), setup[-1].name if setup else "BRAK"))
        if not setup:
            continue
    cps = sorted(d.glob("CP_*.sim"), key=lambda p: p.stat().st_mtime)
    start = cps[-1] if cps else setup[-1]
    (d / "STOP").unlink(missing_ok=True)
    log("h=%g run start z %s (GPU)" % (h, start.name))
    r = starrun.launch(start, HERE / "RunStrut.java", d, cpus=CPUS, gpu=True, timeout_s=8 * 3600, np_=1)
    log("h=%g run koniec rc=%s status=%s" % (h, r.get("returncode"), status(d)))
log("kolejka koniec")
