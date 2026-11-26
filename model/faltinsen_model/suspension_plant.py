"""suspension_plant.py - model dwumasowy do testu zawieszen (zlecenie D / Krok 3): plat (masa nieresorowana) + kadlub (masa resorowana),
miedzy nimi element o sile F_el = f(x, xd, t). Hydrodynamika: FaltinsenPlant (model B, bez dopasowania), na 1 m rozpietosci.

UKLAD I ZNAKI (z w gore +, wszystko na 1 m rozpietosci):
  z_f  [m]  polozenie plata (0 = zanurzenie projektowe 1,09 m);   v_f [m/s]      (to samo co Plant.z, Plant.v)
  z_h  [m]  polozenie kadluba (0 = polozenie projektowe);         v_h [m/s]
  x  = z_f - z_h [m]   ugiecie: + = plat blizej kadluba (sciskanie);   xd = v_f - v_h [m/s]
  F_el(x, xd, t) [N/m] sila elementu PONAD napiecie wstepne: + = pcha kadlub w gore, plat w dol.  F_el(0, 0, t) = 0 dla elementu biernego.
  Napiecie wstepne = ciezar kadluba m_h g (element w rownowadze niesie kadlub przy x = 0).
RUCH:
  m_h dv_h/dt = F_el
  m_f dv_f/dt = L + B - m_f g - m_h g - F_el          (L sila nosna z modelu, B wypornosc profilu)
  MASA DODANA: plat ma 40 kg/m, a jego masa dodana w nurzaniu m_a = rho pi c^2 / 4 = 76,5 kg/m (pierwszy czlon (6.187), Faltinsen s.211).
  Jawne sprzezenie (sila z poprzedniego kroku) jest wtedy niestabilne, wiec czlon -m_a dv_f/dt jest przeniesiony na lewa strone:
      (m_f + m_a) dv_f/dt = (L + m_a a_poprz) + B - m_f g - m_h g - F_el ,   a_poprz = przyspieszenie plata, ktore widzial solver w poprzednim kroku.
  Fizyka ta sama, zmienia sie tylko sposob calkowania (blad rzedu dt). W trybie rigid=True tego nie ma (arytmetyka modelu B).
  Sila hydrodynamiczna L stala w kroku dt (z poprzedniego kroku, jak w modelu B i w makrze URANS); uklad mas calkowany w n_sub podkrokach
  schematem pol-jawnym (najpierw predkosci, potem polozenia) - stabilny takze dla twardych odbojow.
MASY (karta stalych, obciazenie 90 %): masa calkowita 0,9 * 1565 = 1408,5 kg/m (CL rownowagi 0,578). Domyslnie m_f = 40 kg/m jest CZESCIA tej masy,
  czyli m_h = 1368,5 kg/m. Parametr m_hull pozwala podac mase kadluba wprost (np. 1409 kg/m + 40 kg/m plata -> CL 0,594).
POLACZENIE SZTYWNE: rigid=True -> jedna masa, arytmetyka identyczna z FaltinsenPlant (test: test_suspension.py).
"""
import sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
import faltinsen_plant as FP
from faltinsen_plant import FaltinsenPlant, MASS, BUOY, G, C, U, SPAN, DEPTH, RHO
M_ADDED = RHO * np.pi * C ** 2 / 4.0     # kg/m, masa dodana plaskiego plata w nurzaniu, (6.187)


class Suspension:
    """Element bierny + odboje + sila sterowana. Wywolanie: F = el(x, xd, t)  [N/m], znak jak w opisie modulu.
      k [N/m/m]        sztywnosc liniowa;            k3 [N/m^3/m]  czlon szescienny (sprezyna progresywna: k x + k3 x^3)
      c_comp, c_reb    tlumienie przy sciskaniu (xd > 0) i odbiciu (xd < 0) [N s/m/m]; c ustawia oba
      x_up, x_dn [m]   skok do odbojow: sciskanie do +x_up, rozciaganie do -x_dn (None = brak odboju)
      k_stop, c_stop   sztywnosc i tlumienie odboju po przekroczeniu skoku
      f_ctrl(x, xd, t) dodatkowa sila sterowana [N/m] (silownik, tlumik przelaczany); None = brak
      spring(x), damper(xd)  wlasne charakterystyki (funkcje) zamiast k, k3 / c_comp, c_reb"""
    def __init__(self, k=0.0, c=None, c_comp=0.0, c_reb=0.0, k3=0.0, x_up=None, x_dn=None, k_stop=2.0e6, c_stop=2.0e4, f_ctrl=None, spring=None, damper=None):
        if c is not None: c_comp = c_reb = c
        self.k, self.k3, self.c_comp, self.c_reb, self.x_up, self.x_dn, self.k_stop, self.c_stop = k, k3, c_comp, c_reb, x_up, x_dn, k_stop, c_stop
        self.f_ctrl, self.spring, self.damper = f_ctrl, spring, damper
        self.last = dict(spring=0.0, damper=0.0, stop=0.0, ctrl=0.0)

    def __call__(self, x, xd, t):
        fs = self.spring(x) if self.spring else self.k * x + self.k3 * x ** 3
        fd = self.damper(xd) if self.damper else (self.c_comp if xd > 0 else self.c_reb) * xd
        fb = 0.0
        if self.x_up is not None and x > self.x_up: fb = self.k_stop * (x - self.x_up) + self.c_stop * xd
        elif self.x_dn is not None and x < -self.x_dn: fb = self.k_stop * (x + self.x_dn) + self.c_stop * xd
        fc = self.f_ctrl(x, xd, t) if self.f_ctrl else 0.0
        self.last = dict(spring=fs, damper=fd, stop=fb, ctrl=fc)
        return fs + fd + fb + fc


class TwoMassPlant(FaltinsenPlant):
    def __init__(self, element=None, rigid=False, m_foil=40.0, m_hull=None, n_sub=20, load=0.9, **kw):
        self.element, self.rigid, self.n_sub = element or Suspension(), rigid, n_sub
        m_tot = load * MASS if m_hull is None else m_hull + m_foil
        self.m_f, self.m_h = m_foil, m_tot - m_foil
        super().__init__(load=m_tot / MASS, **kw)

    def reset(self, theta_deg=0.0, z=0.0, v=0.0, t=0.0, x0=0.0):
        super().reset(theta_deg=theta_deg, z=z, v=v, t=t)
        self.z_h, self.v_h, self.a_h = z - x0, v, 0.0
        self._zf_new = z; self.F_el = 0.0; self.E_el = 0.0; self.x_max, self.x_min = -np.inf, np.inf; self._vhist = [v, v, v]; self._nh = 0

    def heave_update(self, dt):
        if self.rigid:
            super().heave_update(dt); return
        h = dt / self.n_sub; zf, vf, zh, vh = self.z, self.v, self.z_h, self.v_h; vh0 = vh; Fsum = 0.0
        vh_ = self._vhist; a_prev = ((3 * vh_[0] - 4 * vh_[1] + vh_[2]) / (2 * dt) if self._nh >= 3 else (vh_[0] - vh_[1]) / dt) if self._nh >= 2 else 0.0
        Fhyd = self.Fy + M_ADDED * a_prev + BUOY - self.m_f * G - self.m_h * G      # sila na plat bez elementu i bez czlonu masy dodanej (stala w kroku)
        for i in range(self.n_sub):
            x, xd = zf - zh, vf - vh; F = self.element(x, xd, self.t + i * h)
            vf += h * (Fhyd - F) / (self.m_f + M_ADDED); vh += h * F / self.m_h
            zf += h * vf; zh += h * vh; Fsum += F; self.E_el += F * xd * h
        self.v, self._zf_new, self.z_h, self.v_h = vf, zf, zh, vh
        self.a_h = (vh - vh0) / dt; self.F_el = Fsum / self.n_sub

    def step(self, free_heave=True, **kw):
        if not free_heave and not self.rigid:
            self.v_h, self.a_h, self._zf_new = 0.0, 0.0, self.z
        v0 = self.v
        r = super().step(free_heave=free_heave, **kw)
        self._vhist = [self.v, self._vhist[0], self._vhist[1]]; self._nh += 1     # predkosci plata, ktore widzial solver
        if self.rigid:
            self.z_h, self.v_h, self.a_h = self.z, self.v, (self.v - v0) / self.dt
        elif free_heave:
            self.z = self._zf_new; r["z"] = self.z          # polozenie plata z podkrokow (zamiast z += v dt)
        x = self.z - self.z_h; self.x_max, self.x_min = max(self.x_max, x), min(self.x_min, x)
        r.update(z_hull=self.z_h, v_hull=self.v_h, a_hull=self.a_h, x=x, xd=self.v - self.v_h, F_el=self.F_el, F_link=self.m_h * G + self.F_el, E_el=self.E_el)
        return r


def calm_reference(load=0.9, free_surface=True, kp=6.63, ki=1.18, t_end=8.0, **kw):
    """Woda spokojna, polaczenie sztywne, PID2 Godo: srednia z ostatnich 2 s. Zwraca moc oporu [W na pasek 0,02 m], CL, kat rownowagi [deg]."""
    p = TwoMassPlant(rigid=True, load=load, free_surface=free_surface, wave_amp=0.0, **kw); th0 = float(np.degrees(p.th_ref)); p.reset(theta_deg=th0)
    ie, rows = 0.0, []
    for n in range(int(round(t_end / p.dt))):
        if n % p.tick == 0 and p.t > 1.0:
            ie += (-p.z) * p.tick * p.dt; p.cmd = np.radians(np.clip(th0 + kp * (-p.z) + ki * ie, -7.5, 7.5))
        r = p.step(free_heave=p.t > 1.0)
        if p.t > t_end - 2.0: rows.append((r["P_drag_W_strip"], r["CL"], r["theta_deg"], r["z"]))
    a = np.array(rows).mean(0)
    return dict(load=load, free_surface=free_surface, P_drag_W_strip=float(a[0]), CL=float(a[1]), theta_deg=float(a[2]), z_m=float(a[3]), mass_kg_m=p.mass, cl_ref=p.cl_ref)
