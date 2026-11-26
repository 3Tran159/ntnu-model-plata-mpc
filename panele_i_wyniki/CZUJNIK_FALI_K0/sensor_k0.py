"""sensor_k0.py - realistyczny czujnik fali dla sterownika K0 (zarzut R3-2), 13.11.2026. Wszystko "w modelu" (Faltinsen B, obciazenie 90 %), nie w URANS.
K0 (agent D, zaw90.py): kat = trym + PID1(wysokosc) - k * w / U,  w = pionowa predkosc wody na placie.  Tam w jest znane idealnie.
TU: w szacowane z czujnika wzniesienia powierzchni d metrow PRZED krawedzia natarcia (plant.eta_ahead(d)):
   pomiar   eta_m(t) = eta(d, t - opoznienie) + szum bialy (odchylenie sigma), probkowanie 100 Hz (takt sterownika)
   filtr    dolnoprzepustowy Butterwortha 2. rzedu, czestosc graniczna fc; pochodna = roznica wsteczna sygnalu po filtrze
   przelicz w_est = (omega_0 / omega_e) * exp(-k_f * zanurzenie) * d(eta_f)/dt      (fala regularna o znanym okresie; zanurzenie = 1,09 m - z)
   czas     fala dochodzi od czujnika do srodka cieciwy po tau = (d + c/2) / (U + c_fali) = (d + 0,156 m) / 20,16 m/s.
            Zapas = tau - opoznienie - opoznienie filtru (sqrt(2) / (2 pi fc)) - 5 ms (pochodna). Zapas > 0: sygnal jest przetrzymany o (zapas - t_serwo),
            gdzie t_serwo = wyprzedzenie na opoznienie serwa (0 albo 0,05 s). Zapas < 0: sterownik jest spozniony o -zapas.
Protokol jak zaw90.py: 8 okresow spotkania, srednia z ostatnich 4, 4 fazy fali (kazda z innym ziarnem szumu), fala regularna 0,73 m, T 5 s.
Wynik: SENSOR_K0.json (zapis po kazdej konfiguracji, wznowienie pomija gotowe), sensor_k0.log.   Uzycie: python sensor_k0.py [liczba_procesow]"""
import json, sys, time
from pathlib import Path
from multiprocessing import Pool
import numpy as np
from scipy.signal import butter
HERE = Path(__file__).parent; ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "40_MODEL_WIROWY_I_STEROWANIE" / "faltinsen_model"))
import faltinsen_plant as FP
from faltinsen_plant import FaltinsenPlant, U, C, BUOY, G, DEPTH
T_REL, PH, PID1 = 1.9368, (0.0, np.pi / 2, np.pi, 1.5 * np.pi), (2.01, 0.196)
OUT, LOG = HERE / "SENSOR_K0.json", HERE / "sensor_k0.log"
GAINS = (0.25, 0.5, 0.75, 0.87, 1.0)


def run(gain, phase, sensor=None, load=0.9, nper=8, seed=0):
    """sensor=None: idealna znajomosc w (jak zaw90.py).  sensor = dict(d, sigma, latency, fc, t_servo, gain_err, T_assumed)"""
    P = FaltinsenPlant(wave_amp=0.73, wave_phase=phase, load=load); trim = float(np.degrees(P.th_ref)); P.reset(theta_deg=trim)
    dtc = P.tick * P.dt; ie = 0.0; rows = []; rng = np.random.default_rng(seed)
    if sensor:
        s = dict(d=2.0, sigma=0.02, latency=0.02, fc=3.0, t_servo=0.0, gain_err=1.0, T_assumed=5.0); s.update(sensor)
        om0 = 2 * np.pi / s["T_assumed"]; kf = om0 ** 2 / G; ome = om0 + kf * U; cw = om0 / kf
        tau = (s["d"] + 0.5 * C) / (U + cw); fdel = np.sqrt(2) / (2 * np.pi * s["fc"]) + 0.5 * dtc
        margin = tau - s["latency"] - fdel; hold = max(0.0, margin - s["t_servo"]); nh = int(round(hold / dtc)); nl = int(round(s["latency"] / dtc))
        b, a = butter(2, s["fc"] / (0.5 / dtc)); zi = None; raw = []; est = []; ef_prev = None
    for i in range(int(round(nper * P.Te / P.dt))):
        free = P.t >= T_REL - 0.5 * P.dt
        if i % P.tick == 0:
            cmd = trim
            if free: ie = float(np.clip(ie + (-P.z) * dtc, -1, 1)); cmd = trim + PID1[0] * (-P.z) + PID1[1] * ie
            if sensor:
                raw.append(P.eta_ahead(s["d"]) + s["sigma"] * rng.standard_normal())
                x = raw[max(0, len(raw) - 1 - nl)]                                   # opoznienie czujnika i przetwarzania
                if zi is None: zi = [x * (1 - b[0]), x * (a[2] - b[2])]              # stan poczatkowy filtru = stan ustalony dla x
                y = b[0] * x + zi[0]; zi[0] = b[1] * x - a[1] * y + zi[1]; zi[1] = b[2] * x - a[2] * y    # Butterworth 2. rzedu (postac II transponowana)
                de = 0.0 if ef_prev is None else (y - ef_prev) / dtc; ef_prev = y
                est.append(s["gain_err"] * (om0 / ome) * np.exp(-kf * (DEPTH - P.z)) * de)
                wg = est[max(0, len(est) - 1 - nh)]
            else:
                wg = float(np.mean(P.gust(P.F.xc, P.t)[1]))
            if gain: cmd -= gain * float(np.degrees(wg / U))
            P.cmd = np.radians(float(np.clip(cmd, -7.5, 7.5)))
            w_true = float(np.mean(P.gust(P.F.xc, P.t)[1]))
        r = P.step(free_heave=free)
        rows.append((r["t"], r["theta_deg"], r["rate_deg_s"], r["z"], (r["L"] + BUOY) / P.mass - G, r["P_drag_W_strip"], r["sub_true"], wg if gain or sensor else 0.0, w_true))
    A = np.array(rows); w = A[:, 0] > A[-1, 0] - 4 * P.Te; B = A[w]
    o = dict(P_W=float(B[:, 5].mean()), acc_rms=float(B[:, 4].std()), acc_peak=float(np.abs(B[:, 4]).max()), z_p2p=float(np.ptp(B[:, 3])), sub_min=float(B[:, 6].min()),
             th_min=float(B[:, 1].min()), th_max=float(B[:, 1].max()), rate_rms=float(np.sqrt(np.mean(B[:, 2] ** 2))), rate_max=float(np.abs(B[:, 2]).max()),
             sat_pct=float(100 * np.mean((np.abs(B[:, 2]) > 89.9) | (np.abs(B[:, 1]) > 7.49))), w_err_rms=float(np.sqrt(np.mean((B[:, 7] - B[:, 8]) ** 2))), w_true_rms=float(B[:, 8].std()))
    if sensor: o.update(tau_s=float(tau), filt_delay_s=float(fdel), margin_s=float(margin), hold_s=float(nh * dtc))
    return o


def calm(load=0.9):
    P = FaltinsenPlant(wave_amp=0.0, load=load); trim = float(np.degrees(P.th_ref)); P.reset(theta_deg=trim); ie = 0.0; p = []
    for i in range(8000):
        if i % P.tick == 0 and P.t > 1.0: ie += (-P.z) * 0.01; P.cmd = np.radians(trim + PID1[0] * (-P.z) + PID1[1] * ie)
        r = P.step(free_heave=P.t > 1.0)
        if P.t > 6.0: p.append(r["P_drag_W_strip"])
    return float(np.mean(p))


S0 = dict(d=2.0, sigma=0.02, latency=0.02, fc=3.0)
CONFIGS = [("idealny (jak zaw90.py)", None),
           ("d 1 m, bez szumu", dict(S0, d=1.0, sigma=0.0)), ("d 2 m, bez szumu", dict(S0, sigma=0.0)), ("d 3 m, bez szumu", dict(S0, d=3.0, sigma=0.0)),
           ("d 2 m, szum 1 cm", dict(S0, sigma=0.01)), ("d 2 m, szum 2 cm (bazowy)", dict(S0)), ("d 2 m, szum 5 cm", dict(S0, sigma=0.05)),
           ("d 1 m, szum 2 cm", dict(S0, d=1.0)), ("d 3 m, szum 2 cm", dict(S0, d=3.0)),
           ("bazowy, filtr 1,5 Hz", dict(S0, fc=1.5)), ("bazowy, filtr 5 Hz", dict(S0, fc=5.0)), ("d 3 m, szum 5 cm, filtr 1,5 Hz", dict(S0, d=3.0, sigma=0.05, fc=1.5)),
           ("bazowy, opoznienie 50 ms", dict(S0, latency=0.05)), ("bazowy, opoznienie 100 ms", dict(S0, latency=0.10)),
           ("bazowy, wzmocnienie -20 %", dict(S0, gain_err=0.8)), ("bazowy, wzmocnienie +20 %", dict(S0, gain_err=1.2)),
           ("bazowy, zalozony okres fali 6 s zamiast 5 s", dict(S0, T_assumed=6.0)), ("bazowy, zalozony okres fali 4 s zamiast 5 s", dict(S0, T_assumed=4.0)),
           ("d 3 m, szum 2 cm, wyprzedzenie serwa 50 ms", dict(S0, d=3.0, t_servo=0.05)), ("d 3 m, bez szumu, wyprzedzenie serwa 50 ms", dict(S0, d=3.0, sigma=0.0, t_servo=0.05))]


def job(a):
    name, sensor, g, j = a; return name, g, j, run(g, PH[j], sensor, seed=1000 * j + int(100 * g))


if __name__ == "__main__":
    nproc = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    out = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    if "calm_90_W" not in out: out["calm_90_W"] = calm(); OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    ref = out["calm_90_W"]
    with Pool(nproc) as pool:
        for name, sensor in CONFIGS:
            if name in out: continue
            t0 = time.time(); res = pool.map(job, [(name, sensor, g, j) for g in GAINS for j in range(4)]); cfg = {}
            for g in GAINS:
                rr = [r for (_, gg, _, r) in res if gg == g]; m = {k: float(np.mean([r[k] for r in rr])) for k in rr[0]}
                for k in ("acc_peak", "rate_max", "th_max", "sat_pct"): m[k] = float(max(r[k] for r in rr))
                for k in ("sub_min", "th_min"): m[k] = float(min(r[k] for r in rr))
                m["dP_pct"] = 100 * (m["P_W"] / ref - 1); m["dP_spread_pct"] = float(100 * np.ptp([r["P_W"] for r in rr]) / ref); cfg[str(g)] = m
            out[name] = dict(sensor=sensor, gains=cfg); OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
            line = " | ".join(f"k {g}: {cfg[str(g)]['dP_pct']:+.1f} %, {cfg[str(g)]['acc_rms']:.2f} m/s2, kat RMS {cfg[str(g)]['rate_rms']:.0f} deg/s" for g in GAINS)
            with open(LOG, "a", encoding="utf-8") as f: f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + name + ": " + line + "\n")
            print(f"{name} [{time.time() - t0:.0f} s]: {line}", flush=True)
    print("gotowe")
