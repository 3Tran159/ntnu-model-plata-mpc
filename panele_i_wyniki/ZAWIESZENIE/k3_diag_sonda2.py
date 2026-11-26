"""k3_diag_sonda2.py - kontrola wzoru filtru sondy: ten sam H(we) zastosowany nieprzyczynowo (cale FFT, bez obciecia) - blad powinien byc ~0.
Jesli tak, blad k3_diag_sonda.py to tylko przyczynowosc/obciecie filtru, nie wzor."""
import sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "WIDMO_S1S4"))
import widmo_s1s4 as W
from k3 import _PLANT, probe_kernel, U, G, FP
for sea in ("S1", "S3"):
    Hs, Tp = W.SEAS[sea]; P = _PLANT(**W.Z.VB); wp = 2 * np.pi / Tp; P.set_irregular(Hs=Hs, Tp=Tp, gamma=3.3, seed=100 * int(sea[1]), N=80, wmin=0.5 * wp, wmax=3.0 * wp)
    dt = 0.01; n = 2 ** 15; t = np.arange(n) * dt; xm = float(np.mean(P.F.xc))
    wt = np.array([float(np.mean(P.gust(P.F.xc, x)[1])) for x in t]); m = (t > 20) & (t < t[-1] - 20)
    for d in (3.0, 6.0):
        e = np.array([P.eta_ahead(d, x) for x in t]); we = 2 * np.pi * np.fft.fftfreq(n, dt); aw = np.abs(we)
        w0 = (-1 + np.sqrt(1 + 4 * U * aw / G)) * G / (2 * U); k = w0 * w0 / G; dd = d + xm
        tau = np.where(w0 > 0, dd / (U + G / np.maximum(w0, 1e-9)), dd / U)
        H = 1j * np.sign(we) * w0 * np.exp(-k * FP.DEPTH) * np.exp(-1j * we * tau); H[0] = 0
        est = np.real(np.fft.ifft(H * np.fft.fft(e)))
        kern, lost = probe_kernel(dd); est2 = np.convolve(e, kern)[:n]
        r = lambda x: 100 * np.sqrt(np.mean((x[m] - wt[m]) ** 2) / np.mean(wt[m] ** 2))
        print(f"{sea} d={d}: nieprzyczynowy {r(est):.1f} %, FIR przyczynowy {r(est2):.1f} %, odciete {100*lost:.1f} %", flush=True)
