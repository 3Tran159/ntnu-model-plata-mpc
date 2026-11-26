"""mpc_cel_bridge.py - JEDEN MPC NA WSZYSTKIE PRZEBIEGI (20.11, Julek 11:29: "jeden model MPC, ktorego nie zmieniamy ... ograniczamy zmienne").
To samo samouczace sie MPC co OVS_MPCL_T4_90 (mpc_learn_bridge.py: model ARX z Faltinsena B + RLS sily nosnej + czestosc fali z sondy 3 m),
jedyna zmiana: zamiast stalej wagi komfortu W_A zadany CEL z'' RMS [m/s2]. Petla zewnetrzna co 1 s mierzy z'' RMS z ostatniego okresu spotkania
(z predkosci kadluba, jak akcelerometr) i przestawia W_A: log W_A += 0,5 log(z''_rms / cel), krok <= +-0,3, W_A w [0,01; 2000].
Cel 0 -> W_A = 2000 na stale (najmocniejsze tlumienie, jakie ten MPC umie). Cel < 0 -> W_A = 0 na stale (bez komfortu, "maks").
Uzycie: python mpc_cel_bridge.py CASE_DIR CEL_m_s2 KI   |   python mpc_cel_bridge.py - CEL KI test   (MPC_TEST_T, MPC_TEST_A, MPC_TEST_PER)"""
import os, sys, math, json
import numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
WMIN, WMAX = 0.01, float(os.environ.get("MPC_WA_MAX", "20"))      # 20 = jazda bez oscylacji (OVS_LEVEL_90); 2000 psuje optymalizacje (z'' 0,47 w modelu)
CEL = float(sys.argv[2]); W0 = 0.0 if CEL < 0 else (WMAX if CEL == 0 else 2.2)
sys.argv[2] = str(W0)
import mpc_learn_bridge as LB
AB, FB, MK, DT = LB.AB, LB.FB, LB.MK, LB.DT


class CelBridge(LB.LearnBridge):
    def __init__(s):
        super().__init__(); MK.W_A = W0; s.A = []; s.vprev = None; s.n_cel = 0; s.wa_hist = []

    def step(s, seq, t, z, v, th_deg, rate_deg_s, eta, free):
        if s.vprev is not None and free: s.A.append((v - s.vprev) / DT)
        s.vprev = v; s.A = s.A[-1000:]; s.n_cel += 1
        if CEL > 0 and free and s.n_cel % 100 == 0:
            n = int(round(2 * math.pi / FB.OME / DT))
            if len(s.A) >= 2 * n:
                rms = float(np.std(s.A[-n:]))
                if rms > 1e-6:
                    d = float(np.clip(0.5 * math.log(rms / CEL), -0.3, 0.3)); MK.W_A = float(np.clip(MK.W_A * math.exp(d), WMIN, WMAX)); s.wa_hist.append((t, rms, MK.W_A))
                    if s.n_cel % 500 == 0: FB.log(f"cel z'' {CEL:.3f}: zmierzone {rms:.3f} m/s2 -> W_A {MK.W_A:.3f}")
        return super().step(seq, t, z, v, th_deg, rate_deg_s, eta, free)


if __name__ == "__main__":
    LB.LearnBridge = CelBridge; FB.Bridge = CelBridge; AB.AdaptBridge = CelBridge
    if "test" in sys.argv:
        import psutil; psutil.Process().cpu_affinity([int(os.environ.get("MPC_CORE", "22"))])
        Tw = float(os.environ.get("MPC_TEST_T", "5.0")); Aw = float(os.environ.get("MPC_TEST_A", "0.727")); NP = int(os.environ.get("MPC_TEST_PER", "25"))
        Z = MK.Z; FP = MK.FP; Z.FP.T_WAVE = Tw
        SEA = os.environ.get("MPC_TEST_SEA", ""); SEED = int(os.environ.get("MPC_TEST_SEED", "0")); TSIM = float(os.environ.get("MPC_TEST_TSIM", "180"))
        br = CelBridge()
        if SEA:      # widmo S1-S4: te same realizacje co mpc_komfort.run (seed 100*nr + s); okno t > 30 s
            p, trim = MK.plant(SEA, 100 * int(SEA[1]) + SEED); NSTEP = int(TSIM / DT)
        else:
            p = Z.FaltinsenPlant(wave_amp=Aw, wave_phase=0.4, **Z.VB)
            cl_eq = (FP.MASS * MK.G - MK.BUOY) / p.q; trim = FP.TH_REF_DEG + float(np.degrees((cl_eq - FP.CL_REF) / (p.slope * p.dcl))); NSTEP = int(NP * p.Te / DT)
        p.reset(theta_deg=trim); rows = []; seq = 0; T_REL = 1.9368
        for k in range(NSTEP):
            free = p.t >= T_REL - 0.5e-3
            cmd = br.step(seq, p.t, p.z, p.v, math.degrees(p.th), math.degrees(p.w_servo), p.eta_LE(), free); seq += 1
            p.cmd = math.radians(cmd); Ls = Pd = 0.0
            for _ in range(p.tick):
                r = p.step(free_heave=free); Ls += r["L"]; Pd += r["P_drag_W_strip"]
            g = p.gust(p.F.xc, p.t); rows.append((p.t, Pd / p.tick, (Ls / p.tick + MK.BUOY) / FP.MASS - MK.G, p.z, float(np.mean(g[1]))))
        a = np.array(rows); b = a[a[:, 0] > 30.0] if SEA else a[a[:, 0] > a[-1, 0] - 8 * p.Te]
        if SEA: Tw = SEA + f"s{SEED}"; PC0 = 57.056
        if not np.isfinite(b).all(): print(json.dumps(dict(cel=CEL, sea=SEA, blad="niestabilne")), flush=True); sys.exit()
        acc = b[:, 2] - b[:, 2].mean(); w = b[:, 4] - b[:, 4].mean(); ax = -(b[:, 1] - b[:, 1].mean()) / MK.U / (Z.MASS100 * 0.02)
        out = dict(cel=CEL, cel_g=round(CEL / 9.81, 3), T_fali=Tw, W_A_koniec=MK.W_A, acc_rms=float(acc.std()), zysk_W=float(57.03 - b[:, 1].mean()), zysk_pct=float(100 * (1 - b[:, 1].mean() / 57.03)),
                   ciag_W=float(FP.MASS * 0.02 * np.mean(acc * w)), sufit_W=float(FP.MASS * 0.02 * acc.std() * w.std()), kor=float(np.corrcoef(acc, w)[0, 1]) if acc.std() > 0 else None,  # FP.MASS tu w kg/m -> pasek 0,02 m = 28,17 kg
                   ax_rms=float(ax.std()), z_sr=float(b[:, 3].mean()), we=round(FB.OME, 3))
        out.update(dbg_w_rms=float(w.std()), dbg_M=float(FP.MASS), dbg_n=len(b), dbg_t=[float(b[0, 0]), float(b[-1, 0])], dbg_wa=br.wa_hist[-5:])
        if SEA:
            PC = 57.056; out.update(zysk_W=float(PC - b[:, 1].mean()), zysk_pct=float(100 * (1 - b[:, 1].mean() / PC)), sea=SEA, seed=SEED)
            d = Path(__file__).parent / "cel_widmo"; d.mkdir(exist_ok=True); (d / f"{SEA}_s{SEED}_cel{CEL:g}.json").write_text(json.dumps(out)); print(json.dumps(out), flush=True); sys.exit()
        f = Path(__file__).parent / "MPC_CEL_MODEL.json"; R = json.loads(f.read_text()) if f.exists() else {}
        R[f"T{Tw:g}_cel{CEL:g}"] = out; f.write_text(json.dumps(R, indent=1)); print(json.dumps(out), flush=True)
        sys.exit()
    exec(compile(open(FB.__file__, encoding="utf-8").read().split('if __name__ == "__main__":', 1)[1].replace("\n    ", "\n"), "main", "exec"), vars(FB))
