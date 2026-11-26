"""Thin, dependency-free STAR-CCM+ batch launcher for the Godo-control work.

- STAR 2606.0002 (21.04.009), same as the FIXED checkpoint and the calibration runs.
- Licence: PoD key and licence path are read at launch from the first line of the old
  hydro_validation log (approved by the user on 2026-11-09). The key is only placed in the
  child's environment (LM_PROJECT, CDLMD_LICENSE_FILE); it is never printed or written.
- Affinity: the star process tree is pinned to the given logical CPUs (default 6,7).
"""
import os, re, subprocess, time, json, sys
from pathlib import Path

CLI = r"E:\Program Files\Siemens\21.04.009-R8\STAR-CCM+21.04.009-R8\star\lib\win64\clang20.1vc14.2-r8\lib\starccm+.exe"
LIC_LOG = Path(r"F:\ntnu\flap_control\hydro_validation_2606_20261102\runs\RunURANSFromSteady_SP_C_20261102_203650.log")
FLAG = subprocess.CREATE_NO_WINDOW


def license_env():
    line = LIC_LOG.open(encoding="utf8", errors="replace").readline()
    env = {}
    for flag, key in (("-podkey", "LM_PROJECT"), ("-licpath", "CDLMD_LICENSE_FILE")):
        m = re.search(re.escape(flag) + r'\s+("[^"]+"|\S+)', line)
        if not m:
            raise RuntimeError("licence flag %s not found in old log" % flag)
        env[key] = m.group(1).strip('"')
    return env


def _ps(cmd):
    return subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True,
                          text=True, creationflags=FLAG).stdout


def bind_tree(root_pid, cpus, priority="High"):
    """Pin root_pid and all descendants to logical CPUs `cpus`. Returns list of (pid, name)."""
    mask = sum(1 << c for c in cpus)
    script = ("$all=@(Get-CimInstance Win32_Process);$ids=@(%d);$t0=($all|Where-Object{$_.ProcessId -eq $ids[0]}).CreationDate;"
              "for($n=0;$n -lt 16;$n++){$old=$ids.Count;"
              "$cd=@{};foreach($q in $all){$cd[[int]$q.ProcessId]=$q.CreationDate};$ids+=@($all|Where-Object{$_.ParentProcessId -in $ids -and $_.CreationDate -ge $t0 -and $cd.ContainsKey([int]$_.ParentProcessId) -and $_.CreationDate -ge $cd[[int]$_.ParentProcessId]}|Select-Object -ExpandProperty ProcessId);"
              "$ids=@($ids|Sort-Object -Unique);if($ids.Count -eq $old){break}};"
              "foreach($i in $ids){try{$p=Get-Process -Id $i -ErrorAction Stop;"
              "$p.ProcessorAffinity=[IntPtr]%d;$p.PriorityClass='%s';\"$i $($p.ProcessName)\"}catch{}}"
              % (root_pid, mask, priority))
    out = _ps(script).strip().splitlines()
    return [tuple(x.split(" ", 1)) for x in out if x.strip()]


def launch(sim, macro, outdir, cpus=(6, 7), np_=1, props=None, timeout_s=3600, extra_env=None,
           gpu=False, poll_s=5):
    """Run `starccm+ -batch macro sim` pinned to cpus; block until exit/timeout. Returns dict."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, **license_env(), "MINI_CASE_DIR": str(outdir)}
    if extra_env:
        env.update(extra_env)
    args = [CLI, "-power", "-np", str(np_), "-cpubind", "off", "-printpids",
            "-nbuserdir", str(outdir / "profile")]
    if gpu:
        args += ["-gpgpu", "auto:1", "-mpi", "intel"]   # same flags as Julek's working GPU runs (0.7 s/step at 500k cells)
    args += ["-batch", str(macro), str(sim)]
    with open(outdir / "stdout.log", "ab") as log:
        p = subprocess.Popen(args, cwd=outdir, env=env, stdout=log, stderr=subprocess.STDOUT,
                             creationflags=FLAG)
        (outdir / "launcher.pid").write_text(str(p.pid))
        t0 = time.time()
        bound = []
        while p.poll() is None and time.time() - t0 < timeout_s:
            time.sleep(poll_s)
            try:
                bound = bind_tree(p.pid, cpus) or bound
            except Exception:
                pass
        if p.poll() is None:
            p.terminate()
    res = {"returncode": p.returncode, "seconds": round(time.time() - t0, 1), "bound": bound,
           "cpus": list(cpus), "np": np_, "gpu": gpu}
    (outdir / "launch_result.json").write_text(json.dumps(res, indent=1))
    return res


if __name__ == "__main__":
    # smoke: python starrun.py <sim> <macro> <outdir> [cpus comma-sep]
    sim, macro, out = sys.argv[1:4]
    cpus = tuple(int(x) for x in (sys.argv[4] if len(sys.argv) > 4 else "6,7").split(","))
    print(launch(sim, macro, out, cpus=cpus))
