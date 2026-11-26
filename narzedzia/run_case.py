"""Case runner for the Godo-control integration/evaluation runs (unattended).

usage: python run_case.py <case_name> <mode> <steps> <cpus e.g. 6,7> [key=value ...]
Creates T:\\NTNU_GODO_CONTROL_20261109\\30_runs\\<case_name>_<stamp>\\ with:
  input.sim (copy of the frozen FIXED checkpoint), GodoControl.java, control.properties,
  stdout.log, history.csv / ticks.csv / FC_*.json (written by the macro), RUN_SUMMARY.json.
The macro refuses to overwrite FINAL.sim and never touches the source checkpoint.
"""
import sys, shutil, subprocess, json, time, hashlib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import starrun

ROOT = Path(r"T:\NTNU_GODO_CONTROL_20261109")
SRC = ROOT / "00_source" / "FIXED_FINAL_src.sim"
SRC_SHA = "D3DACBF2FCD0200AB72FB25A9C4CB36DDE74C2EC885A782982EDA574F280398D"
JAVAC = r"C:\Program Files\Eclipse Adoptium\jdk-25.0.3.9-hotspot\bin\javac.exe"
EXT = r"E:\Program Files\Siemens\21.04.009-R8\STAR-CCM+21.04.009-R8\star\lib\java\platform\modules\ext\*"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest().upper()


def main():
    name, mode, steps, cpus = sys.argv[1], sys.argv[2], int(sys.argv[3]), tuple(int(c) for c in sys.argv[4].split(","))
    extra = dict(a.split("=", 1) for a in sys.argv[5:])
    case = ROOT / "30_runs" / ("%s_%s" % (name, time.strftime("%Y%m%d_%H%M%S")))
    case.mkdir(parents=True)
    summary = {"case": str(case), "mode": mode, "steps": steps, "cpus": list(cpus), "star": "2606.0002"}
    if sha(SRC) != SRC_SHA:
        raise SystemExit("source checkpoint hash changed")
    shutil.copy2(SRC, case / "input.sim")
    macro = case / "GodoControl.java"
    shutil.copy2(ROOT / "10_macros" / "GodoControl.java", macro)
    cc = subprocess.run([JAVAC, "-encoding", "UTF-8", "-cp", EXT, "-d", str(case / "compiled"), str(macro)],
                        capture_output=True, text=True)
    if cc.returncode:
        (case / "javac_errors.txt").write_text(cc.stderr)
        raise SystemExit("javac failed")
    props = {"mode": mode, "steps": steps, "tick_steps": 10, "expected_time_s": 3.9230000000004543,
             "cl_target": 0.33154336603961815, "plant_gain_per_deg": 0.0356, "kp": 0.8, "ti_s": 0.15,
             "delta_max_deg": 2.0, "rate_max_deg_s": 30.0, "wall_budget_s": 20000,
             "stop_file": (case / "STOP").as_posix()}
    props.update(extra)
    (case / "control.properties").write_text("\n".join("%s=%s" % kv for kv in props.items()) + "\n")
    summary["properties"] = props
    (case / "RUN_SUMMARY.json").write_text(json.dumps(summary, indent=1))
    res = starrun.launch(case / "input.sim", macro, case, cpus=cpus, np_=int(extra.get("np", 2)),
                         timeout_s=float(props["wall_budget_s"]) + 1800)
    summary["launch"] = res
    for f in ("FC_RESULT.json", "ERROR.json"):
        if (case / f).exists():
            summary[f] = json.loads((case / f).read_text())
    summary["final_sim"] = (case / "FINAL.sim").exists()
    (case / "RUN_SUMMARY.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps({k: summary[k] for k in summary if k != "properties"}, indent=1))


if __name__ == "__main__":
    main()
