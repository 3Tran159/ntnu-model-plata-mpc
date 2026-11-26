import os
"""godo_vortex_env.py - krok 6: srodowisko Gymnasium "plat GodÃ¸ w fali" na skalibrowanym modelu wirowym (Plant).

Jak u GodÃ¸ 2024 (Ocean Eng 312, 119236), z roznicami opisanymi ponizej:
  obserwacje (znormalizowane): z, dz/dt, wzniesienie fali nad LE, pionowa predkosc wody na poziomie sredniej powierzchni, poprzednia komenda
  akcja: kat plata, a in [-1, 1] -> theta_cmd = a * 7,5 deg (komenda dla serwa lag2 jak w makrze URANS)
  epizod: 8 okresow spotkania (Te = 1,94 s -> 15,5 s)
  nagroda (GodÃ¸ eq. 1-8): R = Sg * (r_sv + r_z + r_s + r_rate + We * r_e)
     r_sv = 1 (0 gdy nastepny krok konczy epizod), r_z/r_s/r_rate = f(x, x1, x2) z tab. 2,
     r_e = (D_cw - D)/D_cw  (opor wzgledem wody spokojnej z PID 2 w tym samym modelu)
     ZAMIANA (brief): kary za moc aktuatora NIE ma (moment c/4 niezwalidowany) -> kara za predkosc kata: -W_RATE*(dtheta/dt / 90 deg/s)^2
  zakonczenie: |z| > 0,75 m lub zanurzenie wzgl. sredniej powierzchni < c/2 (GodÃ¸), albo NaN.

Roznice wzgledem GodÃ¸ (swiadome):
  * takt sterowania 100 Hz (10 ms) zamiast 80 Hz - taki sam jak w makrze GodoOversetRun, zeby polityka dala sie przeniesc 1:1 do URANS.
  * przed epizodem 1 s rozbiegu (kat 3,22 deg, nurzanie zablokowane), jak release_s = 1 s w URANS.
  * faza fali losowana na poczatku kazdego epizodu.
Parametry odpornosci (krok 8): cl_scale, cd_scale, wave_scale, obs_delay (w taktach).
Wynik w tym srodowisku to "w modelu wirowym".
"""
import json
from pathlib import Path
import numpy as np
import gymnasium as gym
from gymnasium import spaces
from vortex_plant import Plant, TH_REF_DEG, C, DEPTH, U, SPAN

HERE = Path(__file__).parent
TH_MAX_DEG = 7.5
# tab. 2 GodÃ¸
Z1, Z2 = 0.55, 0.75
S1, S2 = 2.0 * C, 1.0 * C   # NASZE (Julek): zanurzenie wzgl. CHWILOWEJ powierzchni nad LE; kara od 2c, koniec epizodu ponizej 1c
                            # (GodÃ¸: c/2 + 0,15 m i c/2 wzgl. sredniego poziomu)
R1, R2 = 45.0, 80.0
WE, SG = 1.3, 0.5
W_RATE = 0.05            # nasze: zamiennik kary za moc aktuatora
# opor wspornikow (v2, 11.11 wieczor; ZALOZENIE - brak w URANS i w modelu wirowym 2D): 2 wsporniki, cieciwa 0,4 m, t/c 12 %,
# Cf ITTC przy Re 4,2e6 = 0,0035, wsp. ksztaltu 1,25 -> 268 N na metr zanurzenia na wspornik; 2 wsporniki / 8 m plata = 67 N/m na metr
# zanurzenia; na pasek 0,02 m: 1,34 N na metr zanurzenia (lokalnego, wzgledem chwilowej powierzchni)
STRUT_K = float(os.environ.get("GODO_STRUT_K", "67.0")) * 0.02   # N/m zanurzenia na m rozpietosci x pasek; 12.11: CFD wspornika h=1,09 m -> 85,5 (338 N/m / 3,955 m)
OBS_SCALE = np.array([0.75, 1.0, 0.75, 1.0, 1.0])


def f_pen(x, x1, x2):
    if x < x1:
        return 0.0
    if x > x2:
        return -1.0
    return 0.5 * (np.cos(np.pi * (x - x1) / (x2 - x1)) - 1.0)


def calm_drag(plant_kw=None, kp=6.63, ki=1.18, t_end=6.0):
    """D_cw: opor w wodzie spokojnej, PID 2 GodÃ¸, ten sam model (srednia z ostatnich 2 s), N na pasek 0,02 m."""
    p = Plant(wave_amp=0.0, **(plant_kw or {}))
    p.reset(theta_deg=TH_REF_DEG)
    integ, fx = 0.0, []
    nsteps = int(round(t_end / p.dt))
    for n in range(nsteps):
        if n % p.tick == 0 and p.t > 1.0:
            e = 0.0 - p.z
            integ += e * p.tick * p.dt
            p.cmd = np.radians(np.clip(TH_REF_DEG + kp * e + ki * integ, -TH_MAX_DEG, TH_MAX_DEG))
        r = p.step(free_heave=p.t > 1.0)
        if p.t > t_end - 2.0:
            fx.append(r["Fx"] * SPAN)
    return float(np.mean(fx))


class GodoVortexEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, n_periods=8, warmup_s=1.0, random_phase=True, cl_scale=1.0, cd_scale=1.0, wave_scale=1.0,
                 obs_delay=0, D_cw=None, w_rate=W_RATE, seed=None, strut=True):
        super().__init__()
        self.kw = dict(cl_scale=cl_scale)
        self.cd_scale, self.wave_scale, self.obs_delay = cd_scale, wave_scale, int(obs_delay)
        self.plant = Plant(wave_amp=0.73 * wave_scale, **self.kw)
        # MBPO (12.11): GODO_RESIDUAL=<pkl> -> model wirowy + poprawka z URANS; GODO_RANDOMIZE=1 -> losowanie CL/fali/opoznienia co epizod (tylko env treningowy)
        self.randomize = bool(os.environ.get("GODO_RANDOMIZE")) and random_phase
        if os.environ.get("GODO_RESIDUAL"):
            import pickle as _pk
            from mbpo_closedloop import ResidualPlant
            self.plant = ResidualPlant(resid=_pk.load(open(os.environ["GODO_RESIDUAL"], "rb"))["ridge"], wave_amp=0.73 * wave_scale, **self.kw)
        self.wave_scale0 = wave_scale
        self.n_ticks = int(round(n_periods * self.plant.Te / (self.plant.tick * self.plant.dt)))
        self.warm = int(round(warmup_s / self.plant.dt))
        self.random_phase, self.w_rate = random_phase, w_rate
        dfile = HERE / "D_CW.json"
        if D_cw is None:
            if dfile.exists():
                D_cw = json.loads(dfile.read_text())["D_cw_N_strip"]
            else:
                D_cw = calm_drag(); dfile.write_text(json.dumps({"D_cw_N_strip": D_cw, "note": "w modelu wirowym, PID2 GodÃ¸, woda spokojna"}, indent=1))
        self.D_cw = D_cw * cd_scale                       # sam plat (woda spokojna, PID2)
        self.strut_k = STRUT_K if strut else 0.0
        self.D_cw_tot = self.D_cw + self.strut_k * DEPTH  # plat + wsporniki na glebokosci projektowej
        self.observation_space = spaces.Box(-5.0, 5.0, (5,), np.float32)
        self.action_space = spaces.Box(-1.0, 1.0, (1,), np.float32)
        self._rng = np.random.default_rng(seed)

    def _obs_raw(self):
        p = self.plant
        return np.array([p.z, p.v, p.eta_LE(), p.w_surface(), self.prev_a], dtype=np.float64)

    def _obs(self):
        o = self._obs_raw() / OBS_SCALE
        self.obs_hist.append(o)
        o = self.obs_hist[-1 - self.obs_delay] if len(self.obs_hist) > self.obs_delay else self.obs_hist[0]
        o = o.copy(); o[4] = self.prev_a          # poprzednia komenda jest znana bez opoznienia
        if len(self.obs_hist) > 4:
            del self.obs_hist[0]
        return np.clip(o, -5, 5).astype(np.float32)

    def reset(self, seed=None, options=None):
        if seed is not None:
            self._rng = np.random.default_rng(seed)
        p = self.plant
        p.beta = float(self._rng.uniform(0, 2 * np.pi)) if self.random_phase else 0.0
        if options and "phase" in options:
            p.beta = float(options["phase"])
        if self.randomize:
            p.cl_scale = float(self._rng.uniform(0.85, 1.15))
            p.a = 0.73 * self.wave_scale0 * float(self._rng.uniform(0.9, 1.1)); p.A0 = p.a * 2 * np.pi / 5.0
            self.obs_delay = int(self._rng.integers(0, 2))
        p.reset(theta_deg=TH_REF_DEG)
        p.cmd = np.radians(TH_REF_DEG)
        for _ in range(self.warm):
            p.step(free_heave=False)
        self.prev_a = TH_REF_DEG / TH_MAX_DEG
        self.k, self.obs_hist = 0, []
        return self._obs(), {}

    def step(self, action):
        p = self.plant
        a = float(np.clip(np.asarray(action).reshape(-1)[0], -1, 1))
        p.cmd = np.radians(a * TH_MAX_DEG)
        fx, rate_max, v0, psh, ppos = 0.0, 0.0, p.v, 0.0, 0.0
        for _ in range(p.tick):
            r = p.step(free_heave=True)
            fx += r["Fx"]; rate_max = max(rate_max, abs(r["rate_deg_s"]))
            psh += r["P_shaft_W_strip"] / p.tick; ppos += max(0.0, r["P_shaft_W_strip"]) / p.tick
        D = fx / p.tick * SPAN * self.cd_scale
        self.k += 1
        z = p.z; sub = p.eta_LE() - (p.z - DEPTH)     # lokalne zanurzenie [m]: powierzchnia nad LE minus polozenie plata
        bad = (not np.isfinite(z)) or abs(z) > Z2 or sub < S2
        trunc = self.k >= self.n_ticks
        r_sv = 0.0 if bad else 1.0
        r_z = f_pen(abs(z), Z1, Z2)
        r_s = f_pen(-sub, -S1, -S2)
        r_rate = f_pen(rate_max, R1, R2) - self.w_rate * (r["rate_deg_s"] / 90.0) ** 2
        D_strut = self.strut_k * max(sub, 0.0); D_tot = D + D_strut
        r_e = (self.D_cw_tot - D_tot) / self.D_cw_tot
        rew = SG * (r_sv + r_z + r_s + r_rate + WE * r_e)
        self.prev_a = a
        acc = (p.v - v0) / (p.tick * p.dt)
        info = dict(D=D, r_e=r_e, z=z, theta_deg=r["theta_deg"], rate=r["rate_deg_s"], acc=acc, eta=r["eta_LE"],
                    P_drag_W=U * D, CL=r["CL"], sub=sub, P_shaft=psh, P_act=ppos, D_strut=D_strut, D_tot=D_tot, P_tot_W=U * D_tot)
        return self._obs(), float(rew if np.isfinite(rew) else -10.0), bool(bad), bool(trunc and not bad), info


def pid_policy(kp=6.63, ki=1.18):
    """PID GodÃ¸ (tab. 3) w tym samym interfejsie: zwraca f(obs_raw_env) -> a.  Do porownania i testow."""
    st = {"i": 0.0}

    def act(env, o=None):
        p = env.plant
        e = 0.0 - p.z
        st["i"] += e * p.tick * p.dt
        return np.array([np.clip((TH_REF_DEG + kp * e + ki * st["i"]) / TH_MAX_DEG, -1, 1)])
    return act, st


def rollout(env, act_fn, phase=0.0, reset_state=None):
    o, _ = env.reset(options={"phase": phase})
    if reset_state is not None:
        reset_state["i"] = 0.0
    R, rows, done = 0.0, [], False
    while not done:
        a = act_fn(env, o)
        o, r, term, trunc, info = env.step(a)
        R += r; rows.append(info); done = term or trunc
    return R, rows, term


if __name__ == "__main__":
    import time
    env = GodoVortexEnv(random_phase=False)
    print("D_cw [N/pasek] =", env.D_cw, " ticks/epizod =", env.n_ticks)
    act, st = pid_policy()
    t0 = time.time(); R, rows, term = rollout(env, act, 0.0, st); dt = time.time() - t0
    D = np.mean([x["D"] for x in rows[-400:]]); z = np.array([x["z"] for x in rows])
    print(f"PID2 w fali: R={R:.1f} term={term} D={D:.3f} N ({100*(D/env.D_cw-1):+.1f}% vs woda spokojna) z {z.min():.2f}..{z.max():.2f} m, {dt:.1f} s/epizod")
