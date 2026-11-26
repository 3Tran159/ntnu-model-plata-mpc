"""Krok 2: kalibracja CL modelu wirowego.
Model jest liniowy, wiec CL(t) = CL_srednie + CL_fala(t) + CL_ruch(t) (ruch = kat + nurzanie).
Dopasowanie na OVS_PID_BASE2 (okno po zwolnieniu nurzania), sprawdzenie na OVS_PID_PRBS1 i OVS_PID_SINE_A2.
Warianty: (A) jedna skala czesci oscylacyjnej k; (B) osobne skale k_fala, k_ruch.  Fx liczone bez skali (sprawdzamy, ze sie nie psuje).
Wynik: CALIB_CL.json (wspolczynniki + skad), wykres CALIB_CL.png
"""
import csv, json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
from uvm_step import Foil, G, mean_state

RUNS = Path(r"T:\NTNU_GODO_CONTROL_20261109\70_godo_case\overset_runs")
rho, c, U, depth, T, N, span = 1000.0, 0.312, 12.3466667, 1.09, 5.0, 20, 0.02
REL = 1.9368
om = 2 * np.pi / T; k = om * om / G; ome = om + k * U; Te = 2 * np.pi / ome


def load(run):
    R = {}
    for r in csv.DictReader(open(RUNS / run / "history.csv")):
        try:
            R[round(float(r["time_s"]), 6)] = r          # duplikaty po restarcie: zostaje pozniejszy zapis
        except Exception:
            pass
    t = np.array(sorted(R))
    return t, (lambda kk: np.array([float(R[x][kk]) for x in t]))


def components(run):
    t, col = load(run)
    dt = float(np.median(np.diff(t)))
    th = np.radians(col("theta_deg")); thd = np.radians(col("theta_rate_deg_s")); v = col("v_m_s"); z = col("z_m"); eta = col("GODO_eta_at_LE")
    m = t > 0.3; n = int(((t[m][-1] - t[m][0]) // Te) * round(Te / dt))
    zc = 2 * np.mean((eta[m][:n] - eta[m][:n].mean()) * np.exp(-1j * ome * t[m][:n])); a, beta = abs(zc), -np.angle(zc)
    F = Foil(c=c, U=U, N=N, h=depth, dt=dt, wake_len=3 * U * Te, rho=rho)
    idx = lambda tt: min(len(t) - 1, max(0, int(round(tt / dt)) - 1))
    A0 = a * om
    def gust(x, tt):
        psi = k * x - ome * tt + beta; A = A0 * np.exp(-k * (depth - z[idx(tt)]))
        return A * np.cos(psi), A * np.sin(psi)
    thm = th.mean()
    fw = F.simulate(len(t), gust=gust)                                                          # sama fala
    fm = F.simulate(len(t), theta=lambda tt: (th[idx(tt)] - thm, thd[idx(tt)]), heave_rate=lambda tt: -v[idx(tt)])   # sam ruch
    fp = F.simulate(len(t), theta=lambda tt: (th[idx(tt)] - thm, thd[idx(tt)]))                                    # sam kat
    fh = F.simulate(len(t), heave_rate=lambda tt: -v[idx(tt)])                                                    # samo nurzanie
    zero = dict(theta0=0.0, G0=np.zeros(N), w0=np.zeros(N), u0=np.zeros(N))
    w = t >= REL
    cl_u = col("AF_CL"); fx_u = col("AF_Fx") / span
    clw = F.forces(fw, zero)["CL"]; clm = F.forces(fm, zero)["CL"]
    # pelny (do Fx i sredniej): jak w replay_history
    ff = F.simulate(len(t), theta=lambda tt: (th[idx(tt)] - thm, thd[idx(tt)]), heave_rate=lambda tt: -v[idx(tt)], gust=gust)
    r0 = F.forces(ff); qc = 0.5 * rho * U * U * c
    g1 = np.linalg.solve(F.Abb, -U * np.ones(N)); dcl = rho * U * g1.sum() / qc
    th_ref = (cl_u[w].mean() - r0["CL"][w].mean()) / dcl
    mean, _ = mean_state(F, th_ref + thm); mean["G0"] = g1 * th_ref; mean["w0"] = F.Wvb @ mean["G0"]; mean["u0"] = F.Uvb @ mean["G0"]
    ff["th"] = ff["th"] - thm
    rf = F.forces(ff, mean)
    clp = F.forces(fp, zero)["CL"]; clh = F.forces(fh, zero)["CL"]
    return dict(t=t, w=w, cl_u=cl_u, clw=clw, clm=clm, clp=clp, clh=clh, dt=dt, cl_full=rf["CL"], fx_u=fx_u, fx_m=rf["Fx"], eta_amp=a, dcl_drad=dcl, th_ref_deg=np.degrees(th_ref))


def stats(u, mdl, w):
    u1 = u[w] - u[w].mean(); m1 = mdl[w] - mdl[w].mean()
    return dict(amp_ratio=float(m1.std() / u1.std()), corr=float(np.corrcoef(u1, m1)[0, 1]), rms_err_over_std=float(np.sqrt(np.mean((u1 - m1) ** 2)) / u1.std()))


D = {r: components(r) for r in ("OVS_PID_BASE2", "OVS_PID_PRBS1", "OVS_PID_SINE_A2")}
b = D["OVS_PID_BASE2"]; w = b["w"]
y = b["cl_u"][w] - b["cl_u"][w].mean()
xw = b["clw"][w] - b["clw"][w].mean(); xm = b["clm"][w] - b["clm"][w].mean()
kA = float(np.dot(xw + xm, y) / np.dot(xw + xm, xw + xm))
X = np.c_[xw, xm]; kB = np.linalg.lstsq(X, y, rcond=None)[0]
def feats(d, deriv):
    cols = [d["clw"], d["clp"], d["clh"]]
    if deriv:
        cols += [np.gradient(x, d["dt"]) for x in cols]
    return np.c_[tuple(cols)]
Xc = feats(b, False)[w]; Xc = Xc - Xc.mean(0); kC = np.linalg.lstsq(Xc, y, rcond=None)[0]
Xd = feats(b, True)[w]; Xd = Xd - Xd.mean(0); kD = np.linalg.lstsq(Xd, y, rcond=None)[0]
# E/F: dopasowanie na BASE2 + PRBS1 (PRBS ma szerokie pasmo -> czlony fala/kat/nurzanie sa rozroznialne), sprawdzenie na SINE
p_ = D["OVS_PID_PRBS1"]; wp = p_["w"]; yp = p_["cl_u"][wp] - p_["cl_u"][wp].mean()
def stackfit(deriv):
    Xa = feats(b, deriv)[w]; Xa = Xa - Xa.mean(0); Xb = feats(p_, deriv)[wp]; Xb = Xb - Xb.mean(0)
    X_ = np.r_[Xa, Xb]; y_ = np.r_[y, yp]
    sv = np.linalg.svd(X_ / X_.std(0), compute_uv=False)
    return np.linalg.lstsq(X_, y_, rcond=None)[0], float(sv[0] / sv[-1])
kE, condE = stackfit(False); kF, condF = stackfit(True)
condC = float(np.linalg.cond(Xc / Xc.std(0))); condD = float(np.linalg.cond(Xd / Xd.std(0)))
res = {"fit_on": "OVS_PID_BASE2 (t >= %.4f s)" % REL,
       "E_three_scales_fit_BASE2+PRBS1": dict(zip(("k_wave", "k_pitch", "k_heave"), map(float, kE)), cond=condE),
       "F_gain_plus_rate_fit_BASE2+PRBS1": dict(zip(("k_wave", "k_pitch", "k_heave", "tau_wave_s", "tau_pitch_s", "tau_heave_s"), map(float, kF)), cond=condF),
       "cond_C_BASE2": condC, "cond_D_BASE2": condD, "A_single_scale": {"k_osc": kA}, "B_two_scales": {"k_wave": float(kB[0]), "k_motion": float(kB[1])},
       "C_three_scales": dict(zip(("k_wave", "k_pitch", "k_heave"), map(float, kC))),
       "D_three_gain_plus_rate": dict(zip(("k_wave", "k_pitch", "k_heave", "tau_wave_s", "tau_pitch_s", "tau_heave_s"), map(float, kD))), "runs": {}}
for r, d in D.items():
    ww = d["w"]
    cl_raw = d["clw"] + d["clm"]
    res["runs"][r] = {"used_for_fit": r == "OVS_PID_BASE2", "eta_amp_m": d["eta_amp"],
                      "raw": stats(d["cl_u"], cl_raw, ww), "A": stats(d["cl_u"], kA * cl_raw, ww),
                      "B": stats(d["cl_u"], kB[0] * d["clw"] + kB[1] * d["clm"], ww),
                      "C": stats(d["cl_u"], feats(d, False) @ kC, ww), "D": stats(d["cl_u"], feats(d, True) @ kD, ww), "E": stats(d["cl_u"], feats(d, False) @ kE, ww), "F": stats(d["cl_u"], feats(d, True) @ kF, ww), "Fx_unscaled": stats(d["fx_u"], d["fx_m"], ww),
                      "check_full_vs_sum_corr": float(np.corrcoef(d["cl_full"][ww], cl_raw[ww])[0, 1])}
ok = lambda s: 0.9 <= s["amp_ratio"] <= 1.1 and s["corr"] >= 0.98
for v_ in ("A", "B", "C", "D", "E", "F"):
    res[v_ + "_PASS_on_validation"] = all(ok(res["runs"][r][v_]) for r in ("OVS_PID_PRBS1", "OVS_PID_SINE_A2"))
Path(__file__).with_name("CALIB_CL.json").write_text(json.dumps(res, indent=1)); print(json.dumps(res, indent=1))
try:
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
    for a_, (r, d) in zip(ax, D.items()):
        ww = d["w"]; mu = d["cl_u"][ww].mean()
        a_.plot(d["t"], d["cl_u"], "k", lw=1, label="URANS")
        a_.plot(d["t"], mu + d["clw"] + d["clm"] - (d["clw"] + d["clm"])[ww].mean(), "C3:", lw=1, label="model surowy")
        a_.plot(d["t"], mu + kB[0] * d["clw"] + kB[1] * d["clm"] - (kB[0] * d["clw"] + kB[1] * d["clm"])[ww].mean(), "C2--", lw=1.2, label="model skalibrowany (B)")
        a_.set_xlim(REL, d["t"][-1]); a_.set_ylabel("CL"); a_.set_title(r + (" (dopasowanie)" if r == "OVS_PID_BASE2" else " (sprawdzenie)"), fontsize=9); a_.grid(alpha=0.3); a_.legend(fontsize=8, ncol=3)
    ax[-1].set_xlabel("t [s]"); fig.tight_layout(); fig.savefig(Path(__file__).with_name("CALIB_CL.png"), dpi=110)
except Exception as e:
    print("plot:", e)

