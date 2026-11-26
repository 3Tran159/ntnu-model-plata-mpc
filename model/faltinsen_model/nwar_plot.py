"""nwar_plot.py - rysunek i dopasowania do NWAR_CHECK.json. Wynik: NWAR_CHECK.png, NWAR_FIT.json"""
import json, sys
from pathlib import Path
import numpy as np, matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
HERE = Path(__file__).parent
d = json.loads((HERE / "NWAR_CHECK.json").read_text()); c = d["cases"]; QS = d["QS_N"]
th = np.array([x["theta_a_deg"] for x in c]); ru = np.array([x["dCD_rest_URANS"] for x in c]); rm = np.array([x["model_B"]["rest"] / QS for x in c]); res = np.array([x["dCD_URANS_minus_model"] for x in c])
A = np.c_[np.ones_like(th), th ** 2]; cu = np.linalg.lstsq(A, ru, rcond=None)[0]; cm = np.linalg.lstsq(A, rm, rcond=None)[0]; cr = np.linalg.lstsq(A, res, rcond=None)[0]
TH_G, DCD_G = 3.57, 0.0016
fit = dict(postac="dCD = a + b * theta_a^2 (theta_a w stopniach)", rest_URANS=dict(a=cu[0], b=cu[1], przy_theta_Godo=cu[0] + cu[1] * TH_G ** 2),
           rest_model_B=dict(a=cm[0], b=cm[1], przy_theta_Godo=cm[0] + cm[1] * TH_G ** 2), URANS_minus_model=dict(a=cr[0], b=cr[1], przy_theta_Godo=cr[0] + cr[1] * TH_G ** 2,
           srednia=float(res.mean()), min=float(res.min()), max=float(res.max())), Godo=dict(theta_a_deg=TH_G, dCD_URANS_minus_model=DCD_G))
(HERE / "NWAR_FIT.json").write_text(json.dumps(fit, indent=1, default=float)); print(json.dumps(fit, indent=1, default=float))
x = np.linspace(0, 3.8, 100); fig, ax = plt.subplots(1, 2, figsize=(12, 4.2))
ax[0].plot(th, ru * 1e4, "ko", label="NWAR, w URANS: rest"); ax[0].plot(x, (cu[0] + cu[1] * x ** 2) * 1e4, "k:", lw=1)
ax[0].plot(th, rm * 1e4, "C0s", mfc="none", label="NWAR, w modelu B: rest"); ax[0].plot(x, (cm[0] + cm[1] * x ** 2) * 1e4, "C0:", lw=1)
ax[0].set_title("Reszta wzdluz naplywu (definicja NWAR): rest = dFx - tilt"); ax[0].set_ylabel("dCD_rest x 10^4 [-]")
ax[1].plot(th, res * 1e4, "ko", label="NWAR (plat nieruchomy): URANS - model B"); ax[1].plot(x, (cr[0] + cr[1] * x ** 2) * 1e4, "k:", lw=1)
ax[1].plot([TH_G], [DCD_G * 1e4], "r*", ms=14, label="Godo (plat sterowany): URANS - model B = 0,0016"); ax[1].plot([TH_G], [8], "r*", ms=9, mfc="none", label="Godo, PID3: 0,0008")
ax[1].set_title("Brakujacy opor: sredni Fx w URANS minus w modelu B"); ax[1].set_ylabel("dCD (URANS - model B) x 10^4 [-]")
for a in ax: a.axhline(0, color="gray", lw=.6); a.set_xlabel("amplituda kata naplywu od fali theta_a [deg]"); a.grid(alpha=.3); a.legend(fontsize=8)
fig.tight_layout(); fig.savefig(HERE / "NWAR_CHECK.png", dpi=130)
