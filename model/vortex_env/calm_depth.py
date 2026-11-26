"""calm_depth.py - W MODELU WIROWYM: opor plata w wodzie spokojnej w funkcji wysokosci lotu z_ref (PID na z_ref, jak planowane przebiegi URANS).
1) przebieg zadany jak w URANS (start z = 0, zwolnienie 1 s, PID2 albo PID3, 8 s): przeregulowanie i czas ustalania -> wybor nastaw dla URANS
2) krzywa opor(z_ref) dla z_ref = 0 ... -0,7 m, model bazowy i poprawiony (poprawka uczona tylko w fali - tu orientacyjnie)
Wynik: CALM_DEPTH.json"""
import json, sys, pickle
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
from vortex_plant import Plant, SPAN
from mbpo_closedloop import ResidualPlant


def run(zref, kp, ki, resid=None, T=8.0, rel=1.0):
    P = ResidualPlant(resid=resid, wave_amp=1e-6); P.reset(theta_deg=3.5)
    ie = 0.0; rows = []
    for i in range(int(T / P.dt)):
        free = P.t >= rel
        if i % 10 == 0:
            e = zref - P.z; cmd = 3.5
            if free: ie = float(np.clip(ie + e * 0.01, -1, 1)); cmd = 3.5 + kp * e + ki * ie
            P.cmd = np.radians(np.clip(cmd, -7.5, 7.5))
        rows.append(P.step(free_heave=free))
    t = np.array([r["t"] for r in rows]); z = np.array([r["z"] for r in rows]); Pd = np.array([r["P_drag_W_strip"] for r in rows])
    w = t > T - 2.0
    return dict(z_min=float(z.min()), z_end=float(z[w].mean()), P_drag_W=float(Pd[w].mean()), overshoot_m=float(max(0.0, zref - z.min())) if zref < 0 else 0.0)


if __name__ == "__main__":
    resid = pickle.load(open(HERE / "mbpo_residual.pkl", "rb"))["ridge"]
    out = {"przeregulowanie": {}, "krzywa": {}}
    for name, kp, ki in (("PID2", 6.63, 1.18), ("PID3", 22.3, 7.25)):
        for zr in (-0.3, -0.6):
            r = run(zr, kp, ki, T=8.0); out["przeregulowanie"][f"{name}_z{zr}"] = r
            print(f"{name} z_ref {zr:+.1f}: z_min {r['z_min']:+.3f} m (przeregulowanie {r['overshoot_m']:.3f} m), z(ost. 2 s) {r['z_end']:+.3f} m", flush=True)
    for zr in (0.0, -0.1, -0.2, -0.3, -0.4, -0.5, -0.6, -0.7):
        b = run(zr, 6.63, 1.18, T=10.0); c = run(zr, 6.63, 1.18, resid=resid, T=10.0)
        out["krzywa"][f"{zr:+.1f}"] = dict(bazowy_W=b["P_drag_W"], poprawiony_W=c["P_drag_W"], z_bazowy=b["z_end"], z_poprawiony=c["z_end"])
        print(f"z_ref {zr:+.1f} m: moc oporu bazowy {b['P_drag_W']:.2f} W (z {b['z_end']:+.3f}), poprawiony {c['P_drag_W']:.2f} W (z {c['z_end']:+.3f})", flush=True)
    (HERE / "CALM_DEPTH.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
