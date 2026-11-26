# 19.11 pomiar: ile kosztuje krok modelu Faltinsena B i kopia stanu (pod MPC z pelnym modelem w petli).
import os, time, copy, pickle
os.environ["MPC_W_A"] = "1"
import numpy as np, psutil
psutil.Process().cpu_affinity([21])
import mpc_komfort as MK
p, trim = MK.plant("S1", 100); p.reset(theta_deg=trim); p.cmd = np.radians(trim)
t0 = time.time()
for k in range(300):
    for _ in range(p.tick): r = p.step(free_heave=k > 100)
t1 = time.time(); print("tick", p.tick, "dt", p.dt, "krok sterowania [ms]", 1000 * (t1 - t0) / 300, "klucze r", list(r.keys()))
t0 = time.time()
for _ in range(20): q = copy.deepcopy(p)
print("deepcopy [ms]", 1000 * (time.time() - t0) / 20)
try:
    t0 = time.time()
    for _ in range(20): q = pickle.loads(pickle.dumps(p, -1))
    print("pickle [ms]", 1000 * (time.time() - t0) / 20)
except Exception as e: print("pickle blad", e)
q = copy.deepcopy(p); a = []; b = []
for k in range(50):
    for _ in range(p.tick): r1 = p.step(free_heave=True); r2 = q.step(free_heave=True)
    a.append(r1["L"]); b.append(r2["L"])
print("kopia zgodna:", float(np.max(np.abs(np.array(a) - np.array(b)))))
print("atrybuty:", [k for k in vars(p).keys()][:60])
