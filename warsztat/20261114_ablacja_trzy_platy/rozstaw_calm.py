# Przeglad rozstawu w wodzie spokojnej: trzy platy, K0, interakcja rozbita na wiry (downwash 3D) i fale platu przedniego.
# Kopia petli z trzy_platy_interakcja.simulate z flagami; wynik ROZSTAW_CALM.json.
import sys, json
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
import trzy_platy_interakcja as TI
Z, FP, U, G_, BUOY = TI.Z, TI.FP, TI.U, TI.G_, TI.BUOY
AR, RHO, H, K0W, BP = TI.AR, TI.RHO, TI.H, TI.K0W, TI.BP


def calm(Lt, wiry, fala, T=20.0, skip=10.0):
    FP.MASS = Z.MASS100; trim = FP.TH_REF_DEG; L0 = FP.MASS * G_ - BUOY
    xs = np.array([-Lt / 2, 0.0, Lt / 2])
    P = [Z.FaltinsenPlant(wave_amp=0.0, **Z.VB) for _ in xs]
    for p in P: p.reset(theta_deg=trim); p.cmd = np.radians(trim); TI.patch(p)
    dt = P[0].dt; n = int(T / dt); q = P[0].q
    Gam0 = L0 / (RHO * U); CL0 = L0 / q; wfar = 2 * CL0 * U / (np.pi * AR)
    Gh = np.full((3, n + 1), Gam0); rec = []
    pairs = [(i, j, xs[j] - xs[i]) for j in range(3) for i in range(3) if xs[i] < xs[j]]
    dec = np.exp(-K0W * H)
    for it in range(n):
        for j in range(3): P[j]._du, P[j]._dw = 0.0, 0.0
        for i, j, s in pairs:
            r1 = Gh[i, max(0, it - int(round(s / U / dt)))] / Gam0; g2 = Gh[i, max(0, it - int(round(2 * s / U / dt)))]
            if wiry: P[j]._dw += -wfar * 0.5 * (1 + s / np.sqrt(s * s + (BP / 2) ** 2)) * r1
            if fala:
                A = 2 * g2 / U * dec
                P[j]._dw += -U * A * K0W * np.cos(K0W * s) * dec; P[j]._du += U * K0W * A * np.sin(K0W * s) * dec
        if it % P[0].tick == 0:
            w = np.array([float(np.mean(p.gust(p.F.xc, p.t)[1])) for p in P])
            for j, p in enumerate(P): p.cmd = np.radians(float(np.clip(trim - np.degrees(w[j] / U), -7.5, 7.5)))
        r = [p.step(free_heave=False) for p in P]
        for j in range(3): Gh[j, it + 1] = r[j]["L"] / (RHO * U)
        if it % 10 == 9: rec.append([r[0]["t"]] + [x["P_drag_W_strip"] for x in r] + [x["theta_deg"] for x in r])
    a = np.array(rec); a = a[a[:, 0] > skip]
    return dict(Lt=Lt, wiry=wiry, fala=fala, P=[round(float(a[:, 1 + j].mean()), 2) for j in range(3)],
                P_mean=round(float(a[:, 1:4].mean()), 2), th=[round(float(a[:, 4 + j].mean()), 2) for j in range(3)])


def job(a): return calm(*a)


if __name__ == "__main__":
    from multiprocessing import Pool
    LS = [10.0, 15.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 100.0]
    JOBS = [(L, w, f) for L in LS for (w, f) in ((True, True), (True, False), (False, True))]
    with Pool(6) as pool: R = pool.map(job, JOBS)
    (HERE / "ROZSTAW_CALM.json").write_text(json.dumps(R, indent=1))
    print("BEZ_INTERAKCJI 61.07 W/plat")
    for r in R: print(r)
