"""test_suspension.py - testy modelu dwumasowego. Wynik: TEST_SUSPENSION.json
 T1 polaczenie sztywne (rigid=True), obciazenie 100 %: identyczne z FaltinsenPlant (model B) w petli PID2 na fali - roznica ma byc 0.
 T2 bardzo twarda sprezyna (k = 5e6 N/m/m, tlumienie krytyczne): zbieznosc do sztywnego.
 T3 woda spokojna: 100 % i 90 %, z powierzchnia swobodna i bez (odniesienie dla procentow).
 T4 fala nieregularna: Hs z widma, przebieg 20 s bez bledu; 90 %, sztywno.
 T5 przyklad miekkiego zawieszenia (tylko czy dziala i czy bilans sil sie zgadza), 90 %."""
import json, sys, time
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
from faltinsen_plant import FaltinsenPlant, MASS, G, BUOY, C, U, SPAN, TH_REF_DEG
from suspension_plant import TwoMassPlant, Suspension, calm_reference
T_REL = 1.9368


def loop(P, kp=6.63, ki=1.18, nper=8, ctrl="foil"):
    th0 = float(np.degrees(P.th_ref)); P.reset(theta_deg=th0); ie = 0.0; rows = []
    for i in range(int(round((T_REL + nper * P.Te) / P.dt))):
        free = P.t >= T_REL - 0.5 * P.dt
        if i % P.tick == 0:
            zc = P.z if ctrl == "foil" else P.z_h; cmd = th0
            if free: ie = float(np.clip(ie + (-zc) * P.tick * P.dt, -1, 1)); cmd = th0 + kp * (-zc) + ki * ie
            P.cmd = np.radians(np.clip(cmd, -7.5, 7.5))
        rows.append(dict(P.step(free_heave=free)))
    return rows


def summ(P, rows, n=4):
    t = np.array([r["t"] for r in rows]); w = t > t[-1] - n * P.Te; g = lambda k: np.array([r[k] for r in rows])[w]
    o = dict(P_drag_W_strip=float(g("P_drag_W_strip").mean()), z_foil_p2p_m=float(np.ptp(g("z"))), CL_mean=float(g("CL").mean()), sub_min_m=float(P.sub_min), sub_min_chords=float(P.sub_min / C), t_below_1c_s=float(P.t_below_1c))
    if "z_hull" in rows[0]: o.update(z_hull_p2p_m=float(np.ptp(g("z_hull"))), a_hull_rms_m_s2=float(g("a_hull").std()), a_hull_max_m_s2=float(np.abs(g("a_hull")).max()), x_min_m=float(g("x").min()), x_max_m=float(g("x").max()))
    return o


out = {}; t0 = time.time()
# T1
A = loop(FaltinsenPlant()); B = loop(TwoMassPlant(rigid=True, load=1.0))
out["T1_sztywne_vs_model_B"] = {k: float(max(abs(a[k] - b[k]) for a, b in zip(A, B))) for k in ("z", "v", "CL", "Fx", "theta_deg")}
print("T1 max |roznica|:", out["T1_sztywne_vs_model_B"], flush=True)
# T2
m = MASS; el = Suspension(k=5e6, c=2 * np.sqrt(5e6 * 40.0)); Pk = TwoMassPlant(element=el, load=1.0); Ck = loop(Pk)
out["T2_twarda_sprezyna"] = dict(max_dz_foil_m=float(max(abs(a["z"] - b["z"]) for a, b in zip(A, Ck))), max_x_m=float(max(abs(b["x"]) for b in Ck)),
                                 P_B_W=summ(FaltinsenPlant(), A)["P_drag_W_strip"] if False else float(np.mean([r["P_drag_W_strip"] for r in A[-int(4 * Pk.Te / Pk.dt):]])),
                                 P_twarda_W=float(np.mean([r["P_drag_W_strip"] for r in Ck[-int(4 * Pk.Te / Pk.dt):]])))
print("T2:", out["T2_twarda_sprezyna"], flush=True)
# T3
out["T3_woda_spokojna"] = [calm_reference(load=l, free_surface=fs) for l in (1.0, 0.9) for fs in (True, False)]
for r in out["T3_woda_spokojna"]: print("T3:", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()}, flush=True)
# T3b fala regularna, sztywno, PID2: 100 % i 90 %, z FS i bez
out["T3b_fala_regularna_PID2_sztywno"] = {}
for l in (1.0, 0.9):
    for fs in (True, False):
        P = TwoMassPlant(rigid=True, load=l, free_surface=fs); s = summ(P, loop(P)); out["T3b_fala_regularna_PID2_sztywno"][f"load{l}_fs{fs}"] = s; print("T3b", l, fs, {k: round(v, 3) for k, v in s.items()}, flush=True)
# T4
P = TwoMassPlant(rigid=True, load=0.9); P.set_irregular(Hs=1.5, Tp=5.0, seed=1); th0 = float(np.degrees(P.th_ref)); P.reset(theta_deg=th0); ie = 0.0; eta = []; zz = []
for i in range(20000):
    if i % P.tick == 0 and P.t > 1.0: ie = float(np.clip(ie + (-P.z) * 0.01, -1, 1)); P.cmd = np.radians(np.clip(th0 + 6.63 * (-P.z) + 1.18 * ie, -7.5, 7.5))
    r = P.step(free_heave=P.t > 1.0); eta.append(r["eta_LE"]); zz.append(r["z"])
out["T4_fala_nieregularna"] = dict(Hs_zadane_m=1.5, Hs_z_widma_m=float(P.irr["Hs_check"]), Hs_z_przebiegu_20s_m=float(4 * np.std(eta)), z_p2p_m=float(np.ptp(zz)), sub_min_m=float(P.sub_min), eta_ahead_5m=float(P.eta_ahead(5.0)), finite=bool(np.isfinite(zz).all()))
print("T4:", out["T4_fala_nieregularna"], flush=True)
# T5
el = Suspension(k=2.0e4, c_comp=3.0e3, c_reb=6.0e3, x_up=0.25, x_dn=0.25); P = TwoMassPlant(element=el, load=0.9); rows = loop(P, ctrl="hull"); s = summ(P, rows)
Pr = TwoMassPlant(rigid=True, load=0.9); sr = summ(Pr, loop(Pr))
t = np.array([r["t"] for r in rows]); w = t > t[-1] - 4 * P.Te
bal = float(np.mean([r["L"] for r in rows if r["t"] > t[-1] - 4 * P.Te]) + BUOY - (P.m_f + P.m_h) * G)
out["T5_przyklad_miekkie"] = dict(element="k = 20 kN/m/m, c sciskanie 3 / odbicie 6 kN s/m/m, odboje +-0,25 m, PID2 na polozeniu kadluba", miekkie=s, sztywne_90=sr, masy=dict(m_f=P.m_f, m_h=P.m_h),
                                  bilans_sredniej_sily_N_m=bal, F_link_mean_N_m=float(np.mean([r["F_link"] for r in rows if r["t"] > t[-1] - 4 * P.Te])), ciezar_kadluba_N_m=P.m_h * G)
print("T5 miekkie:", {k: round(v, 3) for k, v in s.items()}); print("T5 sztywne:", {k: round(v, 3) for k, v in sr.items()}); print("bilans", bal, out["T5_przyklad_miekkie"]["F_link_mean_N_m"], P.m_h * G)
(HERE / "TEST_SUSPENSION.json").write_text(json.dumps(out, indent=1)); print("gotowe", round(time.time() - t0), "s")
