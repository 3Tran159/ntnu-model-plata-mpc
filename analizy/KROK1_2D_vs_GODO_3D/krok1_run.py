"""krok1_run.py - Krok 1 (zlecenie B): model wirowy 2D z poprawka na skonczona rozpietosc vs Godø 3D.

Wszystko "w modelu wirowym". Pracuje na KOPII modelu (model_kopia\), oryginal w 40_MODEL_WIROWY_I_STEROWANIE\vortex_env nietkniety.
Warianty:
  V0_2D                 - model 2D bez zmian (odtworzenie EVAL_V2.json)
  V1_ind                - + opor indukowany CDi(t) = CL(t)^2 / (pi * AR * e)            (AR = 25,6 Godø tab. 1; e = 1)
  V2_ind_kappa          - + nachylenie nosnej: zmienna czesc CL mnozona przez kappa = 1 / (1 + a0 / (pi * AR * e)),
                          a0 = nachylenie 2D modelu skalibrowanego na URANS (k * dCL/dtheta); srednie CL bez zmian (ciezar musi byc niesiony)
  V3_ind_kappa_trimlim  - + zakres kata +-7,5 deg liczony od kata trymu (jak u Godø, rys. 5 i 7: kat oscyluje wokol ~0), nie od zera
Przypadki: woda spokojna PID2, PID1/2/3 Godø (4 fazy fali), regulator I, plat sztywny (bez nurzania), polityka TD3_GODO (4 fazy).
Wznowienie: kazdy przypadek -> wyniki\<nazwa>.json; istniejace sa pomijane. Log: krok1_run.log. Maks. 4 procesy, rdzenie 18-23 (najmniej obciazone).
"""
import sys, os, json, time, math
from pathlib import Path
import numpy as np

HERE = Path(__file__).parent; MK = HERE / "model_kopia"; OUT = HERE / "wyniki"; LOG = HERE / "krok1_run.log"
sys.path.insert(0, str(MK))
AR, E_OSW = 25.6, 1.0
VARIANTS = {
    "V0_2D": dict(induced=False, kappa=False, trim_lim=False),
    "V1_ind": dict(induced=True, kappa=False, trim_lim=False),
    "V2_ind_kappa": dict(induced=True, kappa=True, trim_lim=False),
    "V3_ind_kappa_trimlim": dict(induced=True, kappa=True, trim_lim=True),
}
PIDS = {"PID1": (2.01, 0.196), "PID2": (6.63, 1.18), "PID3": (22.3, 7.25), "I": (0.0, 0.196)}   # Godø tab. 3 [deg/m], [deg/(m s)]
PH = (0.0, 0.5 * math.pi, math.pi, 1.5 * math.pi)


def log(msg):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")


def patch_copy():
    """Jedyna zmiana w kopii vortex_plant.py: srodek zakresu kata (th_center, domyslnie 0 = oryginal)."""
    f = MK / "vortex_plant.py"; s = f.read_text(encoding="utf-8")
    if "th_center" in s:
        return
    old = ("        if abs(th_new) > thmax:\n"
           "            th_new = float(np.clip(th_new, -thmax, thmax)); w_ = (th_new - self.th) / dt\n")
    new = ("        thc = getattr(self, \"th_center\", 0.0)   # KROK1: srodek zakresu kata [rad]; 0 = oryginal\n"
           "        if abs(th_new - thc) > thmax:\n"
           "            th_new = float(np.clip(th_new, thc - thmax, thc + thmax)); w_ = (th_new - self.th) / dt\n")
    assert old in s, "nie znaleziono fragmentu do zmiany w kopii vortex_plant.py"
    f.write_text(s.replace(old, new), encoding="utf-8")


def make_plant_cls(induced, kappa, trim_lim):
    import vortex_plant as VP

    class Plant3D(VP.Plant):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            c = self.cal; kmean = (c["k_wave"] + c["k_pitch"] + c["k_heave"]) / 3.0
            self.a0_eff = kmean * self.dcl                      # nachylenie 2D [1/rad] modelu skalibrowanego na URANS
            self.kappa = 1.0 / (1.0 + self.a0_eff / (math.pi * AR * E_OSW))
            if kappa:
                self.cl_scale = self.cl_scale * self.kappa
            if trim_lim:
                self.th_center = self.th_ref
            self.induced = induced

        def step(self, *a, **kw):
            r = super().step(*a, **kw)
            cdi = r["CL"] ** 2 / (math.pi * AR * E_OSW) if self.induced else 0.0
            r["CDi"] = cdi; r["Fx"] = r["Fx"] + cdi * self.q; r["P_drag_W_strip"] = VP.U * r["Fx"] * VP.SPAN
            return r
    return Plant3D


def harm(t, y, om):
    """srednia, amplituda i faza 1. harmonicznej: y ~ m + A cos(om t - phi)"""
    m = y.mean(); c = 2 * np.mean((y - m) * np.cos(om * t)); s = 2 * np.mean((y - m) * np.sin(om * t))
    return float(m), float(math.hypot(c, s)), float(math.atan2(s, c))


def stats(p, VP, rows, n_last):
    a = np.array(rows[-n_last:]); full = np.array(rows)
    D, z, acc, th, CL, cdi, sub, eta, t = (a[:, i] for i in range(9))
    om = p.ome
    _, Az, phz = harm(t, z, om); _, Ae, phe = harm(t, eta, om); mCL, ACL, phC = harm(t, CL, om)
    lag = lambda ph: float((math.degrees(ph - phe) + 180) % 360 - 180)      # + = opoznienie wzgledem wzniesienia fali nad noskiem
    q_strip = p.q * VP.SPAN
    return dict(P_drag_W_strip=float(D.mean() * VP.U), D_N_strip=float(D.mean()), P_ind_W_strip=float(cdi.mean() * q_strip * VP.U),
                z_min_m=float(z.min()), z_max_m=float(z.max()), z_mean_m=float(z.mean()), z_amp1_m=Az, z_lag_deg=lag(phz),
                acc_rms_m_s2=float(np.sqrt(np.mean(acc ** 2))), theta_min_deg=float(th.min()), theta_max_deg=float(th.max()),
                CL_mean=mCL, CL_min=float(CL.min()), CL_max=float(CL.max()), CL_amp1=ACL, CL_lag_deg=lag(phC), CL2_mean=float(np.mean(CL ** 2)),
                sub_min_c=float(sub.min() / VP.C), eta_amp1_m=Ae,
                z_absmax_all_m=float(np.abs(full[:, 1]).max()), sub_min_all_c=float(full[:, 6].min() / VP.C))


def run_pid(variant, name, phase, n_periods=8, wave=True, free=True):
    import vortex_plant as VP
    cfg = VARIANTS[variant]; P = make_plant_cls(**cfg)
    kp, ki = PIDS[name] if name in PIDS else (0.0, 0.0)
    p = P(wave_amp=0.73 if wave else 0.0, wave_phase=phase)
    TR = VP.TH_REF_DEG; lo, hi = (TR - 7.5, TR + 7.5) if cfg["trim_lim"] else (-7.5, 7.5)
    p.beta = phase; p.reset(theta_deg=TR); p.cmd = np.radians(TR)
    for _ in range(1000):
        p.step(free_heave=False)
    n_ticks = int(round(n_periods * p.Te / (p.tick * p.dt))); integ, rows = 0.0, []
    for k in range(n_ticks):
        if free:
            e = 0.0 - p.z; integ += e * p.tick * p.dt
            p.cmd = np.radians(np.clip(TR + kp * e + ki * integ, lo, hi))
        fx, cdi, v0 = 0.0, 0.0, p.v
        for _ in range(p.tick):
            r = p.step(free_heave=free); fx += r["Fx"]; cdi += r["CDi"]
        rows.append((fx / p.tick * VP.SPAN, p.z, (p.v - v0) / (p.tick * p.dt), r["theta_deg"], r["CL"], cdi / p.tick,
                     p.eta_LE() - (p.z - VP.DEPTH), r["eta_LE"], p.t))
    n_last = int(round(4 * p.Te / (p.tick * p.dt))) if wave else 200
    s = stats(p, VP, rows, n_last)
    s.update(kappa=p.kappa, a0_eff_per_rad=p.a0_eff, dcl_model_per_rad=float(p.dcl), n_periods=n_periods, Te_s=p.Te,
             sat_frac=float(np.mean([(abs(x[3] - lo) < 0.02) or (abs(x[3] - hi) < 0.02) for x in rows[-n_last:]])))
    return s


def run_td3(variant, phase):
    import torch, vortex_plant as VP, godo_vortex_env as G
    torch.set_num_threads(1)
    G.Plant = make_plant_cls(**VARIANTS[variant])
    env = G.GodoVortexEnv(random_phase=False, D_cw=4.948694900751607)        # D_cw tylko do nagrody; polityka go nie widzi
    sys.argv = ["x", "td3", "TD3_GODO"]
    import train_rl
    ag = train_rl.Agent(); ag.actor.load_state_dict(torch.load(MK / "runs" / "TD3_GODO" / "best_actor.pt", weights_only=False))
    R, info, term = G.rollout(env, lambda e, o: ag.act(o, True), phase)
    p = env.plant; t0 = 1.0
    rows = [(x["D"], x["z"], x["acc"], x["theta_deg"], x["CL"], x["CL"] ** 2 / (math.pi * AR * E_OSW) if p.induced else 0.0, x["sub"], x["eta"],
             t0 + (i + 1) * p.tick * p.dt) for i, x in enumerate(info)]
    s = stats(p, VP, rows, 776); s.update(term=bool(term), kappa=p.kappa, n_ticks=len(rows))
    return s


def task(job):
    kind, variant, name, phase_i = job
    f = OUT / f"{variant}__{name}__ph{phase_i}.json"
    if f.exists():
        return job, "skip"
    t0 = time.time()
    try:
        if kind == "calm":
            s = run_pid(variant, "PID2", 0.0, n_periods=4, wave=False)
        elif kind == "pid":
            s = run_pid(variant, name, PH[phase_i], n_periods=60 if name == "I" else 8)
        elif kind == "rigid":
            s = run_pid(variant, "RIGID", PH[phase_i], n_periods=6, free=False)
        elif kind == "td3":
            s = run_td3(variant, PH[phase_i])
        s.update(kind=kind, variant=variant, name=name, phase_rad=PH[phase_i], wall_s=round(time.time() - t0, 1))
        tmp = f.with_suffix(".tmp"); tmp.write_text(json.dumps(s, indent=1)); os.replace(tmp, f)
        log(f"OK   {f.name} {s['wall_s']} s  P={s['P_drag_W_strip']:.2f} W")
        return job, "ok"
    except Exception as ex:      # noqa
        import traceback
        log(f"BLAD {f.name}: {ex}\n{traceback.format_exc()}")
        return job, "err"


def init_worker(cores):
    import psutil
    pr = psutil.Process(); pr.cpu_affinity(cores); pr.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)


if __name__ == "__main__":
    import multiprocessing as mp, psutil
    OUT.mkdir(exist_ok=True); patch_copy()
    load = psutil.cpu_percent(interval=2.0, percpu=True)
    cand = sorted(range(18, 24), key=lambda i: load[i])[:4]
    cores = [c for c in cand if load[c] < 60] or cand[:2]
    log(f"START obciazenie rdzeni {[round(x) for x in load]} -> rdzenie {cores}")
    jobs = []
    for v in VARIANTS:
        jobs.append(("calm", v, "CALM_PID2", 0))
        jobs.append(("rigid", v, "RIGID", 0))
    for v in VARIANTS:
        for n in ("PID1", "PID2", "PID3"):
            jobs += [("pid", v, n, i) for i in range(4)]
    for v in ("V0_2D", "V1_ind", "V2_ind_kappa"):
        jobs += [("td3", v, "TD3_GODO", i) for i in range(4)]
    for v in ("V0_2D", "V2_ind_kappa", "V3_ind_kappa_trimlim"):
        jobs.append(("pid", v, "I", 0))
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        jobs = [("calm", "V0_2D", "CALM_PID2", 0), ("pid", "V0_2D", "PID1", 0), ("td3", "V0_2D", "TD3_GODO", 0), ("rigid", "V2_ind_kappa", "RIGID", 0)]
    with mp.Pool(len(cores), initializer=init_worker, initargs=(cores,)) as pool:
        for job, st in pool.imap_unordered(task, jobs):
            print(job, st, flush=True)
    log("KONIEC")
