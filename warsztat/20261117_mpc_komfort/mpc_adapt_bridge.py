"""mpc_adapt_bridge.py - ADAPTACYJNE MPC (17.11, prosba Julka 15:39): ten sam MPC co mpc_falt_bridge.py, ale model sily nosnej (ARX)
poprawiany na biezaco rekurencyjnymi najmniejszymi kwadratami (RLS) z zapominaniem. "Pomiar" sily nosnej = z akcelerometru:
L = m (dv/dt + g) - B  (jak akcelerometr / tensometry na wsporniku na prawdziwej lodzi). Co 1 s MPC jest przebudowywany na nowym modelu.
Model oporu bez zmian (z Faltinsena B). Zabezpieczenia: wspolczynniki trzymane w [0,3; 3] x wartosc bazowa (sumy grup), blad nie-skonczony -> powrot.
Uzycie: python mpc_adapt_bridge.py CASE_DIR W_A KI   |   python mpc_adapt_bridge.py - W_A KI test
Zmienne: MPC_LAMBDA (0.9995 = pamiec ok. 20 s), MPC_BAD_LIFT (test: mnoznik czesci dynamicznej ARX na starcie, np. 0.7), MPC_ADAPT (1/0)."""
import os, sys, math, json, time
import numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import mpc_falt_bridge as FB
MK, DT, NL, NW = FB.MK, FB.DT, FB.NL, FB.NW
LAM = float(os.environ.get("MPC_LAMBDA", "0.9995")); BAD = float(os.environ.get("MPC_BAD_LIFT", "1.0")); ADAPT = os.environ.get("MPC_ADAPT", "1") == "1"
SIG = 50.0                                                     # zakladany szum "pomiaru" sily [N/m]


class AdaptBridge(FB.Bridge):
    def __init__(s):
        super().__init__()
        s.a0 = s.m["arx"].copy(); s.ab = s.a0.copy(); s.ab[1:] *= BAD; s.c = np.array([s.ab[0], 1.0]); s.set_arx(s.cur())
        s.P = np.diag([1000.0 ** 2, 0.3 ** 2]) / SIG ** 2                    # a priori: przesuniecie +-1000 N/m, mnoznik +-30 %
        s.TH, s.V, s.WF = [], [], []; s.n_upd = 0; s.err2 = []

    def cur(s):
        a = s.ab.copy(); a[0] = s.c[0]; a[1:] *= s.c[1]; return a

    def set_arx(s, a):
        m = dict(s.m); m["arx"] = a; m["l0"] = a[0] + m["thr"] * a[1:1 + NL].sum(); s.m = m
        U = s.mpc.Uprev; s.mpc = MK.MPC(m, s.H, s.BLK); s.mpc.Uprev = U

    def rls(s, phi, y):
        x = np.array([1.0, phi[1:] @ s.ab[1:]]); e = y - x @ s.c
        Pp = s.P @ x; k = Pp / (LAM + x @ Pp); c = s.c + k * e; s.P = (s.P - np.outer(k, Pp)) / LAM
        if not np.all(np.isfinite(c)) or not (0.5 <= c[1] <= 2.0):
            FB.log(f"RLS: odrzucam krok (mnoznik {c[1]:.3f})"); return
        s.c = c; s.m["arx"] = s.cur(); s.err2.append(e * e)

    def step(s, seq, t, z, v, th_deg, rate_deg_s, eta, free):
        th = math.radians(th_deg)
        if free and ADAPT and len(s.V) > max(NL, NW):
            Lm = MK.MASS * ((v - s.V[-1]) / DT + MK.G) - MK.BUOY             # sila z akcelerometru za poprzedni takt
            phi = np.r_[1.0, np.array(s.TH[-NL:])[::-1], np.array(s.V[-NL:])[::-1], np.array(s.WF[-NW:])[::-1]]
            s.rls(phi, Lm); s.n_upd += 1
            if s.n_upd % 100 == 0:
                a = s.m["arx"]; s.set_arx(a)
                FB.log(f"RLS t {t:.2f}: mnoznik sily dynamicznej {s.c[1]:.3f}, przesuniecie {s.c[0]-s.a0[0]:+.0f} N/m, suma dL/dth {a[1:1+NL].sum():.0f} (Faltinsen {s.a0[1:1+NL].sum():.0f}), "
                       f"blad RMS {math.sqrt(np.mean(s.err2[-100:])) if s.err2 else 0:.0f} N/m")
        b, A = s.wave(); wf = A * FB.OM0 * np.exp(-FB.K * MK.DEPTH) * np.sin(FB.K * MK.XQ - FB.OME * t + b)
        s.TH.append(th); s.V.append(v); s.WF.append(wf); s.TH, s.V, s.WF = s.TH[-64:], s.V[-64:], s.WF[-64:]
        return super().step(seq, t, z, v, th_deg, rate_deg_s, eta, free)


if __name__ == "__main__":
    FB.Bridge = AdaptBridge
    if "test" in sys.argv:
        br = AdaptBridge(); Z = MK.Z; p = Z.FaltinsenPlant(wave_amp=0.727, wave_phase=0.4, **Z.VB); FP = MK.FP
        cl_eq = (FP.MASS * MK.G - MK.BUOY) / p.q; trim = FP.TH_REF_DEG + float(np.degrees((cl_eq - FP.CL_REF) / (p.slope * p.dcl)))
        p.reset(theta_deg=trim); rows = []; seq = 0; T_REL = 1.9368; NP = int(os.environ.get("MPC_TEST_PER", "25"))
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
        print(json.dumps(dict(W_A=MK.W_A, KI=FB.KI, BAD=BAD, ADAPT=ADAPT, LAM=LAM, **out, mnoznik_koniec=round(float(br.c[1]), 3), dLdth_koniec=round(float(br.m["arx"][1:1 + NL].sum())), dLdth_baza=round(float(br.a0[1:1 + NL].sum())))), flush=True)
        sys.exit()
    sys.argv = [a for a in sys.argv]
    exec(compile(open(FB.__file__, encoding="utf-8").read().split('if __name__ == "__main__":', 1)[1].replace("\n    ", "\n"), "main", "exec"), vars(FB))
