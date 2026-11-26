"""k3_diag_sonda.py - jak dobrze sonda fali d m przed platem przewiduje pionowa predkosc wody na placie (plat nieruchomy, bez sterowania).
Filtr FIR z k3.probe_kernel (fizyka fali liniowej, bez dopasowania do widma). Zarzut R3-2. Wynik: blad wzgledny RMS.
Kontrola: polozenie punktow kontrolnych plata (xc) wzgledem krawedzi natarcia i wplyw tego przesuniecia na blad."""
import sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "WIDMO_S1S4"))
import widmo_s1s4 as W
from k3 import _PLANT, probe_kernel
P0 = _PLANT(**W.Z.VB); xm = float(np.mean(P0.F.xc)); print("xc min/max/srednia [m]:", float(P0.F.xc.min()), float(P0.F.xc.max()), xm, flush=True)
for sea, (Hs, Tp) in W.SEAS.items():
    P = _PLANT(**W.Z.VB); wp = 2 * np.pi / Tp; P.set_irregular(Hs=Hs, Tp=Tp, gamma=3.3, seed=100 * int(sea[1]), N=80, wmin=0.5 * wp, wmax=3.0 * wp)
    t = np.arange(0, 300, 0.01); wt = np.array([float(np.mean(P.gust(P.F.xc, x)[1])) for x in t]); m = t > 10
    out = []
    for d in (1.5, 3.0, 6.0):
        e = np.array([P.eta_ahead(d, x) for x in t])
        for lab, dk in (("d", d), ("d+xc", d + xm)):
            kern, lost = probe_kernel(dk); est = np.convolve(e, kern)[:len(t)]
            out.append(f"{lab} {dk:.2f}: {100*np.sqrt(np.mean((est[m]-wt[m])**2)/np.mean(wt[m]**2)):.0f} %")
    print(sea, "w RMS %.3f m/s | " % wt[m].std() + " | ".join(out), flush=True)
