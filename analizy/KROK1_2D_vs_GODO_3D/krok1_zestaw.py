r"""krok1_zestaw.py - zestawienie Kroku 1: Godø 3D (artykul) vs model wirowy 2D (wyniki\*.json) vs URANS 2D (history.csv, tylko odczyt).
Wynik: KROK1_WYNIKI.json + KROK1_porownanie.png.  Niczego nie uruchamia w STAR-CCM+.
"""
import json, csv, math
from pathlib import Path
import numpy as np

HERE = Path(__file__).parent; W = HERE / "wyniki"
OVS = Path(r"T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR\overset_runs")
U, C, SPAN, RHO, AR = 12.3466667, 0.312, 0.02, 1000.0, 25.6
B = AR * C                                  # rozpietosc Godø [m] = wydluzenie x srednia cieciwa (tab. 1) = 7,987 m
TE = 1.9368
QS = 0.5 * RHO * U * U * C * SPAN           # N na pasek przy CL lub CD = 1
TO_FULL = B / SPAN / U                      # W/pasek -> N na caly plat

# --- Godø 2024 (Ocean Eng. 312, 119236) ---
GODO = dict(
    D_cw_N=3301.0,       # odczyt z rys. 7 (s. 12): srednie -Fx agenta "komfort" = -3268 N, a jego opor = 0,99 x woda spokojna (s. 12)
    gain_pct=dict(PID1=11.2, PID2=2.45, PID3=-18.0, I=15.0, TD3=61.8),      # "power gain", tab. 5 (s. 13) i tab. 4 (s. 13); z moca aktuatora
    drag_red_pct=dict(TD3=63.9),                                             # s. 11
    acc_rms=dict(PID1=1.8, PID2=2.0, PID3=1.4, I=1.8, TD3=4.6),              # tab. 5 i 4 (s. 13) [m/s2]
)


def agg(variant, name):
    fs = sorted(W.glob(f"{variant}__{name}__ph*.json"))
    if not fs:
        return None
    Rall = [json.loads(f.read_text()) for f in fs]
    R = [r for r in Rall if not r.get("term", False)]
    n_all = len(Rall)
    m = lambda k: float(np.mean([r[k] for r in R]))
    return dict(n=len(R), n_all=n_all, P_W=m("P_drag_W_strip"), P_ind_W=m("P_ind_W_strip"), acc=m("acc_rms_m_s2"), z_min=min(r["z_min_m"] for r in R), z_max=max(r["z_max_m"] for r in R),
                z_mean=m("z_mean_m"), z_amp=m("z_amp1_m"), z_lag=m("z_lag_deg"), th_min=min(r["theta_min_deg"] for r in R), th_max=max(r["theta_max_deg"] for r in R),
                CL_mean=m("CL_mean"), CL_amp=m("CL_amp1"), CL_lag=m("CL_lag_deg"), CL_min=min(r["CL_min"] for r in R), CL_max=max(r["CL_max"] for r in R),
                sub_min_c=min(r["sub_min_c"] for r in R), sat=m("sat_frac") if "sat_frac" in R[0] else None, kappa=R[0].get("kappa"),
                a0=R[0].get("a0_eff_per_rad"), dcl=R[0].get("dcl_model_per_rad"), term=(len(R) < n_all),
                z_absmax_all=max(r["z_absmax_all_m"] for r in R), sub_min_all_c=min(r["sub_min_all_c"] for r in R))


out = dict(godo=GODO, stale=dict(U_m_s=U, c_m=C, pasek_m=SPAN, rho=RHO, AR=AR, rozpietosc_m=B, Te_s=TE), model_wirowy={}, urans={})
VAR = ["V0_2D", "V1_ind", "V2_ind_kappa", "V3_ind_kappa_trimlim"]
for v in VAR:
    calm = agg(v, "CALM_PID2"); o = dict(calm=calm)
    for n in ("PID1", "PID2", "PID3", "I", "TD3_GODO", "RIGID"):
        a = agg(v, n)
        if a:
            a["pct_vs_calm"] = 100 * (a["P_W"] / calm["P_W"] - 1); a["dD_full_N"] = (a["P_W"] - calm["P_W"]) * TO_FULL; o[n] = a
    o["D_cw_full_N"] = calm["P_W"] * TO_FULL
    out["model_wirowy"][v] = o

# --- URANS 2D (overset, pasek 0,02 m): ostatnie 3 okresy spotkania, jak w URANS_PID_SUMMARY.json ---
def hist(run):
    f = OVS / run / "history.csv"
    if not f.exists():
        return None
    R = list(csv.DictReader(open(f)))
    c = lambda k: np.array([float(r[k]) for r in R])
    return dict(t=c("time_s"), P=c("P_drag_W"), CL=c("AF_CL"), z=c("z_m"), v=c("v_m_s"), th=c("theta_deg"), Pa=c("P_act_W"), low=c("GODO_lift_over_weight"))

hc = hist("OVS_CALM_PID2"); mc = hc["t"] >= hc["t"][-1] - 1.0
P_cw, CL_cw = float(hc["P"][mc].mean()), float(hc["CL"][mc].mean())
Pi_cw = U * QS * float(np.mean(hc["CL"][mc] ** 2)) / (math.pi * AR)
out["urans"]["CALM_PID2"] = dict(P_W=P_cw, CL_mean=CL_cw, P_ind_W=Pi_cw, t_end=float(hc["t"][-1]), lift_over_weight=float(hc["low"][mc].mean()), theta_deg=float(hc["th"][mc].mean()),
                                 D_full_N=P_cw * TO_FULL, D_full_3D_N=(P_cw + Pi_cw) * TO_FULL)
for key, run in (("PID1", "OVS_PID1_GODO"), ("PID2", "OVS_PID2_GODO"), ("PID3", "OVS_PID3_GODO"), ("TD3_GODO", "OVS_POL_TD3_GODO")):
    h = hist(run)
    if h is None:
        continue
    m = h["t"] >= h["t"][-1] - 3 * TE
    P = float(h["P"][m].mean()); Pi = U * QS * float(np.mean(h["CL"][m] ** 2)) / (math.pi * AR)
    acc = np.gradient(h["v"][m], h["t"][m])
    out["urans"][key] = dict(run=run, t_end=float(h["t"][-1]), P_W=P, pct_vs_calm=100 * (P / P_cw - 1), P_ind_W=Pi, P_3D_W=P + Pi,
                             pct_vs_calm_3D=100 * ((P + Pi) / (P_cw + Pi_cw) - 1), dD_full_N=(P - P_cw) * TO_FULL, dD_full_3D_N=(P + Pi - P_cw - Pi_cw) * TO_FULL,
                             CL_mean=float(h["CL"][m].mean()), CL_min=float(h["CL"][m].min()), CL_max=float(h["CL"][m].max()),
                             acc_rms=float(np.sqrt(np.mean((acc - acc.mean()) ** 2))), z_min=float(h["z"][m].min()), z_max=float(h["z"][m].max()),
                             th_min=float(h["th"][m].min()), th_max=float(h["th"][m].max()), P_act_W=float(h["Pa"][m].mean()),
                             P_act_pos_W=float(np.maximum(h["Pa"][m], 0).mean()))
(HERE / "KROK1_WYNIKI.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")

# --- wydruk ---
g = GODO; mw = out["model_wirowy"]; ur = out["urans"]
print(f"rozpietosc {B:.3f} m; Godø D_cw {g['D_cw_N']:.0f} N")
print("URANS calm:", {k: round(x, 4) for k, x in ur["CALM_PID2"].items()})
for v in VAR:
    o = mw[v]; print(f"\n{v}: D_cw {o['calm']['P_W']:.2f} W/pasek = {o['D_cw_full_N']:.0f} N caly plat; kappa {o['calm']['kappa']:.4f} a0 {o['calm']['a0']:.3f} dcl {o['calm']['dcl']:.3f} CL_calm {o['calm']['CL_mean']:.4f}")
    for n in ("PID1", "PID2", "PID3", "I", "TD3_GODO", "RIGID"):
        if n in o:
            a = o[n]
            print(f"  {n:9s} P {a['P_W']:7.2f} W ({a['pct_vs_calm']:+6.1f} %) dD {a['dD_full_N']:+7.0f} N | acc {a['acc']:.2f} | z {a['z_min']:+.2f}..{a['z_max']:+.2f} amp {a['z_amp']:.3f} lag {a['z_lag']:+.0f} | th {a['th_min']:+.2f}..{a['th_max']:+.2f} sat {a['sat']} | CL {a['CL_min']:.2f}..{a['CL_max']:.2f} amp {a['CL_amp']:.3f} lag {a['CL_lag']:+.0f} | zan.min {a['sub_min_c']:.2f}c term {a['term']}")
print()
for k in ("PID1", "PID2", "PID3", "TD3_GODO"):
    if k in ur:
        a = ur[k]
        print(f"URANS {k:9s} P {a['P_W']:.2f} W ({a['pct_vs_calm']:+.1f} %) +ind {a['P_3D_W']:.2f} ({a['pct_vs_calm_3D']:+.1f} %) dD {a['dD_full_N']:+.0f} / 3D {a['dD_full_3D_N']:+.0f} N | acc {a['acc_rms']:.2f} | z {a['z_min']:+.2f}..{a['z_max']:+.2f} | th {a['th_min']:+.2f}..{a['th_max']:+.2f} | CL {a['CL_min']:.2f}..{a['CL_max']:.2f} | Pact {a['P_act_W']:.2f}/{a['P_act_pos_W']:.2f} W t_end {a['t_end']}")


# --- wykres ---
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
lab = ["PID 1 (wolny)", "PID 2 (sredni)", "PID 3 (szybki)", "TD3 (siec)"]
keys = ["PID1", "PID2", "PID3", "TD3_GODO"]
gp = [-g["gain_pct"]["PID1"], -g["gain_pct"]["PID2"], -g["gain_pct"]["PID3"], -g["drag_red_pct"]["TD3"]]
v3 = lambda k: mw["V2_ind_kappa"][k] if k == "TD3_GODO" else mw["V3_ind_kappa_trimlim"][k]
ser = [("Godø 3D (NDLL, artykul)", gp, [x / 100 * g["D_cw_N"] for x in gp], "#222222"),
       ("model wirowy 2D", [mw["V0_2D"][k]["pct_vs_calm"] for k in keys], [mw["V0_2D"][k]["dD_full_N"] for k in keys], "#9ecae1"),
       ("model wirowy 2D + poprawka 3D", [v3(k)["pct_vs_calm"] for k in keys], [v3(k)["dD_full_N"] for k in keys], "#2171b5"),
       ("URANS 2D", [ur[k]["pct_vs_calm"] for k in keys], [ur[k]["dD_full_N"] for k in keys], "#fdae6b"),
       ("URANS 2D + opor indukowany", [ur[k]["pct_vs_calm_3D"] for k in keys], [ur[k]["dD_full_3D_N"] for k in keys], "#d94801")]
fig, ax = plt.subplots(1, 2, figsize=(13, 4.8)); x = np.arange(4); w = 0.16
for j, (name, pct, dn, col) in enumerate(ser):
    for a_, vals, fmt in ((ax[0], pct, "{:+.0f}"), (ax[1], dn, "{:+.0f}")):
        b = a_.bar(x + (j - 2) * w, vals, w, label=name, color=col)
        for xi, v in zip(x + (j - 2) * w, vals):
            a_.text(xi, v + (1 if v >= 0 else -1) * (0.02 * (a_ is ax[1]) * 2500 + 0.02 * (a_ is ax[0]) * 100), fmt.format(v), ha="center", va="bottom" if v >= 0 else "top", fontsize=7)
for a_, yl, tt in ((ax[0], "zmiana oporu plata wzgledem wody spokojnej [%]", "Wzglednie (kazdy model wzgledem WLASNEJ wody spokojnej)"),
                   (ax[1], "zmiana oporu calego plata 7,99 m [N]", "Bezwzglednie (pasek 0,02 m przeliczony na rozpietosc 7,99 m)")):
    a_.axhline(0, color="k", lw=0.8); a_.set_xticks(x); a_.set_xticklabels(lab); a_.set_ylabel(yl); a_.set_title(tt, fontsize=10); a_.grid(axis="y", alpha=0.3)
ax[0].legend(fontsize=8, loc="upper left")
fig.suptitle("Fala czolowa regularna H 1,5 m, T 5 s, 24 wezly. Ujemne = mniejszy opor niz w wodzie spokojnej", fontsize=10)
fig.tight_layout(); fig.savefig(HERE / "KROK1_porownanie.png", dpi=160)
print("wykres OK")
