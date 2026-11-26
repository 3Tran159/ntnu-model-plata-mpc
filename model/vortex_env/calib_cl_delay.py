"""Krok 2b: kalibracja przyczynowa CL = CL_ref + sum_i k_i * L_i(t - d_i)  (i = fala, kat, nurzanie).
Wariant F (wzmocnienie + pochodna) dobrze odtwarza zadany ruch, ale w petli zamknietej czlon tau*dL_nurzanie/dt dziala jak
UJEMNA masa dodana (tau_heave*dL/dz' ~ 1,9 t/m > masa 1,57 t/m) -> niestabilne.  Rownowazny w okolicy czestosci spotkaniowej,
ale przyczynowy i bez czlonu od przyspieszenia, jest model wzmocnienie + opoznienie.
Dopasowanie: BASE2 + PRBS1, sprawdzenie: SINE_A2.  Wynik dopisywany do CALIB_CL.json jako "G_gain_delay_fit_BASE2+PRBS1"."""
import json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
import calib_cl as C   # liczy komponenty (fala/kat/nurzanie) dla 3 przebiegow

D, REL = C.D, C.REL
def shifted(x, d, dt):
    n = int(round(d / dt))
    return np.r_[np.full(n, x[0]), x[:len(x) - n]] if n > 0 else x
def design(dd, delays):
    return np.c_[tuple(shifted(dd[key], de, dd["dt"]) for key, de in zip(("clw", "clp", "clh"), delays))]
fitruns = ("OVS_PID_BASE2", "OVS_PID_PRBS1")
best = None
grid_w = np.arange(0, 0.31, 0.01); grid_p = np.arange(0, 0.11, 0.01); grid_h = np.arange(0, 0.41, 0.01)
for dw in grid_w:
    for dp in grid_p:
        for dh in grid_h:
            Xs, ys = [], []
            for r in fitruns:
                dd = D[r]; w = dd["w"]; X = design(dd, (dw, dp, dh))[w]; Xs.append(X - X.mean(0)); y = dd["cl_u"][w]; ys.append(y - y.mean())
            X = np.r_[tuple(Xs)]; y = np.r_[tuple(ys)]
            kk, *_ = np.linalg.lstsq(X, y, rcond=None); err = float(np.mean((X @ kk - y) ** 2))
            if best is None or err < best[0]:
                best = (err, (float(dw), float(dp), float(dh)), kk)
err, dl, kk = best
G = {"k_wave": float(kk[0]), "k_pitch": float(kk[1]), "k_heave": float(kk[2]), "d_wave_s": dl[0], "d_pitch_s": dl[1], "d_heave_s": dl[2]}
out = {"G_gain_delay_fit_BASE2+PRBS1": G, "G_runs": {}}
for r, dd in D.items():
    out["G_runs"][r] = C.stats(dd["cl_u"], design(dd, dl) @ kk, dd["w"])
out["G_PASS_on_validation"] = (0.9 <= out["G_runs"]["OVS_PID_SINE_A2"]["amp_ratio"] <= 1.1) and out["G_runs"]["OVS_PID_SINE_A2"]["corr"] >= 0.98
cal = json.loads(Path(C.__file__).with_name("CALIB_CL.json").read_text()); cal.update(out)
Path(C.__file__).with_name("CALIB_CL.json").write_text(json.dumps(cal, indent=1)); print(json.dumps(out, indent=1))
