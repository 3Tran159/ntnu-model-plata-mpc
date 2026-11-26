"""widmo_sensor.py - C-6.1 (recenzja runda 6): filtr pomiar eta -> pionowa predkosc wody na placie ZALEZNY OD CZESTOSCI, test na widmie S1-S4.
Wszystko "w modelu" (Faltinsen B, 90 %). Te same realizacje fal co widmo_s1s4.py koordynatora: seed 100 * nr stanu + s, pasmo 0,5-3 wp, 80 skladowych.
Czujnik: wzniesienie powierzchni d metrow przed krawedzia natarcia, 100 Hz, opoznienie t_op, szum bialy sigma.
Estymatory predkosci wody w na placie (srednia po cieciwie, glebokosc 1,09 m - z):
  ideal   - znana dokladnie (jak K0 koordynatora)
  naiwny  - sensor_k0.py: Butterworth 2. rzedu 3 Hz + pochodna + stale omega_0/omega_e, zanik i czas dojscia dla JEDNEGO okresu fali (Tp stanu albo 5 s)
  FIR     - filtr o skonczonej odpowiedzi impulsowej (L probek po 10 ms), wspolczynniki z najmniejszych kwadratow (filtr Wienera, przyczynowy):
            minimalizuje sredni kwadrat bledu w - sum_j h_j eta_m[n-j] na syntetycznym zapisie fal (INNE ziarna niz w tescie) + sigma^2 sum h_j^2 (szum).
            "ogolny": jeden filtr na wszystkie stany (zapis = S1..S4 po kolei, kazdy unormowany do tej samej wariancji w); "stanowy": osobny dla kazdego stanu.
Tryby:  python widmo_sensor.py offline          -> SENSOR_WIDMO_OFFLINE.json  (blad oszacowania w na zapisie 1200 s, bez modelu plata)
        python widmo_sensor.py loop K N [T]     -> wyniki_widmo/<estymator>__<stan>__s<seed>.json  (petla zamknieta K0 85 %, K-ty z N procesow, T s symulacji)
        python widmo_sensor.py summary          -> SENSOR_WIDMO.json"""
import json, sys, time
from pathlib import Path
import numpy as np
from scipy.signal import butter, lfilter
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE.parent / "WIDMO_S1S4")); sys.path.insert(0, str(HERE.parent / "ZAWIESZENIE"))
import widmo_s1s4 as W
Z = W.Z; FP, U, G, BUOY = W.FP, W.U, W.G, W.BUOY
C, DEPTH, DT = 0.312, 1.09, 0.01
SEAS = W.SEAS; RES = HERE / "wyniki_widmo"
SENS = dict(d=2.0, sigma=0.02, latency=0.02)


def comps(sea, seed):
    """skladowe fali dokladnie jak w widmo_s1s4.run (ta sama realizacja)"""
    FP.MASS = W.LOAD * Z.MASS100; P = Z.FaltinsenPlant(**Z.VB); Hs, Tp = SEAS[sea]; wp = 2 * np.pi / Tp
    P.set_irregular(Hs=Hs, Tp=Tp, gamma=3.3, seed=seed, N=80, wmin=0.5 * wp, wmax=3.0 * wp); return P


def signals(P, d, T, t0=0.0):
    """zapis 100 Hz: eta w czujniku (bez opoznienia i szumu) i prawdziwa w na placie (z = 0)"""
    I = P.irr; t = t0 + np.arange(int(round(T / DT))) * DT; ph = -I["we"][:, None] * t[None, :] + I["eps"][:, None]
    eta = (I["a"][:, None] * np.cos(-I["kx"][:, None] * d + ph)).sum(0)
    A = I["a"] * I["w"] * np.exp(-I["k"] * DEPTH); w = np.zeros(len(t))
    for x in P.F.xc: w += (A[:, None] * np.sin(I["kx"][:, None] * x + ph)).sum(0)
    return t, eta, w / len(P.F.xc)


def design_fir(seas, d, sigma, latency, L=60, T=300.0):
    nl = int(round(latency / DT)); R = np.zeros((L, L)); r = np.zeros(L)
    for sea in seas:
        P = comps(sea, 9000 + int(sea[1])); _, eta, w = signals(P, d, T); sc = 1.0 / w.std(); eta, w = eta * sc, w * sc      # kazdy stan z ta sama waga
        m = np.roll(eta, nl); n0 = L + nl; X = np.stack([m[n0 - j: len(m) - j] for j in range(L)], axis=1); y = w[n0:]
        R += X.T @ X / len(y); r += X.T @ y / len(y); R += np.eye(L) * (sigma * sc) ** 2
    return np.linalg.solve(R, r)


class Est:
    """estymator w czasie rzeczywistym: push(eta_m) co 10 ms -> w_est (dla z = 0); kind: 'naiwny' albo 'FIR'"""
    def __init__(self, kind, d, latency, T_assumed=5.0, h=None, fc=3.0):
        self.kind, self.h = kind, h; self.buf = []
        if kind == "naiwny":
            om0 = 2 * np.pi / T_assumed; kf = om0 ** 2 / G; ome = om0 + kf * U; tau = (d + 0.5 * C) / (U + om0 / kf)
            self.gain = om0 / ome * np.exp(-kf * DEPTH); self.kf = kf; fdel = np.sqrt(2) / (2 * np.pi * fc) + 0.5 * DT
            self.nh = int(round(max(0.0, tau - latency - fdel) / DT)); self.b, self.a = butter(2, fc / (0.5 / DT)); self.zi = None; self.yp = None; self.est = []

    def push(self, x):
        if self.kind == "FIR":
            self.buf.append(x); L = len(self.h)
            if len(self.buf) > L: self.buf.pop(0)
            b = self.buf[::-1]; return float(np.dot(self.h[:len(b)], b))
        b, a = self.b, self.a
        if self.zi is None: self.zi = [x * (1 - b[0]), x * (a[2] - b[2])]
        y = b[0] * x + self.zi[0]; self.zi[0] = b[1] * x - a[1] * y + self.zi[1]; self.zi[1] = b[2] * x - a[2] * y
        de = 0.0 if self.yp is None else (y - self.yp) / DT; self.yp = y; self.est.append(self.gain * de)
        return self.est[max(0, len(self.est) - 1 - self.nh)]


def make_est(name, sea, d, sigma, latency):
    if name == "naiwny_Tp": return Est("naiwny", d, latency, T_assumed=SEAS[sea][1])
    if name == "naiwny_5s": return Est("naiwny", d, latency, T_assumed=5.0)
    if name == "FIR_ogolny": return Est("FIR", d, latency, h=design_fir(list(SEAS), d, sigma, latency))
    if name == "FIR_stanowy": return Est("FIR", d, latency, h=design_fir([sea], d, sigma, latency))
    raise ValueError(name)


def offline():
    out = {}
    for d in (1.0, 2.0, 3.0):
        for sea in SEAS:
            P = comps(sea, 100 * int(sea[1]) + 0); t, eta, w = signals(P, d, 1200.0); rng = np.random.default_rng(7)
            nl = int(round(SENS["latency"] / DT)); m = np.roll(eta, nl) + SENS["sigma"] * rng.standard_normal(len(eta))
            for name in ("naiwny_5s", "naiwny_Tp", "FIR_ogolny", "FIR_stanowy"):
                E = make_est(name, sea, d, SENS["sigma"], SENS["latency"]); we = np.array([E.push(x) for x in m]); s = slice(500, None)
                e = we[s] - w[s]; lag = np.arange(-30, 31); cc = [np.mean(we[500 + 30 + l: len(w) - 30 + l] * w[500 + 30: len(w) - 30]) for l in lag]; lbest = int(lag[int(np.argmax(cc))])
                out[f"d{d:g}|{sea}|{name}"] = dict(err_rms=float(e.std()), w_rms=float(w[s].std()), err_rel_pct=float(100 * e.std() / w[s].std()),
                                                  gain=float(np.dot(we[s], w[s]) / np.dot(w[s], w[s])), lag_ms=float(10 * lbest), corr=float(np.corrcoef(we[s], w[s])[0, 1]))
                print(f"d {d:g} m {sea} {name:12s}: blad {out[f'd{d:g}|{sea}|{name}']['err_rel_pct']:5.1f} % RMS w (w RMS {w[s].std():.3f} m/s), wzmocnienie {out[f'd{d:g}|{sea}|{name}']['gain']:.2f}, spoznienie {10 * lbest:+d} ms, korelacja {out[f'd{d:g}|{sea}|{name}']['corr']:.3f}", flush=True)
    (HERE / "SENSOR_WIDMO_OFFLINE.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


def run(estname, sea, seed, d=2.0, sigma=0.02, latency=0.02, gain=0.85, T_SIM=360.0, T_SKIP=60.0):
    P = comps(sea, 100 * int(sea[1]) + seed); cl_eq = (FP.MASS * G - BUOY) / P.q; trim = FP.TH_REF_DEG + float(np.degrees((cl_eq - FP.CL_REF) / (P.slope * P.dcl)))
    P.reset(theta_deg=trim); ie = 0.0; n = int(round(T_SIM / P.dt)); rec = np.zeros((n // 10, 7)); j = 0; rng = np.random.default_rng(50000 + seed)
    E = None if estname == "ideal" else make_est(estname, sea, d, sigma, latency); nl = int(round(latency / DT)); raw = []; kbar = (2 * np.pi / SEAS[sea][1]) ** 2 / G
    for i in range(n):
        free = P.t >= 1.0
        if i % P.tick == 0:
            cmd = trim
            if free: ie = float(np.clip(ie + (-P.z) * P.tick * P.dt, -1, 1)); cmd = trim + W.PID1[0] * (-P.z) + W.PID1[1] * ie
            wt = float(np.mean(P.gust(P.F.xc, P.t)[1]))
            if E is None: wg = wt
            else:
                raw.append(P.eta_ahead(d) + sigma * rng.standard_normal()); wg = E.push(raw[max(0, len(raw) - 1 - nl)]) * float(np.exp(kbar * P.z))   # poprawka zaniku na polozenie plata (dla czestosci szczytu)
            cmd -= gain * float(np.degrees(wg / U)); P.cmd = np.radians(float(np.clip(cmd, -7.5, 7.5)))
        r = P.step(free_heave=free)
        if i % 10 == 9:
            rec[j] = (r["t"], r["z"], r["theta_deg"], (r["L"] + BUOY) / FP.MASS - G, r["P_drag_W_strip"], r["sub_true"], wg - wt); j += 1
    b = rec[:j]; b = b[b[:, 0] > T_SKIP]; acc = b[:, 3]; thr = np.gradient(b[:, 2], 0.01)
    return dict(est=estname, sea=sea, seed=seed, d=d, sigma=sigma, latency=latency, gain=gain, T_s=float(b[-1, 0] - b[0, 0]), P_W=float(b[:, 4].mean()), acc_rms=float(acc.std()),
                acc_wk_rms=float(W.iso_weight(acc, 100.0, "Wk").std()), acc_peak=float(np.abs(acc).max()), z_std=float(b[:, 1].std()), sub_min=float(b[:, 5].min()),
                t_below_1c_pct=float(100 * np.mean(b[:, 5] < C)), sat_pct=float(100 * np.mean(np.abs(b[:, 2]) > 7.49)), rate_rms_deg_s=float(thr.std()), w_err_rms=float(b[:, 6].std()))


JOBS = [(e, s, 0, d) for s in SEAS for (e, d) in (("ideal", 2.0), ("naiwny_Tp", 2.0), ("FIR_ogolny", 2.0), ("FIR_ogolny", 3.0))]

if __name__ == "__main__":
    if sys.argv[1] == "offline": offline()
    elif sys.argv[1] == "loop":
        k, nw = int(sys.argv[2]), int(sys.argv[3]); T = float(sys.argv[4]) if len(sys.argv) > 4 else 360.0; RES.mkdir(exist_ok=True)
        for idx, (e, s, sd, d) in enumerate(JOBS):
            f = RES / f"{e}_d{d:g}__{s}__s{sd}.json"
            if idx % nw != k or f.exists(): continue
            t0 = time.time(); r = run(e, s, sd, d=d, T_SIM=T); f.write_text(json.dumps(r), encoding="utf-8")
            with open(HERE / "widmo_sensor.log", "a", encoding="utf-8") as fl:
                fl.write(time.strftime("%Y-%m-%d %H:%M:%S ") + f"{e} d{d:g} {s} s{sd}: P {r['P_W']:.2f} W, z'' RMS {r['acc_rms']:.3f} (Wk {r['acc_wk_rms']:.3f}), blad w {r['w_err_rms']:.3f} m/s, zan.min {r['sub_min']:.2f}, {time.time() - t0:.0f} s\n")
    elif sys.argv[1] == "summary":
        ref = W.calm_ref(); rows = [json.loads(p.read_text()) for p in sorted(RES.glob("*.json"))]; out = dict(P_calm_90_W=ref, runs=rows)
        for r in rows: r["dP_pct"] = 100 * (r["P_W"] / ref - 1); print(f"{r['est']:12s} d{r['d']:g} {r['sea']}: {r['dP_pct']:+6.1f} %, z'' RMS {r['acc_rms']:.3f}, Wk {r['acc_wk_rms']:.3f}, szczyt {r['acc_peak']:.2f}, blad w {r['w_err_rms']:.3f}, kat {r['rate_rms_deg_s']:.1f} deg/s, zan.min {r['sub_min']:.2f}, <1c {r['t_below_1c_pct']:.2f} %")
        (HERE / "SENSOR_WIDMO.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
