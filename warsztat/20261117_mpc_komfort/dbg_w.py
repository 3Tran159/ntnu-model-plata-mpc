import sys, math, numpy as np, psutil
psutil.Process().cpu_affinity([22])
sys.argv = ["mpc_falt_bridge.py", "-", "2.2", "0.2", "import"]
import mpc_falt_bridge as FB
MK = FB.MK; Z = MK.Z; FP = MK.FP
for tag, setT in (("bez T_WAVE", False), ("z T_WAVE", True)):
    if setT: Z.FP.T_WAVE = 5.0
    p = Z.FaltinsenPlant(wave_amp=0.727, wave_phase=0.4, **Z.VB); p.reset(theta_deg=3.0); W = []
    for k in range(400):
        p.cmd = math.radians(3.0)
        for _ in range(p.tick): p.step(free_heave=False)
        g = p.gust(p.F.xc, p.t); W.append(float(np.mean(g[1])))
    print(tag, "w std", np.std(W), "A0", getattr(p, "A0", None), "k", p.k, "z", p.z, "xc", np.mean(p.F.xc), flush=True)
