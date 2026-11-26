"""zaw90.py - Krok 3 (zlecenie D), 13.11: woda spokojna i punkt odniesienia K0 przy obciazeniu plata 90 %, potem K1 (zawieszenie bierne).
Model: FaltinsenPlant, wariant B z walidacji Kroku 2 (nachylenie 2 pi, z pozioma predkoscia fali, staly CD0; bez dopasowania).
Oryginalu modelu NIE zmieniam: masa ustawiana w pamieci (FP.MASS = obciazenie * masa 100 %), reszta stalych bez zmian.
Protokol jak validate_urans.py: takt sterownika 10 ms, serwo +-7,5 deg / 90 deg/s, nurzanie zwolnione po 1 okresie spotkania,
8 okresow spotkania, srednie z ostatnich 4, srednia z 4 faz fali. Fala regularna H 1,5 m (amplituda w modelu 0,73 m), T 5 s, od dziobu.
K0 = sztywny plat + wolny PID wysokosci + "gladki" sterownik: kat = trym + PID - k * (w_wody - VW * v_plata) / U
     k = udzial kasowania (0,25 ... 1,0); VW = 0: kasuje tylko fale; VW = 1: kasuje fale i tlumienie nurzania (jak smooth_lift.py z modelu v2).
K1 = plat (masa mf) na sprezynie i tlumiku pod kadlubem (masa M - mf), odboje na koncach skoku; nadpisane heave_update().
Wynik: ZAW90.json (zapis po kazdym przypadku, wznowienie pomija gotowe), log: zaw90.log.  Wszystko "w modelu", nie "w URANS".
Uzycie: <faltinsen_model>\.venv\Scripts\python zaw90.py [test]"""
import json, sys, time
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent; ROOT = HERE.parents[1]
MOD = ROOT / "40_MODEL_WIROWY_I_STEROWANIE" / "faltinsen_model"; sys.path.insert(0, str(MOD))
import faltinsen_plant as FP
from faltinsen_plant import FaltinsenPlant, U, C, RHO, BUOY
G = FP.G; MASS100 = 12500.0 / (25.6 * 0.312); VB = dict(slope=1.0, wave_u=True); T_REL = 1.9368
PH = (0.0, np.pi / 2, np.pi, 1.5 * np.pi); OUT, LOG = HERE / "ZAW90.json", HERE / "zaw90.log"


def log(s):
    print(s, flush=True)
    with open(LOG, "a", encoding="utf-8") as f: f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + s + "\n")


class Susp(FaltinsenPlant):
    """dwie masy: plat (self.z, self.v - to widzi hydrodynamika) i kadlub (self.zh, self.vh)"""
    def setup(self, fn, zeta, mf=40.0, stroke=0.30):
        self.mf, self.mh = mf, FP.MASS - mf; self.ks = self.mh * (2 * np.pi * fn) ** 2; self.cs = 2 * zeta * np.sqrt(self.ks * self.mh)
        self.stroke, self.kb = stroke, 20 * self.ks; self.ma = RHO * np.pi * C * C / 4      # masa wody towarzyszacej plata (plaska plyta)

    def reset(self, **kw):
        super().reset(**kw); self.zh, self.vh, self.af, self.ah = self.z, self.v, 0.0, 0.0

    def heave_update(self, dt):
        d, dv = self.z - self.zh, self.v - self.vh                  # ugiecie: plat wzgledem kadluba (+ = scisniecie)
        Fs = self.mh * G + self.ks * d + self.cs * dv               # sila zawieszenia na kadlub (napiecie wstepne = ciezar kadluba)
        if abs(d) > self.stroke: Fs += self.kb * (d - np.sign(d) * self.stroke)            # odboj
        self.ah = Fs / self.mh - G
        # plat: sila nosna z modelu zawiera juz -ma * a z poprzedniego kroku -> masa towarzyszaca niejawnie (stabilnosc przy mf < ma)
        self.af = (self.Fy + BUOY - self.mf * G - Fs + self.ma * self.af) / (self.mf + self.ma)
        self.v += dt * self.af; self.vh += dt * self.ah; self.zh += dt * self.vh


def run(load, amp, phase, kp, ki, gain=0.0, vw=0.0, susp=None, nper=8):
    FP.MASS = load * MASS100
    P = (Susp if susp else FaltinsenPlant)(wave_amp=amp, wave_phase=phase, **VB)
    cl_eq = (FP.MASS * G - BUOY) / P.q; trim = FP.TH_REF_DEG + float(np.degrees((cl_eq - FP.CL_REF) / (P.slope * P.dcl)))
    if susp: P.setup(**susp)
    P.reset(theta_deg=trim); ie = 0.0; rows = []
    for i in range(int(round(nper * P.Te / P.dt))):
        free = P.t >= T_REL - 0.5 * P.dt
        if i % P.tick == 0:
            zc = P.zh if susp else P.z; cmd = trim                 # regulator wysokosci widzi kadlub
            if free: ie = float(np.clip(ie + (-zc) * P.tick * P.dt, -1, 1)); cmd = trim + kp * (-zc) + ki * ie
            if gain:
                wg = float(np.mean(P.gust(P.F.xc, P.t)[1]))        # pionowa predkosc wody na placie (idealna znajomosc fali)
                cmd -= gain * float(np.degrees((wg - vw * P.v) / U))
            P.cmd = np.radians(float(np.clip(cmd, -7.5, 7.5)))
        r = P.step(free_heave=free)
        acc = P.ah if susp else (r["L"] + BUOY) / FP.MASS - G      # przyspieszenie pionowe kadluba
        rows.append((r["t"], r["theta_deg"], r["rate_deg_s"], P.zh if susp else r["z"], acc, r["CL"], r["P_drag_W_strip"], r["sub"],
                     (P.z - P.zh) if susp else 0.0, r["Fx_pot"] * U * FP.SPAN, r["Fx_wave"] * U * FP.SPAN))
    a = np.array(rows); w = a[:, 0] > a[-1, 0] - 4 * P.Te; b = a[w]; w0 = (a[:, 0] > a[-1, 0] - 5 * P.Te) & (a[:, 0] <= a[-1, 0] - 4 * P.Te)
    return dict(trim_deg=trim, CL_eq=float(cl_eq), P_W=float(b[:, 6].mean()), P_pot_W=float(b[:, 9].mean()), P_wave_W=float(b[:, 10].mean()),
                acc_rms=float(np.sqrt(np.mean((b[:, 4] - b[:, 4].mean()) ** 2))), acc_peak=float(np.abs(b[:, 4]).max()),
                z_p2p=float(np.ptp(b[:, 3])), z_mean=float(b[:, 3].mean()), z_drift=float(b[-776:, 3].mean() - a[w0][:, 3].mean()),
                sub_min=float(b[:, 7].min()), th_min=float(b[:, 1].min()), th_max=float(b[:, 1].max()), rate_max=float(np.abs(b[:, 2]).max()),
                sat_pct=float(100 * np.mean((np.abs(b[:, 2]) > 89.9) | (np.abs(b[:, 1]) > 7.49))),
                CL_min=float(b[:, 5].min()), CL_max=float(b[:, 5].max()), CL_mean=float(b[:, 5].mean()),
                stroke_p2p=float(np.ptp(b[:, 8])), stroke_absmax=float(np.abs(b[:, 8]).max()))


PID1, PID2 = (2.01, 0.196), (6.63, 1.18)                           # Godo; PID2 z OVS_PID2_GODO/run.properties
CASES = [("CALM_100", dict(load=1.0, amp=0.0, kp=PID1[0], ki=PID1[1])), ("CALM_90", dict(load=0.9, amp=0.0, kp=PID1[0], ki=PID1[1])),
         ("PID1_90", dict(load=0.9, kp=PID1[0], ki=PID1[1])), ("PID2_90", dict(load=0.9, kp=PID2[0], ki=PID2[1]))]
for vw in (0.0, 1.0):
    for g in (0.25, 0.5, 0.75, 1.0):
        CASES.append((f"K0_{'fala' if vw == 0 else 'fala_i_nurzanie'}_{int(100 * g)}_90", dict(load=0.9, kp=PID1[0], ki=PID1[1], gain=g, vw=vw)))
for fn in (0.3, 0.5, 1.0, 1.5):
    for ze in (0.3, 0.7):
        CASES.append((f"K1_f{fn}_tl{ze}_90", dict(load=0.9, kp=PID1[0], ki=PID1[1], susp=dict(fn=fn, zeta=ze))))
for fn in (0.3, 0.5):
    CASES.append((f"K1_f{fn}_tl0.3_K0fala50_90", dict(load=0.9, kp=PID1[0], ki=PID1[1], gain=0.5, susp=dict(fn=fn, zeta=0.3))))

# dodatki 13.11 12:35: gestsze K0 kolo progu 0,36 m/s2; K0 i PID1 przy 100 % (wplyw obciazenia); K1 miekkie z dluzszym skokiem
for g in (0.85, 0.9):
    CASES.append((f"K0_fala_{int(100 * g)}_90", dict(load=0.9, kp=PID1[0], ki=PID1[1], gain=g, vw=0.0)))
CASES += [("PID1_100", dict(load=1.0, kp=PID1[0], ki=PID1[1])), ("K0_fala_50_100", dict(load=1.0, kp=PID1[0], ki=PID1[1], gain=0.5)),
          ("K0_fala_100_100", dict(load=1.0, kp=PID1[0], ki=PID1[1], gain=1.0))]
for fn in (0.2, 0.3):
    CASES.append((f"K1_f{fn}_tl0.5_skok0.5_90", dict(load=0.9, kp=PID1[0], ki=PID1[1], susp=dict(fn=fn, zeta=0.5, stroke=0.5))))
CASES.append(("K1_f0.2_tl0.5_skok0.5_K0fala50_90", dict(load=0.9, kp=PID1[0], ki=PID1[1], gain=0.5, susp=dict(fn=0.2, zeta=0.5, stroke=0.5))))

if __name__ == "__main__":
    out = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    if "test" in sys.argv: CASES = CASES[:2]
    for name, kw in CASES:
        if name in out: continue
        t0 = time.time(); amp = kw.pop("amp", 0.73); phs = PH if amp > 0 else (0.0,)
        runs = [run(amp=amp, phase=ph, **kw) for ph in phs]
        m = {k: float(np.mean([r[k] for r in runs])) for k in runs[0]}
        for k in ("acc_peak", "rate_max", "CL_max", "th_max", "stroke_absmax", "sat_pct"): m[k] = float(max(r[k] for r in runs))
        for k in ("sub_min", "CL_min", "th_min"): m[k] = float(min(r[k] for r in runs))
        m["P_spread_W"] = float(np.ptp([r["P_W"] for r in runs])); out[name] = m
        OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
        ref = out.get("CALM_90" if name.endswith("_90") else "CALM_100", {}).get("P_W")
        log(f"{name}: moc {m['P_W']:.2f} W/pasek ({100 * (m['P_W'] / ref - 1) if ref else float('nan'):+.1f} % wzgl. wody spok.), z'' RMS {m['acc_rms']:.3f} szczyt {m['acc_peak']:.2f} m/s2, "
            f"z p2p {m['z_p2p']:.3f} m, zan. min {m['sub_min']:.2f} m, kat {m['th_min']:.1f}..{m['th_max']:.1f} deg, nasyc. {m['sat_pct']:.0f} %, skok +-{m['stroke_absmax']:.2f} m, {time.time() - t0:.0f} s")
    log("gotowe")
