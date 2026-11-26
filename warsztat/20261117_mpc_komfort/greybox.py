"""greybox.py - etap A planu "samouczacy sie sterownik" (17.11): model fizyczny plata z 8 nazwanymi parametrami
i sprawdzenie, jak dobrze odtwarza Faltinsena B (ten sam test co sprawdz_model_mpc.py dla modelu ARX MPC: 0,5 / 1,0 / 1,94 s naprzod).

Model (na metr rozpietosci, krok DT = 10 ms):
  V   = U + cw*u                     predkosc naplywu (u: pozioma predkosc wody od fali na glebokosci plata)
  a   = th - a0 + (cw*w - v)/V       kat, ktory czuje woda
  L*  = 0.5 rho V^2 c CLa a          sila bez opoznienia
  L_k = e L_{k-1} + (1-e) L*_k + ma*(d(cw*w)/dt - dv/dt),  e = exp(-DT/tau)
  D   = 0.5 rho V^2 c (CD0 + k CL^2) - L (cw*w - v)/V        (CL = L / (0.5 rho V^2 c); ostatni wyraz = ciag z pochylenia sily)
Serwo (wn, zeta) i lodz (m dv/dt = L + B - m g) jak w Faltinsenie. Parametry dopasowane metoda najmniejszych kwadratow
do 'manewrow wizarda' w Faltinsenie B: schodki trymu na spokojnej wodzie + potrzasanie katem na lekkiej fali."""
import os, sys, json, math
os.environ.setdefault("MPC_W_A", "0")
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
import mpc_komfort as MK
Z, FP, U, G, BUOY, MASS, DT = MK.Z, MK.FP, MK.U, MK.G, MK.BUOY, MK.MASS, MK.DT
RHO, C = 1000.0, MK.C
NAMES = ["CLa", "a0_deg", "tau", "ma", "CD0", "k", "cw"]


def uw(p):
    u, w = p.gust(p.F.xc, p.t); return float(np.mean(u)), float(np.mean(w))


def run(sea, seed, T, mode, rng):
    """mode 'kroki': spokojna woda, schodki trymu; 'trzes': fala + PID + PRBS + sinus (jak wizard krok 2-3)"""
    if sea is None: p = Z.FaltinsenPlant(wave_amp=0.0, **Z.VB); trim = None
    else: p, _ = MK.plant(sea, seed)
    cl_eq = (FP.MASS * G - BUOY) / p.q; trim = FP.TH_REF_DEG + float(np.degrees((cl_eq - FP.CL_REF) / (p.slope * p.dcl)))
    p.reset(theta_deg=trim); p.cmd = np.radians(trim)
    for _ in range(1000): p.step(free_heave=False)
    rows, integ, prbs = [], 0.0, 0.0
    for k in range(int(T / DT)):
        if mode == "kroki":
            cmd = trim + [0, 0.5, -0.5, 1.0, -1.0, 0.25][(k // 300) % 6]
            free = False
        else:
            if k % 15 == 0: prbs = rng.choice([-1, 1]) * rng.uniform(0, 1.0)
            e = -p.z; integ += e * DT; cmd = trim + 3.0 * e + 0.5 * integ + 0.7 * np.sin(2 * np.pi * (0.2 + 0.03 * k * DT) * k * DT) + prbs; free = True
        p.cmd = np.radians(np.clip(cmd, -7.5, 7.5)); th0, v0, z0 = p.th, p.v, p.z; u0, w0 = uw(p); Ls = Ds = 0.0
        for _ in range(p.tick):
            r = p.step(free_heave=free); Ls += r["L"]; Ds += r["Fx"]
        rows.append([th0, v0, z0, u0, w0, Ls / p.tick, Ds / p.tick])
        if abs(p.z) > 0.8: break
    return np.array(rows)


def lift_sim(par, d, L0=None):
    CLa, a0, tau, ma, CD0, kk, cw = par; th, v, z, u, w, Lm, Dm = d.T
    V = U + cw * u; a = th - np.radians(a0) + (cw * w - v) / V; Ls = 0.5 * RHO * V ** 2 * C * CLa * a
    e = math.exp(-DT / tau); L = np.empty_like(Ls); L[0] = Lm[0] if L0 is None else L0
    dww = np.r_[0, np.diff(cw * w)] / DT; dvv = np.r_[0, np.diff(v)] / DT
    for i in range(1, len(L)): L[i] = e * L[i - 1] + (1 - e) * Ls[i] + ma * (dww[i] - dvv[i])
    CL = L / (0.5 * RHO * V ** 2 * C); D = 0.5 * RHO * V ** 2 * C * (CD0 + kk * CL ** 2) - L * (cw * w - v) / V
    return L, D


def resid(par, data):
    out = []
    for d in data:
        L, D = lift_sim(par, d); out += [(L - d[:, 5]) / 1000.0, (D - d[:, 6]) / 20.0]
    return np.concatenate(out)


if __name__ == "__main__":
    rng = np.random.default_rng(7)
    ar = 25.6; h_c = 1.09 / C
    p0 = np.array([2 * np.pi * ar / (ar + 2) * 0.9, -1.0, 2.5 * C / U, RHO * np.pi * (C / 2) ** 2, 0.009, 1 / (np.pi * ar * 0.9) * 0 + 0.02, 1.0])   # z geometrii
    lo = [2.0, -6.0, 0.005, 0.0, 0.0, 0.0, 0.5]; hi = [8.0, 4.0, 0.5, 500.0, 0.05, 0.5, 1.5]
    train = [run(None, 0, 18.0, "kroki", rng)] + [run(s, sd, 40.0, "trzes", rng) for s in ("S1", "S3") for sd in (900, 901)]
    fit = least_squares(resid, p0, bounds=(lo, hi), args=(train,), x_scale="jac")
    par = fit.x; print("parametry:", json.dumps(dict(zip(NAMES, np.round(par, 4).tolist()))), "start z geometrii:", json.dumps(dict(zip(NAMES, np.round(p0, 4).tolist()))), flush=True)
    res = {}
    for sea in ("S1", "S2", "S3"):
        for seed in (0, 1):
            d = run(sea, seed, 40.0, "trzes", np.random.default_rng(seed)); sL, sD = d[:, 5].std(), d[:, 6].std(); e = {h: ([], []) for h in (50, 100, 194)}
            for k0 in range(300, len(d) - 194, 100):
                L, D = lift_sim(par, d[k0:k0 + 194], L0=d[k0, 5])
                for h in e: e[h][0].append(L[:h] - d[k0:k0 + h, 5]); e[h][1].append((D[:h] - D[:h].mean()) - (d[k0:k0 + h, 6] - d[k0:k0 + h, 6].mean()))
            res[f"{sea}_s{seed}"] = {f"{h*DT:.2f}s": [round(float(100 * np.sqrt(np.mean(np.concatenate(e[h][0]) ** 2)) / sL), 1), round(float(100 * np.sqrt(np.mean(np.concatenate(e[h][1]) ** 2)) / sD), 1)] for h in e}
            print(sea, seed, "blad [% std]: sila, opór:", res[f"{sea}_s{seed}"], flush=True)
    (HERE / "GREYBOX_A.json").write_text(json.dumps(dict(par=dict(zip(NAMES, par.tolist())), p0=dict(zip(NAMES, p0.tolist())), test=res), indent=1))
