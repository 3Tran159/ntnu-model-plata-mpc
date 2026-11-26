"""Gymnasium-style environment: Mini-VOF sealed flap in Stokes-V wave, dynamics = URANS-fitted surrogate ensemble.

Adaptation of Godø et al. (2024) to a clamped quasi-2D section with a trailing-edge flap (see 05_literature/GODO_2024_METHOD_EXTRACT.md)
  tick         5 ms (10 URANS steps); episode = 8 encounter periods (as Godø) = 729 ticks
  observation  [cos phi, sin phi, d_prev/d_max, (CLbar - CL_target)/CL_target/0.01]
               cos/sin phi = normalised wave elevation / vertical water velocity at the hinge (regular wave, analytic phase),
               d_prev = previous command (Godø), CLbar = running mean CL over the last encounter period (our mean-lift task)
  action       a in [-1, 1] -> flap command d = a * d_max; actuator limits applied OUTSIDE the policy:
               |d| <= 2 deg, |d_dot| <= 30 deg/s (URANS-qualified range)
  reward       r = S_g * ( W_e * R_e + R_rate + R_cl )
               R_e    = (D_ref - D)/D_ref - max(P_act/(U*D_ref), 0)          (Godø eq. 7, no regeneration)
               P_act  = max(0, -Mh * d_dot)  [W], Mh about -z (same sense as +d, trailing edge down)
               R_rate = Godø cosine ramp, 0 at 15 deg/s -> -1 at 27 deg/s     (Godø 45/80 of 90 deg/s, scaled to 30 deg/s)
               R_cl   = -W_cl * ((CLbar - CL_target)/(0.01*CL_target))^2     (replaces Godø's survival/height terms)
               S_g = 0.5, W_e = 1.3 (Godø Table 2), W_cl = 0.1
Surrogate dynamics: CL, CD, Mh at tick k+1 = ensemble mean f(sin/cos phi, sin/cos 2phi, d_{k+1}, d_k..d_{k-15}).
"""
import json, math
from pathlib import Path
import numpy as np
import torch
import importlib.util

ROOT = Path(r"T:\NTNU_GODO_CONTROL_20261109\50_learning")
spec = importlib.util.spec_from_file_location("surrogate", ROOT / "surrogate.py")
surr = importlib.util.module_from_spec(spec); spec.loader.exec_module(surr)

T_E, LAM, XH, DT_TICK = 0.4555125731921526, 10.0, 0.952, 0.005
U, Q_S = 18.0, 3855.6                       # force normalisation used by the sim (N per unit coefficient)
D_MAX, RATE_MAX = 2.0, 30.0
CL_TARGET = 0.33154336603961815             # FIXED wave mean
CD_REF = 0.0041936940349271085              # FIXED wave mean (reference drag D_ref = CD_REF*Q_S)
S_G, W_E, W_CL = 0.5, 1.3, 0.1
TICKS_PER_PERIOD = int(round(T_E / DT_TICK))  # 91
EP_TICKS = 8 * TICKS_PER_PERIOD


def ramp(x, x1, x2):
    if x < x1:
        return 0.0
    if x > x2:
        return -1.0
    return 0.5 * (math.cos(math.pi * (x - x1) / (x2 - x1)) - 1.0)


class Surrogate:
    def __init__(self, member=None):
        norm = json.loads((ROOT / "surrogate" / "norm.json").read_text())
        self.xm, self.xs = np.array(norm["xm"]), np.array(norm["xs"])
        self.ym, self.ys = np.array(norm["ym"]), np.array(norm["ys"])
        states = torch.load(ROOT / "surrogate" / "ensemble.pt")
        self.nets = []
        for s in states:
            n = surr.Net(len(self.xm), 3); n.load_state_dict(s); n.eval(); self.nets.append(n)
        if member is not None:
            self.nets = [self.nets[member]]
        self.nlag = norm["lags"][0]

    @torch.no_grad()
    def __call__(self, phi_next, d_next, d_hist):
        x = np.array([math.sin(phi_next), math.cos(phi_next), math.sin(2 * phi_next), math.cos(2 * phi_next), d_next] + list(d_hist))
        xx = torch.tensor((x - self.xm) / self.xs, dtype=torch.float32)[None]
        outs = np.stack([n(xx)[0][0].numpy() for n in self.nets]) * self.ys + self.ym
        return outs.mean(0), outs[:, 0].std()


class FlapEnv:
    obs_dim, act_dim = 4, 1

    def __init__(self, seed=0, member=None, random_start=True):
        self.model = Surrogate(member)
        self.rng = np.random.default_rng(seed)
        self.random_start = random_start

    def phi(self, k):
        return 2 * math.pi * XH / LAM - 2 * math.pi * (self.t0 + k * DT_TICK) / T_E

    def _obs(self):
        clbar = np.mean(self.cl_hist[-TICKS_PER_PERIOD:])
        p = self.phi(self.k)
        return np.array([math.cos(p), math.sin(p), self.d_hist[0] / D_MAX,
                         np.clip((clbar - CL_TARGET) / CL_TARGET / 0.01, -5, 5)], dtype=np.float32)

    def reset(self):
        self.t0 = 3.923 + (self.rng.uniform(0, T_E) if self.random_start else 0.0)
        self.k = 0
        self.d_hist = [0.0] * self.model.nlag            # d_k, d_{k-1}, ...
        self.cl_hist = [CL_TARGET] * TICKS_PER_PERIOD
        self.log = []
        return self._obs()

    def step(self, a):
        d_prev = self.d_hist[0]
        d_cmd = float(np.clip(np.asarray(a, dtype=float).reshape(-1)[0], -1, 1)) * D_MAX
        d_new = float(np.clip(d_cmd, d_prev - RATE_MAX * DT_TICK, d_prev + RATE_MAX * DT_TICK))   # actuator outside the policy
        out, spread = self.model(self.phi(self.k + 1), d_new, self.d_hist)
        CL, CD, Mh = map(float, out)
        d_dot = (d_new - d_prev) / DT_TICK                                    # deg/s
        p_act = max(0.0, -Mh * math.radians(d_dot))                          # W, no regeneration
        D = CD * Q_S; D_ref = CD_REF * Q_S
        R_e = (D_ref - D) / D_ref - max(p_act / (U * D_ref), 0.0)
        R_rate = ramp(abs(d_dot), 15.0, 27.0)
        self.cl_hist.append(CL)
        clbar = np.mean(self.cl_hist[-TICKS_PER_PERIOD:])
        R_cl = -W_CL * ((clbar - CL_TARGET) / (0.01 * CL_TARGET)) ** 2
        r = S_G * (W_E * R_e + R_rate + R_cl)
        self.d_hist = [d_new] + self.d_hist[:-1]
        self.k += 1
        self.log.append((self.phi(self.k), d_cmd, d_new, CL, CD, Mh, p_act, r, spread))
        done = self.k >= EP_TICKS
        return self._obs(), r, done, {"CL": CL, "CD": CD, "p_act": p_act, "spread": spread}
