# 17.11 (pytanie Julka: "czy model MPC zgadza sie z Faltinsenem?"): test POZA danymi identyfikacji.
# Faltinsen B na falach S1-S3 (ziarna 0, 1 - identyfikacja byla na 900-903), katem steruje PID + PRBS jak w collect().
# Co 1 s: model MPC dostaje stan i PRAWDZIWY przyszly ciag komend i fali, przewiduje otwarta petla 0,5 / 1,0 / 1,94 s naprzod;
# porownanie z Faltinsenem: sila nosna, opór (wahania wokol sredniej), z.
import os, sys, json
os.environ.setdefault("MPC_W_A", "0")
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
import mpc_komfort as MK
m = MK.model(None); DT, NL, NW = MK.DT, MK.NL, MK.NW
H = 194; mp = MK.MPC(m, H, 5)
OUT = {}
for sea in ("S1", "S2", "S3"):
    for seed in (0, 1):
        rng = np.random.default_rng(seed); p, trim = MK.plant(sea, seed); p.reset(theta_deg=trim); p.cmd = np.radians(trim)
        for _ in range(1000): p.step(free_heave=False)
        integ, kp, A, prbs = 0.0, 4.0, 1.5, 0.0; rows = []
        for k in range(int(60.0 / DT)):
            if k % 15 == 0: prbs = rng.choice([-1, 1]) * rng.uniform(0, 2.0)
            e = -p.z; integ += e * DT; cmd = trim + kp * e + 1.0 * integ + A * np.sin(2.5 * p.t + seed) + prbs
            p.cmd = np.radians(np.clip(cmd, -7.5, 7.5)); th0, thd0, z0, v0, t0 = p.th, p.w_servo, p.z, p.v, p.t; Ls = Ds = 0.0
            for _ in range(p.tick):
                r = p.step(True); Ls += r["L"]; Ds += r["Fx"]
            rows.append([th0, thd0, z0, v0, p.cmd, Ls / p.tick, Ds / p.tick * MK.SPAN, MK.wf_at(p, t0)])
        a = np.array(rows); th, thd, z, v, u, L, D, wf = a.T
        Lm, Dm = L.mean(), D.mean(); err = {h: dict(L=[], D=[], z=[]) for h in (50, 100, 194)}; refL, refD = L.std(), D.std()
        for k0 in range(1000, len(a) - H, 100):
            th_h = th[k0 - NL:k0][::-1]; v_h = v[k0 - NL:k0][::-1]; wf_h = wf[k0 - NW + 1:k0 + 1][::-1]      # jak w run(): historia bez biezacego th/v, wf z biezacym
            f, zz = mp.sim(np.array([th[k0], thd[k0]]), th_h, v_h, wf_h, z[k0], v[k0], u[k0:k0 + H], wf[k0 + 1:k0 + 1 + H])
            Lp = f[:, 5] + m["l0"]; Dp = f @ m["p"] + np.einsum("kf,fg,kg->k", f, m["M"], f)
            for h in err:
                s = slice(0, h); err[h]["L"].append(Lp[s] - L[k0:k0 + h]); err[h]["z"].append(zz[s] - z[k0:k0 + h])
                d1 = Dp[s] - Dp[s].mean(); d2 = D[k0:k0 + h] - D[k0:k0 + h].mean(); err[h]["D"].append(d1 - d2)
        OUT[f"{sea}_s{seed}"] = {f"{h * DT:.2f}s": dict(L_rms_pct_std=float(100 * np.sqrt(np.mean(np.concatenate(err[h]["L"]) ** 2)) / refL),
                                                    D_rms_pct_std=float(100 * np.sqrt(np.mean(np.concatenate(err[h]["D"]) ** 2)) / refD),
                                                    z_rms_m=float(np.sqrt(np.mean(np.concatenate(err[h]["z"]) ** 2)))) for h in err}
        print(sea, seed, json.dumps(OUT[f"{sea}_s{seed}"]), flush=True)
(HERE / "SPRAWDZ_MODEL_MPC.json").write_text(json.dumps(OUT, indent=1))
