"""mpc_learn_bridge.py - SAMOUCZACE SIE MPC (18.11, prosba Julka 20:21): adaptacyjne MPC (mpc_adapt_bridge.py: RLS na sile nosnej) +
NOWE: czestosc fali NIE jest wpisana na sztywno. Co 1 s z ostatnich 8 s pomiaru sondy szukana jest czestosc spotkania w_e
(dopasowanie sinusoidy metoda najmniejszych kwadratow po siatce w_e 1,5-8 rad/s + doprecyzowanie parabola), potem z relacji fali z dziobu
  w_e = w0 + w0^2 U / g   ->   w0,   k = w0^2 / g   (fala gleboka; Faltinsen (6.198)-(6.199))
i podmiana stalych OME, OM0, K, DT_PROBE w mpc_falt_bridge (z nich liczona przyszla predkosc wody na placie i przesuniecie sondy).
Model MPC (ARX) byl identyfikowany na falach nieregularnych S1-S4, wiec pokrywa rozne czestosci. Pliki wejsciowe bez zmian (kopie, nic nie nadpisuje).
Uzycie: python mpc_learn_bridge.py CASE_DIR W_A KI   |   python mpc_learn_bridge.py - W_A KI test   (MPC_TEST_T = okres fali w tescie, MPC_TEST_A = amplituda)"""
import os, sys, math, json, time
import numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import mpc_adapt_bridge as AB
FB, MK, DT = AB.FB, AB.MK, AB.DT
G, U = MK.G, MK.U


def set_wave_consts(we):
    w0 = (-1 + math.sqrt(1 + 4 * U * we / G)) / (2 * U / G); k = w0 * w0 / G
    FB.OME, FB.OM0, FB.K = we, w0, k; FB.DT_PROBE = k * FB.PROBE_D / we
    return w0, k


class LearnBridge(AB.AdaptBridge):
    def __init__(s):
        super().__init__(); s.n_est = 0; s.we_hist = []

    def est_freq(s):
        t = np.array(s.T[-800:]); e = np.array(s.E[-800:])
        if len(t) < 150 or t[-1] - t[0] < 1.5: return None
        def res(w):
            X = np.c_[np.cos(w * t), np.sin(w * t), np.ones_like(t), t - t.mean()]; c = np.linalg.lstsq(X, e, rcond=None)[0]; return float(np.sum((X @ c - e) ** 2))
        W = np.arange(1.5, 8.0, 0.02); R = np.array([res(w) for w in W]); i = int(np.argmin(R))
        if 0 < i < len(W) - 1:
            a, b, c = R[i - 1], R[i], R[i + 1]; den = a - 2 * b + c; d = 0.5 * (a - c) / den if den > 0 else 0.0
            return float(W[i] + d * 0.02)
        return float(W[i])

    def step(s, seq, t, z, v, th_deg, rate_deg_s, eta, free):
        s.n_est += 1
        if s.n_est % 100 == 0:
            we = s.est_freq()
            if we is not None:
                we_old = FB.OME; w0, k = set_wave_consts(we); s.we_hist.append(we)
                if s.n_est % 500 == 0 or abs(we - we_old) > 0.05:
                    FB.log(f"fala: w_e {we:.3f} rad/s (okres spotkania {2*math.pi/we:.3f} s), w0 {w0:.3f} rad/s (okres fali {2*math.pi/w0:.2f} s), k {k:.4f} 1/m, wyprzedzenie sondy {FB.DT_PROBE:.3f} s")
        return super().step(seq, t, z, v, th_deg, rate_deg_s, eta, free)


if __name__ == "__main__":
    FB.Bridge = LearnBridge; AB.AdaptBridge = LearnBridge
    if "test" in sys.argv:
        Tw = float(os.environ.get("MPC_TEST_T", "4.0")); Aw = float(os.environ.get("MPC_TEST_A", "0.5")); NP = int(os.environ.get("MPC_TEST_PER", "25"))
        Z = MK.Z; FP = MK.FP; Z.FP.T_WAVE = Tw
        br = LearnBridge(); p = Z.FaltinsenPlant(wave_amp=Aw, wave_phase=0.4, **Z.VB)
        cl_eq = (FP.MASS * MK.G - MK.BUOY) / p.q; trim = FP.TH_REF_DEG + float(np.degrees((cl_eq - FP.CL_REF) / (p.slope * p.dcl)))
        p.reset(theta_deg=trim); rows = []; seq = 0; T_REL = 1.9368
        for k in range(int(NP * p.Te / DT)):
            free = p.t >= T_REL - 0.5e-3
            cmd = br.step(seq, p.t, p.z, p.v, math.degrees(p.th), math.degrees(p.w_servo), p.eta_LE(), free); seq += 1
            p.cmd = math.radians(cmd); Ls = Pd = 0.0
            for _ in range(p.tick):
                r = p.step(free_heave=free); Ls += r["L"]; Pd += r["P_drag_W_strip"]
            rows.append((p.t, Pd / p.tick, (Ls / p.tick + MK.BUOY) / FP.MASS - MK.G, p.z))
        a = np.array(rows); out = {}
        for nm, lo, hi in (("pierwsze 4 okresy", T_REL, T_REL + 4 * p.Te), ("ostatnie 4 okresy", a[-1, 0] - 4 * p.Te, a[-1, 0])):
            b = a[(a[:, 0] > lo) & (a[:, 0] <= hi)]
            out[nm] = dict(dP_pct=round(100 * (b[:, 1].mean() / 57.03 - 1), 2), acc_rms=round(float(b[:, 2].std()), 3), z=[round(float(b[:, 3].min()), 3), round(float(b[:, 3].max()), 3)])
        print(json.dumps(dict(T_fali=Tw, A=Aw, we_prawdziwe=round(p.ome, 3), we_wyuczone=round(FB.OME, 3), W_A=MK.W_A, KI=FB.KI, **out, mnoznik_koniec=round(float(br.c[1]), 3))), flush=True)
        sys.exit()
    exec(compile(open(FB.__file__, encoding="utf-8").read().split('if __name__ == "__main__":', 1)[1].replace("\n    ", "\n"), "main", "exec"), vars(FB))
