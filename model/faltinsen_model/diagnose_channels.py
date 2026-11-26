"""diagnose_channels.py - DIAGNOZA (nie czesc modelu, nic stad nie wraca do modelu): gdzie model rozni sie od URANS w sile nosnej.
(1) faza z zablokowanym nurzaniem (t = 0,6-1,9 s, kat 3,5 deg staly): sama fala -> CL(t) w URANS vs w modelu.
(2) po zwolnieniu: 1. harmoniczna CL przy ruchu z URANS rozlozona w modelu na: fale / kat / nurzanie; ile wynosi kazda i ich suma vs URANS.
Wynik: DIAGNOSE_z_u.json; z opcja --no-u (bez poziomej predkosci fali): DIAGNOSE_bez_u.json"""
import json, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
import validate_urans as V
from faltinsen_plant import FaltinsenPlant, CL_REF, U, C

out = {}
WU = "--no-u" not in sys.argv
for run in V.RUNS:
    d = V.load(run); P0 = FaltinsenPlant(); a, beta, em = V.wave_fit(d, P0.ome, P0.Te)
    parts = {}
    for name in ("fala", "kat", "nurzanie", "razem"):
        P = FaltinsenPlant(wave_amp=a if name in ("fala", "razem") else 0.0, wave_phase=beta, fs_lift=False, fs_wave=False, wave_u=WU)
        P.reset(theta_deg=d["th"][0], z=d["z"][0], v=d["v"][0], t=d["t"][0] - P.dt); cl = np.zeros(len(d["t"]))
        for i in range(len(d["t"])):
            P.th = np.radians(d["th"][i]) if name in ("kat", "razem") else P.th_ref
            P.w_servo = np.radians(d["thd"][i]) if name in ("kat", "razem") else 0.0
            P.v = d["v"][i] if name in ("nurzanie", "razem") else 0.0
            P.z = d["z"][i]
            cl[i] = V.kin_step(P)["CL"] - CL_REF
        parts[name] = cl
    t = d["t"]; w = V.window(t, t[-1], P0.Te)
    H = lambda x: 2 * np.mean((x[w] - x[w].mean()) * np.exp(-1j * P0.ome * t[w]))
    hu = H(d["CL"]); r = {k: H(v) for k, v in parts.items()}
    pre = (t > 0.6) & (t < 1.9); X = parts["fala"][pre]; Y = d["CL"][pre]
    A = np.c_[X, np.gradient(X, t[pre]), np.ones(pre.sum())]; co = np.linalg.lstsq(A, Y, rcond=None)[0]
    out[run] = dict(wave_amp_m=a,
                    h1_amp=dict(URANS=abs(hu), **{k: abs(v) for k, v in r.items()}),
                    h1_phase_vs_wave_channel_deg={k: float(np.degrees(np.angle(v / r["fala"]))) for k, v in dict(URANS=hu, **r).items()},
                    locked_phase=dict(gain_URANS_over_model=float(co[0]), lag_s=float(-co[1] / co[0]), CL_mean_URANS=float(Y.mean()), CL_p2p_URANS=float(Y.max() - Y.min()),
                                      CL_p2p_model=float(X.max() - X.min()), theta_deg=float(d["th"][pre].mean())))
    print(run, json.dumps(out[run]), flush=True)
(HERE / ("DIAGNOSE_z_u.json" if WU else "DIAGNOSE_bez_u.json")).write_text(json.dumps(out, indent=1))
