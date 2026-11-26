r"""krok1_faltinsen.py - model Faltinsena (krok 2, faltinsen_model\faltinsen_plant.py, TYLKO ODCZYT) w porownaniu z Godø: PID1/2/3 i regulator I.
Warianty modelu:  B = bez dopasowania (CD0 = 0,0104);  E = B + staly dodatek oporu w fali dCD = 0,0016 (krok 2, pkt 5.3; woda spokojna bez dodatku).
Obciazenie:       NASZE = caly ciezar 12,5 t na placie (CL 0,642);  GODO = 90 % ciezaru (CL 0,578 przy rho = 1000), reszta bez zmian.
Jak u Godø: 8 okresow spotkania, srednia z ostatnich 4; 4 fazy fali. Regulator I: 60 okresow, ostatnie 4.
Wynik: KROK1_FALTINSEN.json. Wznawialne (wyniki_falt\*.json), log krok1_faltinsen.log.
"""
import sys, os, json, time, math
sys.dont_write_bytecode = True
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent; OUT = HERE / "wyniki_falt"; LOG = HERE / "krok1_faltinsen.log"
FM = Path(r"T:\NTNU_GODO_CONTROL_20261109\40_MODEL_WIROWY_I_STEROWANIE\faltinsen_model")
sys.path.insert(0, str(FM))
PIDS = {"PID1": (2.01, 0.196), "PID2": (6.63, 1.18), "PID3": (22.3, 7.25), "I": (0.0, 0.196)}
PH = (0.0, 0.5 * math.pi, math.pi, 1.5 * math.pi)
DCD_WAVE = 0.0016


def log(m):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + m + "\n")


def run(model, load, name, phase_i):
    import faltinsen_plant as FP
    q = 0.5 * FP.RHO * FP.U ** 2 * FP.C      # stale modulu ustawiane ZAWSZE (proces roboczy pamieta poprzednie zadanie)
    FP.MASS = (0.9 if load == "GODO" else 1.0) * 12500.0 / (25.6 * 0.312)
    FP.CL_REF = (FP.MASS * FP.G - FP.BUOY) / q if load == "GODO" else 0.642
    wave = name != "CALM"
    kp, ki = PIDS["PID2"] if not wave else PIDS[name]
    cd0 = FP.CD0 + (DCD_WAVE if (model == "E" and wave) else 0.0)
    p = FP.FaltinsenPlant(wave_amp=0.73 if wave else 0.0, wave_phase=PH[phase_i], cd0=cd0)
    TR = FP.TH_REF_DEG
    p.reset(theta_deg=TR); p.cmd = np.radians(TR)
    for _ in range(1000):
        p.step(free_heave=False)
    n_per = 4 if not wave else (60 if name == "I" else 8)
    n_ticks = int(round(n_per * p.Te / (p.tick * p.dt))); integ, rows = 0.0, []
    for k in range(n_ticks):
        e = -p.z; integ += e * p.tick * p.dt
        p.cmd = np.radians(np.clip(TR + kp * e + ki * integ, -7.5, 7.5))
        fx, v0 = 0.0, p.v
        for _ in range(p.tick):
            r = p.step(free_heave=True); fx += r["Fx"]
        rows.append((fx / p.tick * FP.SPAN, p.z, (p.v - v0) / (p.tick * p.dt), r["theta_deg"], r["CL"], r["sub"]))
    a = np.array(rows[-(int(round(4 * p.Te / (p.tick * p.dt))) if wave else 200):])
    return dict(P_W=float(a[:, 0].mean() * FP.U), z_min=float(a[:, 1].min()), z_max=float(a[:, 1].max()), acc=float(np.sqrt(np.mean(a[:, 2] ** 2))),
                th_min=float(a[:, 3].min()), th_max=float(a[:, 3].max()), CL_mean=float(a[:, 4].mean()), CL_min=float(a[:, 4].min()), CL_max=float(a[:, 4].max()),
                CL2_ratio=float(np.mean(a[:, 4] ** 2) / FP.CL_REF ** 2), sub_min_c=float(a[:, 5].min() / FP.C), CL_ref=float(FP.CL_REF), mass_kg_m=float(FP.MASS))


def task(job):
    model, load, name, i = job
    f = OUT / f"{model}__{load}__{name}__ph{i}.json"
    if f.exists():
        return job, "skip"
    t0 = time.time()
    try:
        s = run(model, load, name, i); s.update(model=model, load=load, name=name, phase=i, wall_s=round(time.time() - t0, 1))
        tmp = f.with_suffix(".tmp"); tmp.write_text(json.dumps(s, indent=1)); os.replace(tmp, f)
        log(f"OK   {f.name} {s['wall_s']} s P={s['P_W']:.2f} W"); return job, "ok"
    except Exception as ex:
        import traceback; log(f"BLAD {f.name}: {ex}\n{traceback.format_exc()}"); return job, "err"


def init_worker(cores):
    import psutil
    pr = psutil.Process(); pr.cpu_affinity(cores); pr.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)


if __name__ == "__main__":
    import multiprocessing as mp, psutil
    OUT.mkdir(exist_ok=True)
    load = psutil.cpu_percent(interval=2.0, percpu=True)
    cand = sorted(range(18, 24), key=lambda i: load[i])[:4]; cores = [c for c in cand if load[c] < 60] or cand[:2]
    log(f"START rdzenie {cores}")
    jobs = []
    for ld in ("NASZE", "GODO"):
        for m in ("B", "E"):
            jobs.append((m, ld, "CALM", 0))
            for n in ("PID1", "PID2", "PID3"):
                jobs += [(m, ld, n, i) for i in range(4)]
    for ld in ("NASZE", "GODO"):
        for m in ("B", "E"):
            jobs.append((m, ld, "I", 0))
    with mp.Pool(len(cores), initializer=init_worker, initargs=(cores,)) as pool:
        for job, st in pool.imap_unordered(task, jobs):
            pass
    res = {}
    for ld in ("NASZE", "GODO"):
        for m in ("B", "E"):
            calm = json.loads((OUT / f"{m}__{ld}__CALM__ph0.json").read_text()); key = f"{m}_{ld}"; res[key] = dict(calm_P_W=calm["P_W"], CL_ref=calm["CL_ref"])
            print(f"\nmodel {m}, obciazenie {ld}: woda spokojna {calm['P_W']:.2f} W/pasek, CL {calm['CL_ref']:.3f}")
            for n in ("PID1", "PID2", "PID3", "I"):
                R = [json.loads(f.read_text()) for f in sorted(OUT.glob(f"{m}__{ld}__{n}__ph*.json"))]
                mm = lambda k: float(np.mean([r[k] for r in R]))
                o = dict(n=len(R), P_W=mm("P_W"), pct=100 * (mm("P_W") / calm["P_W"] - 1), acc=mm("acc"), z_min=min(r["z_min"] for r in R), z_max=max(r["z_max"] for r in R),
                         zpp=float(np.mean([r["z_max"] - r["z_min"] for r in R])), th_min=min(r["th_min"] for r in R), th_max=max(r["th_max"] for r in R),
                         CL_min=min(r["CL_min"] for r in R), CL_max=max(r["CL_max"] for r in R), CL2_ratio=mm("CL2_ratio"), sub_min_c=min(r["sub_min_c"] for r in R))
                res[key][n] = o
                print(f"  {n:5s} P {o['P_W']:6.2f} W ({o['pct']:+6.1f} %) | acc {o['acc']:.2f} | z {o['z_min']:+.2f}..{o['z_max']:+.2f} (p-p {o['zpp']:.3f}) | kat {o['th_min']:+.2f}..{o['th_max']:+.2f} | CL {o['CL_min']:.2f}..{o['CL_max']:.2f} | CL2 {o['CL2_ratio']:.3f} | zan.min {o['sub_min_c']:.2f}c")
    (HERE / "KROK1_FALTINSEN.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    log("KONIEC")
