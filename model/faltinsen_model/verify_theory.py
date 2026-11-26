"""verify_theory.py - kontrola: czy numeryczne rozwiazanie (6.180)+(6.182) (Stepper) odtwarza wzory zamkniete Faltinsena.
A) plyn nieskonczony, nurzanie i obrot harmoniczny -> (6.187) z C(kf) (6.189)
B) stacjonarnie pod powierzchnia swobodna: nachylenie CL(h)/CL(inf) -> (6.144)
Wynik: VERIFY_THEORY.json"""
import json, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
from uvm2d import Foil
import faltinsen_eqs as FE
from faltinsen_plant import Stepper, C, U, RHO

def harmonic(mode, om, N=40, nper=6):
    T = 2 * np.pi / om; dt = min(1e-3, T / 400); F = Foil(c=C, U=U, N=N, free_surface=False, dt=dt, wake_len=min(nper * U * T, 400 * C + 3 * U * T) , rho=RHO, xp=0.5)
    S = Stepper(F); n = int(round(nper * T / dt)); t = (np.arange(n) + 1) * dt; L = np.zeros(n)
    for i in range(n):
        if mode == "heave":   # h = h0 cos(om t), h0 = 0.01 m (+ w gore) -> predkosc w dol hd = -dh/dt
            L[i] = S.step(0.0, 0.0, 0.01 * om * np.sin(om * t[i]))["L_lin"]
        else:                 # delta = d0 cos(om t), d0 = 0.01 rad, obrot wokol srodka cieciwy
            L[i] = S.step(0.01 * np.cos(om * t[i]), -0.01 * om * np.sin(om * t[i]), 0.0)["L_lin"]
    m = t > t[-1] - T; zc = 2 * np.mean(L[m] * np.exp(-1j * om * t[m]))
    # znak kata: Faltinsen eta = h - delta x, delta > 0 = nos W GORE przy x w dol strumienia? (6.185): dphi/dy = h' - delta' x - U delta;
    # sila od stalego kata (6.187): L = rho pi c U^2 delta > 0 -> delta > 0 daje sile w gore = nasze theta > 0
    ref = FE.lift_theodorsen(0.01, 0.0, om, U, C, RHO) if mode == "heave" else FE.lift_theodorsen(0.0, 0.01, om, U, C, RHO)
    return zc, ref

out = {"A_theodorsen": [], "B_biplane": []}
for kf in (0.02, 0.041, 0.1, 0.3, 1.0):
    om = 2 * U * kf / C
    for mode in ("heave", "pitch"):
        zc, ref = harmonic(mode, om)
        row = dict(kf=kf, mode=mode, amp_model=abs(zc), amp_6_187=abs(ref), amp_ratio=abs(zc) / abs(ref), phase_diff_deg=float(np.degrees(np.angle(zc / ref))),
                   C_abs=float(abs(FE.theodorsen(kf))), C_phase_deg=float(np.degrees(np.angle(FE.theodorsen(kf)))))
        out["A_theodorsen"].append(row); print(row, flush=True)
Finf = Foil(c=C, U=U, N=40, free_surface=False, dt=1e-3, wake_len=1.0, rho=RHO); s_inf = np.linalg.solve(Finf.Abb, -U * np.ones(40)).sum()
for h in (0.156, 0.312, 0.624, 1.09, 1.82):
    F = Foil(c=C, U=U, N=40, h=h, dt=1e-3, wake_len=1.0, rho=RHO); s = np.linalg.solve(F.Abb, -U * np.ones(40)).sum()
    row = dict(h_m=h, h_over_c=h / C, ratio_model=s / s_inf, ratio_6_144=float(FE.cl_ratio_high_fn(h, C)), Fn_h=float(FE.fn_h(U, h)), Fn_h_min_for_6_144=float(10 / np.sqrt(h / C)))
    out["B_biplane"].append(row); print(row, flush=True)
(HERE / "VERIFY_THEORY.json").write_text(json.dumps(out, indent=1))
