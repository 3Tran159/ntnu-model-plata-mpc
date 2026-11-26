"""analyze_validation.py - srednie z ostatnich 4 okresow spotkaniowych, porownanie URANS z modelem wirowym -> VALIDATION.json"""
import csv, json
from pathlib import Path
import numpy as np
VV = Path(__file__).resolve().parent
geo = json.loads((VV.parent / "GEOMETRY_GODO.json").read_text())
TE, OME, SPAN = geo["encounter_period_s"], geo["encounter_omega_rad_s"], geo["span_m"]
# model wirowy (liniowy, nielepki), fala Godo, na 1 m rozpietosci: zmiana sredniego Fx wzgledem V0 [N/m], amplituda CL
MODEL = {"V0_fixed": (0.0, 0.364), "V1_K05_inphase": (-109.8, 0.541), "V2_K10_inphase": (-207.2, 0.718),
         "V3_7p5deg_inphase": (-370.9, 1.090), "V4_K10_antiphase": (+256.4, 0.064)}
out = {}
for tag in MODEL:
    h = VV / "runs" / tag / "history.csv"
    if not h.exists():
        continue
    rows = list(csv.DictReader(open(h)))
    t = np.array([float(r["time_s"]) for r in rows]); dt = t[1] - t[0]
    n = 4 * int(round(TE / dt))
    if len(t) < n:
        out[tag] = {"status": "za krotki przebieg"}; continue
    col = lambda k: np.array([float(r[k]) for r in rows])[-n:]
    tt = t[-n:]; h1 = lambda y: 2 * np.mean((y - y.mean()) * np.exp(-1j * OME * tt))
    fx, cl, th, pa, eta = col("AF_Fx"), col("AF_CL"), col("theta_deg"), col("P_act_W"), col("GODO_eta_at_LE")
    per = fx.reshape(4, -1).mean(1) / SPAN
    out[tag] = {"Fx_mean_N_per_m": float(fx.mean() / SPAN), "Fx_cycle_means_N_per_m": per.tolist(),
                "CL_mean": float(cl.mean()), "CL_h1_amp": float(abs(h1(cl))), "theta_h1_amp_deg": float(abs(h1(th))),
                "theta_phase_vs_eta_deg": float(np.degrees(np.angle(h1(th) / h1(eta)))), "CL_phase_vs_eta_deg": float(np.degrees(np.angle(h1(cl) / h1(eta)))),
                "P_act_mean_W_per_m": float(pa.mean() / SPAN), "CL_max": float(cl.max()), "CL_min": float(cl.min())}
if "V0_fixed" in out and "Fx_mean_N_per_m" in out["V0_fixed"]:
    f0 = out["V0_fixed"]["Fx_mean_N_per_m"]
    for tag, o in out.items():
        if "Fx_mean_N_per_m" in o:
            o["dFx_vs_V0_URANS_N_per_m"] = o["Fx_mean_N_per_m"] - f0
            o["dFx_vs_V0_model_N_per_m"] = MODEL[tag][0]; o["CL_h1_amp_model"] = MODEL[tag][1]
(VV / "VALIDATION.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
