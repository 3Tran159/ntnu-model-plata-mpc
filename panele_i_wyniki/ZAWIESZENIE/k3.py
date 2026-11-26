"""k3.py - K3: zawieszenie polaktywne z podgladem fali i odzyskiem energii (agent D, 13.11.2026, zlecenie koordynatora 19:00).
Wszystko "w modelu" (Faltinsen B), nic z URANS. Klasy zgodne z widmo_s1s4.py (koordynator): ten sam run(), ten sam slownik CASES.

Obraz: plat na lozysku liniowym pod kadlubem (jak K1: dwie masy, miekka sprezyna gazowa, odboje), ale zamiast tlumika biernego
pradnica liniowa o sterowanej sile (polaktywna: moze tylko hamowac ruch wzgledny, nie napedza). Na kat plata dziala jak K0,
ale predkosc wody na placie jest SZACOWANA z sondy fali d metrow przed platem (szum + filtr), nie znana dokladnie (zarzut R3-2).

Pradnica (co krok 1 ms). Sila na kadlub w gore = m_h g + k_s d + F,  d = z_plat - z_kadlub,  dv = v_plat - v_kadlub:
  F_chciana = c_rel * dv - c_sky * v_kadlub          (odzysk z ruchu wzglednego + "skyhook": hamuj predkosc kadluba)
  F = c * dv,  c = clip(F_chciana / dv, c_min, c_max), gdy F_chciana * dv > 0, inaczej c = c_min (pradnica tylko hamuje)
  moc pochlonieta = c * dv^2 >= 0 [W na metr rozpietosci]; elektryczna = eta_gen * pochlonieta.
Kat plata: kat = trym + PID1(z_kadluba) - k_wave * w_est / U,
  w_est = filtr FIR (probe_kernel) na wzniesieniu z sondy: kazda skladowa z wlasnym opoznieniem d/(U + c) i tlumieniem e^{-kh}; szum sondy noise_m
  preview="ideal" -> dokladna predkosc wody jak K0 w widmo_s1s4.py (porownanie); "probe" -> sonda.
K0P = sztywny plat (jak PID1/K0) z tym samym szacunkiem z sondy - do zarzutu R3-2 bez zawieszenia.
Statystyki dodatkowe w K3.last / K0P.last po przebiegu: moc pradnicy, predkosc kata RMS (do mocy silownika, R3-3), blad szacunku w.
Uzycie: k3_widmo.py (ten folder)."""
import sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
import zaw90 as Z
FP, U, G = Z.FP, Z.U, Z.G
_SUSP, _PLANT = Z.Susp, FP.FaltinsenPlant          # oryginaly (k3_widmo.py chwilowo podmienia Z.Susp / Z.FaltinsenPlant)
C_WATER = 0.5 * 1000 * U * 0.312 * 2 * np.pi        # tlumienie wody 12,1 kN.s/m na metr (0,5 rho U c 2 pi) - skala dla c_rel, c_sky


def probe_kernel(d, h=None, dt=0.01, n=4096, Tw=3.0):
    """Filtr FIR: wzniesienie fali w sondzie d m przed platem -> pionowa predkosc wody na glebokosci plata h.
    Dla kazdej skladowej (fala czolowa, liniowa, glebokowodna): w_plat = (w0/we) e^{-k h} d/dt eta_plat,  eta_plat(t) = eta_sonda(t - tau(w0)),
    tau = d / (U + g/w0) (fala i lodz ida naprzeciw). W dziedzinie czestosci spotkania: H(we) = i w0 e^{-k h} e^{-i we tau}.
    Nie zalezy od widma (tylko U, h, d, g). Zwraca wspolczynniki h_j (j = 0: najnowsza probka) i udzial energii odcietej (czesc nieprzyczynowa + ogon)."""
    h = FP.DEPTH if h is None else h
    we = 2 * np.pi * np.fft.fftfreq(n, dt); aw = np.abs(we)
    w0 = (-1 + np.sqrt(1 + 4 * U * aw / G)) * G / (2 * U); k = w0 * w0 / G
    with np.errstate(divide="ignore", invalid="ignore"): tau = np.where(w0 > 0, d / (U + G / np.maximum(w0, 1e-9)), d / U)
    H = 1j * np.sign(we) * w0 * np.exp(-k * h) * np.exp(-1j * we * tau); H[0] = 0
    kern = np.real(np.fft.ifft(H)); nw = int(round(Tw / dt))
    lost = 1 - float((kern[:nw] ** 2).sum() / (kern ** 2).sum())
    return kern[:nw].copy(), lost


class _Probe:
    """szacunek pionowej predkosci wody na placie z sondy przed platem (filtr FIR z fizyki fali liniowej) + statystyki;
    dziala na self.cmd w chwilach taktu sterownika"""
    def probe_cfg(self, k_wave=0.0, preview="probe", probe_d=3.0, noise_m=0.01, seed=0, eta_gen=0.7):
        self.k_wave, self.preview, self.probe_d, self.noise_m, self.eta_gen = k_wave, preview, probe_d, noise_m, eta_gen
        self.rng = np.random.default_rng(seed); self.w_est = 0.0; self.kern = None; self.kern_lost = None
        self.E_abs = 0.0; self.n_s = 0; self.rate2 = 0.0; self.err2 = 0.0; self.w2 = 0.0

    def _probe_tick(self):
        if self.preview == "ideal":
            self.w_est = self._w_true()
        else:
            if self.kern is None:
                self.kern, self.kern_lost = probe_kernel(self.probe_d + float(np.mean(self.F.xc)), dt=self.tick * self.dt); self.buf = np.zeros(len(self.kern))   # od sondy do srodka cieciwy
            self.buf = np.roll(self.buf, 1); self.buf[0] = self.eta_ahead(self.probe_d) + self.noise_m * self.rng.standard_normal()
            self.w_est = float(self.kern @ self.buf)
        self.cmd = float(np.clip(self.cmd - self.k_wave * self.w_est / U, -np.radians(7.5), np.radians(7.5)))
        if self.t > 5.0:
            wt = self._w_true(); self.err2 += (self.w_est - wt) ** 2; self.w2 += wt * wt; self.n_s += 1

    def _w_true(self):
        return float(np.mean(self.gust(self.F.xc, self.t)[1]))

    def step(self, **kw):
        if self.n % self.tick == 0 and self.k_wave: self._probe_tick()
        r = super().step(**kw); self.rate2 += r["rate_deg_s"] ** 2; T = max(self.t, 1e-9)
        type(self).last = dict(P_gen_abs_W_per_m=self.E_abs / T, P_gen_el_W_per_m=self.eta_gen * self.E_abs / T,
                               rate_rms_deg_s=float(np.sqrt(self.rate2 / max(self.n, 1))),
                               w_est_err_rel=float(np.sqrt(self.err2 / self.w2)) if self.w2 > 0 else None, kern_lost=self.kern_lost)
        return r


class K3(_Probe, _SUSP):
    last = {}

    def setup(self, fn=0.2, zeta=0.0, mf=40.0, stroke=0.5, c_rel=1.0, c_sky=1.0, c_min=0.02, c_max=3.0, **probe):
        """c_rel, c_sky, c_min, c_max w jednostkach tlumienia wody C_WATER (12,1 kN.s/m na metr); zeta = tlumienie bierne rownolegle"""
        _SUSP.setup(self, fn=fn, zeta=zeta, mf=mf, stroke=stroke); self.c_pass = self.cs
        self.c_rel, self.c_sky, self.c_min, self.c_max = (x * C_WATER for x in (c_rel, c_sky, c_min, c_max))
        self.probe_cfg(**probe)

    def heave_update(self, dt):
        dv = self.v - self.vh; F = self.c_rel * dv - self.c_sky * self.vh
        c = float(np.clip(F / dv, self.c_min, self.c_max)) if (abs(dv) > 1e-9 and F * dv > 0) else self.c_min
        self.cs = self.c_pass + c                  # Susp.heave_update: sila tlumika = cs * dv
        self.E_abs += c * dv * dv * dt
        _SUSP.heave_update(self, dt)


class K0P(_Probe, _PLANT):
    """sztywny plat (jak PID1/K0) z szacunkiem predkosci wody z sondy; konfiguracja przez K0P.CFG (ustawia k3_widmo.py)"""
    last = {}; CFG = {}

    def __init__(self, *a, **kw):
        _PLANT.__init__(self, *a, **kw); self.probe_cfg(**K0P.CFG)
