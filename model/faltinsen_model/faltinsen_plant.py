"""faltinsen_plant.py - Krok 2 (zlecenie C): plat Godø w fali wg Faltinsena (2005), rozdz. 6. BEZ dopasowania do przebiegow URANS w fali.

Co liczy (na 1 m rozpietosci; pasek 0,02 m = x SPAN):
  1. Niestacjonarna sila nosna 2D: rownanie calkowe (6.180) s.210 z warunkiem brzegowym (6.176) i sladem gamma(x - U t) (6.179),
     sila z (6.182). Rozwiazywane numerycznie w czasie (wiry skupione na cieciwie + slad, uvm2d.Foil) - w granicy harmonicznej
     daje (6.187) z funkcja Theodorsena (6.189); kontrola w verify_theory.py.
     Predkosc wzgledna V_R w (6.176): kat plata, predkosc katowa, predkosc nurzania i pionowa predkosc fali (6.198) - razem (6.207).
  1b. Pozioma predkosc orbitalna fali u (tab. 3.1 s.81): naplyw U + u w warunku brzegowym (6.176) i w sile Kutty-Zukowskiego (6.62) s.188.
      Czlon 1. rzedu w amplitudzie fali (srednia cyrkulacja x u): zmienia sile nosna o ok. 2 (u/U) CL_sr, przesuniety o 90 deg wzgledem
      czlonu od predkosci pionowej -> opoznia sile nosna na fali. Faltinsen w 6.12 go pomija (tam srednia sila nosna = 0). Opcja wave_u.
  2. Powierzchnia swobodna, sila nosna: przyblizenie dwuplata phi = 0 (obraz o tym samym znaku cyrkulacji, rys. 6.47);
     wspolczynnik (6.144) s.200 liczony dla CHWILOWEGO zanurzenia nad krawedzia natarcia, wzgledem zanurzenia projektowego.
  3. Opor falowy od sily nosnej (6.145) s.200 z Gamma z (6.147), chwilowe zanurzenie, wzgledem stanu odniesienia.
  4. Opor: sila potencjalna z modelu (z sila ssaca krawedzi natarcia) + opor profilowy CD0.
  5. Nurzanie: m dv/dt = L + wypornosc - m g (jak w makrze URANS). Serwo 2. rzedu jak w makrze URANS.

DANE WEJSCIOWE PROFILU (nie z teorii potencjalnej; z URANS w WODZIE SPOKOJNEJ, OVS_CALM_PID2, nie z przebiegow w fali):
  CL_REF = 0,642 przy TH_REF = 3,22 deg (punkt pracy), CD0 = 0,0104.
  slope = 1,00 -> nachylenie 2 pi (cienki plat).  slope = 0,90 -> nachylenie zmierzone w URANS w wodzie spokojnej (wariant B).
OPCJA cd_wave (domyslnie 0): staly dodatek oporu w fali CD_WAVE_URANS = 0,0016 wyznaczony z URANS (fit_polar.py) - to JEST dopasowanie.
OBCIAZENIE: load = 1,0 -> 100 % (jak URANS, CL 0,642, 1565 kg/m); load = 0,9 -> 90 % (karta stalych: CL 0,578, 1408,5 kg/m).
POWIERZCHNIA SWOBODNA: free_surface=False wylacza obraz wiru, (6.144) i zmienna czesc (6.145). Licznik zanurzenia dziala zawsze: sub_min [m], sub_min_t [s], t_below_1c [s].
FALA NIEREGULARNA: set_irregular(Hs, Tp, gamma, seed, ...) jak w vortex_plant; eta_ahead(d) = podglad fali przed platem.
CZEGO NIE MA (swiadomie): wzmocnien i opoznien CALIB_CL.json, biegunowej K_POL, poprawki MBPO, ograniczenia CL_MAX (opcja cl_max).
Wynik z tego modelu to "w modelu", nie "w URANS".
"""
import sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
from uvm2d import Foil, G
import faltinsen_eqs as FE

RHO, C, U, DEPTH, T_WAVE, SPAN = 1000.0, 0.312, 12.3466667, 1.09, 5.0, 0.02
MASS = 12500.0 / (25.6 * 0.312)             # kg/m (31,3 kg na pasek 0,02 m)
BUOY = 1000 * 9.81 * 0.00795948899616472    # N/m, wypornosc profilu
CL_REF, TH_REF_DEG, CD0 = 0.642, 3.22, 0.0104
CD_WAVE_URANS = 0.0016                      # staly dodatek oporu w fali H = 1,46 m, T = 5 s; z URANS (BASE2, PRBS1, SINE_A2), fit_polar.py; NIE z teorii, pochodzenie nieznane
SLOPE_URANS_CALM = 0.90                     # dCL/dalfa w URANS w wodzie spokojnej / (2 pi); patrz slope_from_calm.py


class Stepper:
    """Krok czasowy (6.180): cyrkulacja zwiazana + nowy wir sladu (Kelvin), slad unoszony z U. Jak uvm_step.FoilStepper,
    plus mnoznik `slope` prawej strony (nachylenie dCL/dalfa = slope * 2 pi)."""
    def __init__(self, foil, mean=None, slope=1.0):
        self.F, self.slope = foil, slope; N = foil.N
        self.mean = mean or dict(theta0=0.0, G0=np.zeros(N), w0=np.zeros(N), u0=np.zeros(N))
        self.gw = np.zeros(foil.Nw); self.Gprev = 0.0; self.ph = np.zeros((3, N)); self.n = 0

    def step(self, th_p, thd, hd, gust_c=None, gust_v=None, u_c=None, u_v=None):
        F, m = self.F, self.mean
        rhs = -F.U * th_p - thd * (F.xc - F.xp) - hd                # (6.176): V_R + U eta'
        if gust_c is not None: rhs = rhs - gust_c                   # (6.207): pionowa predkosc fali
        rhs = self.slope * rhs
        if u_c is not None: rhs = rhs - u_c * (m["theta0"] + self.slope * th_p)   # (6.176) z napływem U + u: pozioma predkosc fali (tab. 3.1)
        gw = self.gw; gw[1:] = gw[:-1]; gw[0] = 0.0                 # (6.179): gamma(x - U t)
        b = np.empty(F.N + 1); b[:F.N] = rhs - F.Abw @ gw; b[F.N] = self.Gprev
        sol = F.Minv @ b; Gb = sol[:F.N]; gw[0] = sol[F.N]; self.Gprev = Gb.sum()
        ph = self.ph; ph[2] = ph[1]; ph[1] = ph[0]; ph[0] = np.cumsum(Gb)
        dphi = (3 * ph[0] - 4 * ph[1] + ph[2]) / (2 * F.dt) if self.n >= 2 else (ph[0] - ph[1]) / F.dt
        self.n += 1
        w = F.Wvb @ Gb + F.Wvw @ gw; u = F.Uvb @ Gb + F.Uvw @ gw
        if gust_v is not None: u = u + gust_v[0]; w = w + gust_v[1]
        wb = hd + thd * (F.xv - F.xp)
        Nu = F.rho * F.dx * dphi                                    # czlon d/dt w (6.182)
        Gt = m["G0"] + Gb; wt = m["w0"] + w + wb
        L_lin = F.rho * F.U * Gb.sum() + Nu.sum()                   # (6.182), zaburzenie
        if u_v is not None: L_lin += F.rho * (u_v * Gt).sum()       # (6.62) z lokalna predkoscia naplywu U + u
        Fx = -F.rho * (Gt * wt).sum() + (Nu * (m["theta0"] + th_p)).sum()
        return dict(L_lin=L_lin, Fx=Fx, Gsum=Gb.sum())


class FaltinsenPlant:
    def __init__(self, dt=1e-3, N=20, wave_amp=0.73, wave_phase=0.0, tick=10, slope=1.0, cd0=CD0, fs_lift=True, fs_wave=True, wave_u=True,
                 cl_max=None, k_pol=0.0, cd_wave=0.0, depth_image=DEPTH, load=1.0, free_surface=True):
        self.dt, self.tick, self.slope, self.cd0, self.fs_lift, self.fs_wave, self.cl_max, self.k_pol = dt, tick, slope, cd0, fs_lift, fs_wave, cl_max, k_pol
        if not free_surface: fs_lift = False; fs_wave = False; self.fs_lift = False; self.fs_wave = False
        self.free_surface, self.load, self.irr = free_surface, load, None
        self.mass = load * MASS                                      # masa calkowita na 1 m [kg/m]; load = 0,9 -> 1408,5 kg/m
        self.cl_ref = (self.mass * G - BUOY) / (0.5 * RHO * U * U * C) if load != 1.0 else CL_REF   # CL rownowagi: 0,642 (100 %), 0,578 (90 %)
        self.wave_u = wave_u; self.cd_wave = cd_wave    # cd_wave: staly dodatek oporu w fali (z URANS, fit_polar.py); 0 = model bez dopasowania
        om = 2 * np.pi / T_WAVE; self.ome, self.k = FE.encounter(om, U); self.Te = 2 * np.pi / self.ome; self.om0 = om
        self.a, self.A0, self.beta = wave_amp, wave_amp * om, wave_phase
        self.F = Foil(c=C, U=U, N=N, h=depth_image, dt=dt, wake_len=3 * U * self.Te, rho=RHO, free_surface=free_surface)
        self.q = 0.5 * RHO * U * U * C; self.th_ref = np.radians(TH_REF_DEG)
        g1 = np.linalg.solve(self.F.Abb, -U * np.ones(N)); self.dcl = RHO * U * g1.sum() / self.q   # nachylenie modelu (z obrazem) [1/rad]
        th_m = self.cl_ref / self.dcl
        if load != 1.0: self.th_ref = self.th_ref - (CL_REF - self.cl_ref) / self.dcl    # kat rownowagi przy innym obciazeniu (nachylenie modelu)
        self.mean = dict(theta0=th_m, G0=g1 * th_m, w0=self.F.Wvb @ (g1 * th_m), u0=self.F.Uvb @ (g1 * th_m))
        self.reset()

    def reset(self, theta_deg=0.0, z=0.0, v=0.0, t=0.0):
        self.S = Stepper(self.F, self.mean, self.slope)
        self.t, self.n = t, 0
        self.th, self.w_servo, self.cmd = np.radians(theta_deg), 0.0, np.radians(theta_deg)
        self.z, self.v = z, v; self.Fy = self.mass * G - BUOY; self.last = {}; self.reset_counters()

    # --- fala Airy'ego w ukladzie plata, (6.198)-(6.200) ---
    def reset_counters(self):
        """licznik najmniejszego zanurzenia wzgledem CHWILOWEJ powierzchni nad krawedzia natarcia (od tego wywolania)"""
        self.sub_min, self.sub_min_t, self.t_below_1c = np.inf, None, 0.0

    def set_irregular(self, Hs=1.5, Tp=5.0, gamma=3.3, seed=0, N=30, wmin=0.6, wmax=2.6, spread=False):
        """Fala nieregularna (przeniesione 1:1 z vortex_plant.Plant.set_irregular): JONSWAP, N skladowych liniowych (Airy), losowe fazy (seed).
        Hs=None -> powrot do fali regularnej. spread=True: fala krotkogrzbietowa, kierunki mu ~ cos^2(mu), |mu| < 90 deg, 0 = z dziobu."""
        if Hs is None:
            self.irr = None; return
        rng = np.random.default_rng(seed)
        if spread: N = 3 * N
        dw = (wmax - wmin) / N; w = wmin + dw * (np.arange(N) + rng.uniform(0.2, 0.8, N))
        wp = 2 * np.pi / Tp; sig = np.where(w <= wp, 0.07, 0.09)
        Spm = 5 / 16 * Hs ** 2 * wp ** 4 / w ** 5 * np.exp(-1.25 * (wp / w) ** 4)
        S = Spm * gamma ** np.exp(-(w - wp) ** 2 / (2 * sig ** 2 * wp ** 2)) * (1 - 0.287 * np.log(gamma))
        a = np.sqrt(2 * S * dw); k = w * w / G
        mu = np.zeros(N)
        if spread:
            for i in range(N):
                while True:
                    m = rng.uniform(-np.pi / 2, np.pi / 2)
                    if rng.uniform() < np.cos(m) ** 2: mu[i] = m; break
        kx, ky = k * np.cos(mu), k * np.sin(mu)
        self.irr = dict(a=a, w=w, k=k, kx=kx, ky=ky, mu=mu, we=w + kx * U, eps=rng.uniform(0, 2 * np.pi, N), Hs_check=4 * np.sqrt((a ** 2 / 2).sum()))

    def gust(self, x, t):
        if self.irr is not None:
            I = self.irr; psi = I["kx"][:, None] * np.asarray(x)[None, :] - (I["we"] * t - I["eps"])[:, None]
            A = (I["a"] * I["w"] * np.exp(-I["k"] * (DEPTH - self.z)))[:, None]; cm = np.cos(I["mu"])[:, None]
            return (A * cm * np.cos(psi)).sum(0), (A * np.sin(psi)).sum(0)
        psi = self.k * x - self.ome * t + self.beta; A = self.A0 * np.exp(-self.k * (DEPTH - self.z))
        return A * np.cos(psi), A * np.sin(psi)

    def eta_LE(self, t=None):
        t = self.t if t is None else t
        if self.irr is not None:
            I = self.irr; return float((I["a"] * np.cos(-I["we"] * t + I["eps"])).sum())
        return self.a * np.cos(-self.ome * t + self.beta)

    def w_surface(self, t=None):
        t = self.t if t is None else t
        if self.irr is not None:
            I = self.irr; return float((I["a"] * I["w"] * np.sin(-I["we"] * t + I["eps"])).sum())
        return self.a * self.om0 * np.sin(-self.ome * t + self.beta)

    def eta_ahead(self, d, t=None, y=0.0):
        """wzniesienie fali d metrow PRZED krawedzia natarcia i y metrow w bok, w chwili t (czujnik podgladu fali)"""
        t = self.t if t is None else t
        if self.irr is not None:
            I = self.irr; return float((I["a"] * np.cos(-I["kx"] * d + I["ky"] * y - I["we"] * t + I["eps"])).sum())
        return self.a * np.cos(-self.k * d - self.ome * t + self.beta)

    def submergence(self, t=None):
        """chwilowe zanurzenie plata pod powierzchnia nad krawedzia natarcia [m]"""
        return max(0.05, self.eta_LE(t) - (self.z - DEPTH))

    def heave_update(self, dt):
        """plat sztywno zwiazany z masa; podklasa (zawieszenie, zlecenie D) nadpisuje te metode"""
        self.v += dt * (self.Fy + BUOY - self.mass * G) / self.mass

    def step(self, free_heave=True, wn=40.0, zeta=1.0, th_max_deg=7.5, rate_max_deg_s=90.0):
        dt = self.dt; rmax = np.radians(rate_max_deg_s); thmax = np.radians(th_max_deg)
        w_ = self.w_servo + dt * (wn * wn * (self.cmd - self.th) - 2 * zeta * wn * self.w_servo)
        w_ = float(np.clip(w_, -rmax, rmax)); th_new = self.th + w_ * dt
        if abs(th_new) > thmax: th_new = float(np.clip(th_new, -thmax, thmax)); w_ = (th_new - self.th) / dt
        if free_heave: self.heave_update(dt)
        else: self.v = 0.0
        self.th, self.w_servo = th_new, w_; t_new = self.t + dt; F = self.F
        ug, wg = self.gust(F.xv, t_new); _, wc = self.gust(F.xc, t_new)
        uc = self.gust(F.xc, t_new)[0] if self.wave_u else None
        r = self.S.step(self.th - self.th_ref, w_, -self.v, gust_c=wc, gust_v=(ug, wg), u_c=uc, u_v=ug if self.wave_u else None)
        CL = self.cl_ref + r["L_lin"] / self.q
        h_loc = self.submergence(t_new)
        s_true = self.eta_LE(t_new) - (self.z - DEPTH)             # zanurzenie bez dolnego ograniczenia 0,05 m (do licznika)
        if s_true < self.sub_min: self.sub_min, self.sub_min_t = s_true, t_new
        if s_true < C: self.t_below_1c += dt
        if self.fs_lift: CL *= float(FE.cl_ratio_high_fn(h_loc, C) / FE.cl_ratio_high_fn(DEPTH, C))         # (6.144)
        CL_lin = CL
        if self.cl_max is not None and CL > 0.9 * self.cl_max:
            CL = 0.9 * self.cl_max + 0.1 * self.cl_max * np.tanh((CL - 0.9 * self.cl_max) / (0.1 * self.cl_max))
        L = CL * self.q
        Fx_pot = r["Fx"]; Fx = Fx_pot + (self.cd0 + self.cd_wave + self.k_pol * (CL - self.cl_ref) ** 2) * self.q
        dW = 0.0
        if self.fs_wave:                                                                                      # (6.145), (6.147)
            dW = float(FE.wave_resistance(FE.gamma_from_cl(CL, U, C), h_loc, U, RHO) - FE.wave_resistance(FE.gamma_from_cl(CL_REF, U, C), DEPTH, U, RHO))
            Fx += dW
        elif self.load != 1.0:     # bez powierzchni swobodnej: CD0 (z wody spokojnej przy 100 %) zawiera opor falowy dla CL = 0,642; stala poprawka na obciazenie
            dW = float(FE.wave_resistance(FE.gamma_from_cl(self.cl_ref, U, C), DEPTH, U, RHO) - FE.wave_resistance(FE.gamma_from_cl(CL_REF, U, C), DEPTH, U, RHO)); Fx += dW
        self.Fy = L; self.z += self.v * dt; self.t, self.n = t_new, self.n + 1
        self.last = dict(t=t_new, theta_deg=np.degrees(self.th), rate_deg_s=np.degrees(w_), z=self.z, v=self.v, CL=CL, CL_lin=CL_lin, L=L, Fx=Fx,
                         Fx_pot=Fx_pot, Fx_wave=dW, lift_over_weight=(L + BUOY) / (self.mass * G), P_drag_W_strip=U * Fx * SPAN, eta_LE=self.eta_LE(t_new), sub=h_loc, sub_true=s_true)
        return self.last
