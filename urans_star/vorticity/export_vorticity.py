"""Stopklatki wirowosci z zapisanych stanow koncowych URANS (opcja 1, zgoda Julka 11.11 14:43).
Kopiuje END_*.sim z overset_runs (oryginaly nietkniete) i uruchamia ExportVorticity.java na rdzeniach 2-9.
Potem uruchamia dokonczenie OVS_CALM_PID2 (rdzenie 2-17), jak w RESUME_after_move2.ps1.
usage: python export_vorticity.py
"""
import json, shutil, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, r"T:\NTNU_GODO_CONTROL_20261109\20_supervisor")
import starrun

HERE = Path(__file__).parent; ROOT = HERE.parent
RUNS = ["OVS_PID_BASE2", "OVS_PID_SINE_A2", "OVS_PID_PRBS1"]
LOG = ROOT / "overnight_chain.log"


def log(m):
    with open(LOG, "a", encoding="utf-8") as f: f.write(time.strftime("%Y-%m-%d %H:%M:%S") + " vorticity: " + m + "\n")


for run in RUNS:
    src = sorted((ROOT / "overset_runs" / run).glob("END_*.sim"))
    if not src: log(run + " brak END_*.sim"); continue
    case = HERE / run; case.mkdir(exist_ok=True)
    if (case / "EXPORT_LOG.json").exists() and "ERROR" not in (case / "EXPORT_LOG.json").read_text(): log(run + " juz zrobione"); continue
    shutil.copy2(src[-1], case / "input.sim"); shutil.copy2(HERE / "ExportVorticity.java", case / "ExportVorticity.java")
    log(run + " start z " + src[-1].name)
    res = starrun.launch(case / "input.sim", case / "ExportVorticity.java", case, cpus=tuple(range(2, 10)), np_=8, timeout_s=3600)
    (case / "input.sim").unlink(missing_ok=True)
    log(run + " koniec: " + ((case / "EXPORT_LOG.json").read_text().replace("\n", " ")[:300] if (case / "EXPORT_LOG.json").exists() else json.dumps(res)[:300]))
    if run == RUNS[0] and (not (case / "EXPORT_LOG.json").exists() or "ERROR" in (case / "EXPORT_LOG.json").read_text()):
        log("blad na pierwszym przebiegu - przerywam stopklatki"); break

calm_run = ROOT / "overset_runs" / "OVS_CALM_PID2"
for f in ("RUN_RESULT.json", "STOP"):
    (calm_run / f).unlink(missing_ok=True)
log("start dokonczenia OVS_CALM_PID2")
py = str(ROOT.parent / ".venv" / "Scripts" / "python.exe")
subprocess.Popen([py, "run_overset_ctrl.py", "OVS_CALM_PID2", str(ROOT / "overset" / "CALM" / "GODO_OVERSET_SETUP_CALM.sim"), ",".join(map(str, range(2, 18))),
                  "mode=pid", "kp_deg_per_m=6.63", "ki_deg_per_m_s=1.18", "t_end_s=4.0", "release_s=1.0", "inner=8", "iface_alpha_lo=0.1", "cfl_max=1.5",
                  "actuator=lag2", "servo_wn_rad_s=40"], cwd=str(ROOT), stdout=open(ROOT / "ovs_calm.out", "a"), stderr=open(ROOT / "ovs_calm.err", "a"),
                 creationflags=subprocess.CREATE_NO_WINDOW)
