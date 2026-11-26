import csv, pathlib
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

R = pathlib.Path(r"T:\NTNU_GODO_CONTROL_20261109\70_godo_case\overset_runs")
OUT = pathlib.Path(r"T:\NTNU_GODO_CONTROL_20261109\70_godo_case\plots"); OUT.mkdir(exist_ok=True)


def load(run):
    D = {}
    for r in csv.DictReader(open(R / run / "history.csv")):
        try:
            D[round(float(r["time_s"]), 6)] = r
        except Exception:
            pass
    t = np.array(sorted(D))
    g = lambda k: np.array([float(D[x][k]) if D[x][k] else np.nan for x in t])
    return t, g


runs = [("OVS_PID_BASE2", "PID (baseline)", "#1f77b4"), ("OVS_PID_PRBS1", "PID + PRBS ±2°", "#ff7f0e"), ("OVS_PID_SINE_A2", "PID + sinus ±2° (w toku)", "#2ca02c")]
fig, ax = plt.subplots(5, 1, figsize=(13, 15), sharex=True)
for run, lab, c in runs:
    t, g = load(run)
    P = g("P_drag_W") + g("P_act_W")
    Pm = np.convolve(P, np.ones(1937) / 1937, "same"); Pm[:968] = np.nan; Pm[-968:] = np.nan
    ax[0].plot(t, g("z_m"), c=c, lw=1, label=lab)
    ax[1].plot(t, g("theta_deg"), c=c, lw=1)
    ax[2].plot(t, g("GODO_lift_over_weight"), c=c, lw=1)
    ax[3].plot(t, P, c=c, lw=0.6, alpha=0.5); ax[3].plot(t, Pm, c=c, lw=2.2)
    if run == "OVS_PID_BASE2":
        ax[4].plot(t, g("GODO_eta_at_LE"), c="k", lw=1, label="η nad LE")
        ax[4].plot(t, g("GODO_eta_upstream_quarter_lambda"), c="0.6", lw=1, label="η λ/4 przed płatem")
for a in ax:
    a.axvline(1.9368, c="r", ls="--", lw=0.8); a.grid(alpha=0.3)
ax[0].set_ylabel("heave z [m]"); ax[0].legend(loc="upper right")
ax[0].axhline(0.75, c="r", lw=0.6); ax[0].axhline(-0.75, c="r", lw=0.6)
ax[1].set_ylabel("kąt płata θ [°]"); ax[1].axhline(7.5, c="r", lw=0.6); ax[1].axhline(-7.5, c="r", lw=0.6)
ax[2].set_ylabel("lift / weight [-]")
ax[3].set_ylim(-150, 260); ax[3].set_xlim(left=1.5)
ax[3].set_ylabel("moc U·Fx + P_act [W / 0,02 m]\n(gruba linia: średnia z 1 okresu)")
ax[4].set_ylabel("fala η [m]"); ax[4].legend(loc="upper right"); ax[4].set_xlabel("t [s]   (czerwona przerywana: zwolnienie heave, t = Te)")
fig.suptitle("Godø w URANS-VOF: obracany płat + swobodny heave — przebiegi z nocy 10/11.11", fontsize=13)
fig.tight_layout(); fig.savefig(OUT / "overnight_runs.png", dpi=110)

fig, ax = plt.subplots(1, 2, figsize=(13, 4))
for run, lab, c in (("OVS_PID_BASE", "stary: smoothstep w ticku", "#d62728"), ("OVS_PID_BASE2", "nowy: model serwa", "#1f77b4")):
    t, g = load(run); m = (t > 2.40) & (t < 2.55)
    ax[0].plot(t[m], g("AF_Fx")[m], c=c, label=lab)
    mm = t > 2.2; y = g("AF_Fx")[mm]; y = y - np.convolve(y, np.ones(50) / 50, "same")
    f = np.fft.rfftfreq(mm.sum(), 1e-3); A = np.abs(np.fft.rfft(y)) * 2 / mm.sum()
    ax[1].semilogy(f, A, c=c, lw=0.8, label=lab)
ax[0].set_xlabel("t [s]"); ax[0].set_ylabel("Fx [N]"); ax[0].legend(); ax[0].grid(alpha=0.3)
ax[1].set_xlim(0, 260); ax[1].set_xlabel("f [Hz]"); ax[1].set_ylabel("amplituda Fx [N]"); ax[1].legend(); ax[1].grid(alpha=0.3)
fig.suptitle("Drgania Fx 100/200 Hz: przed i po modelu serwa"); fig.tight_layout(); fig.savefig(OUT / "fx_ripple.png", dpi=110)
print("ok")
