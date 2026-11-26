"""greenfs_unsteady.py - 12.11 wieczor: czy NIESTACJONARNA funkcja Greena powierzchni swobodnej (2D, predkosc U, czestotliwosc w)
zmienia amplitude/faze sily nosnej wzgledem odbicia phi=0 (to, co ma model wirowy)?
Plaski plat c = 0,312 m, 30 wirow + slad 80 m w dziedzinie czestotliwosci, jednostkowa predkosc normalna (nurzanie / dlugi podmuch).
Jadro = plyn nieskonczony + odbicie + poprawka falowa dG(dx) = (1/2pi) int i g |k| sgn k e^{-2|k|h} e^{ik dx} / (g|k| - (w+Uk)^2) dk (FFT).
WYNIK (U 12,35 m/s): |L_pelna / L_odbicie| przy w_e = 3,24 rad/s: 0,996 (h 0,6) ... 1,007 (h 1,69), faza < 1 deg;
 w -> 0: 0,95 (FS zmniejsza stala sile nosna o ~5 %, w modelu juz skalibrowane).
WNIOSEK: liniowa powierzchnia swobodna (ani stacjonarna, ani niestacjonarna) NIE tlumaczy zawyzenia amplitudy CL (23-57 %) ani bledu PID1;
brakujacy skladnik lezy gdzie indziej (wspolgra nurzanie-fala w swobodnym nurzaniu: wzmocnienia/opoznienia, efekty lepkie).
"""
import numpy as np
g = 9.81


def kernel_fft(h, U, w, eps_abs=None, dk=2e-4, kmax_fac=40.0, gg=g):
    if eps_abs is None: eps_abs = max(0.01 * w, 0.005)
    we = w - 1j * eps_abs; kmax = kmax_fac / h; n = int(2 * kmax / dk); n += n % 2
    k = (np.arange(n) - n // 2) * dk
    F = 1j * gg * np.abs(k) * np.sign(k) * np.exp(-2 * np.abs(k) * h) / (gg * np.abs(k) - (we + U * k) ** 2)
    f = np.fft.fftshift(np.fft.ifft(np.fft.ifftshift(F))) * n * dk / (2 * np.pi)
    return (np.arange(n) - n // 2) * 2 * np.pi / (n * dk), f


def solve(h, U, w, N=30, c=0.312, fs=True, Lw=80.0):
    dxw = 0.02; xe = np.linspace(0, c, N + 1); xb = xe[:-1] + 0.25 * c / N; xc = xe[:-1] + 0.75 * c / N
    xw = c + 0.5 * dxw + np.arange(int(Lw / dxw)) * dxw
    k_inf = lambda d: 1 / (2 * np.pi * d); k_mir = lambda d: d / (2 * np.pi * (d * d + 4 * h * h))
    if fs:
        x, f = kernel_fft(h, U, w); m = (x > -2) & (x < Lw + 2); x, f = x[m], f[m]
        dG = lambda d: np.interp(d, x, f.real) + 1j * np.interp(d, x, f.imag)
    else:
        dG = lambda d: 0 * d
    D = xc[:, None] - xb[None, :]; Kb = k_inf(D) + k_mir(D) + dG(D)
    Dw = xc[:, None] - xw[None, :]; ph = np.exp(-1j * w * (xw - c) / U) * (-(1j * w / U)) * dxw
    Kw = ((k_inf(Dw) + k_mir(Dw) + dG(Dw)) * ph[None, :]).sum(1)
    gam = np.linalg.solve(Kb + Kw[:, None], -np.ones(N))
    return 1000 * U * gam.sum() + 1000 * 1j * w * np.sum(gam * (c - xb))


if __name__ == "__main__":
    U = 12.3466667; om = 2 * np.pi / 5; we = om + om * om / g * U
    for h in (0.6, 1.09, 1.39, 1.69):
        print(f"h={h:4.2f} | " + " | ".join(f"w={w:4.2f}: |r|={abs(solve(h, U, w) / solve(h, U, w, fs=False)):.3f}" for w in (0.02, 0.5 * we, we, 2 * we)))
