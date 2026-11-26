"""plot_validation.py - rysunek: sila nosna przy ruchu z URANS (PID1) bez i z pozioma predkoscia fali + moc oporu w petli zamknietej. Wynik: VALIDATION.png"""
import json, sys
from pathlib import Path
import numpy as np, matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
import validate_urans as V
from faltinsen_plant import FaltinsenPlant
d = V.load("OVS_PID1_GODO"); P0 = FaltinsenPlant(); a, beta, _ = V.wave_fit(d, P0.ome, P0.Te); w = V.window(d["t"], d["t"][-1], P0.Te, 2)
fig, ax = plt.subplots(1, 2, figsize=(12, 4.2))
ax[0].plot(d["t"][w], d["CL"][w], "k", lw=2, label="w URANS")
for lab, kw, st in (("w modelu, bez u (A)", dict(wave_u=False), "C1--"), ("w modelu, z u (B)", dict(wave_u=True), "C0-")):
    P = FaltinsenPlant(wave_amp=a, wave_phase=beta, **kw); P.reset(theta_deg=d["th"][0], z=d["z"][0], v=d["v"][0], t=d["t"][0] - P.dt); cl = np.zeros(len(d["t"]))
    for i in range(len(d["t"])):
        P.th = np.radians(d["th"][i]); P.w_servo = np.radians(d["thd"][i]); P.v = d["v"][i]; P.z = d["z"][i]; cl[i] = V.kin_step(P)["CL"]
    ax[0].plot(d["t"][w], cl[w], st, label=lab)
ax[0].set_xlabel("czas [s]"); ax[0].set_ylabel("wspolczynnik sily nosnej CL [-]"); ax[0].set_title("PID1: sila nosna przy tym samym ruchu i fali (ostatnie 2 okresy)"); ax[0].legend(); ax[0].grid(alpha=.3)
o = json.loads((HERE / "VALIDATION.json").read_text()); runs = V.RUNS; x = np.arange(len(runs)); bw = 0.2
ax[1].bar(x - 1.5 * bw, [o[f"{r}|B_2pi_z_u|petla_zamknieta"]["URANS"]["P_drag_W"] for r in runs], bw, color="k", label="w URANS")
for j, (vn, lab, col) in enumerate((("A_2pi_bez_u", "w modelu A (bez u)", "C1"), ("B_2pi_z_u", "w modelu B (z u, bez dopasowania)", "C0"), ("E_2pi_z_u_staly_dodatek_w_fali", "w modelu E (B + staly dodatek oporu z URANS)", "C2"))):
    ax[1].bar(x + (j - 0.5) * bw, [o[f"{r}|{vn}|petla_zamknieta"]["model"]["P_drag_W"] for r in runs], bw, color=col, label=lab)
ax[1].axhline(V.P_CALM, color="gray", ls=":"); ax[1].text(3.45, V.P_CALM + 1, "woda spokojna 61,1 W", ha="right", color="gray")
ax[1].set_xticks(x); ax[1].set_xticklabels(["PID1", "PID2", "PID3", "TD3"]); ax[1].set_ylabel("srednia moc oporu [W na pasek 0,02 m]"); ax[1].set_title("Petla zamknieta: moc oporu, ostatnie 4 okresy spotkania"); ax[1].legend(fontsize=8); ax[1].grid(alpha=.3, axis="y")
fig.tight_layout(); fig.savefig(HERE / "VALIDATION.png", dpi=130)
