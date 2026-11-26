"""mbpo_closedloop.py - MBPO krok 2: model wirowy + poprawka z URANS w PETLI ZAMKNIETEJ (test kroku 5).
Ten sam PID co w URANS, faza fali dopasowana, zwolnienie nurzania po 1 okresie, 11,62 s, srednie z ostatnich 4 okresow.
Trzy modele: bazowy (v2), poprawiony BEZ testowanego przebiegu (uczciwy test), poprawiony na wszystkich.
Wynik: MBPO_CLOSEDLOOP.json. Wszystko "w modelu wirowym (poprawionym z URANS)" vs "w URANS"."""
import csv, json, sys, time
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
import vortex_plant as VP
from vortex_plant import Plant, DEPTH, SPAN
import mbpo_residual as MR

CASES = {"OVS_PID_BASE2": (10.0, 2.0), "OVS_PID1_GODO": (2.01, 0.196), "OVS_PID3_GODO": (22.3, 7.25)}


class ResidualPlant(Plant):
    def __init__(self, resid=None, **kw):
        self.resid = resid; self.hist = []; self.dL = 0.0; self.dFx = 0.0
        super().__init__(**kw)

    def reset(self, *a, **kw):
        super().reset(*a, **kw); self.hist = []; self.dL = 0.0; self.dFx = 0.0

    def step(self, *a, **kw):
        r = super().step(*a, **kw)
        if self.resid is not None:
            if (self.n - 1) % MR.EVERY == 0:
                sub = self.eta_LE() - (self.z - DEPTH)
                self.hist.append(MR.base_feats(*[np.atleast_1d(x) for x in (self.th, self.w_servo, self.v, self.z, self.eta_LE(), self.w_surface(), sub, r["CL_lin"])])[0])
                if len(self.hist) > max(MR.LAGS) + 1: del self.hist[0]
                Hh = np.array(self.hist); need = max(MR.LAGS) + 1
                if len(Hh) < need: Hh = np.vstack([np.repeat(Hh[:1], need - len(Hh), 0), Hh])
                X = MR.features(Hh)[-1:]
                self.dL, self.dFx = (float(v) for v in self.resid.predict(X)[0])
            self.Fy += self.dL
            r["Fx"] += self.dFx; r["L"] += self.dL; r["P_drag_W_strip"] = VP.U * r["Fx"] * SPAN
        return r


def closed_loop(run, kp, ki, resid):
    d = MR.load(run); P0 = Plant(); a, beta = MR.wave_fit(d, P0)
    P = ResidualPlant(resid=resid, wave_amp=a, wave_phase=beta); P.reset(theta_deg=0.0)
    trim, tick, rel, tend = 3.5, 10, 1.9368, min(11.6208, float(d["t"][-1]))
    ie = 0.0; rows = []
    for i in range(int(round(tend / P.dt))):
        tt = P.t; free = tt >= rel - 0.5 * P.dt
        if i % tick == 0:
            e = -P.z; cmd = trim
            if free: ie = float(np.clip(ie + e * tick * P.dt, -1, 1)); cmd = trim + kp * e + ki * ie
            P.cmd = np.radians(np.clip(cmd, -7.5, 7.5))
        rows.append(P.step(free_heave=free))
    t = np.array([r["t"] for r in rows]); Pd = np.array([r["P_drag_W_strip"] for r in rows]); z = np.array([r["z"] for r in rows])
    TE = P.Te; t_last = min(d["t"][-1], t[-1]); nper = min(4, int(np.floor((t_last - rel) / TE + 2e-3)))
    wm = (t > t_last - nper * TE) & (t <= t_last)
    R = {}
    for r_ in csv.DictReader(open(MR.OVR / run / "history.csv")): R[round(float(r_["time_s"]), 6)] = r_
    tu = np.array(sorted(R)); Pu = np.array([float(R[x]["P_drag_W"]) for x in tu]); zu = np.array([float(R[x]["z_m"]) for x in tu])
    wu = (tu > t_last - nper * TE) & (tu <= t_last)
    return dict(P_URANS=float(Pu[wu].mean()), P_model=float(Pd[wm].mean()), err_pct=float(100 * (Pd[wm].mean() / Pu[wu].mean() - 1)),
                z_rng_URANS=[float(zu[wu].min()), float(zu[wu].max())], z_rng_model=[float(z[wm].min()), float(z[wm].max())])


if __name__ == "__main__":
    t0 = time.time(); sets = {}
    for run in MR.RUNS:
        r = MR.replay_run(run)
        if r is None: continue
        A, k = r["A"], r["keep"]
        sets[run] = (MR.features(MR.base_feats(*[A[:, j] for j in (1, 2, 3, 4, 5, 6, 7, 8)]))[k], np.c_[A[k, 10] - A[k, 9], A[k, 12] - A[k, 11]])
    full = MR.Ridge().fit(np.vstack([s[0] for s in sets.values()]), np.vstack([s[1] for s in sets.values()]), 1e-3)
    out = {}
    for run, (kp, ki) in CASES.items():
        loo = MR.Ridge().fit(np.vstack([sets[r][0] for r in sets if r != run]), np.vstack([sets[r][1] for r in sets if r != run]), 1e-3)
        out[run] = {}
        for name, res in (("bazowy_v2", None), ("poprawiony_bez_tego_przebiegu", loo), ("poprawiony_wszystkie", full)):
            c = closed_loop(run, kp, ki, res); out[run][name] = c
            print(f"{run:16s} {name:30s}: moc oporu URANS {c['P_URANS']:5.1f} W, model {c['P_model']:5.1f} W ({c['err_pct']:+5.1f} %) | z URANS {c['z_rng_URANS'][0]:+.2f}..{c['z_rng_URANS'][1]:+.2f}, model {c['z_rng_model'][0]:+.2f}..{c['z_rng_model'][1]:+.2f} m", flush=True)
            (HERE / "MBPO_CLOSEDLOOP.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("gotowe", round(time.time() - t0), "s")
