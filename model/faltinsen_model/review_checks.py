"""review_checks.py - odpowiedz na recenzje (C1, C2, C3), 13.11:
(1) przebiegi NIEUZYTE nigdzie wczesniej: OVS_POL_TD3_C338 (petla zamknieta + ten sam ruch), OVS_MPC_WZ2 (tylko ten sam ruch, jesli dosc dlugi);
(2) reszta oporu URANS - model B dla wszystkich przebiegow obok miar ruchu plata (czy "staly" dodatek zalezy od ruchu).
Wynik: REVIEW_CHECKS.json"""
import json, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
import validate_urans as V
from faltinsen_plant import FaltinsenPlant, CL_REF, U, SPAN, DEPTH
out = {"nowe_przebiegi": {}, "reszta_a_ruch": {}}
# (1)
d = V.load("OVS_POL_TD3_C338")
_lp = V.load_policy
def lp():
    js = json.loads((HERE / "policy_TD3_C338.json").read_text()); Ls = [(np.array(l["W"]), np.array(l["b"])) for l in js["layers"]]; sc = np.array(js["obs_scale"])
    def act(o):
        x = np.clip(np.asarray(o) / sc, -5, 5); h = np.maximum(0, Ls[0][0] @ x + Ls[0][1]); h = np.maximum(0, Ls[1][0] @ h + Ls[1][1]); return float(np.tanh(Ls[2][0] @ h + Ls[2][1])[0])
    return act
V.load_policy = lp
for vn, kw in (("B", dict()), ("E", dict(cd_wave=0.0016))):
    c = V.closed_loop("OVS_POL_TD3_C338", d, kw); r = V.replay("OVS_POL_TD3_C338", d, kw)
    out["nowe_przebiegi"][f"OVS_POL_TD3_C338|{vn}"] = dict(petla=c, ruch=r)
    print(f"TD3_C338 {vn}: petla P URANS {c['URANS']['P_drag_W']:.1f} model {c['model']['P_drag_W']:.1f} ({c['err_P_pct']:+.1f} %), z p2p {c['URANS']['z_p2p_m']:.3f} / {c['model']['z_p2p_m']:.3f} ({c['err_z_p2p_pct']:+.1f} %), z sr {c['URANS']['z_mean_m']:+.3f}/{c['model']['z_mean_m']:+.3f} | ten sam ruch P {r['P_URANS_W']:.1f} / {r['P_model_W']:.1f} ({r['err_P_pct']:+.1f} %), CL h1 U/M {r['CL_h1_ratio_URANS_over_model']:.3f} faza {r['CL_h1_phase_URANS_minus_model_deg']:+.1f}", flush=True)
V.load_policy = _lp
# (2)
RUNS = ["OVS_PID_BASE2", "OVS_PID_PRBS1", "OVS_PID_SINE_A2"] + V.RUNS + ["OVS_POL_TD3_C338", "OVS_MPC_WZ2"]
for run in RUNS:
    try: d = V.load(run)
    except Exception as e: print(run, "brak", e); continue
    P0 = FaltinsenPlant(); nper = int((d["t"][-1] - V.T_REL - 0.5 * P0.Te) // P0.Te)
    if nper < 2: print(run, "za krotki", d["t"][-1]); continue
    nper = min(nper, 4); a, beta, _ = V.wave_fit(d, P0.ome, P0.Te)
    P = FaltinsenPlant(wave_amp=a, wave_phase=beta); P.reset(theta_deg=d["th"][0], z=d["z"][0], v=d["v"][0], t=d["t"][0] - P.dt); n = len(d["t"]); fx = np.zeros(n); cl = np.zeros(n); sub = np.zeros(n); wv = np.zeros(n)
    for i in range(n):
        P.th = np.radians(d["th"][i]); P.w_servo = np.radians(d["thd"][i]); P.v = d["v"][i]; P.z = d["z"][i]; r = V.kin_step(P); fx[i] = r["Fx"]; cl[i] = r["CL"]; sub[i] = P.submergence(); wv[i] = P.gust(np.array([0.078]), P.t)[1][0]
    w = d["t"] > d["t"][-1] - nper * P.Te; y = d["Fx"][w] - fx[w]; H = lambda x: 2 * np.mean((x[w] - x[w].mean()) * np.exp(-1j * P.ome * d["t"][w]))
    arel = np.radians(d["th"][w]) + (wv[w] - d["v"][w]) / U
    o = dict(okresy=nper, reszta_N_m=float(y.mean()), dCD=float(y.mean() / P.q), z_p2p_m=float(np.ptp(d["z"][w])), z_sr_m=float(d["z"][w].mean()), theta_p2p_deg=float(np.ptp(d["th"][w])),
             theta_rate_rms_deg_s=float(d["thd"][w].std()), zanurzenie_min_m=float(sub[w].min()), zanurzenie_sr_m=float(sub[w].mean()), kat_wzgledny_p2p_deg=float(np.degrees(np.ptp(arel))),
             CL_URANS_max=float(d["CL"][w].max()), CL_URANS_min=float(d["CL"][w].min()), P_URANS_W=float(U * SPAN * d["Fx"][w].mean()), P_model_B_W=float(U * SPAN * fx[w].mean()),
             P_pot_model_W=float(U * SPAN * (fx[w].mean() - 0.0104 * P.q)), CLh1_U_over_M=float(abs(H(d["CL"])) / abs(H(cl))))
    out["reszta_a_ruch"][run] = o
    print(f"{run:18s} n {nper} reszta {o['reszta_N_m']:5.1f} N/m dCD {o['dCD']:.4f} | z p2p {o['z_p2p_m']:.2f} z sr {o['z_sr_m']:+.2f} th p2p {o['theta_p2p_deg']:4.1f} rate rms {o['theta_rate_rms_deg_s']:4.1f} | sub min {o['zanurzenie_min_m']:.2f} sr {o['zanurzenie_sr_m']:.2f} | kat wzgl p2p {o['kat_wzgledny_p2p_deg']:.1f} | CL URANS {o['CL_URANS_min']:.2f}..{o['CL_URANS_max']:.2f} | P URANS {o['P_URANS_W']:.1f} model B {o['P_model_B_W']:.1f} pot {o['P_pot_model_W']:+.1f} | blad E {100*((o['P_model_B_W']+U*SPAN*0.0016*P.q)/o['P_URANS_W']-1):+.1f} %", flush=True)
R = out["reszta_a_ruch"]; y = np.array([R[r]["dCD"] for r in R])
for k in ("z_p2p_m", "z_sr_m", "theta_p2p_deg", "theta_rate_rms_deg_s", "zanurzenie_min_m", "kat_wzgledny_p2p_deg", "CL_URANS_max", "P_pot_model_W", "CLh1_U_over_M"):
    x = np.array([R[r][k] for r in R]); c = float(np.corrcoef(x, y)[0, 1]); out.setdefault("korelacja_dCD", {})[k] = c; print(f"korelacja dCD ~ {k}: {c:+.2f}")
(HERE / "REVIEW_CHECKS.json").write_text(json.dumps(out, indent=1))
