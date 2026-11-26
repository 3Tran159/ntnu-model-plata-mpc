"""Krok 5 (kryterium przejscia): ten sam PID co w URANS (Kp 10 deg/m, Ki 2 deg/(m s), trim 3,5 deg, tick 10 ms, serwo lag2),
puszczony w modelu wirowym w petli zamknietej; porownanie z OVS_PID_BASE2 (ostatnie 4 okresy). Faza fali jak w URANS."""
import csv, json, sys, time
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
from vortex_plant import Plant, SPAN

RUN = sys.argv[1] if len(sys.argv) > 1 else "OVS_PID_BASE2"; MODE = {"OVS_PID_BASE2": "pid", "OVS_PID_PRBS1": "pid_prbs", "OVS_PID_SINE_A2": "pid_sine"}[RUN]
HIST = Path(r"T:\NTNU_GODO_CONTROL_20261109\70_godo_case\overset_runs") / RUN / "history.csv"
def knot(seed, k):
    M = (1 << 64) - 1; x = (seed * 6364136223846793005 + k * 1442695040888963407) & M
    x ^= x >> 33; x = (x * 0xff51afd7ed558ccd) & M; x ^= x >> 33; x = (x * 0xc4ceb9fe1a85ec53) & M; x ^= x >> 33
    return ((x >> 11) * (1.0 / 9007199254740992.0)) * 2 - 1
R = {}
for r in csv.DictReader(open(HIST)):
    R[round(float(r["time_s"]), 6)] = r
tu = np.array(sorted(R)); cu = lambda k: np.array([float(R[x][k]) for x in tu])
om = 2 * np.pi / 5.0
P0 = Plant()
eta = cu("GODO_eta_at_LE"); m = tu > 0.3; n = int(((tu[m][-1] - tu[m][0]) // P0.Te) * round(P0.Te / 1e-3))
zc = 2 * np.mean((eta[m][:n] - eta[m][:n].mean()) * np.exp(-1j * P0.ome * tu[m][:n])); a, beta = abs(zc), -np.angle(zc)
P = Plant(wave_amp=a, wave_phase=beta)
kp, ki, trim, tick, rel, tend = 10.0, 2.0, 3.5, 10, 1.9368, 11.6208
P.reset(theta_deg=0.0)
ie = 0.0; rows = []; t0 = time.time()
nsteps = int(round(tend / P.dt))
for i in range(nsteps):
    tt = P.t; free = tt >= rel - 0.5 * P.dt
    if i % tick == 0:
        e = -P.z; cmd = trim
        if free:
            ie = float(np.clip(ie + e * tick * P.dt, -1, 1)); cmd = trim + kp * e + ki * ie
            ts = tt - rel
            if MODE == "pid_prbs": cmd += 2.0 * knot(1, int(np.floor(ts / 0.2)))
            if MODE == "pid_sine": cmd += 2.0 * np.sin(2 * np.pi * ts / 1.9368)
        P.cmd = np.radians(np.clip(cmd, -7.5, 7.5))
    rows.append(P.step(free_heave=free))
wall = time.time() - t0
S = {k: np.array([r[k] for r in rows]) for k in rows[0]}
TE = P.Te


def win(t, t1):
    return t > t1 - 4 * TE


def h1(t, y, ref):
    A = np.c_[np.ones_like(t), np.cos(P.ome * t), np.sin(P.ome * t)]
    c = np.linalg.lstsq(A, y, rcond=None)[0]; cr = np.linalg.lstsq(A, ref, rcond=None)[0]
    return float(np.hypot(c[1], c[2])), float(np.degrees((np.arctan2(-c[2], c[1]) - np.arctan2(-cr[2], cr[1]) + np.pi) % (2 * np.pi) - np.pi))


t_last = min(tu[-1], S["t"][-1]); nper = min(4, int(np.floor((t_last - rel) / TE + 2e-3)))
wu = (tu > t_last - nper * TE) & (tu <= t_last); wm = (S["t"] > t_last - nper * TE) & (S["t"] <= t_last)
zu, thu, lwu, pdu = cu("z_m"), cu("theta_deg"), cu("GODO_lift_over_weight"), cu("P_drag_W")
zu_h1, zu_ph = h1(tu[wu], zu[wu], eta[wu]); zm_h1, zm_ph = h1(S["t"][wm], S["z"][wm], S["eta_LE"][wm])
res = {
    "heave_h1_amp_m": {"URANS": zu_h1, "model": zm_h1, "diff_pct": 100 * (zm_h1 / zu_h1 - 1)},
    "heave_phase_vs_eta_deg": {"URANS": zu_ph, "model": zm_ph},
    "theta_range_deg": {"URANS": [float(thu[wu].min()), float(thu[wu].max())], "model": [float(S["theta_deg"][wm].min()), float(S["theta_deg"][wm].max())]},
    "theta_mean_deg": {"URANS": float(thu[wu].mean()), "model": float(S["theta_deg"][wm].mean())},
    "drag_power_mean_W_strip": {"URANS": float(pdu[wu].mean()), "model": float(S["P_drag_W_strip"][wm].mean()), "diff_pct": 100 * (S["P_drag_W_strip"][wm].mean() / pdu[wu].mean() - 1)},
    "lift_over_weight_range": {"URANS": [float(lwu[wu].min()), float(lwu[wu].max())], "model": [float(S["lift_over_weight"][wm].min()), float(S["lift_over_weight"][wm].max())]},
    "z_mean_m": {"URANS": float(zu[wu].mean()), "model": float(S["z"][wm].mean())},
    "CL_max_model": float(S["CL"].max()), "CL_lin_max_model": float(S["CL_lin"].max()),
    "wave": {"amp_m": a, "phase_rad": beta}, "window_s": [float(t_last - nper * TE), float(t_last)], "periods": nper, "wall_s": wall, "us_per_step": 1e6 * wall / nsteps,
}
res["PASS_15pct"] = bool(abs(res["heave_h1_amp_m"]["diff_pct"]) <= 15 and abs(res["drag_power_mean_W_strip"]["diff_pct"]) <= 15)
Path(__file__).with_name("TEST_STEP5_%s.json" % RUN).write_text(json.dumps(res, indent=1)); print(json.dumps(res, indent=1))
try:
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(4, 1, figsize=(12, 11), sharex=True)
    ax[0].plot(tu, zu, "k", label="URANS"); ax[0].plot(S["t"], S["z"], "C3--", label="model wirowy"); ax[0].set_ylabel("nurzanie z [m]"); ax[0].legend()
    ax[1].plot(tu, thu, "k"); ax[1].plot(S["t"], S["theta_deg"], "C3--"); ax[1].set_ylabel("kąt płata θ [°]")
    ax[2].plot(tu, cu("AF_CL"), "k"); ax[2].plot(S["t"], S["CL"], "C3--"); ax[2].set_ylabel("CL")
    ax[3].plot(tu, cu("AF_Fx") / SPAN, "k", lw=0.8); ax[3].plot(S["t"], S["Fx"], "C3--", lw=0.8); ax[3].set_ylabel("Fx [N/m]"); ax[3].set_xlabel("t [s]")
    ax[3].set_ylim(-200, 900)
    for a_ in ax:
        a_.axvline(rel, c="r", ls=":", lw=0.8); a_.grid(alpha=0.3); a_.set_xlim(1.5, tend)
    fig.suptitle("Krok 5: ten sam PID w modelu wirowym (pętla zamknięta) vs URANS " + RUN); fig.tight_layout()
    fig.savefig(Path(__file__).with_name("TEST_STEP5_%s.png" % RUN), dpi=110)
except Exception as e:
    print("plot:", e)
