"""Sequential solver benchmark on the Godø medium mesh (B = 1 m, 112 339 cells, dt = 1 ms), unattended.

Waits until the running CPU-2 probe has written COST_PROBE.json / ERROR.json, then runs (one at a time, 40 steps each):
  GPU np1, GPU np2, CPU np8 (8 least-loaded cores, never 22/23).
During GPU runs nvidia-smi is sampled every 5 s (utilisation, memory, power, clocks) -> runs/<case>/gpu_log.csv.
Summary -> 70_godo_case/BENCH.json (s/step after warm-up, h per encounter period, GPU utilisation).
"""
import csv, json, subprocess, sys, threading, time
from pathlib import Path

HERE = Path(__file__).parent
RUNS = HERE / "runs"
PY = sys.executable
FLAG = subprocess.CREATE_NO_WINDOW
TE = 1.9367999917313226


def ps(cmd):
    return subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, creationflags=FLAG).stdout


def free_cores(n):
    out = ps("$c=Get-Counter '\\Processor(*)\\% Processor Time' -SampleInterval 3 -MaxSamples 1;"
             "$c.CounterSamples|Where-Object{$_.InstanceName -ne '_total'}|ForEach-Object{\"$($_.InstanceName) $($_.CookedValue)\"}")
    load = sorted((float(l.split()[1]), int(l.split()[0])) for l in out.splitlines() if l.strip() and l.split()[0].isdigit())
    return [c for _, c in load if c not in (22, 23)][:n]


def newest(prefix):
    c = sorted(p for p in RUNS.glob(prefix + "*") if p.is_dir())
    return c[-1] if c else None


def sample_gpu(stop, path):
    with open(path, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["t_s", "util_gpu_pct", "util_mem_pct", "mem_used_MiB", "power_W", "sm_clock_MHz"])
        t0 = time.time()
        while not stop.is_set():
            q = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu,utilization.memory,memory.used,power.draw,clocks.sm",
                                "--format=csv,noheader,nounits"], capture_output=True, text=True, creationflags=FLAG).stdout.strip()
            if q:
                w.writerow([round(time.time() - t0, 1)] + [x.strip() for x in q.split(",")]); f.flush()
            stop.wait(5)


def run(tag, cores, np_, gpu):
    before = set(p.name for p in RUNS.iterdir())
    args = [PY, str(HERE / "run_godo.py"), tag, "probe", "1.0", "0.001", "40", ",".join(map(str, cores)), str(np_)] + (["gpu"] if gpu else [])
    stop = threading.Event(); th = None
    p = subprocess.Popen(args, cwd=HERE, stdout=open(HERE / ("bench_%s.out" % tag), "w"), stderr=subprocess.STDOUT, creationflags=FLAG)
    if gpu:
        time.sleep(20)
        new = [d for d in RUNS.iterdir() if d.name not in before]
        if new:
            th = threading.Thread(target=sample_gpu, args=(stop, new[0] / "gpu_log.csv"), daemon=True); th.start()
    p.wait(); stop.set()
    case = newest(tag)
    r = {"tag": tag, "np": np_, "gpu": gpu, "cores": cores, "case": str(case)}
    for f in ("COST_PROBE.json", "ERROR.json"):
        if case and (case / f).exists():
            r[f] = json.loads((case / f).read_text())
    if gpu and case and (case / "gpu_log.csv").exists():
        rows = list(csv.DictReader(open(case / "gpu_log.csv")))
        busy = [float(x["util_gpu_pct"]) for x in rows if x["util_gpu_pct"].replace(".", "").isdigit()]
        r["gpu_util_mean_pct"] = sum(busy) / len(busy) if busy else None
        r["gpu_mem_max_MiB"] = max((float(x["mem_used_MiB"]) for x in rows), default=None)
    return r


def main():
    cpu2 = newest("PROBE_B1_dt0.001_20261109_200304")
    while cpu2 and not ((cpu2 / "COST_PROBE.json").exists() or (cpu2 / "ERROR.json").exists()):
        time.sleep(30)
    res = []
    if cpu2:
        r = {"tag": "CPU_np2", "np": 2, "gpu": False, "case": str(cpu2)}
        for f in ("COST_PROBE.json", "ERROR.json"):
            if (cpu2 / f).exists():
                r[f] = json.loads((cpu2 / f).read_text())
        res.append(r)
    for tag, n, np_, gpu in (("BENCH_GPU1", 1, 1, True), ("BENCH_GPU2", 2, 2, True), ("BENCH_CPU8", 8, 8, False)):
        res.append(run(tag, free_cores(n), np_, gpu))
        (HERE / "BENCH.json").write_text(json.dumps(res, indent=1))
    for r in res:
        cp = r.get("COST_PROBE.json", {})
        r["s_per_step"] = cp.get("solver_s_per_step_after_warmup")
        r["h_per_period"] = cp.get("hours_per_encounter_period")
    (HERE / "BENCH.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
