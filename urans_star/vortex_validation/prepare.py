"""prepare.py - buduje w tym folderze makro i runner do walidacji modelu wirowego, na bazie AKTUALNYCH plikow
70_godo_case/GodoOversetRun.java i run_overset_ctrl.py (niczego w nich nie zmienia).
Dodaje tryb 'hold_sine': nurzanie zablokowane, theta = trim + amp * rampa * sin(2*pi*tt/T + faza), tt = t - release_s.
Uruchom ponownie po kazdej zmianie makra bazowego (np. po poprawkach stabilnosci oversetu)."""
import sys
from pathlib import Path
VV = Path(__file__).resolve().parent
BASE = Path(sys.argv[1]) if len(sys.argv) > 1 else VV.parent

def patch(txt, old, new, what):
    if txt.count(old) != 1:
        raise SystemExit("PATCH NIEUDANY (%s): wzorzec wystepuje %d razy - makro bazowe sie zmienilo, popraw prepare.py" % (what, txt.count(old)))
    return txt.replace(old, new)

j = (BASE / "GodoOversetRun.java").read_text(encoding="utf-8")
j = patch(j, 'if(mode.equals("pid_sine"))cmd+=',
          'if(mode.equals("hold_sine"))cmd+=d("exc_amp_deg",0.0)*Math.min(1.0,tt/d("ramp_s",1.9368))*Math.sin(2*Math.PI*tt/d("exc_period_s",1.9368)+Math.toRadians(d("exc_phase_deg",0)));\n       if(mode.equals("pid_sine"))cmd+=', "sinus")
j = patch(j, 'if(free){v+=dt*(fy-mass*g)/mass;}else{v=0;}',
          'if(free&&!mode.equals("hold_sine")){v+=dt*(fy-mass*g)/mass;}else{v=0;}', "blokada nurzania")
(VV / "GodoOversetRun.java").write_text(j, encoding="utf-8")

r = (BASE / "run_overset_ctrl.py").read_text(encoding="utf-8")
r = patch(r, 'import night_queue as nq', 'sys.path.insert(0, str(Path(__file__).resolve().parent.parent))\nimport night_queue as nq', "sciezka importu")
r = patch(r, 'HERE = Path(__file__).parent', 'VV = Path(__file__).resolve().parent\nHERE = VV.parent', "HERE")
r = patch(r, 'case = HERE / "overset_runs" / tag', 'case = VV / "runs" / tag', "folder przypadku")
r = patch(r, 'shutil.copy2(HERE / "GodoOversetRun.java", case / "GodoOversetRun.java")', 'shutil.copy2(VV / "GodoOversetRun.java", case / "GodoOversetRun.java")', "zrodlo makra")
(VV / "run_vv_ctrl.py").write_text(r, encoding="utf-8")
print("OK: GodoOversetRun.java (tryb hold_sine) i run_vv_ctrl.py zapisane w", VV)
