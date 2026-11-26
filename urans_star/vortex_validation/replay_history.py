"""replay_history.py - walidacja modelu wirowego na DOWOLNYM przebiegu overset (PID, policy, hold...):
bierze z history.csv zmierzony kat theta(t), predkosc nurzania v(t) i fale (dopasowana z GODO_eta_at_LE),
puszcza je przez model wirowy i porownuje CL(t), Fx(t), M(t) z URANS. Nie wymaga zadnych dodatkowych obliczen CFD.
usage: python replay_history.py <history.csv> [t_start=1.0] [out_prefix]"""
import sys, json
from pathlib import Path
import numpy as np, csv
sys.path.insert(0, str(Path(__file__).resolve().parent / "model"))
from uvm2d import Foil, G

def replay(hist, t0=1.0, rho=1000.0, c=0.312, U=12.3466667, depth=1.09, span=0.02, T=5.0, N=20):
    rows = list(csv.DictReader(open(hist)))
    col = lambda k: np.array([float(r[k]) for r in rows])
    t = col("time_s"); th = np.radians(col("theta_deg")); thd = np.radians(col("theta_rate_deg_s")); z = col("z_m"); v = col("v_m_s")
    eta = col("GODO_eta_at_LE"); dt = float(np.median(np.diff(t)))
    om = 2 * np.pi / T; k = om * om / G; ome = om + k * U; Te = 2 * np.pi / ome
    m = t > 0.3
    zc = 2 * np.mean((eta[m][: int(len(eta[m]) // round(Te / dt) * round(Te / dt))] - eta[m].mean()) * np.exp(-1j * ome * t[m][: int(len(eta[m]) // round(Te / dt) * round(Te / dt))])) if (t[m][-1] - t[m][0]) >= Te else None
    if zc is None:
        raise SystemExit("za krotki przebieg (< 1 okres)")
    a, beta = abs(zc), -np.angle(zc)                      # eta_LE(t) = a cos(ome t - beta)
    F = Foil(c=c, U=U, N=N, h=depth, dt=dt, wake_len=3 * U * Te, rho=rho)
    idx = lambda tt: min(len(t) - 1, max(0, int(round(tt / dt)) - 1))
    A0 = a * om
    def gust(x, tt):
        psi = k * x - ome * tt + beta; A = A0 * np.exp(-k * (depth - z[idx(tt)]))
        return A * np.cos(psi), A * np.sin(psi)
    f = F.simulate(len(t), theta=lambda tt: (th[idx(tt)] - th.mean(), thd[idx(tt)]), heave_rate=lambda tt: -v[idx(tt)], gust=gust)
    # staly kat odniesienia (kat zerowej sily nosnej nieznany): dopasowany tak, by srednie CL sie zgadzalo
    w = t >= t0
    cl_u = col("AF_CL"); fx_u = col("AF_Fx") / span; M_u = col("GODO_M_pivot") / span
    r0 = F.forces(f); qc = 0.5 * rho * U * U * c
    g1 = np.linalg.solve(F.Abb, -U * np.ones(N)); dcl = rho * U * g1.sum() / qc         # dCL/dtheta ze swobodna powierzchnia
    th_ref = (cl_u[w].mean() - r0["CL"][w].mean()) / dcl
    mean = dict(theta0=th_ref + th.mean(), G0=g1 * th_ref, w0=F.Wvb @ (g1 * th_ref), u0=F.Uvb @ (g1 * th_ref))
    f["th"] = f["th"] - th.mean()   # nachylenie do rzutu sily: (theta0 + th') = th_ref + theta(t)
    r = F.forces(f, mean)
    def cmp(u, mdl):
        u1, m1 = u[w] - u[w].mean(), mdl[w] - mdl[w].mean()
        return dict(urans_mean=float(u[w].mean()), model_mean=float(mdl[w].mean()), urans_std=float(u1.std()), model_std=float(m1.std()),
                    amp_ratio_model_over_urans=float(m1.std() / u1.std()), corr=float(np.corrcoef(u1, m1)[0, 1]), rms_err_over_std=float(np.sqrt(np.mean((u1 - m1) ** 2)) / u1.std()))
    sgn = np.sign(np.corrcoef(M_u[w], r["Mp"][w])[0, 1])
    out = dict(history=str(hist), window_s=[float(t0), float(t[-1])], eta_amp_m=float(a), theta_ref_fit_deg=float(np.degrees(th_ref)), rho=rho,
               CL=cmp(cl_u, r["CL"]), Fx_N_per_m=cmp(fx_u, r["Fx"]), M_pivot_Nm_per_m=cmp(sgn * M_u, r["Mp"]),
               implied_viscous_drag_N_per_m=float(fx_u[w].mean() - r["Fx"][w].mean()), implied_CD=float((fx_u[w].mean() - r["Fx"][w].mean()) / qc))
    return out, dict(t=t, cl_u=cl_u, cl_m=r["CL"], fx_u=fx_u, fx_m=r["Fx"], th=np.degrees(th), v=v, z=z, eta=eta, w=w)

if __name__ == "__main__":
    hist = sys.argv[1]; t0 = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
    pre = sys.argv[3] if len(sys.argv) > 3 else str(Path(hist).with_name("VORTEX_REPLAY"))
    out, s = replay(hist, t0)
    Path(pre + ".json").write_text(json.dumps(out, indent=1)); print(json.dumps(out, indent=1))
    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        fig, ax = plt.subplots(3, 1, figsize=(10, 8.5), sharex=True)
        ax[0].plot(s["t"], s["th"], label="kat plata theta [deg]"); ax[0].plot(s["t"], 10 * s["z"], label="nurzanie z x10 [m]"); ax[0].plot(s["t"], 5 * s["eta"], "k:", label="fala eta x5 [m]"); ax[0].legend(ncol=3, fontsize=8); ax[0].set_ylabel("wejscia")
        ax[1].plot(s["t"], s["cl_u"], "k", label="URANS"); ax[1].plot(s["t"], s["cl_m"], "C3--", label="model wirowy"); ax[1].set_ylabel("CL"); ax[1].legend(fontsize=8)
        off = out["implied_viscous_drag_N_per_m"]
        ax[2].plot(s["t"], s["fx_u"], "k", label="URANS"); ax[2].plot(s["t"], s["fx_m"] + off, "C3--", label="model wirowy + staly opor lepki %.0f N/m" % off); ax[2].set_ylabel("Fx [N/m]"); ax[2].set_xlabel("czas [s]"); ax[2].legend(fontsize=8)
        ax[2].set_ylim(np.percentile(s["fx_u"][s["w"]], 0.5) - 300, np.percentile(s["fx_u"][s["w"]], 99.5) + 300)
        for a_ in ax: a_.axvline(t0, color="0.7", lw=0.8); a_.grid(alpha=0.3)
        fig.tight_layout(); fig.savefig(pre + ".png", dpi=110)
    except Exception as e:
        print("bez wykresu:", e)
