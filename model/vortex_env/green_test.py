"""green_test.py - W MODELU WIROWYM: wplyw czlonu falowego z funkcji Greena (fs_wave) na
 (a) test kroku 5 w petli zamknietej (PID1 / PID3 / BASE2 vs URANS, ostatnie 4 okresy), (b) opor w wodzie spokojnej vs wysokosc lotu.
Wynik: GREEN_TEST.json"""
import json, sys, csv
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
import mbpo_residual as MR
import mbpo_closedloop as MC
from vortex_plant import Plant

CASES = {"OVS_PID_BASE2": (10.0, 2.0), "OVS_PID1_GODO": (2.01, 0.196), "OVS_PID3_GODO": (22.3, 7.25)}


def cl(run, kp, ki, fs):
    d = MR.load(run); a, beta = MR.wave_fit(d, Plant())
    P = MC.ResidualPlant(resid=None, wave_amp=a, wave_phase=beta, fs_wave=fs); P.reset(theta_deg=0.0)
    trim, rel, tend = 3.5, 1.9368, min(11.6208, float(d["t"][-1])); ie = 0.0; rows = []
    for i in range(int(round(tend / P.dt))):
        free = P.t >= rel - 0.5 * P.dt
        if i % 10 == 0:
            e = -P.z; cmd = trim
            if free: ie = float(np.clip(ie + e * 0.01, -1, 1)); cmd = trim + kp * e + ki * ie
            P.cmd = np.radians(np.clip(cmd, -7.5, 7.5))
        rows.append(P.step(free_heave=free))
    t = np.array([r["t"] for r in rows]); Pd = np.array([r["P_drag_W_strip"] for r in rows])
    TE = P.Te; t_last = min(d["t"][-1], t[-1]); nper = min(4, int(np.floor((t_last - rel) / TE + 2e-3)))
    R = {}
    for r_ in csv.DictReader(open(MR.OVR / run / "history.csv")): R[round(float(r_["time_s"]), 6)] = r_
    tu = np.array(sorted(R)); Pu = np.array([float(R[x]["P_drag_W"]) for x in tu])
    wu = (tu > t_last - nper * TE) & (tu <= t_last); wm = (t > t_last - nper * TE) & (t <= t_last)
    return float(Pu[wu].mean()), float(Pd[wm].mean())


def calm(zref, fs, T=10.0):
    P = Plant(wave_amp=1e-6, fs_wave=fs); P.reset(theta_deg=3.5); ie = 0.0; rows = []
    for i in range(int(T / P.dt)):
        free = P.t >= 1.0
        if i % 10 == 0:
            e = zref - P.z; cmd = 3.5
            if free: ie = float(np.clip(ie + e * 0.01, -1, 1)); cmd = 3.5 + 6.63 * e + 1.18 * ie
            P.cmd = np.radians(np.clip(cmd, -7.5, 7.5))
        rows.append(P.step(free_heave=free))
    t = np.array([r["t"] for r in rows]); Pd = np.array([r["P_drag_W_strip"] for r in rows])
    return float(Pd[t > T - 2].mean())


if __name__ == "__main__":
    out = {"krok5": {}, "woda_spokojna": {}}
    for run, (kp, ki) in CASES.items():
        Pu, P0 = cl(run, kp, ki, False); _, P1 = cl(run, kp, ki, True)
        out["krok5"][run] = dict(URANS_W=Pu, model_W=P0, model_green_W=P1, blad_pct=100 * (P0 / Pu - 1), blad_green_pct=100 * (P1 / Pu - 1))
        print(f"{run:16s}: URANS {Pu:5.1f} W | model {P0:5.1f} W ({100*(P0/Pu-1):+5.1f} %) | model + Green {P1:5.1f} W ({100*(P1/Pu-1):+5.1f} %)", flush=True)
    for z in (0.0, -0.3, -0.6):
        a, b = calm(z, False), calm(z, True)
        out["woda_spokojna"][f"{z:+.1f}"] = dict(model_W=a, model_green_W=b)
        print(f"woda spokojna z {z:+.1f} m: model {a:5.2f} W | model + Green {b:5.2f} W", flush=True)
    (HERE / "GREEN_TEST.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
