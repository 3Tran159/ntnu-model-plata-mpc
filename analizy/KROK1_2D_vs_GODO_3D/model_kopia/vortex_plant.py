"""vortex_plant.py - obiekt sterowania "plat Godø w fali" oparty o skalibrowany model wirowy 2D (kroki 3-4).

Fizyka (na 1 m rozpietosci, przelicz na pasek 0,02 m mnozac przez SPAN):
  * sila nosna: L = q*c*CL_ref + sum_i k_i L_i(t - d_i),  i = fala / kat / nurzanie
    L_i z trzech niezaleznych liniowych modeli wirowych (FoilStepper), wspolczynniki k_i i opoznienia d_i z CALIB_CL.json (wariant G: L_i(t - d_i),
    dopasowany na OVS_PID_BASE2 + OVS_PID_PRBS1, sprawdzony na OVS_PID_SINE_A2).  CL_ref = 0,642 przy theta_ref = 3,22 deg (URANS BASE2).
  * opor: Fx = Fx_model (pelny model wirowy, nielepki, bez skali) + CD_visc*q*c ; CD_visc z danych URANS (CALIB: implied_CD).
  * oderwanie (ZALOZENIE, brak danych URANS przy duzych katach): CL nasycone gladko do CL_MAX = 1.00 (najwyzsze CL w URANS 0,99,
    PRBS1); powyzej rosnie opor dCD = K_STALL*(CL_lin-CL_sat)^2.
  * nurzanie: m' dv/dt = L + B' - m' g (jawnie, jak w GodoOversetRun.java; sila z poprzedniego kroku), z w gore +.
  * serwo: 2. rzad, wn = 40 rad/s, zeta = 1, |theta| <= 7,5 deg, |dtheta/dt| <= 90 deg/s; komenda trzymana przez tick (10 ms jak w makrze).
  * fala: Airy, H = 1,46 m (amplituda dopasowana z eta nad LE w URANS: 0,73 m), T = 5 s, U = 12,35 m/s, predkosci orbitalne
    tlumione exp(-k(d - z)).
Wynik z tego modelu to "w modelu wirowym", nie dowod skutecznosci w URANS.
"""
import json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
from uvm_step import FoilStepper, Foil, G, mean_state

HERE = Path(__file__).parent
RHO, C, U, DEPTH, T_WAVE, SPAN = 1000.0, 0.312, 12.3466667, 1.09, 5.0, 0.02
MASS = 12500.0 / (25.6 * 0.312)          # kg/m  (31,3 kg na pasek 0,02 m)
BUOY = 1000 * 9.81 * 0.00795948899616472  # N/m wypornosc profilu
CL_REF, TH_REF_DEG = 0.642, 3.22
CL_MAX, K_STALL = 1.00, 0.5
# biegunowa oporu lepkiego/profilowego (v2, 11.11 wieczor): CD_v = CD0 + K_POL*(CL - CL_REF)^2
#   CD0 = 0,0104 z URANS w wodzie spokojnej (OVS_CALM_PID2, 61,1 W/pasek);  K_POL = 0,072 dopasowane (MNK) do BASE2/PRBS1/SINE_A2
#   (v1 mialo stale CD_v = 0,0121 -> w wodzie spokojnej 71,1 W zamiast 61,1 W)
CD0, K_POL = 0.0104, 0.0716


def _fs_table():
    """Wspolczynnik nachylenia CL(theta) w modelu z ujemnym obrazem (Fn_h -> inf) na glebokosci s, wzgledem s = DEPTH.
    ZALOZENIE: quasi-stacjonarnie, bez fal generowanych przez plat i bez wentylacji; Fn_h = U/sqrt(g h) = 3,8 przy h = 1,09 m."""
    S = np.r_[np.linspace(0.05, 0.6, 23), np.linspace(0.65, 3.0, 25)]
    def slope(h):
        F = Foil(c=C, U=U, N=20, h=h, dt=1e-3, wake_len=1.0, rho=RHO)
        return np.linalg.solve(F.Abb, -U * np.ones(20)).sum()
    k0 = slope(DEPTH)
    return S, np.array([slope(h) / k0 for h in S])


FS_S, FS_K = _fs_table()


class Plant:
    def __init__(self, dt=1e-3, N=20, calib=None, cd_visc=None, wave_amp=0.73, wave_phase=0.0, cl_scale=1.0, tick=10, fs_local=True, fs_wave=False):
        self.dt, self.tick, self.fs_local = dt, tick, fs_local
        self.fs_wave = fs_wave     # 12.11: opor falowy z 2D funkcji Greena powierzchni swobodnej (greenfs.py), quasi-stacjonarnie jak NDLL Godø
        cal = json.loads((HERE / "CALIB_CL.json").read_text())
        self.cal = calib or cal["G_gain_delay_fit_BASE2+PRBS1"]
        self.cd_visc = cd_visc if cd_visc is not None else CD0      # CD0 biegunowej (cd_visc = stare stale CD, gdy k_pol = 0)
        self.k_pol = K_POL
        self.cl_scale = cl_scale
        om = 2 * np.pi / T_WAVE; self.k = om * om / G; self.ome = om + self.k * U; self.Te = 2 * np.pi / self.ome
        self.a, self.A0, self.beta = wave_amp, wave_amp * om, wave_phase
        self.F = Foil(c=C, U=U, N=N, h=DEPTH, dt=dt, wake_len=3 * U * self.Te, rho=RHO)
        self.q = 0.5 * RHO * U * U * C
        self.th_ref = np.radians(TH_REF_DEG)
        # model pelny (do Fx) ze stanem srednim dopasowanym do CL_REF przy th_ref (jak replay_history)
        g1 = np.linalg.solve(self.F.Abb, -U * np.ones(N)); self.dcl = RHO * U * g1.sum() / self.q
        th_m = CL_REF / self.dcl
        self.mean_full = dict(theta0=th_m, G0=g1 * th_m, w0=self.F.Wvb @ (g1 * th_m), u0=self.F.Uvb @ (g1 * th_m))
        self.reset()

    def reset(self, theta_deg=0.0, z=0.0, v=0.0, t=0.0):
        self.S = {k: FoilStepper(self.F) for k in ("wave", "pitch", "heave")}
        self.Sf = FoilStepper(self.F, self.mean_full)
        self.prevL = {k: 0.0 for k in self.S}; self.buf = {k: [] for k in self.S}
        self.t, self.n = t, 0
        self.th, self.w_servo, self.cmd = np.radians(theta_deg), 0.0, np.radians(theta_deg)
        self.z, self.v = z, v
        self.Fy = MASS * G - BUOY      # sila z "poprzedniego kroku" na starcie: rownowaga
        self.last = {}

    def set_irregular(self, Hs=1.5, Tp=5.0, gamma=3.3, seed=0, N=30, wmin=0.6, wmax=2.6, spread=False):
        """Fala nieregularna: JONSWAP, N skladowych liniowych (Airy), losowe fazy (seed). None -> regularna.
        spread=True: fala krotkogrzbietowa, kazda skladowa z wlasnym kierunkiem mu ~ cos^2(mu), |mu| < 90 deg (ITTC), 0 = z dziobu."""
        if Hs is None:
            self.irr = None; return
        rng = np.random.default_rng(seed)
        if spread: N = 3 * N
        dw = (wmax - wmin) / N; w = wmin + dw * (np.arange(N) + rng.uniform(0.2, 0.8, N))   # losowe przesuniecie -> brak okresowosci
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
        if getattr(self, "irr", None):
            I = self.irr; psi = I["kx"][:, None] * np.asarray(x)[None, :] - (I["we"] * t - I["eps"])[:, None]
            A = (I["a"] * I["w"] * np.exp(-I["k"] * (DEPTH - self.z)))[:, None]
            cm = np.cos(I.get("mu", np.zeros(len(I["a"]))))[:, None]     # skladowa pozioma w plaszczyznie plata
            return (A * cm * np.cos(psi)).sum(0), (A * np.sin(psi)).sum(0)
        psi = self.k * x - self.ome * t + self.beta
        A = self.A0 * np.exp(-self.k * (DEPTH - self.z))
        return A * np.cos(psi), A * np.sin(psi)

    def eta_LE(self, t=None):
        t = self.t if t is None else t
        if getattr(self, "irr", None):
            I = self.irr; return float((I["a"] * np.cos(-I["we"] * t + I["eps"])).sum())
        return self.a * np.cos(-self.ome * t + self.beta)

    def w_surface(self, t=None):
        """pionowa predkosc wody na poziomie sredniej powierzchni nad LE (obserwacja Godø)"""
        t = self.t if t is None else t
        if getattr(self, "irr", None):
            I = self.irr; return float((I["a"] * I["w"] * np.sin(-I["we"] * t + I["eps"])).sum())
        return self.a * 2 * np.pi / T_WAVE * np.sin(-self.ome * t + self.beta)

    def eta_ahead(self, d, t=None, y=0.0):
        """wzniesienie fali d metrow PRZED nosem i y metrow w bok (pomiar czujnikiem), w chwili t"""
        t = self.t if t is None else t
        if getattr(self, "irr", None):
            I = self.irr; return float((I["a"] * np.cos(-I["kx"] * d + I["ky"] * y - I["we"] * t + I["eps"])).sum())
        return self.a * np.cos(-self.k * d - self.ome * t + self.beta)

    def heave_update(self, dt):
        """nurzanie plata sztywno zwiazanego z kadlubem (podklasa moze to nadpisac, np. zawieszenie)"""
        self.v += dt * (self.Fy + BUOY - MASS * G) / MASS

    def step(self, free_heave=True, wn=40.0, zeta=1.0, th_max_deg=7.5, rate_max_deg_s=90.0):
        """Jeden krok dt z aktualna komenda self.cmd [rad]."""
        dt = self.dt; rmax = np.radians(rate_max_deg_s); thmax = np.radians(th_max_deg)
        # serwo (jak GodoOversetRun actuator=lag2)
        w_ = self.w_servo + dt * (wn * wn * (self.cmd - self.th) - 2 * zeta * wn * self.w_servo)
        w_ = float(np.clip(w_, -rmax, rmax)); th_new = self.th + w_ * dt
        thc = getattr(self, "th_center", 0.0)   # KROK1: srodek zakresu kata [rad]; 0 = oryginal
        if abs(th_new - thc) > thmax:
            th_new = float(np.clip(th_new, thc - thmax, thc + thmax)); w_ = (th_new - self.th) / dt
        # nurzanie (jawnie, sila z poprzedniego kroku)
        if free_heave:
            self.heave_update(dt)
        else:
            self.v = 0.0
        self.th, self.w_servo = th_new, w_
        t_new = self.t + dt
        F = self.F
        ug, wg = self.gust(F.xv, t_new); _, wc = self.gust(F.xc, t_new)
        hd = -self.v
        thp = self.th - self.th_ref
        rw = self.S["wave"].step(0.0, 0.0, 0.0, gust_c=wc, gust_v=(ug, wg))
        rp = self.S["pitch"].step(thp, w_, 0.0)
        rh = self.S["heave"].step(0.0, 0.0, hd)
        rf = self.Sf.step(self.th - self.th_ref, w_, hd, gust_c=wc, gust_v=(ug, wg))
        cal = self.cal; Lsum = 0.0
        for key, r in (("wave", rw), ("pitch", rp), ("heave", rh)):
            if "d_" + key + "_s" in cal:             # wariant G: wzmocnienie + opoznienie (przyczynowy)
                buf = self.buf[key]; buf.append(r["L"])
                nd = int(round(cal["d_" + key + "_s"] / dt))
                Ld = buf[-1 - nd] if len(buf) > nd else buf[0]
                if len(buf) > nd + 2:
                    del buf[0]
                Lsum += cal["k_" + key] * Ld
            else:                                    # wariant F: wzmocnienie + pochodna (tylko do odtwarzania zadanego ruchu)
                dL = (r["L"] - self.prevL[key]) / dt if self.n > 0 else 0.0
                Lsum += cal["k_" + key] * r["L"] + cal["tau_" + key + "_s"] * dL
            self.prevL[key] = r["L"]
        CL_lin = CL_REF + self.cl_scale * Lsum / self.q
        if self.fs_local:      # quasi-stacjonarna poprawka na lokalne zanurzenie (obraz ujemny na glebokosci s zamiast stalej DEPTH)
            s_loc = max(0.05, self.eta_LE(t_new) - (self.z - DEPTH))
            CL_lin *= float(np.interp(s_loc, FS_S, FS_K))
        CL_sat = CL_MAX * np.tanh(CL_lin / CL_MAX) if CL_lin > 0.9 * CL_MAX else CL_lin
        if CL_lin > 0.9 * CL_MAX:      # gladkie przejscie: tanh ponizej 0.9 CL_MAX ~ liniowe
            CL_sat = 0.9 * CL_MAX + 0.1 * CL_MAX * np.tanh((CL_lin - 0.9 * CL_MAX) / (0.1 * CL_MAX))
        cd_stall = K_STALL * max(0.0, CL_lin - CL_sat) ** 2
        L = CL_sat * self.q
        Fx = rf["Fx"] + (self.cd_visc + self.k_pol * (CL_sat - CL_REF) ** 2 + cd_stall) * self.q
        if self.fs_wave:       # D_w(Gamma(t), h_lok(t)) - D_w(Gamma_ref, DEPTH): stala czesc jest juz w CD0 (dopasowanie do URANS przy 1,09 m)
            from greenfs import wave_drag
            h_loc = max(0.05, self.eta_LE(t_new) - (self.z - DEPTH))
            Fx += wave_drag(0.5 * U * C * CL_sat, h_loc, U) - wave_drag(0.5 * U * C * CL_REF, DEPTH, U)
        self.Fy = L
        self.z += self.v * dt
        self.t, self.n = t_new, self.n + 1
        self.last = dict(t=t_new, theta_deg=np.degrees(self.th), rate_deg_s=np.degrees(w_), z=self.z, v=self.v, CL=CL_sat, CL_lin=CL_lin,
                         L=L, Fx=Fx, lift_over_weight=(L + BUOY) / (MASS * G), P_drag_W_strip=U * Fx * SPAN, eta_LE=self.eta_LE(t_new),
                         Mp=rf["Mp"] * SPAN, P_shaft_W_strip=-rf["Mp"] * w_ * SPAN)   # moment c/4 NIEZWALIDOWANY: tylko informacyjnie, nie w nagrodzie
        return self.last
