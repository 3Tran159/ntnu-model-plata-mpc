"""validate_urans.py - walidacja modelu Faltinsena na istniejacych przebiegach URANS (tylko odczyt history.csv), bez dopasowania.
Dla kazdego przebiegu:
  (1) PETLA ZAMKNIETA w modelu: ten sam regulator co w URANS (PID z run.properties albo siec TD3), ta sama masa, serwo, takt 10 ms,
      zwolnienie nurzania po 1,9368 s; fala: amplituda i faza 1. harmonicznej wzniesienia nad krawedzia natarcia z URANS.
  (2) ODTWORZENIE RUCHU: ruch plata z URANS (kat, nurzanie) zadany w modelu -> porownanie sily nosnej i oporu przy tym samym ruchu.
Srednie z ostatnich 4 okresow spotkania. Wynik: VALIDATION.json (zapis po kazdym przypadku; ponowne uruchomienie pomija gotowe), log: validate.log.
Uzycie: python validate_urans.py [--force]"""
import csv, json, sys, time
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
from faltinsen_plant import FaltinsenPlant, U, SPAN, DEPTH, CL_REF, SLOPE_URANS_CALM

OVR = HERE.parents[1] / "30_URANS_STAR" / "overset_runs"
RUNS = ["OVS_PID1_GODO", "OVS_PID2_GODO", "OVS_PID3_GODO", "OVS_POL_TD3_GODO"]
VARIANTS = {"A_2pi_bez_u": dict(slope=1.0, wave_u=False), "B_2pi_z_u": dict(slope=1.0, wave_u=True),
            "C_nachylenie_090_z_u": dict(slope=SLOPE_URANS_CALM, wave_u=True),
            "D_2pi_z_u_biegunowa_DOPASOWANA_v2": dict(slope=1.0, wave_u=True, k_pol=0.0716),
            "E_2pi_z_u_staly_dodatek_w_fali": dict(slope=1.0, wave_u=True, cd_wave=0.0016),            # E: dCD = 0,0016 z BASE2/PRBS1/SINE_A2 (fit_polar.py)
            "F_2pi_z_u_dodatek_i_biegunowa": dict(slope=1.0, wave_u=True, cd_wave=0.0013, k_pol=0.0109)}  # F: jak E, postac C+K   # D: tylko odniesienie, K_POL z dopasowania v2 - NIE jest bez dopasowania
T_REL, P_CALM = 1.9368, 61.1          # zwolnienie nurzania [s]; moc oporu w wodzie spokojnej w URANS [W na pasek]
OUT, LOG = HERE / "VALIDATION.json", HERE / "validate.log"


def log(s):
    print(s, flush=True)
    with open(LOG, "a", encoding="utf-8") as f: f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + s + "\n")


def load(run):
    rows = list(csv.DictReader(open(OVR / run / "history.csv")))
    R = {}
    for r in rows:
        try: R[round(float(r["time_s"]), 6)] = r
        except Exception: pass
    t = np.array(sorted(R)); c = lambda k: np.array([float(R[x][k]) for x in t])
    props = dict(l.strip().split("=", 1) for l in open(OVR / run / "run.properties") if "=" in l)
    return dict(t=t, th=c("theta_deg"), thd=c("theta_rate_deg_s"), z=c("z_m"), v=c("v_m_s"), CL=c("AF_CL"), Fx=c("AF_Fx") / SPAN, P=c("P_drag_W"),
                eta=c("GODO_eta_at_LE"), props=props)


def wave_fit(d, ome, Te):
    m = d["t"] > 0.3; n = int(((d["t"][m][-1] - d["t"][m][0]) // Te) * round(Te / 1e-3))
    e = d["eta"][m][:n]; tt = d["t"][m][:n]; zc = 2 * np.mean((e - e.mean()) * np.exp(-1j * ome * tt))
    return float(abs(zc)), float(-np.angle(zc)), float(e.mean())


def load_policy():
    js = json.loads((HERE / "policy_TD3_GODO.json").read_text()); Ls = [(np.array(l["W"]), np.array(l["b"])) for l in js["layers"]]; sc = np.array(js["obs_scale"])
    def act(o):
        x = np.clip(np.asarray(o) / sc, -5, 5); h = np.maximum(0, Ls[0][0] @ x + Ls[0][1]); h = np.maximum(0, Ls[1][0] @ h + Ls[1][1])
        return float(np.tanh(Ls[2][0] @ h + Ls[2][1])[0])
    return act


def window(t, t_last, Te, nper=4):
    return (t > t_last - nper * Te) & (t <= t_last)


def stats(t, z, th, P, CL, w):
    return dict(P_drag_W=float(P[w].mean()), dP_vs_calm_pct=float(100 * (P[w].mean() / P_CALM - 1)), z_min_m=float(z[w].min()), z_max_m=float(z[w].max()),
                z_p2p_m=float(z[w].max() - z[w].min()), z_mean_m=float(z[w].mean()), theta_mean_deg=float(th[w].mean()), theta_p2p_deg=float(th[w].max() - th[w].min()),
                CL_mean=float(CL[w].mean()), CL_p2p=float(CL[w].max() - CL[w].min()), CL_max=float(CL[w].max()))


def closed_loop(run, d, kw):
    P = FaltinsenPlant(**kw); a, beta, eta_mean = wave_fit(d, P.ome, P.Te)
    P = FaltinsenPlant(wave_amp=a, wave_phase=beta, **kw); P.reset(theta_deg=0.0)
    pr = d["props"]; mode = pr["mode"]; trim = float(pr["pitch_trim_deg"]); kp, ki = float(pr["kp_deg_per_m"]), float(pr["ki_deg_per_m_s"])
    pol = load_policy() if mode == "policy" else None
    tend = min(11.6208, float(d["t"][-1])); ie = 0.0; cmd = trim; eta_prev = None; rows = []
    for i in range(int(round(tend / P.dt))):
        free = P.t >= T_REL - 0.5 * P.dt
        if i % P.tick == 0:
            eta = P.eta_LE(); eta_prev = eta if eta_prev is None else eta_prev
            w_s = (P.om0 / P.ome) * (eta - eta_prev) / (P.tick * P.dt); eta_prev = eta
            if mode == "policy" and free:
                cmd = 7.5 * pol([P.z, P.v, eta, w_s, cmd / 7.5])
            else:
                cmd = trim
                if free: ie = float(np.clip(ie + (-P.z) * P.tick * P.dt, -1, 1)); cmd = trim + kp * (-P.z) + ki * ie
            cmd = float(np.clip(cmd, -7.5, 7.5)); P.cmd = np.radians(cmd)
        rows.append(P.step(free_heave=free))
    g = lambda k: np.array([r[k] for r in rows]); t = g("t")
    t_last = min(d["t"][-1], t[-1]); wm = window(t, t_last, P.Te); wu = window(d["t"], t_last, P.Te)
    M = stats(t, g("z"), g("theta_deg"), g("P_drag_W_strip"), g("CL"), wm); Us = stats(d["t"], d["z"], d["th"], d["P"], d["CL"], wu)
    M["P_pot_W"] = float(U * SPAN * g("Fx_pot")[wm].mean()); M["P_wave_W"] = float(U * SPAN * g("Fx_wave")[wm].mean()); M["sub_min_m"] = float(g("sub")[wm].min())
    zi = np.interp(d["t"][wu], t, g("z"))
    return dict(wave_amp_m=a, eta_mean_URANS_m=eta_mean, URANS=Us, model=M, err_P_pct=float(100 * (M["P_drag_W"] / Us["P_drag_W"] - 1)),
                err_z_p2p_pct=float(100 * (M["z_p2p_m"] / Us["z_p2p_m"] - 1)), rms_z_diff_m=float(np.sqrt(np.mean((zi - d["z"][wu]) ** 2))),
                diff_dP_points=float(M["dP_vs_calm_pct"] - Us["dP_vs_calm_pct"]))


def replay(run, d, kw):
    P = FaltinsenPlant(**kw); a, beta, _ = wave_fit(d, P.ome, P.Te)
    P = FaltinsenPlant(wave_amp=a, wave_phase=beta, **kw); P.reset(theta_deg=d["th"][0], z=d["z"][0], v=d["v"][0], t=d["t"][0] - P.dt)
    CL = np.zeros(len(d["t"])); Fx = np.zeros(len(d["t"]))
    for i in range(len(d["t"])):
        # zadany ruch: wymuszamy stan serwa i nurzania na wartosci z URANS, sily liczy model
        P.th = np.radians(d["th"][i]); P.cmd = P.th; P.w_servo = np.radians(d["thd"][i]); P.v = d["v"][i]; P.z = d["z"][i]
        r = kin_step(P); CL[i] = r["CL"]; Fx[i] = r["Fx"]
    w = window(d["t"], d["t"][-1], P.Te)
    def harm(x): return 2 * np.mean((x[w] - x[w].mean()) * np.exp(-1j * P.ome * d["t"][w]))
    hm, hu = harm(CL), harm(d["CL"])
    return dict(P_model_W=float(U * SPAN * Fx[w].mean()), P_URANS_W=float(U * SPAN * d["Fx"][w].mean()), err_P_pct=float(100 * (Fx[w].mean() / d["Fx"][w].mean() - 1)),
                CL_mean_model=float(CL[w].mean()), CL_mean_URANS=float(d["CL"][w].mean()), CL_std_model=float(CL[w].std()), CL_std_URANS=float(d["CL"][w].std()),
                CL_std_ratio_URANS_over_model=float(d["CL"][w].std() / CL[w].std()), CL_h1_ratio_URANS_over_model=float(abs(hu) / abs(hm)),
                CL_h1_phase_URANS_minus_model_deg=float(np.degrees(np.angle(hu / hm))), corr=float(np.corrcoef(CL[w], d["CL"][w])[0, 1]))


def kin_step(P):
    """krok modelu z zadanym ruchem: jak FaltinsenPlant.step, ale bez serwa i bez rownania nurzania"""
    import faltinsen_plant as FP, faltinsen_eqs as FE
    t_new = P.t + P.dt; F = P.F; ug, wg = P.gust(F.xv, t_new); _, wc = P.gust(F.xc, t_new)
    uc = P.gust(F.xc, t_new)[0] if P.wave_u else None
    r = P.S.step(P.th - P.th_ref, P.w_servo, -P.v, gust_c=wc, gust_v=(ug, wg), u_c=uc, u_v=ug if P.wave_u else None); CL = CL_REF + r["L_lin"] / P.q; h = P.submergence(t_new)
    if P.fs_lift: CL *= float(FE.cl_ratio_high_fn(h, FP.C) / FE.cl_ratio_high_fn(DEPTH, FP.C))
    Fx = r["Fx"] + (P.cd0 + P.cd_wave + P.k_pol * (CL - CL_REF) ** 2) * P.q
    if P.fs_wave: Fx += float(FE.wave_resistance(FE.gamma_from_cl(CL, U, FP.C), h, U) - FE.wave_resistance(FE.gamma_from_cl(CL_REF, U, FP.C), DEPTH, U))
    P.t = t_new; P.n += 1
    return dict(CL=CL, Fx=Fx)


if __name__ == "__main__":
    out = json.loads(OUT.read_text()) if OUT.exists() and "--force" not in sys.argv else {}
    for run in RUNS:
        d = None
        for vn, kw in VARIANTS.items():
            for kind, fn in (("petla_zamknieta", closed_loop), ("odtworzenie_ruchu", replay)):
                key = f"{run}|{vn}|{kind}"
                if key in out: continue
                d = d or load(run); t0 = time.time(); out[key] = fn(run, d, kw)
                OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
                r = out[key]
                if kind == "petla_zamknieta":
                    log(f"{key}: moc oporu URANS {r['URANS']['P_drag_W']:.1f} W, model {r['model']['P_drag_W']:.1f} W ({r['err_P_pct']:+.1f} %); z p2p URANS {r['URANS']['z_p2p_m']:.3f} m, model {r['model']['z_p2p_m']:.3f} m ({r['err_z_p2p_pct']:+.1f} %); CLmax model {r['model']['CL_max']:.2f}; {time.time()-t0:.0f} s")
                else:
                    log(f"{key}: moc oporu URANS {r['P_URANS_W']:.1f} W, model {r['P_model_W']:.1f} W ({r['err_P_pct']:+.1f} %); CL 1.harm URANS/model {r['CL_h1_ratio_URANS_over_model']:.3f}, faza {r['CL_h1_phase_URANS_minus_model_deg']:+.1f} deg; {time.time()-t0:.0f} s")
    log("gotowe")
