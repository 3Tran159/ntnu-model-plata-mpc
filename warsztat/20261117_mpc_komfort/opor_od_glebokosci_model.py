# 23.11 (falsyfikacja): opor plata w WODZIE SPOKOJNEJ w modelu w funkcji glebokosci (z wzgledem nominalnej 1,09 m), przy sile nosnej = ciezar.
# Cel: odroznic zysk z fali od zysku z tego, ze MPC lata glebiej (odniesienie 57,03 W jest przy z = 0).
import json, math, sys, numpy as np, psutil
sys.argv = [sys.argv[0], "-", "0.4905", "0.2", "test"]
psutil.Process().cpu_affinity([0])
import mpc_learn_bridge as LB
MK = LB.MK if hasattr(LB, "MK") else __import__("mpc_komfort")
Z = MK.Z; FP = MK.FP
out = {}
for z0 in (0.0, -0.1, -0.2, -0.3, -0.4, -0.5):
    p = Z.FaltinsenPlant(wave_amp=1e-6, wave_phase=0.0, **Z.VB)
    cl_eq = (FP.MASS * MK.G - MK.BUOY) / p.q; trim = FP.TH_REF_DEG + float(np.degrees((cl_eq - FP.CL_REF) / (p.slope * p.dcl)))
    lo, hi = trim - 3.0, trim + 3.0
    for it in range(22):
        th = 0.5 * (lo + hi); p.reset(theta_deg=th); p.z = z0; p.cmd = math.radians(th); Ls = Pd = 0.0; n = 0
        for k in range(int(3.0 / MK.DT)):
            for _ in range(p.tick):
                r = p.step(free_heave=False); p.z = z0
                if k * MK.DT > 1.5: Ls += r["L"]; Pd += r["P_drag_W_strip"]; n += 1
        L = Ls / n + MK.BUOY
        if L > FP.MASS * MK.G: hi = th
        else: lo = th
    out[z0] = dict(theta_deg=th, P_drag_W=Pd / n, L_over_W=L / (FP.MASS * MK.G))
    print(f"z {z0:+.2f} m: kat {th:+.3f} st, P_drag {Pd / n:.3f} W, L/W {L / (FP.MASS * MK.G):.4f}", flush=True)
json.dump(out, open("OPOR_OD_GLEBOKOSCI_MODEL.json", "w"), indent=1)

