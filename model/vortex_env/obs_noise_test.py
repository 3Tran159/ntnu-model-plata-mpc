"""obs_noise_test.py - 13.11 rano: dlaczego kat TD3 w URANS jest poszarpany i czy filtr pomaga (W MODELU WIROWYM).
Makro STAR liczy predkosc wody jako roznice eta przy LE co 10 ms (wSurf = omW/omE * d(eta)/dt), a eta w URANS ma szum i stala
doline od plata (~ -0,15 m). Model daje sygnaly gladkie, analityczne. Tu podmieniam obserwacje TD3_GODO w modelu na "jak w STAR":
roznica skonczona + szum pomiaru eta + ew. przesuniecie -0,15 m, z filtrem dolnoprzepustowym albo bez.
Wynik: OBS_NOISE.json; miara szarpania = RMS zmiany kata miedzy taktami [deg]."""
import json, sys, math
from pathlib import Path
import numpy as np, torch
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
import godo_vortex_env as G
from godo_vortex_env import GodoVortexEnv, OBS_SCALE
torch.set_num_threads(1)
sys.argv = ["x", "td3", "TD3_GODO"]; import train_rl
ag = train_rl.Agent(); ag.actor.load_state_dict(torch.load(HERE / "runs" / "TD3_GODO" / "best_actor.pt", weights_only=False))
env = GodoVortexEnv(random_phase=False); p = env.plant
OMW, OME = 2 * math.pi / 5.0, p.ome


def run(phase, fd=False, noise=0.0, offset=0.0, tau=0.0, seed=0):
    rng = np.random.default_rng(seed); o, _ = env.reset(options={"phase": phase}); done = False; rows = []
    eprev = None; wf = 0.0; ths = []
    while not done:
        raw = o * OBS_SCALE                                     # [z, v, eta, w, a_prev] (fizyczne)
        eta = p.eta_LE() + offset + noise * rng.standard_normal()
        if fd:
            w = OMW / OME * ((eta - (eprev if eprev is not None else eta)) / 0.01); eprev = eta
            if tau > 0: wf += (w - wf) * 0.01 / (tau + 0.01); w = wf
            raw = raw.copy(); raw[2] = eta; raw[3] = w
        a = ag.act((raw / OBS_SCALE).astype(np.float32), True)
        o, r, term, trunc, info = env.step(a); rows.append(info); ths.append(info["theta_deg"]); done = term or trunc
    n = len(rows); h = slice(max(0, n - 776), n); D = np.array([x["D"] for x in rows])[h]; acc = np.array([x["acc"] for x in rows])[h]
    th = np.array(ths)[h]
    return dict(term=bool(term), plat=100 * (D.mean() / env.D_cw - 1), acc=float(np.sqrt((acc ** 2).mean())), jerk=float(np.sqrt((np.diff(th) ** 2).mean())))


cases = {"czysty (jak w treningu)": dict(), "roznica eta, bez szumu": dict(fd=True), "roznica eta + szum 5 mm": dict(fd=True, noise=0.005),
         "roznica eta + szum 5 mm + dolina -0,15 m": dict(fd=True, noise=0.005, offset=-0.15),
         "j.w. + filtr 50 ms": dict(fd=True, noise=0.005, offset=-0.15, tau=0.05), "j.w. + filtr 100 ms": dict(fd=True, noise=0.005, offset=-0.15, tau=0.10)}
res = {}
for k, kw in cases.items():
    rr = [run(ph, **kw) for ph in (0.0, math.pi / 2, math.pi, 1.5 * math.pi)]; ok = [r for r in rr if not r["term"]]
    res[k] = dict(przezyl=f"{len(ok)}/4", **({m: float(np.mean([r[m] for r in ok])) for m in ("plat", "acc", "jerk")} if ok else {}))
    v = res[k]; print(f"{k:42s} {v['przezyl']}  plat {v.get('plat', float('nan')):+6.1f} %  z'' {v.get('acc', float('nan')):.2f}  szarpanie kata {v.get('jerk', float('nan')):.3f} deg/takt", flush=True)
(HERE / "OBS_NOISE.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
