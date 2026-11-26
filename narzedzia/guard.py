"""Run guard for unattended STAR-CCM+ cases (keep-awake + watchdog + one automatic relaunch).

- Keeps Windows awake while any watched case runs: SetThreadExecutionState(ES_CONTINUOUS|ES_SYSTEM_REQUIRED).
  This is a per-process request (no power settings are changed); it ends when the guard exits.
  It does NOT stop sleep on lid close / manual sleep / Windows Update restart.
- Watchdog every 60 s per case:
    DONE   : FC_RESULT.json present
    FAILED : ERROR.json present, or the run_case supervisor is gone without FC_RESULT.json
    HUNG   : FC_STATE.json not updated for > hang_s while the supervisor is alive -> process tree killed
  FAILED/HUNG -> relaunched once from the frozen source checkpoint with identical properties and cores
  (the macro does not checkpoint mid-run yet, so a relaunch restarts the case).
- Status: 30_runs/GUARD_STATUS.json, log: 30_runs/guard.log
usage: python guard.py NAME1 NAME2 ...      (names = case prefixes, e.g. MAP_FF FIXED_LONG)
"""
import ctypes, json, subprocess, sys, time
from pathlib import Path

ROOT = Path(r"T:\NTNU_GODO_CONTROL_20261109")
RUNS = ROOT / "30_runs"
RUNCASE = ROOT / "20_supervisor" / "run_case.py"
HANG_S = 1500
MAX_RELAUNCH = 1
FLAG = subprocess.CREATE_NO_WINDOW


def log(msg):
    with open(RUNS / "guard.log", "a", encoding="utf8") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")


def keep_awake(on):
    ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if on else 0))


def ps(cmd):
    return subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True,
                          creationflags=FLAG).stdout


def supervisors():
    """{case_prefix: pid} of running run_case.py processes."""
    out = ps("Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
             "Where-Object {$_.CommandLine -like '*run_case.py*'} | "
             "ForEach-Object { \"$($_.ProcessId)|$($_.CommandLine)\" }")
    res = {}
    for line in out.splitlines():
        if "|" in line:
            pid, cl = line.split("|", 1)
            parts = cl.split()
            for i, p in enumerate(parts):
                if p.strip('"').endswith("run_case.py") and i + 1 < len(parts):
                    res[parts[i + 1]] = int(pid)
    return res


def kill_tree(pid):
    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, creationflags=FLAG)


def newest(prefix):
    """Newest case for a prefix; an exact case-directory name is also accepted (its relaunches are newer)."""
    c = sorted(p for p in RUNS.glob(prefix + "_2*") if p.is_dir())
    if c:
        return c[-1]
    return RUNS / prefix if (RUNS / prefix).is_dir() else None


def relaunch(name, case):
    s = json.loads((case / "RUN_SUMMARY.json").read_text())
    props = s["properties"]
    extra = ["%s=%s" % (k, v) for k, v in props.items()
             if k not in ("mode", "steps", "stop_file")]
    args = [sys.executable, str(RUNCASE), name,
            s["mode"], str(s["steps"]), ",".join(map(str, s["cpus"]))] + extra
    out = open(RUNS / ("launch_%s.out" % name), "ab")
    subprocess.Popen(args, cwd=str(RUNCASE.parent), stdout=out, stderr=subprocess.STDOUT, creationflags=FLAG)
    log("RELAUNCH %s from %s" % (name, case.name))


def main():
    names = sys.argv[1:]
    relaunched = {n: 0 for n in names}; dead = {n: 0 for n in names}
    keep_awake(True)
    log("guard start: " + ", ".join(names))
    try:
        while True:
            sup = supervisors()
            status, active = {}, 0
            for n in names:
                c = newest(n)
                st = {"case": str(c) if c else None}
                if c is None:
                    st["state"] = "MISSING"
                elif (c / "FC_RESULT.json").exists():
                    st["state"] = "DONE"; st["result"] = json.loads((c / "FC_RESULT.json").read_text())
                else:
                    fs = c / "FC_STATE.json"
                    age = time.time() - fs.stat().st_mtime if fs.exists() else time.time() - c.stat().st_mtime
                    st["state_age_s"] = round(age)
                    try:
                        st["progress"] = {k: json.loads(fs.read_text()).get(k) for k in ("step", "of", "time_s", "CL")}
                    except Exception:
                        pass
                    dead[n] = 0 if n in sup else dead[n] + 1; alive = dead[n] < 3  # 3 consecutive misses
                    if (c / "ERROR.json").exists() or not alive:
                        st["state"] = "FAILED"
                    elif age > HANG_S:
                        st["state"] = "HUNG"; kill_tree(sup[n]); log("HUNG %s: killed supervisor tree" % n)
                    else:
                        st["state"] = "RUNNING"; active += 1
                    if st["state"] in ("FAILED", "HUNG"):
                        if relaunched[n] < MAX_RELAUNCH:
                            relaunched[n] += 1; relaunch(n, c); st["state"] = "RELAUNCHED"; active += 1
                        else:
                            log("GIVE UP %s (already relaunched)" % n)
                status[n] = st
            (RUNS / "GUARD_STATUS.json").write_text(json.dumps({"time": time.strftime("%Y-%m-%d %H:%M:%S"),
                                                                "cases": status, "relaunches": relaunched}, indent=1))
            if active == 0:
                log("guard: nothing active, exit")
                break
            time.sleep(60)
    finally:
        keep_awake(False)


if __name__ == "__main__":
    main()
