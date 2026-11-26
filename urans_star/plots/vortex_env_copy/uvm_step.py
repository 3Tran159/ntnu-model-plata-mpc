"""uvm_step.py - krokowa (stanowa) wersja modelu wirowego uvm2d.Foil.simulate + Foil.forces.

Ta sama arytmetyka co Foil.simulate (wiry zwiazane w 1/4 paneli, kolokacja w 3/4, slad przesuwany o U*dt,
odbicie od swobodnej powierzchni) i Foil.forces, ale liczona krok po kroku ze stanem:
  gw   - cyrkulacje wirow sladu (rosnaca odleglosc od krawedzi splywu)
  Gprev- suma cyrkulacji zwiazanej z poprzedniego kroku (warunek Kelvina)
  ph   - historia skumulowanej cyrkulacji (pochodna potencjalu, schemat 2. rzedu)
Wejscia kroku: th_p (zaburzenie kata wzgledem stanu sredniego) [rad], thd [rad/s], hd (predkosc nurzania, + w DOL) [m/s],
gust: (u, w) predkosci fali w punktach kolokacji / wirow (lub None). Sily na 1 m rozpietosci.
"""
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(r"T:\NTNU_GODO_CONTROL_20261109\70_godo_case\vortex_validation\model")))
from uvm2d import Foil, G  # noqa: E402


class FoilStepper:
    def __init__(self, foil: Foil, mean=None):
        self.F = foil
        N = foil.N
        self.mean = mean or dict(theta0=0.0, G0=np.zeros(N), w0=np.zeros(N), u0=np.zeros(N))
        self.reset()

    def reset(self):
        F = self.F
        self.gw = np.zeros(F.Nw); self.Gprev = 0.0
        self.ph = np.zeros((3, F.N)); self.n = 0

    def state(self):
        return dict(gw=self.gw.copy(), Gprev=self.Gprev, ph=self.ph.copy(), n=self.n)

    def set_state(self, s):
        self.gw = s["gw"].copy(); self.Gprev = s["Gprev"]; self.ph = s["ph"].copy(); self.n = s["n"]

    def step(self, th_p, thd, hd, gust_c=None, gust_v=None):
        """Jeden krok dt. gust_c = w fali w punktach kolokacji (N,), gust_v = (u, w) fali w punktach wirow."""
        F, m = self.F, self.mean
        rhs = -F.U * th_p - thd * (F.xc - F.xp) - hd
        if gust_c is not None:
            rhs = rhs - gust_c
        gw = self.gw
        gw[1:] = gw[:-1]; gw[0] = 0.0
        b = np.empty(F.N + 1); b[:F.N] = rhs - F.Abw @ gw; b[F.N] = self.Gprev
        sol = F.Minv @ b
        Gb = sol[:F.N]; gw[0] = sol[F.N]; self.Gprev = Gb.sum()
        ph = self.ph; ph[2] = ph[1]; ph[1] = ph[0]; ph[0] = np.cumsum(Gb)
        n = self.n
        dphi = (3 * ph[0] - 4 * ph[1] + ph[2]) / (2 * F.dt) if n >= 2 else (ph[0] - ph[1]) / F.dt
        self.n = n + 1
        w = F.Wvb @ Gb + F.Wvw @ gw; u = F.Uvb @ Gb + F.Uvw @ gw
        if gust_v is not None:
            u = u + gust_v[0]; w = w + gust_v[1]
        wb = hd + thd * (F.xv - F.xp)
        Nu = F.rho * F.dx * dphi
        Gt = m["G0"] + Gb; wt = m["w0"] + w + wb; ut = m["u0"] + u
        Lc = F.rho * (F.U + ut) * Gt
        L = Lc.sum() + Nu.sum()
        slope = m["theta0"] + th_p
        Fx = -F.rho * (Gt * wt).sum() + (Nu * slope).sum()
        Mp = -(Lc * (F.xv - F.xp)).sum() - (Nu * (F.xm - F.xp)).sum()
        return dict(L=L, Fx=Fx, Mp=Mp, CL=L / (0.5 * F.rho * F.U ** 2 * F.c), Gsum=Gb.sum())


def mean_state(F: Foil, th_ref):
    """Stan sredni dla kata odniesienia th_ref [rad] (jak w replay_history.py)."""
    g1 = np.linalg.solve(F.Abb, -F.U * np.ones(F.N))
    return dict(theta0=th_ref, G0=g1 * th_ref, w0=F.Wvb @ (g1 * th_ref), u0=F.Uvb @ (g1 * th_ref)), g1
